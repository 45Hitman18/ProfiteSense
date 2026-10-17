"""
test_telegram_phase4.py — Unit Tests for Telegram Management API & Admin Control
================================================================================
Covers Phase 4 Acceptance Criteria:
  1. GET /api/telegram/status returns configuration, bot info, chats, and never leaks TELEGRAM_BOT_TOKEN.
  2. POST /api/telegram/settings updates preferences (impact, confidence, quiet hours, digest).
  3. POST /api/telegram/settings validates bad input and missing chats.
  4. POST /api/telegram/test-send delivers formatted test alerts with mandatory compliance disclaimer.
  5. DELETE /api/telegram/chat/{chat_id} deactivates chats.
  6. Admin API key protection / localhost authorization.
"""

import os
import sys
import pytest
from unittest.mock import MagicMock, patch

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from fastapi.testclient import TestClient
import config
from main import app
from database import init_db, get_connection, get_telegram_chat
from telegram_alerts import MANDATORY_DISCLAIMER
from telegram_client import TelegramClient

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_test_db():
    """Ensure clean test data in telegram tables."""
    init_db()
    conn = get_connection()
    try:
        conn.execute("DELETE FROM telegram_chats WHERE chat_id LIKE 'test_p4_%'")
        conn.execute("DELETE FROM telegram_alert_log WHERE chat_id LIKE 'test_p4_%'")
        conn.commit()
    finally:
        conn.close()

    orig_token = getattr(config, "TELEGRAM_BOT_TOKEN", "")
    orig_enabled = getattr(config, "TELEGRAM_ENABLED", False)
    orig_admin_key = getattr(config, "ADMIN_API_KEY", "")

    config.TELEGRAM_BOT_TOKEN = "123456:SECRET_TEST_TOKEN"
    config.TELEGRAM_ENABLED = True
    config.ADMIN_API_KEY = ""

    yield

    config.TELEGRAM_BOT_TOKEN = orig_token
    config.TELEGRAM_ENABLED = orig_enabled
    config.ADMIN_API_KEY = orig_admin_key


def insert_test_chat(
    chat_id: str = "test_p4_user1",
    username: str = "dalal_trader",
    is_active: int = 1,
    min_confidence: float = 0.6,
    min_impact: str = "HIGH",
    directions: str = '["BULLISH","BEARISH"]',
    digest_enabled: int = 1,
    digest_time: str = "18:30"
):
    conn = get_connection()
    try:
        conn.execute("""
            INSERT OR REPLACE INTO telegram_chats (
                chat_id, username, is_active, min_confidence, min_impact,
                directions, digest_enabled, digest_time, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """, (chat_id, username, is_active, min_confidence, min_impact, directions, digest_enabled, digest_time))
        conn.commit()
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════
# 1. STATUS ENDPOINT & TOKEN LEAKAGE PREVENTION
# ══════════════════════════════════════════════════════════════════
def test_telegram_status_endpoint_no_token_leak():
    insert_test_chat("test_p4_user1", username="trader1", is_active=1)
    insert_test_chat("test_p4_user2", username="trader2", is_active=0)

    with patch("main.get_telegram_client") as mock_get_client:
        mock_cli = MagicMock(spec=TelegramClient)
        mock_cli.is_configured = True
        mock_cli.get_me.return_value = {"ok": True, "result": {"username": "ProfitSenseBot"}}
        mock_get_client.return_value = mock_cli

        resp = client.get("/api/telegram/status")
        assert resp.status_code == 200
        data = resp.json()

        # Bot info & counts
        assert data["enabled"] is True
        assert data["configured"] is True
        assert data["bot_username"] == "ProfitSenseBot"
        assert data["active_chats_count"] >= 1
        assert "chats" in data

        # HARD RULE: TELEGRAM_BOT_TOKEN must NEVER be present anywhere in response
        raw_text = resp.text
        assert "SECRET_TEST_TOKEN" not in raw_text
        assert "token" not in data or data.get("token") is None


