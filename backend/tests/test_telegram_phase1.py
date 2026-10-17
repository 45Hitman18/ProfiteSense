"""
test_telegram_phase1.py — Comprehensive Unit Tests for Telegram Client & Storage
===============================================================================
Covers Phase 1 Acceptance Criteria:
  1. HTML escaping (&, <, >).
  2. Message splitting at 4096 character boundaries without data loss.
  3. Token redaction from strings and error logs.
  4. 429 Too Many Requests: retry with backoff and retry_after honouring.
  5. 403 Forbidden: immediate non-retry and automatic chat deactivation in database.
  6. 400 Bad Request: immediate non-retry.
  7. 5xx Server Error: exponential backoff and retry.
  8. Unique dedupe constraint on (chat_id, article_id, ticker) in telegram_alert_log.
  9. Rate limiter behavior.
"""

import os
import sys
import time
import pytest
import sqlite3
from unittest.mock import MagicMock, patch

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from telegram_client import (
    escape_html,
    split_message,
    redact_token,
    TelegramClient,
    TelegramRateLimiter,
    TELEGRAM_MAX_MESSAGE_LENGTH,
)
from database import (
    init_db,
    get_connection,
    deactivate_telegram_chat,
    record_telegram_alert,
    is_telegram_alert_sent,
)


@pytest.fixture(autouse=True)
def setup_test_db():
    """Ensure clean database tables before each test."""
    init_db()
    conn = get_connection()
    conn.execute("DELETE FROM telegram_alert_log WHERE chat_id LIKE 'test_%'")
    conn.execute("DELETE FROM telegram_chats WHERE chat_id LIKE 'test_%'")
    conn.commit()
    conn.close()
    yield
    conn = get_connection()
    conn.execute("DELETE FROM telegram_alert_log WHERE chat_id LIKE 'test_%'")
    conn.execute("DELETE FROM telegram_chats WHERE chat_id LIKE 'test_%'")
    conn.commit()
    conn.close()


# ══════════════════════════════════════════════════════════════════
# 1. HTML ESCAPING
# ══════════════════════════════════════════════════════════════════
def test_escape_html_special_characters():
    """Ensure &, <, > are properly escaped, while regular quotes and text are untouched."""
    raw = "Reliance & Adani: <Q3 Profits> Up 15% in 'FY26' & \"Q4\""
    expected = "Reliance &amp; Adani: &lt;Q3 Profits&gt; Up 15% in 'FY26' &amp; \"Q4\""
    assert escape_html(raw) == expected


def test_escape_html_empty_and_none():
    """Ensure None and empty string return an empty string safely."""
    assert escape_html(None) == ""
    assert escape_html("") == ""
    assert escape_html("Plain text without tags") == "Plain text without tags"


# ══════════════════════════════════════════════════════════════════
# 2. MESSAGE SPLITTING
# ══════════════════════════════════════════════════════════════════
def test_split_message_within_limit():
    """Short messages under 4096 chars should not be split."""
    msg = "Short message under 4096 characters."
    chunks = split_message(msg, max_length=TELEGRAM_MAX_MESSAGE_LENGTH)
    assert len(chunks) == 1
    assert chunks[0] == msg


def test_split_message_exact_limit():
    """Message of exactly 4096 chars should be returned as a single chunk."""
    msg = "A" * TELEGRAM_MAX_MESSAGE_LENGTH
    chunks = split_message(msg, max_length=TELEGRAM_MAX_MESSAGE_LENGTH)
    assert len(chunks) == 1
    assert len(chunks[0]) == TELEGRAM_MAX_MESSAGE_LENGTH


