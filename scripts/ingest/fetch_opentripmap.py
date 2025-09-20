import os, time, json, requests
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTDIR = ROOT / "data/raw/opentripmap"
OUTDIR.mkdir(parents=True, exist_ok=True)

API_KEY = os.getenv("OPENTRIPMAP_API_KEY")
BBOX = (58.20, 23.45, 58.80, 23.80)  # lon_min, lat_min, lon_max, lat_max

CATEGORIES = {
    "hotel": ["other_hotels", "accomodations"],
    "restaurant": ["restaurants"],
    "mall": ["shops", "shopping_malls"]
}

BASE_BBOX = "https://api.opentripmap.com/0.1/en/places/bbox"
BASE_XID  = "https://api.opentripmap.com/0.1/en/places/xid/"

def fetch_bbox(kinds, offset=0, limit=500):
    params = {
        "apikey": API_KEY,
        "lon_min": BBOX[0], "lat_min": BBOX[1],
        "lon_max": BBOX[2], "lat_max": BBOX[3],
        "kinds": ",".join(kinds),
        "format": "json",
        "limit": limit,
        "offset": offset,
    }
    r = requests.get(BASE_BBOX, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def fetch_detail(xid):
    r = requests.get(BASE_XID + xid, params={"apikey": API_KEY}, timeout=30)
    r.raise_for_status()
    return r.json()

def main():
    all_items = []
    for cat, kinds in CATEGORIES.items():
        offset = 0
        while True:
            batch = fetch_bbox(kinds, offset)
            if not batch:
                break
            for x in batch:
                x["_bm_category"] = cat
            all_items.extend(batch)
            offset += len(batch)
            time.sleep(0.3)

    # Fetch details for each xid to enrich address/website
    detailed = []
    for x in all_items:
        xid = x.get("xid")
        if not xid:
            continue
        try:
            d = fetch_detail(xid)
            # map to a simpler structure and keep category + point
            lat, lon = None, None
            if "point" in d:
                lat, lon = d["point"].get("lat"), d["point"].get("lon")
            addr = d.get("address") or {}
            address = ", ".join(filter(None, [
                addr.get("house_number"),
                addr.get("road"),
                addr.get("suburb"),
                addr.get("city"),
                addr.get("postcode")
            ])) or None
            detailed.append({
                "xid": xid,
                "name": d.get("name") or x.get("name"),
                "_bm_category": x.get("_bm_category"),
                "location": {"lat": lat, "lon": lon, "address": address},
                "contacts": {"website": d.get("url")},
            })
            time.sleep(0.2)
        except Exception:
            continue

    with open(OUTDIR/"places.json", "w", encoding="utf-8") as f:
        json.dump(detailed, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
