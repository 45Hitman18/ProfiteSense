"""
test_telegram_easy_commands.py — Unit Tests for Easiest Commands & 52-Week High/Loss Quote Engine
==================================================================================================
Tests:
  1. fetch_stock_quote_details: computes current price, 52W High, Loss from 52W High, 52W Low, gauge.
  2. handle_command_price: formats rich HTML card with mandatory disclaimer and inline keyboard.
  3. Direct share name lookup: user sends "RELIANCE" without slash -> receives 52W quote card.
  4. Command aliases: /p, /w, /uw, /signals, /buy.
  5. Interactive button callbacks: price_<ticker>, watch_<ticker>, unwatch_<ticker>, signals_refresh.
"""

import os
import sys
import pytest
from unittest.mock import MagicMock

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import config
from database import init_db, get_connection, get_telegram_chat
from telegram_bot import (
    fetch_stock_quote_details,
    handle_command_price,
    handle_command_signals,
    dispatch_telegram_update,
    create_link_code,
    MANDATORY_DISCLAIMER,
)
from telegram_client import TelegramClient


@pytest.fixture(autouse=True)
def setup_easy_commands_db():
    init_db()
    conn = get_connection()
    try:
        conn.execute("DELETE FROM telegram_chats WHERE chat_id LIKE 'test_easy_%'")
        conn.execute("DELETE FROM watchlist WHERE ticker IN ('RELIANCE.NS', 'TCS.NS', 'INFY.NS', 'TATAMOTORS.NS')")
        conn.commit()
    finally:
        conn.close()

    orig_enabled = getattr(config, "TELEGRAM_ENABLED", False)
    config.TELEGRAM_ENABLED = True
    yield
    config.TELEGRAM_ENABLED = orig_enabled


def link_easy_chat(chat_id="test_easy_user_1", username="easy_tester"):
    """Helper to link a chat for tests."""
    mock_client = MagicMock(spec=TelegramClient)
    mock_client.is_configured = True
    mock_client.send_message.return_value = {"ok": True, "result": {"message_id": 101}}
    mock_client.answer_callback_query.return_value = {"ok": True}

    info = create_link_code()
    code = info["code"]

    update = {
        "update_id": 1001,
        "message": {
            "message_id": 1,
            "chat": {"id": chat_id, "username": username},
            "text": f"/start {code}",
        }
    }
    dispatch_telegram_update(update, client=mock_client)
    return mock_client


def make_message_update(chat_id: str, text: str):
    return {
        "update_id": 2001,
        "message": {
            "message_id": 2,
            "chat": {"id": chat_id, "username": "easy_tester"},
            "text": text,
        }
    }


def make_callback_update(chat_id: str, callback_data: str):
    return {
        "update_id": 3001,
        "callback_query": {
            "id": "cb_query_999",
            "data": callback_data,
            "message": {
                "message_id": 3,
                "chat": {"id": chat_id, "username": "easy_tester"},
            }
        }
    }


def test_fetch_stock_quote_details_reliance():
    """Verify fetch_stock_quote_details returns complete 52W metrics for RELIANCE."""
    data = fetch_stock_quote_details("RELIANCE")
    assert data is not None
    assert data["symbol"] == "RELIANCE"
    assert data["price"] > 0
    assert data["high_52w"] >= data["price"]
    assert data["low_52w"] <= data["price"]
    assert data["loss_from_high_pct"] <= 0.01  # Loss from high is negative or zero
    assert data["loss_from_high_amt"] <= 0.01
    assert data["gain_from_low_pct"] >= -0.01  # Gain from low is positive or zero
    assert "🔘" in data["gauge"]
    assert 0 <= data["range_pct"] <= 100
    assert "Bracket" in data or "bracket" in data


def test_fetch_stock_quote_details_unknown_returns_none():
    """Verify unknown stock symbol returns None."""
    data = fetch_stock_quote_details("COMPLETELY_FAKE_XYZ_NOT_EXIST")
    assert data is None


def test_handle_command_price_rendering():
    """Verify handle_command_price card formatting and mandatory disclaimer."""
    card, markup = handle_command_price("TCS")
    assert card is not None
    assert "TCS" in card
    assert "52-Week High" in card
    assert "Loss from 52W High" in card
    assert "52-Week Low" in card
    assert "Gain from 52W Low" in card
    assert "52-Week Range Position" in card
    assert MANDATORY_DISCLAIMER in card
    assert markup is not None
    assert "inline_keyboard" in markup


