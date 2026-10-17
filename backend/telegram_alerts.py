"""
telegram_alerts.py — Intelligent Alert Dispatcher & Evening Digest Engine for ProfitSense
========================================================================================
Handles:
  1. Filtering: min impact, min confidence, direction, watchlist-only, quiet hours
     (with midnight-crossing support), mute timers, stale news skip (>6h), and hourly capping (10/hr).
  2. Deduplication via telegram_alert_log (chat_id, article_id, ticker).
  3. Signal alert formatting with HTML styling, model predictions, inline buttons
     (Open in ProfitSense, Mute 2h, Unwatch), and mandatory compliance disclaimer.
  4. Evening Daily Market Digest (18:30 IST / scheduled time) with market pulse and top catalysts.
  5. Safe dispatching hooked into news synchronization that never blocks or crashes.

HARD RULE: Every alert and digest ends with:
"AI/model estimate — not investment advice."
"""

import os
import re
import json
import logging
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple, Set

import config
from database import (
    get_connection,
    list_telegram_chats,
    is_telegram_alert_sent,
    record_telegram_alert,
    count_recent_telegram_alerts,
    get_telegram_chat,
)
from telegram_client import get_telegram_client, escape_html
from ml_pipeline import predict_article

logger = logging.getLogger("telegram_alerts")

MANDATORY_DISCLAIMER = "AI/model estimate — not investment advice."
MAX_ALERTS_PER_HOUR = 10
MAX_NEWS_AGE_HOURS = 6.0
IST_OFFSET = timedelta(hours=5, minutes=30)
IST_TZ = timezone(IST_OFFSET, name="IST")


# ══════════════════════════════════════════════════════════════════
# 1. TIME & FILTER UTILITIES
# ══════════════════════════════════════════════════════════════════
def get_current_ist_time() -> datetime:
    """Return current datetime in Indian Standard Time (UTC+5:30)."""
    return datetime.now(timezone.utc).astimezone(IST_TZ)


def parse_datetime_flexible(dt_str: Optional[str]) -> Optional[datetime]:
    """Parse various datetime string formats into UTC-aware datetime."""
    if not dt_str:
        return None
    clean = str(dt_str).strip()
    # Try ISO
    try:
        dt = datetime.fromisoformat(clean)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass

    # Try common formats
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%Y%m%dT%H%M%S",
        "%d %b %Y %H:%M:%S",
        "%d %b %Y",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(clean[:19], fmt)
            return dt.replace(tzinfo=timezone.utc)
        except Exception:
            continue
    return None


def is_muted(chat: Dict[str, Any], now: Optional[datetime] = None) -> bool:
    """
    Check if chat is currently muted.
    Returns True if muted_until is in the future.
    """
    muted_until_str = chat.get("muted_until")
    if not muted_until_str:
        return False

    muted_dt = parse_datetime_flexible(muted_until_str)
    if not muted_dt:
        return False

    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    return now < muted_dt


def is_quiet_hours(
    quiet_start: Optional[str],
    quiet_end: Optional[str],
    now: Optional[datetime] = None
) -> bool:
    """
    Check if `now` (default current IST) falls inside [quiet_start, quiet_end].
    Correctly supports windows crossing midnight (e.g. '22:00' to '07:00').
    Format expected: 'HH:MM'.
    """
    if not quiet_start or not quiet_end:
        return False

    time_re = r"^([01]?[0-9]|2[0-3]):([0-5][0-9])$"
    m_start = re.match(time_re, quiet_start.strip())
    m_end = re.match(time_re, quiet_end.strip())
    if not m_start or not m_end:
        return False

    s_hour, s_min = int(m_start.group(1)), int(m_start.group(2))
    e_hour, e_min = int(m_end.group(1)), int(m_end.group(2))

    start_mins = s_hour * 60 + s_min
    end_mins = e_hour * 60 + e_min

    if start_mins == end_mins:
        return False  # Zero duration window

    if now is None:
        now = get_current_ist_time()
    elif now.tzinfo is None:
        now = now.replace(tzinfo=IST_TZ)
    else:
        now = now.astimezone(IST_TZ)

    cur_mins = now.hour * 60 + now.minute

    # Standard case: does not cross midnight (e.g. 13:00 to 15:00)
    if start_mins < end_mins:
        return start_mins <= cur_mins < end_mins

    # Midnight crossing case (e.g. 22:00 to 07:00)
    return cur_mins >= start_mins or cur_mins < end_mins


