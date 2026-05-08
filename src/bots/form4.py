"""Form 4 insider trading tracker."""
import re
from dataclasses import dataclass
from xml.etree import ElementTree as ET


@dataclass
class InsiderTransaction:
    ticker: str
    accession: str
    filing_date: str
    insider_name: str
    insider_role: str
    is_officer: bool
    is_director: bool
    is_ten_percent_owner: bool
    transaction_code: str
    shares: float
    price: float
    total_value: float
    filing_url: str


C_SUITE_PATTERNS = [
    r"\bchief executive\b", r"\bceo\b",
    r"\bchief financial\b", r"\bcfo\b",
    r"\bchief operating\b", r"\bcoo\b",
    r"\bpresident\b", r"\bchairman\b", r"\bchair\b",
]


def _is_c_suite(role: str) -> bool:
    role_lower = role.lower()
    return any(re.search(pat, role_lower) for pat in C_SUITE_PATTERNS)


def _parse_form4_xml(xml_text: str) -> list[dict]:
    transactions = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return transactions

    owner = root.find("reportingOwner")
    if owner is None:
        return transactions

    name_el = owner.find("reportingOwnerId/rptOwnerName")
    name = name_el.text if name_el is not None else "Unknown"

    rel = owner.find("reportingOwnerRelationship")
    is_officer = rel.findtext("isOfficer") == "1" if rel is not None else False
    is_director = rel.findtext("isDirector") == "1" if rel is not None else False
    is_ten_pct = rel.findtext("isTenPercentOwner") == "1" if rel is not None else False
    role = rel.findtext("officerTitle") or "" if rel is not None else ""

    for txn in root.findall(".//nonDerivativeTransaction"):
        code_el = txn.find("transactionCoding/transactionCode")
        shares_el = txn.find("transactionAmounts/transactionShares/value")
        price_el = txn.find("transactionAmounts/transactionPricePerShare/value")
        if code_el is None or shares_el is None:
            continue
        try:
            shares = float(shares_el.text)
            price = float(price_el.text) if price_el is not None and price_el.text else 0.0
        except (TypeError, ValueError):
            continue
        transactions.append({
            "insider_name": name,
            "insider_role": role,
            "is_officer": is_officer,
            "is_director": is_director,
            "is_ten_percent_owner": is_ten_pct,
            "transaction_code": code_el.text,
            "shares": shares,
            "price": price,
            "total_value": shares * price,
        })
    return transactions


def _passes_filters(txn: dict, cfg) -> bool:
    code = txn["transaction_code"]
    value = txn["total_value"]
    role = txn["insider_role"]

    if txn["is_ten_percent_owner"] and value >= 500_000:
        return True
    if code == "P":
        if value >= cfg.MIN_INSIDER_PURCHASE_USD:
            return True
        if cfg.NOTIFY_ALL_C_SUITE_PURCHASES and _is_c_suite(role):
            return True
        return False
    if code == "S":
        return value >= cfg.MIN_INSIDER_SALE_USD
    return False


def fetch_insider_transactions(client, state, company, cfg) -> list[InsiderTransaction]:
    filings = client.get_company_filings(company.cik, "4", count=20)
    out = []
    for filing in filings:
        if state.is_filing_seen(filing["accession"]):
            continue
        xml_text = client.fetch_filing_text(
            filing["cik"], filing["accession"], filing["primary_doc"]
        )
        if not xml_text:
            state.mark_filing_seen(filing["accession"], "4")
            continue
        for txn in _parse_form4_xml(xml_text):
            if _passes_filters(txn, cfg):
                out.append(InsiderTransaction(
                    ticker=company.ticker,
                    accession=filing["accession"],
                    filing_date=filing["filing_date"],
                    filing_url=client.get_filing_url(
                        filing["cik"], filing["accession"], filing["primary_doc"]
                    ),
                    **txn,
                ))
        state.mark_filing_seen(filing["accession"], "4")
    return out
