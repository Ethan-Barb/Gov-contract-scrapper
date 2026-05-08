"""Rate-limited SEC EDGAR HTTP client."""
import time
import httpx


class EdgarClient:
    BASE_URL = "https://www.sec.gov"
    DATA_URL = "https://data.sec.gov"
    MIN_INTERVAL = 0.12

    def __init__(self, user_agent: str):
        if "@" not in user_agent:
            raise ValueError(
                "SEC requires a real contact email in User-Agent. "
                "Set SEC_USER_AGENT like 'YourBot you@example.com'"
            )
        self.headers = {
            "User-Agent": user_agent,
            "Accept-Encoding": "gzip, deflate",
            "Host": "www.sec.gov",
        }
        self._last_request = 0.0

    def _throttle(self):
        elapsed = time.time() - self._last_request
        if elapsed < self.MIN_INTERVAL:
            time.sleep(self.MIN_INTERVAL - elapsed)
        self._last_request = time.time()

    def get(self, url: str, **kwargs) -> httpx.Response:
        self._throttle()
        headers = dict(self.headers)
        if url.startswith(self.DATA_URL):
            headers["Host"] = "data.sec.gov"
        resp = httpx.get(url, headers=headers, timeout=30.0, **kwargs)
        resp.raise_for_status()
        return resp

    def get_company_filings(self, cik: str, form_type: str, count: int = 20) -> list[dict]:
        url = f"{self.DATA_URL}/submissions/CIK{cik}.json"
        try:
            data = self.get(url).json()
        except httpx.HTTPStatusError:
            return []

        recent = data.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        accessions = recent.get("accessionNumber", [])
        dates = recent.get("filingDate", [])
        primary_docs = recent.get("primaryDocument", [])

        results = []
        for i, form in enumerate(forms[:count * 5]):
            if form == form_type:
                results.append({
                    "accession": accessions[i],
                    "filing_date": dates[i],
                    "primary_doc": primary_docs[i],
                    "form_type": form,
                    "cik": cik,
                })
                if len(results) >= count:
                    break
        return results

    def get_filing_url(self, cik: str, accession: str, primary_doc: str) -> str:
        acc_no_dashes = accession.replace("-", "")
        return f"{self.BASE_URL}/Archives/edgar/data/{int(cik)}/{acc_no_dashes}/{primary_doc}"

    def fetch_filing_text(self, cik: str, accession: str, primary_doc: str) -> str:
        url = self.get_filing_url(cik, accession, primary_doc)
        try:
            return self.get(url).text
        except httpx.HTTPStatusError:
            return ""
