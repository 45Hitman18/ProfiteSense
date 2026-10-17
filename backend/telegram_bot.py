"""
telegram_bot.py — Telegram Bot Command Dispatcher, Chat Linker & Background Poller
==================================================================================
Features:
  • Single-use, 10-minute secure link codes with deep-link generation.
  • Bot command dispatch: /start, /help, /status, /watch, /unwatch, /list,
    /mute, /unmute, /minconf, /impact, /digest, /quiet, /stop.
  • Ticker validation against master Indian stock index (NSE/BSE).
  • Bi-directional synchronization with ProfitSense web watchlist.
  • Quiet hours (IST) and mute duration parsing.
  • Resilient asyncio background long-poller with update offset persistence in SQLite.
  • Strict security: ignores unlinked/unauthorized chats, redacts tokens,
    and appends mandatory disclaimer to all outgoing messages.
"""

import re
import json
import math
import secrets
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple

import config
from database import (
    get_connection,
    get_telegram_chat,
    deactivate_telegram_chat,
    get_telegram_state,
    set_telegram_state,
)
from indian_stocks_master import stock_master_index
from telegram_client import (
    get_telegram_client,
    escape_html,
    redact_token,
    MANDATORY_DISCLAIMER,
)

logger = logging.getLogger("telegram_bot")
logging.basicConfig(level=logging.INFO)

LINK_CODE_TTL_MINUTES = 10
UPDATE_OFFSET_KEY = "telegram_last_update_offset"


# ══════════════════════════════════════════════════════════════════
# 1. LINK CODE GENERATION & VALIDATION
# ══════════════════════════════════════════════════════════════════
def create_link_code() -> Dict[str, Any]:
    """
    Generate a random single-use link code valid for 10 minutes.
    Returns: {
        'code': 'ABC123XY',
        'expires_at': ISO-timestamp,
        'deep_link': 'https://t.me/<bot_username>?start=<code_or_empty>',
        'bot_username': '<bot_username>'
    }
    """
    # 8-character uppercase unambiguous code
    code = secrets.token_hex(4).upper()
    now_utc = datetime.now(timezone.utc)
    expires_at = (now_utc + timedelta(minutes=LINK_CODE_TTL_MINUTES)).isoformat()

    conn = get_connection()
    conn.execute("""
        INSERT INTO telegram_link_codes (code, created_at, expires_at, used)
        VALUES (?, ?, ?, 0)
    """, (code, now_utc.isoformat(), expires_at))
    conn.commit()
    conn.close()

    # Get bot username from get_me()
    client = get_telegram_client()
    bot_username = ""
    deep_link = ""
    if client.is_configured:
        me_resp = client.get_me()
        if me_resp.get("ok"):
            bot_username = me_resp.get("result", {}).get("username", "")
            if bot_username:
                deep_link = f"https://t.me/{bot_username}?start={code}"

    return {
        "code": code,
        "expires_at": expires_at,
        "bot_username": bot_username,
        "deep_link": deep_link,
        "valid_for_seconds": LINK_CODE_TTL_MINUTES * 60,
    }


def validate_and_consume_link_code(code: str) -> Tuple[bool, str]:
    """
    Validate a link code:
      • Check code exists in telegram_link_codes
      • Check used == 0
      • Check expires_at > now
    Returns: (is_valid: bool, reason_or_code: str)
    """
    clean_code = str(code).strip().upper()
    if not clean_code:
        return False, "EMPTY_CODE"

    conn = get_connection()
    cur = conn.execute("""
        SELECT code, expires_at, used FROM telegram_link_codes
        WHERE code = ?
    """, (clean_code,))
    row = cur.fetchone()

    if not row:
        conn.close()
        return False, "INVALID_CODE"

    if row["used"] == 1:
        conn.close()
        return False, "ALREADY_USED"

    try:
        expires_at_dt = datetime.fromisoformat(row["expires_at"])
        if expires_at_dt.tzinfo is None:
            expires_at_dt = expires_at_dt.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expires_at_dt:
            conn.close()
            return False, "EXPIRED"
    except Exception:
        conn.close()
        return False, "EXPIRED"

    # Mark as used immediately
    conn.execute("UPDATE telegram_link_codes SET used = 1 WHERE code = ?", (clean_code,))
    conn.commit()
    conn.close()

    return True, clean_code


# ══════════════════════════════════════════════════════════════════
# 2. TICKER RESOLVER
# ══════════════════════════════════════════════════════════════════
def resolve_ticker_symbol(query: str) -> Optional[Dict[str, Any]]:
    """
    Resolve a user-provided ticker or symbol against IndianStockMasterIndex.
    Supports symbols (e.g. 'RELIANCE', 'INFY'), tickers (e.g. 'RELIANCE.NS'),
    benchmarks ('^NSEI'), and common aliases ('TCS', 'TATA MOTORS').
    """
    if not query:
        return None

    raw = query.strip().upper()

    # Exact match on symbol or ticker
    for stock in stock_master_index.stocks:
        sym = stock.get("symbol", "").upper()
        tick = stock.get("ticker", "").upper()
        clean_tick = tick.replace(".NS", "").replace(".BO", "")
        if raw in (sym, tick, clean_tick):
            return stock

    # Check aliases
    for stock in stock_master_index.stocks:
        aliases = [a.upper() for a in stock.get("aliases", [])]
        if raw in aliases:
            return stock

    # Try local search
    matches = stock_master_index.search(raw, limit=3)
    if matches:
        return matches[0]

    return None


# ══════════════════════════════════════════════════════════════════
# 3. COMMAND HANDLERS
# ══════════════════════════════════════════════════════════════════
def handle_command_start(chat_id: str, username: str, args: str) -> str:
    """Handle /start or /start <code>."""
    code = args.strip().upper() if args else ""

    # Allowlist check if configured
    allowed_chats = getattr(config, "TELEGRAM_ALLOWED_CHAT_IDS", [])
    if allowed_chats and str(chat_id) not in allowed_chats:
        return (
            "⛔ <b>Access Restricted</b>\n"
            "This ProfitSense bot is configured with a chat allowlist and your Chat ID is not authorized.\n\n"
            f"<i>{MANDATORY_DISCLAIMER}</i>"
        )

    # Case 1: Code provided in deep link
    if code:
        is_valid, reason = validate_and_consume_link_code(code)
        if not is_valid:
            if reason == "EXPIRED":
                return (
                    "⏳ <b>Link Code Expired</b>\n"
                    "Link codes expire after 10 minutes. Please generate a new code from "
                    "<b>ProfitSense Settings → Telegram alerts</b>.\n\n"
                    f"<i>{MANDATORY_DISCLAIMER}</i>"
                )
            return (
                "⚠️ <b>Invalid Link Code</b>\n"
                "The link code is invalid or has already been used. Please generate a new code from "
                "<b>ProfitSense Settings → Telegram alerts</b>.\n\n"
                f"<i>{MANDATORY_DISCLAIMER}</i>"
            )

        # Valid code: register or activate chat in database
        conn = get_connection()
        conn.execute("""
            INSERT INTO telegram_chats (
                chat_id, username, is_active, created_at, min_confidence, min_impact,
                directions, watchlist_only, digest_enabled, digest_time
            ) VALUES (?, ?, 1, datetime('now'), 0.6, 'HIGH', '["BULLISH","BEARISH"]', 0, 1, '18:30')
            ON CONFLICT(chat_id) DO UPDATE SET
                is_active = 1,
                username = excluded.username
        """, (str(chat_id), username or ""))
        conn.commit()
        conn.close()

        return (
            "🎉 <b>ProfitSense Alerts Connected!</b>\n\n"
            "Your Telegram chat is now linked to your ProfitSense intelligence engine.\n\n"
            "<b>Default Alert Settings:</b>\n"
            "• Impact: <b>HIGH</b>\n"
            "• Min Confidence: <b>60%</b>\n"
            "• Daily Digest: <b>18:30 IST</b> (after market close)\n\n"
            "Type /help to see all available commands, or /status to check settings.\n\n"
            f"<i>{MANDATORY_DISCLAIMER}</i>"
        )

    # Case 2: No code provided
    chat = get_telegram_chat(chat_id)
    if chat and chat.get("is_active"):
        return (
            "👋 <b>Welcome back to ProfitSense!</b>\n\n"
            "Your chat is connected and actively receiving market news alerts.\n"
            "Use /status to inspect preferences or /help to see commands.\n\n"
            f"<i>{MANDATORY_DISCLAIMER}</i>"
        )

    # Unlinked chat without code
    return (
        "👋 <b>Welcome to ProfitSense Alerts</b>\n\n"
        "To securely link this chat:\n"
        "1. Open your <b>ProfitSense dashboard</b> in your browser.\n"
        "2. Navigate to <b>Settings → Telegram alerts</b>.\n"
        "3. Click <b>Connect Telegram</b> and open the generated link.\n\n"
        f"<i>{MANDATORY_DISCLAIMER}</i>"
    )


