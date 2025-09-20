import json, requests
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTDIR = ROOT / "data/raw/wikidata"
OUTDIR.mkdir(parents=True, exist_ok=True)

SPARQL = """
SELECT ?item ?itemLabel ?coord ?website ?image WHERE {
  ?item wdt:P131* wd:Q842633 .        # Muscat Governorate
  OPTIONAL { ?item wdt:P625 ?coord. }
  OPTIONAL { ?item wdt:P856 ?website. }
  OPTIONAL { ?item wdt:P18 ?image. }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
"""

def main():
    r = requests.get(
        "https://query.wikidata.org/sparql",
        params={"query": SPARQL, "format": "json"},
        headers={"User-Agent": "bestmuscat/1.0"},
        timeout=60,
    )
    r.raise_for_status()
    data = r.json()
    with open(OUTDIR / "muscat.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
