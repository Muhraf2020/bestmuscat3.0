import os, json, requests
from io import BytesIO
from PIL import Image
from pathlib import Path

from .utils import DATA_DIR, MEDIA_DIR, read_json, write_json

OPENVERSE_ENDPOINT = "https://api.openverse.org/v1/images/"

def _download_image(url: str) -> Image.Image:
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    img = Image.open(BytesIO(r.content))
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")
    return img

def _save_variants(img: Image.Image, outdir: Path):
    outdir.mkdir(parents=True, exist_ok=True)
    im = img.copy(); im.thumbnail((1600, 1200)); im.save(outdir/"hero.webp", "WEBP", quality=85)
    im = img.copy(); im.thumbnail((640, 480));   im.save(outdir/"thumb.webp", "WEBP", quality=82)
    im = img.copy(); im.thumbnail((1200, 630));  im.save(outdir/"social.jpg", "JPEG", quality=86)

def _search_openverse(q: str):
    params = {
        "q": q,
        "license_type": "commercial",
        "page_size": 5,
        "format": "json"
    }
    try:
        r = requests.get(OPENVERSE_ENDPOINT, params=params, timeout=20, headers={"User-Agent":"bestmuscat/1.0"})
        r.raise_for_status()
        return r.json().get("results", [])
    except Exception:
        return []

def add_photos():
    places = read_json(DATA_DIR/"places.json", default=[]) or []
    changed = False

    for p in places:
        if p.get("photos"):
            continue  # already has photos
        img = None
        at_meta = None

        # 1) Wikimedia via Wikidata image URL
        wm = p.get("wikimedia_image_url")
        if wm:
            try:
                img = _download_image(wm)
                at_meta = {
                    "license": "See Wikimedia page",
                    "attribution": "Wikimedia Commons",
                    "source_url": wm
                }
            except Exception:
                img = None

        # 2) Openverse fallback (city+name+category)
        if img is None:
            q = f"{p['name']} Muscat {p['category']}"
            res = _search_openverse(q)
            if res:
                for r in res:
                    url = r.get("url") or r.get("thumbnail")
                    if not url:
                        continue
                    try:
                        img = _download_image(url)
                        at_meta = {
                            "license": r.get("license"),
                            "attribution": (r.get("creator") or "Unknown"),
                            "source_url": r.get("foreign_landing_url") or r.get("url")
                        }
                        break
                    except Exception:
                        continue

        if img is None:
            continue  # leave without photo

        slug = p["id"].split(":")[-1]
        outdir = MEDIA_DIR / slug
        _save_variants(img, outdir)

        p.setdefault("photos", []).append({
            "type": "hero",
            "src": f"data/media/{slug}/hero.webp",
            "license": at_meta.get("license"),
            "attribution": at_meta.get("attribution"),
            "source_url": at_meta.get("source_url")
        })

        changed = True

    if changed:
        write_json(DATA_DIR/"places.json", places)
        print("Updated places.json with photo metadata")
    else:
        print("No photo updates were necessary")

if __name__ == "__main__":
    add_photos()
