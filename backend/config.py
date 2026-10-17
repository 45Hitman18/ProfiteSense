import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root or backend
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./backend/market_news.db")
REDIS_URL = os.getenv("REDIS_URL", "")
MARKETAUX_API_KEY = os.getenv("MARKETAUX_API_KEY", "")
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY", "")
ENABLE_EXTERNAL_LLM = os.getenv("ENABLE_EXTERNAL_LLM", "false").lower() == "true"
PORT = int(os.getenv("PORT", 8000))
HOST = os.getenv("HOST", "127.0.0.1")
DEBUG = os.getenv("DEBUG", "true").lower() == "true"

# --------------------------------------------------------
# TELEGRAM ALERTS CONFIGURATION
# --------------------------------------------------------
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_ENABLED = os.getenv("TELEGRAM_ENABLED", "false").lower() == "true"
TELEGRAM_POLL_INTERVAL = float(os.getenv("TELEGRAM_POLL_INTERVAL", "2.0"))
TELEGRAM_ALLOWED_CHAT_IDS = [
    x.strip() for x in os.getenv("TELEGRAM_ALLOWED_CHAT_IDS", "").split(",") if x.strip()
]
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:5173")
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")