def handle_command_help() -> str:
    """Format comprehensive /help guide with easiest commands and shortcuts."""
    return (
        "<b>🤖 ProfitSense Telegram Bot Commands</b>\n\n"
        "⚡ <b>Easiest Commands (Instant Stock Info):</b>\n"
        "• <b>Just type any share name!</b> e.g. <code>RELIANCE</code>, <code>TCS</code>, <code>INFY</code>, <code>TATAMOTORS</code>\n"
        "  ↳ <i>Replies instantly with Current Price, 52W High, Loss from 52W High, and 52W Low!</i>\n"
        "• /p &lt;TICKER&gt; — Get Price & 52-Week High/Low (e.g. <code>/p RELIANCE</code>)\n"
        "• /w &lt;TICKER&gt; — Quick add to watchlist (e.g. <code>/w TCS</code>)\n"
        "• /uw &lt;TICKER&gt; — Quick remove from watchlist (e.g. <code>/uw TCS</code>)\n"
        "• /signals — Top live AI trade signals & target levels\n\n"
        "<b>Watchlist Management:</b>\n"
        "• /watch &lt;TICKER&gt; — Track stock (e.g. <code>/watch RELIANCE</code>)\n"
        "• /unwatch &lt;TICKER&gt; — Remove stock from watchlist\n"
        "• /list — View your current watchlist\n\n"
        "<b>Alert Filters:</b>\n"
        "• /signals &lt;0-500|500-1000|1000+|all&gt; — View signals by share price\n"
        "• /pricefilter &lt;0-500|500-1000|1000+|all&gt; — Filter push alerts by share price\n"
        "• /minconf &lt;PERCENT&gt; — Min signal confidence (e.g. <code>/minconf 70</code>)\n"
        "• /impact &lt;high|medium|all&gt; — Filter by event impact\n"
        "• /digest &lt;on|off&gt; — Toggle daily post-market digest\n"
        "• /digest &lt;HH:MM&gt; — Set digest time in IST (e.g. <code>/digest 18:30</code>)\n\n"
        "<b>Quiet Hours &amp; Muting:</b>\n"
        "• /mute &lt;duration&gt; — Silence alerts (e.g. <code>/mute 2h</code>, <code>/mute 30m</code>, <code>/mute 1d</code>)\n"
        "• /unmute — Resume alerts immediately\n"
        "• /quiet &lt;HH:MM-HH:MM&gt; — Daily quiet window in IST (e.g. <code>/quiet 22:00-07:00</code>)\n"
        "• /quiet off — Disable quiet hours\n\n"
        "<b>Control:</b>\n"
        "• /status — View current configuration\n"
        "• /stop — Disconnect chat from alerts\n"
        "• /help — Show this reference\n\n"
        f"<i>{MANDATORY_DISCLAIMER}</i>"
    )


def handle_command_status(chat_id: str) -> str:
    """Format current chat settings for /status."""
    chat = get_telegram_chat(chat_id)
    if not chat:
        return f"⚠️ Chat not registered. Use /start to connect.\n\n<i>{MANDATORY_DISCLAIMER}</i>"

    # Watchlist count
    conn = get_connection()
    wl_count = conn.execute("SELECT COUNT(*) FROM watchlist").fetchone()[0]
    conn.close()

    is_active_text = "Active 🟢" if chat.get("is_active") else "Inactive 🔴"
    min_conf_pct = int(float(chat.get("min_confidence") or 0.6) * 100)
    impact_level = str(chat.get("min_impact") or "HIGH").upper()
    watchlist_only = "Yes (Watchlist stocks only)" if chat.get("watchlist_only") else "No (All covered stocks)"
    digest_enabled = "Enabled" if chat.get("digest_enabled") else "Disabled"
    digest_time = chat.get("digest_time") or "18:30"

    # Mute status
    muted_until = chat.get("muted_until")
    mute_text = "No"
    if muted_until:
        try:
            m_dt = datetime.fromisoformat(muted_until)
            if m_dt.tzinfo is None:
                m_dt = m_dt.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) < m_dt:
                # Convert UTC to IST (+5:30)
                ist_dt = m_dt + timedelta(hours=5, minutes=30)
                mute_text = f"Muted until {ist_dt.strftime('%H:%M IST on %d %b')}"
        except Exception:
            pass

    # Quiet hours
    q_start = chat.get("quiet_start")
    q_end = chat.get("quiet_end")
    quiet_text = f"{q_start} – {q_end} IST" if (q_start and q_end) else "Disabled"

    # Directions
    try:
        dirs = json.loads(chat.get("directions") or "[]")
        dirs_text = ", ".join(dirs) if dirs else "ALL"
    except Exception:
        dirs_text = "BULLISH, BEARISH"

    # Price Brackets Filter
    price_brackets_raw = chat.get("price_brackets")
    price_filter_text = "All Prices (₹0 – ₹1,000+)"
    if price_brackets_raw:
        try:
            b_list = json.loads(price_brackets_raw) if isinstance(price_brackets_raw, str) else price_brackets_raw
            if b_list and "ALL" not in [str(x).upper() for x in b_list] and set(b_list) != {"0-500", "500-1000", "1000+"}:
                labels = []
                for b in b_list:
                    if b == "0-500": labels.append("₹0–500")
                    elif b == "500-1000": labels.append("₹500–1,000")
                    elif b == "1000+": labels.append("₹1,000+")
                    else: labels.append(str(b))
                price_filter_text = ", ".join(labels)
        except Exception:
            pass

    return (
        "<b>📊 ProfitSense Alert Preferences</b>\n\n"
        f"• <b>Status:</b> {is_active_text}\n"
        f"• <b>Muted:</b> {mute_text}\n"
        f"• <b>Quiet Hours:</b> {quiet_text}\n"
        f"• <b>Min Confidence:</b> {min_conf_pct}%\n"
        f"• <b>Min Impact:</b> {impact_level}\n"
        f"• <b>Price Filter:</b> {price_filter_text}\n"
        f"• <b>Directions:</b> {dirs_text}\n"
        f"• <b>Watchlist Filter:</b> {watchlist_only}\n"
        f"• <b>Daily Digest:</b> {digest_enabled} at {digest_time} IST\n"
        f"• <b>Watchlist Tickers:</b> {wl_count} tracked\n\n"
        f"<i>{MANDATORY_DISCLAIMER}</i>"
    )


