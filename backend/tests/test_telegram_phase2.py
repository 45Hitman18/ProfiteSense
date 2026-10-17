"""
test_telegram_phase2.py — Comprehensive Unit Tests for Telegram Chat Linking & Bot Commands
==========================================================================================
Covers Phase 2 Acceptance Criteria:
  1. Code expiry and single-use reuse prevention.
  2. Unknown / unlinked chats ignored (leak zero information).
  3. Allowlist enforcement via TELEGRAM_ALLOWED_CHAT_IDS.
  4. Each command's happy path:
     /start <code>, /help, /status, /watch, /unwatch, /list, /mute, /unmute,
     /minconf, /impact, /digest, /quiet, /stop.
  5. Bad input handling on all commands.
  6. Watchlist synchronization between Telegram and ProfitSense DB.
  7. Update offset persistence in telegram_state.
  8. POST /api/telegram/link-code FastAPI endpoint.
"""

import os
import sys
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from fastapi.testclient import TestClient
import config
from main import app
from database import (
    init_db,
    get_connection,
    get_telegram_chat,
)
from telegram_bot import (
    create_link_code,
    validate_and_consume_link_code,
    dispatch_telegram_update,
    get_stored_update_offset,
    set_stored_update_offset,
)
from telegram_client import TelegramClient



@pytest.fixture(autouse=True)
def setup_test_environment():
    """Ensure clean database tables and reset config overrides."""
    init_db()
    conn = get_connection()
    conn.execute("DELETE FROM telegram_link_codes")
    conn.execute("DELETE FROM telegram_chats WHERE chat_id LIKE 'test_%'")
    conn.execute("DELETE FROM watchlist WHERE notes = 'Added via Telegram Bot'")
    conn.execute("DELETE FROM telegram_state WHERE key = 'telegram_last_update_offset'")
    conn.commit()
    conn.close()

    orig_allowed = getattr(config, "TELEGRAM_ALLOWED_CHAT_IDS", [])
    config.TELEGRAM_ALLOWED_CHAT_IDS = []

    yield

    config.TELEGRAM_ALLOWED_CHAT_IDS = orig_allowed
    conn = get_connection()
    conn.execute("DELETE FROM telegram_link_codes")
    conn.execute("DELETE FROM telegram_chats WHERE chat_id LIKE 'test_%'")
    conn.execute("DELETE FROM watchlist WHERE notes = 'Added via Telegram Bot'")
    conn.execute("DELETE FROM telegram_state WHERE key = 'telegram_last_update_offset'")
    conn.commit()
    conn.close()


def make_update(chat_id: str, text: str, username: str = "trader1") -> dict:
    """Helper to build a Telegram update payload."""
    return {
        "update_id": 10001,
        "message": {
            "message_id": 555,
            "chat": {"id": chat_id, "username": username, "type": "private"},
            "from": {"id": chat_id, "username": username},
            "text": text,
            "date": int(datetime.now(timezone.utc).timestamp()),
        }
    }


# ══════════════════════════════════════════════════════════════════
# 1. LINK CODE CREATION, EXPIRY & REUSE PREVENTION
# ══════════════════════════════════════════════════════════════════
def test_link_code_happy_path_and_reuse():
    """Verify code can be generated, used once, and cannot be reused."""
    link_data = create_link_code()
    code = link_data["code"]
    assert len(code) == 8

    # First consumption: valid
    is_valid, consumed_code = validate_and_consume_link_code(code)
    assert is_valid is True
    assert consumed_code == code

    # Second consumption: rejected (ALREADY_USED)
    is_valid2, reason2 = validate_and_consume_link_code(code)
    assert is_valid2 is False
    assert reason2 == "ALREADY_USED"


def test_link_code_expired():
    """Verify expired codes are rejected."""
    conn = get_connection()
    expired_time = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    conn.execute("""
        INSERT INTO telegram_link_codes (code, created_at, expires_at, used)
        VALUES ('EXPIRED1', datetime('now'), ?, 0)
    """, (expired_time,))
    conn.commit()
    conn.close()

    is_valid, reason = validate_and_consume_link_code("EXPIRED1")
    assert is_valid is False
    assert reason == "EXPIRED"


