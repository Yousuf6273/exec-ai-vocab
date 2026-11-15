# Results: are executives letting ChatGPT write for them?

**Verdict.** Not in any way this data can pin on ChatGPT. There is **no jump at the release date**. There is a
**modest, gradual rise in 2024-25 that appears only in text someone drafted in advance** (prepared remarks,
quotes in press releases) and not in live answers from the same executives. That pattern is what AI-assisted
drafting would look like, but the rise is small, rests on a handful of words, and is **not statistically
distinguishable from ordinary vocabulary drift** once compared with matched control words. The biggest
vocabulary shock of the period is COVID-19, not ChatGPT.

## Corpus

| Series | Documents | Words | Companies | Period |
|---|---|---|---|---|
| Scripted (prepared remarks on earnings calls) | 33,537 | 47.7M | 630 | Jan 2017 - May 2025 |
| Spontaneous (same executives, live Q&A) | 36,050 | 66.4M | 630 | Jan 2017 - May 2025 |
| Written: executive quotes in press releases | 26,578 | 2.9M | 644 | Jan 2017 - Nov 2026 |
| Written: press-release narrative | 23,584 | 29.9M | 659 | Jan 2017 - Nov 2026 |

S&P 500 companies. "Before" = 2021Q1-2022Q4, "after" = 2024Q1 onward. Brackets are 95% intervals.

## Key numbers

**1. No break at ChatGPT.** Tell-words per 10,000 words in prepared remarks: 4.2 (2019), **7.1 (2020)**, 7.9 (2022),
7.4 (2023), 7.7 (2024), 9.7 (Jan-May 2025). The jump is in 2020 ("navigate", "elevated", "unwavering").
Segmented regression with a break at 2023Q1: the post-ChatGPT period sits **below** the pre-trend,
-1.8 per 10k (-2.6 to -0.9), because the pre-trend is inflated by COVID; allowing a COVID step it is
-0.3 (-0.9 to +0.3), i.e. nothing. The placebo break (fake date Nov 2020) gives -0.2 (-2.3 to +1.9), also nothing.

**2. Headline metric.** Share of 300-word passages of prepared remarks containing a tell-word: 19.3% in 2022,
18.4% in 2023, 18.5% in 2024, 22% in early 2025. Share of whole prepared-remark sections: 74%, 73%, 73%, 78%.
Flat through the two years after release, then up in 2025, when "navigate" returned with tariffs.

**3. Before vs after, by channel.**

| Channel | All 18 words | Core 13 (five confounded families removed) |
|---|---|---|
| Scripted remarks | **+10%** (+4 to +17) | **+29%** (+18 to +41) |
| Spontaneous Q&A | -6% (-14 to +2) | +4% (-10 to +20) |
| Press-release quotes | **+17%** (+6 to +30) | **+41%** (+22 to +66) |
| Press-release narrative | -9% (-20 to +5) | +19% (-2 to +47) |

Scripted relative to spontaneous on the same calls (difference-in-differences): ratio **1.17** (1.06-1.28) for
all 18 words, **1.25** (1.08-1.45) for the core 13. In the regression version the scripted-minus-spontaneous
gap shows no level jump, but its slope steepens after 2023Q1 by +0.10 per 10k per quarter (p<0.001).

**4. Controls say: be careful.** Against 1,000 random sets of ordinary words matched on pre-2023 frequency,
the tell-word change is on the high side but **inside the normal range**: scripted +11% vs control range
-16% to +18% (one-sided p = 0.08); press-release quotes +16% vs -29% to +29% (p = 0.11); spontaneous and
narrative p = 0.71 and 0.69. Only two families individually beat their matched controls in prepared remarks:
*transformative* (+91%) and *landscape* (+78%).

**5. Which words.** Up in prepared remarks: transformative +91%, landscape +78%, harness +62%, showcase +51%,
pivotal +47%, unwavering +43%, underscore +40%. In press-release quotes: harness +169%, underscore +162%,
landscape +100%, pivotal +97%. Down or flat: navigate, elevate, testament, bolster. The famous ones are
absent: **"delve" appears about twice per million words and did not move**; intricate, meticulous, tapestry
and realm are too rare to measure.

**6. Excess vocabulary (Kobak et al.).** In 2024 prepared remarks, 231 words pass the robust excess test, and
nearly all are topics: *genai* (179x), *copilot*, *generative*, *inferencing*, hurricane *Milton*, *peso*,
*deflation*. Ten are style words (advancements, crucial, empowers, enhance, enhancing, insights, landscape,
transformative, underscoring, unlocking). Live Q&A has four, press-release narrative two. The paper's
lower-bound estimate of LLM-affected text: prepared remarks +2.1 pp in 2024 (-0.9 to +3.9) and +4.2 pp in
2025 (0.0 to +6.8); live Q&A +1.5 pp; press-release narrative -1.4 pp. For comparison the paper finds
about 13% for biomedical abstracts in 2024. The same estimator swings by several points in pre-ChatGPT
placebo years here, so these are within noise.

**7. Where.** CEOs **+19%** (+11 to +28) vs CFOs -4% (-14 to +7) in prepared remarks; CEO press-release quotes +18%.
Sectors (scripted): Healthcare +38% (+17 to +62) and Utilities +42% (+5 to +90) are the only ones clearly
above zero; Energy +51% and Real Estate +22% have intervals spanning zero; Consumer Cyclical -11%.
Company size: no difference (+9%, +10%, +10% by thirds). Region: US South +21% (+7 to +35), others not
distinguishable from zero. All companies are US-listed, so region is weak.

**8. Company vocabulary shift.** Of 361 companies with enough text, 62 moved up and 33 down beyond their own
noise. Largest increases: Elevance Health (13.6 to 37.8 per 10k, mostly "underscore"), GoDaddy ("seamless"),
L3Harris ("elevate"), Lennox and Deere ("navigate"), Intuit ("seamless"). This is a ranking of
**vocabulary shift, not of AI use**: several top movers are driven by words with obvious business meanings.

## Limitations

- **Tell-words are not AI detectors.** Most of these words were rising in corporate language before 2022, and
  several carry business meaning (elevated rates, pivotal trials, competitive landscape, navigating tariffs).
- **The pre-period is not stable.** COVID changed executive vocabulary more than anything since, which makes
  any "projected trend" fragile; conclusions rest on the scripted-vs-spontaneous and control-word comparisons.
- **Effects are small in absolute terms**: the core-13 rise in prepared remarks is 0.8 extra words per 10,000,
  roughly one extra tell-word in every four calls.
- Large caps only; the main transcript series ends May 2025; 2025-26 transcript data come from a different
  vendor and are shown separately. About a fifth of 2025 calls are transcribed verbatim (results unchanged
  without them).
- Speaker roles are inferred from titles (16% of management turns fall back to "Other exec"). Press-release
  quotes are short, so their series is noisy; 880 of 25,124 releases were skipped (oversized or no prose).
- Sector and company results are many comparisons with wide intervals; treat them as descriptive.
- The alternative explanations are not ruled out: fashion in corporate language, new communications staff,
  and AI *as a topic* pulling in words like "transformative" and "harness".

Full numbers: `results/` (CSV) and `results/summary.json`. Method: [methodology.md](methodology.md).
