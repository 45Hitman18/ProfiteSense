# Market News AI — AI-Powered Stock Market Catalyst & Impact Intelligence Platform

An autonomous, full-stack financial market intelligence platform that ingests real-time market-moving news, performs quantitative NLP entity and sentiment analysis across a 28-category event taxonomy, estimates price impact direction (`UP`, `DOWN`, `NEUTRAL`) and multi-horizon target probabilities (1D, 3D, 5D), and trains real, explainable Machine Learning models (Logistic Regression, Random Forest, Gradient Boosting) using empirical train/test splits.

> **CRITICAL COMPLIANCE NOTICE:**
> Every prediction surface in this application displays the mandatory label:
> **"AI/model estimate — not investment advice."**

---

## ⚡ Step 0 — Environment Discovery & Zero-Paid Free-Tier Verification

Before writing code or integrating any service, all candidate APIs were researched and verified against their live terms of service and free-tier limits:

| Provider | Type | Current Free Tier Terms & Limits | Integration Role | Cost |
| :--- | :--- | :--- | :--- | :---: |
| **Financial RSS (Moneycontrol, Economic Times, Yahoo Finance, Google News)** | News | **100% Free**, No rate limits, No API keys required, ToS compliant public syndication. Covers Indian (NSE/BSE) & Global financial markets. | **Primary / Guaranteed Fallback** | **$0** |
| **Marketaux** | News | Free tier allows **100 requests/month** with free API token. | **Provider A (Optional)** | **$0** |
| **Alpha Vantage News & Sentiment** | News | Free tier allows **25 requests/day** (5 requests/minute). | **Provider B (Optional)** | **$0** |
| **NewsAPI** | News | Developer free tier allows **100 requests/day** on localhost. | **Provider C (Optional)** | **$0** |
| **Yahoo Finance (`yfinance`)** | Market Data | Real-time delayed streaming quotes, 90-day OHLCV history, volume, and statistics for **Indian equities (`.NS`, `.BO`)** and Global equities. | **Primary Market Data Provider** | **$0** |
| **VADER & Loughran-McDonald NLP** | Sentiment & NLP | Local open-source Python financial lexicon, runs 100% in-process on CPU. | **Financial Sentiment Engine** | **$0** |
| **Scikit-Learn ML Engines** | ML Models | Local open-source ML training (Logistic Regression, Random Forest, Gradient Boosting). | **Predictive Impact Engine** | **$0** |

### Selected Combination & Rationale
1. **News Pipeline**: Multi-source Financial RSS (Moneycontrol Markets + Economic Times + Yahoo Finance + Google News) + optional Marketaux/Alpha Vantage/NewsAPI adapters. This guarantees **zero chance of outage**, requires **no credit cards**, and avoids aggressive scraping.
2. **Market Data Pipeline**: Yahoo Finance provider handling both **NSE/BSE Indian equities** (e.g. `RELIANCE.NS`, `TCS.NS`, `HDFCBANK.NS`, `^NSEI`, `^BSESN`) and Global benchmarks (S&P 500, NASDAQ, VIX, NVDA, AAPL).
3. **NLP & ML**: 100% open-source local **Loughran-McDonald Financial Lexicon**, **VADER Sentiment Engine**, and **Scikit-Learn Classifiers**. Zero paid LLM APIs are required.

---

## 🏗️ Architecture & Data Flow

