# Methodology

Question: did "AI-style" vocabulary rise in what senior executives say and publish after ChatGPT
was released on 30 November 2022, and where did it rise most?

Everything below was decided by the analyst (an AI coding agent working autonomously) and is
recorded so that each judgement call can be challenged. Word lists, windows, break dates and control
rules were written into `src/config.py` and `src/analyse.py` **before** results were inspected. Where a
choice was made after seeing data, it is flagged with **[post-hoc]**.

## 1. Sources considered

| Source | Attributable to execs? | Free, no sign-up? | 2019 to present? | Scale | Scripted vs spontaneous? | Verdict |
|---|---|---|---|---|---|---|
| **Earnings-call transcripts** (S&P 500), Hugging Face `zcyeee/sp500-earnings-call-turns` | Yes: every turn has a speaker, role and section | Yes (public Hub download, MIT-labelled) | 2005 to May 2025 | 33k calls, 685 tickers | **Yes**: prepared remarks vs live Q&A, same people, same day | **Chosen: main source** |
| **Earnings press releases**, SEC EDGAR 8-K item 2.02, exhibit 99.1 | Partly: named executive quotes, plus corporate narrative | Yes (public-domain filings; SEC fair-access rules) | 2001 to today | ~25k filings for the same companies | No (all written) | **Chosen: written source, runs to Nov 2026** |
| Motley Fool transcripts, Hugging Face `Rogersurf/earnings-call-transcripts` | Yes | Yes (research-use licence) | Feb 2024 to May 2026 only | 9k calls | Yes | **Chosen as a caveated extension only**: no pre-ChatGPT baseline, and the site changed layout in mid-2025 |
| Other Hub copies (`kurry/`, `Bose345/`, `glopardo/`) | Same underlying calls | Yes | to 2025 | same | Not pre-split | Rejected: same text without speaker turns |
| Shareholder letters (10-K exhibit 13 / annual reports) | Yes (CEO/chair signed) | Yes via EDGAR, but most letters live in PDF annual reports that are not filed as text | Yes | One per company-year: about 4k documents | No | Rejected: too few documents, hard to extract reliably |
| Executive LinkedIn posts | Yes | **No**: login required, terms and robots.txt forbid scraping | - | - | - | Rejected on legal grounds |
| Speeches (conference keynotes, Davos, etc.) | Yes | Scattered, no consistent archive | Patchy | Hundreds | No | Rejected: no consistent corpus |
| Paid transcript vendors (Refinitiv, FactSet, Seeking Alpha, AlphaSense) | Yes | No (paid / sign-up) | - | - | - | Rejected by the brief |
| Kaggle transcript dumps | Yes | No (account needed) | mostly to 2022-23 | - | - | Rejected |

Why this combination: the transcript set gives the strongest design available (the same executives
reading a script and then speaking off the cuff minutes later, 2017-2025), and EDGAR adds a
second, independent, purely written channel from the same companies that runs to the present day.

### Access and conduct
- Hugging Face: plain `snapshot_download`, no token. `robots.txt` allows all.
- SEC EDGAR: `robots.txt` allows `/Archives/edgar/data`. Requests carry the declared User-Agent
  `exec-vocab-research yous.ahm33@gmail.com`, are globally rate-limited to 9 per second (SEC limit: 10),
  back off on 403/429/5xx, and are cached so nothing is fetched twice.
- **Redistribution.** Call transcripts are third-party copyrighted text. The published `data/` folder
  therefore contains document-level metadata and word counts, not the transcript text. The full cleaned
  text (`data/corpus_text.csv.gz`) is produced locally by the pipeline and is git-ignored.

### Failures and switches (log)
- First EDGAR run used 6 connections and was too slow (about 2 filings/s); restarted with 16 connections
  under the same 9 req/s cap. No data lost (cache).
- Motley Fool layout change (mid-2025): the new pages no longer list participants with titles on every
  turn, and a transitional layout has no participant list at all. Fallback: speakers are matched to
  executives already known from the same company's earlier calls. 43 of 2,217 transcripts could not
  be parsed and were dropped.
- EDGAR: 25,497 item-2.02 filings found; 373 have no exhibit 99 (results furnished inside the 8-K body) and
  were skipped. The first cleaning run stalled for two hours on a few multi-megabyte exhibits; it was
  rewritten to run in resumable batches with a 20-second limit per document and a 3 MB size cap.
  414 oversized exhibits (financial supplements, not releases) and 466 with no usable prose were skipped,
  leaving 23,527 releases.

