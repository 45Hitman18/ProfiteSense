import feedparser
import hashlib
import re
from datetime import datetime
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from .base import BaseNewsProvider

class RSSNewsProvider(BaseNewsProvider):
    """
    Legitimate public financial RSS provider with 100% free uptime.
    Supports Indian markets (NSE/BSE, Moneycontrol, Economic Times) and Global markets.
    """
    
    FEEDS = [
        # Top Indian Business & Equities
        {
            "name": "Moneycontrol Top News",
            "url": "https://www.moneycontrol.com/rss/MCtopnews.xml",
            "category": "Indian Equities"
        },
        {
            "name": "Moneycontrol Business",
            "url": "https://www.moneycontrol.com/rss/business.xml",
            "category": "Indian Corporate & Stocks"
        },
        {
            "name": "Moneycontrol Market Reports",
            "url": "https://www.moneycontrol.com/rss/marketreports.xml",
            "category": "NSE / BSE Analysis"
        },
        {
            "name": "Economic Times Markets",
            "url": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
            "category": "NSE / BSE News"
        },
        {
            "name": "Economic Times Stocks",
            "url": "https://economictimes.indiatimes.com/markets/stocks/rssfeeds/2146842.cms",
            "category": "Indian Equities"
        },
        {
            "name": "LiveMint Markets",
            "url": "https://www.livemint.com/rss/markets",
            "category": "Indian Financial Markets"
        },
        # Indian Shares & Corporate Catalysts
        {
            "name": "Google News Indian Equities",
            "url": "https://news.google.com/rss/search?q=(NSE+OR+BSE+OR+NIFTY+OR+SENSEX+OR+Tata+OR+Reliance+OR+HDFC+OR+Infosys+OR+Adani)+India+stocks+when:2d&hl=en-IN&gl=IN&ceid=IN:en",
            "category": "Indian Corporate Catalysts"
        },
        # Macro Factors Affecting Indian Markets (RBI, SEBI, FII/DII, Rupee, Crude Oil, Repo Rate, Inflation)
        {
            "name": "India Market Factors & Macro",
            "url": "https://news.google.com/rss/search?q=(RBI+OR+SEBI+OR+FII+OR+DII+OR+Rupee+OR+Crude+oil+OR+repo+rate+OR+inflation)+India+market+when:2d&hl=en-IN&gl=IN&ceid=IN:en",
            "category": "Indian Market Macro Factors"
        }
    ]

    @property
    def name(self) -> str:
        return "Financial RSS (Moneycontrol / Economic Times / LiveMint / India Market Factors)"

    @property
    def is_available(self) -> bool:
        # RSS requires no API keys and is always available
        return True

    def _clean_html(self, raw_html: str) -> str:
        if not raw_html:
            return ""
        try:
            soup = BeautifulSoup(raw_html, "html.parser")
            return re.sub(r'\s+', ' ', soup.get_text(separator=" ")).strip()
        except Exception:
            return re.sub(r'<[^>]+>', ' ', raw_html).strip()

    def _generate_id(self, title: str, url: str) -> str:
        raw = f"{title}_{url}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()[:16]

    def _parse_date(self, entry) -> str:
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            try:
                return datetime(*entry.published_parsed[:6]).isoformat()
            except Exception:
                pass
        if hasattr(entry, "published"):
            return str(entry.published)
        return datetime.now().isoformat()

    def fetch_latest_news(self, limit: int = 30) -> List[Dict[str, Any]]:
        articles = []
        for feed_info in self.FEEDS:
            try:
                parsed = feedparser.parse(feed_info["url"], agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) MarketNewsAI/2.0")
                for entry in parsed.entries[:15]:
                    title = self._clean_html(getattr(entry, "title", "")).strip()
                    if not title or len(title) < 10:
                        continue
                    
                    summary = self._clean_html(getattr(entry, "summary", "")).strip()
                    link = getattr(entry, "link", "")
                    pub_date = self._parse_date(entry)
                    
                    raw_content = ""
                    if hasattr(entry, "content"):
                        raw_content = self._clean_html(entry.content[0].value if entry.content else "")
                        
                    articles.append({
                        "id": self._generate_id(title, link),
                        "title": title,
                        "summary": summary,
                        "source": feed_info["name"],
                        "url": link,
                        "published_at": pub_date,
                        "category": feed_info["category"],
                        "raw_content": raw_content,
                        "created_at": datetime.now().isoformat()
                    })
            except Exception as e:
                print(f"RSS Provider warning for {feed_info['name']}: {e}")
                
        return articles[:limit]