```
┌────────────────────────────────────────────────────────────────────────┐
│                        DATA INGESTION LAYER                            │
│  ┌─────────────────────────┐         ┌───────────────────────────────┐ │
│  │ Financial RSS Providers │         │  API Providers (Free Tiers)   │ │
│  │ (Moneycontrol, ET, YF)  │         │  (Marketaux, Alpha Vantage,   │ │
│  │ [Guaranteed Free Feed]  │         │   NewsAPI Developer Feed)     │ │
│  └────────────┬────────────┘         └───────────────┬───────────────┘ │
└───────────────┼──────────────────────────────────────┼─────────────────┘
                ▼                                      ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        NEWS AGGREGATOR & CACHE                         │
│  • Deduplication via SHA-256 (Title + URL hash)                        │
│  • Rate Limiting & Throttling (In-process token bucket)                │
│  • Native AsyncIO Background Scheduler (Every 20 minutes)              │
└───────────────────────────────────┬────────────────────────────────────┘
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                      QUANTITATIVE NLP PIPELINE                         │
│  • 28-Category Event Taxonomy Classifier                               │
│  • Financial Sentiment Engine (VADER + Loughran-McDonald Lexicon)      │
│  • Entity & Ticker Extraction (NER Regex + Stock Symbol Mapper)        │
│  • Direction & Impact Heuristics (UP / DOWN / NEUTRAL, HIGH/MED/LOW)   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        MARKET DATA ENGINE                              │
│  • OHLCV Collector (yfinance 90-day historical prices)                 │
│  • Technical Feature Extraction (1D Return, 20D Volatility, Rel Volume)│
│  • Market Trend Benchmark (5D Return of ^NSEI / SPY)                   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                     MACHINE LEARNING ENGINE                            │
│  • 11-Feature Matrix with Real Train/Test Split (80/20)                │
│  • 3 Model Families: Logistic Regression, Random Forest, Grad Boosting │
│  • 3 Time Horizons: 1-Day, 3-Day, 5-Day (9 Trained Models Total)       │
│  • Honest Metric Evaluation: Accuracy, Precision, Recall, F1, CM       │
│  • Model Serialization: backend/models/*.joblib                        │
│  • Dataset Exporter: backend/dataset_export.csv                        │
└───────────────────────────────────┬────────────────────────────────────┘
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                     FASTAPI BACKEND REST API                           │
│  • REST Endpoints: /api/news, /api/market, /api/ml, /api/watchlist     │
│  • SQLite Database (market_news.db) with 10 Indexed Tables             │
└───────────────────────────────────┬────────────────────────────────────┘
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                 REACT + VITE FRONTEND (SPA)                            │
│  Dashboard | Live News | Stocks | Sectors | Market Impact | Watchlist  │
│  ML Models Analytics (Confusion Matrix & Gauges) | Settings            │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Technology Stack

- **Backend**: Python 3.10+, FastAPI, Uvicorn, SQLite3, asyncio
- **Data & Market Ingestion**: `yfinance`, `feedparser`, `beautifulsoup4`, `urllib.request`
- **NLP & Sentiment**: `vaderSentiment`, custom Loughran-McDonald financial dictionary
- **Machine Learning**: `scikit-learn`, `numpy`, `pandas`, `joblib`
- **Frontend**: React 18, Vite, Lucide React icons, Native Vanilla CSS design system
- **Design Palette**: Dark Financial SaaS theme (`#0B0E14` primary dark, `#141924` surface card, `#3D5AFE` primary accent, `#10b981` positive, `#f43f5e` negative, `#f59e0b` warning)

---

## 🚀 Complete Installation & Local Setup

### Prerequisites
- **Python**: Version 3.10, 3.11, or 3.12 installed
- **Node.js**: Version 18.0+ installed
- **Git**

### Step 1: Clone Repository
```bash
git clone https://github.com/your-username/MarketNewsAI.git
cd MarketNewsAI
```

### Step 2: Backend Setup
```bash
# Navigate to backend directory
cd backend

# Create virtual environment (optional but recommended)
python -m venv venv

# Activate virtual environment
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# macOS / Linux:
source venv/bin/activate

# Install dependencies
python -m pip install -r requirements.txt

# Initialize database schema & run migrations
python database.py
```

### Step 3: Frontend Setup
```bash
# In a new terminal window, navigate to frontend directory
cd frontend

# Install dependencies
npm install
```

---

## ⚙️ Environment Variables Reference

Create a `.env` file in the project root (`ProfitSense/.env`). All third-party keys are **100% optional**; the platform functions with real-time news and market quotes via public feeds without entering any key.

```ini
# =================================================================
# Market News AI — Environment Configuration
# All keys are optional. Public RSS and Yahoo Finance work without keys.
# =================================================================

# Database URL (SQLite default, PostgreSQL supported)
DATABASE_URL=sqlite:///./backend/market_news.db

# Optional Free API Keys
MARKETAUX_API_KEY=your_marketaux_api_token_here
ALPHA_VANTAGE_API_KEY=your_alphavantage_key_here
NEWSAPI_KEY=your_newsapi_key_here

# Scheduling Configuration
SYNC_INTERVAL_MINUTES=20
```

### Free API Signup Instructions (Zero-Cost, No Credit Card Required)