## 2. Corpus construction

**Window.** 1 Jan 2017 onward (the brief asked for 2019+; two extra years give the pre-trend more support).
Pre-ChatGPT baseline: 2017Q1-2022Q4. Calls for the quarter ending Dec 2022 happen in Jan-Feb 2023, so the
first post-release calendar quarter is **2023Q1**; "break at Q4 2022" is implemented as post = 2023Q1 onward.

**Call transcripts (main).** Kept: calls with no quality flag, with an SEC CIK, not marked as another
company's call; duplicates filed under two share classes removed. Only `management` turns are used.
- *Scripted* = management turns before the Q&A starts. *Spontaneous* = management turns inside the Q&A.
- Operator and analyst turns are discarded.
- **Speaker role.** CEO / CFO / Chair / Other exec / IR from (a) the title printed in the transcript,
  (b) the introduction ("with me are Jane Doe, Chief Financial Officer..."), (c) the same person's role on
  the company's other calls. "Chairman and CEO" counts as CEO. If none applies: "Other exec".
  Roughly 72% of management turns get a role from the same call, 11% from other calls, 16% stay "Other exec".
  **Investor-relations hosts are excluded** from all analyses: their text is mostly safe-harbor boilerplate
  and they are not senior executives.
- **Boilerplate.** Sentences matching safe-harbor, non-GAAP, filing-reference, webcast/replay,
  greeting and hand-over patterns are deleted. This removes about 3% of executive words (most boilerplate
  sits in the excluded IR and operator turns).

**Press releases (written).** Exhibit 99.1 of every 8-K with item 2.02 filed since 2017 by the same CIKs.
HTML is stripped; numeric tables are dropped (a table is kept only if it merely wraps prose); sections
headed forward-looking statements / non-GAAP / conference call / about / contacts are dropped, as are
paragraphs under 20 words, digit-heavy fragments, and paragraphs with boilerplate cues (URLs, phone
numbers, "is a leading...", "differ materially"...). Each release yields
- *written_quote*: text inside quotation marks, attributed to a role by the title in the same
  paragraph (or by surname from an earlier attribution), and
- *written_body*: the remaining narrative prose (role "Company").

About 43% of raw release words survive cleaning. Every release is kept (a few companies file more than one
per quarter). Quotes are usually under 300 words, so the quote series is reported as a rate per 10,000
words and left out of the passage-share charts. Because press releases are public filings, their cleaned
text is published in `data/corpus_text_press_releases.csv.gz`.

