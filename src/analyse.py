"""Step 3 - all statistics. Writes tables to results/ and key numbers to results/summary.json.

Every choice here (windows, break dates, word lists, control matching) was fixed in config.py /
this file before the results were examined; nothing is tuned towards finding an effect.
"""
import json
import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import sparse

from config import (CACHE, CONFOUNDED_FAMILIES, DATA, FIRST_POST_Q, PLACEBO_FIRST_POST_Q, ROOT, TELL_FAMILIES,
                    TELL_FORMS)

warnings.filterwarnings("ignore")
RES = ROOT / "results"
RES.mkdir(exist_ok=True)
RNG = np.random.default_rng(20221130)

FAMS = list(TELL_FAMILIES)
CORE = [f for f in FAMS if f not in CONFOUNDED_FAMILIES]
PRE_WIN = ("2021Q1", "2022Q4")          # eight quarters immediately before ChatGPT
POST_WIN = ("2024Q1", "2026Q4")         # 2024 onwards (as far as each series reaches)
SERIES = ["scripted", "spontaneous", "written_quote", "written_body"]
SUMMARY = {}


def qnum(q):                             # '2023Q1' -> integer quarter index
    return int(q[:4]) * 4 + int(q[5]) - 1


def in_win(q, win):
    return (q >= win[0]) & (q <= win[1])


# ------------------------------------------------------------------ regression helpers
def its(y, quarters, first_post, covid_step=False, hac_lags=4):
    """Segmented (interrupted time-series) regression on a quarterly series.
    y_t = a + b*t + c*post_t + d*(t - t0)*post_t + quarter-of-year dummies (+ optional COVID level step)
    Newey-West (HAC) standard errors. Returns level jump, slope change and the average post-period
    gap between the fitted series and the projected pre-trend, with 95% CIs."""
    q = np.array([qnum(x) for x in quarters])
    t = q - q.min()
    t0 = qnum(first_post) - q.min()
    post = (t >= t0).astype(float)
    cols = {"const": np.ones(len(t)), "t": t.astype(float), "post": post, "tpost": (t - t0) * post}
    for s in (1, 2, 3):
        cols[f"s{s}"] = (q % 4 == s).astype(float)
    if covid_step:
        cols["covid"] = (q >= qnum("2020Q2")).astype(float)
    Xd = pd.DataFrame(cols)
    m = sm.OLS(np.asarray(y, float), Xd).fit(cov_type="HAC", cov_kwds={"maxlags": hac_lags})
    k = (t[post == 1] - t0).mean()
    L = np.zeros(len(Xd.columns)); L[list(Xd.columns).index("post")] = 1; L[list(Xd.columns).index("tpost")] = k
    tt = m.t_test(L)
    eff, (lo, hi) = float(tt.effect[0]), tt.conf_int()[0]
    Xc = Xd.copy(); Xc["post"] = 0; Xc["tpost"] = 0
    cf = float((Xc[post == 1] @ m.params).mean())
    ci = m.conf_int()
    return {
        "level_jump": m.params["post"], "level_lo": ci.loc["post", 0], "level_hi": ci.loc["post", 1], "level_p": m.pvalues["post"],
        "slope_change_per_q": m.params["tpost"], "slope_lo": ci.loc["tpost", 0], "slope_hi": ci.loc["tpost", 1],
        "slope_p": m.pvalues["tpost"], "pre_slope_per_q": m.params["t"],
        "avg_post_effect": eff, "avg_lo": float(lo), "avg_hi": float(hi), "avg_p": float(tt.pvalue),
        "counterfactual_post_mean": cf, "avg_post_effect_pct": 100 * eff / cf if cf else np.nan,
        "n_quarters": len(t), "n_post": int(post.sum()),
        "fitted": m.fittedvalues.values, "counterfactual": (Xc @ m.params).values,
    }


def strip(r):
    return {k: (float(v) if isinstance(v, (float, np.floating)) else v) for k, v in r.items()
            if k not in ("fitted", "counterfactual")}


def cluster_boot(tab, stat, n=1000):
    """tab: DataFrame indexed by company, numeric columns. stat: function(column sums) -> float."""
    arr = tab.values
    idx = RNG.integers(0, len(arr), size=(n, len(arr)))
    sums = arr[idx].sum(1)
    vals = np.array([stat(pd.Series(s, index=tab.columns)) for s in sums])
    point = stat(tab.sum())
    return point, float(np.nanpercentile(vals, 2.5)), float(np.nanpercentile(vals, 97.5))


def window_table(df, num, den="n_tokens"):
    """Per-company sums of numerator/denominator in the pre and post windows."""
    pre = df[in_win(df["quarter"], PRE_WIN)].groupby("cik")[[num, den]].sum()
    post = df[in_win(df["quarter"], POST_WIN)].groupby("cik")[[num, den]].sum()
    t = pre.join(post, lsuffix="_pre", rsuffix="_post", how="outer").fillna(0)
    t.columns = ["n0", "w0", "n1", "w1"]
    return t


