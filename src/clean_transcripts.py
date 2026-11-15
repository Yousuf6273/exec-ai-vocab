"""Step 2a - turn raw earnings-call transcripts into clean executive-speech documents.

One output row = one (call, text_type, speaker_role):
    text_type  scripted     management turns in the prepared-remarks section
               spontaneous  management answers in the live Q&A
    speaker_role CEO / CFO / Chair / Other exec / IR  (IR rows are kept but excluded from analysis)

Main source: zcyeee/sp500-earnings-call-turns (2017 - May 2025).
Extension:   Rogersurf/earnings-call-transcripts (Motley Fool, Feb 2024 - May 2026), parsed here.
Boilerplate (safe-harbor / non-GAAP / housekeeping sentences, operator turns) is removed.
"""
import glob
import re
from collections import Counter, defaultdict

import pandas as pd
import pyarrow.parquet as pq

from config import CACHE, DATA, HF_DIR, START_DATE

# ------------------------------------------------------------------ roles
CEO_RE = re.compile(r"\bC\.?E\.?O\b|chief\s+executive|principal\s+executive", re.I)
CFO_RE = re.compile(r"\bC\.?F\.?O\b|chief\s+financ|principal\s+financial|finance\s+chief", re.I)
IR_RE = re.compile(r"investor\s+relations|\bIR\b|shareholder\s+relations|investor\s+communications", re.I)
CHAIR_RE = re.compile(r"\bchair(man|woman|person)?\b", re.I)
EXEC_HINT = re.compile(r"president|officer|chief|\bEVP\b|\bSVP\b|vice|director|head|treasurer|controller|counsel|"
                       r"founder|\bC[A-Z]O\b|manager|partner", re.I)


def classify_title(title):
    """Map a free-text job title to a role. CEO wins over Chair ('Chairman and CEO' -> CEO)."""
    if not title:
        return None
    ceo, cfo = CEO_RE.search(title), CFO_RE.search(title)
    if ceo and cfo:
        return None                      # two people's titles ran together - ambiguous
    if ceo:
        return "CEO"
    if cfo:
        return "CFO"
    if IR_RE.search(title):
        return "IR"
    if CHAIR_RE.search(title):
        return "Chair"
    if EXEC_HINT.search(title):
        return "Other exec"
    return None


def roles_from_intro(intro, names):
    """Find 'Jane Doe, Chief Financial Officer' / 'our CEO, John Roe' in the opening turns."""
    out = {}
    spans = []
    for n in names:
        last = n.split()[-1]
        for m in re.finditer(re.escape(n) + r"|\b(?:Mr|Ms|Mrs|Dr)\.?\s+" + re.escape(last), intro):
            spans.append((m.start(), m.end(), n))
    spans.sort()
    for k, (s, e, n) in enumerate(spans):
        if n in out:
            continue
        nxt = spans[k + 1][0] if k + 1 < len(spans) else len(intro)
        prev = spans[k - 1][1] if k > 0 else 0
        after = re.split(r"[;.]", intro[e:min(nxt, e + 110)])[0]
        role = classify_title(after)
        if role is None:
            before = re.split(r"[;.]", intro[max(prev, s - 70):s])[-1]
            role = classify_title(before)
        if role:
            out[n] = role
    return out


# ------------------------------------------------------------------ boilerplate
BOILER_RE = re.compile(
    r"forward[- ]looking|safe[- ]harbor|actual results|differ materially|risks and uncertainties|risk factors|"
    r"undertakes? no obligation|no obligation to update|private securities litigation|form 10-[kq]|form 8-k|"
    r"\b10-[KQ]\b|sec filings|filings with the (sec|securities)|non-gaap|reconciliation|gaap financial measures|"
    r"press release|earnings release|webcast|replay|slide presentation|investor relations (section|page|website|portion)|"
    r"our website|being recorded|operator instructions|turn (the|this) (call|conference) (back )?over|"
    r"hand (the|this) (call|it) (back )?over|open (up )?the (call|line|lines|floor) (up )?(for|to) questions|"
    r"with me (on the call |today |this morning |this afternoon )|joining me (on the call |today )|"
    r"welcome to .{0,60}(earnings|conference|quarter)|thank you for joining|thanks for joining|"
    r"next question|first question|good (morning|afternoon|evening),? (everyone|everybody|and)",
    re.I)
SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"“])")
WORD_RE = re.compile(r"[A-Za-z]+")


def strip_boilerplate(text):
    keep = []
    for para in text.split("\n"):
        for sent in SENT_SPLIT.split(para.strip()):
            if sent and not BOILER_RE.search(sent):
                keep.append(sent)
    return " ".join(keep)


def nwords(t):
    return len(WORD_RE.findall(t))


def add_docs(rows, base, buckets, raw_words):
    for (ttype, role), parts in buckets.items():
        raw = " ".join(parts)
        txt = strip_boilerplate(raw)
        n = nwords(txt)
        if n < 50:
            continue
        rows.append({**base, "text_type": ttype, "speaker_role": role, "n_words": n,
                     "n_words_raw": nwords(raw), "text": txt})


# ------------------------------------------------------------------ main source
def clean_main():
    files = sorted(glob.glob(str(HF_DIR / "sp500-earnings-call-turns/data/*.parquet")))
    cols = ["symbol", "fiscal_year", "fiscal_quarter", "date", "ticker_company_name", "sector", "company_check",
            "cik", "cik_name", "flags", "turns"]
    calls = []
    for f in files:
        pf = pq.ParquetFile(f)
        for rg in range(pf.num_row_groups):
            for c in pf.read_row_group(rg, columns=cols).to_pylist():
                if c["date"] < START_DATE or c["flags"] or c["company_check"] == "not_this_company" or c["cik"] is None:
                    continue
                calls.append(c)
    print("calls kept after quality filters:", len(calls))

    # pass 1: per-call role evidence, then a per-(company, person) majority vote across calls
    votes = defaultdict(Counter)
    per_call = []
    for c in calls:
        turns = [t for t in c["turns"] if t["role"] == "management" and t["speaker"]]
        names = sorted({t["speaker"] for t in turns}, key=len, reverse=True)
        direct = {}
        for t in turns:
            r = classify_title(t["affiliation"]) or classify_title(
                t["label"].split(" - ", 1)[1] if t["label"] and " - " in t["label"] else None)
            if r:
                direct.setdefault(t["speaker"], r)
        intro = " ".join(t["text"] for t in c["turns"][:4] if t["section"] == "prepared")[:6000]
        for n, r in roles_from_intro(intro, names).items():
            direct.setdefault(n, r)
        for n, r in direct.items():
            votes[(c["cik"], n)][r] += 1
        per_call.append(direct)
    person_role = {k: v.most_common(1)[0][0] for k, v in votes.items()}

    rows, seen = [], set()
    src_stats = Counter()
    for c, direct in zip(calls, per_call):
        key = (c["cik"], c["date"][:10])
        if key in seen:                      # same call filed under two share-class tickers
            continue
        seen.add(key)
        base = {"source": "sp500_turns", "call_id": f"{int(c['cik'])}_{c['date'][:10]}", "symbol": c["symbol"],
                "cik": int(c["cik"]), "company": c["ticker_company_name"] or c["cik_name"], "sector": c["sector"],
                "date": c["date"][:10]}
        buckets = defaultdict(list)
        for t in c["turns"]:
            if t["role"] != "management" or not t["speaker"] or t["section"] not in ("prepared", "qa"):
                continue
            n = t["speaker"]
            if n in direct:
                role = direct[n]; src_stats["same_call"] += 1
            elif (c["cik"], n) in person_role:
                role = person_role[(c["cik"], n)]; src_stats["other_calls"] += 1
            else:
                role = "Other exec"; src_stats["unresolved"] += 1
            buckets[("scripted" if t["section"] == "prepared" else "spontaneous", role)].append(t["text"])
        add_docs(rows, base, buckets, None)
    print("role evidence per management turn:", dict(src_stats))
    known = defaultdict(dict)
    for (cik, name), role in person_role.items():
        known[int(cik)][name] = role
    return pd.DataFrame(rows), known


# ------------------------------------------------------------------ Motley Fool extension
OLD_TURN = re.compile(r"\n([A-Z][^\n]{1,70})\n--\n([^\n]{1,140})\n\n|\n(Operator)\n")
NEW_TURN = re.compile(r"(?:^|\n)([A-Z][A-Za-z.'’\- ]{1,60}):\n")
PARTICIPANT = re.compile(r"\n([^\n—]{3,120}) — ([^\n]{3,60})\n")


