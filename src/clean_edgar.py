"""Step 2b - turn SEC earnings press releases (8-K exhibit 99.1) into clean written documents.

Two rows per release:
    text_type written_quote  the quoted statements attributed to a named executive (role CEO/CFO/...)
              written_body   the remaining narrative prose (role 'Company')
Removed: financial tables, safe-harbor / non-GAAP / conference-call / contact / 'About' sections,
headings, bullet fragments and anything that is not running prose.
"""
import os
import re
import signal
import time
import warnings
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

import pandas as pd
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

from clean_transcripts import classify_title, nwords
from config import CACHE, DATA, EDGAR_DIR

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
DOC_DIR = EDGAR_DIR / "docs"
PART_DIR = EDGAR_DIR / "clean_parts"
BATCH, DOC_TIMEOUT_S, MAX_DOC_BYTES = 100, 20, 3_000_000
WORKERS = int(os.environ.get("WORKERS", 8))

BOILER_HEAD = re.compile(
    r"forward[- ]looking|safe harbor|cautionary|non-gaap|use of non|reconciliation|conference call|webcast|"
    r"^about |contacts?\b|investor relations|media relations|basis of presentation|definitions|"
    r"additional information|where to find|important information|notes? to|supplemental|earnings call|"
    r"teleconference|investor contact|media contact|explanatory note|footnotes|financial measures", re.I)
BOILER_PARA = re.compile(
    r"forward[- ]looking|safe harbor|private securities litigation|differ materially|undertakes? no obligation|"
    r"risks and uncertainties|risk factors|form 10-[kq]|non-gaap|not (a|an) (measure|substitute)|reconciliation|"
    r"conference call|webcast|replay|dial[- ]in|www\.|http|@|\(\d{3}\)\s*\d{3}|\d{3}-\d{3}-\d{4}|"
    r"is a (leading|global|world|premier)|headquartered in|for more information|investor relations|"
    r"generally accepted accounting|constant currency (is|basis)|see (the )?(accompanying|attached|table)|"
    r"exhibit 99|pursuant to|securities (and )?exchange (act|commission)|nyse:|nasdaq:|\(nyse|\(nasdaq", re.I)
