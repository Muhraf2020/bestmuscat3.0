import os, time, json, requests
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTDIR = ROOT / "data/raw/opentripmap"
OUTDIR.mkdir(parents=True, exist_ok=True)

API_KEY = os.getenv("OPENTRIPMAP_API_KEY")
# Bounding box for Muscat Governorate (approx; tweak as needed)
BBOX = (58.20, 23.45, 58.80, 23.80)  # lon_min, lat_min, lon_max, lat_max

# Map our taxonomy to OTM kinds
CATEGORIES = {
    "hotel": ["other_hotels", "accomodations"],
    "restaurant": ["restaurants"],
    "mall": ["shops", "shopping_malls"]
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
    r.raise_for_status()
    return r.json()

def main():
    all_items = []
    for cat, kinds in CATEGORIES.items():
        offset = 0
        while True:
            batch = fetch(kinds, offset)
            if not batch:
                break
            for x in batch:
                x["_bm_category"] = cat
            all_items.extend(batch)
            offset += len(batch)
            time.sleep(0.3)
    with open(OUTDIR / "places.json", "w", encoding="utf-8") as f:
        json.dump(all_items, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