def ratio_stat(s):
    return np.log((s["n1"] / s["w1"]) / (s["n0"] / s["w0"])) if min(s["n0"], s["n1"], s["w0"], s["w1"]) > 0 else np.nan


def prepost(df, num, den="n_tokens"):
    t = window_table(df, num, den)
    s = t.sum()
    lr, lo, hi = cluster_boot(t, ratio_stat)
    return {"pre_rate": 1e4 * s["n0"] / s["w0"], "post_rate": 1e4 * s["n1"] / s["w1"],
            "pct_change": 100 * (np.exp(lr) - 1), "pct_lo": 100 * (np.exp(lo) - 1), "pct_hi": 100 * (np.exp(hi) - 1),
            "n_firms": int(len(t)), "words_pre": int(s["w0"]), "words_post": int(s["w1"])}


# ------------------------------------------------------------------ load
d = pd.read_parquet(CACHE / "docs_features.parquet")
d["n_core"] = d[[f"tell_{f}" for f in CORE]].sum(1)
X = sparse.load_npz(CACHE / "doc_term.npz").tocsr()
vocab = np.array(json.load(open(CACHE / "vocab.json")))
present = [s for s in SERIES if (d["series"] == s).any()]
print("series present:", present)

corpus_stats = d.groupby("series").agg(documents=("doc_id", "size"), events=("call_id", "nunique"), words=("n_tokens", "sum"),
                                       companies=("cik", "nunique"), first=("date", "min"), last=("date", "max"))
corpus_stats.to_csv(RES / "corpus_stats.csv")
SUMMARY["corpus"] = json.loads(corpus_stats.astype(str).to_json(orient="index"))

# ------------------------------------------------------------------ 1. quarterly tell-word series
# event-level documents: all executives of one call/release pooled, per text type
ev = d.groupby(["series", "call_id", "cik", "quarter"], observed=True).agg(
    n_tokens=("n_tokens", "sum"), n_tell=("n_tell", "sum"), n_core=("n_core", "sum"),
    n_passages=("n_passages", "sum"), n_passages_with_tell=("n_passages_with_tell", "sum"),
    **{f"tell_{f}": (f"tell_{f}", "sum") for f in FAMS}).reset_index()
ev["has_tell"] = (ev["n_tell"] > 0).astype(int)
ev["one"] = 1

rows = []
for (s, q), g in ev.groupby(["series", "quarter"]):
    by = g.groupby("cik")[["n_tell", "n_core", "n_tokens", "has_tell", "one", "n_passages", "n_passages_with_tell"]].sum()
    r = {"series": s, "quarter": q, "events": len(g), "words": int(g["n_tokens"].sum())}
    for name, num, den, scale in [("tell_rate", "n_tell", "n_tokens", 1e4), ("core_rate", "n_core", "n_tokens", 1e4),
                                  ("pct_docs_with_tell", "has_tell", "one", 100),
                                  ("pct_passages_with_tell", "n_passages_with_tell", "n_passages", 100)]:
        p, lo, hi = cluster_boot(by[[num, den]], lambda x, a=num, b=den: x[a] / x[b] if x[b] else np.nan, n=300)
        r[name], r[name + "_lo"], r[name + "_hi"] = scale * p, scale * lo, scale * hi
    for f in FAMS:
        r[f"rate_{f}"] = 1e4 * g[f"tell_{f}"].sum() / g["n_tokens"].sum()
    rows.append(r)
qs = pd.DataFrame(rows).sort_values(["series", "quarter"])
qs = qs[qs["events"] >= 30]                     # drop thin edge quarters
qs.to_csv(RES / "quarterly_series.csv", index=False)

# equal-weighted family index: mean over families of log(rate / pre-2023 mean rate)
def family_index(sub, fams):
    out = []
    for f in fams:
        base = sub.loc[sub["quarter"] < FIRST_POST_Q, f"rate_{f}"].mean()
        if base > 0:
            out.append(np.log((sub[f"rate_{f}"] + 0.25 * base) / (1.25 * base)))   # smoothed log-ratio
    return np.mean(out, axis=0)

# ------------------------------------------------------------------ 2. segmented regression (+ placebo)
reg_rows, fits = [], {}
for s in qs["series"].unique():
    sub = qs[qs["series"] == s].reset_index(drop=True)
    if sub["quarter"].min() > "2019Q4":
        continue                                 # extension series have no pre-period
    sub["family_index"] = family_index(sub, FAMS)
    for metric in ["tell_rate", "core_rate", "pct_docs_with_tell", "pct_passages_with_tell", "family_index"]:
        for spec, kw in [("main", {}), ("covid_step", {"covid_step": True})]:
            r = its(sub[metric], sub["quarter"], FIRST_POST_Q, **kw)
            fits[(s, metric, spec)] = (sub["quarter"].tolist(), r["fitted"], r["counterfactual"])
            reg_rows.append({"series": s, "metric": metric, "spec": spec, "break": FIRST_POST_Q, **strip(r)})
        pl = sub[sub["quarter"] < FIRST_POST_Q]  # placebo: pre-ChatGPT data only, fake break after Nov 2020
        r = its(pl[metric], pl["quarter"], PLACEBO_FIRST_POST_Q)
        reg_rows.append({"series": s, "metric": metric, "spec": "placebo_nov2020", "break": PLACEBO_FIRST_POST_Q, **strip(r)})