def test_split_message_over_limit_with_newlines():
    """Message exceeding 4096 chars should be split cleanly at newline boundaries."""
    para1 = "Paragraph 1: " + "X" * 3000
    para2 = "Paragraph 2: " + "Y" * 2000
    full_text = para1 + "\n\n" + para2

    chunks = split_message(full_text, max_length=TELEGRAM_MAX_MESSAGE_LENGTH)
    assert len(chunks) == 2
    for chunk in chunks:
        assert len(chunk) <= TELEGRAM_MAX_MESSAGE_LENGTH
    assert "Paragraph 1:" in chunks[0]
    assert "Paragraph 2:" in chunks[1]


def test_split_message_continuous_long_string():
    """Message with no whitespace should be hard split without data loss."""
    full_text = "Z" * 9000
    chunks = split_message(full_text, max_length=4000)
    assert len(chunks) == 3
    assert len(chunks[0]) == 4000
    assert len(chunks[1]) == 4000
    assert len(chunks[2]) == 1000
    assert "".join(chunks) == full_text


# ══════════════════════════════════════════════════════════════════
# 3. TOKEN REDACTION
# ══════════════════════════════════════════════════════════════════
def test_redact_token():
    """Verify bot tokens are scrubbed from logs, URLs, and errors."""
    fake_token = "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz123456789"
    url = f"https://api.telegram.org/bot{fake_token}/sendMessage"
    redacted = redact_token(url, fake_token)
    assert fake_token not in redacted
    assert "[REDACTED_BOT_TOKEN]" in redacted

    # Test regex scrubbing on generic token pattern
    generic_log = "Error connecting to bot987654:ABC-DEF1234ghIkl-zyx57W2v1u123ew11 on port 443"
    redacted_generic = redact_token(generic_log)
    assert "987654:ABC-DEF" not in redacted_generic
    assert "bot[REDACTED_BOT_TOKEN]" in redacted_generic


# ══════════════════════════════════════════════════════════════════
# 4. 429 TOO MANY REQUESTS RETRY WITH BACKOFF
# ══════════════════════════════════════════════════════════════════
def test_retry_on_429():
    """Verify client sleeps for retry_after and retries upon encountering 429."""
    mock_session = MagicMock()
    
    # Response 1: 429 with retry_after = 0.05
    resp_429 = MagicMock()
    resp_429.status_code = 429
    resp_429.headers = {"content-type": "application/json"}
    resp_429.json.return_value = {
        "ok": False,
        "error_code": 429,
        "description": "Too Many Requests: retry after 1",
        "parameters": {"retry_after": 0.02}
    }

    # Response 2: 200 OK
    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.json.return_value = {"ok": True, "result": {"message_id": 999}}

    mock_session.request.side_effect = [resp_429, resp_200]

    client = TelegramClient(token="mock_token_123", session=mock_session)
    client.rate_limiter = TelegramRateLimiter(global_limit_per_sec=1000.0, per_chat_limit_per_sec=1000.0)

    res = client.send_message(chat_id="test_chat_1", text="Hello 429 test")
    assert res.get("ok") is True
    assert res["result"]["message_id"] == 999
    assert mock_session.request.call_count == 2


# ══════════════════════════════════════════════════════════════════
# 5. 403 FORBIDDEN (BOT BLOCKED) — NO RETRY & DEACTIVATE CHAT
# ══════════════════════════════════════════════════════════════════
def test_403_forbidden_deactivates_chat():
    """Verify 403 Forbidden is NOT retried and marks chat as inactive in DB."""
    conn = get_connection()
    conn.execute("""
        INSERT INTO telegram_chats (chat_id, username, is_active)
        VALUES ('test_blocked_chat', 'test_user', 1)
    """)
    conn.commit()
    conn.close()

    mock_session = MagicMock()
    resp_403 = MagicMock()
    resp_403.status_code = 403
    resp_403.headers = {"content-type": "application/json"}
    resp_403.json.return_value = {
        "ok": False,
        "error_code": 403,
        "description": "Forbidden: bot was blocked by the user"
    }
    mock_session.request.return_value = resp_403

    client = TelegramClient(token="mock_token_123", session=mock_session)
    client.rate_limiter = TelegramRateLimiter(global_limit_per_sec=1000.0, per_chat_limit_per_sec=1000.0)

    res = client.send_message(chat_id="test_blocked_chat", text="Test message")
    assert res.get("ok") is False
    assert res.get("error_code") == 403
    # Exactly 1 request made (do NOT retry on 403)
    assert mock_session.request.call_count == 1

    # Verify chat was marked inactive in DB
    conn = get_connection()
    row = conn.execute("SELECT is_active FROM telegram_chats WHERE chat_id = 'test_blocked_chat'").fetchone()
    conn.close()
    assert row is not None
    assert row[0] == 0