def test_link_code_nonexistent():
    """Verify non-existent code returns INVALID_CODE."""
    is_valid, reason = validate_and_consume_link_code("NONEXIST")
    assert is_valid is False
    assert reason == "INVALID_CODE"


# ══════════════════════════════════════════════════════════════════
# 2. UNKNOWN / UNLINKED CHATS IGNORED (NO DATA LEAK)
# ══════════════════════════════════════════════════════════════════
def test_unlinked_chat_commands_ignored():
    """Any command other than /start from an unlinked chat must be ignored completely."""
    mock_client = MagicMock()
    unlinked_id = "test_unlinked_999"

    # Command: /watch RELIANCE
    up1 = make_update(unlinked_id, "/watch RELIANCE")
    res1 = dispatch_telegram_update(up1, client=mock_client)
    assert res1 is None
    assert mock_client.send_message.call_count == 0

    # Command: /status
    up2 = make_update(unlinked_id, "/status")
    res2 = dispatch_telegram_update(up2, client=mock_client)
    assert res2 is None
    assert mock_client.send_message.call_count == 0

    # Command: /list
    up3 = make_update(unlinked_id, "/list")
    res3 = dispatch_telegram_update(up3, client=mock_client)
    assert res3 is None
    assert mock_client.send_message.call_count == 0


def test_unlinked_chat_start_without_code_prompts_politely():
    """Sending /start without a code from an unlinked chat gives connection instructions."""
    mock_client = MagicMock()
    unlinked_id = "test_unlinked_888"

    up = make_update(unlinked_id, "/start")
    reply = dispatch_telegram_update(up, client=mock_client)

    assert reply is not None
    assert "Settings" in reply
    assert mock_client.send_message.call_count == 1
    # Verify chat was NOT linked as active
    chat = get_telegram_chat(unlinked_id)
    assert chat is None


# ══════════════════════════════════════════════════════════════════
# 3. ALLOWLIST ENFORCEMENT
# ══════════════════════════════════════════════════════════════════
def test_allowlist_enforcement():
    """When TELEGRAM_ALLOWED_CHAT_IDS is set, unauthorized chats must be refused."""
    config.TELEGRAM_ALLOWED_CHAT_IDS = ["test_allowed_111"]
    link_data = create_link_code()
    code = link_data["code"]

    mock_client = MagicMock()

    # Unauthorized chat tries to connect with valid code
    up_unauth = make_update("test_unauth_222", f"/start {code}")
    reply_unauth = dispatch_telegram_update(up_unauth, client=mock_client)
    assert "Access Restricted" in reply_unauth
    assert get_telegram_chat("test_unauth_222") is None

    # Authorized chat connects
    up_auth = make_update("test_allowed_111", f"/start {code}")
    reply_auth = dispatch_telegram_update(up_auth, client=mock_client)
    assert "ProfitSense Alerts Connected" in reply_auth
    chat = get_telegram_chat("test_allowed_111")
    assert chat is not None
    assert chat["is_active"] == 1


# ══════════════════════════════════════════════════════════════════
# 4. CHAT LINKING & COMMAND HAPPY PATHS
# ══════════════════════════════════════════════════════════════════
def link_test_chat(chat_id: str = "test_linked_chat_1", username: str = "alpha_trader") -> TelegramClient:
    """Helper to register and link a chat for command testing."""
    link_data = create_link_code()
    mock_client = MagicMock()
    up = make_update(chat_id, f"/start {link_data['code']}", username=username)
    reply = dispatch_telegram_update(up, client=mock_client)
    assert "Connected" in reply
    return mock_client


def test_command_start_and_status():
    """Verify /start links chat and /status reflects initial configuration."""
    chat_id = "test_status_chat"
    mock_client = link_test_chat(chat_id=chat_id)

    up_status = make_update(chat_id, "/status")
    reply = dispatch_telegram_update(up_status, client=mock_client)
    assert "ProfitSense Alert Preferences" in reply
    assert "Active 🟢" in reply
    assert "HIGH" in reply
    assert "60%" in reply
    assert "18:30 IST" in reply
    assert "AI/model estimate — not investment advice." in reply


