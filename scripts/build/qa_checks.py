import csv, sys
from .utils import DATA_DIR, read_json

MAX_MISSING_ADDR_PCT = 0.20
MAX_NO_PHOTO_PCT = 0.40

def main():
    places = read_json(DATA_DIR/"places.json", default=[]) or []
    if not places:
        print("No places found; failing QA.")
        sys.exit(2)

    issues = []
    for p in places:
        if not p.get("location", {}).get("address"):
            issues.append({"id": p["id"], "issue": "missing_address"})
        if not p.get("photos"):
            issues.append({"id": p["id"], "issue": "no_photo"})

    out = DATA_DIR.parent / "data_quality_issues.csv"
    with open(out, "w", newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=["id","issue"])
        w.writeheader()
        w.writerows(issues)

    n = len(places)
    miss_addr_pct = sum(1 for i in issues if i["issue"]=="missing_address")/n
    no_photo_pct = sum(1 for i in issues if i["issue"]=="no_photo")/n

    print(f"QA: {n} places | missing_address={miss_addr_pct:.1%} | no_photo={no_photo_pct:.1%}")

    if miss_addr_pct > MAX_MISSING_ADDR_PCT or no_photo_pct > MAX_NO_PHOTO_PCT:
        sys.exit(3)

if __name__ == "__main__":
    main()
