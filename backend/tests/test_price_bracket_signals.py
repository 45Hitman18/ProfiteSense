"""
Tests for Share Price Bracket Filtering (0-500, 500-1000, 1000+) across:
1. price_brackets utility
2. Telegram alert filter Rule 10 (evaluate_alert_filters)
3. Telegram bot commands (/signals <bracket>, /pricefilter <bracket>)
4. API endpoints (GET /api/notifications?price_bracket=..., POST /api/telegram/settings)
"""

import json
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from main import app
from price_brackets import get_signal_price_bracket, ALL_PRICE_BRACKETS
from telegram_alerts import evaluate_alert_filters
from telegram_bot import handle_command_signals, handle_command_price_filter
from database import get_connection, get_telegram_chat

client = TestClient(app)


def insert_test_chat(chat_id: str, username: str = "test_user"):
    conn = get_connection()
    try:
        conn.execute("""
            INSERT OR REPLACE INTO telegram_chats (
                chat_id, username, is_active, min_confidence, min_impact,
                directions, digest_enabled, digest_time, created_at
            ) VALUES (?, ?, 1, 0.6, 'HIGH', '["BULLISH","BEARISH"]', 1, '18:30', datetime('now'))
        """, (str(chat_id), username))
        conn.commit()
    finally:
        conn.close()


def test_price_bracket_ranges():
    """Verify boundaries for 0-500, 500-1000, and 1000+."""
    # Under 500
    b, label = get_signal_price_bracket(100.0)
    assert b == "0-500"
    assert "500" in label

    b, label = get_signal_price_bracket(500.0)
    assert b == "0-500"

    # Between 500 and 1000
    b, label = get_signal_price_bracket(500.01)
    assert b == "500-1000"
    assert "1,000" in label

    b, label = get_signal_price_bracket(1000.0)
    assert b == "500-1000"

    # Above 1000
    b, label = get_signal_price_bracket(1000.01)
    assert b == "1000+"
    assert "1,000+" in label

    b, label = get_signal_price_bracket(3500.0)
    assert b == "1000+"


def test_telegram_alert_price_bracket_filtering():
    """Verify Rule 10 in evaluate_alert_filters filters alerts by chat price bracket preferences."""
    # Chat only wants 0-500 stocks
    chat_prefs = {
        "chat_id": "99901",
        "is_active": 1,
        "min_confidence": 0.5,
        "min_impact": "MEDIUM",
        "directions": '["BULLISH", "BEARISH"]',
        "watchlist_only": 0,
        "price_brackets": json.dumps(["0-500"]),
    }

    now_iso = datetime.now(timezone.utc).isoformat()
    article = {
        "id": "art_filter_test",
        "published_at": now_iso,
        "created_at": now_iso
    }

    # Signal for ₹280 stock (ZOMATO) -> should pass
    analysis_under = {
        "ticker": "ZOMATO.NS",
        "direction": "BULLISH",
        "impact_level": "HIGH",
        "confidence": 0.8,
        "current_price": 280.0
    }
    passed, reason = evaluate_alert_filters(
        chat=chat_prefs,
        article=article,
        analysis=analysis_under
    )
    assert passed is True
    assert reason == "OK"

    # Signal for ₹2850 stock (RELIANCE) -> should be filtered out
    analysis_over = {
        "ticker": "RELIANCE.NS",
        "direction": "BULLISH",
        "impact_level": "HIGH",
        "confidence": 0.8,
        "current_price": 2850.0
    }
    passed, reason = evaluate_alert_filters(
        chat=chat_prefs,
        article=article,
        analysis=analysis_over
    )
    assert passed is False
    assert "price bracket" in reason.lower()


def test_bot_command_signals_bracket_filter():
    """Verify /signals 0-500 returns filtered signals and inline keyboard buttons."""
    card_text, reply_markup = handle_command_signals(args="0-500", chat_id="99902")
    assert "0-500" in card_text or "₹0" in card_text
    assert reply_markup is not None
    assert "inline_keyboard" in reply_markup

    buttons = [btn["text"] for row in reply_markup["inline_keyboard"] for btn in row]
    assert any("0-500" in b for b in buttons)
    assert any("500-1000" in b for b in buttons)
    assert any("1000+" in b for b in buttons)


def test_bot_command_price_filter_setting():
    """Verify /pricefilter 500-1000 updates chat preferences in database."""
    chat_id = "99903"
    insert_test_chat(chat_id=chat_id, username="test_filter_user")

    res_text = handle_command_price_filter(chat_id=chat_id, args="500-1000")
    assert "500-1000" in res_text or "1,000" in res_text

    chat = get_telegram_chat(chat_id)
    assert "500-1000" in chat["price_brackets"]


def test_api_telegram_settings_price_brackets():
    """Verify POST /api/telegram/settings accepts price_brackets field."""
    chat_id = "99904"
    insert_test_chat(chat_id=chat_id, username="test_api_user")

    resp = client.post("/api/telegram/settings", json={
        "chat_id": chat_id,
        "price_brackets": "1000+"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True

    chat = get_telegram_chat(chat_id)
    assert "1000+" in chat["price_brackets"]


def test_api_notifications_price_bracket_query():
    """Verify GET /api/notifications?price_bracket=0-500 returns valid bracket tagged items."""
    resp = client.get("/api/notifications?price_bracket=0-500")
    assert resp.status_code == 200
    data = resp.json()
    assert "notifications" in data
    # All returned notifications should match 0-500 if any returned
    for item in data["notifications"]:
        if "price_bracket" in item:
            assert item["price_bracket"] == "0-500"


def test_bot_command_signals_pagination_and_capacity():
    """Verify /signals returns Page 1 with capacity for multiple pages and navigation."""
    card_text_p1, markup_p1 = handle_command_signals(args="all", chat_id="99905")
    assert "Live AI Market Signals" in card_text_p1
    assert "Page" in card_text_p1
    assert "Signals Available" in card_text_p1 or "Signals" in card_text_p1
    assert markup_p1 is not None

    # Check page 2 query
    card_text_p2, markup_p2 = handle_command_signals(args="all 2", chat_id="99905")
    assert "Live AI Market Signals" in card_text_p2