reg = pd.DataFrame(reg_rows)
reg.to_csv(RES / "segmented_regression.csv", index=False)
pd.DataFrame([{"series": k[0], "metric": k[1], "spec": k[2], "quarter": q, "fitted": f, "counterfactual": c}
              for k, (qq, ff, cc) in fits.items() for q, f, c in zip(qq, ff, cc)]).to_csv(RES / "its_fits.csv", index=False)

# scripted-minus-spontaneous difference series (same calls) -> difference-in-differences
piv = qs[qs["series"].isin(["scripted", "spontaneous"])].pivot(index="quarter", columns="series")
did_rows = []
for metric in ["tell_rate", "core_rate", "pct_passages_with_tell"]:
    diff = (piv[metric]["scripted"] - piv[metric]["spontaneous"]).dropna()
    for spec, kw, data in [("main", {}, diff), ("covid_step", {"covid_step": True}, diff),
                           ("placebo_nov2020", {}, diff[diff.index < FIRST_POST_Q])]:
        r = its(data.values, data.index, PLACEBO_FIRST_POST_Q if spec.startswith("placebo") else FIRST_POST_Q, **kw)
        did_rows.append({"metric": metric + "_scripted_minus_spontaneous", "spec": spec, **strip(r)})
pd.DataFrame(did_rows).to_csv(RES / "did_regression.csv", index=False)

# company fixed-effects panel on scripted calls (robustness for composition changes)
def fe_panel(df, ycol, first_post, covid_step=False):
    df = df[df["n_tokens"] >= 300].copy()
    q = df["quarter"].map(qnum).values
    t = q - q.min(); t0 = qnum(first_post) - q.min(); post = (t >= t0).astype(float)
    Z = pd.DataFrame({"t": t.astype(float), "post": post, "tpost": (t - t0) * post,
                      "s1": (q % 4 == 1) * 1.0, "s2": (q % 4 == 2) * 1.0, "s3": (q % 4 == 3) * 1.0}, index=df.index)
    if covid_step:
        Z["covid"] = (q >= qnum("2020Q2")) * 1.0
    y = df[ycol].astype(float)
    w = df["n_tokens"].astype(float)
    g = df["cik"]
    wm = lambda v: (v * w).groupby(g).transform("sum") / w.groupby(g).transform("sum")
    yd = y - wm(y)
    Zd = Z.apply(lambda c: c - wm(c))
    m = sm.WLS(yd, Zd, weights=w).fit(cov_type="cluster", cov_kwds={"groups": g.values})
    k = (t[post == 1] - t0).mean()
    L = np.zeros(len(Zd.columns)); L[1] = 1; L[2] = k
    tt = m.t_test(L)
    return {"level_jump": m.params["post"], "level_p": m.pvalues["post"], "slope_change_per_q": m.params["tpost"],
            "slope_p": m.pvalues["tpost"], "avg_post_effect": float(tt.effect[0]), "avg_lo": float(tt.conf_int()[0][0]),
            "avg_hi": float(tt.conf_int()[0][1]), "avg_p": float(tt.pvalue), "n_obs": int(len(df)), "n_firms": int(g.nunique())}

fe_rows = []
for s in present:
    e = ev[ev["series"] == s].copy()
    e["tell_rate"] = 1e4 * e["n_tell"] / e["n_tokens"]; e["core_rate"] = 1e4 * e["n_core"] / e["n_tokens"]
    for metric in ["tell_rate", "core_rate"]:
        fe_rows.append({"series": s, "metric": metric, "spec": "main", **fe_panel(e, metric, FIRST_POST_Q)})
        fe_rows.append({"series": s, "metric": metric, "spec": "covid_step", **fe_panel(e, metric, FIRST_POST_Q, True)})
        fe_rows.append({"series": s, "metric": metric, "spec": "placebo_nov2020",
                        **fe_panel(e[e["quarter"] < FIRST_POST_Q], metric, PLACEBO_FIRST_POST_Q)})
