from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

class BaseMarketProvider(ABC):
    """Abstract base class for all market data providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def is_available(self) -> bool:
        pass

    @abstractmethod
    def get_quote(self, ticker: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_historical_chart(self, ticker: str, period: str = "1mo") -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_indices(self) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_sectors(self) -> List[Dict[str, Any]]:
        pass
