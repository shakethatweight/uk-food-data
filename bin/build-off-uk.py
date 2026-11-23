#!/usr/bin/env python3
"""Build a slim UK-only CSV from the Open Food Facts CSV export (streamed, no unpacking).

Usage: build-off-uk.py (--input FILE.csv.gz | --download WORKDIR) --outdir DIR

Writes DIR/off-uk-YYYY-MM-DD.csv.gz and DIR/stats.json.
Contains data from Open Food Facts, available under the Open Database License.
"""
import argparse
import csv
import datetime
import gzip
import io
import json
import os
import re
import resource
import sys
import urllib.request

EXPORT_URL = "https://static.openfoodfacts.org/data/en.openfoodfacts.org.products.csv.gz"
USER_AGENT = "MyJurnee-UKFoodData/1.0 (dev@shakethatweight.co.uk)"
COLUMNS = ["barcode", "name", "brand", "unit", "kcal", "protein", "carbs", "sugars", "fat",
           "saturates", "fibre", "salt", "serving_qty", "serving_label", "source_updated"]
LIQUID_RE = re.compile(r"\d\s*(ml|cl|dl|l|litres?|liters?)\.?\s*(e|℮)?\s*$", re.I)
WS_RE = re.compile(r"\s+")


def download(workdir):
    os.makedirs(workdir, exist_ok=True)
    dest = os.path.join(workdir, "en.openfoodfacts.org.products.csv.gz")
    req = urllib.request.Request(EXPORT_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as r, open(dest + ".part", "wb") as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
    os.rename(dest + ".part", dest)
    return dest


def valid_gtin(code):
    # EAN-8, UPC-A and EAN-13 only: what a phone scans on a consumer pack and what
    # the WordPress importer accepts. GTIN-14 marks trade units (outer cases).
    if not code.isdigit() or len(code) not in (8, 12, 13):
        return False
    digits = [int(c) for c in code]
    check = digits.pop()
    total = sum(d * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(digits)))
    return (10 - total % 10) % 10 == check


def num(row, key):
    v = row.get(key)
    if v is None or v == "":
        return None
    try:
        f = float(v)
    except ValueError:
        return None
    if f != f or f in (float("inf"), float("-inf")):
        return None
    return f


def g1(v):
    return "" if v is None else "%.1f" % v


def g2(v):
    # Salt only: 0.05 g per 100 g matters on a food diary, so it keeps 2 dp.
    return "" if v is None else "%.2f" % v


def clean(s, maxlen):
    s = WS_RE.sub(" ", (s or "").replace("\x00", "")).strip()
    return s[:maxlen].strip()


def process_row(row):
    """Return (drop_reason, None) or (None, (last_modified_ts, csv_row))."""
    code = (row.get("code") or "").strip()
    if not valid_gtin(code):
        return "bad_barcode", None
    name = clean(row.get("product_name_en") or row.get("product_name"), 191)
    if not name:
        return "no_name", None
    kcal = num(row, "energy-kcal_100g")
    if kcal is None:
        kj = num(row, "energy-kj_100g")
        if kj is not None:
            kcal = kj / 4.184
    protein = num(row, "proteins_100g")
    carbs = num(row, "carbohydrates_100g")
    fat = num(row, "fat_100g")
    if kcal is None or protein is None or carbs is None or fat is None:
        return "missing_macros", None
    if kcal < 0 or kcal > 900:
        return "kcal_out_of_range", None
    if min(protein, carbs, fat) < 0 or protein + carbs + fat > 105:
        return "macros_implausible", None
    salt = num(row, "salt_100g")
    if salt is None:
        sodium = num(row, "sodium_100g")
        if sodium is not None:
            salt = sodium * 2.5
    brand = clean((row.get("brands") or "").split(",")[0], 100)
    unit = "ml" if LIQUID_RE.search(row.get("quantity") or "") else "g"
    sq = num(row, "serving_quantity")
    serving_qty = ("%g" % round(sq, 1)) if sq is not None and 0 < sq <= 2000 else ""
    try:
        ts = int(row.get("last_modified_t") or 0)
    except ValueError:
        ts = 0
    updated = datetime.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d") if ts > 0 else ""
    out = [code, name, brand, unit, str(int(round(kcal))), g1(protein), g1(carbs),
           g1(num(row, "sugars_100g")), g1(fat), g1(num(row, "saturated-fat_100g")),
           g1(num(row, "fiber_100g")), g2(salt), serving_qty,
           clean(row.get("serving_size"), 60), updated]
    return None, (ts, out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input")
    ap.add_argument("--download", metavar="WORKDIR")
    ap.add_argument("--outdir", required=True)
    args = ap.parse_args()
    path = args.input or (download(args.download) if args.download else None)
    if not path:
        ap.error("need --input or --download")
    os.makedirs(args.outdir, exist_ok=True)
    csv.field_size_limit(1 << 28)

    stats = {"rows_total": 0, "rows_uk": 0, "dropped": {}, "duplicates_removed": 0}
    best = {}  # barcode -> (ts, row)
    with gzip.open(path, "rb") as raw:
        text = io.TextIOWrapper(raw, encoding="utf-8", errors="replace", newline="")
        # The export occasionally contains NUL bytes, which csv rejects
        lines = (line.replace("\x00", "") for line in text)
        reader = csv.DictReader(lines, delimiter="\t", quoting=csv.QUOTE_NONE)
        for row in reader:
            stats["rows_total"] += 1
            if "en:united-kingdom" not in (row.get("countries_tags") or "").split(","):
                continue
            stats["rows_uk"] += 1
            reason, res = process_row(row)
            if reason:
                stats["dropped"][reason] = stats["dropped"].get(reason, 0) + 1
                continue
            ts, out = res
            prev = best.get(out[0])
            if prev is not None:
                stats["duplicates_removed"] += 1
                if prev[0] >= ts:
                    continue
            best[out[0]] = (ts, out)

    today = datetime.datetime.now().strftime("%Y-%m-%d")
    out_path = os.path.join(args.outdir, "off-uk-%s.csv.gz" % today)
    with gzip.open(out_path + ".part", "wt", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\r\n", quoting=csv.QUOTE_MINIMAL)
        w.writerow(COLUMNS)
        for code in sorted(best):
            w.writerow(best[code][1])
    os.rename(out_path + ".part", out_path)
    stats["rows_kept"] = len(best)
    stats["file"] = os.path.basename(out_path)
    stats["bytes"] = os.path.getsize(out_path)
    stats["built"] = today
    stats["peak_rss_mb"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)
    stats["attribution"] = "Contains data from Open Food Facts, available under the Open Database License"
    with open(os.path.join(args.outdir, "stats.json"), "w") as f:
        json.dump(stats, f, indent=2)
    print(json.dumps(stats, indent=2))
    if args.download:
        os.remove(path)


if __name__ == "__main__":
    sys.exit(main())