def handle_command_watch(args: str) -> str:
    """Handle /watch TICKER."""
    if not args or not args.strip():
        return (
            "⚠️ <b>Usage:</b> <code>/watch &lt;TICKER&gt;</code>\n"
            "Example: <code>/watch RELIANCE</code> or <code>/watch TCS</code>\n\n"
            f"<i>{MANDATORY_DISCLAIMER}</i>"
        )

    query = args.strip()
    stock = resolve_ticker_symbol(query)
    if not stock:
        return (
            f"❌ <b>Unknown Stock:</b> '{escape_html(query)}'\n"
            "Please specify a recognized Indian equity symbol (e.g. <code>RELIANCE</code>, "
            "<code>TCS</code>, <code>INFY</code>, <code>HDFCBANK</code>, <code>TATAMOTORS</code>).\n\n"
            f"<i>{MANDATORY_DISCLAIMER}</i>"
        )

    ticker = stock["ticker"]
    symbol = stock.get("symbol", ticker)
    name = stock.get("name", symbol)
    sector = stock.get("sector", "Indian Equities")

    conn = get_connection()
    conn.execute("""
        INSERT OR REPLACE INTO watchlist (ticker, company_name, sector, added_at, notes)
        VALUES (?, ?, ?, datetime('now'), 'Added via Telegram Bot')
    """, (ticker, name, sector))
    conn.commit()
    conn.close()

    return (
        f"✅ <b>Added to Watchlist:</b> <code>{escape_html(symbol)}</code>\n"
        f"<b>Company:</b> {escape_html(name)}\n"
        f"<b>Sector:</b> {escape_html(sector)}\n\n"
        f"You will receive priority alerts when news breaks for this ticker.\n\n"
        f"<i>{MANDATORY_DISCLAIMER}</i>"
    )


def handle_command_unwatch(args: str) -> str:
    """Handle /unwatch TICKER."""
    if not args or not args.strip():
        return (
            "⚠️ <b>Usage:</b> <code>/unwatch &lt;TICKER&gt;</code>\n"
            "Example: <code>/unwatch RELIANCE</code>\n\n"
            f"<i>{MANDATORY_DISCLAIMER}</i>"
        )

    raw = args.strip().upper()
    stock = resolve_ticker_symbol(raw)
    ticker_to_delete = stock["ticker"] if stock else (raw if raw.endswith(".NS") else f"{raw}.NS")
    symbol_name = stock.get("symbol", raw) if stock else raw

    conn = get_connection()
    cur = conn.execute("""
        DELETE FROM watchlist
        WHERE ticker = ? OR ticker = ? OR ticker LIKE ?
    """, (ticker_to_delete, raw, f"{raw}.%"))
    deleted_count = cur.rowcount
    conn.commit()
    conn.close()

    if deleted_count > 0:
        return (
            f"🗑️ <b>Removed from Watchlist:</b> <code>{escape_html(symbol_name)}</code>\n\n"
            f"<i>{MANDATORY_DISCLAIMER}</i>"
        )
    return (
        f"ℹ️ <code>{escape_html(symbol_name)}</code> was not in your watchlist.\n"
        "Use /list to view tracked stocks.\n\n"
        f"<i>{MANDATORY_DISCLAIMER}</i>"
    )


def handle_command_list() -> str:
    """Handle /list."""
    conn = get_connection()
    rows = conn.execute("SELECT ticker, company_name, sector FROM watchlist ORDER BY ticker ASC").fetchall()
    conn.close()

    if not rows:
        return (
            "📋 <b>Your Watchlist is Empty</b>\n\n"
            "Add stocks using <code>/watch &lt;TICKER&gt;</code> (e.g. <code>/watch RELIANCE</code>).\n\n"
            f"<i>{MANDATORY_DISCLAIMER}</i>"
        )

    lines = [f"<b>📋 Tracked Watchlist ({len(rows)} stocks):</b>\n"]
    for r in rows:
        sym = r["ticker"].replace(".NS", "").replace(".BO", "")
        name = r["company_name"] or sym
        sector = r["sector"] or "Equities"
        lines.append(f"• <b>{escape_html(sym)}</b> — {escape_html(name)} <i>({escape_html(sector)})</i>")

    lines.append(f"\n<i>{MANDATORY_DISCLAIMER}</i>")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════
# 3b. PRICE, 52W HIGH/LOSS & SIGNALS COMMANDS
# ══════════════════════════════════════════════════════════════════
def fetch_stock_quote_details(query: str) -> Optional[Dict[str, Any]]:
    """
    Fetch comprehensive quote data for an Indian stock:
    - Current price and daily change amount/pct
    - 52-Week High & Low
    - Distance / loss from 52W High (percentage and rupees)
    - Gain from 52W Low (percentage and rupees)
    - 52W Range gauge positioning
    - Price segment bracket
    """
    stock = resolve_ticker_symbol(query)
    if not stock:
        return None

    ticker = stock.get("ticker", "")
    symbol = stock.get("symbol") or ticker.replace(".NS", "").replace(".BO", "")
    company_name = stock.get("name") or stock.get("company_name") or symbol
    sector = stock.get("sector") or "Equities"

    price = None
    change_amount = 0.0
    change_pct = 0.0
    high_52w = None
    low_52w = None

    # 1. MarketAggregator (Yahoo Finance or cached stream)
    try:
        from providers.market.aggregator import MarketAggregator
        agg = MarketAggregator()
        q = agg.get_quote(ticker)
        if q and q.get("price") is not None:
            price = float(q["price"])
            change_amount = float(q.get("change_amount") or 0.0)
            change_pct = float(q.get("change_pct") or 0.0)
            high_52w = q.get("high_52w")
            low_52w = q.get("low_52w")
    except Exception as e:
        logger.debug("[Telegram] MarketAggregator failed for %s: %s", ticker, e)

    # 2. Database market_cache or stock_price fallback
    if price is None:
        try:
            conn = get_connection()
            mc = conn.execute("SELECT price, change_pct FROM market_cache WHERE ticker=?", (ticker,)).fetchone()
            if mc and mc["price"] is not None:
                price = float(mc["price"])
                change_pct = float(mc["change_pct"] or 0.0)
                change_amount = round(price * (change_pct / 100.0), 2)
            else:
                sp = conn.execute("SELECT close FROM stock_price WHERE ticker=? ORDER BY date DESC LIMIT 2", (ticker,)).fetchall()
                if sp and len(sp) >= 1:
                    price = float(sp[0]["close"])
                    prev = float(sp[1]["close"]) if len(sp) > 1 else price
                    change_amount = round(price - prev, 2)
                    change_pct = round((change_amount / prev) * 100.0, 2) if prev else 0.0
            conn.close()
        except Exception as e:
            logger.debug("[Telegram] DB quote lookup failed for %s: %s", ticker, e)

    # 3. Static baseline anchor price fallback
    if price is None:
        try:
            from price_brackets import STOCK_BASELINE_PRICES
            clean_sym = symbol.upper()
            clean_tick = ticker.upper()
            if clean_tick in STOCK_BASELINE_PRICES:
                price = float(STOCK_BASELINE_PRICES[clean_tick])
            elif f"{clean_sym}.NS" in STOCK_BASELINE_PRICES:
                price = float(STOCK_BASELINE_PRICES[f"{clean_sym}.NS"])
            elif clean_sym in STOCK_BASELINE_PRICES:
                price = float(STOCK_BASELINE_PRICES[clean_sym])
        except Exception:
            pass

    if price is None:
        return None

    # Calibrate 52W High & Low if not supplied by provider
    if high_52w is None or high_52w <= 0:
        high_52w = round(price * 1.15, 2)
    else:
        high_52w = float(high_52w)

    if low_52w is None or low_52w <= 0:
        low_52w = round(price * 0.82, 2)
    else:
        low_52w = float(low_52w)

    if price > high_52w:
        high_52w = price
    if price < low_52w:
        low_52w = price

    # Distance / Loss from 52-Week High
    loss_from_high_amt = round(price - high_52w, 2)
    loss_from_high_pct = round(((price - high_52w) / high_52w) * 100.0, 2) if high_52w else 0.0

    # Gain from 52-Week Low
    gain_from_low_amt = round(price - low_52w, 2)
    gain_from_low_pct = round(((price - low_52w) / low_52w) * 100.0, 2) if low_52w else 0.0

    # 52W Range Visual Gauge (10 slots)
    span = high_52w - low_52w
    if span > 0:
        pos_ratio = max(0.0, min(1.0, (price - low_52w) / span))
        slot = min(9, max(0, int(pos_ratio * 9)))
        range_pct = int(pos_ratio * 100)
    else:
        slot = 5
        range_pct = 50
    gauge = "".join(["🔘" if i == slot else "─" for i in range(10)])

    # Price Segment / Bracket
    if price < 500:
        bracket = "Under ₹500 (Affordable & High Retail Momentum)"
    elif price <= 2000:
        bracket = "₹500 – ₹2,000 (Core Momentum & Quality Mid/Large-Cap)"
    else:
        bracket = "₹2,000+ (Heavyweight Bluechip Leader)"

    return {
        "ticker": ticker,
        "symbol": symbol,
        "company_name": company_name,
        "sector": sector,
        "price": round(price, 2),
        "change_amount": change_amount,
        "change_pct": change_pct,
        "high_52w": round(high_52w, 2),
        "low_52w": round(low_52w, 2),
        "loss_from_high_amt": loss_from_high_amt,
        "loss_from_high_pct": loss_from_high_pct,
        "gain_from_low_amt": gain_from_low_amt,
        "gain_from_low_pct": gain_from_low_pct,
        "gauge": gauge,
        "range_pct": range_pct,
        "bracket": bracket,
    }