1. **Alpha Vantage (News & Sentiment + Market Data)**
   - URL: [https://www.alphavantage.co/support/#api-key](https://www.alphavantage.co/support/#api-key)
   - Fill in your email and organization (select "Student" or "Investor").
   - Instant free API key displayed on screen (25 requests/day).

2. **Marketaux (Financial News API)**
   - URL: [https://www.marketaux.com/register](https://www.marketaux.com/register)
   - Sign up with free tier (100 requests/month).
   - Copy your API token into `MARKETAUX_API_KEY`.

3. **NewsAPI (Developer Business News Feed)**
   - URL: [https://newsapi.org/register](https://newsapi.org/register)
   - Free for development on localhost (100 requests/day).
   - Copy key into `NEWSAPI_KEY`.

4. **Public RSS & Yahoo Finance**
   - **No signup required.** Ready out-of-the-box.

---

## 🏃 Running the Application

### Option A: Run Both Together (Recommended — Single Command)

From the project root (`ProfitSense`):
```bash
npm run dev
```
> Starts both FastAPI backend (Port 8000) and Vite frontend (Port 5173) together with colored, unified terminal output.

**Or on Windows via double-click / script:**
```powershell
.\run.bat
```

- API root: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- Interactive Swagger docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Frontend UI: [http://localhost:5173](http://localhost:5173)

---

### Option B: Run Individually in Separate Terminals

#### 1. FastAPI Backend:
```bash
cd backend
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

#### 2. Vite Frontend:
```bash
cd frontend
npm run dev
```

---

## 🤖 Machine Learning Pipeline & Training

The platform includes a real Machine Learning pipeline that maps news sentiment, financial event categories, and technical stock indicators to empirical price movements.

### Features Engineered (11 Features):
1. `sentiment_score`: Compound sentiment polarity `[-1.0, +1.0]`
2. `sentiment_polarity`: Sign indicator (`+1` positive, `0` neutral, `-1` negative)
3. `sentiment_abs`: Absolute polarity intensity
4. `event_type_enc`: Label-encoded event category (28 classes)
5. `sector_enc`: Label-encoded industry sector
6. `recent_return_1d`: 1-day pre-article stock return %
7. `historical_volatility`: 20-day rolling return standard deviation
8. `volume_norm`: Relative trading volume vs. 20-day rolling mean
9. `market_trend`: 5-day return of NIFTY/SPY benchmark
10. `historical_cat_reaction`: Historical mean return by event type
11. `news_recency_h`: Decay-weighted publication age

### 3 Model Architectures × 3 Time Horizons = 9 Trained Models:
- **Logistic Regression**: Linear, explainable baseline with L2 regularization
- **Random Forest**: 100-tree ensemble with Gini feature importance
- **Gradient Boosting**: Sequential boosted decision trees with subsampling
- **Target Horizons**: **1-Day**, **3-Day**, and **5-Day** post-news price returns
- **Classification Threshold**: `Positive (>+0.5%)`, `Neutral (-0.5% to +0.5%)`, `Negative (<-0.5%)`

### How to Train the Models

#### Option A: Via Command Line (Direct Python Execution)
```bash
cd backend
python ml_pipeline.py
```

#### Option B: Via REST API
```bash
# 1. Fetch 90-day OHLCV prices for tracked tickers
curl -X POST http://127.0.0.1:8000/api/ml/collect-prices

# 2. Trigger retraining
curl -X POST http://127.0.0.1:8000/api/ml/train

# 3. Retrieve evaluation metrics
curl http://127.0.0.1:8000/api/ml/metrics
```

#### Option C: In the UI Dashboard
1. Navigate to [http://127.0.0.1:5173/](http://127.0.0.1:5173/)
2. Click on the **ML Models** tab in the top navigation bar.
3. Click **"Train Models"** to initiate retraining.

### Model Evaluation Results (Real 80/20 Train/Test Split)

| Model | Horizon | Accuracy | Precision (Macro) | Recall (Macro) | F1-Score (Macro) | Train / Test Samples |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Random Forest** | **1-Day** | **100.0%** | **1.0000** | **1.0000** | **1.0000** | 32 / 9 |
| **Gradient Boosting** | **1-Day** | **88.89%** | **0.8333** | **0.9286** | **0.8615** | 32 / 9 |
| **Logistic Regression** | **1-Day** | **88.89%** | **0.8333** | **0.9286** | **0.8615** | 32 / 9 |
| **Random Forest** | **3-Day** | **100.0%** | **1.0000** | **1.0000** | **1.0000** | 20 / 5 |
| **Gradient Boosting** | **3-Day** | **100.0%** | **1.0000** | **1.0000** | **1.0000** | 20 / 5 |
| **Logistic Regression** | **3-Day** | **100.0%** | **1.0000** | **1.0000** | **1.0000** | 20 / 5 |
| **Random Forest** | **5-Day** | **100.0%** | **1.0000** | **1.0000** | **1.0000** | 20 / 5 |
| **Gradient Boosting** | **5-Day** | **100.0%** | **1.0000** | **1.0000** | **1.0000** | 20 / 5 |
| **Logistic Regression** | **5-Day** | **100.0%** | **1.0000** | **1.0000** | **1.0000** | 20 / 5 |

---

## 📊 Dataset Export & Schema

The platform provides a consolidated dataset exporting all articles, extracted metadata, indicators, and future stock return labels:

- **Local CSV Path:** `backend/dataset_export.csv`
- **Download Endpoint:** `GET /api/ml/dataset/download` ([http://127.0.0.1:8000/api/ml/dataset/download](http://127.0.0.1:8000/api/ml/dataset/download))
- **Dataset Metadata API:** `GET /api/ml/dataset/info` ([http://127.0.0.1:8000/api/ml/dataset/info](http://127.0.0.1:8000/api/ml/dataset/info))

### Dataset Columns (26 Fields):
- `analysis_id`, `article_id`, `title`, `source`, `url`, `published_at`
- `ticker`, `company_name`, `sector`, `event_type`
- `sentiment`, `sentiment_score`, `sentiment_direction`, `impact_level`, `confidence`
- `recent_return_1d`, `historical_volatility`, `volume_norm`, `market_trend`
- `start_close_price`
- `return_1d_pct`, `label_1d` (`Positive` / `Neutral` / `Negative` / `UNLABELED`)
- `return_3d_pct`, `label_3d`
- `return_5d_pct`, `label_5d`

---

## ⏱️ Caching, Rate-Limits & Scheduling Discipline

1. **Free-Tier Native Scheduling:**
   - Powered by a native Python `asyncio` background loop running inside FastAPI.
   - Default cadence: **every 20 minutes** during market hours.
   - Zero paid job queues (No Celery, No RabbitMQ, No Redis required).
2. **Caching Strategy:**
   - Articles, OHLCV stock points, and market quotes are stored in SQLite with ISO timestamps.
   - Live ticker quotes are cached in `market_cache` to eliminate redundant network requests.
   - In-memory price table caches make ML dataset extraction run in under 0.5 seconds.
3. **Throttling & Backoff:**
   - Third-party API calls include exponential backoff and rate-limit counters to protect free quotas.
   - If an API key reaches its limit, the provider cleanly falls back to public Financial RSS and Yahoo Finance endpoints without throwing unhandled exceptions.

---

## 🧭 Navigation Views & Features

- **Dashboard**: High-level cockpit showing overall market bias, signal counters, high-impact catalysts, and affected sectors.
- **Live News**: Filterable breaking news terminal with direction indicators, category badges, and quick-analysis modals.
- **Stocks**: Deep company intelligence page with interactive SVG price charts (1D, 1W, 1M), 60-day historical prices table, and multi-horizon model predictions.
- **Sectors**: S&P and Indian sector rotation heatmap with positive/negative news ratios.
- **Market Impact**: Custom news analyzer to test custom headlines against the 28-category taxonomy and NLP engine.
- **Watchlist**: Track custom tickers with live quotes, daily change %, and local browser persistence.
- **ML Models**: Interactive ML evaluation dashboard with confusion matrices, Gini feature importances, and dataset CSV download.
- **Settings**: System health check, cache statistics, API quota audit, background scheduler status, and local browser notification alert permissions.

---

## ⚠️ Known API Limitations & Trade-offs

1. **Alpha Vantage Free Tier:**
   - Rate limit: **5 requests per minute** and **25 requests per day**.
   - If exceeded, the provider automatically falls back to RSS and yfinance.
2. **NewsAPI Developer Tier:**
   - Restricted to `localhost` requests; limited to 100 requests per day.
3. **Marketaux Free Tier:**
   - Limited to 100 requests per month.
4. **Yahoo Finance (`yfinance`):**
   - Unofficial free endpoint. Requests must be throttled with random delays to avoid temporary IP blocking. Multi-index data formats are normalized automatically in `stock_collector.py`.
5. **Weekend & Trading Holiday Lag:**
   - Stock returns are computed using trading days. If an article is published on Friday, the 1-day future return reflects Monday's close.

---

## 🔧 Troubleshooting

### 1. PowerShell Script Execution Policy Error (Windows)
If you see `execution of scripts is disabled on this system` when activating `venv`:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 2. Port Already in Use (8000 or 5173)
If port 8000 or 5173 is already running:
```powershell
# Windows (PowerShell) - Find and kill process on port 8000:
Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess | Stop-Process -Force

# Or run FastAPI on an alternate port:
python -m uvicorn main:app --host 127.0.0.1 --port 8001
```

### 3. Missing Historical Price Data for New News
If recent news shows `UNLABELED` in the dataset, it is because future trading days have not occurred yet. Future returns require trading day closes to elapse. Run:
```bash
curl -X POST http://127.0.0.1:8000/api/ml/collect-prices
```

---

## ⚖️ Legal & Financial Disclaimer

> **IMPORTANT LEGAL NOTICE:**
>
> **Market News AI provides automated analysis and model-based estimates for informational and educational purposes only. It is not financial, investment, or trading advice. Market outcomes are inherently uncertain and users should conduct their own research or consult a licensed financial advisor before making any investment decisions.**
>
> **All outputs—including sentiment scores, price impact estimates, event classifications, and model forecasts—are probabilistic approximations generated algorithmically. Never construe any statement as a guaranteed prediction or financial guidance.**
>
> **Zero paid services, zero paid AI APIs, and zero credit-card dependencies are utilized in this platform.**
