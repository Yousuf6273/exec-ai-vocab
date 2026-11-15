"""Step 2c - merge sources, attach company metadata, tokenise once and count.

Outputs
  data/corpus_documents.csv        one row per cleaned document: metadata + tell-word counts (no text)
  data/corpus_text.csv.gz          the same rows WITH cleaned text (local only - not redistributed)
  data/yearly_passage_counts.csv.gz  word x (series, year): number of 300-word passages containing the word
  cache/doc_term.npz, cache/vocab.json   sparse document-term counts for the analysis step
"""
import json
from collections import Counter, defaultdict

import numpy as np
import pandas as pd
from scipy import sparse

from config import CACHE, CHUNK_WORDS, DATA, TELL_FAMILIES, TELL_FORMS, quarter_of, tokenize

REGION = {}
for _reg, _states in {
    "US Northeast": "CT ME MA NH RI VT NJ NY PA",
    "US Midwest": "IL IN MI OH WI IA KS MN MO NE ND SD",
    "US South": "DE FL GA MD NC SC VA DC WV AL KY MS TN AR LA OK TX",
    "US West": "AZ CO ID MT NV NM UT WY AK CA HI OR WA",
}.items():
    for _s in _states.split():
        REGION[_s] = _reg


def series_of(source, text_type):
    """Analysis series: vendor-consistent groups that are never mixed in a time series."""
    if source == "sp500_turns":
        return text_type                                   # scripted / spontaneous (main)
    if source.startswith("fool"):
        return f"{text_type}_ext"                          # Motley Fool extension
    return text_type                                       # written_quote / written_body


def load_docs():
    parts = [pd.read_parquet(CACHE / "docs_transcripts.parquet")]
    if (CACHE / "docs_edgar.parquet").exists():
        parts.append(pd.read_parquet(CACHE / "docs_edgar.parquet"))
    d = pd.concat(parts, ignore_index=True)
    d = d[d["speaker_role"] != "IR"].reset_index(drop=True)     # investor-relations hosts are not senior executives
    d["date"] = pd.to_datetime(d["date"])
    d = d[d["date"] >= "2017-01-01"].reset_index(drop=True)
    d["quarter"] = d["date"].map(quarter_of)
    d["year"] = d["date"].dt.year
    d["series"] = [series_of(s, t) for s, t in zip(d["source"], d["text_type"])]
    meta_path = DATA / "edgar_company_meta.csv"
    if meta_path.exists():
        m = pd.read_csv(meta_path)[["cik", "sic", "sic_desc", "hq_state", "public_float_usd"]]
        d = d.merge(m, on="cik", how="left")
        firms = d.drop_duplicates("cik")[["cik", "public_float_usd"]].dropna()
        firms["size_bucket"] = pd.qcut(firms["public_float_usd"], 3, labels=["Smaller third", "Middle third", "Largest third"])
        d = d.merge(firms[["cik", "size_bucket"]], on="cik", how="left")
        d["region"] = d["hq_state"].map(REGION)
        d.loc[d["hq_state"].notna() & d["region"].isna(), "region"] = "Non-US HQ"
    else:
        for c in ("sic", "sic_desc", "hq_state", "public_float_usd", "size_bucket", "region"):
            d[c] = np.nan
    # ~18% of 2025 calls in the main source are transcribed verbatim ("gonna", numbers spelled out).
    # Flag those calls so vocabulary-wide analyses can exclude them.
    slang = d["text"].str.count(r"\b(?:gonna|kinda|gotta|wanna)\b")
    nums = d["text"].str.count(r"\b(?:twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)\b")
    per_call = pd.DataFrame({"k": d["source"] + "|" + d["call_id"], "s": slang, "n": nums}).groupby("k").sum()
    verb = set(per_call.index[(per_call["s"] >= 3) | (per_call["n"] >= 3)])
    d["verbatim_style"] = (d["source"] + "|" + d["call_id"]).isin(verb)
    d["doc_id"] = np.arange(len(d))
    return d


