import json, os, re, unicodedata, math
from pathlib import Path
from slugify import slugify as _slugify

# Paths (relative to repo)
ROOT = Path(__file__).resolve().parents[2]  # repo root
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
MEDIA_DIR = DATA_DIR / "media"

MEDIA_DIR.mkdir(parents=True, exist_ok=True)
RAW_DIR.mkdir(parents=True, exist_ok=True)

# Slug logic
def slugify(name: str) -> str:
    s = unicodedata.normalize("NFKC", (name or "").strip())
    return _slugify(s, lowercase=True, separator="-")

# Geo distance (meters)
def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    from math import radians, sin, cos, asin, sqrt
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi/2)**2 + cos(phi1)*cos(phi2)*sin(dlambda/2)**2
    return 2*R*asin(sqrt(a))

# JSON IO
def read_json(path: Path, default=None):
    if not path.exists():
        return default if default is not None else {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

# Taxonomy (fallback)
def load_taxonomy():
    cats = read_json(DATA_DIR / "categories.json", default=None)
    if not cats:
        cats = {
            "hotel": {"synonyms": ["hotels", "resort"], "icon": "hotel"},
            "restaurant": {"synonyms": ["food", "dining"], "icon": "restaurant"},
            "mall": {"synonyms": ["shopping", "shopping-mall"], "icon": "mall"},
        }
    return cats

# Name normalizer for reconciliation
def norm_name(s: str) -> str:
    s = unicodedata.normalize("NFKC", (s or "").strip().lower())
    s = re.sub(r"[’'`´]", "'", s)
    s = re.sub(r"[^a-z0-9\s&-]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s
