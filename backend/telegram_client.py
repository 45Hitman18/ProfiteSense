"""
telegram_client.py — Resilient, Zero-Dependency Telegram Bot API Client
=======================================================================
Features:
  • Plain requests against https://api.telegram.org (no heavy frameworks).
  • Strict token security: token lives in .env, never logged, redacted from URLs & errors.
  • Exponential backoff for 429 (Too Many Requests, respecting retry_after) & 5xx server errors.
  • Immediate non-retry for 400 (Bad Request) & 403 (Forbidden / Bot Blocked).
  • Automatic deactivation of chat in database upon receiving 403.
  • HTML escaping (&, <, >) for article and user content.
  • Message splitting for payloads exceeding Telegram's 4096 character limit.
  • Rate limiting: at most ~20 messages/second globally and 1 message/second per chat.
  • Safe wraps on all calls — failures never crash the caller.
"""

import os
import re
import html
import time
import logging
import threading
from typing import Dict, Any, List, Optional

import requests

import config
from database import deactivate_telegram_chat

logger = logging.getLogger("telegram_client")
logging.basicConfig(level=logging.INFO)

TELEGRAM_MAX_MESSAGE_LENGTH = 4096
MANDATORY_DISCLAIMER = "AI/model estimate — not investment advice."


# ══════════════════════════════════════════════════════════════════
# 1. SECURITY & TOKEN REDACTION
# ══════════════════════════════════════════════════════════════════
def redact_token(text: Optional[str], token: Optional[str] = None) -> str:
    """
    Scrub bot token and any bot token patterns from strings, URLs, and exception messages.
    Ensures tokens are never written to disk, console, or API responses.
    """
    if not text:
        return ""
    s = str(text)
    if token and token in s:
        s = s.replace(token, "[REDACTED_BOT_TOKEN]")
    # Scrub common Telegram bot token pattern: bot<digits>:<alphanumeric_- >
    s = re.sub(r"bot\d+:[a-zA-Z0-9_-]+", "bot[REDACTED_BOT_TOKEN]", s)
    return s


# ══════════════════════════════════════════════════════════════════
# 2. TEXT ESCAPING & SPLITTING HELPERS
# ══════════════════════════════════════════════════════════════════
def escape_html(text: Optional[str]) -> str:
    """
    Escape text for Telegram HTML parse mode.
    Escapes only '&', '<', and '>' so user text doesn't corrupt HTML formatting.
    """
    if text is None:
        return ""
    return html.escape(str(text), quote=False)


def split_message(text: str, max_length: int = TELEGRAM_MAX_MESSAGE_LENGTH) -> List[str]:
    """
    Split text into chunks of at most max_length characters without truncation.
    Attempts natural splits at line breaks and spaces before hard character boundaries.
    """
    if not text:
        return [""]
    if len(text) <= max_length:
        return [text]

    chunks = []
    remaining = text
    while len(remaining) > max_length:
        # Prefer splitting at a newline within the max_length window
        split_pos = remaining.rfind("\n", 0, max_length)
        if split_pos == -1 or split_pos < max_length // 2:
            # Fall back to splitting at a space
            split_pos = remaining.rfind(" ", 0, max_length)
        if split_pos == -1 or split_pos < max_length // 4:
            # Hard split boundary if no convenient break found
            split_pos = max_length

        chunk = remaining[:split_pos].rstrip()
        if chunk:
            chunks.append(chunk)
        remaining = remaining[split_pos:].lstrip()

    if remaining:
        chunks.append(remaining)

    return chunks


# ══════════════════════════════════════════════════════════════════
# 3. RATE LIMITING
# ══════════════════════════════════════════════════════════════════
class TelegramRateLimiter:
    """
    Enforces Telegram API rate limits:
      • Global limit: <= 20 messages/second overall (~0.05s interval).
      • Per-chat limit: <= 1 message/second per chat (~1.0s interval).
    Thread-safe and deterministic.
    """
    def __init__(self, global_limit_per_sec: float = 20.0, per_chat_limit_per_sec: float = 1.0):
        self.min_global_interval = 1.0 / global_limit_per_sec if global_limit_per_sec > 0 else 0.05
        self.min_chat_interval = 1.0 / per_chat_limit_per_sec if per_chat_limit_per_sec > 0 else 1.0
        self.last_global_send: float = 0.0
        self.last_chat_send: Dict[str, float] = {}
        self._lock = threading.Lock()

    def wait_if_needed(self, chat_id: Optional[str] = None) -> None:
        """Sleep if necessary to respect global and per-chat rate limits."""
        with self._lock:
            now = time.monotonic()

            # Global rate limit
            time_since_global = now - self.last_global_send
            if time_since_global < self.min_global_interval:
                time.sleep(self.min_global_interval - time_since_global)

            # Per-chat rate limit
            if chat_id is not None:
                chat_key = str(chat_id)
                last_chat = self.last_chat_send.get(chat_key, 0.0)
                now = time.monotonic()
                time_since_chat = now - last_chat
                if time_since_chat < self.min_chat_interval:
                    time.sleep(self.min_chat_interval - time_since_chat)
                self.last_chat_send[chat_key] = time.monotonic()

            self.last_global_send = time.monotonic()


