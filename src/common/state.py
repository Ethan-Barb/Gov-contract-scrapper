"""Unified SQLite state store. Single DB shared by all bots and the dashboard."""
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime


class StateStore:
    def __init__(self, db_path: str):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self._init_schema()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self):
        with self._conn() as conn:
            # All Telegram alerts ever sent. This is what the dashboard's "Alerts" tab reads.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    sent_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    source       TEXT NOT NULL,         -- 'contract' | 'form4' | '8k' | 'earnings'
                    ticker       TEXT,
                    title        TEXT NOT NULL,
                    body         TEXT NOT NULL,
                    metadata     TEXT,                  -- JSON blob with structured data
                    link         TEXT
                )
            """)

            # Government contract awards
            conn.execute("""
                CREATE TABLE IF NOT EXISTS contracts (
                    award_id      TEXT PRIMARY KEY,
                    posted_date   TEXT,
                    recipient     TEXT NOT NULL,
                    ticker        TEXT,
                    amount        REAL NOT NULL,
                    naics         TEXT,
                    title         TEXT,
                    summary       TEXT,
                    ui_link       TEXT,
                    seen_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # SEC filings (Form 4 and 8-K)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sec_filings (
                    accession_number TEXT PRIMARY KEY,
                    form_type        TEXT NOT NULL,
                    seen_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Insider transactions (Form 4 detail)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS insider_transactions (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    accession_number TEXT,
                    ticker           TEXT NOT NULL,
                    filing_date      TEXT,
                    insider_name     TEXT,
                    insider_role     TEXT,
                    transaction_code TEXT,
                    shares           REAL,
                    price            REAL,
                    total_value      REAL,
                    filing_url       TEXT
                )
            """)

            # 8-K filings (with summary)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS form_8k_filings (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    accession_number TEXT,
                    ticker           TEXT NOT NULL,
                    filing_date      TEXT,
                    items            TEXT,
                    summary          TEXT,
                    filing_url       TEXT
                )
            """)

            # Earnings alerts (dedup tracker)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS earnings_alerts (
                    ticker          TEXT NOT NULL,
                    earnings_date   TEXT NOT NULL,
                    phase           TEXT NOT NULL,
                    sent_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (ticker, earnings_date, phase)
                )
            """)

            # Earnings history (for dashboard charts)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS earnings_history (
                    ticker             TEXT NOT NULL,
                    earnings_date      TEXT NOT NULL,
                    eps_estimate       REAL,
                    eps_actual         REAL,
                    revenue_estimate   REAL,
                    revenue_actual     REAL,
                    price_before       REAL,
                    price_after        REAL,
                    pct_change         REAL,
                    recorded_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (ticker, earnings_date)
                )
            """)

            # Ticker resolution cache (for contract bot)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ticker_cache (
                    company_name_clean TEXT PRIMARY KEY,
                    ticker             TEXT,
                    resolved_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

    # ---------- Alerts (used by all modules) ----------
    def log_alert(self, source: str, ticker: str | None, title: str,
                  body: str, link: str | None = None, metadata: dict | None = None):
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO alerts (source, ticker, title, body, link, metadata) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (source, ticker, title, body, link,
                 json.dumps(metadata) if metadata else None),
            )

    # ---------- Contracts ----------
    def is_contract_seen(self, award_id: str) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM contracts WHERE award_id = ?", (award_id,)
            ).fetchone()
            return row is not None

    def save_contract(self, **kwargs):
        cols = ",".join(kwargs.keys())
        placeholders = ",".join("?" * len(kwargs))
        with self._conn() as conn:
            conn.execute(
                f"INSERT OR REPLACE INTO contracts ({cols}) VALUES ({placeholders})",
                tuple(kwargs.values()),
            )

    # ---------- Ticker cache ----------
    def lookup_ticker(self, name_clean: str) -> tuple[bool, str | None]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT ticker FROM ticker_cache WHERE company_name_clean = ?",
                (name_clean,),
            ).fetchone()
            if row is None:
                return False, None
            return True, (row["ticker"] or None)

    def cache_ticker(self, name_clean: str, ticker: str | None):
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO ticker_cache (company_name_clean, ticker) VALUES (?, ?)",
                (name_clean, ticker or ""),
            )

    # ---------- SEC filings (dedup) ----------
    def is_filing_seen(self, accession: str) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM sec_filings WHERE accession_number = ?", (accession,)
            ).fetchone()
            return row is not None

    def mark_filing_seen(self, accession: str, form_type: str):
        with self._conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO sec_filings (accession_number, form_type) VALUES (?, ?)",
                (accession, form_type),
            )

    # ---------- Insider transactions ----------
    def save_insider_transaction(self, **kwargs):
        cols = ",".join(kwargs.keys())
        placeholders = ",".join("?" * len(kwargs))
        with self._conn() as conn:
            conn.execute(
                f"INSERT INTO insider_transactions ({cols}) VALUES ({placeholders})",
                tuple(kwargs.values()),
            )

    # ---------- 8-K filings ----------
    def save_8k(self, **kwargs):
        cols = ",".join(kwargs.keys())
        placeholders = ",".join("?" * len(kwargs))
        with self._conn() as conn:
            conn.execute(
                f"INSERT INTO form_8k_filings ({cols}) VALUES ({placeholders})",
                tuple(kwargs.values()),
            )

    # ---------- Earnings ----------
    def is_earnings_alerted(self, ticker: str, date: str, phase: str) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM earnings_alerts WHERE ticker=? AND earnings_date=? AND phase=?",
                (ticker, date, phase),
            ).fetchone()
            return row is not None

    def mark_earnings_alerted(self, ticker: str, date: str, phase: str):
        with self._conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO earnings_alerts (ticker, earnings_date, phase) VALUES (?, ?, ?)",
                (ticker, date, phase),
            )

    def record_earnings(self, **kwargs):
        cols = ",".join(kwargs.keys())
        placeholders = ",".join("?" * len(kwargs))
        with self._conn() as conn:
            conn.execute(
                f"INSERT OR REPLACE INTO earnings_history ({cols}) VALUES ({placeholders})",
                tuple(kwargs.values()),
            )