def is_stale_news(
    published_at: Optional[str],
    max_age_hours: float = MAX_NEWS_AGE_HOURS,
    now: Optional[datetime] = None
) -> bool:
    """Check if article published timestamp is older than max_age_hours (default 6h)."""
    if not published_at:
        return False

    pub_dt = parse_datetime_flexible(published_at)
    if not pub_dt:
        return False

    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    age_seconds = (now - pub_dt).total_seconds()
    return age_seconds > (max_age_hours * 3600.0)


def normalize_impact_level(impact_str: Optional[str]) -> int:
    """Map impact string to integer priority (3=HIGH, 2=MEDIUM/MODERATE, 1=LOW)."""
    val = str(impact_str or "").strip().upper()
    if val == "HIGH":
        return 3
    if val in ("MEDIUM", "MODERATE", "MED"):
        return 2
    return 1


def normalize_confidence(conf_val: Any) -> float:
    """Normalize confidence from 0-100 or 0.0-1.0 into 0.0-1.0."""
    try:
        f = float(conf_val)
        if f > 1.0:
            f = f / 100.0
        return max(0.0, min(1.0, f))
    except Exception:
        return 0.5


def normalize_ticker_symbol(ticker: Optional[str]) -> str:
    """Strip .NS / .BO and upper-case."""
    if not ticker:
        return ""
    t = str(ticker).strip().upper()
    for ext in (".NS", ".BO"):
        if t.endswith(ext):
            t = t[:-len(ext)]
    return t


def normalize_direction(dir_val: Optional[str]) -> str:
    """Normalize direction to BULLISH, BEARISH, or NEUTRAL."""
    val = str(dir_val or "").strip().upper()
    if val in ("UP", "BULLISH", "POSITIVE"):
        return "BULLISH"
    if val in ("DOWN", "BEARISH", "NEGATIVE"):
        return "BEARISH"
    return "NEUTRAL"


