import json
from pathlib import Path
from rapidfuzz import fuzz

from .utils import (
    ROOT, DATA_DIR, RAW_DIR, write_json, read_json,
    slugify, haversine_m, norm_name, load_taxonomy
)

OUT = DATA_DIR / "places.json"
TARGET_CATEGORIES = {"hotel", "restaurant", "mall"}

def extract_otm():
    path = RAW_DIR / "opentripmap/places.json"
    items = read_json(path, default=[]) or []
    mapped = []
    for r in items:
        name = r.get("name")
        loc = r.get("location") or {}
        lat, lon = loc.get("lat"), loc.get("lon")
        cat = r.get("_bm_category")
        if not name or lat is None or lon is None or cat not in TARGET_CATEGORIES:
            continue
        mapped.append({
            "name": name,
            "category": cat,
            "location": {"lat": lat, "lon": lon, "address": loc.get("address")},
            "contacts": {"website": (r.get("contacts") or {}).get("website")},
            "sources": {"opentripmap": {"id": r.get("xid")}}
        })
    return mapped

def extract_osm():
    path = RAW_DIR / "osm/places.json"
    items = read_json(path, default=[]) or []
    mapped = []
    for r in items:
        name = r.get("name")
        cat  = r.get("category")
        loc  = r.get("location") or {}
        lat, lon = loc.get("lat"), loc.get("lon")
        if not name or lat is None or lon is None or cat not in TARGET_CATEGORIES:
            continue
        mapped.append({
            "name": name,
            "category": cat,
            "location": {"lat": lat, "lon": lon, "address": loc.get("address")},
            "contacts": {"website": (r.get("contacts") or {}).get("website")},
            "sources": {"osm": r.get("sources",{}).get("osm")}
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
        name = b.get("itemLabel",{}).get("value")
        coord = b.get("coord",{}).get("value")
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
            "location": {"lat": lat, "lon": lon, "address": None},
            "contacts": {"website": (b.get("website",{}) or {}).get("value")},
            "wikimedia_image_url": (b.get("image",{}) or {}).get("value"),
            "sources": {"wikidata": {"id": (b.get("item",{}) or {}).get("value")}}
        })
    return mapped

def reconcile_and_merge():
    otm = extract_otm()  # now includes addresses
    osm = extract_osm()  # good for addresses
    wd  = extract_wd()   # websites + possible images

    merged = []

    # seed with OSM (addresses) then enrich with OTM (maybe website) and WD (website/image)
    for p in osm:
        merged.append(p)

    def try_merge(target, candidate, dist=200, sim_thr=0.85):
        n1, n2 = norm_name(target["name"]), norm_name(candidate["name"])
        name_sim = fuzz.token_sort_ratio(n1, n2) / 100.0
        d = haversine_m(target["location"]["lat"], target["location"]["lon"],
                        candidate["location"]["lat"], candidate["location"]["lon"])
        if name_sim >= sim_thr and d <= dist:
            # prefer non-empty fields, keep best
            target["location"]["address"] = target["location"].get("address") or candidate.get("location",{}).get("address")
            tweb = target.get("contacts",{}).get("website")
            cweb = candidate.get("contacts",{}).get("website")
            if not tweb and cweb:
                target.setdefault("contacts",{})["website"] = cweb
            ts = target.setdefault("sources",{})
            for k,v in candidate.get("sources",{}).items():
                ts[k] = v
            if candidate.get("wikimedia_image_url") and not target.get("wikimedia_image_url"):
                target["wikimedia_image_url"] = candidate["wikimedia_image_url"]
            return True
        return False

    # merge OTM into OSM-seeded list
    for c in otm:
        matched = False
        for t in merged:
            if t["category"] != c["category"]:
                continue
            if try_merge(t, c):
                matched = True
                break
        if not matched:
            merged.append(c)

    # WD enrichment (tight distance)
    for c in wd:
        # find nearest by category-agnostic enrichment, but close by
        best_i, best_score = None, 0
        for i, t in enumerate(merged):
            d = haversine_m(t["location"]["lat"], t["location"]["lon"], c["location"]["lat"], c["location"]["lon"])
            if d > 120:
                continue
            sim = fuzz.token_sort_ratio(norm_name(t["name"]), norm_name(c["name"])) / 100.0
            score = sim + (1 - min(d/120,1)) * 0.2
            if score > best_score:
                best_score, best_i = score, i
        if best_i is not None:
            t = merged[best_i]
            if c.get("contacts",{}).get("website") and not t.get("contacts",{}).get("website"):
                t.setdefault("contacts",{})["website"] = c["contacts"]["website"]
            if c.get("wikimedia_image_url") and not t.get("wikimedia_image_url"):
                t["wikimedia_image_url"] = c["wikimedia_image_url"]
            t.setdefault("sources",{}).update(c.get("sources",{}))

    # finalize
    canonical = []
    for p in merged:
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
            "open_hours": None,
            "price_tier": None,
            "rating": {},
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
