import os
import time
import json
import requests
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTDIR = ROOT / "data/raw/opentripmap"
OUTDIR.mkdir(parents=True, exist_ok=True)

API_KEY = os.getenv("OPENTRIPMAP_API_KEY")
if not API_KEY:
    raise SystemExit("OPENTRIPMAP_API_KEY is not set. Add it in Repo Settings → Secrets and variables → Actions.")

# Bounding box for Muscat Governorate (approx; tweak as needed)
# format: lon_min, lat_min, lon_max, lat_max
BBOX = (58.20, 23.45, 58.80, 23.80)

# ✅ Use only well-supported kinds here.
# - We intentionally skip "mall"/"shops" here (OTM often 400s on some shop groupings),
#   because malls/markets are fetched comprehensively via OpenStreetMap in fetch_osm.py.
CATEGORIES = {
    "hotel": ["other_hotels"],   # hotels/guest houses/etc.
    "restaurant": ["restaurants"]
}

BASE = "https://api.opentripmap.com/0.1/en/places/bbox"


def fetch(kinds, offset=0, limit=500):
    params = {
        "apikey": API_KEY,
        "lon_min": BBOX[0],
        "lat_min": BBOX[1],
        "lon_max": BBOX[2],
        "lat_max": BBOX[3],
        "kinds": ",".join(kinds),
        "format": "json",
        "limit": limit,
        "offset": offset,
    }
    r = requests.get(BASE, params=params, timeout=30)
    # Raise with more detail on failure (helps debugging in Actions logs)
    if r.status_code >= 400:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise requests.HTTPError(f"OpenTripMap 400/.. for kinds={kinds}, offset={offset}: {detail}", response=r)
    return r.json()


def main():
    all_items = []
    for cat, kinds in CATEGORIES.items():
        offset = 0
        while True:
            batch = fetch(kinds, offset)
            if not isinstance(batch, list) or not batch:
                break
            for x in batch:
                x["_bm_category"] = cat
            all_items.extend(batch)
            offset += len(batch)
            # polite pacing
            time.sleep(0.3)

    with open(OUTDIR / "places.json", "w", encoding="utf-8") as f:
        json.dump(all_items, f, ensure_ascii=False, indent=2)
    print(f"OpenTripMap: wrote {len(all_items)} records → {OUTDIR/'places.json'}")


if __name__ == "__main__":
    main()
