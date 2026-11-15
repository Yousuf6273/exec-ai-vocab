"""Step 4 - render every chart in charts/ from the tables in results/."""
import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

from config import CHARTS, FIRST_POST_Q, ROOT, TELL_FAMILIES

RES = ROOT / "results"
BLUE, ORANGE, AQUA, VIOLET = "#2a78d6", "#eb6834", "#1baf7a", "#6250d6"
INK, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
COL = {"scripted": BLUE, "spontaneous": ORANGE, "written_quote": AQUA, "written_body": VIOLET}
LABEL = {"scripted": "Scripted: prepared remarks", "spontaneous": "Spontaneous: live Q&A answers",
         "written_quote": "Written: executive quotes in press releases", "written_body": "Written: press-release narrative"}
plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE, "font.family": "DejaVu Sans",
    "font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.7,
    "axes.titleweight": "bold", "axes.titlesize": 11.5, "axes.titlecolor": INK, "axes.titlelocation": "left",
    "legend.frameon": False, "figure.dpi": 110, "savefig.dpi": 170, "lines.linewidth": 2})


def qx(q):
    q = pd.Series(q).astype(str)
    return (q.str[:4].astype(int) + (q.str[5].astype(int) - 0.5) / 4).values


LAUNCH_X = 2022 + 11 / 12


def mark_launch(ax, label=True):
    ax.axvline(LAUNCH_X, color=INK, lw=1.1, ls=(0, (4, 3)), zorder=1)
    if label:
        ax.annotate("ChatGPT released\n30 Nov 2022", xy=(LAUNCH_X, 1), xycoords=("data", "axes fraction"),
                    xytext=(5, -4), textcoords="offset points", va="top", fontsize=8.5, color=INK)


def finish(fig, name, title, subtitle, source="Sources: S&P 500 earnings-call transcripts (2017-2025) and SEC EDGAR 8-K earnings releases. "
                                               "Bands = 95% company-cluster bootstrap CI."):
    fig.suptitle(title, x=0.012, y=0.995, ha="left", va="top", fontsize=14.5, fontweight="bold", color=INK)
    fig.text(0.012, 0.945 if fig.get_figheight() > 6 else 0.925, subtitle, ha="left", va="top", fontsize=10, color=MUTED)
    fig.text(0.012, 0.008, source, ha="left", va="bottom", fontsize=7.8, color=MUTED)
    fig.savefig(CHARTS / name)
    plt.close(fig)
    print("wrote", name)


SHORT = {"scripted": "Scripted", "spontaneous": "Spontaneous", "written_quote": "Release quotes", "written_body": "Release text"}
qs = pd.read_csv(RES / "quarterly_series.csv")
main_series = [s for s in COL if (qs["series"] == s).any()]

# ------------------------------------------------------------------ 1. tell-word trend
fig, axes = plt.subplots(2, 1, figsize=(10.5, 8.6), sharex=True)
fig.subplots_adjust(top=0.835, bottom=0.075, left=0.075, right=0.975, hspace=0.2)
for ax, metric, ttl in [(axes[0], "tell_rate", "AI-sounding words per 10,000 words"),
                        (axes[1], "pct_passages_with_tell", "Share of 300-word passages with at least one AI-sounding word (%); short quotes left out")]:
    for s in main_series:
        if metric == "pct_passages_with_tell" and s == "written_quote":
            continue                                        # quotes are rarely 300 words long: too few passages
        g = qs[qs["series"] == s]
        ax.fill_between(qx(g["quarter"]), g[metric + "_lo"], g[metric + "_hi"], color=COL[s], alpha=0.14, lw=0)
        ax.plot(qx(g["quarter"]), g[metric], color=COL[s], label=LABEL[s])
    for s in ["scripted", "spontaneous"]:
        g = qs[(qs["series"] == s + "_ext") & (qs["quarter"] >= "2025Q2")]
        if len(g):
            ax.plot(qx(g["quarter"]), g[metric], color=COL[s], ls=(0, (1, 1.6)), lw=2,
                    label="Dotted: same measure, Motley Fool transcripts (different vendor)" if s == "scripted" else None)
    mark_launch(ax, label=ax is axes[0])
    ax.set_title(ttl)
    ax.set_ylim(0, None)
    ax.set_xlim(2016.9, max(2026.6, qx(qs["quarter"]).max() + 0.2))
