import json, time, requests
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTDIR = ROOT / "data/raw/osm"
OUTDIR.mkdir(parents=True, exist_ok=True)

# Muscat bbox (approx) — lon_min, lat_min, lon_max, lat_max
BBOX = (58.20, 23.45, 58.80, 23.80)

# OSM tags to fetch
QUERIES = {
    "restaurant": [
        'node["amenity"~"restaurant|cafe|fast_food"]({lat_min},{lon_min},{lat_max},{lon_max});',
        'way["amenity"~"restaurant|cafe|fast_food"]({lat_min},{lon_min},{lat_max},{lon_max});',
        'relation["amenity"~"restaurant|cafe|fast_food"]({lat_min},{lon_min},{lat_max},{lon_max});'
    ],
    "hotel": [
        'node["tourism"~"hotel|guest_house|hostel|motel|resort"]({lat_min},{lon_min},{lat_max},{lon_max});',
        'way["tourism"~"hotel|guest_house|hostel|motel|resort"]({lat_min},{lon_min},{lat_max},{lon_max});',
        'relation["tourism"~"hotel|guest_house|hostel|motel|resort"]({lat_min},{lon_min},{lat_max},{lon_max});'
    ],
    "mall": [
        'node["shop"="mall"]({lat_min},{lon_min},{lat_max},{lon_max});',
        'way["shop"="mall"]({lat_min},{lon_min},{lat_max},{lon_max});',
        'relation["shop"="mall"]({lat_min},{lon_min},{lat_max},{lon_max});',
        'node["amenity"="marketplace"]({lat_min},{lon_min},{lat_max},{lon_max});',
        'way["amenity"="marketplace"]({lat_min},{lon_min},{lat_max},{lon_max});',
        'relation["amenity"="marketplace"]({lat_min},{lon_min},{lat_max},{lon_max});'
    ]
}

OVERPASS = "https://overpass-api.de/api/interpreter"

def build_query(blocks):
    lat_min, lon_min, lat_max, lon_max = BBOX[1], BBOX[0], BBOX[3], BBOX[2]
    body = "".join([b.format(lat_min=lat_min, lon_min=lon_min, lat_max=lat_max, lon_max=lon_max) for b in blocks])
    return f"""
    [out:json][timeout:90];
    (
      {body}
    );
    out center tags;
    """

def fetch(category):
    q = build_query(QUERIES[category])
    r = requests.post(OVERPASS, data={"data": q}, timeout=120, headers={"User-Agent":"bestmuscat/1.0"})
    r.raise_for_status()
    return r.json()

def main():
    all_items = []
    for cat in QUERIES.keys():
        try:
            data = fetch(cat)
            for el in data.get("elements", []):
                lat = el.get("lat") or (el.get("center") or {}).get("lat")
                lon = el.get("lon") or (el.get("center") or {}).get("lon")
                if lat is None or lon is None:
                    continue
                nm = (el.get("tags") or {}).get("name") or (el.get("tags") or {}).get("name:en")
                item = {
                    "_bm_category": cat,
                    "name": nm,
                    "lat": lat,
                    "lon": lon,
                    "address": (el.get("tags") or {}).get("addr:full"),
                    "street": (el.get("tags") or {}).get("addr:street"),
                    "postcode": (el.get("tags") or {}).get("addr:postcode"),
                    "city": (el.get("tags") or {}).get("addr:city"),
                    "phone": (el.get("tags") or {}).get("contact:phone") or (el.get("tags") or {}).get("phone"),
                    "website": (el.get("tags") or {}).get("contact:website") or (el.get("tags") or {}).get("website"),
                    "osm_type": el.get("type"),
                    "osm_id": el.get("id"),
                    "tags": el.get("tags", {})
                }
                all_items.append(item)
            time.sleep(1.0)  # be polite to Overpass
        except Exception as e:
            print(f"OSM fetch error for {cat}: {e}")

    with open(OUTDIR / "places.json", "w", encoding="utf-8") as f:
        json.dump(all_items, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
