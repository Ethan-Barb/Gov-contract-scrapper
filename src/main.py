"""Main orchestrator - runs all enabled bot modules and saves to unified DB."""
import logging

from src.common.config import config
from src.common.state import StateStore
from src.common.watchlist import load_watchlist
from src.common.edgar_client import EdgarClient
from src.common.summarizer import summarize_8k, summarize_contract
from src.common.telegram_bot import (
    format_contract, format_form4, format_8k,
    format_earnings_preview, format_earnings_reaction,
    fmt_money, send_notification,
)
from src.bots.contracts import SAMClient, TickerResolver, calculate_atr
from src.bots.form4 import fetch_insider_transactions
from src.bots.form8k import fetch_8k_filings
from src.bots.earnings import find_upcoming_earnings, find_earnings_reactions

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
)
log = logging.getLogger("bot")


def _send(text: str) -> bool:
    try:
        send_notification(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID, text)
        return True
    except Exception as e:
        log.error("Telegram send failed: %s", e)
        return False


def run_contracts(state) -> int:
    if not config.MODULE_CONTRACTS or not config.SAM_API_KEY:
        return 0
    sam = SAMClient(config.SAM_API_KEY, config.MIN_AWARD_AMOUNT, config.NAICS_CODES)
    resolver = TickerResolver(state, config.TICKER_CONFIDENCE_THRESHOLD, config.SEC_USER_AGENT)
    notified = 0
    for award in sam.fetch_recent_awards(config.LOOKBACK_DAYS):
        award_id = award["award_id"]
        if not award_id or state.is_contract_seen(award_id):
            continue
        log.info("Contract: %s | %s | $%s",
                 award_id, award["recipient"], f"{award['amount']:,.0f}")

        ticker = resolver.resolve(award["recipient"])
        summary = ""
        vol = None

        if ticker:
            vol = calculate_atr(ticker)
            summary = summarize_contract(award["description"], config.GROQ_API_KEY, config.LLM_MODEL)
            text = format_contract(award, ticker, vol, summary)
            if _send(text):
                state.log_alert(
                    source="contract",
                    ticker=ticker,
                    title=f"{award['recipient']} - {fmt_money(award['amount'])}",
                    body=summary,
                    link=award.get("ui_link"),
                    metadata={"naics": award.get("naics"), "amount": award["amount"]},
                )
                notified += 1

        # Always save to contracts table for the dashboard
        state.save_contract(
            award_id=award_id,
            posted_date=award.get("posted_date"),
            recipient=award["recipient"],
            ticker=ticker,
            amount=award["amount"],
            naics=award.get("naics"),
            title=award.get("title"),
            summary=summary,
            ui_link=award.get("ui_link"),
        )
    return notified


def run_form4(client, state, watchlist) -> int:
    if not config.MODULE_FORM4:
        return 0
    notified = 0
    for company in watchlist:
        try:
            txns = fetch_insider_transactions(client, state, company, config)
            for txn in txns:
                log.info("Form 4: %s %s %s $%.0f",
                         txn.ticker, txn.transaction_code, txn.insider_name, txn.total_value)
                if _send(format_form4(txn)):
                    state.save_insider_transaction(
                        accession_number=txn.accession,
                        ticker=txn.ticker,
                        filing_date=txn.filing_date,
                        insider_name=txn.insider_name,
                        insider_role=txn.insider_role,
                        transaction_code=txn.transaction_code,
                        shares=txn.shares,
                        price=txn.price,
                        total_value=txn.total_value,
                        filing_url=txn.filing_url,
                    )
                    state.log_alert(
                        source="form4",
                        ticker=txn.ticker,
                        title=f"{'BUY' if txn.transaction_code == 'P' else 'SALE'}: {txn.insider_name}",
                        body=f"{txn.shares:,.0f} shares @ ${txn.price:.2f} = {fmt_money(txn.total_value)}",
                        link=txn.filing_url,
                        metadata={"code": txn.transaction_code, "value": txn.total_value},
                    )
                    notified += 1
        except Exception as e:
            log.error("Form 4 error for %s: %s", company.ticker, e)
    return notified