**Company metadata.** Sector: Yahoo Finance sector shipped with the transcript set (today's classification).
Size: public float from the FY2022 10-K cover page (SEC XBRL `EntityPublicFloat`), cut into thirds
*within this large-cap sample*. Region: headquarters state from EDGAR mapped to US Census regions, or
"Non-US HQ". All S&P 500 constituents are US-listed, so the region split is weak by construction.

**Unit of analysis.** A *document* is one (event, text type, speaker role). For document-frequency
statistics the text is cut into consecutive **300-word passages** (roughly the length of the paper abstracts
used by Kobak et al.), because whole calls are so long that "contains the word at least once" saturates.

## 3. Measures

- **Tell-words.** The 18 words in the brief, expanded to inflections (`delve, delves, delved, delving`...).
  Rate = occurrences per 10,000 words. Capitalised name-like forms (`Foster`, `Pivotal`, `Harness`...)
  are never counted, which can only bias counts downward.
- **Core 13.** Before looking at results, five families were set aside as having obvious non-AI drivers in
  earnings language: `navigate` and `unwavering` (pandemic), `elevate` (dominated by "elevated" rates,
  costs, inventories), `pivotal` (pivotal clinical trials) and `landscape` ("competitive landscape").
  Every result is reported for all 18 and for the remaining 13.
- **Headline.** Share of documents containing at least one tell-word, by quarter, reported at two levels:
  whole event sections (as the brief asks) and 300-word passages (length-neutral).
- **Family index.** Mean over families of the log ratio to the family's own pre-2023 level, so that two
  frequent words do not dominate.

## 4. Statistical design

1. **Segmented regression** on each quarterly series:
   `y = a + b*t + c*post + d*(t - t0)*post + quarter-of-year dummies`, Newey-West errors (4 lags).
   Reported: level jump `c`, slope change `d`, and the **average post-period gap** between the fit and
   the projected pre-trend with its 95% CI. A sensitivity version adds a level step at 2020Q2 (COVID).
   A company fixed-effects panel version (call level, word-weighted, errors clustered by company) guards
   against the sample of companies changing.
2. **Placebo.** The same regression on pre-2023 data only, with a fake break after November 2020.
3. **Difference-in-differences.** Scripted minus spontaneous rate on the same calls, same regression; and
   a ratio of ratios over fixed windows (2021Q1-2022Q4 vs 2024Q1 onward) with a company-cluster bootstrap.
4. **Matched-frequency controls.** For each tell-word family, ordinary words (4+ letters, used by at least
   30 companies before 2023) whose 2017-22 frequency is within 20% of the family's. 1,000 random
   control sets (one word per family) give the distribution of "what a random set of equally common words
   did". Controls are matched on frequency only, never on their later behaviour.
5. **Excess vocabulary (Kobak et al. 2024).** For every word, `p = (a+1)/(b+1)` where `a` is the number
   of passages containing it in year Y and `b` the number of passages. Projection
   `q = p[Y-2] + 2*max(p[Y-2] - p[Y-3], 0)`; gap `delta = p - q`, ratio `r = p/q`; a word is "excess" if
   `delta > 0.01` or `log10 r > log10 2 - (log10 p + 4) * log10(2)/4` (the authors' code).
   Y = 2024 uses 2021 and 2022, exactly as in the paper. For 2025 and 2026 the baseline stays at
   2021-22 and the trend term is extended, so no post-ChatGPT year enters the projection.
   - **Adaptation.** The paper has over a million abstracts a year; this corpus has 15-25k passages per
     series-year, so the paper's thresholds flag thousands of words in every year, placebo years included.
     Words are therefore also required to appear in at least 0.2% of passages, at least 30 passages, and to
     sit 5 standard errors above the projection ("robust excess"). **[post-hoc, after seeing that the raw
     thresholds were all noise]**
   - **Style vs content.** Instead of hand-labelling, style words are taken from the authors' own published
     annotation (407 "style" excess words). The paper's lower-bound estimate (share of documents with at
     least one rare marker word, observed minus projected) is reproduced with that list.
6. **Splits**: sector, size third, region, role, text type: % change in rate between the fixed windows
   with company-cluster bootstrap CIs.
7. **Leaderboard**: per-company change in rate between the windows, with a Poisson interval. It ranks
   **vocabulary shift**. It does not and cannot show that a company used AI.

## 5. Other judgement calls

- **Verbatim transcripts [post-hoc].** About a fifth of 2025 calls in the main set are transcribed
  verbatim ("gonna", numbers spelled out), evidently a change at the vendor. Tell-word rates are the same in
  those calls, so they stay in the tell-word analyses (a sensitivity check without them is reported), but
  they are excluded from the vocabulary-wide excess-word counts, where "gonna" and "twenty" would otherwise
  top the list.
- **2025 and "navigate" [post-hoc observation, no change to the analysis].** Tell-word rates spike in
  early 2025 in every channel. The spike is the `navigate` family (tariffs), one of the five families
  set aside in advance; it is another reminder that these words respond to events.
- **Thin quarters.** Series-quarters with fewer than 30 events are dropped (e.g. the first weeks of a
  partial quarter).
- **Extension series.** Motley Fool transcripts are never spliced into a main series. On the ~680 calls
  present in both sources, tell-word counts correlate at 0.97, so the measure itself is vendor-robust,
  but the 2025-26 pages use a different layout and transcription style and are shown dotted.
- **Windows.** "Before" = 2021Q1-2022Q4 (after the COVID vocabulary shock had settled, immediately before
  the release). "After" = 2024Q1 onward (a year for adoption).
- **What is not done.** No AI-detector models, no attempt to classify individual documents, no manual
  relabelling of words after seeing results, no removal of inconvenient families.

## 6. Reference

Kobak, D., González-Márquez, R., Horvát, E.-Á., Lause, J. (2024/2025). *Delving into LLM-assisted writing
in biomedical publications through excess vocabulary.* arXiv:2406.07016. Code and word annotations:
github.com/berenslab/llm-excess-vocab.