both = ev[ev["series"].isin(["scripted", "spontaneous"]) & (ev["n_tokens"] >= 300)].copy()
both["tell_rate"] = 1e4 * both["n_tell"] / both["n_tokens"]; both["core_rate"] = 1e4 * both["n_core"] / both["n_tokens"]
wide = both.pivot_table(index=["call_id", "cik", "quarter"], columns="series", values=["tell_rate", "core_rate", "n_tokens"]).dropna()
for metric in ["tell_rate", "core_rate"]:
    dd = pd.DataFrame({"y": wide[metric]["scripted"] - wide[metric]["spontaneous"],
                       "n_tokens": wide["n_tokens"].min(axis=1)}).reset_index()
    fe_rows.append({"series": "scripted_minus_spontaneous", "metric": metric, "spec": "main", **fe_panel(dd, "y", FIRST_POST_Q)})
    fe_rows.append({"series": "scripted_minus_spontaneous", "metric": metric, "spec": "covid_step", **fe_panel(dd, "y", FIRST_POST_Q, True)})
    fe_rows.append({"series": "scripted_minus_spontaneous", "metric": metric, "spec": "placebo_nov2020",
                    **fe_panel(dd[dd["quarter"] < FIRST_POST_Q], "y", PLACEBO_FIRST_POST_Q)})
pd.DataFrame(fe_rows).to_csv(RES / "panel_fixed_effects.csv", index=False)

# ------------------------------------------------------------------ 3. simple pre/post windows, by family
pp_rows = []
for s in present:
    sub = d[d["series"] == s]
    for name, col in [("ALL 18 tell words", "n_tell"), ("CORE 13 (ex. confounded)", "n_core")] + [(f, f"tell_{f}") for f in FAMS]:
        t = window_table(sub, col)
        if t[["n0", "n1"]].sum().min() < 5:
            tot = t.sum()
            pp_rows.append({"series": s, "word": name, "pre_rate": 1e4 * tot.n0 / tot.w0, "post_rate": 1e4 * tot.n1 / tot.w1,
                            "pre_count": int(tot.n0), "post_count": int(tot.n1)})
            continue
        r = prepost(sub, col)
        pp_rows.append({"series": s, "word": name, **r, "pre_count": int(t.n0.sum()), "post_count": int(t.n1.sum())})
pp = pd.DataFrame(pp_rows)
pp.to_csv(RES / "prepost_by_word.csv", index=False)

# difference-in-differences in the windows: (scripted post/pre) / (spontaneous post/pre)
def did_window(df, col):
    a = window_table(df[df["series"] == "scripted"], col)
    b = window_table(df[df["series"] == "spontaneous"], col)
    t = a.join(b, lsuffix="_s", rsuffix="_q", how="inner")
    def stat(x):
        try:
            return np.log((x["n1_s"] / x["w1_s"]) / (x["n0_s"] / x["w0_s"])) - np.log((x["n1_q"] / x["w1_q"]) / (x["n0_q"] / x["w0_q"]))
        except ZeroDivisionError:
            return np.nan
    p, lo, hi = cluster_boot(t, stat)
    return {"ratio_of_ratios": float(np.exp(p)), "lo": float(np.exp(lo)), "hi": float(np.exp(hi)), "n_firms": int(len(t))}

if "spontaneous" in present:
    SUMMARY["did_window"] = {"all18": did_window(d, "n_tell"), "core13": did_window(d, "n_core")}

if "spontaneous" in present:
    nv = d[~d["verbatim_style"]]
    SUMMARY["sensitivity_no_verbatim_calls"] = {
        "share_of_2025_calls_flagged": float(d[(d["series"] == "scripted") & (d["year"] == 2025)].groupby("call_id")["verbatim_style"].first().mean()),
        "scripted_all18": prepost(nv[nv["series"] == "scripted"], "n_tell"), "scripted_core13": prepost(nv[nv["series"] == "scripted"], "n_core"),
        "spontaneous_all18": prepost(nv[nv["series"] == "spontaneous"], "n_tell"), "did_all18": did_window(nv, "n_tell"),
        "did_core13": did_window(nv, "n_core")}

