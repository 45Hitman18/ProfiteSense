import urllib.request
import json
import hashlib
from datetime import datetime
from typing import List, Dict, Any
from .base import BaseNewsProvider
from config import MARKETAUX_API_KEY

class MarketauxNewsProvider(BaseNewsProvider):
    """
    Marketaux Financial News API provider.
    Free tier: 100 requests/month or limited calls/day.
    Uses MARKETAUX_API_KEY from .env if available.
    """
    
    BASE_URL = "https://api.marketaux.com/v1/news/all"

    @property
    def name(self) -> str:
        return "Marketaux Financial News API"

    @property
    def is_available(self) -> bool:
        return bool(MARKETAUX_API_KEY and len(MARKETAUX_API_KEY.strip()) > 5)

    def fetch_latest_news(self, limit: int = 25) -> List[Dict[str, Any]]:
        if not self.is_available:
            return []
            
        try:
            url = f"{self.BASE_URL}?api_token={MARKETAUX_API_KEY}&language=en&countries=in&limit={min(limit, 25)}"
            req = urllib.request.Request(url, headers={"User-Agent": "MarketNewsAI/1.0"})
            with urllib.request.urlopen(req, timeout=8) as res:
                payload = json.loads(res.read().decode())
                data = payload.get("data", [])
                
                normalized = []
                for item in data:
                    title = item.get("title", "").strip()
                    url_link = item.get("url", "")
                    if not title:
                        continue
                    
                    art_id = hashlib.sha256(f"{title}_{url_link}".encode()).hexdigest()[:16]
                    normalized.append({
                        "id": art_id,
                        "title": title,
                        "summary": item.get("description", ""),
                        "source": item.get("source", "Marketaux"),
                        "url": url_link,
                        "published_at": item.get("published_at", datetime.now().isoformat()),
                        "category": "Equities",
                        "raw_content": item.get("snippet", ""),
                        "created_at": datetime.now().isoformat()
                    })
                return normalized
        except Exception as e:
            print(f"Marketaux provider fallback triggered: {e}")
            return []