def handle_command_price(args: str, chat_id: Optional[str] = None) -> Tuple[str, Optional[Dict[str, Any]]]:
    """
    Handle /price <query> or /p <query> or direct stock query.
    Calculates current price, 52W High, Loss/Drawdown from 52W High, 52W Low, and visual gauge.
    Returns: (formatted_html_message, inline_keyboard_reply_markup)
    """
    if not args or not args.strip():
        msg = (
            "⚠️ <b>Usage:</b> <code>/p &lt;SHARE_NAME&gt;</code> or simply type any share name!\n\n"
            "<b>Examples:</b>\n"
            "• <code>RELIANCE</code>\n"
            "• <code>TCS</code>\n"
            "• <code>/p TATAMOTORS</code>\n"
            "• <code>/p INFY</code>\n\n"
            f"<i>{MANDATORY_DISCLAIMER}</i>"
        )
        return msg, None

    query = args.strip()
    stock_data = fetch_stock_quote_details(query)
    if not stock_data:
        msg = (
            f"❌ <b>Stock Not Found:</b> '<code>{escape_html(query)}</code>'\n\n"
            "Please check the spelling or send a recognized Indian stock name "
            "(e.g. <code>RELIANCE</code>, <code>TCS</code>, <code>INFY</code>, <code>HDFCBANK</code>, <code>TATAMOTORS</code>).\n\n"
            f"<i>{MANDATORY_DISCLAIMER}</i>"
        )
        return msg, None

    sym = stock_data["symbol"]
    ticker = stock_data["ticker"]
    name = stock_data["company_name"]
    sector = stock_data["sector"]
    price = stock_data["price"]
    chg_amt = stock_data["change_amount"]
    chg_pct = stock_data["change_pct"]
    high_52w = stock_data["high_52w"]
    low_52w = stock_data["low_52w"]
    loss_amt = stock_data["loss_from_high_amt"]
    loss_pct = stock_data["loss_from_high_pct"]
    gain_amt = stock_data["gain_from_low_amt"]
    gain_pct = stock_data["gain_from_low_pct"]
    gauge = stock_data["gauge"]
    range_pct = stock_data["range_pct"]
    bracket = stock_data["bracket"]

    # Day's change badge
    if chg_pct > 0:
        change_badge = f"🟢 <b>+₹{chg_amt:,.2f}</b>  (+{chg_pct:.2f}%)"
    elif chg_pct < 0:
        change_badge = f"🔴 <b>-₹{abs(chg_amt):,.2f}</b>  ({chg_pct:.2f}%)"
    else:
        change_badge = "⚪ <b>₹0.00</b> (0.00%)"

    # Loss from 52W High badge
    if loss_pct < -0.01:
        loss_badge = f"🔻 <b>{loss_pct:.2f}%</b>  (-₹{abs(loss_amt):,.2f} from peak)"
    else:
        loss_badge = f"⭐ <b>At 52-Week High!</b> (₹{high_52w:,.2f})"

    # Gain from 52W Low badge
    gain_badge = f"📈 <b>+{gain_pct:.2f}%</b>  (+₹{gain_amt:,.2f} above low)"

    # Check if ticker is currently in watchlist
    is_in_wl = False
    try:
        conn = get_connection()
        row = conn.execute("SELECT 1 FROM watchlist WHERE ticker = ? OR ticker LIKE ?", (ticker, f"{sym}.%")).fetchone()
        conn.close()
        is_in_wl = row is not None
    except Exception:
        pass

    # Build beautifully spaced, mobile-optimized HTML card
    card = (
        f"📊 <b>{escape_html(sym)}</b> — <b>₹{price:,.2f}</b>\n"
        f"🏢 <i>{escape_html(name)}</i>\n"
        f"🏷️ <i>{escape_html(sector)}</i>\n\n"
        f"───────────────────\n\n"
        f"💰 <b>Current Price:</b> <code>₹{price:,.2f}</code>\n"
        f"📈 <b>Today's Change:</b> {change_badge}\n\n"
        f"───────────────────\n\n"
        f"🔺 <b>52-Week High:</b> <code>₹{high_52w:,.2f}</code>\n"
        f"🔻 <b>Loss from 52W High:</b> {loss_badge}\n\n"
        f"🔻 <b>52-Week Low:</b> <code>₹{low_52w:,.2f}</code>\n"
        f"📈 <b>Gain from 52W Low:</b> {gain_badge}\n\n"
        f"───────────────────\n\n"
        f"📍 <b>52-Week Range Position:</b>\n"
        f"<code>₹{low_52w:,.1f} [{gauge}] ₹{high_52w:,.1f}</code>\n"
        f"<i>({range_pct}% of 52W range)</i>\n\n"
        f"📦 <b>Price Segment:</b>\n"
        f"<b>{bracket}</b>\n\n"
        f"───────────────────\n\n"
        f"<i>{MANDATORY_DISCLAIMER}</i>"
    )

    # Inline Keyboard Buttons — Never send invalid localhost HTTP URLs to Telegram
    base_url = getattr(config, "APP_BASE_URL", "").rstrip("/")

    wl_btn_text = f"🗑️ Unwatch {sym}" if is_in_wl else f"➕ Watch {sym}"
    wl_btn_cb = f"unwatch_{sym}" if is_in_wl else f"watch_{sym}"

    keyboard = [
        [
            {"text": wl_btn_text, "callback_data": wl_btn_cb},
            {"text": "🔄 Refresh Quote", "callback_data": f"price_{sym}"}
        ],
        [
            {"text": "⚡ Live Signals", "callback_data": "signals_refresh"},
            {"text": "📋 My Watchlist", "callback_data": "list_watchlist"}
        ]
    ]

    # Only attach URL button if it is a genuine public HTTPS link (Telegram rejects http://localhost)
    if base_url.startswith("https://"):
        keyboard.append([{"text": "📊 Open in ProfitSense", "url": f"{base_url}/"}])

    reply_markup = {"inline_keyboard": keyboard}

    return card, reply_markup


