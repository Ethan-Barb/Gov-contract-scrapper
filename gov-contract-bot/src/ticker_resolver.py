"""Resolve a contractor recipient name to a public ticker via SEC EDGAR + fuzzy matching."""
import re
import httpx
from rapidfuzz import process, fuzz

from src.state import StateStore

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
USER_AGENT = "GovContractBot research@example.com"   # SEC requires a UA; replace with yours

SUFFIX_PATTERN = re.compile(
    r"\b(inc|incorporated|corp|corporation|co|company|llc|l\.l\.c|"
    r"ltd|limited|lp|llp|plc|holdings|group|the|and|&)\b\.?",
    re.IGNORECASE,
)
PUNCT_PATTERN = re.compile(r"[^\w\s]")


def clean_company_name(name: str) -> str:
    """Lowercase, strip punctuation, drop common corporate suffixes."""
    name = name.lower()
    name = PUNCT_PATTERN.sub(" ", name)
    name = SUFFIX_PATTERN.sub("", name)
    return re.sub(r"\s+", " ", name).strip()


class TickerResolver:
    def __init__(self, state: StateStore, confidence_threshold: int = 88):
        self.state = state
        self.threshold = confidence_threshold
        self._sec_index: dict[str, str] | None = None

    def _load_sec_index(self) -> dict[str, str]:
        """Fetch SEC company-ticker map once per process; key=cleaned title, val=ticker."""
        if self._sec_index is not None:
            return self._sec_index

        resp = httpx.get(SEC_TICKERS_URL, headers={"User-Agent": USER_AGENT}, timeout=30.0)
        resp.raise_for_status()
        raw = resp.json()  # {"0": {"cik_str":..., "ticker":..., "title":...}, ...}

        index: dict[str, str] = {}
        for entry in raw.values():
            clean = clean_company_name(entry["title"])
            if clean:
                index[clean] = entry["ticker"]
        self._sec_index = index
        return index

    def resolve(self, recipient_name: str) -> str | None:
        """Return ticker symbol or None if not confidently a public company."""
        clean = clean_company_name(recipient_name)
        if not clean:
            return None

        cache_hit, cached = self.state.lookup_ticker(clean)
        if cache_hit:
            return cached

        index = self._load_sec_index()
        match = process.extractOne(clean, index.keys(), scorer=fuzz.token_sort_ratio)
        if match and match[1] >= self.threshold:
            ticker = index[match[0]]
            self.state.cache_ticker(clean, ticker)
            return ticker

        self.state.cache_ticker(clean, None)   # negative cache
        return None