# ══════════════════════════════════════════════════════════════════
# 4. TELEGRAM API CLIENT
# ══════════════════════════════════════════════════════════════════
class TelegramClient:
    """
    Robust HTTP client for Telegram Bot API using requests.
    Handles network errors, rate limits, token redaction, and chat deactivation.
    """
    def __init__(self, token: Optional[str] = None, session: Optional[requests.Session] = None):
        self.token = token if token is not None else getattr(config, "TELEGRAM_BOT_TOKEN", "")
        self.session = session or requests.Session()
        self.rate_limiter = TelegramRateLimiter()

    @property
    def is_configured(self) -> bool:
        """True if a non-empty bot token is configured."""
        return bool(self.token and self.token.strip())

    @property
    def base_url(self) -> str:
        return f"https://api.telegram.org/bot{self.token}"

    def _request(
        self,
        method: str,
        endpoint: str,
        timeout: float = 10.0,
        max_retries: int = 3,
        chat_id: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Internal dispatcher with backoff and error handling:
          • 429: wait for retry_after and retry.
          • 5xx: exponential backoff (1s, 2s, 4s).
          • 400: bad request, do NOT retry.
          • 403: bot blocked / chat not found, do NOT retry, deactivate chat.
        """
        if not self.is_configured:
            return {"ok": False, "error_code": 401, "description": "TELEGRAM_BOT_TOKEN not configured"}

        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        attempt = 0
        backoff_delay = 1.0

        while attempt <= max_retries:
            attempt += 1
            try:
                # Apply rate limiting
                self.rate_limiter.wait_if_needed(chat_id)

                resp = self.session.request(method, url, timeout=timeout, **kwargs)

                # 200 OK
                if resp.status_code == 200:
                    try:
                        return resp.json()
                    except Exception:
                        return {"ok": True, "result": resp.text}

                # 400 Bad Request — Do not retry (e.g. malformed HTML or invalid chat ID)
                if resp.status_code == 400:
                    err_data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                    desc = redact_token(err_data.get("description", resp.text), self.token)
                    logger.warning("[Telegram] 400 Bad Request on %s: %s", endpoint, desc)
                    return {"ok": False, "error_code": 400, "description": desc}

                # 403 Forbidden — Bot blocked or chat deleted: do NOT retry, deactivate chat in DB
                if resp.status_code == 403:
                    err_data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                    desc = redact_token(err_data.get("description", resp.text), self.token)
                    logger.warning("[Telegram] 403 Forbidden for chat %s (marking inactive): %s", chat_id, desc)
                    if chat_id:
                        try:
                            deactivate_telegram_chat(str(chat_id))
                        except Exception as db_err:
                            logger.error("[Telegram] Error deactivating chat %s: %s", chat_id, db_err)
                    return {"ok": False, "error_code": 403, "description": desc}

                # 429 Too Many Requests — Respect retry_after parameter with backoff
                if resp.status_code == 429:
                    err_data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                    retry_after = err_data.get("parameters", {}).get("retry_after", backoff_delay)
                    logger.warning("[Telegram] 429 Rate limited on %s. Waiting %ss (attempt %d/%d)",
                                   endpoint, retry_after, attempt, max_retries)
                    if attempt > max_retries:
                        return {"ok": False, "error_code": 429, "description": f"Rate limited after {max_retries} retries"}
                    time.sleep(float(retry_after))
                    backoff_delay *= 2
                    continue

                # 5xx Server Error — Retry with exponential backoff
                if 500 <= resp.status_code < 600:
                    logger.warning("[Telegram] %s Server error on %s. Retrying in %ss (attempt %d/%d)",
                                   resp.status_code, endpoint, backoff_delay, attempt, max_retries)
                    if attempt > max_retries:
                        return {"ok": False, "error_code": resp.status_code, "description": f"Server error {resp.status_code}"}
                    time.sleep(backoff_delay)
                    backoff_delay *= 2
                    continue

                # Other HTTP status codes
                desc = redact_token(resp.text, self.token)
                return {"ok": False, "error_code": resp.status_code, "description": desc}

            except requests.exceptions.Timeout as e:
                logger.warning("[Telegram] Request timeout on %s (attempt %d/%d): %s",
                               endpoint, attempt, max_retries, redact_token(str(e), self.token))
                if attempt > max_retries:
                    return {"ok": False, "description": "Request timed out"}
                time.sleep(backoff_delay)
                backoff_delay *= 2

            except requests.exceptions.RequestException as e:
                redacted_msg = redact_token(str(e), self.token)
                logger.warning("[Telegram] Network error on %s (attempt %d/%d): %s",
                               endpoint, attempt, max_retries, redacted_msg)
                if attempt > max_retries:
                    return {"ok": False, "description": f"Network error: {redacted_msg}"}
                time.sleep(backoff_delay)
                backoff_delay *= 2

            except Exception as e:
                redacted_msg = redact_token(str(e), self.token)
                logger.error("[Telegram] Unexpected exception on %s: %s", endpoint, redacted_msg)
                return {"ok": False, "description": f"Unexpected error: {redacted_msg}"}

        return {"ok": False, "description": "Max retries exceeded"}

    def get_me(self) -> Dict[str, Any]:
        """
        Verify bot token and fetch bot profile details.
        Returns: {'ok': True, 'result': {'id': ..., 'is_bot': True, 'username': '...'}}
        """
        return self._request("GET", "getMe", timeout=8.0)

    def get_updates(
        self,
        offset: Optional[int] = None,
        timeout: int = 20,
        allowed_updates: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Fetch updates using long polling.
        Socket timeout is set to timeout + 5 to avoid premature dropouts.
        """
        payload: Dict[str, Any] = {"timeout": timeout}
        if offset is not None:
            payload["offset"] = offset
        if allowed_updates is not None:
            payload["allowed_updates"] = allowed_updates
        return self._request("POST", "getUpdates", json=payload, timeout=float(timeout + 5))

    def send_message(
        self,
        chat_id: str,
        text: str,
        parse_mode: str = "HTML",
        disable_web_page_preview: bool = True,
        reply_markup: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Send a message to a chat, automatically splitting messages > 4096 chars.
        Returns response dict for the final chunk (or first failure).
        """
        if not text:
            return {"ok": False, "description": "Empty message text"}

        chunks = split_message(text, max_length=TELEGRAM_MAX_MESSAGE_LENGTH)
        last_result: Optional[Dict[str, Any]] = None

        def _sanitize_markup(m: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
            if not m or not isinstance(m, dict) or "inline_keyboard" not in m:
                return m
            clean_kb = []
            for row in m.get("inline_keyboard", []):
                clean_row = []
                for btn in row:
                    url = btn.get("url")
                    if url and not (url.startswith("https://") or url.startswith("tg://")):
                        # Telegram API strictly rejects http://localhost or non-https URLs with 400 Bad Request
                        continue
                    clean_row.append(btn)
                if clean_row:
                    clean_kb.append(clean_row)
            return {"inline_keyboard": clean_kb} if clean_kb else None

        for i, chunk in enumerate(chunks):
            # Only attach inline buttons/keyboard to the last chunk
            raw_markup = reply_markup if i == len(chunks) - 1 else None
            markup = _sanitize_markup(raw_markup)
            payload: Dict[str, Any] = {
                "chat_id": str(chat_id),
                "text": chunk,
                "parse_mode": parse_mode,
                "disable_web_page_preview": disable_web_page_preview,
            }
            if markup:
                payload["reply_markup"] = markup

            res = self._request("POST", "sendMessage", json=payload, chat_id=str(chat_id))
            last_result = res
            if not res.get("ok"):
                return res

        return last_result or {"ok": False, "description": "No chunks sent"}

    def answer_callback_query(
        self,
        callback_query_id: str,
        text: Optional[str] = None,
        show_alert: bool = False
    ) -> Dict[str, Any]:
        """Acknowledge an inline keyboard callback query."""
        payload: Dict[str, Any] = {
            "callback_query_id": str(callback_query_id),
            "show_alert": show_alert
        }
        if text:
            payload["text"] = text
        return self._request("POST", "answerCallbackQuery", json=payload)


_telegram_client: Optional[TelegramClient] = None

def get_telegram_client() -> TelegramClient:
    """Singleton accessor for TelegramClient."""
    global _telegram_client
    if _telegram_client is None:
        _telegram_client = TelegramClient()
    return _telegram_client