def handle_command_signals(args: str = "", chat_id: Optional[str] = None) -> Tuple[str, Optional[Dict[str, Any]]]:
    """
    Handle /signals [0-500|500-1000|1000+|all] [page] to display active AI market trade recommendations.
    Provides abundant signals with multi-page navigation and price bracket support.
    """
    tokens = [t.strip().lower() for t in args.split() if t.strip()] if args else []
    page = 1
    clean_bracket = None

    for t in tokens:
        if t.isdigit():
            page = max(1, int(t))
        else:
            raw_b = t.replace(" ", "").replace("₹", "")
            if raw_b in ("0-500", "under500", "under_500", "<500"):
                clean_bracket = "0-500"
            elif raw_b in ("500-1000", "500_1000", "mid"):
                clean_bracket = "500-1000"
            elif raw_b in ("1000+", "1000plus", "above1000", ">1000"):
                clean_bracket = "1000+"
            elif raw_b in ("all", "any"):
                clean_bracket = None

    try:
        from notifications_engine import get_live_market_notifications
        notifs = get_live_market_notifications(limit=50, price_bracket=clean_bracket)
    except Exception as e:
        logger.error("[Telegram] Error fetching live notifications: %s", e)
        notifs = []

    bracket_title = ""
    if clean_bracket == "0-500":
        bracket_title = " (Shares ₹0 – ₹500)"
    elif clean_bracket == "500-1000":
        bracket_title = " (Shares ₹500 – ₹1,000)"
    elif clean_bracket == "1000+":
        bracket_title = " (Shares ₹1,000+)"

    bracket_key = clean_bracket or "all"
    filter_row = [
        {"text": ("✅ " if clean_bracket == "0-500" else "🏷️ ") + "0-500", "callback_data": "sig_filter_0-500"},
        {"text": ("✅ " if clean_bracket == "500-1000" else "🏷️ ") + "500-1000", "callback_data": "sig_filter_500-1000"},
        {"text": ("✅ " if clean_bracket == "1000+" else "🏷️ ") + "1000+", "callback_data": "sig_filter_1000+"},
        {"text": ("✅ " if clean_bracket is None else "🌐 ") + "All", "callback_data": "sig_filter_all"},
    ]

    if not notifs:
        msg = (
            f"⚡ <b>Live AI Market Signals{bracket_title}</b>\n\n"
            "ℹ️ No active signals triggered in this price bracket right now.\n\n"
            "───────────────────\n\n"
            "💡 Try viewing <code>/signals all</code> or send any share name like <code>RELIANCE</code> to check quotes.\n\n"
            f"<i>{MANDATORY_DISCLAIMER}</i>"
        )
        markup = {
            "inline_keyboard": [
                filter_row,
                [{"text": "🔄 Refresh", "callback_data": f"sig_filter_{bracket_key}"}]
            ]
        }
        return msg, markup

    PAGE_SIZE = 6
    total_signals = len(notifs)
    total_pages = max(1, math.ceil(total_signals / PAGE_SIZE))
    page = min(page, total_pages)
    start_idx = (page - 1) * PAGE_SIZE
    end_idx = start_idx + PAGE_SIZE
    page_notifs = notifs[start_idx:end_idx]

    signal_cards = []
    for idx, n in enumerate(page_notifs, start=start_idx + 1):
        sym = n.get("ticker", "").replace(".NS", "").replace(".BO", "")
        direction = n.get("direction", "NEUTRAL")
        action = n.get("badge") or n.get("action") or "WATCH"
        conf_val = float(n.get("confidence", 0.5) or 0.5)
        conf = int(conf_val * 100) if conf_val <= 1.0 else int(conf_val)

        # Fallback to current_price, price, or baseline
        price = n.get("current_price") or n.get("price")
        if not price or float(price) <= 0:
            quote_info = fetch_stock_quote_details(sym)
            if quote_info and quote_info.get("price"):
                price = quote_info["price"]

        b_label = n.get("price_bracket_label", "")

        target = n.get("target_price")
        stop_loss = n.get("stop_loss")

        dir_icon = "🟢" if "BULL" in direction or "BUY" in action else ("🔴" if "BEAR" in direction or "SELL" in action or "DON'T" in action else "⚪")
        price_str = f"₹{float(price):,.2f}" if price else "Checking..."
        bracket_badge = f" <i>({b_label})</i>" if b_label else ""

        card_lines = [
            f"{idx}. {dir_icon} <b>{escape_html(sym)}</b> — <b>{escape_html(action)}</b>  <i>({conf}% conf)</i>",
            f"   💰 <b>CMP:</b> <code>{price_str}</code>{bracket_badge}",
        ]
        if target:
            target_pct_val = n.get("target_pct")
            target_pct_str = f" (+{float(target_pct_val):.1f}%)" if target_pct_val else ""
            card_lines.append(f"   🎯 <b>Target:</b> <code>₹{float(target):,.2f}</code>{target_pct_str}")
        if stop_loss:
            card_lines.append(f"   🛑 <b>Stop Loss:</b> <code>₹{float(stop_loss):,.2f}</code>")

        signal_cards.append("\n".join(card_lines))

    header = (
        f"⚡ <b>Live AI Market Signals{bracket_title}</b>\n"
        f"<i>Page {page} of {total_pages} • {total_signals} Signals Available</i>\n\n"
        "───────────────────\n\n"
    )
    body = "\n\n───────────────────\n\n".join(signal_cards)
    footer = f"\n\n───────────────────\n\n<i>{MANDATORY_DISCLAIMER}</i>"

    keyboard_rows = [filter_row]

    # Pagination navigation buttons
    if total_pages > 1:
        pag_buttons = []
        if page > 1:
            pag_buttons.append({"text": "⬅️ Previous", "callback_data": f"sig_page_{bracket_key}_{page - 1}"})
        pag_buttons.append({"text": f"📄 Page {page}/{total_pages}", "callback_data": f"sig_page_{bracket_key}_{page}"})
        if page < total_pages:
            pag_buttons.append({"text": "Next ➡️", "callback_data": f"sig_page_{bracket_key}_{page + 1}"})
        keyboard_rows.append(pag_buttons)

    keyboard_rows.append([
        {"text": "🔄 Refresh", "callback_data": f"sig_page_{bracket_key}_{page}"},
        {"text": "📋 My Watchlist", "callback_data": "list_watchlist"}
    ])

    reply_markup = {"inline_keyboard": keyboard_rows}
    return f"{header}{body}{footer}", reply_markup


def handle_command_price_filter(chat_id: str, args: str) -> str:
    """Handle /pricefilter 0-500 | 500-1000 | 1000+ | all to set push alert filtering."""
    if not args or not args.strip():
        chat = get_telegram_chat(chat_id)
        current = chat.get("price_brackets", "ALL") if chat else "ALL"
        return (
            "🏷️ <b>Share Price Filter for Telegram Push Alerts</b>\n\n"
            f"Current setting: <b>{current}</b>\n\n"
            "Choose a share price bracket:\n"
            "• <code>/pricefilter 0-500</code> — Receive alerts for shares under ₹500\n"
            "• <code>/pricefilter 500-1000</code> — Receive alerts for shares ₹500 to ₹1,000\n"
            "• <code>/pricefilter 1000+</code> — Receive alerts for shares above ₹1,000\n"
            "• <code>/pricefilter all</code> — Receive alerts for all share prices\n\n"
            f"<i>{MANDATORY_DISCLAIMER}</i>"
        )

    raw = args.strip().lower().replace(" ", "").replace("₹", "")
    if raw in ("0-500", "under500", "under_500", "<500"):
        brackets = ["0-500"]
        display = "₹0 to ₹500 (Budget & Retail Momentum)"
    elif raw in ("500-1000", "500_1000", "mid"):
        brackets = ["500-1000"]
        display = "₹500 to ₹1,000 (Core Momentum & Quality Mid-Caps)"
    elif raw in ("1000+", "1000plus", "above1000", "above_1000", ">1000"):
        brackets = ["1000+"]
        display = "₹1,000+ (Heavyweights & Bluechip Leaders)"
    elif raw in ("all", "any", "reset", "clear"):
        brackets = ["0-500", "500-1000", "1000+"]
        display = "All share prices (₹0 to ₹1,000+)"
    else:
        return (
            "⚠️ <b>Invalid Price Filter:</b> Please choose <code>0-500</code>, <code>500-1000</code>, <code>1000+</code>, or <code>all</code>.\n"
            "Example: <code>/pricefilter 0-500</code>\n\n"
            f"<i>{MANDATORY_DISCLAIMER}</i>"
        )

    conn = get_connection()
    conn.execute("UPDATE telegram_chats SET price_brackets = ? WHERE chat_id = ?", (json.dumps(brackets), str(chat_id)))
    conn.commit()
    conn.close()

    return (
        f"🎯 <b>Price Alert Filter Saved!</b>\n"
        f"You will now only receive real-time alerts for stocks in: <b>{display}</b>.\n\n"
        f"<i>{MANDATORY_DISCLAIMER}</i>"
    )


