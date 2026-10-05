import yfinance as yf
from datetime import datetime
from typing import Dict, Any, List, Optional
from .base import BaseMarketProvider

INDICES_CONFIG = [
    # Indian Benchmarks
    {"symbol": "^NSEI", "name": "NIFTY 50 Index", "short": "NIFTY 50", "region": "India"},
    {"symbol": "^BSESN", "name": "BSE SENSEX Index", "short": "SENSEX", "region": "India"},
    {"symbol": "^INDIAVIX", "name": "India Volatility Index", "short": "INDIA VIX", "region": "India"},
    # Macro Factors Affecting Indian Share Market
    {"symbol": "INR=X", "name": "USD / INR Forex Rate", "short": "USD/INR", "region": "Macro Factor"},
    {"symbol": "BZ=F", "name": "Brent Crude Oil", "short": "BRENT CRUDE", "region": "Commodity Factor"}
]

SECTORS_CONFIG = [
    {"symbol": "HDFCBANK.NS", "sector": "Banking & Finance", "icon": "Landmark"},
    {"symbol": "TCS.NS", "sector": "Information Technology", "icon": "Cpu"},
    {"symbol": "MARUTI.NS", "sector": "Automobile & Auto Ancillary", "icon": "Car"},
    {"symbol": "RELIANCE.NS", "sector": "Energy & Petrochemicals", "icon": "Flame"},
    {"symbol": "HINDUNILVR.NS", "sector": "Consumer Goods (FMCG)", "icon": "ShoppingBag"},
    {"symbol": "SUNPHARMA.NS", "sector": "Pharmaceuticals & Healthcare", "icon": "Pill"},
    {"symbol": "TATASTEEL.NS", "sector": "Metals & Mining", "icon": "Pickaxe"},
    {"symbol": "LT.NS", "sector": "Engineering & Infrastructure", "icon": "HardHat"},
    {"symbol": "BHARTIARTL.NS", "sector": "Telecommunications", "icon": "Radio"},
    {"symbol": "DLF.NS", "sector": "Real Estate & Realty", "icon": "Building2"},
    {"symbol": "TATAPOWER.NS", "sector": "Power & Renewable Energy", "icon": "Zap"},
    {"symbol": "BAJFINANCE.NS", "sector": "NBFC & Financial Services", "icon": "CreditCard"}
]

