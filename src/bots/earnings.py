"""Earnings calendar and post-earnings reaction tracker."""
from dataclasses import dataclass
from datetime import datetime, timedelta, date

import pandas as pd
import yfinance as yf


@dataclass
class EarningsPreview:
    ticker: str
    earnings_date: str
    eps_estimate: float | None
    revenue_estimate: float | None
    last_4_beats: int
    last_4_misses: int


@dataclass
class EarningsReaction:
    ticker: str
    earnings_date: str
    eps_estimate: float | None
    eps_actual: float | None
    eps_surprise_pct: float | None
    price_before: float | None
    price_after: float | None
    pct_change: float | None


def _safe_float(x) -> float | None:
    try:
        if x is None or pd.isna(x):
            return None
        return float(x)
    except (TypeError, ValueError):
        return None


def find_upcoming_earnings(state, company, lookahead_days: int = 1) -> EarningsPreview | None:
    try:
        tkr = yf.Ticker(company.ticker)
        cal = tkr.calendar
    except Exception:
        return None

    earnings_date = None
    if isinstance(cal, dict):
        ed = cal.get("Earnings Date")
        if ed:
            earnings_date = ed[0] if isinstance(ed, list) else ed
    elif isinstance(cal, pd.DataFrame) and not cal.empty:
        try:
            earnings_date = cal.iloc[0, 0]
        except Exception:
            pass

    if earnings_date is None:
        return None

    if isinstance(earnings_date, datetime):
        earnings_date = earnings_date.date()
    elif isinstance(earnings_date, str):
        try:
            earnings_date = datetime.fromisoformat(earnings_date[:10]).date()
        except ValueError:
            return None

    today = date.today()
    if earnings_date < today or earnings_date > today + timedelta(days=lookahead_days):
        return None

    date_str = earnings_date.isoformat()
    if state.is_earnings_alerted(company.ticker, date_str, "preview"):
        return None

    last_4_beats = 0
    last_4_misses = 0
    try:
        history = tkr.earnings_history
        if isinstance(history, pd.DataFrame) and not history.empty:
            for _, row in history.tail(4).iterrows():
                surprise = _safe_float(row.get("surprisePercent"))
                if surprise is not None:
                    if surprise > 0:
                        last_4_beats += 1
                    elif surprise < 0:
                        last_4_misses += 1
    except Exception:
        pass

    eps_estimate = None
    revenue_estimate = None
    if isinstance(cal, dict):
        eps_estimate = _safe_float(cal.get("Earnings Average"))
        revenue_estimate = _safe_float(cal.get("Revenue Average"))

    return EarningsPreview(
        ticker=company.ticker,
        earnings_date=date_str,
        eps_estimate=eps_estimate,
        revenue_estimate=revenue_estimate,
        last_4_beats=last_4_beats,
        last_4_misses=last_4_misses,
    )


def find_earnings_reactions(state, company) -> EarningsReaction | None:
    try:
        tkr = yf.Ticker(company.ticker)
        history = tkr.earnings_history
    except Exception:
        return None

    if not isinstance(history, pd.DataFrame) or history.empty:
        return None

    last = history.tail(1).iloc[0]
    earnings_date_raw = last.name if hasattr(last, "name") else None
    if earnings_date_raw is None:
        return None

    try:
        if isinstance(earnings_date_raw, pd.Timestamp):
            earnings_date = earnings_date_raw.date()
        else:
            earnings_date = pd.Timestamp(earnings_date_raw).date()
    except Exception:
        return None

    today = date.today()
    if (today - earnings_date).days > 2 or earnings_date > today:
        return None

    date_str = earnings_date.isoformat()
    if state.is_earnings_alerted(company.ticker, date_str, "reaction"):
        return None

    eps_estimate = _safe_float(last.get("epsEstimate"))
    eps_actual = _safe_float(last.get("epsActual"))
    surprise_pct = _safe_float(last.get("surprisePercent"))

    price_before = None
    price_after = None
    pct_change = None
    try:
        prices = tkr.history(period="10d", interval="1d")
        if not prices.empty:
            prices.index = prices.index.tz_localize(None) if prices.index.tz else prices.index
            before_mask = prices.index.date < earnings_date
            after_mask = prices.index.date >= earnings_date
            if before_mask.any() and after_mask.any():
                price_before = float(prices.loc[before_mask, "Close"].iloc[-1])
                price_after = float(prices.loc[after_mask, "Close"].iloc[-1])
                pct_change = ((price_after / price_before) - 1) * 100
    except Exception:
        pass

    return EarningsReaction(
        ticker=company.ticker,
        earnings_date=date_str,
        eps_estimate=eps_estimate,
        eps_actual=eps_actual,
        eps_surprise_pct=surprise_pct,
        price_before=price_before,
        price_after=price_after,
        pct_change=pct_change,
    )