axes[0].axvspan(2020.2, 2021.5, color=MUTED, alpha=0.07, lw=0)
h, l = axes[0].get_legend_handles_labels()
h.append(plt.Rectangle((0, 0), 1, 1, color=MUTED, alpha=0.15, lw=0)); l.append("Shaded: COVID-19 ('navigate', 'elevated', 'unwavering' surge)")
axes[0].legend(h, l, loc="upper left", fontsize=8.8, ncol=1, bbox_to_anchor=(0.0, 1.0))
finish(fig, "tell_word_trend.png", "How often do executives use 'AI-sounding' words?",
       "18 words AI loves (delve, underscore, pivotal, showcase ... transformative). The big jump is COVID in 2020, not ChatGPT.\n"
       "After ChatGPT: flat for two years, then a small rise in pre-written text only.\n"
       "The 2025 spike is the word 'navigate' (tariffs), not AI.")

# ------------------------------------------------------------------ 2. scripted vs spontaneous
fits = pd.read_csv(RES / "its_fits.csv")
fig, axes = plt.subplots(1, 2, figsize=(12.5, 5.4))
fig.subplots_adjust(top=0.78, bottom=0.12, left=0.06, right=0.98, wspace=0.2)
ax = axes[0]
for s in ["scripted", "spontaneous"]:
    g = qs[qs["series"] == s]
    base = g.loc[g["quarter"].between("2021Q1", "2022Q4"), "core_rate"].mean()
    ax.plot(qx(g["quarter"]), 100 * g["core_rate"] / base, color=COL[s], label=LABEL[s])
    ax.fill_between(qx(g["quarter"]), 100 * g["core_rate_lo"] / base, 100 * g["core_rate_hi"] / base, color=COL[s], alpha=0.13, lw=0)
ax.axhline(100, color=MUTED, lw=0.8)
mark_launch(ax)
ax.set_title("Scripted vs live speech (100 = the 2021-22 level)")
ax.legend(loc="upper left", fontsize=9)
ax = axes[1]
p = qs[qs["series"].isin(["scripted", "spontaneous"])].pivot(index="quarter", columns="series", values="core_rate").dropna()
diff = p["scripted"] - p["spontaneous"]
ax.plot(qx(diff.index), diff.values, color=INK, label="Scripted minus spontaneous (per 10k words)")
# counterfactual from pre-2023 linear trend of the difference
pre = diff[diff.index < FIRST_POST_Q]
co = np.polyfit(qx(pre.index), pre.values, 1)
ax.plot(qx(diff.index), np.polyval(co, qx(diff.index)), color=MUTED, ls=(0, (4, 3)), lw=1.5, label="Pre-2023 linear trend, projected")
mark_launch(ax, label=False)
ax.set_title("The gap between script and live speech keeps widening")
ax.legend(loc="upper left", fontsize=9)
finish(fig, "scripted_vs_spontaneous.png", "Same executives: reading a script vs speaking live",
       "If AI is helping write the scripts, scripted speech should change and live answers should not. That is what happens, slightly.\n"
       "Uses 13 of the 18 words: five with obvious business meanings are left out (navigate, elevate, unwavering, pivotal, landscape).",
       source="Source: S&P 500 earnings-call transcripts, 2017Q1-2025Q2 (about 17,000 calls). Bands = 95% company-cluster bootstrap CI.")

# ------------------------------------------------------------------ 3. sector heat-map
sy = pd.read_csv(RES / "sector_year.csv")
heat_series = [s for s in ["scripted", "spontaneous", "written_body"] if (sy["series"] == s).any()]
fig, axes = plt.subplots(1, len(heat_series), figsize=(5.6 * len(heat_series) + 1.4, 6.0), sharey=True)
axes = np.atleast_1d(axes)
fig.subplots_adjust(top=0.8, bottom=0.1, left=0.16 if len(heat_series) > 1 else 0.3, right=0.99, wspace=0.05)
cmap = LinearSegmentedColormap.from_list("div", ["#1c5cab", "#86b6ef", "#efeeea", "#f3a07c", "#c2410c"])
order = None
for ax, s in zip(axes, heat_series):
    g = sy[sy["series"] == s].pivot(index="sector", columns="year", values="tell_rate")
    base = g[[2021, 2022]].mean(axis=1)
    pct = 100 * (g.div(base, axis=0) - 1)
    pct = pct[[c for c in pct.columns if c >= 2018]]
    if order is None:
        last = [c for c in pct.columns if c >= 2024]
        order = pct[last].mean(axis=1).sort_values(ascending=False).index
    pct = pct.reindex(order)
    im = ax.imshow(pct.values, cmap=cmap, norm=TwoSlopeNorm(0, -60, 60), aspect="auto")
    ax.set_xticks(range(len(pct.columns)), pct.columns)
    ax.set_yticks(range(len(pct.index)), pct.index)
    ax.grid(False)
    for i in range(pct.shape[0]):
        for j in range(pct.shape[1]):
            v = pct.values[i, j]
            if np.isfinite(v):
                ax.text(j, i, f"{v:+.0f}", ha="center", va="center", fontsize=8.2, color="white" if abs(v) > 42 else INK)
    ax.axvline(list(pct.columns).index(2023) - 0.5, color=INK, lw=1.2, ls=(0, (4, 3)))
    ax.set_title(LABEL[s], fontsize=10.5)
    ax.tick_params(length=0)
    for sp in ax.spines.values():
        sp.set_visible(False)