# ------------------------------------------------------------------ 4. matched-frequency control words
print("controls ...")
is_ok = np.array([len(w) >= 4 and w.isalpha() and w not in TELL_FORMS for w in vocab])
ctrl_rows, fam_ctrl_rows, ctrl_series = [], [], []
N_DRAWS = 1000
for s in present:
    m = (d["series"] == s).values
    sub = d[m]
    Xs = X[m]
    qcodes, qlabels = pd.factorize(sub["quarter"], sort=True)
    G = sparse.csr_matrix((np.ones(len(sub)), (qcodes, np.arange(len(sub)))), shape=(len(qlabels), len(sub)))
    Q = np.asarray((G @ Xs).todense())                         # quarters x vocab term counts
    tokens_q = sub.groupby("quarter")["n_tokens"].sum().reindex(qlabels).values
    ccodes, _ = pd.factorize(sub["cik"])
    C = sparse.csr_matrix((np.ones(len(sub)), (ccodes, np.arange(len(sub)))), shape=(ccodes.max() + 1, len(sub)))
    pre_docs = (sub["quarter"] < FIRST_POST_Q).values
    firms_using = np.asarray(((C[:, pre_docs] @ Xs[pre_docs]) > 0).sum(0)).ravel()
    pre_q = qlabels < FIRST_POST_Q
    w_pre, w_post = in_win(qlabels, PRE_WIN), in_win(qlabels, POST_WIN)
    base_rate = Q[pre_q].sum(0) / tokens_q[pre_q].sum()        # matching variable: 2017-2022 frequency
    pool = is_ok & (firms_using >= 30)
    lr_word = np.log((Q[w_post].sum(0) / tokens_q[w_post].sum() + 1e-12) / (Q[w_pre].sum(0) / tokens_q[w_pre].sum() + 1e-12))
    fam_cols = {f: np.where(np.isin(vocab, TELL_FAMILIES[f]))[0] for f in FAMS}
    cands = {}
    for f in FAMS:
        fr = base_rate[fam_cols[f]].sum()
        if fr <= 0:
            continue
        c = np.where(pool & (np.abs(np.log((base_rate + 1e-15) / fr)) < np.log(1.2)))[0]
        if len(c) < 10:                                       # widen to the 10 nearest in log-frequency
            order = np.argsort(np.abs(np.log((base_rate + 1e-15) / fr)) + (~pool) * 99)
            c = order[:10]
        cands[f] = c
        fam_n = Q[:, fam_cols[f]].sum(1)
        own = np.log((fam_n[w_post].sum() / tokens_q[w_post].sum() + 1e-12) / (fam_n[w_pre].sum() / tokens_q[w_pre].sum() + 1e-12))
        cl = lr_word[c]
        fam_ctrl_rows.append({"series": s, "family": f, "pre_rate_2017_22": 1e4 * fr, "n_candidates": len(c),
                              "tell_log_ratio": own, "ctrl_median": np.median(cl), "ctrl_p05": np.percentile(cl, 5),
                              "ctrl_p95": np.percentile(cl, 95), "percentile_among_controls": 100 * (cl < own).mean(),
                              "example_controls": " ".join(vocab[RNG.choice(c, min(6, len(c)), replace=False)])})

    def set_stats(counts_q):
        rate = 1e4 * counts_q / tokens_q
        lr = np.log(rate[w_post].mean() / rate[w_pre].mean()) if rate[w_pre].mean() > 0 else np.nan
        try:
            r = its(rate, qlabels, FIRST_POST_Q)
            return lr, r["avg_post_effect_pct"], r["level_jump"], rate
        except Exception:
            return lr, np.nan, np.nan, rate

    tell_n = sum(Q[:, fam_cols[f]].sum(1) for f in cands)
    t_lr, t_its, t_lvl, t_rate = set_stats(tell_n)
    draws, idx_series = [], []
    for _ in range(N_DRAWS):
        pick = [RNG.choice(cands[f]) for f in cands]
        lr, itp, lvl, rate = set_stats(Q[:, pick].sum(1))
        draws.append((lr, itp))
        idx_series.append(100 * rate / rate[pre_q].mean())
    draws = np.array(draws); idx_series = np.array(idx_series)
    ctrl_rows.append({"series": s, "tell_log_ratio": t_lr, "tell_pct_change": 100 * (np.exp(t_lr) - 1),
                      "ctrl_median_pct_change": 100 * (np.exp(np.nanmedian(draws[:, 0])) - 1),
                      "ctrl_p025_pct": 100 * (np.exp(np.nanpercentile(draws[:, 0], 2.5)) - 1),
                      "ctrl_p975_pct": 100 * (np.exp(np.nanpercentile(draws[:, 0], 97.5)) - 1),
                      "empirical_p_one_sided": float((draws[:, 0] >= t_lr).mean()),
                      "tell_its_avg_effect_pct": t_its, "ctrl_its_median_pct": float(np.nanmedian(draws[:, 1])),
                      "ctrl_its_p025": float(np.nanpercentile(draws[:, 1], 2.5)), "ctrl_its_p975": float(np.nanpercentile(draws[:, 1], 97.5)),
                      "empirical_p_its": float((draws[:, 1] >= t_its).mean()), "n_draws": N_DRAWS})
    for i, q in enumerate(qlabels):
        ctrl_series.append({"series": s, "quarter": q, "tell_index": 100 * t_rate[i] / t_rate[pre_q].mean(),
                            "ctrl_median": np.median(idx_series[:, i]), "ctrl_p05": np.percentile(idx_series[:, i], 5),
                            "ctrl_p95": np.percentile(idx_series[:, i], 95), "words": tokens_q[i]})
pd.DataFrame(ctrl_rows).to_csv(RES / "controls_summary.csv", index=False)
pd.DataFrame(fam_ctrl_rows).to_csv(RES / "controls_by_family.csv", index=False)
cs = pd.DataFrame(ctrl_series)
cs[cs["words"] >= 20000].to_csv(RES / "controls_series.csv", index=False)

