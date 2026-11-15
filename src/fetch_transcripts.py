"""Step 1a - download the earnings-call transcript datasets from the Hugging Face Hub (no account needed).

  zcyeee/sp500-earnings-call-turns   33k S&P 500 calls 2005-May 2025, split into speaker turns with
                                     role (management/analyst/operator) and section (prepared/qa).
  Rogersurf/earnings-call-transcripts 9k calls Feb 2024-May 2026 (used only as an out-of-sample extension).
"""
from huggingface_hub import snapshot_download
from config import HF_DIR

REPOS = ["zcyeee/sp500-earnings-call-turns", "Rogersurf/earnings-call-transcripts"]

if __name__ == "__main__":
    for repo in REPOS:
        path = snapshot_download(repo, repo_type="dataset", local_dir=HF_DIR / repo.split("/")[1])
        print("cached", repo, "->", path)
