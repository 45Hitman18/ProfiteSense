"""
test_telegram_phase3.py — Comprehensive Unit Tests for Telegram Alert Dispatcher & Digest Engine
================================================================================================
Covers Phase 3 Acceptance Criteria:
  1. Deduplication via telegram_alert_log (chat_id, article_id, ticker).
  2. Quiet hours filtering, including standard and midnight-crossing windows.
  3. Mute duration timer checking and expiry.
  4. Stale news skipping (>6 hours).
  5. Minimum impact level filtering (HIGH / MEDIUM / ALL).
  6. Minimum confidence filtering.
  7. Direction filtering (BULLISH / BEARISH / ALL).
  8. Watchlist-only filtering.
  9. Hourly rate capping (10 alerts/hour max per chat).
 10. Alert message rendering with HTML styling, model predictions, inline keyboard buttons.
 11. Evening Daily Digest generation, scheduling, and single-day deduplication.
 12. Failure tolerance (Telegram API exceptions never crash the pipeline).
"""

import os
import sys
import pytest
import sqlite3
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import config
from database import (
    init_db,
    get_connection,
    record_telegram_alert,
    is_telegram_alert_sent,
    count_recent_telegram_alerts,
)
from telegram_alerts import (
    is_muted,
    is_quiet_hours,
    is_stale_news,
    evaluate_alert_filters,
    format_signal_alert,
    format_daily_digest,
    dispatch_signal_alert_for_article,
    dispatch_all_pending_alerts,
    check_and_send_daily_digests,
    MANDATORY_DISCLAIMER,
    IST_TZ,
)
from telegram_client import TelegramClient


@pytest.fixture(autouse=True)
def setup_test_db():
    """Ensure clean test data in telegram tables and isolate from live chats."""
    init_db()
    conn = get_connection()
    try:
        # Temporarily deactivate any non-test chats so tests only dispatch to test chats
        conn.execute("UPDATE telegram_chats SET is_active = 0 WHERE chat_id NOT LIKE 'test_p3_%'")
        conn.execute("DELETE FROM telegram_chats WHERE chat_id LIKE 'test_p3_%'")
        conn.execute("DELETE FROM telegram_alert_log WHERE chat_id LIKE 'test_p3_%'")
        conn.execute("DELETE FROM analysis WHERE article_id LIKE 'art_test_p3_%'")
        conn.execute("DELETE FROM articles WHERE id LIKE 'art_test_p3_%'")
        conn.execute("DELETE FROM watchlist WHERE ticker IN ('RELIANCE.NS', 'TCS.NS', 'INFY.NS')")
        conn.commit()
    finally:
        conn.close()

    orig_enabled = getattr(config, "TELEGRAM_ENABLED", False)
    config.TELEGRAM_ENABLED = True
    yield
    config.TELEGRAM_ENABLED = orig_enabled
    # Restore live chats
    conn = get_connection()
    try:
        conn.execute("UPDATE telegram_chats SET is_active = 1 WHERE chat_id NOT LIKE 'test_p3_%'")
        conn.commit()
    finally:
        conn.close()



