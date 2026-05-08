"""Configuration loaded from environment variables."""
import os
from dataclasses import dataclass, field


@dataclass
class Config:
    # --- Required secrets ---
    SAM_API_KEY: str = os.environ.get("SAM_API_KEY", "")
    GROQ_API_KEY: str = os.environ.get("GROQ_API_KEY", "")
    TELEGRAM_BOT_TOKEN: str = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.environ.get("TELEGRAM_CHAT_ID", "")

    # --- Filter parameters ---
    MIN_AWARD_AMOUNT: float = float(os.environ.get("MIN_AWARD_AMOUNT", 5_000_000))
    NAICS_CODES: list = field(default_factory=lambda: [
        "541330",  # Engineering Services
        "541512",  # Computer Systems Design Services
        "541715",  # R&D in Physical/Engineering/Life Sciences
        "336411",  # Aircraft Manufacturing
        "336414",  # Guided Missile & Space Vehicle Manufacturing
    ])

    # --- Operational parameters ---
    DB_PATH: str = os.environ.get("DB_PATH", "data/state.db")
    TICKER_CONFIDENCE_THRESHOLD: int = 88   # rapidfuzz score 0-100
    LOOKBACK_DAYS: int = 2                  # SAM query window per run
    LLM_MODEL: str = "llama-3.1-8b-instant"

    def validate(self):
        missing = [
            k for k in ("SAM_API_KEY", "GROQ_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")
            if not getattr(self, k)
        ]
        if missing:
            raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")


config = Config()