def test_command_help():
    """Verify /help returns complete command reference."""
    chat_id = "test_help_chat"
    mock_client = link_test_chat(chat_id=chat_id)

    up = make_update(chat_id, "/help")
    reply = dispatch_telegram_update(up, client=mock_client)
    assert "/watch" in reply
    assert "/unwatch" in reply
    assert "/mute" in reply
    assert "/minconf" in reply
    assert "/quiet" in reply
    assert "AI/model estimate — not investment advice." in reply


def test_command_watch_unwatch_list():
    """Verify /watch adds to watchlist DB, /list displays it, and /unwatch removes it."""
    chat_id = "test_watch_chat"
    mock_client = link_test_chat(chat_id=chat_id)

    # 1. Watch valid ticker
    up_watch = make_update(chat_id, "/watch RELIANCE")
    reply_watch = dispatch_telegram_update(up_watch, client=mock_client)
    assert "Added to Watchlist" in reply_watch
    assert "RELIANCE" in reply_watch

    # Verify presence in database
    conn = get_connection()
    row = conn.execute("SELECT ticker, company_name FROM watchlist WHERE ticker LIKE 'RELIANCE%'").fetchone()
    conn.close()
    assert row is not None

    # 2. List watchlist
    up_list = make_update(chat_id, "/list")
    reply_list = dispatch_telegram_update(up_list, client=mock_client)
    assert "Tracked Watchlist" in reply_list
    assert "RELIANCE" in reply_list

    # 3. Unwatch
    up_unwatch = make_update(chat_id, "/unwatch RELIANCE")
    reply_unwatch = dispatch_telegram_update(up_unwatch, client=mock_client)
    assert "Removed from Watchlist" in reply_unwatch

    # Verify removal from database
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM watchlist WHERE ticker LIKE 'RELIANCE%'").fetchone()[0]
    conn.close()
    assert count == 0


def test_command_mute_and_unmute():
    """Verify /mute sets muted_until and /unmute clears it."""
    chat_id = "test_mute_chat"
    mock_client = link_test_chat(chat_id=chat_id)

    # Mute for 2 hours
    up_mute = make_update(chat_id, "/mute 2h")
    reply_mute = dispatch_telegram_update(up_mute, client=mock_client)
    assert "Alerts Muted" in reply_mute
    assert "IST" in reply_mute

    chat = get_telegram_chat(chat_id)
    assert chat["muted_until"] is not None

    # Unmute
    up_unmute = make_update(chat_id, "/unmute")
    reply_unmute = dispatch_telegram_update(up_unmute, client=mock_client)
    assert "Alerts Resumed" in reply_unmute

    chat = get_telegram_chat(chat_id)
    assert chat["muted_until"] is None


def test_command_minconf():
    """Verify /minconf updates confidence filter in database."""
    chat_id = "test_minconf_chat"
    mock_client = link_test_chat(chat_id=chat_id)

    up = make_update(chat_id, "/minconf 75")
    reply = dispatch_telegram_update(up, client=mock_client)
    assert "75%" in reply

    chat = get_telegram_chat(chat_id)
    assert chat["min_confidence"] == 0.75


def test_command_impact():
    """Verify /impact updates event impact level."""
    chat_id = "test_impact_chat"
    mock_client = link_test_chat(chat_id=chat_id)

    up = make_update(chat_id, "/impact medium")
    reply = dispatch_telegram_update(up, client=mock_client)
    assert "MEDIUM" in reply

    chat = get_telegram_chat(chat_id)
    assert chat["min_impact"] == "MEDIUM"


def test_command_digest():
    """Verify /digest toggles and sets time."""
    chat_id = "test_digest_chat"
    mock_client = link_test_chat(chat_id=chat_id)

    # Disable
    up_off = make_update(chat_id, "/digest off")
    reply_off = dispatch_telegram_update(up_off, client=mock_client)
    assert "Disabled" in reply_off
    assert get_telegram_chat(chat_id)["digest_enabled"] == 0

    # Set time
    up_time = make_update(chat_id, "/digest 19:15")
    reply_time = dispatch_telegram_update(up_time, client=mock_client)
    assert "19:15 IST" in reply_time
    chat = get_telegram_chat(chat_id)
    assert chat["digest_enabled"] == 1
    assert chat["digest_time"] == "19:15"