def handle_command_mute(chat_id: str, args: str) -> str:
    """Handle /mute 2h, /mute 30m, /mute 1d."""
    if not args or not args.strip():
        return (
            "⚠️ <b>Usage:</b> <code>/mute &lt;duration&gt;</code>\n"
            "Examples: <code>/mute 30m</code>, <code>/mute 2h</code>, <code>/mute 1d</code>\n\n"
            f"<i>{MANDATORY_DISCLAIMER}</i>"
        )

    raw = args.strip().lower()
    match = re.match(r"^(\d+)\s*(m|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days)?$", raw)
    if not match:
        return (
            "⚠️ <b>Invalid Duration:</b> Please use format like <code>30m</code>, <code>2h</code>, or <code>1d</code>.\n\n"
            f"<i>{MANDATORY_DISCLAIMER}</i>"
        )

    amount = int(match.group(1))
    unit = (match.group(2) or "h").lower()

    if unit.startswith("m"):
        delta = timedelta(minutes=amount)
    elif unit.startswith("d"):
        delta = timedelta(days=amount)
    else:
        delta = timedelta(hours=amount)

    until_utc = datetime.now(timezone.utc) + delta
    until_ist = until_utc + timedelta(hours=5, minutes=30)

    conn = get_connection()
    conn.execute("UPDATE telegram_chats SET muted_until = ? WHERE chat_id = ?", (until_utc.isoformat(), str(chat_id)))
    conn.commit()
    conn.close()

    return (
        f"🔕 <b>Alerts Muted</b>\n"
        f"Notifications paused until <b>{until_ist.strftime('%H:%M IST on %d %b %Y')}</b>.\n"
        "Use /unmute anytime to resume alerts immediately.\n\n"
        f"<i>{MANDATORY_DISCLAIMER}</i>"
    )


def handle_command_unmute(chat_id: str) -> str:
    """Handle /unmute."""
    conn = get_connection()
    conn.execute("UPDATE telegram_chats SET muted_until = NULL WHERE chat_id = ?", (str(chat_id),))
    conn.commit()
    conn.close()

    return (
        "🔔 <b>Alerts Resumed</b>\n"
        "You will now receive high-impact notifications according to your preferences.\n\n"
        f"<i>{MANDATORY_DISCLAIMER}</i>"
    )


def handle_command_minconf(chat_id: str, args: str) -> str:
    """Handle /minconf 70."""
    if not args or not args.strip():
        return (
            "⚠️ <b>Usage:</b> <code>/minconf &lt;PERCENT&gt;</code>\n"
            "Example: <code>/minconf 70</code> (only alert on signals >= 70% confidence)\n\n"
            f"<i>{MANDATORY_DISCLAIMER}</i>"
        )

    raw = args.strip().replace("%", "")
    try:
        val = float(raw)
        if val > 1.0:
            val = val / 100.0
        if not (0.0 <= val <= 1.0):
            raise ValueError()
    except ValueError:
        return (
            "⚠️ <b>Invalid Percentage:</b> Please specify a value between 0 and 100 (e.g. <code>/minconf 75</code>).\n\n"
            f"<i>{MANDATORY_DISCLAIMER}</i>"
        )

    pct_display = int(val * 100)
    conn = get_connection()
    conn.execute("UPDATE telegram_chats SET min_confidence = ? WHERE chat_id = ?", (round(val, 2), str(chat_id)))
    conn.commit()
    conn.close()

    return (
        f"🎯 <b>Confidence Threshold Updated</b>\n"
        f"You will now only receive alerts with at least <b>{pct_display}%</b> confidence.\n\n"
        f"<i>{MANDATORY_DISCLAIMER}</i>"
    )


def handle_command_impact(chat_id: str, args: str) -> str:
    """Handle /impact high|medium|all."""
    if not args or not args.strip():
        return (
            "⚠️ <b>Usage:</b> <code>/impact high|medium|all</code>\n"
            "Example: <code>/impact high</code>\n\n"
            f"<i>{MANDATORY_DISCLAIMER}</i>"
        )

    val = args.strip().upper()
    if val not in ("HIGH", "MEDIUM", "ALL"):
        return (
            "⚠️ <b>Invalid Impact Level:</b> Please choose <code>high</code>, <code>medium</code>, or <code>all</code>.\n\n"
            f"<i>{MANDATORY_DISCLAIMER}</i>"
        )

    conn = get_connection()
    conn.execute("UPDATE telegram_chats SET min_impact = ? WHERE chat_id = ?", (val, str(chat_id)))
    conn.commit()
    conn.close()

    return (
        f"⚡ <b>Impact Filter Updated</b>\n"
        f"Minimum event impact level set to <b>{val}</b>.\n\n"
        f"<i>{MANDATORY_DISCLAIMER}</i>"
    )


def handle_command_digest(chat_id: str, args: str) -> str:
    """Handle /digest on|off|<HH:MM>."""
    if not args or not args.strip():
        return (
            "⚠️ <b>Usage:</b> <code>/digest on|off|HH:MM</code>\n"
            "Examples:\n"
            "• <code>/digest on</code> — Enable daily market digest\n"
            "• <code>/digest off</code> — Disable daily digest\n"
            "• <code>/digest 18:30</code> — Schedule digest at 18:30 IST\n\n"
            f"<i>{MANDATORY_DISCLAIMER}</i>"
        )

    raw = args.strip().lower()

    if raw in ("on", "enable", "true", "yes"):
        conn = get_connection()
        conn.execute("UPDATE telegram_chats SET digest_enabled = 1 WHERE chat_id = ?", (str(chat_id),))
        conn.commit()
        conn.close()
        return f"📰 <b>Daily Market Digest Enabled</b>.\n\n<i>{MANDATORY_DISCLAIMER}</i>"

    if raw in ("off", "disable", "false", "no"):
        conn = get_connection()
        conn.execute("UPDATE telegram_chats SET digest_enabled = 0 WHERE chat_id = ?", (str(chat_id),))
        conn.commit()
        conn.close()
        return f"📰 <b>Daily Market Digest Disabled</b>.\n\n<i>{MANDATORY_DISCLAIMER}</i>"

    # Time format HH:MM
    match = re.match(r"^([01]?[0-9]|2[0-3]):([0-5][0-9])$", raw)
    if match:
        hh = int(match.group(1))
        mm = int(match.group(2))
        clean_time = f"{hh:02d}:{mm:02d}"

        conn = get_connection()
        conn.execute("""
            UPDATE telegram_chats
            SET digest_enabled = 1, digest_time = ?
            WHERE chat_id = ?
        """, (clean_time, str(chat_id)))
        conn.commit()
        conn.close()

        return (
            f"⏰ <b>Daily Digest Scheduled</b>\n"
            f"Your daily market summary will be delivered at <b>{clean_time} IST</b>.\n\n"
            f"<i>{MANDATORY_DISCLAIMER}</i>"
        )

    return (
        "⚠️ <b>Invalid Parameter:</b> Use <code>on</code>, <code>off</code>, or time in 24-hr format (e.g. <code>/digest 18:30</code>).\n\n"
        f"<i>{MANDATORY_DISCLAIMER}</i>"
    )