QUOTE_RE = re.compile(r"[“\"]([^”\"]{40,1500})[”\"]")
SAID_RE = re.compile(r"\b(said|says|stated|commented|added|noted|continued|concluded|remarked|explained)\b", re.I)
NAME_RE = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z]\.)?(?:\s+[A-Z][A-Za-z'’\-]+){1,2})\b")


def html_to_paragraphs(raw):
    if b"<" not in raw[:4000] and b"<" not in raw:
        return [p.strip() for p in re.split(r"\n\s*\n", raw.decode("latin-1")) if p.strip()]
    soup = BeautifulSoup(raw, "lxml")
    for t in soup(["script", "style", "head", "title"]):
        t.decompose()
    # Tables: drop numeric/financial tables, keep layout tables that just wrap prose.
    for tb in soup.find_all("table"):
        if tb.find("table"):
            continue
        txt = tb.get_text(" ", strip=True)
        letters = sum(c.isalpha() for c in txt)
        digits = sum(c.isdigit() for c in txt)
        cells = tb.find_all("td")
        long_cells = [c for c in cells if len(c.get_text(" ", strip=True).split()) >= 40]
        if not long_cells or digits > 0.12 * max(letters, 1):
            tb.decompose()
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for blk in soup.find_all(["p", "div", "td", "li", "h1", "h2", "h3", "h4", "tr"]):
        blk.insert_before("\n\n")
        blk.insert_after("\n\n")
    text = soup.get_text(" ")
    text = text.replace("\xa0", " ").replace("&nbsp;", " ")
    paras = []
    for p in re.split(r"\n\s*\n", text):
        p = re.sub(r"\s+", " ", p).strip()
        if p:
            paras.append(p)
    return paras


def clean_release(raw):
    """Return (quotes: {role: [text]}, body_text, n_raw_words)."""
    paras = html_to_paragraphs(raw)
    n_raw = sum(nwords(p) for p in paras)
    kept, in_boiler = [], False
    for p in paras:
        n = nwords(p)
        is_heading = n <= 14 and not p.rstrip().endswith((".", "”", '"'))
        if is_heading:
            in_boiler = bool(BOILER_HEAD.search(p))
            continue
        if in_boiler or n < 20:
            continue
        letters = sum(c.isalpha() for c in p)
        if sum(c.isdigit() for c in p) > 0.18 * max(letters, 1):   # table debris
            continue
        if BOILER_PARA.search(p) and not QUOTE_RE.search(p):
            continue
        kept.append(p)

    quotes, body = defaultdict(list), []
    surname_role, last_role = {}, None
    for p in kept:
        qs = QUOTE_RE.findall(p)
        if not qs:
            body.append(p)
            continue
        outside = QUOTE_RE.sub(" ", p)
        role = classify_title(outside) if SAID_RE.search(outside) or len(outside) > 15 else None
        names = NAME_RE.findall(outside)
        if role:
            for nm in names:
                surname_role[nm.split()[-1]] = role
        else:
            for w in re.findall(r"[A-Z][A-Za-z'’\-]+", outside):
                if w in surname_role:
                    role = surname_role[w]
                    break
        if role is None:
            role = last_role if (last_role and nwords(outside) < 4) else "Other exec"
        last_role = role
        quotes[role].append(" ".join(qs))
        rest = outside.strip()
        if nwords(rest) >= 25 and not BOILER_PARA.search(rest):
            body.append(rest)
    return {r: " ".join(v) for r, v in quotes.items()}, " ".join(body), n_raw


class _Timeout(Exception):
    pass


def _alarm(signum, frame):
    raise _Timeout()


def process(rec):
    signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(DOC_TIMEOUT_S)                             # a pathological filing must not stall the run
    try:
        raw = (DOC_DIR / rec["doc"]).read_bytes()
        if len(raw) > MAX_DOC_BYTES:                        # multi-MB exhibits are financial supplements, not releases
            return [{"error": "too_large", "accession": rec["accession"]}]
        quotes, body, n_raw = clean_release(raw)
    except _Timeout:
        return [{"error": "timeout", "accession": rec["accession"]}]
    except Exception as e:                                  # noqa: BLE001 - log and move on
        return [{"error": repr(e)[:200], "accession": rec["accession"]}]
    finally:
        signal.alarm(0)
    base = {"source": "edgar_8k", "call_id": rec["accession"], "cik": int(rec["cik"]), "date": rec["filing_date"],
            "n_words_raw": n_raw}
    rows = []
    for role, txt in quotes.items():
        if nwords(txt) >= 25:
            rows.append({**base, "text_type": "written_quote", "speaker_role": role, "n_words": nwords(txt), "text": txt})
    if nwords(body) >= 80:
        rows.append({**base, "text_type": "written_body", "speaker_role": "Company", "n_words": nwords(body), "text": body})
    return rows or [{"error": "no_prose", "accession": rec["accession"]}]


def process_batch(job):
    k, recs = job
    out = PART_DIR / f"part_{k:04d}.parquet"
    if not out.exists():
        rows = [r for rec in recs for r in process(rec)]
        pd.DataFrame(rows).to_parquet(out, index=False)
    return k


if __name__ == "__main__":
    idx = pd.read_csv(EDGAR_DIR / "filing_index.csv")
    idx = idx[idx["doc"].notna()].sort_values("accession").reset_index(drop=True)
    PART_DIR.mkdir(exist_ok=True)
    recs = idx.to_dict("records")
    jobs = [(k, recs[i:i + BATCH]) for k, i in enumerate(range(0, len(recs), BATCH))]
    t0 = time.time()
    with ProcessPoolExecutor(WORKERS) as ex:
        for n, k in enumerate(ex.map(process_batch, jobs)):
            if n % 10 == 0:
                print(f"batch {n}/{len(jobs)}  {time.time() - t0:.0f}s", flush=True)
    df = pd.concat([pd.read_parquet(p) for p in sorted(PART_DIR.glob("part_*.parquet"))], ignore_index=True)
    if "error" in df:
        print("skipped releases:\n" + df["error"].value_counts().to_string())
        df = df[df["error"].isna()].drop(columns=["error", "accession"])
    df["cik"] = df["cik"].astype(int)
    # every item-2.02 release is kept (a few companies file more than one per quarter)
    tx = pd.read_parquet(CACHE / "docs_transcripts.parquet", columns=["cik", "symbol", "company", "sector", "date"])
    comp = tx.sort_values("date").groupby("cik").agg(symbol=("symbol", "last"), company=("company", "last"),
                                                      sector=("sector", "last")).reset_index()
    df = df.merge(comp, on="cik", how="left")
    df.to_parquet(CACHE / "docs_edgar.parquet", index=False)
    print(df.groupby("text_type").agg(docs=("n_words", "size"), words=("n_words", "sum"),
                                      releases=("call_id", "nunique")).to_string())
    print(df.groupby(["text_type", "speaker_role"])["n_words"].agg(["size", "sum"]).to_string())
    print("share of raw words kept:", df.n_words.sum() / df.drop_duplicates("call_id").n_words_raw.sum())
