"""Main polling loop — orchestrates SAM → ticker → volatility → AI → Telegram."""
import logging

from src.config import config
from src.state import StateStore
from src.sam_client import SAMClient
from src.ticker_resolver import TickerResolver
from src.volatility import calculate_atr
from src.summarizer import summarize
from src.telegram_bot import format_message, send_notification

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
)
log = logging.getLogger("bot")


def main() -> None:
    config.validate()

    state = StateStore(config.DB_PATH)
    sam = SAMClient(config.SAM_API_KEY, config.MIN_AWARD_AMOUNT, config.NAICS_CODES)
    resolver = TickerResolver(state, config.TICKER_CONFIDENCE_THRESHOLD)

    processed = 0
    notified = 0

    for award in sam.fetch_recent_awards(config.LOOKBACK_DAYS):
        award_id = award["award_id"]
        if not award_id or state.is_seen(award_id):
            continue

        processed += 1
        log.info(
            "Processing %s | %s | $%s",
            award_id, award["recipient"], f"{award['amount']:,.0f}",
        )

        ticker = resolver.resolve(award["recipient"])
        if not ticker:
            log.info("  → no public ticker; skipping notification")
            state.mark_seen(award_id)
            continue

        vol = calculate_atr(ticker)
        summary = summarize(award["description"], config.GROQ_API_KEY, config.LLM_MODEL)
        message = format_message(award, ticker, vol, summary)

        try:
            send_notification(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID, message)
            notified += 1
            log.info("  → notified for %s", ticker)
        except Exception as e:
            log.error("  → telegram send failed: %s", e)
            continue   # don't mark seen so we retry next run

        state.mark_seen(award_id)

    log.info("Run complete. processed=%d notified=%d", processed, notified)


if __name__ == "__main__":
    main()
