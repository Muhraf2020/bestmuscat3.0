# scripts/build/generate_tools_from_places.py
from pathlib import Path
import json

# Reuse paths used elsewhere in your repo
ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"

PLACES = DATA / "places.json"
TOOLS  = DATA / "tools.json"

# UI expects these category names
CAT_MAP = {
    "hotel": "Hotels",
    "restaurant": "Restaurants",
    "mall": "Malls",
}

# Fallback images you already have in /assets/images
FALLBACK_IMG = {
    "hotel": "assets/images/hotels.png",
    "restaurant": "assets/images/restaurants.png",
    "mall": "assets/images/malls.png",
}

def main():
    if not PLACES.exists():
        raise SystemExit("places.json not found; run reconcile step first")

    places = json.loads(PLACES.read_text(encoding="utf-8"))

    tools = []
    for p in places:
        cat_key = (p.get("category") or "").strip().lower()
        cat_ui  = CAT_MAP.get(cat_key)
        if not cat_ui:
            # only export categories your UI supports
            continue

        # slug from id "bestmuscat:category:slug"
        pid = p.get("id") or ""
        slug = pid.split(":")[-1] if ":" in pid else pid

        # prefer our hero image, otherwise fallback per category
        img = None
        photos = p.get("photos") or []
        if photos and isinstance(photos, list):
            img = photos[0].get("src")
        if not img:
            img = FALLBACK_IMG[cat_key]

        # subtitle line on your cards uses tagline/description
        address = (p.get("location") or {}).get("address") or ""
        tagline = address or f"{CAT_MAP[cat_key]} in Muscat"

        website = (p.get("contacts") or {}).get("website") or "#"

        tools.append({
            "id": slug,
            "slug": slug,
            "name": p.get("name") or slug,
            "url": website,
            "tagline": tagline,
            "description": "",           # optional for your UI; empty is fine
            "pricing": "free",           # neutral default
            "categories": [cat_ui],      # your UI expects exactly one of its 6
            "tags": [],                  # you can enrich later
            "logo": "",                  # optional
            "image": img,                # used for the card hero image
            "short_description": tagline,
            "price": ""
        })

    TOOLS.write_text(json.dumps(tools, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(tools)} items → {TOOLS}")

if __name__ == "__main__":
    main()
