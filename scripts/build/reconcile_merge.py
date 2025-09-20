import sys, json
from pathlib import Path
from rapidfuzz import fuzz

# Make 'scripts/build' importable to use utils.py
HERE = Path(__file__).resolve().parent
sys.path.append(str(HERE))
from utils import (
    DATA_DIR, RAW_DIR, write_json, read_json,
    slugify, haversine_m, norm_name, load_taxonomy
)

OUT = DATA_DIR / "places.json"
TARGET_CATEGORIES = {"hotel", "restaurant", "mall"}

def extract_otm():
    path = RAW_DIR / "opentripmap/places.json"
    items = read_json(path, default=[]) or []
    mapped = []
    for r in items:
        name = r.get("name") or r.get("name_en")
        lat, lon = r.get("point", {}).get("lat"), r.get("point", {}).get("lon")
        cat = r.get("_bm_category")
        if not name or lat is None or lon is None or cat not in TARGET_CATEGORIES:
            continue
        mapped.append({
            "name": name,
            "category": cat,
            "location": {"lat": lat, "lon": lon, "address": None},
            "contacts": {"phone": None, "website": None},
            "open_hours": None,
            "price_tier": None,
            "rating": {"score": None, "count": None},
            "sources": {"opentripmap": {"id": r.get("xid")}}
        })
    return mapped

def extract_osm():
    path = RAW_DIR / "osm/places.json"
    items = read_json(path, default=[]) or []
    mapped = []
    for r in items:
        name = r.get("name")
        lat, lon = r.get("lat"), r.get("lon")
        cat = r.get("_bm_category")
        if not name or lat is None or lon is None or cat not in TARGET_CATEGORIES:
            continue
        address = r.get("address") or r.get("street")
        mapped.append({
            "name": name,
            "category": cat,
            "location": {"lat": lat, "lon": lon, "address": address},
            "contacts": {"phone": r.get("phone"), "website": r.get("website")},
            "open_hours": None,
            "price_tier": None,
            "rating": {"score": None, "count": None},
            "sources": {"osm": {"type": r.get("osm_type"), "id": r.get("osm_id")}}
        })
    return mapped

def extract_wd():
    path = RAW_DIR / "wikidata/muscat.json"
    data = read_json(path, default=None)
    if not data:
        return []
    rows = data.get("results", {}).get("bindings", [])
    mapped = []
    for b in rows:
        name = b.get("itemLabel", {}).get("value")
        coord = b.get("coord", {}).get("value")
        lat = lon = None
        if coord and coord.startswith("Point("):
            try:
                s = coord[6:-1].split()
                lon = float(s[0]); lat = float(s[1])
            except Exception:
                pass
        if not name or lat is None or lon is None:
            continue
        mapped.append({
            "name": name,
            "category": None,
            "location": {"lat": lat, "lon": lon, "address": None},
            "contacts": {"website": (b.get("website", {}) or {}).get("value")},
            "wikimedia_image_url": (b.get("image", {}) or {}).get("value"),
            "sources": {"wikidata": {"id": (b.get("item", {}) or {}).get("value")}}
        })
    return mapped

def reconcile_and_merge():
    _ = load_taxonomy()
    otm = extract_otm()
    osm = extract_osm()
    wd  = extract_wd()

    merged = []  # seed empty

    def try_merge(target, candidate):
        n1, n2 = norm_name(target["name"]), norm_name(candidate["name"])
        name_sim = fuzz.token_sort_ratio(n1, n2) / 100.0
        d = haversine_m(target["location"]["lat"], target["location"]["lon"],
                        candidate["location"]["lat"], candidate["location"]["lon"])
        if name_sim >= 0.85 and d <= 200:
            target["contacts"]["website"] = target["contacts"].get("website") or candidate.get("contacts", {}).get("website")
            target["contacts"]["phone"] = target["contacts"].get("phone") or candidate.get("contacts", {}).get("phone")
            target["location"]["address"] = target["location"].get("address") or candidate.get("location", {}).get("address")
            target["price_tier"] = target.get("price_tier") or candidate.get("price_tier")
            target["rating"] = target.get("rating") or candidate.get("rating")
            ts = target.setdefault("sources", {})
            for k, v in candidate.get("sources", {}).items():
                ts[k] = v
            if candidate.get("wikimedia_image_url") and not target.get("wikimedia_image_url"):
                target["wikimedia_image_url"] = candidate["wikimedia_image_url"]
            return True
        return False

    def merge_list(source_list):
        for c in source_list:
            for t in merged:
                if try_merge(t, c):
                    break
            else:
                merged.append(c)

    # Merge OTM then OSM; enrich with WD
    merge_list(otm)
    merge_list(osm)

    for c in wd:
        best_i, best_score = None, 0
        for i, t in enumerate(merged):
            d = haversine_m(t["location"]["lat"], t["location"]["lon"], c["location"]["lat"], c["location"]["lon"])
            if d > 120:
                continue
            n1, n2 = norm_name(t["name"]), norm_name(c["name"])
            sim = fuzz.token_sort_ratio(n1, n2) / 100.0
            score = sim + (1 - min(d/120, 1)) * 0.2
            if score > best_score:
                best_score, best_i = score, i
        if best_i is not None:
            t = merged[best_i]
            if c.get("contacts", {}).get("website") and not t["contacts"].get("website"):
                t["contacts"]["website"] = c["contacts"]["website"]
            if c.get("wikimedia_image_url") and not t.get("wikimedia_image_url"):
                t["wikimedia_image_url"] = c["wikimedia_image_url"]
            t.setdefault("sources", {}).update(c.get("sources", {}))

    canonical = []
    for p in merged:
        if p.get("category") not in TARGET_CATEGORIES:
            if p.get("category") is None:
                nm = norm_name(p["name"])
                cat = None
                if any(k in nm for k in ["hotel", "resort"]): cat = "hotel"
                elif any(k in nm for k in ["mall", "centre", "center"]): cat = "mall"
                elif any(k in nm for k in ["restaurant", "cafe", "diner", "grill", "bistro"]): cat = "restaurant"
                p["category"] = cat
            if p.get("category") not in TARGET_CATEGORIES:
                continue

        slug = slugify(p["name"])[:80]

        # Ensure both lon and lng for frontend compatibility
        loc_in = p["location"] or {}
        lat = loc_in.get("lat")
        lon = loc_in.get("lon")
        address = loc_in.get("address")
        location_out = {"lat": lat, "lon": lon, "lng": lon, "address": address}

        canonical.append({
            "id": f"bestmuscat:{p['category']}:{slug}",
            "name": p["name"],
            "category": p["category"],
            "subcategories": [],
            "location": location_out,
            "contacts": p.get("contacts", {}),
            "open_hours": p.get("open_hours"),
            "price_tier": p.get("price_tier"),
            "rating": p.get("rating", {}),
            "amenities": [],
            "photos": [],
            "wikimedia_image_url": p.get("wikimedia_image_url"),
            "sources": p.get("sources", {}),
            "status": "active"
        })

    write_json(OUT, canonical)
    print(f"Wrote {len(canonical)} places → {OUT}")

if __name__ == "__main__":
    reconcile_and_merge()
