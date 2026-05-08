"""SAM.gov Opportunities API client (v2) — fetches Award notices."""
import httpx
from datetime import datetime, timedelta
from typing import Iterator

SAM_BASE = "https://api.sam.gov/opportunities/v2/search"


class SAMClient:
    def __init__(self, api_key: str, min_amount: float, naics_codes: list[str]):
        self.api_key = api_key
        self.min_amount = min_amount
        self.naics_codes = naics_codes

    def fetch_recent_awards(self, lookback_days: int = 2) -> Iterator[dict]:
        """Yield parsed award dicts above MIN_AWARD_AMOUNT."""
        posted_from = (datetime.utcnow() - timedelta(days=lookback_days)).strftime("%m/%d/%Y")
        posted_to = datetime.utcnow().strftime("%m/%d/%Y")

        # Combine all NAICS codes into one request to save API calls
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
            opportunities = data.get("opportunitiesData", []) or []
            if not opportunities:
                break

            for opp in opportunities:
                parsed = self._parse_award(opp)
                if parsed and parsed["amount"] >= self.min_amount:
                    yield parsed

            if len(opportunities) < limit:
                break
            offset += limit

    @staticmethod
    def _parse_award(opp: dict) -> dict | None:
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