# ══════════════════════════════════════════════════════════════════
# 2. SETTINGS UPDATE ENDPOINT
# ══════════════════════════════════════════════════════════════════
def test_update_telegram_settings_happy_path():
    insert_test_chat("test_p4_settings_user", min_impact="HIGH", min_confidence=0.6)

    payload = {
        "chat_id": "test_p4_settings_user",
        "min_impact": "MEDIUM",
        "min_confidence": 0.75,
        "directions": ["BULLISH"],
        "quiet_start": "23:00",
        "quiet_end": "06:30",
        "watchlist_only": 1,
        "digest_enabled": 1,
        "digest_time": "19:00"
    }

    resp = client.post("/api/telegram/settings", json=payload)
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["success"] is True

    # Verify in DB
    chat = get_telegram_chat("test_p4_settings_user")
    assert chat is not None
    assert chat["min_impact"] == "MEDIUM"
    assert chat["min_confidence"] == 0.75
    assert chat["quiet_start"] == "23:00"
    assert chat["quiet_end"] == "06:30"
    assert chat["watchlist_only"] == 1
    assert chat["digest_time"] == "19:00"


def test_update_telegram_settings_validation_errors():
    insert_test_chat("test_p4_settings_user")

    # Invalid impact
    resp = client.post("/api/telegram/settings", json={
        "chat_id": "test_p4_settings_user",
        "min_impact": "INVALID_IMPACT"
    })
    assert resp.status_code == 400
    assert "min_impact must be HIGH, MEDIUM, or ALL" in resp.json()["detail"]

    # Non-existent chat
    resp_404 = client.post("/api/telegram/settings", json={
        "chat_id": "test_p4_nonexistent",
        "min_impact": "HIGH"
    })
    assert resp_404.status_code == 404


# ══════════════════════════════════════════════════════════════════
# 3. TEST SEND ENDPOINT
# ══════════════════════════════════════════════════════════════════
def test_telegram_test_send_happy_path():
    insert_test_chat("test_p4_test_send_user", is_active=1)

    with patch("main.get_telegram_client") as mock_get_client:
        mock_cli = MagicMock(spec=TelegramClient)
        mock_cli.is_configured = True
        mock_cli.send_message.return_value = {"ok": True, "result": {"message_id": 777}}
        mock_get_client.return_value = mock_cli

        resp = client.post("/api/telegram/test-send", json={"chat_id": "test_p4_test_send_user"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["delivered_count"] == 1

        # Check call arguments
        assert mock_cli.send_message.called
        args = mock_cli.send_message.call_args[0]
        cid, text = args[0], args[1]
        assert cid == "test_p4_test_send_user"
        assert "ProfitSense Test Alert" in text
        # HARD RULE: Ends with disclaimer
        assert text.endswith(f"<i>{MANDATORY_DISCLAIMER}</i>")


def test_telegram_test_send_disabled_or_no_chats():
    config.TELEGRAM_ENABLED = False
    resp = client.post("/api/telegram/test-send", json={})
    assert resp.status_code == 400
    assert "not configured or disabled" in resp.json()["detail"]


# ══════════════════════════════════════════════════════════════════
# 4. DELETE CHAT ENDPOINT
# ══════════════════════════════════════════════════════════════════
def test_delete_telegram_chat():
    insert_test_chat("test_p4_to_delete", is_active=1)

    resp = client.delete("/api/telegram/chat/test_p4_to_delete")
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    # Chat must be marked inactive
    chat = get_telegram_chat("test_p4_to_delete")
    assert chat is not None
    assert chat["is_active"] == 0

    # Deleting non-existent chat gives 404
    resp_404 = client.delete("/api/telegram/chat/test_p4_ghost")
    assert resp_404.status_code == 404


# ══════════════════════════════════════════════════════════════════
# 5. ADMIN API KEY PROTECTION
# ══════════════════════════════════════════════════════════════════
def test_admin_api_key_protection():
    config.ADMIN_API_KEY = "SUPER_SECRET_ADMIN_PASS_123"

    # Simulated remote client without header should be rejected
    # In TestClient, client.host is 'testclient', which our helper allows unless we simulate remote IP
    with patch("fastapi.Request.client") as mock_client_host:
        mock_client_host.host = "192.168.1.100"

        # Missing header
        resp_unauth = client.get("/api/telegram/status")
        assert resp_unauth.status_code == 403
        assert "Invalid admin key" in resp_unauth.json()["detail"]

        # Valid header
        resp_auth = client.get("/api/telegram/status", headers={"x-admin-key": "SUPER_SECRET_ADMIN_PASS_123"})
        assert resp_auth.status_code == 200
