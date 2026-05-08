"""Telegram MarkdownV2 message formatting and dispatch."""
import httpx

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"

# All characters MarkdownV2 requires escaping
MD2_SPECIALS = set(r"_*[]()~`>#+-=|{}.!\\")


def escape_md2(text) -> str:
    return "".join(f"\\{c}" if c in MD2_SPECIALS else c for c in str(text))


def format_message(award: dict, ticker: str, vol, summary: str) -> str:
    company = escape_md2(award["recipient"])
    ticker_e = escape_md2(ticker)
    amount = escape_md2(f"${award['amount']:,.0f}")
    naics = escape_md2(award["naics"])
    summary_e = escape_md2(summary)
    link = award.get("ui_link") or "https://sam.gov"

    if vol is not None:
        vol_line = escape_md2(
            f"📈 Volatility: {vol.ratio}x ATR ({vol.interpretation})"
        )
    else:
        vol_line = escape_md2("📈 Volatility: n/a")

    lines = [
        f"🏛️ *{company}* \\({ticker_e}\\)",
        f"💰 {amount} \\| NAICS {naics}",
        vol_line,
        f"📝 {summary_e}",
        f"🔗 [View on SAM\\.gov]({link})",
    ]
    return "\n".join(lines)


def send_notification(token: str, chat_id: str, text: str) -> None:
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "MarkdownV2",
        "disable_web_page_preview": True,
    }
    resp = httpx.post(TELEGRAM_API.format(token=token), json=payload, timeout=15.0)
    resp.raise_for_status()
