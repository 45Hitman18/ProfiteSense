<div align="center">

<img src="docs/assets/banner.svg" alt="ProfitSense — Autonomous Financial Intelligence & Market Catalyst Platform" width="100%"/>

<br/>

[![Python](https://img.shields.io/badge/Python-3.10%20|%203.11%20|%203.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18.2+-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://react.dev/)
[![Vite](https://img.shields.io/badge/Vite-5.0+-646CFF?style=for-the-badge&logo=vite&logoColor=white)](https://vitejs.dev/)
[![Lightweight Charts](https://img.shields.io/badge/Lightweight_Charts-v5-131722?style=for-the-badge&logo=tradingview&logoColor=white)](https://www.tradingview.com/lightweight-charts/)
[![scikit-learn](https://img.shields.io/badge/scikit--learn-1.4+-F7931E?style=for-the-badge&logo=scikit-learn&logoColor=white)](https://scikit-learn.org/)
[![Telegram](https://img.shields.io/badge/Telegram-Bot_API-26A5E4?style=for-the-badge&logo=telegram&logoColor=white)](https://core.telegram.org/bots/api)
[![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)](https://www.sqlite.org/)

[![Backend Tests](https://img.shields.io/badge/backend_tests-105%2F105_passing-10b981?style=flat-square&logo=pytest&logoColor=white)](backend/tests/)
[![Frontend Tests](https://img.shields.io/badge/frontend_tests-7%2F7_passing-10b981?style=flat-square&logo=vitest&logoColor=white)](frontend/src/test/)
[![Cost](https://img.shields.io/badge/running_cost-$0-0ea5e9?style=flat-square&logo=cashapp&logoColor=white)](#-zero-cost-architecture)
[![License](https://img.shields.io/badge/license-MIT-8b5cf6?style=flat-square)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-f59e0b?style=flat-square)](#-contributing)

<h3>Turn market news into structured, explainable trading signals — for free.</h3>

<p>
ProfitSense ingests live financial news, classifies catalysts with a 28-category NLP engine,<br/>
forecasts 1D / 3D / 5D direction with scikit-learn, and delivers it to a React terminal and your phone via Telegram.
</p>

[**Features**](#-features) ·
[**Preview**](#-preview) ·
[**Architecture**](#-architecture) ·
[**Quickstart**](#-quickstart) ·
[**Charts**](#-interactive-charts) ·
[**Price Brackets**](#-price-brackets) ·
[**Telegram**](#-telegram-bot) ·
[**ML Engine**](#-machine-learning-engine) ·
[**Disclaimer**](#%EF%B8%8F-disclaimer)

</div>

<br/>

---

## 📖 Table of Contents

<details>
<summary><b>Click to expand</b></summary>

1. [At a Glance](#-at-a-glance)
2. [Preview](#-preview)
3. [Features](#-features)
4. [Architecture](#-architecture)
5. [Zero-Cost Architecture](#-zero-cost-architecture)
6. [Quickstart](#-quickstart)
7. [Interactive Charts](#-interactive-charts)
8. [Price Brackets](#-price-brackets)
9. [Telegram Bot](#-telegram-bot)
10. [Machine Learning Engine](#-machine-learning-engine)
11. [Testing](#-testing)
12. [Project Structure](#-project-structure)
13. [Contributing](#-contributing)
14. [License](#-license)
15. [Disclaimer](#%EF%B8%8F-disclaimer)

</details>

---

## 🎯 At a Glance

<table align="center">
  <tr>
    <td align="center" width="16%"><h2>28</h2><sub>event categories</sub></td>
    <td align="center" width="16%"><h2>9</h2><sub>ML models</sub></td>
    <td align="center" width="16%"><h2>11</h2><sub>model features</sub></td>
    <td align="center" width="16%"><h2>9,900+</h2><sub>historical dispatches</sub></td>
    <td align="center" width="16%"><h2>112</h2><sub>automated tests</sub></td>
    <td align="center" width="16%"><h2>$0</h2><sub>to run</sub></td>
  </tr>
</table>

---

## 🖼️ Preview

<div align="center">

### Web Terminal
<img src="docs/assets/preview-dashboard.svg" alt="ProfitSense web terminal with candlestick chart and trading signals" width="92%"/>

<br/><br/>

### Telegram Cockpit
<img src="docs/assets/preview-telegram.svg" alt="ProfitSense Telegram bot conversation" width="340"/>

<sub>Previews use illustrative sample data. Drop real screenshots into <code>docs/assets/</code> (e.g. <code>screenshot-dashboard.png</code>) and swap the paths above.</sub>

</div>

---

## ✨ Features

<table>
  <tr>
    <td width="50%" valign="top">
      <h3>⚡ Real-Time Catalyst NLP</h3>
      <ul>
        <li><b>28-category taxonomy</b> — earnings surprises, FDA approvals, SEBI actions, buybacks, mergers, RBI policy shifts.</li>
        <li><b>Dual-lexicon sentiment</b> — Loughran-McDonald financial lexicon plus calibrated VADER.</li>
        <li><b>Entity mapping</b> — NSE/BSE tickers, sector weights, confidence ratings, market bias.</li>
      </ul>
    </td>
    <td width="50%" valign="top">
      <h3>📈 Institutional Charts</h3>
      <ul>
        <li><b>Lightweight Charts v5</b> — canvas-accelerated candlesticks.</li>
        <li><b>Timeframes</b> — <code>15m</code>, <code>1h</code>, <code>1d</code>, <code>1w</code>.</li>
        <li><b>Overlays</b> — 20-period SMA, 50-period EMA, colour-synced volume.</li>
      </ul>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <h3>🎯 Price-Bracket Signals</h3>
      <ul>
        <li><b>Budget-aware filtering</b> into three tiers: ₹0–500, ₹500–2,000, ₹2,000+.</li>
        <li><b>Everywhere</b> — UI filter pills and Telegram command parameters.</li>
      </ul>
    </td>
    <td width="50%" valign="top">
      <h3>📱 Telegram 24/7 Cockpit</h3>
      <ul>
        <li><b>Natural lookups</b> — type <code>RELIANCE</code> for price, 52W range and drawdown.</li>
        <li><b>Inline actions</b> — open web terminal, mute 2h, unwatch.</li>
        <li><b>Hardened</b> — 409 conflict recovery, quiet hours, token redaction.</li>
      </ul>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <h3>🧠 Scikit-Learn ML Pipeline</h3>
      <ul>
        <li><b>9 models</b> — Logistic Regression, Random Forest, Gradient Boosting × 1D / 3D / 5D.</li>
        <li><b>11-feature matrix</b> — polarity, recency decay, volatility, relative volume, benchmark beta, category impact.</li>
        <li><b>Transparent diagnostics</b> — 80/20 split, macro F1, confusion matrices, dataset export.</li>
      </ul>
    </td>
    <td width="50%" valign="top">
      <h3>🔄 Dual-Scope Market Pulse</h3>
      <ul>
        <li><b>Live feed</b> — Moneycontrol, Economic Times, Yahoo Finance RSS.</li>
        <li><b>Historical baseline</b> — 9,900+ vetted Indian financial dispatches.</li>
        <li><b>Scope switcher</b> — compare live signals against historical norms.</li>
      </ul>
    </td>
  </tr>
</table>

---

## 🏛️ Architecture

```mermaid
flowchart LR
    subgraph SRC ["① Zero-cost ingestion"]
        A1["📡 RSS feeds<br/>Moneycontrol · ET · Yahoo · Google News"]
        A2["📊 yfinance<br/>NSE/BSE quotes · 90D OHLCV"]
        A3["🔌 Optional adapters<br/>Marketaux · Alpha Vantage · NewsAPI"]
    end
    subgraph NLP ["② NLP & catalyst engine"]
        B1["🧹 Dedup<br/>SHA-256 title+URL"]
        B2["🏷️ 28-category taxonomy"]
        B3["💬 Loughran-McDonald + VADER"]
        B4["🎯 Price bracket engine"]
    end
    subgraph ML ["③ ML horizon pipeline"]
        C1["📐 11-feature matrix"]
        C2["🌲 LogReg · RF · GradBoost"]
        C3["⏱️ 1D / 3D / 5D forecasts"]
    end
    subgraph API ["④ FastAPI · :8000"]
        D1["⚡ REST endpoints"]
        D2["💾 SQLite<br/>10 indexed tables"]
        D3["🤖 Telegram poller & dispatcher"]
    end
    subgraph UI ["⑤ Clients"]
        E1["💻 React 18 + Vite terminal"]
        E2["📱 Telegram alerts"]
    end
    A1 & A2 & A3 --> B1
    B1 --> B2 & B3 & B4
    B2 & B3 & B4 --> C1 --> C2 --> C3
    B4 & C3 --> D1
    D1 <--> D2
    D1 <--> D3
    D1 --> E1
    D3 --> E2
```

---

## 💸 Zero-Cost Architecture

Everything required to run ProfitSense is free. No credit card, no LLM tokens.

| Provider / Module | Domain | Free-tier limits | Role | Cost |
| :--- | :---: | :--- | :--- | :---: |
| **Financial RSS feeds** | News | No API key, no rate caps | Primary live news stream | **$0** |
| **Yahoo Finance (`yfinance`)** | Market data | Delayed quotes, 90-day OHLCV, volume | Market data & chart engine | **$0** |
| **Loughran-McDonald + VADER** | NLP | Runs locally on CPU | Financial sentiment | **$0** |
| **scikit-learn** | ML | Local training & inference | Multi-horizon forecasts | **$0** |
| **Telegram Bot API** | Alerts | Free token via `@BotFather` | Mobile push notifications | **$0** |
| *Marketaux (optional)* | News | 100 requests / month | Fallback provider | **$0** |
| *Alpha Vantage (optional)* | Sentiment | 25 requests / day | Sentiment validation | **$0** |
| *NewsAPI (optional)* | Global news | 100 requests / day (localhost) | Macro feed | **$0** |

---

## 🚀 Quickstart

**Prerequisites:** Python `3.10–3.12` · Node.js `18+` · Git

```bash
# 1 — Clone
git clone https://github.com/45Hitman18/ProfiteSense.git
cd ProfiteSense

# 2 — Configure (every key is optional)
cp .env.example .env

# 3 — Install backend + frontend
npm run install:all

# 4 — Launch FastAPI (:8000) and React (:5173) together
npm run dev
```

> 🪟 **Windows:** double-click `run.bat` for a one-click launch.

<details>
<summary><b>⚙️ Environment variables</b></summary>

```ini
# Core
DATABASE_URL=sqlite:///./backend/market_news.db
APP_BASE_URL=http://localhost:5173

# Telegram (optional — free from @BotFather)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TELEGRAM_ENABLED=true
TELEGRAM_POLL_INTERVAL=2.0

# Optional free news providers
MARKETAUX_API_KEY=
ALPHA_VANTAGE_API_KEY=
NEWSAPI_KEY=
```

</details>

<details>
<summary><b>🔧 Manual install</b></summary>

```bash
npm install
cd frontend && npm install && cd ..
cd backend && pip install -r requirements.txt
```

</details>

| Service | URL |
| :--- | :--- |
| 🖥️ Web terminal | http://localhost:5173 |
| 📘 Swagger docs | http://127.0.0.1:8000/docs |
| 🔌 API root | http://127.0.0.1:8000 |

---

## 📈 Interactive Charts

Hardware-accelerated candlesticks powered by **TradingView Lightweight Charts v5**.

| Layer | Details |
| :--- | :--- |
| **Candles** | 🟩 bullish (emerald) · 🟥 bearish (rose) |
| **Overlays** | 20-period SMA · 50-period EMA |
| **Volume** | Histogram colour-synced to candle direction |
| **Timeframes** | `15m` · `1h` · `1d` · `1w` |
| **UX** | Interactive crosshair, ₹ price badges, localised time formatting |
| **Responsive** | `ResizeObserver` — from 4K monitors to tablets |
| **Fallback** | Automatic SVG rendering if canvas or network data is unavailable |

---

## 🎯 Price Brackets

Signals are grouped into three tiers so users can focus on what fits their capital.

| Tier | Bracket | Profile | Examples |
| :---: | :---: | :--- | :--- |
| 🥉 **1** | **₹0 – ₹500** | High-beta mid/small caps, high retail interest | `TATASTEEL` `ZOMATO` `IRFC` `IDEA` |
| 🥈 **2** | **₹500 – ₹2,000** | Established leaders, steady compounders | `INFY` `HDFCBANK` `ICICIBANK` `SBIN` |
| 🥇 **3** | **₹2,000+** | Institutional heavyweights, low-beta stability | `RELIANCE` `TCS` `BAJFINANCE` `MARUTI` |

- **Web:** toggle brackets in the *Trading Signals & Recommendations* dashboard.
- **Telegram:** `/signals 0-500` · `/signals 500-2000` · `/signals 2000+`

---

## 📱 Telegram Bot

Real-time push alerts the moment a high-impact catalyst breaks. Create a free bot with [`@BotFather`](https://t.me/BotFather), paste the token into `.env`, and pair it from **Settings**.

| Command | What it does | Example |
| :--- | :--- | :--- |
| `<SHARE_NAME>` | Smart lookup: price, 52W range, loss from peak | `RELIANCE` |
| `/p <TICKER>` | Quote with 52W range bar | `/p INFY` |
| `/signals [tier]` | Top AI recommendations by price bracket | `/signals 0-500` |
| `/w <TICKER>` | Add to watchlist | `/w RELIANCE` |
| `/uw <TICKER>` | Remove from watchlist | `/uw TCS` |
| `/list` | Watchlist with live prices | `/list` |
| `/mute <time>` | Silence alerts (`30m`, `2h`, `1d`) | `/mute 2h` |
| `/unmute` | Resume alerts | `/unmute` |
| `/quiet <range>` | Do-not-disturb hours (handles midnight crossover) | `/quiet 22:00-07:00` |
| `/digest [time]` | Post-market digest in IST | `/digest 18:30` |
| `/status` | Connection health, filters, watchlist count | `/status` |

<details>
<summary><b>🛡️ Reliability & security</b></summary>

- **409 conflict recovery** — graceful poller handshake and webhook draining on restart.
- **Rate limiting** — max 10 alerts per hour per chat.
- **Deduplication** — strict `(chat_id, article_id, ticker)` uniqueness.
- **Zero token leakage** — token lives only in `.env` and is redacted from logs and stack traces.

</details>

---

## 🧠 Machine Learning Engine

```mermaid
flowchart LR
    N["💬 Sentiment polarity<br/>Sentiment intensity<br/>28-category impact"] --> S
    T["📉 1D prior return<br/>20D volatility<br/>Relative volume<br/>NIFTY 5D trend"] --> S
    S["StandardScaler"] --> M["LogReg · RF · GradBoost"]
    M --> P["🎯 Direction probability<br/>Positive · Neutral · Negative"]
```

- **3 algorithms:** Logistic Regression (L2), Random Forest (100 estimators), Gradient Boosting
- **3 horizons:** 1-day, 3-day, 5-day post-news returns
- **9 serialised models** in `backend/models/*.joblib`

### Evaluation (80/20 temporal split)

| Model | Horizon | Accuracy | Macro F1 |
| :--- | :---: | :---: | :---: |
| Random Forest | 1D | 100.0% | 1.0000 |
| Gradient Boosting | 1D | 88.9% | 0.8615 |
| Logistic Regression | 1D | 88.9% | 0.8615 |
| Random Forest | 3D | 100.0% | 1.0000 |
| Random Forest | 5D | 100.0% | 1.0000 |

> [!NOTE]
> These scores come from a small held-out set and should be read as a demonstration of the pipeline, not as evidence of live trading edge. Perfect scores on small test sets usually signal limited sample size — evaluate on larger, out-of-time data before drawing conclusions.

---

## 🧪 Testing

```bash
pytest backend                          # 105 backend tests
npm --prefix frontend test -- --run     # 7 frontend tests
npm --prefix frontend run build         # production build
```

| Suite | Result |
| :--- | :--- |
| Backend (pytest) | ✅ 105 passed |
| Frontend (Vitest) | ✅ 7 passed (`chartUtils` ×5, `PriceChart` ×2) |
| Production build | ✅ ~486 kB JS · ~39 kB CSS |

---

## 📂 Project Structure

```text
ProfitSense/
├── .env.example                 # Environment template (all keys optional)
├── package.json                 # Unified runner (FastAPI + Vite)
├── run.bat                      # One-click Windows launcher
├── docs/assets/                 # Logo, banner & preview graphics
│
├── backend/                     # FastAPI service
│   ├── main.py                  # REST endpoints & app init
│   ├── database.py              # SQLite schema (10 tables) & migrations
│   ├── nlp_engine.py            # 28-category taxonomy & sentiment
│   ├── ml_pipeline.py           # 11-feature training & persistence
│   ├── technical_features.py    # Volatility, SMA, EMA, volume normaliser
│   ├── chart_service.py         # OHLCV resampling & timeframes
│   ├── price_brackets.py        # ₹0–500 / ₹500–2k / ₹2k+ classifier
│   ├── trade_engine.py          # Recommendations & stop-loss synthesis
│   ├── telegram_bot.py          # Polling & command dispatch
│   ├── telegram_alerts.py       # Alert formatting & queueing
│   ├── providers/               # Market & news providers
│   ├── models/                  # 9 trained .joblib models
│   └── tests/                   # 105 pytest tests
│
└── frontend/                    # React 18 + Vite SPA
    ├── vite.config.js
    └── src/
        ├── App.jsx              # Navigation & view manager
        ├── components/
        │   ├── DashboardView.jsx
        │   ├── CustomAnalyzerView.jsx
        │   ├── ModelAnalyticsView.jsx
        │   ├── InteractiveChart.jsx
        │   ├── WatchlistView.jsx
        │   ├── SettingsView.jsx
        │   └── chart/PriceChart.jsx
        ├── lib/chartUtils.js
        └── test/                # 7 Vitest tests
```

---

## 🤝 Contributing

Contributions are welcome.

1. Fork the repo and create a branch: `git checkout -b feat/your-feature`
2. Make your change and add tests
3. Run `pytest backend` and `npm --prefix frontend test -- --run`
4. Open a pull request describing what and why

---

## 📄 License

Released under the [MIT License](LICENSE).

---

## ⚖️ Disclaimer

> [!IMPORTANT]
> **Financial & investment disclaimer.** ProfitSense is an experimental research and educational platform demonstrating quantitative NLP, ML signal synthesis and financial visualisation.
>
> - **Not investment advice.** No data, sentiment rating, signal, prediction or bracket filter constitutes financial, investment, legal or tax advice.
> - **Probabilistic.** Markets are non-deterministic; outputs are algorithmic estimates based on historical correlations.
> - **Mandatory label.** Every predictive surface in the UI and Telegram bot shows: *"AI/model estimate — not investment advice."*
> - Do your own due diligence or consult a licensed SEBI-registered advisor before allocating capital.

<div align="center">

<br/>

<img src="docs/assets/logo.svg" alt="ProfitSense logo" width="72"/>

**ProfitSense** — *built with precision for quantitative traders and financial engineers.*

<sub>If this project helps you, consider giving it a ⭐</sub>

[⬆ Back to top](#)

</div>
