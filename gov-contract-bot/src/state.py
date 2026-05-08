"""SQLite-backed state store for seen awards and ticker resolution cache."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path


class StateStore:
    def __init__(self, db_path: str):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self._init_schema()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS seen_awards (
                    award_id TEXT PRIMARY KEY,
                    seen_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ticker_cache (
                    company_name_clean TEXT PRIMARY KEY,
                    ticker             TEXT,           -- empty string = known-not-public
                    resolved_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

    # ---- seen-awards API ------------------------------------------------
    def is_seen(self, award_id: str) -> bool:
        with self._conn() as conn:
            cur = conn.execute(
                "SELECT 1 FROM seen_awards WHERE award_id = ?", (award_id,)
            )
            return cur.fetchone() is not None

    def mark_seen(self, award_id: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO seen_awards (award_id) VALUES (?)",
                (award_id,),
            )

    # ---- ticker-cache API -----------------------------------------------
    def lookup_ticker(self, name_clean: str) -> tuple[bool, str | None]:
        """
        Returns (cache_hit, ticker_or_None).
          (False, None)  -> not in cache, must resolve
          (True,  None)  -> cached as 'not public'
          (True,  'NOC') -> cached ticker
        """
        with self._conn() as conn:
            cur = conn.execute(
                "SELECT ticker FROM ticker_cache WHERE company_name_clean = ?",
                (name_clean,),
            )
            row = cur.fetchone()
            if row is None:
                return False, None
            return True, (row[0] or None)

    def cache_ticker(self, name_clean: str, ticker: str | None) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO ticker_cache (company_name_clean, ticker) "
                "VALUES (?, ?)",
                (name_clean, ticker or ""),
            )
