"""Step 1b - list the SEC CIKs that hold an earnings call in the transcript dataset since START_DATE."""
import glob

import pandas as pd

from config import DATA, HF_DIR, START_DATE

cols = ["symbol", "date", "cik", "cik_name"]
m = pd.concat(pd.read_parquet(f, columns=cols) for f in sorted(glob.glob(str(HF_DIR / "sp500-earnings-call-turns/data/*.parquet"))))
m = m[(m["date"] >= START_DATE) & m["cik"].notna()]
u = m.groupby("cik").agg(symbol=("symbol", "first"), name=("cik_name", "last"), n_calls=("date", "size")).reset_index()
u["cik"] = u["cik"].astype(int)
u.to_csv(DATA / "universe.csv", index=False)
print(len(u), "companies")
