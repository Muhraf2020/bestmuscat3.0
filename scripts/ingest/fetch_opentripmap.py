import os, time, json, requests
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTDIR = ROOT / "data/raw/opentripmap"
OUTDIR.mkdir(parents=True, exist_ok=True)

API_KEY = os.getenv("OPENTRIPMAP_API_KEY")

# Muscat-ish bbox: lon_min, lat_min, lon_max, lat_max
BBOX = (58.20, 23.45, 58.80, 23.80)

BASE_BBOX = "https://api.opentripmap.com/0.1/en/places/bbox"
BASE_XID  = "https://api.opentripmap.com/0.1/en/places/xid/"

# IMPORTANT: OTM 'kinds' taxonomy is finicky. We try candidates in order.
# If an option returns 400, we'll fall back to the next one automatically.

KIND_CANDIDATES = {
    "restaurant": [
        ["restaurants"],            # most commonly accepted
        ["foods"],                  # broader fallback
        ["catering"],               # last resort
    ],
    "hotel": [
        ["accomodations"],          # spelling per OTM taxonomy (one 'm')
        ["hotels"],                 # sometimes exists
    ],
    "mall": [
        ["shopping_mall"],          # singular is more likely than plural
        ["shops"],                  # broad fallback
    ],
}

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
    # Let the caller inspect status to try fallbacks on 400
    if r.status_code == 400:
        return None, 400
    r.raise_for_status()
    return r.json(), r.status_code

def fetch_detail(xid):
    r = requests.get(BASE_XID + xid, params={"apikey": API_KEY}, timeout=30)
    r.raise_for_status()
    return r.json()

def pull_category(cat_name, kind_options):
    """Try several 'kinds' options until one works (not 400).
       Returns a list of simplified OTM detail dicts or [] if none work."""
    collected = []
    worked = False
    for kinds in kind_options:
        print(f"[OTM] Trying category={cat_name} kinds={kinds} ...")
        offset = 0
        batch_count = 0
        while True:
            data, code = fetch_bbox(kinds, offset, limit=200)
            if code == 400:
                print(f"[OTM] kinds={kinds} not accepted (400). Trying next candidate.")
                collected = []
                break  # try next kinds candidate
            results = data or []
            if not results:
                if batch_count == 0:
                    print(f"[OTM] kinds={kinds} yielded 0 results.")
                break
            # annotate category
            for x in results:
                x["_bm_category"] = cat_name
            collected.extend(results)
            batch_count += len(results)
            offset += len(results)
            time.sleep(0.25)
        if collected:
            worked = True
            print(f"[OTM] Using kinds={kinds} for category={cat_name} (fetched {len(collected)}).")
            break
    if not worked:
        print(f"[OTM] WARNING: No valid kinds for category={cat_name}. Skipping OTM for this category.")
        return []
    # fetch details to enrich with address/website
    detailed = []
    for x in collected:
        xid = x.get("xid")
        if not xid:
            continue
        try:
            d = fetch_detail(xid)
            lat = (d.get("point") or {}).get("lat")
            lon = (d.get("point") or {}).get("lon")
            addr = d.get("address") or {}
            address = ", ".join(filter(None, [
                addr.get("house_number"),
                addr.get("road"),
                addr.get("suburb"),
                addr.get("city"),
                addr.get("postcode"),
            ])) or None
            detailed.append({
                "xid": xid,
                "name": d.get("name") or x.get("name"),
                "_bm_category": cat_name,
                "location": {"lat": lat, "lon": lon, "address": address},
                "contacts": {"website": d.get("url")},
            })
            time.sleep(0.15)
        except Exception:
            continue
    return detailed

def main():
    all_items = []
    for cat, options in KIND_CANDIDATES.items():
        all_items.extend(pull_category(cat, options))

    with open(OUTDIR/"places.json", "w", encoding="utf-8") as f:
        json.dump(all_items, f, ensure_ascii=False, indent=2)
    print(f"[OTM] Wrote {len(all_items)} detailed records to {OUTDIR/'places.json'}")

if __name__ == "__main__":
    main()