finish(fig, "sector_heatmap.png", "Which industries changed most?",
       "Each cell: how much more (orange) or less (blue) each industry used the 18 words that year, in %, compared with its own\n"
       "2021-22 level. Dashed line = ChatGPT release.",
       source="Sources: S&P 500 earnings-call transcripts and SEC EDGAR earnings releases. Sector = Yahoo Finance classification. 2025 transcripts cover Jan-May only.")

# ------------------------------------------------------------------ 4. top excess words
ex = pd.read_csv(RES / "excess_words.csv")
mk = pd.read_csv(RES / "excess_marker_words_all.csv")
fig, axes = plt.subplots(1, 2, figsize=(13, 7.6))
fig.subplots_adjust(top=0.83, bottom=0.14, left=0.11, right=0.975, wspace=0.42)
ax = axes[0]
g = ex[(ex["series"] == "scripted") & (ex["year"] == 2024)].sort_values("ratio", ascending=False).head(28).iloc[::-1]
style = (g["kobak_type"] == "style") | g["is_tell_word"]
ax.barh(g["word"], g["ratio"], color=np.where(style, ORANGE, BLUE), height=0.62)
ax.set_xscale("log")
ax.set_xlabel("Times more common than its earlier trend predicted (log scale)")
ax.set_title("Words that grew fastest in scripted remarks, 2024\n(times more common than expected)")
ax.grid(axis="y", visible=False)
for w, r in zip(g["word"], g["ratio"]):
    ax.text(r * 1.07, w, f"{r:.0f}x" if r >= 10 else f"{r:.1f}x", va="center", fontsize=8, color=MUTED)
ax.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=BLUE), plt.Rectangle((0, 0), 1, 1, color=ORANGE)],
          labels=["Topic or name", "Writing-style word"], loc="lower right", fontsize=8.5)
ax = axes[1]
m = mk[(mk["year"] == 2024) & mk["series"].isin(["scripted", "spontaneous"])]
w = m.pivot(index="word", columns="series", values=["ratio", "count", "z"])
w = w[(w[("count", "scripted")] >= 30)].sort_values(("ratio", "scripted"), ascending=False).head(28).iloc[::-1]
y = np.arange(len(w))
ax.hlines(y, w[("ratio", "spontaneous")].fillna(1), w[("ratio", "scripted")], color=GRID, lw=2, zorder=1)
ax.scatter(w[("ratio", "spontaneous")], y, color=ORANGE, s=42, zorder=3, label="Spontaneous (Q&A)", edgecolor=SURFACE, lw=1)
ax.scatter(w[("ratio", "scripted")], y, color=BLUE, s=42, zorder=3, label="Scripted (prepared remarks)", edgecolor=SURFACE, lw=1)
ax.axvline(1, color=INK, lw=1)
ax.set_yticks(y, w.index)
ax.set_xscale("log")
ax.set_xticks([0.5, 1, 2, 3, 4], ["0.5x", "1x", "2x", "3x", "4x"])
ax.minorticks_off()
ax.set_xlabel("Times more common than expected in 2024 (1x = as expected)")
ax.set_title("Known AI-style words: scripted vs live speech, 2024\n(right of the line = more common than expected)")
ax.grid(axis="y", visible=False)
ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.09), fontsize=8.5, ncol=2)
finish(fig, "top_excess_words.png", "Which words suddenly became more common in 2024?",
       "Every word's 2024 use compared with what its 2021-22 trend predicted (method of Kobak et al. 2024). The words that exploded\n"
       "are topics (AI products, hurricanes, deflation), not writing style. A few AI-style words do rise - in scripted remarks only.",
       source="Source: S&P 500 earnings-call transcripts. Left: words in >=0.2% of passages, >=30 passages, z>=5. Right: Kobak et al.'s published style list plus the tell-words, >=30 passages;\nwords are picked for high scripted excess, so some scripted-over-spontaneous gap is expected by selection alone.")

