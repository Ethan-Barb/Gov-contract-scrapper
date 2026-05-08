"""Telegram MarkdownV2 formatters and sender for all alert types."""
import httpx

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
MD2_SPECIALS = set(r"_*[]()~`>#+-=|{}.!\\")

# 8-K item labels
ITEM_LABELS = {
    "1.01": "Material Agreement",
    "1.02": "Agreement Terminated",
    "1.03": "Bankruptcy",
    "2.01": "Acquisition Completed",
    "2.02": "Earnings Released",
    "2.06": "Material Impairments",
    "3.01": "Notice of Delisting",
    "4.01": "Auditor Changed",
    "4.02": "🚨 Restatement",
    "5.02": "Officer Departure",
    "8.01": "Other Events",
}


def escape_md2(text) -> str:
    return "".join(f"\\{c}" if c in MD2_SPECIALS else c for c in str(text))


def fmt_money(amount: float) -> str:
    if amount >= 1_000_000_000:
        return f"${amount/1_000_000_000:.2f}B"
    if amount >= 1_000_000:
        return f"${amount/1_000_000:.2f}M"
    if amount >= 1_000:
        return f"${amount/1_000:.0f}K"
    return f"${amount:.0f}"


def format_contract(award: dict, ticker: str, vol, summary: str) -> str:
    company = escape_md2(award["recipient"])
    ticker_e = escape_md2(ticker)
    amount = escape_md2(fmt_money(award["amount"]))
    naics = escape_md2(award.get("naics", ""))
    summary_e = escape_md2(summary)
    link = award.get("ui_link") or "https://sam.gov"

    if vol is not None:
        vol_line = escape_md2(f"📈 Volatility: {vol.ratio}x ATR ({vol.interpretation})")
    else:
        vol_line = escape_md2("📈 Volatility: n/a")

    return "\n".join([
        f"🏛️ *{company}* \\({ticker_e}\\)",
        f"💰 {amount} \\| NAICS {naics}",
        vol_line,
        f"📝 {summary_e}",
        f"🔗 [SAM\\.gov]({link})",
    ])


def format_form4(txn) -> str:
    if txn.transaction_code == "P":
        emoji = "🟢 INSIDER BUY"
    elif txn.transaction_code == "S":
        emoji = "🔴 INSIDER SALE"
    else:
        emoji = "⚪ INSIDER TRANSACTION"

    role_str = txn.insider_role or (
        "10% Owner" if txn.is_ten_percent_owner else
        "Officer" if txn.is_officer else
        "Director" if txn.is_director else "Insider"
    )
    return "\n".join([
        f"{escape_md2(emoji)}: *{escape_md2(txn.ticker)}*",
        f"👤 {escape_md2(txn.insider_name)} \\({escape_md2(role_str)}\\)",
        f"💰 {escape_md2(f'{txn.shares:,.0f} @ ${txn.price:.2f}')} \\= {escape_md2(fmt_money(txn.total_value))}",
        f"🔗 [Form 4]({txn.filing_url})",
    ])


def format_8k(filing, summary: str) -> str:
    item_labels = []
    for item in filing.items[:3]:
        label = ITEM_LABELS.get(item, "Other")
        item_labels.append(f"{item} \\({escape_md2(label)}\\)")
    items_line = " \\| ".join(item_labels)
    return "\n".join([
        f"📋 *8\\-K*: *{escape_md2(filing.ticker)}*",
        f"🏷️ {items_line}",
        f"📝 {escape_md2(summary)}",
        f"📅 {escape_md2(filing.filing_date)}",
        f"🔗 [Filing]({filing.filing_url})",
    ])


def format_earnings_preview(p) -> str:
    eps_str = f"${p.eps_estimate:.2f}" if p.eps_estimate else "n/a"
    rev_str = fmt_money(p.revenue_estimate) if p.revenue_estimate else "n/a"
    return "\n".join([
        f"📅 *EARNINGS UPCOMING*: *{escape_md2(p.ticker)}*",
        f"🗓️ {escape_md2(p.earnings_date)}",
        f"💵 EPS est: {escape_md2(eps_str)} \\| Rev est: {escape_md2(rev_str)}",
        f"📊 Last 4Q: {p.last_4_beats}B / {p.last_4_misses}M",
    ])


def format_earnings_reaction(r) -> str:
    if r.eps_actual is not None and r.eps_estimate is not None:
        beat = "✅" if r.eps_actual >= r.eps_estimate else "❌"
        eps_line = f"{beat} EPS: ${r.eps_actual:.2f} (est ${r.eps_estimate:.2f})"
        if r.eps_surprise_pct is not None:
            eps_line += f" {r.eps_surprise_pct:+.1f}%"
    else:
        eps_line = "EPS: data unavailable"

    if r.pct_change is not None:
        arrow = "📈" if r.pct_change >= 0 else "📉"
        price_line = f"{arrow} Stock: {r.pct_change:+.2f}%"
    else:
        price_line = "Stock: reaction not yet measurable"

    return "\n".join([
        f"📊 *EARNINGS RESULT*: *{escape_md2(r.ticker)}*",
        f"🗓️ {escape_md2(r.earnings_date)}",
        escape_md2(eps_line),
        escape_md2(price_line),
    ])


def send_notification(token: str, chat_id: str, text: str) -> None:
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "MarkdownV2",
        "disable_web_page_preview": True,
    }
    resp = httpx.post(TELEGRAM_API.format(token=token), json=payload, timeout=15.0)
    resp.raise_for_status()