def match_known(name, known):
    """Match a speaker to executives already seen on this company's earlier calls."""
    if name in known:
        return known[name]
    parts = name.replace(".", "").split()
    if len(parts) < 2:
        return None
    for k, role in known.items():
        kp = k.replace(".", "").split()
        if len(kp) >= 2 and kp[-1] == parts[-1] and kp[0][0] == parts[0][0]:
            return role
    return None


def parse_fool(row, known=None):
    """Return {(text_type, role): [texts]} for one Motley Fool transcript (two site layouts)."""
    buckets = defaultdict(list)
    raw = row["transcript"]
    if "Prepared Remarks:" in raw:                      # layout used until mid-2025
        body = raw.split("Prepared Remarks:", 1)[1]
        body = re.split(r"\nCall participants:|\nDuration: ", body)[0]
        qa_at = body.find("Questions & Answers:")
        if qa_at < 0:
            qa_at = body.find("Questions and Answers:")
        ms = list(OLD_TURN.finditer(body))
        for k, m in enumerate(ms):
            end = ms[k + 1].start() if k + 1 < len(ms) else len(body)
            if m.group(3):
                continue
            title = m.group(2)
            if re.search(r"analyst", title, re.I):
                continue
            role = classify_title(title) or "Other exec"
            section = "spontaneous" if (qa_at >= 0 and m.start() > qa_at) else "scripted"
            buckets[(section, role)].append(body[m.end():end].replace("Questions & Answers:", " "))
        return buckets, "old"
    body = row["transcript_clean"] or ""                # layout used from mid-2025: "Name:\ntext"
    people = {}
    head = raw.split("Takeaways", 1)[0] if "Call participants" in raw else ""
    for title, name in PARTICIPANT.findall(head):
        people[name.strip()] = classify_title(title) or "Other exec"
    ms = list(NEW_TURN.finditer(body))
    for m in ms:                                        # fall back on executives known from earlier calls
        nm = m.group(1).strip()
        if nm not in people and known:
            r = match_known(nm, known)
            if r:
                people[nm] = r
    if not people:
        return buckets, "unparsed"
    in_qa, mgmt_words = False, 0
    for k, m in enumerate(ms):
        end = ms[k + 1].start() if k + 1 < len(ms) else len(body)
        name, text = m.group(1).strip(), body[m.end():end]
        if name == "Operator":
            if mgmt_words > 150 and re.search(r"question", text, re.I):
                in_qa = True
            continue
        if name not in people:                          # analysts are not in the participant list
            if mgmt_words > 150:
                in_qa = True
            continue
        mgmt_words += nwords(text)
        buckets[("spontaneous" if in_qa else "scripted", people[name])].append(text)
    return buckets, "new"


def clean_fool(universe, known):
    d = pd.read_parquet(HF_DIR / "earnings-call-transcripts/transcripts_clean.parquet")
    d = d[d["ticker"].isin(universe["symbol"])].drop_duplicates(["ticker", "call_date"])
    sym = universe.set_index("symbol")
    rows, layouts = [], Counter()
    for r in d.to_dict("records"):
        s = sym.loc[r["ticker"]]
        buckets, layout = parse_fool(r, known.get(int(s["cik"])))
        layouts[layout] += 1
        base = {"source": f"fool_{layout}", "call_id": f"{int(s['cik'])}_{r['call_date'][:10]}", "symbol": r["ticker"],
                "cik": int(s["cik"]), "company": s["company"], "sector": s["sector"], "date": r["call_date"][:10]}
        add_docs(rows, base, buckets, None)
    print("Motley Fool layouts:", dict(layouts))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    main, known = clean_main()
    uni = (main.sort_values("date").groupby("symbol").agg(cik=("cik", "last"), company=("company", "last"),
                                                           sector=("sector", "last")).reset_index())
    fool = clean_fool(uni, known)
    out = pd.concat([main, fool], ignore_index=True)
    out.to_parquet(CACHE / "docs_transcripts.parquet", index=False)
    print(out.groupby(["source", "text_type"]).agg(docs=("n_words", "size"), words=("n_words", "sum"),
                                                  calls=("call_id", "nunique")).to_string())
    print(out.groupby("speaker_role")["n_words"].agg(["size", "sum"]).to_string())
    print("boilerplate share removed:", 1 - out.n_words.sum() / out.n_words_raw.sum())
