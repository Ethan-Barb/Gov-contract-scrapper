"""Unified configuration for all bots and dashboard."""
import os
from dataclasses import dataclass, field


@dataclass
class Config:
    # ---- Required secrets ----
    SAM_API_KEY: str = os.environ.get("SAM_API_KEY", "")
    GROQ_API_KEY: str = os.environ.get("GROQ_API_KEY", "")
    TELEGRAM_BOT_TOKEN: str = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.environ.get("TELEGRAM_CHAT_ID", "")
    SEC_USER_AGENT: str = os.environ.get(
        "SEC_USER_AGENT", "InvestingIntelBot research@example.com"
    )

    # ---- Paths ----
    DB_PATH: str = os.environ.get("DB_PATH", "data/intel.db")
    WATCHLIST_PATH: str = os.environ.get("WATCHLIST_PATH", "data/watchlist.csv")
    PORTFOLIO_PATH: str = os.environ.get("PORTFOLIO_PATH", "data/portfolio.csv")

    # ---- Module toggles ----
    MODULE_CONTRACTS: bool = os.environ.get("MODULE_CONTRACTS", "true").lower() == "true"
    MODULE_FORM4:    bool = os.environ.get("MODULE_FORM4",    "true").lower() == "true"
    MODULE_8K:       bool = os.environ.get("MODULE_8K",       "true").lower() == "true"
    MODULE_EARNINGS: bool = os.environ.get("MODULE_EARNINGS", "true").lower() == "true"

    # ---- Government contract filter ----
    MIN_AWARD_AMOUNT: float = 5_000_000
    LOOKBACK_DAYS: int = 2
    NAICS_CODES: list = field(default_factory=lambda: [
        "541330", "541512", "541715", "336411", "336414",
    ])
    TICKER_CONFIDENCE_THRESHOLD: int = 88

    # ---- Form 4 filters ----
    MIN_INSIDER_PURCHASE_USD: float = 100_000
    MIN_INSIDER_SALE_USD:     float = 1_000_000
    NOTIFY_ALL_C_SUITE_PURCHASES: bool = True

    # ---- 8-K filters ----
    HIGH_SIGNAL_ITEMS: list = field(default_factory=lambda: [
        "1.01", "1.02", "2.01", "2.06", "3.01", "4.01", "4.02", "5.02", "8.01",
    ])

    # ---- Earnings ----
    EARNINGS_LOOKAHEAD_DAYS: int = 1

    # ---- LLM ----
    LLM_MODEL: str = "llama-3.1-8b-instant"

    def validate(self):
        missing = [
            k for k in ("GROQ_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")
            if not getattr(self, k)
        ]
        if missing:
            raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")


config = Config()
