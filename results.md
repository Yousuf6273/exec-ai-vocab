# Results: are executives letting ChatGPT write for them?

## The answer

**Maybe a little, but there is no proof.**

- Nothing changed when ChatGPT came out in November 2022.
- From 2024, a few "AI-sounding" words creep up, but only in text written ahead of time (speeches, press-release
  quotes). When the same executives speak live, nothing changes. That is a real hint.
- The change is small and no bigger than the normal ups and downs of business language. A hint, not a
  smoking gun.
- The moment executive language really changed was COVID in 2020, not ChatGPT.

## How it works

ChatGPT overuses certain words (delve, underscore, pivotal, showcase, seamless, transformative...). I count
18 of them in what the bosses of S&P 500 companies say and publish.

On an earnings call, executives first **read a script**, then **answer questions live**. AI can write a
script. It cannot write a live answer. So if AI is involved, scripts should change and live answers should not.

| What I looked at | Documents | Words | Period |
|---|---|---|---|
| Scripted speeches on earnings calls | 33,537 | 47.7M | 2017 - May 2025 |
| Live answers, same executives | 36,050 | 66.4M | 2017 - May 2025 |
| Executive quotes in press releases | 26,578 | 2.9M | 2017 - Nov 2026 |
| Rest of the press release | 23,584 | 29.9M | 2017 - Nov 2026 |

## What I found

### 1. No change at the ChatGPT date
The 18 words nearly doubled in scripts in 2020 ("navigating" "elevated" uncertainty: COVID). After ChatGPT
they stay flat for two years: 7.9 per 10,000 words in 2022, 7.4 in 2023, 7.7 in 2024.

> *Technical:* segmented regression, break at 2023Q1, Newey-West errors: −0.3 per 10,000 words
> (95% interval −0.9 to +0.3) with a COVID step. Placebo break at Nov 2020: −0.2 (−2.3 to +1.9).

### 2. Scripts changed, live speech did not
Change from 2021-22 to 2024 onward. "Cleaner 13" drops five words with obvious business meanings
(navigate, elevate, unwavering, pivotal, landscape).

| | All 18 words | Cleaner 13 words |
|---|---|---|
| Scripted speeches | **+10%** | **+29%** |
| Live answers | −6% | +4% |
| Press-release quotes | **+17%** | **+41%** |
| Rest of the press release | −9% | +19% |

Bold = clearly different from zero.

> *Technical:* 95% company-cluster bootstrap intervals: scripted +4 to +17 (core +18 to +41); live −14 to +2
> (core −10 to +20); quotes +6 to +30 (core +22 to +66); narrative −20 to +5 (core −2 to +47).
> Difference-in-differences, scripted vs live on the same calls: ratio 1.17 (1.06-1.28), core 1.25 (1.08-1.45).
> The gap shows no jump at 2023Q1 but its slope steepens by +0.10 per 10,000 words per quarter (p<0.001).

### 3. It could still be chance
Words drift in and out of fashion. I compared the 18 words with 1,000 random groups of equally common
ordinary words. The AI words moved more than most groups, but about 1 random group in 12 moved just as much.
Only *transformative* (+91%) and *landscape* (+78%) clearly beat chance on their own.

> *Technical:* one-sided empirical p = 0.08 (scripts), 0.11 (quotes), 0.71 (live), 0.69 (narrative).
> Controls matched on 2017-22 frequency only.

### 4. The words that really took off are topics
Checking every word, the fastest risers in 2024 scripts are things people were talking about: *GenAI*
(179 times more than expected), *Copilot*, hurricane *Milton*, the *peso*. Ten AI-style words also rose in
scripts (*crucial, empowers, enhance, enhancing, unlocking, underscoring, advancements, insights,
landscape, transformative*), against four in live answers. In scientific papers the same method finds hundreds.

"Delve", the most famous ChatGPT word, appears about twice per million words and did not move.

> *Technical:* excess-vocabulary method of Kobak et al. (2024). Lower-bound share of AI-affected text:
> scripts +2.1 points in 2024 (−0.9 to +3.9), +4.2 in early 2025 (0.0 to +6.8); live +1.5; press-release
> narrative −1.4. The paper reports about 13% for biomedical abstracts. Pre-ChatGPT placebo years swing by
> several points here, so these are within noise.

### 5. Who changed most
- **CEOs, not CFOs.** CEO scripts +19%, CFO scripts −4%.
- **Industries:** healthcare +38% and utilities +42% clearly up; the rest not clearly different from zero.
- **Company size:** no difference.
- **Companies:** of 361 with enough text, 62 moved clearly up and 33 clearly down. Biggest movers: Elevance
  Health, GoDaddy, L3Harris, Lennox, Deere, Intuit. This ranks **vocabulary shift only**. It is not
  evidence that any company uses AI: several of these are driven by words like "navigate" and "elevated".

> *Technical:* CEO +11 to +28, CFO −14 to +7; Healthcare +17 to +62; Utilities +5 to +90. Many comparisons,
> wide intervals: descriptive only.

## Why not to over-read this

- **These words do not prove AI.** People used them before ChatGPT, and most were already rising.
- **The change is tiny:** about one extra AI-sounding word in every four speeches.
- **COVID muddies the baseline,** so "what would have happened anyway" is hard to pin down.
- **Other explanations fit:** fashion in business language, new speech-writers, and AI as a *topic* pulling
  in words like "transformative" and "harness".
- Big US-listed companies only. Speech data ends May 2025 (a different vendor's 2025-26 data is shown
  separately). 880 of 25,124 press releases could not be used. Speaker roles are read from job titles and
  16% of turns could not be assigned.

Full numbers: `results/` and `results/summary.json`. Method: [methodology.md](methodology.md).
