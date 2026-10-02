from typing import List, Dict, Any
from .rss_provider import RSSNewsProvider
from .marketaux_provider import MarketauxNewsProvider
from .alpha_vantage_news import AlphaVantageNewsProvider, NewsAPINewsProvider

class NewsAggregator:
    """
    Orchestrates the fallback chain for news ingestion:
    Provider A (Marketaux) -> Provider B (Alpha Vantage) -> Provider C (NewsAPI) -> Legitimate RSS / Public fallback.
    Guarantees the system never crashes due to a single provider failure.
    """

    def __init__(self):
        self.providers = [
            RSSNewsProvider(),        # 100% Indian Financial Feeds (Moneycontrol, ET, LiveMint, India Factors)
            MarketauxNewsProvider(),  # Indian Equities (countries=in)
            NewsAPINewsProvider(),    # Indian Business (country=in)
        ]

    def get_active_providers(self) -> List[str]:
        return [p.name for p in self.providers if p.is_available]

    def fetch_all(self, target_count: int = 50) -> List[Dict[str, Any]]:
        collected = []
        seen_ids = set()

        # Iterate through fallback chain
        for provider in self.providers:
            if not provider.is_available:
                continue

            try:
                print(f"[NewsAggregator] Polling provider: {provider.name}")
                items = provider.fetch_latest_news(limit=target_count)
                for item in items:
                    if item["id"] not in seen_ids:
                        seen_ids.add(item["id"])
                        collected.append(item)
                        
                # If we have collected enough articles, we can continue or return
                if len(collected) >= target_count:
                    break
            except Exception as e:
                print(f"[NewsAggregator] Provider '{provider.name}' failed with error: {e}. Falling back to next in chain.")
                continue

        # If primary providers were exhausted or returned few articles, ensure RSS fills the buffer
        if len(collected) < 15:
            rss_prov = RSSNewsProvider()
            try:
                for item in rss_prov.fetch_latest_news(limit=30):
                    if item["id"] not in seen_ids:
                        seen_ids.add(item["id"])
                        collected.append(item)
            except Exception as e:
                print(f"[NewsAggregator] RSS fallback error: {e}")

        return collected