# ------------------------------------------------------------------ 5. controls + placebo
cs = pd.read_csv(RES / "controls_series.csv")
reg = pd.read_csv(RES / "segmented_regression.csv")
cf = pd.read_csv(RES / "controls_by_family.csv")
fig = plt.figure(figsize=(13, 9.4))
gs = fig.add_gridspec(2, 2, top=0.86, bottom=0.15, left=0.15, right=0.98, hspace=0.36, wspace=0.3)
for k, s in enumerate(["scripted", "spontaneous"]):
    ax = fig.add_subplot(gs[0, k])
    g = cs[cs["series"] == s]
    ax.fill_between(qx(g["quarter"]), g["ctrl_p05"], g["ctrl_p95"], color=MUTED, alpha=0.2, lw=0, label="Random ordinary words: typical range")
    ax.plot(qx(g["quarter"]), g["ctrl_median"], color=MUTED, lw=1.5, label="Random ordinary words: middle")
    ax.plot(qx(g["quarter"]), g["tell_index"], color=COL[s], label="The 18 AI-sounding words")
    ax.axhline(100, color=MUTED, lw=0.6)
    mark_launch(ax, label=k == 1)
    ax.set_title(f"{LABEL[s]}\n100 = its 2017-22 average", fontsize=10.5)
    ax.set_ylim(30, 210)
    if k == 0:
        ax.legend(loc="upper left", fontsize=8.3)
ax = fig.add_subplot(gs[1, 0])
rows = []
for s in main_series:
    for metric, mlab in [("tell_rate", "all 18"), ("core_rate", "core 13")]:
        for spec, slab in [("main", "Real date: after ChatGPT (2023 onward)"), ("placebo_nov2020", "Placebo break (2021Q1)")]:
            r = reg[(reg["series"] == s) & (reg["metric"] == metric) & (reg["spec"] == spec)]
            if len(r):
                r = r.iloc[0]
                rows.append((f"{SHORT[s]} - {mlab}", spec, 100 * r["avg_post_effect"] / r["counterfactual_post_mean"],
                             100 * r["avg_lo"] / r["counterfactual_post_mean"], 100 * r["avg_hi"] / r["counterfactual_post_mean"]))
rf = pd.DataFrame(rows, columns=["label", "spec", "eff", "lo", "hi"])
labs = list(dict.fromkeys(rf["label"]))[::-1]
for spec, c, off in [("main", BLUE, 0.16), ("placebo_nov2020", MUTED, -0.16)]:
    g = rf[rf["spec"] == spec]
    yy = np.array([labs.index(l) for l in g["label"]]) + off
    ax.hlines(yy, g["lo"], g["hi"], color=c, lw=2)
    ax.scatter(g["eff"], yy, color=c, s=40, zorder=3, label="Real date: after ChatGPT (2023 onward)" if spec == "main" else "Fake date: Nov 2020 (should show nothing)")
ax.axvline(0, color=INK, lw=1)
ax.set_yticks(range(len(labs)), labs)
ax.set_xlabel("After the date: % above or below the earlier trend (95% interval)")
ax.set_title("Did the trend change at ChatGPT? Real date vs a fake date", fontsize=10.5)
ax.grid(axis="y", visible=False)
ax.legend(loc="upper center", bbox_to_anchor=(0.4, -0.17), fontsize=8.3, ncol=1)
ax = fig.add_subplot(gs[1, 1])
g = cf[cf["series"] == "scripted"].copy()
g = g[g["pre_rate_2017_22"] >= 0.05].sort_values("tell_log_ratio")
pc = lambda v: 100 * (np.exp(v) - 1)
y = np.arange(len(g))
ax.hlines(y, pc(g["ctrl_p05"]), pc(g["ctrl_p95"]), color=MUTED, alpha=0.35, lw=6, label="Ordinary words of the same frequency: typical range")
out = (g["tell_log_ratio"] > g["ctrl_p95"]) | (g["tell_log_ratio"] < g["ctrl_p05"])
ax.scatter(pc(g["tell_log_ratio"]), y, color=np.where(out, BLUE, "#86b6ef"), s=46, zorder=3, edgecolor=SURFACE, lw=1, label="AI-sounding word (dark = beyond what random words do)")
ax.axvline(0, color=INK, lw=1)
ax.set_yticks(y, g["family"])
ax.set_xlabel("% change in rate, 2021-22 vs 2024-25, scripted remarks")
ax.set_title("Each AI-sounding word vs ordinary words", fontsize=10.5)
ax.grid(axis="y", visible=False)
ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.17), fontsize=8.3)
finish(fig, "controls_placebo.png", "Sanity checks: is this more than random change?",
       "Top: the 18 words against 1,000 random sets of equally common ordinary words (grey = how much random words move anyway).\n"
       "Bottom-left: the same test with a made-up date. Bottom-right: words too rare to test (delve, intricate, meticulous, tapestry, realm) left out.",
       source="Source: S&P 500 earnings-call transcripts (and SEC EDGAR releases where shown). Controls matched on 2017-22 frequency (+/-20%), used by >=30 companies.")

