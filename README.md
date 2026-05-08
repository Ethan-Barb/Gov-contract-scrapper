# Investing Intel

A unified investing intelligence system: Telegram alerts + web dashboard, all running on free tiers.

## What it does

**Four bots that run 3x/day on weekdays and ping your phone via Telegram:**

1. **Government Contracts** — high-value SAM.gov awards to public companies, with AI summary + volatility check
2. **Insider Trading (Form 4)** — executives buying/selling their own stock, filtered to high-signal events
3. **8-K Filings** — material corporate events (acquisitions, restatements, exec departures), AI-summarized
4. **Earnings** — pre-announcement preview + post-announcement reaction tracker

**A web dashboard you can open on phone or laptop:**

- Overview of recent alerts
- Searchable alert history
- Insider buy/sell charts
- Earnings beat/miss tracker that builds up over time
- Government contract totals by company
- Your personal portfolio with live P&L

All data flows through a single SQLite DB. Bots write, dashboard reads.

## Setup

### 1. Push to GitHub

Create a new private repo on GitHub. Then:

```bash
cd investing-intel
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/investing-intel.git
git push -u origin main
```

### 2. Add bot secrets

Settings → Secrets and variables → Actions → New repository secret. Add:

| Name | Value |
|---|---|
| `SAM_API_KEY` | Get free at https://sam.gov |
| `GROQ_API_KEY` | Free at https://console.groq.com |
| `TELEGRAM_BOT_TOKEN` | From @BotFather on Telegram |
| `TELEGRAM_CHAT_ID` | From @userinfobot on Telegram |
| `SEC_USER_AGENT` | Format: `YourName your@email.com` (SEC requires real contact) |

### 3. Deploy the dashboard

1. Go to https://share.streamlit.io
2. Sign in with GitHub
3. Click **New app**
4. Pick your `investing-intel` repo
5. Set **Main file path** to: `dashboard/app.py`
6. Click **Advanced settings** → **Secrets** → paste:
   ```
   DASHBOARD_PASSWORD = "pick-a-password-you-remember"
   ```
7. Click **Deploy**

After ~2 minutes you'll get a URL like `https://yourname-investing-intel.streamlit.app`

### 4. Customize

- **`data/watchlist.csv`** — which tickers the SEC bots monitor (30 starter companies included)
- **`data/portfolio.csv`** — your stock holdings (starts empty; edit with your real positions)
- **`src/common/config.py`** — all filter thresholds, NAICS codes, signal logic

## How the data flows

```
GitHub Actions (3x/day weekdays)
    ↓
Run bots (src/main.py)
    ↓
Bots write to data/intel.db (SQLite)
    ↓
Bots commit DB back to repo
    ↓
Streamlit redeploys (auto-detects new commit)
    ↓
You open dashboard URL → see latest data
```

The DB is committed back to your repo on every run. This means your dashboard always has the latest data without needing a separate database service. Your Telegram still gets the real-time alerts independently.

## Project layout

```
investing-intel/
├── .github/workflows/poll.yml      # 3x/day cron
├── .streamlit/
│   ├── config.toml                 # dark theme
│   └── secrets.toml.example
├── src/
│   ├── main.py                     # orchestrator
│   ├── common/
│   │   ├── config.py               # all knobs
│   │   ├── state.py                # SQLite (8 tables)
│   │   ├── watchlist.py
│   │   ├── edgar_client.py         # rate-limited SEC client
│   │   ├── summarizer.py           # Groq
│   │   └── telegram_bot.py         # MarkdownV2 formatters
│   └── bots/
│       ├── contracts.py            # SAM + tickers + ATR
│       ├── form4.py                # insider trades
│       ├── form8k.py               # material events
│       └── earnings.py             # earnings calendar
├── dashboard/
│   └── app.py                      # Streamlit (single file)
├── data/
│   ├── watchlist.csv               # tickers + CIKs
│   ├── portfolio.csv               # your holdings
│   └── intel.db                    # generated, committed by bot
├── requirements.txt
└── README.md
```

## Tuning

All knobs are in `src/common/config.py`:

```python
MIN_AWARD_AMOUNT = 5_000_000          # contract bot threshold
MIN_INSIDER_PURCHASE_USD = 100_000    # ignore tiny insider buys
MIN_INSIDER_SALE_USD = 1_000_000      # only big sales notify
HIGH_SIGNAL_ITEMS = ["1.01", "2.01", "4.02", "5.02", ...]
EARNINGS_LOOKAHEAD_DAYS = 1           # alert N days before earnings
```

To turn off a module without deleting code, set env var to false:
```yaml
env:
  MODULE_FORM4: "false"
```

## Schedule

Three runs per weekday (all times are UTC; Central US):
- **13:00 UTC = 8 AM CT** — pre-market check
- **17:00 UTC = 12 PM CT** — midday
- **22:00 UTC = 5 PM CT** — after-hours catch

To change: edit `.github/workflows/poll.yml`.

## What you'll see

**Telegram alerts** are exactly the same format you already know.

**Dashboard tabs:**
- 📊 **Overview** — top numbers + recent activity feed
- 📋 **Alerts** — full history with filters
- 🟢 **Insiders** — buy/sell charts per ticker
- 📅 **Earnings** — beat rate per ticker, full history
- 🏛️ **Contracts** — totals by company, all awards
- 💼 **Portfolio** — your holdings with live prices

## Important notes

**This is information, not advice.** Insider buying is interesting because executives have inside knowledge — but you can't legally trade on inside info, and even insiders are wrong constantly. Use these signals to research deeper, not as buy/sell triggers.

**The portfolio P&L pulls real prices** but is read-only — there's no integration with brokerages. Update `portfolio.csv` manually when you trade.

**The dashboard refreshes every 15 minutes.** Hit "🔄 Refresh data" to force a reload. New bot runs propagate within ~2 minutes of completing.

**SEC EDGAR has no rate limit but asks politely for ≤10 req/sec.** With 30 watchlist companies × 3 modules × 3 runs/day, you're well under.

## What this teaches you

Each module shows you a different lens on markets:

- **Form 4** — insiders putting their own money to work; closest thing to a "smart money" signal retail can see
- **8-Ks** — the official news feed for material corporate events
- **Earnings tracker** — over time, becomes a personal database of which companies tend to beat and how the market reacts
- **Contracts** — sector-level capital flows from the largest customer in the world (US gov)

Run it for 6 months. The patterns you'll start to notice in the data are the actual education.
