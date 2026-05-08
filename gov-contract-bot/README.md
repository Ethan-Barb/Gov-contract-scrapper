# Government Contract & Market Intelligence Bot

Polls SAM.gov for new high-value contract awards, identifies whether the recipient is a publicly traded company, computes a 14-day ATR volatility check, generates a one-sentence AI summary, and pushes a Telegram notification.

Designed to run for **$0** on GitHub Actions free tier.

## Setup

1. **Get free API keys**
   - SAM.gov: https://open.gsa.gov/api/get-opportunities-public-api/ (free, requires registration)
   - Groq: https://console.groq.com (free tier, 30 req/min)
   - Telegram: chat with [@BotFather](https://t.me/BotFather), then get your chat id from [@userinfobot](https://t.me/userinfobot)

2. **Local dev**
   ```bash
   cp .env.example .env       # fill in your keys
   pip install -r requirements.txt
   set -a && source .env && set +a
   python -m src.main
   ```

3. **GitHub Actions deploy**
   - Push this repo to GitHub
   - Settings → Secrets and variables → Actions → add the four secrets from `.env.example`
   - Workflow runs hourly automatically; trigger manually via Actions tab

## Project Structure

```
gov-contract-bot/
├── .github/workflows/poll.yml   # hourly cron
├── src/
│   ├── config.py                # env vars + filter params
│   ├── state.py                 # SQLite: seen awards + ticker cache
│   ├── sam_client.py            # SAM.gov Opportunities API v2
│   ├── ticker_resolver.py       # SEC EDGAR + fuzzy match
│   ├── volatility.py            # 14-day ATR via yfinance
│   ├── summarizer.py            # Groq Llama 3.1
│   ├── telegram_bot.py          # MarkdownV2 dispatcher
│   └── main.py                  # orchestrator
├── data/                        # state.db lives here
├── requirements.txt
├── .env.example
└── .gitignore
```

## Tuning Knobs

- `MIN_AWARD_AMOUNT` (env) — default $5M
- `NAICS_CODES` (config.py) — defense / R&D / aerospace by default
- `TICKER_CONFIDENCE_THRESHOLD` (config.py) — fuzzy-match score 0-100, default 88
- Cron schedule (poll.yml) — default hourly

## Known Limitations

- SAM `description` field is sometimes a URL rather than inline text; bot uses whatever is returned. Add a `httpx.get()` follow-up if you need full text.
- Ticker matcher will miss subsidiaries (e.g. "Sikorsky Aircraft" → LMT). Maintain a manual override CSV for high-priority contractors.
- `yfinance` is unofficial — for production-grade reliability, swap in a paid feed.