# ------------------------------------------------------------------ 5. excess vocabulary (Kobak et al. 2024)
print("excess vocabulary ...")
pc = pd.read_csv(DATA / "yearly_passage_counts.csv.gz", index_col=0, keep_default_na=False, na_values=[])
totals = pc.loc["__TOTAL_PASSAGES__"]
pc = pc.drop(index="__TOTAL_PASSAGES__")
pc = pc[[len(str(w)) >= 4 and str(w).isalpha() for w in pc.index]]
kob = pd.read_csv(CACHE / "kobak_excess_words.csv", index_col=0)
kob_type = dict(zip(kob["word"], kob["type"]))
tell_set = set(TELL_FORMS)


def excess(series, year, fixed_baseline=False, cutoff=1e-4):
    """Kobak et al.: p=(a+1)/(b+1); q = p[Y-2] + 2*max(p[Y-2]-p[Y-3], 0); delta=p-q; r=p/q.
    With fixed_baseline the projection always starts from 2021->2022 (never uses post-ChatGPT years)."""
    f = lambda y: (pc[f"{series}|{y}"] + 1) / (totals[f"{series}|{y}"] + 1)
    p, prev = f(year), f(year - 1)
    if fixed_baseline:
        b2, b3, h = f(2022), f(2021), year - 2022
    else:
        b2, b3, h = f(year - 2), f(year - 3), 2
    q = b2 + h * np.maximum(b2 - b3, 0)
    n = totals[f"{series}|{year}"]
    out = pd.DataFrame({"count": pc[f"{series}|{year}"], "p": p, "q": q, "delta": p - q, "ratio": p / q})
    out["z"] = (out["count"] - n * q) / np.sqrt(n * q * (1 - q))     # binomial z-score against the projection
    out = out[(p >= cutoff) & (prev >= cutoff)]
    thr = np.log10(2) - (np.log10(out["p"]) + 4) * (np.log10(2) / 4)
    out["is_excess"] = (np.log10(out["ratio"]) > thr) | (out["delta"] > 0.01)
    out["excess_score"] = np.log10(out["ratio"]) - thr          # distance above the ratio threshold line
    # Kobak's thresholds were built for >1M abstracts/year. With ~15-25k passages/year a word needs
    # real support to count: seen in >=0.2% of passages, >=30 passages, and z >= 5 against the projection.
    out["is_robust_excess"] = out["is_excess"] & (out["p"] >= 2e-3) & (out["count"] >= 30) & (out["z"] >= 5)
    out["kobak_type"] = [kob_type.get(w, "") for w in out.index]
    out["is_tell_word"] = [w in tell_set for w in out.index]
    return out


ex_rows, n_rows = [], []
for s in present:
    years = sorted(int(c.split("|")[1]) for c in pc.columns if c.split("|")[0] == s and totals[c] >= 3000)
    for y in years:
        if y - 3 < min(years):
            continue
        e = excess(s, y)
        exc = e[e["is_excess"]]
        rob = e[e["is_robust_excess"]]
        n_rows.append({"series": s, "year": y, "method": "kobak_exact(Y-3,Y-2)", "words_tested": len(e), "excess_words": len(exc),
                       "robust_excess_words": len(rob), "robust_kobak_style": int((rob["kobak_type"] == "style").sum()),
                       "robust_tell": int(rob["is_tell_word"].sum()),
                       "robust_style_words": " ".join(rob[(rob["kobak_type"] == "style") | rob["is_tell_word"]].index),
                       "of_which_kobak_style": int((exc["kobak_type"] == "style").sum()),
                       "of_which_tell": int(exc["is_tell_word"].sum()), "passages": int(totals[f"{s}|{y}"]),
                       "top_by_ratio": " ".join(rob.sort_values("ratio", ascending=False).index[:15])})
        if y >= 2023:
            e2 = excess(s, y, fixed_baseline=True)
            e2 = e2.assign(series=s, year=y).reset_index().rename(columns={"index": "word"})
            ex_rows.append(e2)
            exc2 = e2[e2["is_excess"]]
            rob2 = e2[e2["is_robust_excess"]]
            n_rows.append({"series": s, "year": y, "method": "fixed_baseline(2021,2022)", "words_tested": len(e2),
                           "excess_words": len(exc2), "robust_excess_words": len(rob2),
                           "robust_kobak_style": int((rob2["kobak_type"] == "style").sum()), "robust_tell": int(rob2["is_tell_word"].sum()),
                           "robust_style_words": " ".join(rob2.loc[(rob2["kobak_type"] == "style") | rob2["is_tell_word"], "word"]),
                           "of_which_kobak_style": int((exc2["kobak_type"] == "style").sum()),
                           "of_which_tell": int(exc2["is_tell_word"].sum()), "passages": int(totals[f"{s}|{y}"]),
                           "top_by_ratio": " ".join(rob2.sort_values("ratio", ascending=False)["word"][:15])})