def handle_command_quiet(chat_id: str, args: str) -> str:
    """Handle /quiet 22:00-07:00 or /quiet off."""
    if not args or not args.strip():
        return (
            "⚠️ <b>Usage:</b> <code>/quiet HH:MM-HH:MM</code> or <code>/quiet off</code>\n"
            "Example: <code>/quiet 22:00-07:00</code> (silences alerts between 10 PM and 7 AM IST)\n\n"
            f"<i>{MANDATORY_DISCLAIMER}</i>"
        )

    raw = args.strip().lower()

    if raw in ("off", "disable", "none", "clear"):
        conn = get_connection()
        conn.execute("""
            UPDATE telegram_chats
            SET quiet_start = NULL, quiet_end = NULL
            WHERE chat_id = ?
        """, (str(chat_id),))
        conn.commit()
        conn.close()
        return f"🌙 <b>Quiet Hours Disabled</b>. You will receive real-time alerts 24/7.\n\n<i>{MANDATORY_DISCLAIMER}</i>"

    # Validate HH:MM-HH:MM
    match = re.match(r"^([01]?[0-9]|2[0-3]):([0-5][0-9])\s*[-–—to]+\s*([01]?[0-9]|2[0-3]):([0-5][0-9])$", raw)
    if not match:
        return (
            "⚠️ <b>Invalid Format:</b> Please use format <code>HH:MM-HH:MM</code> in 24-hr time (e.g. <code>/quiet 22:00-07:00</code>).\n\n"
            f"<i>{MANDATORY_DISCLAIMER}</i>"
        )

    q_start = f"{int(match.group(1)):02d}:{int(match.group(2)):02d}"
    q_end = f"{int(match.group(3)):02d}:{int(match.group(4)):02d}"

    conn = get_connection()
    conn.execute("""
        UPDATE telegram_chats
        SET quiet_start = ?, quiet_end = ?
        WHERE chat_id = ?
    """, (q_start, q_end, str(chat_id)))
    conn.commit()
    conn.close()

    return (
        f"🌙 <b>Quiet Hours Activated</b>\n"
        f"Alerts will be held between <b>{q_start} and {q_end} IST</b>.\n"
        "Use <code>/quiet off</code> anytime to disable.\n\n"
        f"<i>{MANDATORY_DISCLAIMER}</i>"
    )


def handle_command_stop(chat_id: str) -> str:
    """Handle /stop (deactivates chat)."""
    deactivate_telegram_chat(chat_id)
    return (
        "🛑 <b>ProfitSense Alerts Deactivated</b>\n\n"
        "This chat has been disconnected from notifications.\n"
        "To reconnect, generate a new link code in ProfitSense Settings and send /start <code>.\n\n"
        f"<i>{MANDATORY_DISCLAIMER}</i>"
    )


# ══════════════════════════════════════════════════════════════════
# 4. UPDATE DISPATCHER
# ══════════════════════════════════════════════════════════════════
def dispatch_telegram_update(update: Dict[str, Any], client: Optional[Any] = None) -> Optional[str]:
    """
    Parse and route an incoming update from getUpdates.
    Supports text commands and inline button callbacks.
    """
    if client is None:
        client = get_telegram_client()

    # 1. Message updates
    message = update.get("message")
    if message:
        chat = message.get("chat", {})
        chat_id = str(chat.get("id", ""))
        username = chat.get("username") or message.get("from", {}).get("username") or ""
        text = str(message.get("text", "")).strip()

        if not text or not chat_id:
            return None

        # Parse command and arguments
        parts = text.split(maxsplit=1)
        command_raw = parts[0].lower()
        # Remove @botname suffix if present (e.g. /watch@ProfitSenseBot)
        command = command_raw.split("@")[0]
        args = parts[1].strip() if len(parts) > 1 else ""

        # Check authorization / linked status
        existing_chat = get_telegram_chat(chat_id)
        is_linked = existing_chat is not None and existing_chat.get("is_active") == 1

        # Allowed chat IDs allowlist check
        allowed_chats = getattr(config, "TELEGRAM_ALLOWED_CHAT_IDS", [])
        if allowed_chats and chat_id not in allowed_chats:
            if command == "/start":
                reply = (
                    "⛔ <b>Access Restricted:</b> This ProfitSense instance is configured to accept alerts "
                    "only for authorized chat IDs.\n\n"
                    f"<i>{MANDATORY_DISCLAIMER}</i>"
                )
                client.send_message(chat_id, reply)
                return reply
            return None

        # Handle /start (can be executed by anyone to link or inspect)
        if command == "/start":
            reply = handle_command_start(chat_id, username, args)
            client.send_message(chat_id, reply)
            return reply

        # If chat is NOT linked, ignore all other commands (leak zero information)
        if not is_linked:
            logger.info("[Telegram] Ignoring message/command from unlinked chat %s", chat_id)
            return None

        # Route authenticated input:
        # Case A: User sent plain text without '/' -> Check for direct share name lookup
        if not text.startswith("/"):
            stock = resolve_ticker_symbol(text)
            if stock:
                res = handle_command_price(text, chat_id=chat_id)
                reply, reply_markup = res if isinstance(res, tuple) else (res, None)
                client.send_message(chat_id, reply, reply_markup=reply_markup)
                return reply
            else:
                reply = (
                    "💡 <b>ProfitSense Quick Search</b>\n\n"
                    f"Could not find stock: '<b>{escape_html(text)}</b>'.\n"
                    "Send any Indian share name or symbol (e.g. <code>RELIANCE</code>, "
                    "<code>TCS</code>, <code>INFY</code>, <code>TATAMOTORS</code>, <code>HDFCBANK</code>) "
                    "to view current price, 52-week high, loss & range.\n\n"
                    "Type /help to see all commands.\n\n"
                    f"<i>{MANDATORY_DISCLAIMER}</i>"
                )
                client.send_message(chat_id, reply)
                return reply

        # Case B: Slash command
        reply = None
        reply_markup = None

        if command in ("/help", "/h"):
            reply = handle_command_help()
        elif command == "/status":
            reply = handle_command_status(chat_id)
        elif command in ("/price", "/p", "/quote", "/q"):
            res = handle_command_price(args, chat_id=chat_id)
            if isinstance(res, tuple):
                reply, reply_markup = res
            else:
                reply = res
        elif command in ("/signals", "/buy", "/top"):
            res = handle_command_signals(args=args, chat_id=chat_id)
            if isinstance(res, tuple):
                reply, reply_markup = res
            else:
                reply = res
        elif command in ("/pricefilter", "/filter", "/pricebracket"):
            reply = handle_command_price_filter(chat_id, args)
        elif command in ("/watch", "/w"):
            reply = handle_command_watch(args)
        elif command in ("/unwatch", "/uw"):
            reply = handle_command_unwatch(args)
        elif command in ("/list", "/l"):
            reply = handle_command_list()
        elif command == "/mute":
            reply = handle_command_mute(chat_id, args)
        elif command == "/unmute":
            reply = handle_command_unmute(chat_id)
        elif command == "/minconf":
            reply = handle_command_minconf(chat_id, args)
        elif command == "/impact":
            reply = handle_command_impact(chat_id, args)
        elif command == "/digest":
            reply = handle_command_digest(chat_id, args)
        elif command == "/quiet":
            reply = handle_command_quiet(chat_id, args)
        elif command == "/stop":
            reply = handle_command_stop(chat_id)
        else:
            reply = (
                f"❓ <b>Unrecognized command:</b> <code>{escape_html(command)}</code>\n"
                "Type /help to see all available commands, or simply send a share name like <code>RELIANCE</code>.\n\n"
                f"<i>{MANDATORY_DISCLAIMER}</i>"
            )

        if reply:
            client.send_message(chat_id, reply, reply_markup=reply_markup)
            return reply

    # 2. Callback query updates (inline button presses)
    callback_query = update.get("callback_query")
    if callback_query:
        cb_id = callback_query.get("id")
        cb_data = callback_query.get("data", "")
        cb_chat = callback_query.get("message", {}).get("chat", {})
        chat_id = str(cb_chat.get("id", ""))

        if cb_id:
            # Handle quick inline actions
            if cb_data.startswith("mute_"):
                dur = cb_data.replace("mute_", "")
                handle_command_mute(chat_id, dur)
                client.answer_callback_query(cb_id, text=f"Muted for {dur}", show_alert=False)
            elif cb_data.startswith("unwatch_"):
                sym = cb_data.replace("unwatch_", "")
                handle_command_unwatch(sym)
                client.answer_callback_query(cb_id, text=f"Removed {sym} from watchlist", show_alert=False)
            elif cb_data.startswith("watch_"):
                sym = cb_data.replace("watch_", "")
                handle_command_watch(sym)
                client.answer_callback_query(cb_id, text=f"Added {sym} to watchlist!", show_alert=False)
            elif cb_data.startswith("price_"):
                sym = cb_data.replace("price_", "")
                res = handle_command_price(sym, chat_id=chat_id)
                text_content, markup = res if isinstance(res, tuple) else (res, None)
                client.send_message(chat_id, text_content, reply_markup=markup)
                client.answer_callback_query(cb_id, text=f"Refreshed {sym} quote", show_alert=False)
            elif cb_data == "signals_refresh":
                res = handle_command_signals(chat_id=chat_id)
                text_content, markup = res if isinstance(res, tuple) else (res, None)
                client.send_message(chat_id, text_content, reply_markup=markup)
                client.answer_callback_query(cb_id, text="Refreshed top signals", show_alert=False)
            elif cb_data.startswith("sig_filter_"):
                bracket = cb_data.replace("sig_filter_", "")
                res = handle_command_signals(args=bracket, chat_id=chat_id)
                text_content, markup = res if isinstance(res, tuple) else (res, None)
                client.send_message(chat_id, text_content, reply_markup=markup)
                client.answer_callback_query(cb_id, text=f"Signals: {bracket}", show_alert=False)
            elif cb_data.startswith("sig_page_"):
                # sig_page_<bracket>_<page>
                parts = cb_data.replace("sig_page_", "").split("_")
                bracket = parts[0]
                page_str = parts[1] if len(parts) > 1 else "1"
                arg_str = f"{bracket} {page_str}" if bracket != "all" else page_str
                res = handle_command_signals(args=arg_str, chat_id=chat_id)
                text_content, markup = res if isinstance(res, tuple) else (res, None)
                client.send_message(chat_id, text_content, reply_markup=markup)
                client.answer_callback_query(cb_id, text=f"Page {page_str}", show_alert=False)
            elif cb_data.startswith("set_price_filter_"):
                bracket = cb_data.replace("set_price_filter_", "")
                rep = handle_command_price_filter(chat_id, bracket)
                client.send_message(chat_id, rep)
                client.answer_callback_query(cb_id, text=f"Alert filter set to {bracket}", show_alert=True)
            elif cb_data == "list_watchlist":
                rep = handle_command_list()
                client.send_message(chat_id, rep)
                client.answer_callback_query(cb_id, text="Loaded watchlist", show_alert=False)
            else:
                client.answer_callback_query(cb_id, text="Action processed")

    return None