def insert_test_chat(
    chat_id: str = "test_p3_chat1",
    is_active: int = 1,
    muted_until: str = None,
    quiet_start: str = None,
    quiet_end: str = None,
    min_confidence: float = 0.6,
    min_impact: str = "HIGH",
    directions: str = '["BULLISH","BEARISH"]',
    watchlist_only: int = 0,
    digest_enabled: int = 1,
    digest_time: str = "18:30"
):
    conn = get_connection()
    conn.execute("""
        INSERT OR REPLACE INTO telegram_chats (
            chat_id, username, is_active, muted_until, quiet_start, quiet_end,
            min_confidence, min_impact, directions, watchlist_only, digest_enabled, digest_time
        ) VALUES (?, 'tester', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (chat_id, is_active, muted_until, quiet_start, quiet_end,
          min_confidence, min_impact, directions, watchlist_only, digest_enabled, digest_time))
    conn.commit()
    conn.close()


def insert_test_article(
    article_id: str = "art_test_p3_001",
    ticker: str = "RELIANCE.NS",
    company_name: str = "Reliance Industries Ltd",
    title: str = "Reliance announces mega green energy expansion",
    impact_level: str = "HIGH",
    direction: str = "BULLISH",
    confidence: float = 0.85,
    published_at: str = None
):
    if published_at is None:
        published_at = datetime.now(timezone.utc).isoformat()

    conn = get_connection()
    conn.execute("""
        INSERT OR REPLACE INTO articles (id, title, summary, source, url, published_at, category, raw_content)
        VALUES (?, ?, 'Summary text here', 'Economic Times', 'https://example.com/news1', ?, 'Indian Equities', 'Full article content')
    """, (article_id, title, published_at))

    conn.execute("""
        INSERT OR REPLACE INTO analysis (
            article_id, ticker, company_name, sentiment, sentiment_score,
            direction, impact_level, confidence, event_type, event_display, sector, reason_explanation
        ) VALUES (?, ?, ?, 'Positive', 0.65, ?, ?, ?, 'EXPANSION', 'Expansion & Capex', 'Energy', 'High-confidence expansion catalyst')
    """, (article_id, ticker, company_name, direction, impact_level, confidence))

    conn.commit()
    conn.close()


# ══════════════════════════════════════════════════════════════════
# 1. FILTER UNIT TESTS
# ══════════════════════════════════════════════════════════════════
def test_is_muted():
    now = datetime(2026, 10, 5, 12, 0, 0, tzinfo=timezone.utc)

    # Active mute in future
    chat_muted = {"muted_until": "2026-10-05T14:00:00+00:00"}
    assert is_muted(chat_muted, now=now) is True

    # Expired mute in past
    chat_expired = {"muted_until": "2026-10-05T10:00:00+00:00"}
    assert is_muted(chat_expired, now=now) is False

    # Not muted
    assert is_muted({}, now=now) is False
    assert is_muted({"muted_until": None}, now=now) is False


def test_is_quiet_hours_standard():
    # Quiet between 13:00 and 15:00 IST
    t_inside = datetime(2026, 10, 5, 14, 0, 0, tzinfo=IST_TZ)
    t_before = datetime(2026, 10, 5, 12, 59, 0, tzinfo=IST_TZ)
    t_after = datetime(2026, 10, 5, 15, 0, 0, tzinfo=IST_TZ)

    assert is_quiet_hours("13:00", "15:00", now=t_inside) is True
    assert is_quiet_hours("13:00", "15:00", now=t_before) is False
    assert is_quiet_hours("13:00", "15:00", now=t_after) is False


def test_is_quiet_hours_midnight_crossing():
    # Quiet from 22:00 to 07:00 IST (crosses midnight)
    t_night = datetime(2026, 10, 5, 23, 30, 0, tzinfo=IST_TZ)
    t_early_morn = datetime(2026, 10, 6, 4, 15, 0, tzinfo=IST_TZ)
    t_daytime = datetime(2026, 10, 5, 14, 0, 0, tzinfo=IST_TZ)
    t_exact_start = datetime(2026, 10, 5, 22, 0, 0, tzinfo=IST_TZ)
    t_exact_end = datetime(2026, 10, 6, 7, 0, 0, tzinfo=IST_TZ)

    assert is_quiet_hours("22:00", "07:00", now=t_night) is True
    assert is_quiet_hours("22:00", "07:00", now=t_early_morn) is True
    assert is_quiet_hours("22:00", "07:00", now=t_daytime) is False
    assert is_quiet_hours("22:00", "07:00", now=t_exact_start) is True
    assert is_quiet_hours("22:00", "07:00", now=t_exact_end) is False


def test_is_stale_news():
    now = datetime(2026, 10, 5, 12, 0, 0, tzinfo=timezone.utc)

    # 2 hours old -> Fresh
    fresh_date = "2026-10-05T10:00:00+00:00"
    assert is_stale_news(fresh_date, max_age_hours=6, now=now) is False

    # 8 hours old -> Stale
    stale_date = "2026-10-05T04:00:00+00:00"
    assert is_stale_news(stale_date, max_age_hours=6, now=now) is True

    # Empty date
    assert is_stale_news(None, max_age_hours=6, now=now) is False


def test_evaluate_alert_filters_deduplication():
    chat = {"chat_id": "test_p3_chat1", "is_active": 1, "min_impact": "HIGH", "min_confidence": 0.6}
    article = {"id": "art_100", "published_at": datetime.now(timezone.utc).isoformat()}
    analysis = {"ticker": "TCS.NS", "impact_level": "HIGH", "confidence": 0.8, "direction": "BULLISH"}

    # First time -> Allowed
    ok, reason = evaluate_alert_filters(chat, article, analysis)
    assert ok is True

    # Record alert as sent
    record_telegram_alert("test_p3_chat1", "art_100", "TCS.NS", status="SENT")

    # Second time -> Rejected due to dedupe
    ok2, reason2 = evaluate_alert_filters(chat, article, analysis)
    assert ok2 is False
    assert "dedupe" in reason2.lower()


def test_evaluate_alert_filters_impact_and_confidence():
    chat = {"chat_id": "test_p3_chat1", "is_active": 1, "min_impact": "HIGH", "min_confidence": 0.70}
    article = {"id": "art_101", "published_at": datetime.now(timezone.utc).isoformat()}

    # Low impact -> Rejected
    an_low = {"ticker": "INFY.NS", "impact_level": "LOW", "confidence": 0.85, "direction": "BULLISH"}
    ok_low, _ = evaluate_alert_filters(chat, article, an_low)
    assert ok_low is False

    # Medium impact -> Rejected (chat requires HIGH)
    an_med = {"ticker": "INFY.NS", "impact_level": "MEDIUM", "confidence": 0.85, "direction": "BULLISH"}
    ok_med, _ = evaluate_alert_filters(chat, article, an_med)
    assert ok_med is False

    # Low confidence -> Rejected
    an_low_conf = {"ticker": "INFY.NS", "impact_level": "HIGH", "confidence": 0.55, "direction": "BULLISH"}
    ok_conf, _ = evaluate_alert_filters(chat, article, an_low_conf)
    assert ok_conf is False

    # High impact & High confidence -> Accepted
    an_ok = {"ticker": "INFY.NS", "impact_level": "HIGH", "confidence": 0.80, "direction": "BULLISH"}
    ok_high, _ = evaluate_alert_filters(chat, article, an_ok)
    assert ok_high is True


def test_evaluate_alert_filters_direction():
    chat = {
        "chat_id": "test_p3_chat1",
        "is_active": 1,
        "min_impact": "ALL",
        "min_confidence": 0.5,
        "directions": '["BULLISH"]'
    }
    article = {"id": "art_102", "published_at": datetime.now(timezone.utc).isoformat()}

    an_bear = {"ticker": "WIPRO.NS", "impact_level": "HIGH", "confidence": 0.8, "direction": "BEARISH"}
    ok_bear, _ = evaluate_alert_filters(chat, article, an_bear)
    assert ok_bear is False

    an_bull = {"ticker": "WIPRO.NS", "impact_level": "HIGH", "confidence": 0.8, "direction": "BULLISH"}
    ok_bull, _ = evaluate_alert_filters(chat, article, an_bull)
    assert ok_bull is True


def test_evaluate_alert_filters_watchlist_only():
    chat = {
        "chat_id": "test_p3_chat1",
        "is_active": 1,
        "min_impact": "ALL",
        "min_confidence": 0.5,
        "watchlist_only": 1
    }
    article = {"id": "art_103", "published_at": datetime.now(timezone.utc).isoformat()}
    an = {"ticker": "TATAMOTORS.NS", "impact_level": "HIGH", "confidence": 0.8, "direction": "BULLISH"}

    # Not in watchlist
    ok_not_wl, _ = evaluate_alert_filters(chat, article, an, watchlist_tickers={"RELIANCE", "TCS"})
    assert ok_not_wl is False

    # In watchlist
    ok_wl, _ = evaluate_alert_filters(chat, article, an, watchlist_tickers={"TATAMOTORS", "TCS"})
    assert ok_wl is True


def test_evaluate_alert_filters_hourly_cap():
    chat_id = "test_p3_chat_cap"
    chat = {"chat_id": chat_id, "is_active": 1, "min_impact": "ALL", "min_confidence": 0.5}
    article = {"id": "art_cap_11", "published_at": datetime.now(timezone.utc).isoformat()}
    an = {"ticker": "SBIN.NS", "impact_level": "HIGH", "confidence": 0.8, "direction": "BULLISH"}

    # Insert 10 alerts in the last 10 minutes
    for i in range(10):
        record_telegram_alert(chat_id, f"art_cap_{i}", "SBIN.NS", status="SENT")

    assert count_recent_telegram_alerts(chat_id, minutes=60) == 10

    # 11th alert must be rejected
    ok, reason = evaluate_alert_filters(chat, article, an)
    assert ok is False
    assert "hourly alert cap" in reason.lower()


# ══════════════════════════════════════════════════════════════════
# 2. MESSAGE RENDERING & COMPLIANCE TESTS
# ══════════════════════════════════════════════════════════════════
def test_format_signal_alert_rendering():
    article = {
        "id": "art_render_1",
        "title": "Reliance Q2 Results Beat Estimates with 15% Profit Surge",
        "summary": "Operating margins expanded across oil and retail divisions.",
        "published_at": "2026-10-05T09:15:00+00:00"
    }
    analysis = {
        "ticker": "RELIANCE.NS",
        "company_name": "Reliance Industries Limited",
        "impact_level": "HIGH",
        "direction": "BULLISH",
        "confidence": 0.88,
        "event_type": "EARNINGS_SURPRISE",
        "event_display": "Earnings Beat",
        "sector": "Energy & Retail",
        "reason_explanation": "Net profit up 15% YoY surpassing consensus estimates."
    }
    preds = {
        "1d": {"ensemble": "Positive"},
        "3d": {"ensemble": "Positive"}
    }

    text, markup = format_signal_alert(article, analysis, preds)

    # Compliance disclaimer check (HARD RULE)
    assert text.endswith(f"<i>{MANDATORY_DISCLAIMER}</i>")
    assert MANDATORY_DISCLAIMER in text

    # Signal badges & data
    assert "🟢 <b>BULLISH SIGNAL | RELIANCE</b>" in text
    assert "Reliance Industries Limited" in text
    assert "1D Horizon:" in text
    assert "Positive" in text
    assert "Confidence:</b> 88%" in text

    # Buttons
    assert "inline_keyboard" in markup
    buttons = markup["inline_keyboard"]
    assert len(buttons) == 2
    # Row 1: Open in ProfitSense
    assert buttons[0][0]["text"] == "📊 Open in ProfitSense"
    assert "article=art_render_1" in buttons[0][0]["url"]
    # Row 2: Mute and Unwatch
    assert buttons[1][0]["callback_data"] == "mute_2h"
    assert buttons[1][1]["callback_data"] == "unwatch_RELIANCE"


def test_format_daily_digest_rendering():
    chat = {"chat_id": "test_p3_chat1"}
    top_articles = [
        {"ticker": "RELIANCE.NS", "title": "Mega green hydrogen capex launched", "direction": "BULLISH"},
        {"ticker": "INFY.NS", "title": "US BFSI slowdown dampens guidance", "direction": "BEARISH"},
    ]
    stats = {"total_articles": 18, "bullish_count": 11, "bearish_count": 7}

    digest_text = format_daily_digest(chat, top_articles, stats)

    # Compliance disclaimer check
    assert digest_text.endswith(f"<i>{MANDATORY_DISCLAIMER}</i>")
    assert "ProfitSense Daily Market Digest" in digest_text
    assert "Bullish Signals: 🟢 <b>11</b>" in digest_text
    assert "Bearish Signals: 🔴 <b>7</b>" in digest_text
    assert "RELIANCE" in digest_text
    assert "INFY" in digest_text


# ══════════════════════════════════════════════════════════════════
# 3. END-TO-END DISPATCH & DIGEST EXECUTION
# ══════════════════════════════════════════════════════════════════
def test_dispatch_signal_alert_end_to_end():
    insert_test_chat("test_p3_dispatch_user", min_impact="HIGH", min_confidence=0.6)
    insert_test_article("art_test_p3_001", ticker="RELIANCE.NS", impact_level="HIGH", confidence=0.85)

    mock_client = MagicMock(spec=TelegramClient)
    mock_client.is_configured = True
    mock_client.send_message.return_value = {"ok": True, "result": {"message_id": 999}}

    # Dispatch alert
    res = dispatch_signal_alert_for_article("art_test_p3_001", client=mock_client)
    assert res["status"] == "success"
    assert res["sent_count"] == 1
    assert mock_client.send_message.called

    sent_call_args = mock_client.send_message.call_args[1]
    assert sent_call_args["chat_id"] == "test_p3_dispatch_user"
    assert "RELIANCE" in sent_call_args["text"]
    assert MANDATORY_DISCLAIMER in sent_call_args["text"]
    assert "inline_keyboard" in sent_call_args["reply_markup"]

    # Verify database log recorded
    assert is_telegram_alert_sent("test_p3_dispatch_user", "art_test_p3_001", "RELIANCE") is True

    # Immediate second dispatch must skip (deduplication)
    mock_client.reset_mock()
    res2 = dispatch_signal_alert_for_article("art_test_p3_001", client=mock_client)
    assert res2["sent_count"] == 0
    assert not mock_client.send_message.called


def test_check_and_send_daily_digests():
    insert_test_chat("test_p3_digest_user", digest_enabled=1, digest_time="18:30")
    insert_test_article("art_test_p3_002", ticker="TCS.NS", impact_level="HIGH", confidence=0.8)

    mock_client = MagicMock(spec=TelegramClient)
    mock_client.is_configured = True
    mock_client.send_message.return_value = {"ok": True, "result": {"message_id": 1000}}

    # At 18:30 IST
    ist_1830 = datetime(2026, 10, 5, 18, 30, 0, tzinfo=IST_TZ)
    sent = check_and_send_daily_digests(now=ist_1830, client=mock_client)
    assert sent == 1
    assert mock_client.send_message.called

    call_args = mock_client.send_message.call_args[1]
    assert "Daily Market Digest" in call_args["text"]
    assert MANDATORY_DISCLAIMER in call_args["text"]

    # Second check at same time on same day -> must not resend
    mock_client.reset_mock()
    sent_dup = check_and_send_daily_digests(now=ist_1830, client=mock_client)
    assert sent_dup == 0
    assert not mock_client.send_message.called


def test_telegram_failure_does_not_crash():
    """Telegram network or HTTP failure must be logged gracefully without crashing."""
    insert_test_chat("test_p3_fail_user", min_impact="HIGH", min_confidence=0.6)
    insert_test_article("art_test_p3_fail", ticker="INFY.NS", impact_level="HIGH", confidence=0.85)

    mock_client = MagicMock(spec=TelegramClient)
    mock_client.is_configured = True
    # Simulate network exception
    mock_client.send_message.side_effect = Exception("Simulated connection reset")

    # Should not throw exception
    res = dispatch_signal_alert_for_article("art_test_p3_fail", client=mock_client)
    assert res["status"] == "success"
    assert res["sent_count"] == 0

    # Verify failure recorded in log
    conn = get_connection()
    cur = conn.execute("""
        SELECT status, error FROM telegram_alert_log
        WHERE chat_id = 'test_p3_fail_user' AND article_id = 'art_test_p3_fail'
    """)
    row = cur.fetchone()
    conn.close()
    assert row is not None
    assert row[0] == "FAILED"
    assert "Simulated connection reset" in row[1]