pd.DataFrame(n_rows).to_csv(RES / "excess_words_per_year.csv", index=False)
exw = pd.concat(ex_rows)
exw[exw["is_robust_excess"]].sort_values(["series", "year", "ratio"], ascending=[True, True, False]).to_csv(
    RES / "excess_words.csv", index=False)
exw[exw["is_tell_word"] | (exw["kobak_type"] == "style")].to_csv(RES / "excess_marker_words_all.csv", index=False)

# Kobak-style lower bound: share of passages containing >=1 RARE marker word, observed vs projected
marks = pd.read_parquet(CACHE / "passage_marks.parquet")
kstyle = json.load(open(CACHE / "kobak_style_words.json"))
doc_series = d.set_index("doc_id")["series"]
marks["series"] = marks["doc_id"].map(doc_series).values
marks["year"] = marks["doc_id"].map(d.set_index("doc_id")["year"]).values
marks["cik"] = marks["doc_id"].map(d.set_index("doc_id")["cik"]).values
lb_rows = []
for s in present:
    ms = marks[marks["series"] == s]
    if not {f"{s}|2021", f"{s}|2022"} <= set(pc.columns):
        continue
    base = (pc.reindex(kstyle)[f"{s}|2021"].fillna(0) + pc.reindex(kstyle)[f"{s}|2022"].fillna(0)) / (
        totals[f"{s}|2021"] + totals[f"{s}|2022"])
    for label, thresh in [("rare (<1% of passages in 2021-22)", 0.01), ("rare (<2%)", 0.02), ("rare (<5%)", 0.05)]:
        ids = {i for i, w in enumerate(kstyle) if base[w] < thresh}
        hit = ms["marks"].map(lambda a: any(x in ids for x in a)).values
        tab = pd.DataFrame({"cik": ms["cik"].values, "year": ms["year"].values, "hit": hit, "n": 1})
        byc = tab.pivot_table(index="cik", columns="year", values=["hit", "n"], aggfunc="sum").fillna(0)
        for y in [yy for yy in sorted(tab["year"].unique()) if yy >= 2023 and tab[tab.year == yy].shape[0] >= 3000]:
            def stat(x, y=y):
                P = lambda yr: x[("hit", yr)] / x[("n", yr)]
                return P(y) - (P(2022) + (y - 2022) * max(P(2022) - P(2021), 0))
            p, lo, hi = cluster_boot(byc, stat, n=500)
            tot = byc.sum()
            lb_rows.append({"series": s, "marker_set": label, "n_marker_words": len(ids), "year": int(y),
                            "observed_pct": 100 * tot[("hit", y)] / tot[("n", y)],
                            "p2021_pct": 100 * tot[("hit", 2021)] / tot[("n", 2021)],
                            "p2022_pct": 100 * tot[("hit", 2022)] / tot[("n", 2022)],
                            "delta_pp": 100 * p, "delta_lo": 100 * lo, "delta_hi": 100 * hi})
        # placebo years with the exact Kobak window
        for y in [2020, 2021, 2022]:
            if all(("n", yy) in byc.columns for yy in (y, y - 2, y - 3)):
                def stat(x, y=y):
                    P = lambda yr: x[("hit", yr)] / x[("n", yr)]
                    return P(y) - (P(y - 2) + 2 * max(P(y - 2) - P(y - 3), 0))
                p, lo, hi = cluster_boot(byc, stat, n=500)
                lb_rows.append({"series": s, "marker_set": label + " [placebo year]", "n_marker_words": len(ids), "year": y,
                                "delta_pp": 100 * p, "delta_lo": 100 * lo, "delta_hi": 100 * hi})
pd.DataFrame(lb_rows).to_csv(RES / "kobak_lower_bound.csv", index=False)

# ------------------------------------------------------------------ 6. splits
print("splits ...")
split_rows = []


def add_split(dim, val, df):
    for s in [x for x in present if (df["series"] == x).any()]:
        sub = df[df["series"] == s]
        for mname, col in [("all18", "n_tell"), ("core13", "n_core")]:
            t = window_table(sub, col)
            tot = t.sum()
            if len(t) < 8 or min(tot.w0, tot.w1) < 100000 or min(tot.n0, tot.n1) < 10:
                continue
            split_rows.append({"dimension": dim, "group": val, "series": s, "measure": mname, **prepost(sub, col)})


add_split("all", "All companies", d)
for dim in ["sector", "size_bucket", "region", "speaker_role"]:
    if dim in d and d[dim].notna().any():
        for val, g in d.groupby(dim, observed=True):
            add_split(dim, str(val), g)
pd.DataFrame(split_rows).to_csv(RES / "splits.csv", index=False)

# sector x year heat-map table (scripted + written), rate per 10k words
heat = d[d["sector"].notna()].groupby(["series", "sector", "year"]).agg(n=("n_tell", "sum"), core=("n_core", "sum"),
                                                                        w=("n_tokens", "sum")).reset_index()