# ------------------------------------------------------------------ 6. family small multiples
fams = list(TELL_FAMILIES)
fig, axes = plt.subplots(3, 6, figsize=(14.5, 7.6), sharex=True)
fig.subplots_adjust(top=0.84, bottom=0.07, left=0.04, right=0.99, hspace=0.42, wspace=0.3)
yr = lambda g, f: g.assign(y=g["quarter"].str[:4].astype(int)).groupby("y").apply(lambda x: np.average(x[f"rate_{f}"], weights=x["words"]))
for ax, f in zip(axes.ravel(), fams):
    for s in ["scripted", "spontaneous"]:
        a = yr(qs[qs["series"] == s], f)
        ax.plot(a.index, a.values, color=COL[s], lw=1.8, marker="o", ms=3)
    ax.axvline(2022.92, color=INK, lw=0.9, ls=(0, (4, 3)))
    ax.set_title(f, fontsize=10)
    ax.set_ylim(0, None)
    ax.set_xticks([2018, 2021, 2024])
    ax.tick_params(labelsize=8)
axes[0, 0].legend(handles=[plt.Line2D([], [], color=BLUE), plt.Line2D([], [], color=ORANGE)], labels=["Scripted", "Spontaneous"], fontsize=8, loc="upper left")
finish(fig, "tell_word_families.png", "Each of the 18 words, year by year (per 10,000 words)",
       "Yearly rates; 2025 = January-May. Note the different y-axes: 'delve', 'intricate', 'meticulous', 'tapestry' and 'realm' are almost never used by executives.",
       source="Source: S&P 500 earnings-call transcripts, 2017-2025. Dashed line = ChatGPT release.")

# ------------------------------------------------------------------ 7. leaderboard
lb = pd.read_csv(RES / "company_vocabulary_shift.csv")
g = lb[lb["series"] == "scripted"].sort_values("shift_per_10k", ascending=False).head(20).iloc[::-1]
fig, ax = plt.subplots(figsize=(10.5, 7.4))
fig.subplots_adjust(top=0.85, bottom=0.085, left=0.33, right=0.97)
y = np.arange(len(g))
ax.barh(y, g["shift_per_10k"], color=BLUE, height=0.6)
ax.hlines(y, g["shift_lo"], g["shift_hi"], color=INK, lw=1)
ax.set_yticks(y, [f"{c} ({s})" for c, s in zip(g["company"].str.slice(0, 34), g["symbol"])])
for yy, r in zip(y, g.itertuples()):
    ax.text(max(r.shift_hi, r.shift_per_10k) + 0.4, yy, f"{r.pre_rate:.1f} -> {r.post_rate:.1f}  ({r.biggest_mover})", va="center", fontsize=8, color=MUTED)
ax.set_xlabel("Change in tell-words per 10,000 words, 2021-22 -> 2024-25 (95% interval)")
ax.grid(axis="y", visible=False)
ax.set_xlim(0, g["shift_hi"].max() * 1.45)
finish(fig, "company_vocabulary_shift.png", "Companies whose wording changed most (scripted remarks)",
       "This is a VOCABULARY SHIFT ranking, not evidence that any company uses AI to write. Labels: rate before -> after, and the\n"
       "word family that moved most. Many shifts are topical (e.g. 'navigate' tariffs, 'elevated' rates) or a new speech-writer.",
       source="Source: S&P 500 earnings-call transcripts. Companies with >=12,000 words of prepared remarks in each window. Interval: Poisson approximation.")
