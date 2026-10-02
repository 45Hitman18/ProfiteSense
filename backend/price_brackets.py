"""
price_brackets.py — Share Price Segmentation & Categorization Engine
=====================================================================
Divides Indian shares and market news into 3 clear investment & trading price brackets:
1. UNDER_500   : ₹0 to ₹500      (Affordable, Small & Mid-Cap, High Retail Participation)
2. 500_TO_2000 : ₹500 to ₹2,000  (Core, Mainstream Momentum & Quality Mid/Large-Caps)
3. ABOVE_2000  : ₹2,000+         (Heavyweights, Premium Quality & Bluechip Leaders)
"""

from typing import Dict, Any, Optional, List, Tuple
from database import get_connection

# Curated reference price baseline for top Indian stocks
# Used as instant fallback if live provider quote is cold/offline
STOCK_BASELINE_PRICES: Dict[str, float] = {
    # ── Bracket 1: ₹0 to ₹500 ─────────────────────────────────────────
    "TATASTEEL.NS": 152.40,
    "ONGC.NS": 264.80,
    "COALINDIA.NS": 422.50,
    "NTPC.NS": 372.10,
    "POWERGRID.NS": 308.60,
    "ITC.NS": 482.30,
    "BEL.NS": 286.40,
    "ZOMATO.NS": 268.50,
    "JIOFIN.NS": 318.00,
    "BHEL.NS": 248.90,
    "IRFC.NS": 156.20,
    "RVNL.NS": 388.40,
    "IREDA.NS": 212.50,
    "SUZLON.NS": 62.40,
    "YESBANK.NS": 21.80,
    "OLAELEC.NS": 76.50,
    "MOTHERSON.NS": 146.20,
    "SWIGGY.NS": 492.00,
    "IDEA.NS": 10.40,
    "VEDL.NS": 456.00,
    "TATAPOWER.NS": 396.50,
    "PAYTM.NS": 420.00,
    "DELHIVERY.NS": 384.50,
    "NYKAA.NS": 178.20,
    "IDFCFIRSTB.NS": 72.80,
    "FEDERALBNK.NS": 186.50,
    "PNB.NS": 104.80,
    "BANKBARODA.NS": 248.50,
    "CANBK.NS": 102.40,
    "UNIONBANK.NS": 122.00,
    "IOC.NS": 144.50,
    "GAIL.NS": 178.60,
    "AMBUJACEM.NS": 486.00,
    "HUDCO.NS": 218.40,
    "NHPC.NS": 92.50,
    "PFC.NS": 482.00,
    "RECLTD.NS": 494.50,
    "SAIL.NS": 126.80,
    "NMDC.NS": 224.50,
    "EXIDEIND.NS": 448.00,
    "BIOCON.NS": 342.00,

    # ── Bracket 2: ₹500 to ₹2,000 ─────────────────────────────────────
    "SBIN.NS": 824.50,
    "TATAMOTORS.NS": 924.80,
    "ICICIBANK.NS": 1262.40,
    "HDFCBANK.NS": 1664.20,
    "INFY.NS": 1888.50,
    "AXISBANK.NS": 1162.00,
    "WIPRO.NS": 546.80,
    "HCLTECH.NS": 1784.00,
    "ADANIENT.NS": 1948.00,
    "ADANIPORTS.NS": 1284.50,
    "JSWSTEEL.NS": 984.00,
    "M&M.NS": 1982.00,
    "BAJAJFINSV.NS": 1895.60,
    "GRASIM.NS": 1992.00,
    "TECHM.NS": 1524.00,
    "HINDALCO.NS": 662.50,
    "CIPLA.NS": 1564.00,
    "SUNPHARMA.NS": 1782.00,
    "TATACONSUM.NS": 962.40,
    "INDUSINDBK.NS": 1452.00,
    "BPCL.NS": 632.50,
    "SHRIRAMFIN.NS": 1954.00,
    "BHARTIARTL.NS": 1624.00,
    "TVSMOTOR.NS": 1985.00,
    "INDIGO.NS": 1950.00,
    "DLF.NS": 782.40,
    "PRESTIGE.NS": 1625.00,
    "VBL.NS": 582.00,
    "HAVELLS.NS": 1754.00,
    "GODREJCP.NS": 1286.00,
    "DABUR.NS": 534.50,
    "JINDALSTEL.NS": 926.00,
    "APOLLOTYRE.NS": 512.00,
    "LUPIN.NS": 1956.00,
    "AUROPHARMA.NS": 1385.00,
    "KPITTECH.NS": 1654.00,
    "POLICYBZR.NS": 1456.00,
    "IRCTC.NS": 864.00,

    # ── Bracket 3: ₹2,000+ ────────────────────────────────────────────
    "RELIANCE.NS": 2954.00,
    "TCS.NS": 4256.00,
    "LT.NS": 3658.00,
    "KOTAKBANK.NS": 2082.00,
    "HINDUNILVR.NS": 2624.00,
    "BAJFINANCE.NS": 7254.00,
    "MARUTI.NS": 12240.00,
    "TITAN.NS": 3482.00,
    "ASIANPAINT.NS": 2785.00,
    "ULTRACEMCO.NS": 11250.00,
    "NESTLEIND.NS": 2386.00,
    "DRREDDY.NS": 6512.00,
    "APOLLOHOSP.NS": 7120.00,
    "DIVISLAB.NS": 4954.00,
    "EICHERMOT.NS": 4862.00,
    "BAJAJ-AUTO.NS": 9720.00,
    "HEROMOTOCO.NS": 5320.00,
    "BRITANNIA.NS": 5164.00,
    "LTIM.NS": 5912.00,
    "TRENT.NS": 7624.00,
    "HAL.NS": 4360.00,
    "MAZDOCK.NS": 4210.00,
    "COCHINSHIP.NS": 2154.00,
    "DMART.NS": 4120.00,
    "BAJAJHLDNG.NS": 8920.00,
    "SIEMENS.NS": 7120.00,
    "ABB.NS": 7840.00,
    "POLYCAB.NS": 6820.00,
    "PIDILITIND.NS": 3120.00,
    "MRF.NS": 132400.00,
    "BOSCHLTD.NS": 33600.00,
    "PERSISTENT.NS": 5460.00,
    "COFORGE.NS": 7920.00,
    "TATAELXSI.NS": 6960.00,
    "BSE.NS": 3854.00,
    "MCX.NS": 5860.00,
    "CDSL.NS": 2860.00,
}