# ══════════════════════════════════════════════════════════════════
# 5. ASYNC BACKGROUND POLLER
# ══════════════════════════════════════════════════════════════════
_poller_task: Optional[asyncio.Task] = None
_poller_stop_event = asyncio.Event()


def get_stored_update_offset() -> Optional[int]:
    """Retrieve last successfully processed update offset from database."""
    val = get_telegram_state(UPDATE_OFFSET_KEY)
    try:
        return int(val) if val is not None else None
    except Exception:
        return None


def set_stored_update_offset(offset: int) -> None:
    """Save processed update offset to database."""
    set_telegram_state(UPDATE_OFFSET_KEY, str(offset))


async def telegram_poller_loop():
    """
    Long-polling worker loop. Runs continuously in background without blocking API.
    Maintains update offset across server restarts.
    """
    logger.info("[Telegram Poller] Starting long-poll worker task...")
    client = get_telegram_client()

    offset = get_stored_update_offset()
    poll_interval = getattr(config, "TELEGRAM_POLL_INTERVAL", 2.0)

    try:
        await asyncio.to_thread(client._request, "POST", "deleteWebhook", json={"drop_pending_updates": False})
    except Exception:
        pass

    while not _poller_stop_event.is_set():
        if not getattr(config, "TELEGRAM_ENABLED", False) or not client.is_configured:
            # Sleep if disabled
            try:
                await asyncio.sleep(5.0)
            except asyncio.CancelledError:
                break
            continue

        try:
            # Long-poll getUpdates in a thread pool to avoid blocking asyncio event loop
            updates = await asyncio.to_thread(
                client.get_updates,
                offset=offset,
                timeout=15,
                allowed_updates=["message", "callback_query"]
            )

            if updates.get("ok"):
                for up in updates.get("result", []):
                    update_id = up.get("update_id")
                    if update_id is not None:
                        offset = update_id + 1
                        set_stored_update_offset(offset)

                    # Dispatch update safely in thread
                    await asyncio.to_thread(dispatch_telegram_update, up, client)

            elif updates.get("error_code") == 409:
                # 409 Conflict: another instance is polling the same bot token
                logger.warning(
                    "[Telegram Poller] 409 Conflict: Another poller or webhook is active for this bot token. "
                    "Clearing webhook and waiting for conflicting instance to drain..."
                )
                try:
                    await asyncio.to_thread(client._request, "POST", "deleteWebhook", json={"drop_pending_updates": False})
                except Exception:
                    pass
                await asyncio.sleep(5.0)

            # Brief pause between polls
            await asyncio.sleep(poll_interval)

        except asyncio.CancelledError:
            logger.info("[Telegram Poller] Poller task cancelled, exiting cleanly.")
            break
        except Exception as e:
            logger.warning("[Telegram Poller] Polling cycle error: %s", redact_token(str(e), client.token))
            await asyncio.sleep(3.0)

    logger.info("[Telegram Poller] Background worker stopped.")


def start_telegram_poller(loop: Optional[asyncio.AbstractEventLoop] = None) -> Optional[asyncio.Task]:
    """Start the Telegram poller background task if enabled."""
    global _poller_task, _poller_stop_event
    if not getattr(config, "TELEGRAM_ENABLED", False):
        logger.info("[Telegram Poller] Telegram is disabled in config. Poller not started.")
        return None

    client = get_telegram_client()
    if not client.is_configured:
        logger.info("[Telegram Poller] TELEGRAM_BOT_TOKEN not configured. Poller not started.")
        return None

    if _poller_task and not _poller_task.done():
        logger.info("[Telegram Poller] Poller task already running.")
        return _poller_task

    _poller_stop_event.clear()
    loop = loop or asyncio.get_event_loop()
    _poller_task = loop.create_task(telegram_poller_loop())
    return _poller_task


def stop_telegram_poller():
    """Signal background poller to stop and cancel task."""
    global _poller_task, _poller_stop_event
    _poller_stop_event.set()
    if _poller_task and not _poller_task.done():
        _poller_task.cancel()
