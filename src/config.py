"""Shared paths, constants and word lists. Everything pre-specified here, before looking at results."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "cache"
DATA = ROOT / "data"
CHARTS = ROOT / "charts"
HF_DIR = CACHE / "hf"
EDGAR_DIR = CACHE / "edgar"
for _p in (CACHE, DATA, CHARTS, HF_DIR, EDGAR_DIR):
    _p.mkdir(parents=True, exist_ok=True)

# SEC fair-access policy: identify yourself, stay under 10 requests/second.
SEC_UA = "exec-vocab-research yous.ahm33@gmail.com"
SEC_MAX_RPS = 9

START_DATE = "2017-01-01"          # start of analysis window (pre-ChatGPT baseline: 2017Q1-2022Q4)
CHATGPT_RELEASE = "2022-11-30"
FIRST_POST_Q = "2023Q1"            # first calendar quarter fully after the release
PLACEBO_FIRST_POST_Q = "2021Q1"    # fake break: "Nov 2020" -> first quarter after it
CHUNK_WORDS = 300                  # abstract-sized passage used for document-frequency analyses

# ---------------------------------------------------------------- tell words
# The 18 words named in the project brief, expanded to inflections (word families).
TELL_FAMILIES = {
    "delve": ["delve", "delves", "delved", "delving"],
    "underscore": ["underscore", "underscores", "underscored", "underscoring"],
    "pivotal": ["pivotal"],
    "showcase": ["showcase", "showcases", "showcased", "showcasing"],
    "intricate": ["intricate", "intricately", "intricacy", "intricacies"],
    "meticulous": ["meticulous", "meticulously"],
    "tapestry": ["tapestry", "tapestries"],
    "realm": ["realm", "realms"],
    "testament": ["testament", "testaments"],
    "seamless": ["seamless", "seamlessly"],
    "foster": ["foster", "fosters", "fostered", "fostering"],
    "bolster": ["bolster", "bolsters", "bolstered", "bolstering"],
    "navigate": ["navigate", "navigates", "navigated", "navigating"],
    "landscape": ["landscape", "landscapes"],
    "elevate": ["elevate", "elevates", "elevated", "elevating"],
    "harness": ["harness", "harnesses", "harnessed", "harnessing"],
    "unwavering": ["unwavering"],
    "transformative": ["transformative"],
}
TELL_FORMS = {f: fam for fam, forms in TELL_FAMILIES.items() for f in forms}
# Families with an obvious non-AI driver in this corpus; used only for a robustness variant.
CONFOUNDED_FAMILIES = ["navigate", "unwavering", "pivotal", "elevate", "landscape"]

# ---------------------------------------------------------------- tokenising
TOKEN_RE = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)?")
# Capitalised tokens that are (almost always) names rather than the tell word.
NAME_TOKENS = {"Foster", "Fosters", "Harness", "Pivotal", "Elevate", "Realm", "Landscape", "Testament",
               "Showcase", "Tapestry", "Navigate", "Bolster"}


def tokenize(text):
    """Lower-cased alphabetic tokens. Capitalised name-like forms of tell words (e.g. the surname
    'Foster', the company 'Pivotal') are dropped unless they start a sentence-like position; we
    simply drop them always, which is conservative (it can only lower tell-word counts)."""
    out = []
    for m in TOKEN_RE.finditer(text):
        w = m.group(0)
        if w in NAME_TOKENS:
            out.append("_name_")
            continue
        out.append(w.lower().replace("’", "'"))
    return out


def quarter_of(ts):
    return f"{ts.year}Q{(ts.month - 1) // 3 + 1}"
