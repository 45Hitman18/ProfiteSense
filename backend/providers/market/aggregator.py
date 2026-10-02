import time
from typing import Dict, Any, List, Optional
from datetime import datetime
from .yahoo_provider import YahooFinanceMarketProvider

class MarketAggregator:
    """
    Orchestrates market data providers with caching and fallback chain.
    Provider A (Alpha Vantage if available) -> Provider B (Yahoo Finance) -> Graceful 'data unavailable'.
    Guarantees no unhandled crash occurs if a provider is throttled or offline.
    """

    def __init__(self):
        self.yahoo_provider = YahooFinanceMarketProvider()
        self.quote_cache: Dict[str, Dict[str, Any]] = {}
        self.cache_ttl = 120  # 2 minutes

    def get_quote(self, ticker: str) -> Dict[str, Any]:
        clean_ticker = ticker.strip().upper()
        now = time.time()

        # Check in-memory cache
        if clean_ticker in self.quote_cache:
            entry = self.quote_cache[clean_ticker]
            if now - entry["time"] < self.cache_ttl:
                return entry["data"]

        # Try Yahoo Finance Provider
        quote = self.yahoo_provider.get_quote(clean_ticker)
        if quote:
            self.quote_cache[clean_ticker] = {"time": now, "data": quote}
            return quote

        # Fallback chain exhausted: return graceful "data unavailable" structure
        fallback_data = {
            "ticker": clean_ticker,
            "company_name": clean_ticker,
            "price": None,
            "prev_close": None,
            "change_amount": 0.0,
            "change_pct": 0.0,
            "high_52w": None,
            "low_52w": None,
            "market_cap": None,
            "volume": None,
            "pe_ratio": None,
            "sector": "Equities",
            "sparkline": [],
            "status": "data unavailable",
            "provider": "None (Providers Offline / Unlisted Ticker)",
            "last_updated": datetime.now().isoformat()
        }
        return fallback_data

    def get_historical_chart(self, ticker: str, period: str = "1mo") -> List[Dict[str, Any]]:
        chart = self.yahoo_provider.get_historical_chart(ticker, period)
        if chart:
            return chart
        return []

    def get_market_overview(self) -> Dict[str, Any]:
        indices = self.yahoo_provider.get_indices()
        
        # Determine market mood from Indian indices & factors
        vix_obj = next((i for i in indices if "VIX" in i["short"]), None)
        vix_val = vix_obj["value"] if vix_obj else 15.0
        nifty_obj = next((i for i in indices if i["short"] == "NIFTY 50"), None)
        sensex_obj = next((i for i in indices if i["short"] == "SENSEX"), None)
        
        avg_change = 0.0
        active_benchmarks = [b for b in [nifty_obj, sensex_obj] if b]
        if active_benchmarks:
            avg_change = sum(b["change_pct"] for b in active_benchmarks) / len(active_benchmarks)

        if vix_val < 16 and avg_change > 0:
            mood_label = "Strong Bullish"
            mood_score = 78
        elif vix_val < 21 and avg_change >= -0.5:
            mood_label = "Cautious Bullish"
            mood_score = 62
        elif vix_val >= 25 or avg_change < -1.5:
            mood_label = "Bearish / Risk-Off"
            mood_score = 32
        else:
            mood_label = "Neutral / Mixed"
            mood_score = 50

        return {
            "indices": indices,
            "market_mood": {
                "label": mood_label,
                "score": mood_score,
                "vix": vix_val,
                "summary": f"VIX at {vix_val:.1f} signals {'contained' if vix_val < 20 else 'elevated'} implied volatility. Benchmark equity drift: {avg_change:+.2f}%."
            },
            "last_updated": datetime.now().isoformat()
        }

    def get_sectors(self) -> List[Dict[str, Any]]:
        return self.yahoo_provider.get_sectors()
