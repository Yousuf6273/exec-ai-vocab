"""Step 1b - download earnings press releases (8-K item 2.02, exhibit 99.1) from SEC EDGAR.

Universe: every SEC CIK that holds an earnings call in the transcript dataset since 2017.
For each CIK:  submissions JSON -> list of 8-K filings with item 2.02 since START_DATE
               -> filing index page -> EX-99.1 document (HTML) cached to cache/edgar/docs/.
Also pulls company metadata (SIC, state of HQ) and public float (XBRL frames API) for the size split.

SEC fair-access rules are respected: declared User-Agent with contact e-mail, global rate limit
below 10 requests/second, exponential back-off on 429/403/5xx. Everything is cached, so re-runs are free.
"""
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import requests

from config import DATA, EDGAR_DIR, SEC_MAX_RPS, SEC_UA, START_DATE

SUB_DIR = EDGAR_DIR / "submissions"
IDX_DIR = EDGAR_DIR / "index"
DOC_DIR = EDGAR_DIR / "docs"
for d in (SUB_DIR, IDX_DIR, DOC_DIR):
    d.mkdir(parents=True, exist_ok=True)

_session = requests.Session()
_session.headers.update({"User-Agent": SEC_UA, "Accept-Encoding": "gzip, deflate"})
_lock = threading.Lock()
_next_slot = [0.0]


def _throttle():
    with _lock:
        now = time.monotonic()
        wait = _next_slot[0] - now
        _next_slot[0] = max(now, _next_slot[0]) + 1.0 / SEC_MAX_RPS
    if wait > 0:
        time.sleep(wait)


def get(url, binary=False, tries=6):
    for attempt in range(tries):
        _throttle()
        try:
            r = _session.get(url, timeout=40)
        except requests.RequestException:
            time.sleep(2 ** attempt)
            continue
        if r.status_code == 200:
            return r.content if binary else r.text
        if r.status_code == 404:
            return None
        time.sleep(min(60, 3 * 2 ** attempt))   # 429 / 403 / 5xx: back off
    return None


def cached(path, url, binary=False):
    if path.exists():
        return path.read_bytes() if binary else path.read_text(errors="ignore")
    body = get(url, binary=binary)
    if body is None:
        return None
    if binary:
        path.write_bytes(body)
    else:
        path.write_text(body)
    return body


def list_filings(cik):
    """All 8-K / 8-K/A filings with item 2.02 since START_DATE, plus company metadata."""
    cik10 = f"{int(cik):010d}"
    raw = cached(SUB_DIR / f"{cik10}.json", f"https://data.sec.gov/submissions/CIK{cik10}.json")
    if raw is None:
        return None, []
    sub = json.loads(raw)
    meta = {
        "cik": int(cik), "edgar_name": sub.get("name"), "sic": sub.get("sic"),
        "sic_desc": sub.get("sicDescription"),
        "hq_state": (sub.get("addresses", {}).get("business", {}) or {}).get("stateOrCountry"),
        "tickers": ",".join(sub.get("tickers") or []),
    }
    blocks = [sub["filings"]["recent"]]
    for f in sub["filings"].get("files", []):
        if f.get("filingTo", "9999") >= START_DATE:
            extra = cached(SUB_DIR / f["name"], f"https://data.sec.gov/submissions/{f['name']}")
            if extra:
                blocks.append(json.loads(extra))
    rows = []
    for b in blocks:
        for form, date, acc, items in zip(b["form"], b["filingDate"], b["accessionNumber"], b["items"]):
            if form in ("8-K", "8-K/A") and "2.02" in (items or "") and date >= START_DATE:
                rows.append({"cik": int(cik), "filing_date": date, "accession": acc, "form": form})
    return meta, rows


EX_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
HREF = re.compile(r'href="([^"]+)"', re.I)
TAGS = re.compile(r"<[^>]+>")


def find_exhibit(cik, acc):
    """Return (url, filename) of the EX-99.1 exhibit (falls back to the first EX-99*)."""
    nodash = acc.replace("-", "")
    base = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{nodash}/"
    html = cached(IDX_DIR / f"{acc}.htm", base + f"{acc}-index.htm")
    if not html:
        return None
    cands = []
    for row in EX_ROW.findall(html):
        cells = [TAGS.sub("", c).strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S | re.I)]
        if len(cells) < 4:
            continue
        typ = cells[3].upper()
        href = HREF.search(row)
        if not href or not typ.startswith("EX-99"):
            continue
        link = href.group(1).replace("/ix?doc=", "")
        if not link.lower().endswith((".htm", ".html", ".txt")):
            continue
        rank = 0 if typ in ("EX-99.1", "EX-99.01") else 1 if typ == "EX-99" else 2
        cands.append((rank, link))
    if not cands:
        return None
    link = sorted(cands)[0][1]
    return "https://www.sec.gov" + link if link.startswith("/") else base + link


def fetch_one(row):
    acc = row["accession"]
    ext_path = None
    for p in DOC_DIR.glob(f"{acc}.*"):
        ext_path = p
    if ext_path is None:
        url = find_exhibit(row["cik"], acc)
        if not url:
            return {**row, "doc": None, "status": "no_ex99"}
        ext = ".txt" if url.lower().endswith(".txt") else ".htm"
        ext_path = DOC_DIR / f"{acc}{ext}"
        body = cached(ext_path, url, binary=True)
        if body is None:
            return {**row, "doc": None, "status": "fetch_failed"}
    return {**row, "doc": ext_path.name, "status": "ok"}


def fetch_public_float():
    """Aggregate market value held by non-affiliates (10-K cover page), FY2022 -> size proxy."""
    out = {}
    for period in ["CY2022Q2I", "CY2022Q1I", "CY2022Q3I", "CY2022Q4I", "CY2021Q4I", "CY2023Q1I", "CY2023Q2I"]:
        raw = cached(EDGAR_DIR / f"float_{period}.json",
                     f"https://data.sec.gov/api/xbrl/frames/dei/EntityPublicFloat/USD/{period}.json")
        if not raw:
            continue
        for d in json.loads(raw)["data"]:
            out.setdefault(int(d["cik"]), d["val"])   # first period listed wins (mid-2022 preferred)
    return out


if __name__ == "__main__":
    uni = pd.read_csv(DATA / "universe.csv")
    ciks = sorted(uni["cik"].dropna().astype(int).unique())
    print(f"{len(ciks)} CIKs", flush=True)

    metas, filings = [], []
    with ThreadPoolExecutor(16) as ex:
        for i, (meta, rows) in enumerate(ex.map(list_filings, ciks)):
            if meta:
                metas.append(meta)
            filings.extend(rows)
            if i % 100 == 0:
                print("submissions", i, len(filings), flush=True)
    floats = fetch_public_float()
    meta_df = pd.DataFrame(metas)
    meta_df["public_float_usd"] = meta_df["cik"].map(floats)
    meta_df.to_csv(DATA / "edgar_company_meta.csv", index=False)
    print(f"{len(filings)} item-2.02 8-K filings; float found for {meta_df.public_float_usd.notna().sum()} CIKs", flush=True)

    results = []
    with ThreadPoolExecutor(16) as ex:
        for i, res in enumerate(ex.map(fetch_one, filings)):
            results.append(res)
            if i % 500 == 0:
                print("docs", i, flush=True)
    res_df = pd.DataFrame(results)
    res_df.to_csv(EDGAR_DIR / "filing_index.csv", index=False)
    print(res_df["status"].value_counts().to_string())
    sys.exit(0)
