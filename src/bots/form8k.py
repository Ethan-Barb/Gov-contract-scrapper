"""8-K material event tracker."""
import re
from dataclasses import dataclass
from html import unescape


@dataclass
class Form8KFiling:
    ticker: str
    accession: str
    filing_date: str
    items: list
    text_excerpt: str
    filing_url: str


def _strip_html(text: str) -> str:
    text = re.sub(r"<script.*?</script>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _extract_items(text: str) -> list[str]:
    pattern = re.compile(r"\bItem\s+(\d+\.\d{2})\b", re.IGNORECASE)
    items = pattern.findall(text)
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _extract_excerpt(text: str, max_chars: int = 3000) -> str:
    idx = text.lower().find("item ")
    if idx < 0:
        return text[:max_chars]
    return text[idx:idx + max_chars]


def fetch_8k_filings(client, state, company, cfg) -> list[Form8KFiling]:
    filings = client.get_company_filings(company.cik, "8-K", count=10)
    out = []
    for filing in filings:
        if state.is_filing_seen(filing["accession"]):
            continue
        raw = client.fetch_filing_text(
            filing["cik"], filing["accession"], filing["primary_doc"]
        )
        if not raw:
            state.mark_filing_seen(filing["accession"], "8-K")
            continue
        text = _strip_html(raw)
        items = _extract_items(text)
        high_signal = [i for i in items if i in cfg.HIGH_SIGNAL_ITEMS]
        if not high_signal:
            state.mark_filing_seen(filing["accession"], "8-K")
            continue
        out.append(Form8KFiling(
            ticker=company.ticker,
            accession=filing["accession"],
            filing_date=filing["filing_date"],
            items=items,
            text_excerpt=_extract_excerpt(text),
            filing_url=client.get_filing_url(
                filing["cik"], filing["accession"], filing["primary_doc"]
            ),
        ))
        state.mark_filing_seen(filing["accession"], "8-K")
    return out