class YahooFinanceMarketProvider(BaseMarketProvider):
    """
    High-performance market provider using Yahoo Finance public streams.
    Seamlessly handles Indian stocks (.NS, .BO), US stocks, and global indices.
    """

    @property
    def name(self) -> str:
        return "Yahoo Finance Public Stream (NSE/BSE & Global)"

    @property
    def is_available(self) -> bool:
        return True

    def _normalize_ticker(self, ticker: str) -> str:
        t = ticker.strip().upper()
        # If user typed Reliance or TCS without extension, check
        india_top = {
            "RELIANCE": "RELIANCE.NS",
            "TCS": "TCS.NS",
            "HDFCBANK": "HDFCBANK.NS",
            "INFY": "INFY.NS",
            "TATAMOTORS": "TATAMOTORS.NS",
            "SBIN": "SBIN.NS",
            "ICICIBANK": "ICICIBANK.NS",
            "BHARTIARTL": "BHARTIARTL.NS"
        }
        return india_top.get(t, t)

    def get_quote(self, ticker: str) -> Optional[Dict[str, Any]]:
        clean_ticker = self._normalize_ticker(ticker)
        try:
            yf_ticker = yf.Ticker(clean_ticker)
            fast_info = getattr(yf_ticker, "fast_info", None)
            hist = yf_ticker.history(period="5d", interval="1d")
            
            if hist.empty:
                return None
                
            current_price = float(hist["Close"].iloc[-1])
            prev_close = float(hist["Close"].iloc[-2]) if len(hist) > 1 else current_price
            change_pct = round(((current_price - prev_close) / prev_close) * 100, 2)
            change_amount = round(current_price - prev_close, 2)
            
            high_52w = float(getattr(fast_info, "year_high", current_price * 1.15)) if fast_info else current_price * 1.15
            low_52w = float(getattr(fast_info, "year_low", current_price * 0.85)) if fast_info else current_price * 0.85
            market_cap = float(getattr(fast_info, "market_cap", 0)) if fast_info else 0

            info = {}
            try:
                info = yf_ticker.info or {}
            except Exception:
                pass

            return {
                "ticker": clean_ticker,
                "company_name": info.get("shortName") or info.get("longName") or clean_ticker,
                "price": round(current_price, 2),
                "prev_close": round(prev_close, 2),
                "change_amount": change_amount,
                "change_pct": change_pct,
                "high_52w": round(high_52w, 2),
                "low_52w": round(low_52w, 2),
                "market_cap": market_cap,
                "volume": int(hist["Volume"].iloc[-1]) if "Volume" in hist else 0,
                "pe_ratio": info.get("trailingPE") or info.get("forwardPE") or None,
                "sector": info.get("sector") or "Equities",
                "sparkline": [round(float(p), 2) for p in hist["Close"].tolist()],
                "status": "available",
                "provider": self.name,
                "last_updated": datetime.now().isoformat()
            }
        except Exception as e:
            print(f"Yahoo quote error for {clean_ticker}: {e}")
            return None

    def get_historical_chart(self, ticker: str, period: str = "1mo") -> List[Dict[str, Any]]:
        clean_ticker = self._normalize_ticker(ticker)
        try:
            yf_ticker = yf.Ticker(clean_ticker)
            hist = yf_ticker.history(period=period, interval="1d")
            
            series = []
            for index, row in hist.iterrows():
                date_str = index.strftime("%Y-%m-%d")
                series.append({
                    "date": date_str,
                    "open": round(float(row["Open"]), 2),
                    "high": round(float(row["High"]), 2),
                    "low": round(float(row["Low"]), 2),
                    "close": round(float(row["Close"]), 2),
                    "volume": int(row["Volume"])
                })
            return series
        except Exception as e:
            print(f"Yahoo chart error for {clean_ticker}: {e}")
            return []

    def get_indices(self) -> List[Dict[str, Any]]:
        results = []
        for item in INDICES_CONFIG:
            symbol = item["symbol"]
            current = None
            prev = None
            change_pct = 0.0
            change_val = 0.0

            try:
                yf_ticker = yf.Ticker(symbol)
                hist = yf_ticker.history(period="5d")
                if not hist.empty and len(hist) >= 1:
                    current = float(hist["Close"].iloc[-1])
                    if len(hist) >= 2:
                        prev = float(hist["Close"].iloc[-2])
                        change_pct = round(((current - prev) / prev) * 100, 2)
                        change_val = round(current - prev, 2)
            except Exception:
                pass

            if current is None or current <= 0:
                try:
                    from database import get_connection
                    conn = get_connection()
                    rows = conn.execute(
                        "SELECT close FROM stock_price WHERE ticker=? AND close > 0 ORDER BY date DESC LIMIT 2",
                        (symbol,)
                    ).fetchall()
                    conn.close()
                    if rows and len(rows) >= 1:
                        current = float(rows[0][0])
                        if len(rows) >= 2:
                            prev = float(rows[1][0])
                            change_pct = round(((current - prev) / prev) * 100, 2)
                            change_val = round(current - prev, 2)
                except Exception:
                    pass

            if current is not None and current > 0:
                results.append({
                    "symbol": symbol,
                    "name": item["name"],
                    "short": item["short"],
                    "region": item["region"],
                    "value": round(current, 2),
                    "change": change_val,
                    "change_pct": change_pct
                })
        return results

    def get_sectors(self) -> List[Dict[str, Any]]:
        results = []
        for item in SECTORS_CONFIG:
            symbol = item["symbol"]
            sector_name = item["sector"]
            icon = item.get("icon", "Layers")
            current = None
            prev = None
            change_pct = 0.0

            # 1. Try yfinance with 5d lookback for reliable prior close
            try:
                yf_ticker = yf.Ticker(symbol)
                hist = yf_ticker.history(period="5d")
                if not hist.empty and len(hist) >= 1:
                    current = float(hist["Close"].iloc[-1])
                    if len(hist) >= 2:
                        prev = float(hist["Close"].iloc[-2])
                        change_pct = round(((current - prev) / prev) * 100, 2)
            except Exception:
                pass

            # 2. Database price fallback
            if current is None or current <= 0 or change_pct == 0.0:
                try:
                    from database import get_connection
                    conn = get_connection()
                    rows = conn.execute(
                        "SELECT close FROM stock_price WHERE ticker=? AND close > 0 ORDER BY date DESC LIMIT 2",
                        (symbol,)
                    ).fetchall()
                    conn.close()
                    if rows and len(rows) >= 1:
                        if current is None or current <= 0:
                            current = float(rows[0][0])
                        if len(rows) >= 2 and change_pct == 0.0:
                            prev = float(rows[1][0])
                            change_pct = round(((current - prev) / prev) * 100, 2)
                except Exception:
                    pass

            if current is not None and current > 0:
                results.append({
                    "symbol": symbol,
                    "sector": sector_name,
                    "icon": icon,
                    "price": round(current, 2),
                    "change_pct": change_pct
                })
        return results