heat["tell_rate"] = 1e4 * heat["n"] / heat["w"]; heat["core_rate"] = 1e4 * heat["core"] / heat["w"]
heat[heat["w"] >= 50000].to_csv(RES / "sector_year.csv", index=False)

# ------------------------------------------------------------------ 7. company leaderboard ("vocabulary shift")
lead = []
for s in [x for x in ["scripted", "written_body"] if x in present]:
    sub = d[d["series"] == s]
    t = window_table(sub, "n_tell").join(window_table(sub, "n_core")[["n0", "n1"]].rename(columns={"n0": "c0", "n1": "c1"}))
    t = t[(t["w0"] >= 12000) & (t["w1"] >= 12000)] if s == "scripted" else t[(t["w0"] >= 6000) & (t["w1"] >= 6000)]
    names = sub.sort_values("date").groupby("cik").agg(company=("company", "last"), symbol=("symbol", "last"), sector=("sector", "last"))
    t = t.join(names)
    t["pre_rate"] = 1e4 * t["n0"] / t["w0"]; t["post_rate"] = 1e4 * t["n1"] / t["w1"]
    t["shift_per_10k"] = t["post_rate"] - t["pre_rate"]
    se = 1e4 * np.sqrt(t["n0"] / t["w0"] ** 2 + t["n1"] / t["w1"] ** 2)        # Poisson approximation
    t["shift_lo"], t["shift_hi"], t["z"] = t["shift_per_10k"] - 1.96 * se, t["shift_per_10k"] + 1.96 * se, t["shift_per_10k"] / se
    t["core_shift_per_10k"] = 1e4 * (t["c1"] / t["w1"] - t["c0"] / t["w0"])
    fam_shift = {}
    for f in FAMS:
        ft = window_table(sub, f"tell_{f}").reindex(t.index).fillna(0)
        fam_shift[f] = 1e4 * (ft["n1"] / t["w1"] - ft["n0"] / t["w0"])
    fs = pd.DataFrame(fam_shift)
    t["biggest_mover"] = fs.idxmax(axis=1)
    t["series"] = s
    lead.append(t.reset_index())
lead = pd.concat(lead)
lead[["series", "company", "symbol", "sector", "pre_rate", "post_rate", "shift_per_10k", "shift_lo", "shift_hi", "z",
      "core_shift_per_10k", "biggest_mover", "w0", "w1", "n0", "n1"]].sort_values(
    ["series", "shift_per_10k"], ascending=[True, False]).round(3).to_csv(RES / "company_vocabulary_shift.csv", index=False)

# ------------------------------------------------------------------ 8. extension vs main on overlapping calls
ext = {}
for tt in ["scripted", "spontaneous"]:
    a = ev[ev["series"] == tt].set_index("call_id"); b = ev[ev["series"] == tt + "_ext"].set_index("call_id")
    j = a.join(b, lsuffix="_main", rsuffix="_ext", how="inner")
    if len(j):
        ext[tt] = {"overlapping_calls": int(len(j)), "main_rate": 1e4 * j.n_tell_main.sum() / j.n_tokens_main.sum(),
                   "ext_rate": 1e4 * j.n_tell_ext.sum() / j.n_tokens_ext.sum(),
                   "word_count_ratio": float(j.n_tokens_ext.sum() / j.n_tokens_main.sum()),
                   "call_level_corr": float(np.corrcoef(j.n_tell_main, j.n_tell_ext)[0, 1])}
SUMMARY["extension_overlap"] = ext

# ------------------------------------------------------------------ summary json
def pick(df, **kw):
    m = np.ones(len(df), bool)
    for k, v in kw.items():
        m &= (df[k] == v).values
    return df[m].iloc[0].to_dict() if m.any() else None


SUMMARY["its"] = {f"{s}|{m}|{sp}": {k: v for k, v in pick(reg, series=s, metric=m, spec=sp).items() if k not in ("series", "metric", "spec")}
                  for s in reg["series"].unique() for m in reg["metric"].unique() for sp in reg["spec"].unique()}
SUMMARY["did_its"] = did_rows
SUMMARY["panel_fe"] = fe_rows
SUMMARY["prepost"] = {f"{r['series']}|{r['word']}": {k: v for k, v in r.items() if k not in ("series", "word")} for r in pp_rows}
SUMMARY["controls"] = ctrl_rows
SUMMARY["excess_per_year"] = n_rows
SUMMARY["kobak_lower_bound"] = lb_rows
SUMMARY["headline_quarters"] = {
    s: qs[qs["series"] == s].set_index("quarter")[["tell_rate", "core_rate", "pct_docs_with_tell", "pct_passages_with_tell", "events"]]
    .round(3).to_dict("index") for s in qs["series"].unique()}
json.dump(SUMMARY, open(RES / "summary.json", "w"), indent=1, default=lambda o: float(o) if isinstance(o, np.floating) else int(o) if isinstance(o, np.integer) else str(o))
print("done")
