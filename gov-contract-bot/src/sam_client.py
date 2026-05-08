def fetch_recent_awards(self, lookback_days: int = 2):
    posted_from = (datetime.utcnow() - timedelta(days=lookback_days)).strftime("%m/%d/%Y")
    posted_to = datetime.utcnow().strftime("%m/%d/%Y")

    # Combine all NAICS codes into ONE request
    naics_param = ",".join(self.naics_codes)

    offset = 0
    limit = 1000   # max page size — fewer pagination calls
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
