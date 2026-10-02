from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class BaseNewsProvider(ABC):
    """Abstract base class for all financial news providers."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the news provider."""
        pass

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Checks if provider has required credentials and is within rate limits."""
        pass

    @abstractmethod
    def fetch_latest_news(self, limit: int = 30) -> List[Dict[str, Any]]:
        """
        Fetch latest market news.
        Returns normalized list of dicts with:
        id, title, summary, source, url, published_at, category, raw_content
        """
        pass