def run_8k(client, state, watchlist) -> int:
    if not config.MODULE_8K:
        return 0
    notified = 0
    for company in watchlist:
        try:
            filings = fetch_8k_filings(client, state, company, config)
            for f in filings:
                log.info("8-K: %s items=%s", f.ticker, f.items)
                summary = summarize_8k(f.text_excerpt, f.items, config.GROQ_API_KEY, config.LLM_MODEL)
                if _send(format_8k(f, summary)):
                    state.save_8k(
                        accession_number=f.accession,
                        ticker=f.ticker,
                        filing_date=f.filing_date,
                        items=",".join(f.items),
                        summary=summary,
                        filing_url=f.filing_url,
                    )
                    state.log_alert(
                        source="8k",
                        ticker=f.ticker,
                        title=f"8-K: {', '.join(f.items[:2])}",
                        body=summary,
                        link=f.filing_url,
                        metadata={"items": f.items},
                    )
                    notified += 1
        except Exception as e:
            log.error("8-K error for %s: %s", company.ticker, e)
    return notified


def run_earnings(state, watchlist) -> int:
    if not config.MODULE_EARNINGS:
        return 0
    notified = 0
    for company in watchlist:
        try:
            preview = find_upcoming_earnings(state, company, config.EARNINGS_LOOKAHEAD_DAYS)
            if preview:
                log.info("Earnings preview: %s on %s", preview.ticker, preview.earnings_date)
                if _send(format_earnings_preview(preview)):
                    state.mark_earnings_alerted(preview.ticker, preview.earnings_date, "preview")
                    state.log_alert(
                        source="earnings",
                        ticker=preview.ticker,
                        title=f"Earnings tomorrow: {preview.ticker}",
                        body=f"EPS est: ${preview.eps_estimate:.2f}" if preview.eps_estimate else "Earnings tomorrow",
                        metadata={"phase": "preview", "date": preview.earnings_date},
                    )
                    notified += 1
        except Exception as e:
            log.error("Earnings preview error for %s: %s", company.ticker, e)

        try:
            reaction = find_earnings_reactions(state, company)
            if reaction:
                log.info("Earnings reaction: %s on %s", reaction.ticker, reaction.earnings_date)
                if _send(format_earnings_reaction(reaction)):
                    state.mark_earnings_alerted(reaction.ticker, reaction.earnings_date, "reaction")
                    state.record_earnings(
                        ticker=reaction.ticker,
                        earnings_date=reaction.earnings_date,
                        eps_estimate=reaction.eps_estimate,
                        eps_actual=reaction.eps_actual,
                        price_before=reaction.price_before,
                        price_after=reaction.price_after,
                        pct_change=reaction.pct_change,
                    )
                    state.log_alert(
                        source="earnings",
                        ticker=reaction.ticker,
                        title=f"Earnings result: {reaction.ticker}",
                        body=f"EPS ${reaction.eps_actual} vs est ${reaction.eps_estimate}",
                        metadata={"phase": "reaction", "pct_change": reaction.pct_change},
                    )
                    notified += 1
        except Exception as e:
            log.error("Earnings reaction error for %s: %s", company.ticker, e)
    return notified


def main() -> None:
    config.validate()

    state = StateStore(config.DB_PATH)
    watchlist = load_watchlist(config.WATCHLIST_PATH)
    client = EdgarClient(config.SEC_USER_AGENT)

    log.info("Loaded %d companies from watchlist", len(watchlist))

    contracts = run_contracts(state)
    log.info("Contracts: %d notifications", contracts)

    f4 = run_form4(client, state, watchlist)
    log.info("Form 4: %d notifications", f4)

    eight_k = run_8k(client, state, watchlist)
    log.info("8-K: %d notifications", eight_k)

    earnings = run_earnings(state, watchlist)
    log.info("Earnings: %d notifications", earnings)

    log.info("Run complete. Total: %d", contracts + f4 + eight_k + earnings)


if __name__ == "__main__":
    main()