def test_direct_share_name_lookup():
    """Verify user can simply type 'RELIANCE' without '/' to receive quote."""
    chat_id = "test_easy_direct_share"
    mock_client = link_easy_chat(chat_id=chat_id)

    # User sends plain stock name
    up = make_message_update(chat_id, "RELIANCE")
    reply = dispatch_telegram_update(up, client=mock_client)

    assert reply is not None
    assert "RELIANCE" in reply
    assert "52-Week High" in reply
    assert "Loss from 52W High" in reply
    assert MANDATORY_DISCLAIMER in reply

    # Verify send_message was called with reply_markup
    args, kwargs = mock_client.send_message.call_args
    sent_chat_id = args[0] if len(args) > 0 else kwargs.get("chat_id")
    sent_text = args[1] if len(args) > 1 else kwargs.get("text")
    assert sent_chat_id == chat_id
    assert "RELIANCE" in sent_text
    assert "inline_keyboard" in kwargs.get("reply_markup", {})


def test_direct_share_name_lookup_tata_motors():
    """Verify common aliases like 'Tata Motors' resolve to TATAMOTORS quote."""
    chat_id = "test_easy_tatamotors"
    mock_client = link_easy_chat(chat_id=chat_id)

    up = make_message_update(chat_id, "Tata Motors")
    reply = dispatch_telegram_update(up, client=mock_client)

    assert reply is not None
    assert "TATAMOTORS" in reply
    assert "52-Week High" in reply
    assert MANDATORY_DISCLAIMER in reply


def test_shortcut_command_p():
    """Verify /p RELIANCE works identically to /price RELIANCE."""
    chat_id = "test_easy_p_cmd"
    mock_client = link_easy_chat(chat_id=chat_id)

    up = make_message_update(chat_id, "/p RELIANCE")
    reply = dispatch_telegram_update(up, client=mock_client)

    assert reply is not None
    assert "RELIANCE" in reply
    assert "52-Week High" in reply
    assert "Loss from 52W High" in reply
    assert MANDATORY_DISCLAIMER in reply


def test_shortcut_command_w_and_uw():
    """Verify /w and /uw shortcuts for watchlist management."""
    chat_id = "test_easy_w_uw"
    mock_client = link_easy_chat(chat_id=chat_id)

    # /w INFY
    up_w = make_message_update(chat_id, "/w INFY")
    reply_w = dispatch_telegram_update(up_w, client=mock_client)
    assert "Added to Watchlist" in reply_w
    assert "INFY" in reply_w

    # /uw INFY
    up_uw = make_message_update(chat_id, "/uw INFY")
    reply_uw = dispatch_telegram_update(up_uw, client=mock_client)
    assert "Removed from Watchlist" in reply_uw
    assert "INFY" in reply_uw


def test_signals_command():
    """Verify /signals returns live AI trade recommendations."""
    chat_id = "test_easy_signals"
    mock_client = link_easy_chat(chat_id=chat_id)

    up = make_message_update(chat_id, "/signals")
    reply = dispatch_telegram_update(up, client=mock_client)

    assert reply is not None
    assert "AI" in reply
    assert MANDATORY_DISCLAIMER in reply


def test_inline_button_callbacks():
    """Verify watch, unwatch, and price refresh callback queries."""
    chat_id = "test_easy_callbacks"
    mock_client = link_easy_chat(chat_id=chat_id)

    # 1. Watch via callback
    up_cb_watch = make_callback_update(chat_id, "watch_TCS")
    dispatch_telegram_update(up_cb_watch, client=mock_client)
    assert mock_client.answer_callback_query.called
    assert "Added TCS" in mock_client.answer_callback_query.call_args[1]["text"]

    # 2. Refresh quote via callback
    mock_client.reset_mock()
    up_cb_price = make_callback_update(chat_id, "price_TCS")
    dispatch_telegram_update(up_cb_price, client=mock_client)
    assert mock_client.answer_callback_query.called
    assert "Refreshed TCS" in mock_client.answer_callback_query.call_args[1]["text"]
    assert mock_client.send_message.called
    c_args, c_kwargs = mock_client.send_message.call_args
    sent_text = c_args[1] if len(c_args) > 1 else c_kwargs.get("text", "")
    assert "TCS" in sent_text
    assert "52-Week High" in sent_text

    # 3. Unwatch via callback
    mock_client.reset_mock()
    up_cb_unwatch = make_callback_update(chat_id, "unwatch_TCS")
    dispatch_telegram_update(up_cb_unwatch, client=mock_client)
    assert mock_client.answer_callback_query.called
    assert "Removed TCS" in mock_client.answer_callback_query.call_args[1]["text"]