if __name__ == "__main__":
    d = load_docs()
    print(len(d), "documents;", d["n_words"].sum(), "words")
    fams = list(TELL_FAMILIES)
    vocab, rows, cols, vals = {}, [], [], []
    tell = np.zeros((len(d), len(fams)), dtype=np.int32)
    n_tok = np.zeros(len(d), dtype=np.int64)
    n_chunks = np.zeros(len(d), dtype=np.int32)
    n_chunks_tell = np.zeros(len(d), dtype=np.int32)
    first1000_tell = np.full(len(d), -1, dtype=np.int8)
    passage_df = defaultdict(Counter)                    # (series, year) -> word -> passages containing it
    passage_n = Counter()
    fam_idx = {f: i for i, f in enumerate(fams)}
    # externally defined marker list: the "style" excess words published by Kobak et al. (2024)
    kob = pd.read_csv(CACHE / "kobak_excess_words.csv", index_col=0)
    kob_style = sorted(set(kob.loc[kob["type"] == "style", "word"]))
    kob_id = {w: k for k, w in enumerate(kob_style)}
    ch_doc, ch_marks = [], []
    tell_forms = set(TELL_FORMS)

    for i, (text, series, year, verbatim) in enumerate(zip(d["text"], d["series"], d["year"], d["verbatim_style"])):
        toks = tokenize(text)
        n_tok[i] = len(toks)
        cnt = Counter(toks)
        for w, c in cnt.items():
            j = vocab.setdefault(w, len(vocab))
            rows.append(i); cols.append(j); vals.append(c)
            if w in tell_forms:
                tell[i, fam_idx[TELL_FORMS[w]]] += c
        if len(toks) >= 1000:
            first1000_tell[i] = int(any(t in tell_forms for t in toks[:1000]))
        key = (series, year)
        for s in range(0, len(toks) - CHUNK_WORDS + 1, CHUNK_WORDS):   # full 300-word passages only
            chunk = set(toks[s:s + CHUNK_WORDS])
            if not verbatim:                               # vocabulary-wide counts exclude verbatim-style calls
                passage_df[key].update(chunk)
                passage_n[key] += 1
            n_chunks[i] += 1
            if chunk & tell_forms:
                n_chunks_tell[i] += 1
            ch_doc.append(i)
            ch_marks.append(sorted(kob_id[w] for w in chunk if w in kob_id))
        if i % 20000 == 0:
            print("tokenised", i, flush=True)

    d["n_tokens"] = n_tok
    for f in fams:
        d[f"tell_{f}"] = tell[:, fam_idx[f]]
    d["n_tell"] = tell.sum(1)
    d["n_passages"] = n_chunks
    d["n_passages_with_tell"] = n_chunks_tell
    d["first1000_has_tell"] = first1000_tell

    pd.DataFrame({"doc_id": ch_doc, "marks": ch_marks}).to_parquet(CACHE / "passage_marks.parquet", index=False)
    json.dump(kob_style, open(CACHE / "kobak_style_words.json", "w"))

    # document-term matrix, dropping very rare words
    X = sparse.csr_matrix((vals, (rows, cols)), shape=(len(d), len(vocab)), dtype=np.int32)
    words = np.array(sorted(vocab, key=vocab.get))
    keep = np.asarray((X > 0).sum(0)).ravel() >= 20
    X, words = X[:, keep], words[keep]
    sparse.save_npz(CACHE / "doc_term.npz", X)
    json.dump(words.tolist(), open(CACHE / "vocab.json", "w"))
    print("doc-term matrix", X.shape, X.nnz)

    # yearly passage-occurrence counts (the Kobak-style matrix); last row = number of passages
    keys = sorted(passage_n)
    allw = sorted({w for k in keys for w, c in passage_df[k].items() if c >= 3 and len(w) >= 4 and w.isalpha()})
    tab = pd.DataFrame({f"{s}|{y}": [passage_df[(s, y)].get(w, 0) for w in allw] for s, y in keys}, index=allw)
    tab.loc["__TOTAL_PASSAGES__"] = [passage_n[k] for k in keys]
    tab.index.name = "word"
    tab.to_csv(DATA / "yearly_passage_counts.csv.gz")
    print("passage matrix", tab.shape)

    meta_cols = [c for c in d.columns if c != "text"]
    d[meta_cols].to_parquet(CACHE / "docs_features.parquet", index=False)
    pub = d[meta_cols].drop(columns=["n_words_raw", "sic_desc"], errors="ignore")
    pub.to_csv(DATA / "corpus_documents.csv", index=False)
    d[["doc_id", "source", "call_id", "symbol", "date", "text_type", "speaker_role", "n_words", "text"]].to_csv(
        DATA / "corpus_text.csv.gz", index=False)
    # SEC press releases are public filings, so their cleaned text is published
    d.loc[d["source"] == "edgar_8k", ["doc_id", "call_id", "symbol", "date", "text_type", "speaker_role", "n_words", "text"]
          ].to_csv(DATA / "corpus_text_press_releases.csv.gz", index=False)
    print(d.groupby("series").agg(docs=("doc_id", "size"), words=("n_tokens", "sum"), firms=("cik", "nunique"),
                                  first=("date", "min"), last=("date", "max")).to_string())
