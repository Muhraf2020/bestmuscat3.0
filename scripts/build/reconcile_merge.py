import json
from pathlib import Path
from rapidfuzz import fuzz
from dateutil import parser as dt  # kept for future enrichment

from .utils import (
    DATA_DIR, RAW_DIR, write_json, read_json,
    slugify, haversine_m, norm_name, load_taxonomy
)

OUT = DATA_DIR / "places.json"
TARGET_CATEGORIES = {"hotel", "restaurant", "mall"}

def extract_fsq():
    path = RAW_DIR / "foursquare/places.json"
    items = read_json(path, default=[]) or []
    mapped = []
    for r in items:
        name = r.get("name")
        geoc = r.get("geocodes", {}).get("main", {})
        lat, lon = geoc.get("latitude"), geoc.get("longitude")
        cat = r.get("_bm_category")
        if not name or not lat or not lon or cat not in TARGET_CATEGORIES:
            continue
        mapped.append({
            "name": name,
            "category": cat,
            "location": {
                "lat": lat,
                "lon": lon,
                "address": ", ".join(filter(None, [
                    (r.get("location", {}) or {}).get("address"),
                    (r.get("location", {}) or {}).get("locality"),
                ]))
            },
            "contacts": {
                "phone": r.get("tel"),
                "website": (r.get("website") or (r.get("link") if isinstance(r.get("link"), str) else None))
            },
            "open_hours": None,
            "price_tier": r.get("price"),
            "rating": {"score": None, "count": r.get("stats", {}).get("total_ratings")},
            "sources": {"foursquare": {"id": r.get("fsq_id")}}
        })
    return mapped

def extract_otm():
    path = RAW_DIR / "opentripmap/places.json"
    items = read_json(path, default=[]) or []
    mapped = []
    for r in items:
        name = r.get("name") or r.get("name_en")
        lat, lon = r.get("point", {}).get("lat"), r.get("point", {}).get("lon")
        cat = r.get("_bm_category")
        if not name or not lat or not lon or cat not in TARGET_CATEGORIES:
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
    _ = load_taxonomy()  # ready for future use
    fsq = extract_fsq()
    otm = extract_otm()
    wd  = extract_wd()

    merged = list(fsq)  # seed with FSQ

    def try_merge(target, candidate):
        n1, n2 = norm_name(target["name"]), norm_name(candidate["name"])
        name_sim = fuzz.token_sort_ratio(n1, n2) / 100.0
        d = haversine_m(target["location"]["lat"], target["location"]["lon"],
                        candidate["location"]["lat"], candidate["location"]["lon"])
        if name_sim >= 0.85 and d <= 200:
            target["contacts"]["website"] = target["contacts"].get("website") or candidate.get("contacts", {}).get("website")
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

    for c in otm:
        for t in merged:
            if try_merge(t, c):
                break
        else:
            merged.append(c)

    # Wikidata enrich only (do not append new POIs)
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
        canonical.append({
            "id": f"bestmuscat:{p['category']}:{slug}",
            "name": p["name"],
            "category": p["category"],
            "subcategories": [],
            "location": p["location"],
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