BRACKET_CONFIG = {
    "UNDER_500": {
        "id": "UNDER_500",
        "label": "₹0 – ₹500",
        "title": "Under ₹500 (Budget & Small/Mid)",
        "min": 0.0,
        "max": 500.0,
        "color": "#059669",
        "bg": "#ECFDF5",
        "border": "#A7F3D0"
    },
    "500_TO_2000": {
        "id": "500_TO_2000",
        "label": "₹500 – ₹2,000",
        "title": "₹500 to ₹2,000 (Core & Momentum)",
        "min": 500.0,
        "max": 2000.0,
        "color": "#2563EB",
        "bg": "#EFF6FF",
        "border": "#BFDBFE"
    },
    "ABOVE_2000": {
        "id": "ABOVE_2000",
        "label": "₹2,000+",
        "title": "₹2,000 & Above (Bluechips & Leaders)",
        "min": 2000.0,
        "max": float("inf"),
        "color": "#7C3AED",
        "bg": "#F5F3FF",
        "border": "#DDD6FE"
    },
    "MACRO": {
        "id": "MACRO",
        "label": "Macro / Index",
        "title": "Macro / Benchmark / Commodities",
        "min": -1.0,
        "max": -1.0,
        "color": "#78716C",
        "bg": "#F5F5F4",
        "border": "#E7E5E4"
    }
}


def classify_price_bracket(price: Optional[float], ticker: str = "") -> Tuple[str, str, Dict[str, str]]:
    """
    Given a share price (or ticker), returns (bracket_id, bracket_label, styling_dict).
    """
    clean = (ticker or "").upper().strip()
    if clean in ("^NSEI", "^BSESN", "BZ=F", "INR=X", "^VIX", "^GSPC", "^DJI") or not clean or clean.startswith("^"):
        cfg = BRACKET_CONFIG["MACRO"]
        return cfg["id"], cfg["label"], cfg

    if price is None or price <= 0:
        # Check baseline mapping
        if clean in STOCK_BASELINE_PRICES:
            price = STOCK_BASELINE_PRICES[clean]
        elif clean + ".NS" in STOCK_BASELINE_PRICES:
            price = STOCK_BASELINE_PRICES[clean + ".NS"]
        else:
            # Query stock_price database table
            try:
                conn = get_connection()
                row = conn.execute("SELECT close FROM stock_price WHERE ticker=? ORDER BY date DESC LIMIT 1", (clean,)).fetchone()
                conn.close()
                if row and row["close"] is not None:
                    price = float(row["close"])
            except Exception:
                price = None

    if price is None or price <= 0:
        cfg = BRACKET_CONFIG["MACRO"]
        return cfg["id"], cfg["label"], cfg

    if price <= 500.0:
        cfg = BRACKET_CONFIG["UNDER_500"]
    elif price <= 2000.0:
        cfg = BRACKET_CONFIG["500_TO_2000"]
    else:
        cfg = BRACKET_CONFIG["ABOVE_2000"]

    return cfg["id"], cfg["label"], cfg


def get_stock_price_info(ticker: str, quote: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Determines share price, change pct, and price bracket for any ticker.
    """
    clean = (ticker or "").upper().strip()
    price = None
    change_pct = 0.0

    if quote and quote.get("price") is not None and float(quote.get("price") or 0) > 0:
        price = float(quote["price"])
        change_pct = float(quote.get("change_pct") or 0.0)
    else:
        if clean in STOCK_BASELINE_PRICES:
            price = STOCK_BASELINE_PRICES[clean]
        elif clean + ".NS" in STOCK_BASELINE_PRICES:
            price = STOCK_BASELINE_PRICES[clean + ".NS"]
        else:
            try:
                conn = get_connection()
                row = conn.execute("SELECT close FROM stock_price WHERE ticker=? ORDER BY date DESC LIMIT 1", (clean,)).fetchone()
                conn.close()
                if row and row["close"] is not None:
                    price = float(row["close"])
            except Exception:
                pass

    bracket_id, bracket_label, cfg = classify_price_bracket(price, clean)
    return {
        "ticker": clean,
        "price": round(price, 2) if price else None,
        "change_pct": round(change_pct, 2),
        "bracket_id": bracket_id,
        "bracket_label": bracket_label,
        "bracket_color": cfg["color"],
        "bracket_bg": cfg["bg"],
        "bracket_border": cfg["border"]
    }