def test_command_quiet():
    """Verify /quiet sets quiet window and /quiet off clears it."""
    chat_id = "test_quiet_chat"
    mock_client = link_test_chat(chat_id=chat_id)

    # Set quiet window
    up_quiet = make_update(chat_id, "/quiet 23:00-06:30")
    reply_quiet = dispatch_telegram_update(up_quiet, client=mock_client)
    assert "23:00 and 06:30 IST" in reply_quiet
    chat = get_telegram_chat(chat_id)
    assert chat["quiet_start"] == "23:00"
    assert chat["quiet_end"] == "06:30"

    # Disable quiet window
    up_off = make_update(chat_id, "/quiet off")
    reply_off = dispatch_telegram_update(up_off, client=mock_client)
    assert "Disabled" in reply_off
    chat = get_telegram_chat(chat_id)
    assert chat["quiet_start"] is None
    assert chat["quiet_end"] is None


def test_command_stop():
    """Verify /stop deactivates chat."""
    chat_id = "test_stop_chat"
    mock_client = link_test_chat(chat_id=chat_id)

    up = make_update(chat_id, "/stop")
    reply = dispatch_telegram_update(up, client=mock_client)
    assert "Deactivated" in reply

    chat = get_telegram_chat(chat_id)
    assert chat["is_active"] == 0


# ══════════════════════════════════════════════════════════════════
# 5. BAD INPUT HANDLING
# ══════════════════════════════════════════════════════════════════
def test_bad_input_handling():
    """Verify graceful error messages for malformed arguments."""
    chat_id = "test_bad_input_chat"
    mock_client = link_test_chat(chat_id=chat_id)

    # /watch unknown ticker
    up_w1 = make_update(chat_id, "/watch UNKNOWN_RANDOM_XYZ")
    assert "Unknown Stock" in dispatch_telegram_update(up_w1, client=mock_client)

    # /watch empty
    up_w2 = make_update(chat_id, "/watch")
    assert "Usage" in dispatch_telegram_update(up_w2, client=mock_client)

    # /mute invalid format
    up_m = make_update(chat_id, "/mute invalid")
    assert "Invalid Duration" in dispatch_telegram_update(up_m, client=mock_client)

    # /minconf invalid range
    up_mc = make_update(chat_id, "/minconf 250")
    assert "Invalid Percentage" in dispatch_telegram_update(up_mc, client=mock_client)

    # /impact invalid
    up_imp = make_update(chat_id, "/impact extreme")
    assert "Invalid Impact Level" in dispatch_telegram_update(up_imp, client=mock_client)

    # /quiet invalid format
    up_q = make_update(chat_id, "/quiet 99:99")
    assert "Invalid Format" in dispatch_telegram_update(up_q, client=mock_client)


# ══════════════════════════════════════════════════════════════════
# 6. UPDATE OFFSET STORAGE
# ══════════════════════════════════════════════════════════════════
def test_update_offset_persistence():
    """Verify telegram_last_update_offset persists across queries."""
    assert get_stored_update_offset() is None
    set_stored_update_offset(10500)
    assert get_stored_update_offset() == 10500
    set_stored_update_offset(10505)
    assert get_stored_update_offset() == 10505


# ══════════════════════════════════════════════════════════════════
# 7. FASTAPI /api/telegram/link-code ENDPOINT
# ══════════════════════════════════════════════════════════════════
def test_api_link_code_endpoint():
    """Verify POST /api/telegram/link-code generates valid link code and deep link structure."""
    client = TestClient(app)
    resp = client.post("/api/telegram/link-code")
    assert resp.status_code == 200
    data = resp.json()
    assert "code" in data
    assert len(data["code"]) == 8
    assert "expires_at" in data
    assert "deep_link" in data