# ══════════════════════════════════════════════════════════════════
# 2. FILTER EVALUATION PIPELINE
# ══════════════════════════════════════════════════════════════════
def evaluate_alert_filters(
    chat: Dict[str, Any],
    article: Dict[str, Any],
    analysis: Dict[str, Any],
    watchlist_tickers: Optional[Set[str]] = None,
    now: Optional[datetime] = None,
    conn: Optional[sqlite3.Connection] = None
) -> Tuple[bool, str]:
    """
    Evaluate all filtering rules for sending an alert to a specific chat.
    Returns (should_send, reason).
    """
    chat_id = str(chat.get("chat_id", ""))

    # 1. Active status
    if int(chat.get("is_active", 0)) != 1:
        return False, "Chat is inactive"

    # 2. Muted timer
    if is_muted(chat, now=now):
        return False, "Chat is currently muted"

    # 3. Quiet hours
    if is_quiet_hours(chat.get("quiet_start"), chat.get("quiet_end"), now=now):
        return False, "Current time is in quiet hours"

    # 4. Stale news (>6 hours old)
    pub_date = article.get("published_at") or article.get("created_at")
    if is_stale_news(pub_date, max_age_hours=MAX_NEWS_AGE_HOURS, now=now):
        return False, "News article is older than 6 hours"

    # 5. Deduplication
    art_id = str(article.get("id", ""))
    ticker_clean = normalize_ticker_symbol(analysis.get("ticker") or article.get("ticker", ""))
    if not art_id or not ticker_clean:
        return False, "Missing article ID or ticker"

    if is_telegram_alert_sent(chat_id, art_id, ticker_clean, conn=conn):
        return False, "Alert already sent previously (dedupe)"

    # 6. Minimum Impact Level
    min_impact_chat = str(chat.get("min_impact", "HIGH")).strip().upper()
    art_impact = str(analysis.get("impact_level", "LOW")).strip().upper()

    req_score = normalize_impact_level(min_impact_chat)
    art_score = normalize_impact_level(art_impact)
    if min_impact_chat != "ALL" and art_score < req_score:
        return False, f"Impact {art_impact} does not meet requirement {min_impact_chat}"

    # 7. Minimum Confidence
    chat_min_conf = normalize_confidence(chat.get("min_confidence", 0.6))
    art_conf = normalize_confidence(analysis.get("confidence", 0.5))
    if art_conf < chat_min_conf:
        return False, f"Confidence {art_conf:.2f} below chat minimum {chat_min_conf:.2f}"

    # 8. Direction Filter
    art_dir = normalize_direction(analysis.get("direction"))
    dirs_raw = chat.get("directions")
    allowed_dirs = ["BULLISH", "BEARISH"]
    if dirs_raw:
        try:
            allowed_dirs = json.loads(dirs_raw)
            if not isinstance(allowed_dirs, list):
                allowed_dirs = ["BULLISH", "BEARISH"]
        except Exception:
            allowed_dirs = ["BULLISH", "BEARISH"]

    allowed_dirs_norm = [normalize_direction(d) for d in allowed_dirs]
    if "ALL" not in [d.upper() for d in allowed_dirs] and art_dir not in allowed_dirs_norm:
        return False, f"Direction {art_dir} not in allowed directions {allowed_dirs}"

    # 9. Watchlist Only Filter
    if int(chat.get("watchlist_only", 0)) == 1:
        if watchlist_tickers is None:
            # Query watchlist
            wl_conn = conn or get_connection()
            try:
                cur = wl_conn.execute("SELECT ticker FROM watchlist")
                watchlist_tickers = {normalize_ticker_symbol(r[0]) for r in cur.fetchall()}
            finally:
                if conn is None:
                    wl_conn.close()

        if ticker_clean not in watchlist_tickers:
            return False, f"Ticker {ticker_clean} is not in user's watchlist"

    # 10. Price Bracket Filter (0-500, 500-1000, 1000+)
    chat_brackets_raw = chat.get("price_brackets")
    if chat_brackets_raw:
        try:
            if isinstance(chat_brackets_raw, str):
                allowed_brackets = json.loads(chat_brackets_raw)
            elif isinstance(chat_brackets_raw, list):
                allowed_brackets = chat_brackets_raw
            else:
                allowed_brackets = ["0-500", "500-1000", "1000+"]
        except Exception:
            allowed_brackets = ["0-500", "500-1000", "1000+"]
    else:
        allowed_brackets = ["0-500", "500-1000", "1000+"]

    if not isinstance(allowed_brackets, list):
        allowed_brackets = [str(allowed_brackets)]

    upper_brackets = [str(b).upper().strip() for b in allowed_brackets]
    if "ALL" not in upper_brackets and set(upper_brackets) != {"0-500", "500-1000", "1000+"}:
        # Determine current stock price
        stock_price = None
        for key in ("current_price", "price", "close"):
            if key in analysis and analysis[key] is not None:
                try:
                    val = float(analysis[key])
                    if val > 0:
                        stock_price = val
                        break
                except Exception:
                    pass

        if stock_price is None or stock_price <= 0:
            try:
                from price_brackets import get_stock_price_info
                p_info = get_stock_price_info(ticker_clean)
                stock_price = p_info.get("price")
            except Exception:
                stock_price = None

        if stock_price is not None and stock_price > 0:
            if stock_price <= 500.0:
                art_bracket = "0-500"
            elif stock_price <= 1000.0:
                art_bracket = "500-1000"
            else:
                art_bracket = "1000+"

            allowed_clean = [
                str(b).lower().replace(" ", "").replace("₹", "").replace("_to_", "-").replace("under_", "0-").replace("above_", "")
                for b in allowed_brackets
            ]
            if art_bracket not in allowed_clean:
                return False, f"Stock price ₹{stock_price:.1f} ({art_bracket}) not in chat allowed price brackets {allowed_brackets}"

    # 11. Hourly Rate Cap (Max 10 alerts per hour)
    recent_count = count_recent_telegram_alerts(chat_id, minutes=60, conn=conn)
    if recent_count >= MAX_ALERTS_PER_HOUR:
        return False, f"Hourly alert cap reached ({recent_count}/{MAX_ALERTS_PER_HOUR})"

    return True, "OK"


