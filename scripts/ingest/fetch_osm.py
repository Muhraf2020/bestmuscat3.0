import json, time, requests
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTDIR = ROOT / "data/raw/osm"
OUTDIR.mkdir(parents=True, exist_ok=True)

# Muscat Governorate-ish bbox (lon_min, lat_min, lon_max, lat_max)
BBOX = (58.20, 23.45, 58.80, 23.80)

# amenity/shop tags we care about
QUERIES = {
    "restaurant": 'node["amenity"="restaurant"]({s});way["amenity"="restaurant"]({s});relation["amenity"="restaurant"]({s});',
    "hotel":      'node["tourism"="hotel"]({s});way["tourism"="hotel"]({s});relation["tourism"="hotel"]({s});',
    "mall":       'node["shop"="mall"]({s});way["shop"="mall"]({s});relation["shop"="mall"]({s});'
}

OVERPASS = "https://overpass-api.de/api/interpreter"

def bbox_str(b):
    return f"{b[1]},{b[0]},{b[3]},{b[2]}"  # lat_min,lon_min,lat_max,lon_max

def fetch(query):
    data = {"data": query}
    r = requests.post(OVERPASS, data=data, timeout=120, headers={"User-Agent":"bestmuscat/1.0"})
    r.raise_for_status()
    return r.json()

def main():
    bboxS = bbox_str(BBOX)
    results = []
    for cat, body in QUERIES.items():
        q = f'[out:json][timeout:120];({body.format(s=bboxS)});out center tags;'
        data = fetch(q)
        for el in data.get("elements", []):
            lat, lon = None, None
            if "lat" in el and "lon" in el:
                lat, lon = el["lat"], el["lon"]
            elif "center" in el:
                lat, lon = el["center"]["lat"], el["center"]["lon"]
            name = (el.get("tags", {}) or {}).get("name")
            if not name or lat is None or lon is None:
                continue
            addr = []
            tags = el.get("tags", {})
            for k in ["addr:housenumber","addr:street","addr:suburb","addr:city","addr:postcode"]:
                v = tags.get(k)
                if v: addr.append(v)
            address = ", ".join(addr) or None
            results.append({
                "id": f"osm:{el.get('type')}:{el.get('id')}",
                "name": name,
                "category": cat,
                "location": {"lat": lat, "lon": lon, "address": address},
                "contacts": {"website": tags.get("website")},
                "sources": {"osm": {"id": f"{el.get('type')}/{el.get('id')}" }}
            })
        time.sleep(1.0)  # be polite
    with open(OUTDIR/"places.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
