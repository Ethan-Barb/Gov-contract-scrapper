"""Government contracts bot - SAM.gov polling + ticker resolution + volatility."""
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterator

import httpx
import pandas as pd
import yfinance as yf
from rapidfuzz import process, fuzz

SAM_BASE = "https://api.sam.gov/opportunities/v2/search"
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"

SUFFIX_PATTERN = re.compile(
    r"\b(inc|incorporated|corp|corporation|co|company|llc|l\.l\.c|"
    r"ltd|limited|lp|llp|plc|holdings|group|the|and|&)\b\.?",
    re.IGNORECASE,
)
PUNCT_PATTERN = re.compile(r"[^\w\s]")


def clean_company_name(name: str) -> str:
    name = name.lower()
    name = PUNCT_PATTERN.sub(" ", name)
    name = SUFFIX_PATTERN.sub("", name)
    return re.sub(r"\s+", " ", name).strip()


# ---------- Ticker resolution ----------
class TickerResolver:
    def __init__(self, state, threshold: int, sec_user_agent: str):
        self.state = state
        self.threshold = threshold
        self.user_agent = sec_user_agent
        self._sec_index = None

    def _load_index(self) -> dict:
        if self._sec_index is not None:
            return self._sec_index
        resp = httpx.get(SEC_TICKERS_URL, headers={"User-Agent": self.user_agent}, timeout=30.0)
        resp.raise_for_status()
        raw = resp.json()
        index = {}
        for entry in raw.values():
            clean = clean_company_name(entry["title"])
            if clean:
                index[clean] = entry["ticker"]
        self._sec_index = index
        return index

    def resolve(self, recipient_name: str) -> str | None:
        clean = clean_company_name(recipient_name)
        if not clean:
            return None
        cache_hit, cached = self.state.lookup_ticker(clean)
        if cache_hit:
            return cached
        index = self._load_index()
        match = process.extractOne(clean, index.keys(), scorer=fuzz.token_sort_ratio)
        if match and match[1] >= self.threshold:
            ticker = index[match[0]]
            self.state.cache_ticker(clean, ticker)
            return ticker
        self.state.cache_ticker(clean, None)
        return None


# ---------- Volatility ----------
@dataclass
class VolatilityReading:
    current_range: float
    atr_14: float
    ratio: float
    interpretation: str


def calculate_atr(ticker: str, period_days: int = 30) -> VolatilityReading | None:
    try:
        data = yf.Ticker(ticker).history(period=f"{period_days}d", interval="1d")
    except Exception:
        return None
    if data is None or len(data) < 15:
        return None
    high = data["High"]
    low = data["Low"]
    close = data["Close"]
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr_14 = tr.rolling(window=14).mean().iloc[-2]
    current_range = high.iloc[-1] - low.iloc[-1]
    if pd.isna(atr_14) or atr_14 == 0:
        return None
    ratio = float(current_range) / float(atr_14)
    if ratio > 1.5:
        interp = "elevated"
    elif ratio < 0.6:
        interp = "compressed"
    else:
        interp = "normal"
    return VolatilityReading(
        current_range=round(float(current_range), 2),
        atr_14=round(float(atr_14), 2),
        ratio=round(ratio, 2),
        interpretation=interp,
    )


# ---------- SAM client ----------
class SAMClient:
    def __init__(self, api_key: str, min_amount: float, naics_codes: list[str]):
        self.api_key = api_key
        self.min_amount = min_amount
        self.naics_codes = naics_codes

    def fetch_recent_awards(self, lookback_days: int = 2) -> Iterator[dict]:
        posted_from = (datetime.utcnow() - timedelta(days=lookback_days)).strftime("%m/%d/%Y")
        posted_to = datetime.utcnow().strftime("%m/%d/%Y")
        naics_param = ",".join(self.naics_codes)

        offset = 0
        limit = 1000
        while True:
            params = {
                "api_key": self.api_key,
                "postedFrom": posted_from,
                "postedTo": posted_to,
                "ncode": naics_param,
                "ptype": "a",
                "limit": limit,
                "offset": offset,
            }
            resp = httpx.get(SAM_BASE, params=params, timeout=30.0)
            resp.raise_for_status()
            data = resp.json()
            opps = data.get("opportunitiesData", []) or []
            if not opps:
                break
            for opp in opps:
                parsed = self._parse(opp)
                if parsed and parsed["amount"] >= self.min_amount:
                    yield parsed
            if len(opps) < limit:
                break
            offset += limit

    @staticmethod
    def _parse(opp: dict) -> dict | None:
        award = opp.get("award") or {}
        amount_raw = award.get("amount")
        recipient = (award.get("awardee") or {}).get("name")
        if not amount_raw or not recipient:
            return None
        try:
            amount = float(amount_raw)
        except (TypeError, ValueError):
            return None
        return {
            "award_id":    opp.get("noticeId"),
            "title":       opp.get("title", "") or "",
            "description": opp.get("description", "") or "",
            "recipient":   recipient,
            "amount":      amount,
            "naics":       opp.get("naicsCode", "") or "",
            "posted_date": opp.get("postedDate", "") or "",
            "ui_link":     opp.get("uiLink", "") or "",
        }
