import os, time, json, requests
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTDIR = ROOT / "data/raw/foursquare"
OUTDIR.mkdir(parents=True, exist_ok=True)

FSQ_KEY = os.getenv("FSQ_API_KEY")
CENTER = (23.5880, 58.3829)  # Muscat center
RADIUS = 35000               # meters

# Foursquare category IDs (broad)
CATEGORIES = {
  "restaurant": "13065",
  "hotel": "19014",
  "mall": "17069"
}

BASE = "https://api.foursquare.com/v3/places/search"
HEADERS = {"Authorization": FSQ_KEY, "accept": "application/json"}

def fetch(params):
    r = requests.get(BASE, headers=HEADERS, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def main():
    all_results = []
    for cat_name, cat_id in CATEGORIES.items():
        cursor = None
        while True:
            params = {
                "ll": f"{CENTER[0]},{CENTER[1]}",
                "radius": RADIUS,
                "categories": cat_id,
                "limit": 50,
            }
            if cursor:
                params["cursor"] = cursor
            data = fetch(params)
            results = data.get("results", [])
            for p in results:
                p["_bm_category"] = cat_name
            all_results += results
            cursor = data.get("context", {}).get("next_cursor")
            if not cursor:
                break
            time.sleep(0.25)
    with open(OUTDIR / "places.json", "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
