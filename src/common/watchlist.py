"""Watchlist loader - tickers + CIKs to monitor."""
import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass
class WatchedCompany:
    ticker: str
    cik: str
    priority: str


def load_watchlist(path: str) -> list[WatchedCompany]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Watchlist not found at {path}")

    companies = []
    with p.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            companies.append(WatchedCompany(
                ticker=row["ticker"].strip().upper(),
                cik=row["cik"].strip().zfill(10),
                priority=row.get("priority", "medium").strip().lower(),
            ))
    return companies