# ══════════════════════════════════════════════════════════════════
# 3. ALERT RENDERING & MESSAGE FORMATTING
# ══════════════════════════════════════════════════════════════════
def format_signal_alert(
    article: Dict[str, Any],
    analysis: Dict[str, Any],
    predictions: Optional[Dict[str, Any]] = None
) -> Tuple[str, Dict[str, Any]]:
    """
    Render formatted HTML alert message and inline keyboard markup.
    Returns (html_text, reply_markup_dict).
    """
    ticker_raw = analysis.get("ticker") or article.get("ticker") or "EQUITY"
    clean_ticker = normalize_ticker_symbol(ticker_raw)
    company_name = analysis.get("company_name") or article.get("company") or clean_ticker
    title = article.get("title") or "Market Catalyst Update"
    event_display = analysis.get("event_display") or analysis.get("event_type", "Catalyst").replace("_", " ").title()
    sector = analysis.get("sector") or "Indian Equities"
    impact = (analysis.get("impact_level") or "HIGH").upper()
    direction = normalize_direction(analysis.get("direction"))
    confidence_pct = int(round(normalize_confidence(analysis.get("confidence", 0.6)) * 100))

    # Emojis and signal cues
    if direction == "BULLISH":
        emoji = "🟢"
        signal_badge = "BULLISH SIGNAL"
    elif direction == "BEARISH":
        emoji = "🔴"
        signal_badge = "BEARISH SIGNAL"
    else:
        emoji = "⚪"
        signal_badge = "NEUTRAL UPDATE"

    # ML Predictions summary
    preds_lines = []
    if predictions:
        p1 = predictions.get("1d", {}).get("ensemble")
        p3 = predictions.get("3d", {}).get("ensemble")
        if p1:
            p1_emoji = "📈" if p1 == "Positive" else ("📉" if p1 == "Negative" else "➡️")
            preds_lines.append(f"• <b>1D Horizon:</b> {p1_emoji} {p1}")
        if p3:
            p3_emoji = "📈" if p3 == "Positive" else ("📉" if p3 == "Negative" else "➡️")
            preds_lines.append(f"• <b>3D Horizon:</b> {p3_emoji} {p3}")

    preds_block = "\n" + "\n".join(preds_lines) + "\n" if preds_lines else ""

    # Reason explanation
    explanation = analysis.get("reason_explanation") or article.get("summary") or ""
    clean_expl = ""
    if explanation:
        # Keep explanation concise
        if len(explanation) > 280:
            clean_expl = explanation[:277] + "..."
        else:
            clean_expl = explanation
        clean_expl = f"\n💡 <i>{escape_html(clean_expl)}</i>\n"

    # Price and bracket line
    stock_price = None
    for key in ("current_price", "price", "close"):
        if key in analysis and analysis[key] is not None:
            try:
                val = float(analysis[key])
                if val > 0:
                    stock_price = val
                    break
            except Exception:
                pass
    if stock_price is None or stock_price <= 0:
        try:
            from price_brackets import get_stock_price_info
            p_info = get_stock_price_info(clean_ticker)
            stock_price = p_info.get("price")
        except Exception:
            stock_price = None

    price_line = ""
    if stock_price is not None and stock_price > 0:
        try:
            from price_brackets import get_signal_price_bracket
            b_key, b_label = get_signal_price_bracket(stock_price, clean_ticker)
            price_line = f"• <b>Price:</b> ₹{stock_price:,.2f} ({b_label})\n"
        except Exception:
            price_line = f"• <b>Price:</b> ₹{stock_price:,.2f}\n"

    # Assemble message HTML
    msg = (
        f"{emoji} <b>{signal_badge} | {escape_html(clean_ticker)}</b>\n"
        f"<b>{escape_html(company_name)}</b>\n\n"
        f"📰 <b>{escape_html(title)}</b>\n\n"
        f"• <b>Impact:</b> {escape_html(impact)}\n"
        f"• <b>Event:</b> {escape_html(event_display)}\n"
        f"• <b>Sector:</b> {escape_html(sector)}\n"
        f"{price_line}"
        f"• <b>Confidence:</b> {confidence_pct}%"
        f"{preds_block}"
        f"{clean_expl}\n"
        f"<i>{MANDATORY_DISCLAIMER}</i>"
    )

    # Inline Keyboard Buttons
    base_url = getattr(config, "APP_BASE_URL", "http://localhost:5173").rstrip("/")
    art_id = article.get("id", "")
    open_url = f"{base_url}/?article={art_id}" if art_id else f"{base_url}/"

    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "📊 Open in ProfitSense", "url": open_url}
            ],
            [
                {"text": "🔕 Mute 2h", "callback_data": "mute_2h"},
                {"text": f"❌ Unwatch {clean_ticker}", "callback_data": f"unwatch_{clean_ticker}"}
            ]
        ]
    }

    return msg, reply_markup