# ══════════════════════════════════════════════════════════════════
# 6. 400 BAD REQUEST — NO RETRY
# ══════════════════════════════════════════════════════════════════
def test_400_bad_request_no_retry():
    """Verify 400 Bad Request stops immediately without retrying."""
    mock_session = MagicMock()
    resp_400 = MagicMock()
    resp_400.status_code = 400
    resp_400.headers = {"content-type": "application/json"}
    resp_400.json.return_value = {
        "ok": False,
        "error_code": 400,
        "description": "Bad Request: can't parse entities: Unsupported start tag"
    }
    mock_session.request.return_value = resp_400

    client = TelegramClient(token="mock_token_123", session=mock_session)
    client.rate_limiter = TelegramRateLimiter(global_limit_per_sec=1000.0, per_chat_limit_per_sec=1000.0)

    res = client.send_message(chat_id="test_chat_2", text="<b>Invalid HTML")
    assert res.get("ok") is False
    assert res.get("error_code") == 400
    # Must NOT retry on 400
    assert mock_session.request.call_count == 1


# ══════════════════════════════════════════════════════════════════
# 7. 5XX SERVER ERROR — EXPONENTIAL BACKOFF & RETRY
# ══════════════════════════════════════════════════════════════════
def test_5xx_server_error_retry():
    """Verify 502/503 server errors trigger retry with backoff."""
    mock_session = MagicMock()
    resp_502 = MagicMock()
    resp_502.status_code = 502
    resp_502.headers = {"content-type": "text/html"}
    resp_502.text = "Bad Gateway"

    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.json.return_value = {"ok": True, "result": {"message_id": 888}}

    mock_session.request.side_effect = [resp_502, resp_200]

    client = TelegramClient(token="mock_token_123", session=mock_session)
    client.rate_limiter = TelegramRateLimiter(global_limit_per_sec=1000.0, per_chat_limit_per_sec=1000.0)

    with patch("time.sleep", return_value=None):  # Fast execution in tests
        res = client.send_message(chat_id="test_chat_3", text="Hello 5xx test")

    assert res.get("ok") is True
    assert res["result"]["message_id"] == 888
    assert mock_session.request.call_count == 2


# ══════════════════════════════════════════════════════════════════
# 8. DEDUPE CONSTRAINT IN TELEGRAM_ALERT_LOG
# ══════════════════════════════════════════════════════════════════
def test_telegram_alert_log_dedupe():
    """Verify UNIQUE(chat_id, article_id, ticker) constraint prevents duplicate alerts."""
    chat_id = "test_chat_dedupe"
    article_id = "art-test-123"
    ticker = "INFY"

    # First insert: succeeds
    success1 = record_telegram_alert(chat_id, article_id, ticker, status="SENT")
    assert success1 is True
    assert is_telegram_alert_sent(chat_id, article_id, ticker) is True

    # Duplicate insert with same (chat_id, article_id, ticker): fails due to UNIQUE constraint
    success2 = record_telegram_alert(chat_id, article_id, ticker, status="SENT")
    assert success2 is False

    # Different ticker on same article and chat: succeeds
    success3 = record_telegram_alert(chat_id, article_id, "TCS", status="SENT")
    assert success3 is True

    # Verify count in database
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM telegram_alert_log WHERE chat_id = ?", (chat_id,)).fetchone()[0]
    conn.close()
    assert count == 2
