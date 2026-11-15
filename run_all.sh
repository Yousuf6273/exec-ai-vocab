#!/usr/bin/env bash
# Reproduce everything end to end. ~1.6 GB download from Hugging Face, ~25k small requests to SEC EDGAR (about 90 min).
set -euo pipefail
cd "$(dirname "$0")/src"
PY=${PYTHON:-../.venv/bin/python}
$PY fetch_transcripts.py      # 1a  transcripts from the Hugging Face Hub
$PY build_universe.py         # 1b  company universe (CIKs) from the transcripts
$PY fetch_edgar.py            # 1c  earnings press releases + company metadata from SEC EDGAR
curl -sL https://raw.githubusercontent.com/berenslab/llm-excess-vocab/main/results/excess_words.csv -o ../cache/kobak_excess_words.csv
$PY clean_transcripts.py      # 2a  executive speech, scripted vs spontaneous, boilerplate removed
$PY clean_edgar.py            # 2b  press releases -> executive quotes + narrative
$PY features.py               # 2c  tokenise, count, write data/
$PY analyse.py                # 3   statistics -> results/
$PY charts.py                 # 4   charts/