# ══════════════════════════════════════════════════════════════════
# 4. EVENING DAILY DIGEST FORMATTING
# ══════════════════════════════════════════════════════════════════
def format_daily_digest(
    chat: Dict[str, Any],
    top_articles: List[Dict[str, Any]],
    stats: Optional[Dict[str, Any]] = None
) -> str:
    """
    Format evening daily market digest ending with the mandatory disclaimer.
    """
    ist_now = get_current_ist_time()
    date_str = ist_now.strftime("%d %b %Y")

    stats = stats or {}
    total_catalysts = stats.get("total_articles", len(top_articles))
    bull_count = stats.get("bullish_count", 0)
    bear_count = stats.get("bearish_count", 0)

    # Header
    header = (
        f"📰 <b>ProfitSense Daily Market Digest</b>\n"
        f"📅 <i>{date_str} • Evening Edition</i>\n\n"
        f"📊 <b>Market Pulse Today:</b>\n"
        f"• Total Analyzed Catalysts: <b>{total_catalysts}</b>\n"
        f"• Bullish Signals: 🟢 <b>{bull_count}</b>\n"
        f"• Bearish Signals: 🔴 <b>{bear_count}</b>\n\n"
        f"⭐ <b>Key High-Impact Highlights:</b>\n"
    )

    items = []
    for i, item in enumerate(top_articles[:5], 1):
        ticker = item.get("ticker", "EQUITY")
        clean_tick = normalize_ticker_symbol(ticker)
        title = item.get("title", "")
        if len(title) > 90:
            title = title[:87] + "..."
        direction = normalize_direction(item.get("direction"))
        badge = "🟢" if direction == "BULLISH" else ("🔴" if direction == "BEARISH" else "⚪")
        items.append(f"{i}. {badge} <b>{escape_html(clean_tick)}</b>: {escape_html(title)}")

    if not items:
        body = "<i>No major high-impact catalysts recorded during market hours today.</i>\n\n"
    else:
        body = "\n".join(items) + "\n\n"

    footer = f"<i>{MANDATORY_DISCLAIMER}</i>"
    return header + body + footer


