import urllib.request
import json
import hashlib
from datetime import datetime
from typing import List, Dict, Any
from .base import BaseNewsProvider
from config import ALPHA_VANTAGE_API_KEY, NEWSAPI_KEY

class AlphaVantageNewsProvider(BaseNewsProvider):
    """
    Alpha Vantage News & Sentiment API provider.
    Free tier: 25 requests/day.
    Uses ALPHA_VANTAGE_API_KEY from .env if available.
    """

    @property
    def name(self) -> str:
        return "Alpha Vantage News & Sentiment"

    @property
    def is_available(self) -> bool:
        return bool(ALPHA_VANTAGE_API_KEY and len(ALPHA_VANTAGE_API_KEY.strip()) > 4)

    def fetch_latest_news(self, limit: int = 25) -> List[Dict[str, Any]]:
        if not self.is_available:
            return []
            
        try:
            url = f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&limit={limit}&apikey={ALPHA_VANTAGE_API_KEY}"
            req = urllib.request.Request(url, headers={"User-Agent": "MarketNewsAI/1.0"})
            with urllib.request.urlopen(req, timeout=8) as res:
                payload = json.loads(res.read().decode())
                feed = payload.get("feed", [])
                
                normalized = []
                for item in feed:
                    title = item.get("title", "").strip()
                    url_link = item.get("url", "")
                    if not title:
                        continue
                    
                    art_id = hashlib.sha256(f"{title}_{url_link}".encode()).hexdigest()[:16]
                    normalized.append({
                        "id": art_id,
                        "title": title,
                        "summary": item.get("summary", ""),
                        "source": item.get("source", "Alpha Vantage"),
                        "url": url_link,
                        "published_at": item.get("time_published", datetime.now().isoformat()),
                        "category": item.get("category_within_source", "Market News"),
                        "raw_content": "",
                        "created_at": datetime.now().isoformat()
                    })
                return normalized
        except Exception as e:
            print(f"Alpha Vantage news provider fallback triggered: {e}")
            return []

class NewsAPINewsProvider(BaseNewsProvider):
    """
    NewsAPI Developer Free Tier (100 requests/day).
    Uses NEWSAPI_KEY from .env if available.
    """

    @property
    def name(self) -> str:
        return "NewsAPI Developer Feed"

    @property
    def is_available(self) -> bool:
        return bool(NEWSAPI_KEY and len(NEWSAPI_KEY.strip()) > 5)

    def fetch_latest_news(self, limit: int = 25) -> List[Dict[str, Any]]:
        if not self.is_available:
            return []
            
        try:
            url = f"https://newsapi.org/v2/top-headlines?country=in&category=business&pageSize={limit}&apiKey={NEWSAPI_KEY}"
            req = urllib.request.Request(url, headers={"User-Agent": "MarketNewsAI/1.0"})
            with urllib.request.urlopen(req, timeout=8) as res:
                payload = json.loads(res.read().decode())
                articles = payload.get("articles", [])
                
                normalized = []
                for item in articles:
                    title = item.get("title", "").strip()
                    url_link = item.get("url", "")
                    if not title or title == "[Removed]":
                        continue
                    
                    art_id = hashlib.sha256(f"{title}_{url_link}".encode()).hexdigest()[:16]
                    normalized.append({
                        "id": art_id,
                        "title": title,
                        "summary": item.get("description", "") or "",
                        "source": item.get("source", {}).get("name", "NewsAPI"),
                        "url": url_link,
                        "published_at": item.get("publishedAt", datetime.now().isoformat()),
                        "category": "Business & Markets",
                        "raw_content": item.get("content", "") or "",
                        "created_at": datetime.now().isoformat()
                    })
                return normalized
        except Exception as e:
            print(f"NewsAPI provider fallback triggered: {e}")
            return []