# ══════════════════════════════════════════════════════════════════
# 5. DISPATCHER ENGINE
# ══════════════════════════════════════════════════════════════════
def dispatch_signal_alert_for_article(
    article_id: str,
    client: Optional[Any] = None,
    now: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Dispatch a single article's alert to all eligible active chats.
    Guaranteed never to crash or throw uncaught exceptions.
    """
    if client is None:
        client = get_telegram_client()

    if not getattr(config, "TELEGRAM_ENABLED", False) or not client.is_configured:
        return {"status": "skipped", "reason": "Telegram disabled or not configured"}

    conn = get_connection()
    try:
        # Fetch article & analysis
        cur = conn.execute("""
            SELECT a.id, a.title, a.summary, a.published_at, a.created_at,
                   an.ticker, an.company_name, an.sentiment_score, an.event_type,
                   an.event_display, an.sector, an.confidence, an.direction,
                   an.impact_level, an.reason_explanation
            FROM articles a
            JOIN analysis an ON a.id = an.article_id
            WHERE a.id = ?
        """, (str(article_id),))
        row = cur.fetchone()
        if not row:
            return {"status": "skipped", "reason": f"Article {article_id} not found with analysis"}

        art_dict = {
            "id": row[0],
            "title": row[1],
            "summary": row[2],
            "published_at": row[3],
            "created_at": row[4],
        }
        an_dict = {
            "ticker": row[5],
            "company_name": row[6],
            "sentiment_score": row[7],
            "event_type": row[8],
            "event_display": row[9],
            "sector": row[10],
            "confidence": row[11],
            "direction": row[12],
            "impact_level": row[13],
            "reason_explanation": row[14],
        }

        # Check ticker validity
        raw_ticker = an_dict["ticker"]
        if not raw_ticker:
            return {"status": "skipped", "reason": "No ticker in analysis"}

        # Run ML model inference for 1D and 3D horizons
        preds = None
        try:
            preds = predict_article(an_dict, art_dict.get("published_at"))
        except Exception as pred_err:
            logger.debug("[Telegram Alerts] Model prediction error: %s", pred_err)

        # Pre-cache watchlist tickers
        cur_wl = conn.execute("SELECT ticker FROM watchlist")
        watchlist_tickers = {normalize_ticker_symbol(r[0]) for r in cur_wl.fetchall()}

        active_chats = list_telegram_chats(active_only=True, conn=conn)
        sent_count = 0
        skipped_count = 0

        for chat in active_chats:
            chat_id = str(chat["chat_id"])
            should_send, reason = evaluate_alert_filters(
                chat=chat,
                article=art_dict,
                analysis=an_dict,
                watchlist_tickers=watchlist_tickers,
                now=now,
                conn=conn
            )

            if not should_send:
                skipped_count += 1
                logger.debug("[Telegram Alerts] Skipping chat %s for article %s: %s", chat_id, article_id, reason)
                continue

            # Format alert message and keyboard
            msg_text, reply_markup = format_signal_alert(art_dict, an_dict, preds)

            try:
                res = client.send_message(
                    chat_id=chat_id,
                    text=msg_text,
                    reply_markup=reply_markup
                )
                if res.get("ok"):
                    record_telegram_alert(
                        chat_id=chat_id,
                        article_id=art_dict["id"],
                        ticker=an_dict["ticker"],
                        status="SENT",
                        conn=conn
                    )
                    sent_count += 1
                    logger.info("[Telegram Alerts] Alert sent to chat %s for %s", chat_id, an_dict["ticker"])
                else:
                    err_desc = res.get("description", "Unknown Telegram send error")
                    record_telegram_alert(
                        chat_id=chat_id,
                        article_id=art_dict["id"],
                        ticker=an_dict["ticker"],
                        status="FAILED",
                        error=err_desc,
                        conn=conn
                    )
                    logger.warning("[Telegram Alerts] Failed to send to chat %s: %s", chat_id, err_desc)
            except Exception as send_err:
                record_telegram_alert(
                    chat_id=chat_id,
                    article_id=art_dict["id"],
                    ticker=an_dict["ticker"],
                    status="FAILED",
                    error=str(send_err),
                    conn=conn
                )
                logger.error("[Telegram Alerts] Exception sending alert to chat %s: %s", chat_id, send_err)

        return {
            "status": "success",
            "article_id": article_id,
            "sent_count": sent_count,
            "skipped_count": skipped_count
        }

    except Exception as e:
        logger.error("[Telegram Alerts] Top-level dispatch error on article %s: %s", article_id, e)
        return {"status": "error", "message": str(e)}
    finally:
        conn.close()


def dispatch_all_pending_alerts(
    limit: int = 30,
    client: Optional[Any] = None,
    now: Optional[datetime] = None
):
    """
    Scan recent articles and dispatch alerts to active chats.
    Invoked periodically by background news synchronizer.
    """
    conn = get_connection()
    try:
        cur = conn.execute("""
            SELECT a.id
            FROM articles a
            JOIN analysis an ON a.id = an.article_id
            WHERE an.ticker IS NOT NULL AND an.ticker != ''
            ORDER BY a.published_at DESC
            LIMIT ?
        """, (int(limit),))
        article_ids = [r[0] for r in cur.fetchall()]
    finally:
        conn.close()

    total_sent = 0
    for aid in article_ids:
        try:
            res = dispatch_signal_alert_for_article(aid, client=client, now=now)
            total_sent += res.get("sent_count", 0)
        except Exception as e:
            logger.warning("[Telegram Alerts] Error dispatching pending article %s: %s", aid, e)

    return {"status": "completed", "articles_checked": len(article_ids), "alerts_sent": total_sent}


def check_and_send_daily_digests(
    now: Optional[datetime] = None,
    client: Optional[Any] = None
) -> int:
    """
    Check if any chats with digest_enabled == 1 are due for their evening digest.
    Guaranteed not to duplicate on the same date.
    Returns count of digests sent.
    """
    if client is None:
        client = get_telegram_client()

    if not getattr(config, "TELEGRAM_ENABLED", False) or not client.is_configured:
        return 0

    if now is None:
        now = get_current_ist_time()
    elif now.tzinfo is None:
        now = now.replace(tzinfo=IST_TZ)
    else:
        now = now.astimezone(IST_TZ)

    today_str = now.strftime("%Y-%m-%d")
    cur_time_hm = now.strftime("%H:%M")

    conn = get_connection()
    sent_digests = 0
    try:
        chats = list_telegram_chats(active_only=True, conn=conn)

        for chat in chats:
            chat_id = str(chat["chat_id"])
            if int(chat.get("digest_enabled", 0)) != 1:
                continue

            # Respect quiet hours for daily digest as well
            if is_quiet_hours(chat.get("quiet_start"), chat.get("quiet_end"), now=now):
                continue

            # Respect mute timer
            if is_muted(chat, now=now):
                continue

            digest_time = str(chat.get("digest_time") or "18:30").strip()
            # Send if within current 15-minute window or exact minute
            # For testing and cron schedules, we compare HH:MM
            if digest_time != cur_time_hm:
                continue

            # Deduplication key in telegram_alert_log: article_id = f"digest_{today_str}", ticker = "MARKET"
            digest_key = f"digest_{today_str}"
            if is_telegram_alert_sent(chat_id, digest_key, "MARKET", conn=conn):
                continue

            # Compile today's articles
            cur = conn.execute("""
                SELECT a.id, a.title, an.ticker, an.direction, an.impact_level, an.confidence
                FROM articles a
                JOIN analysis an ON a.id = an.article_id
                WHERE a.published_at >= datetime('now', '-24 hours')
                ORDER BY an.impact_level DESC, a.published_at DESC
                LIMIT 20
            """)
            rows = cur.fetchall()

            top_arts = []
            bull_count = 0
            bear_count = 0
            for r in rows:
                direction = normalize_direction(r[3])
                if direction == "BULLISH":
                    bull_count += 1
                elif direction == "BEARISH":
                    bear_count += 1

                top_arts.append({
                    "id": r[0],
                    "title": r[1],
                    "ticker": r[2],
                    "direction": direction,
                    "impact_level": r[4],
                    "confidence": r[5]
                })

            stats = {
                "total_articles": len(top_arts),
                "bullish_count": bull_count,
                "bearish_count": bear_count
            }

            msg_text = format_daily_digest(chat, top_arts, stats)
            try:
                res = client.send_message(chat_id=chat_id, text=msg_text)
                if res.get("ok"):
                    record_telegram_alert(chat_id, digest_key, "MARKET", status="SENT", conn=conn)
                    sent_digests += 1
                    logger.info("[Telegram Digest] Sent daily digest to chat %s for %s", chat_id, today_str)
                else:
                    err_desc = res.get("description", "Send failed")
                    record_telegram_alert(chat_id, digest_key, "MARKET", status="FAILED", error=err_desc, conn=conn)
            except Exception as e:
                logger.error("[Telegram Digest] Exception sending digest to chat %s: %s", chat_id, e)

        return sent_digests
    finally:
        conn.close()
