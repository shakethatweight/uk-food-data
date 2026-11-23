# uk-food-data

A slim, UK-only extract of the [Open Food Facts](https://world.openfoodfacts.org) product database, refreshed weekly and published as GitHub Release assets. It exists so apps (we use it for the MyJurnee food diary) can look up calories and macros by barcode without carrying the 1.5 GB full export.

**The data file is a Release asset, never committed to git.** Grab the latest from the [Releases page](../../releases/latest): `off-uk-YYYY-MM-DD.csv.gz` plus `stats.json` (row counts in, kept and dropped by reason). The last 8 releases are kept.

## Source and filters

Built from the official Open Food Facts CSV export (`en.openfoodfacts.org.products.csv.gz`, tab-separated, streamed without unpacking).

- UK only: `countries_tags` contains `en:united-kingdom`.
- Barcode must be digits only with a valid GTIN check digit: EAN-8, UPC-A or EAN-13. GTIN-14 (trade units such as outer cases) is dropped as `bad_barcode`, since no consumer pack carries one.
- Must have a product name.
- Must have kcal, protein, carbs and fat; kcal between 0 and 900; protein + carbs + fat no more than 105 g per 100 g.
- One row per barcode (latest `last_modified_t` wins).

## File format

gzipped UTF-8 CSV, RFC 4180 (CRLF line ends), header row, one row per product. Nutrients are per 100 g (or per 100 ml when `unit` is `ml`).

| Column | Notes |
|---|---|
| `barcode` | digits, 8, 12 or 13 chars (leading zeros kept; the file is text) |
| `name` | `product_name`, whitespace collapsed, max 191 chars |
| `brand` | first brand only, max 100 chars, may be empty |
| `unit` | `ml` if the pack quantity is a volume (ml/cl/dl/l), else `g` |
| `kcal` | integer; from `energy-kcal_100g`, else `energy-kj_100g` / 4.184 |
| `protein`, `carbs`, `sugars`, `fat`, `saturates`, `fibre` | grams, 1 dp; empty if unknown (sugars/saturates/fibre may be empty) |
| `salt` | grams, **2 dp** (0.05 g matters); empty if unknown. Falls back to sodium x 2.5 |
| `serving_qty` | grams/ml from `serving_quantity` if 0 < x <= 2000, else empty |
| `serving_label` | `serving_size` text, max 60 chars, may be empty |
| `source_updated` | `last_modified_t` as `YYYY-MM-DD` (UTC) |

**Rounding** is half away from zero on the value's decimal text (0.25 to 1 dp is 0.3, 80.5 kcal is 81, 0.125 salt is 0.13), not Python's round-half-to-even or the binary value. This is the rule of the MyJurnee API contract, and the WordPress side (`STW_MJ_Food_Off::round_half_up()`) uses the same one, so a live lookup and this file give identical rows. `serving_qty` is rounded to 1 dp and written without trailing zeros (`207`, `33.3`).

Note: the export has no `product_name_en` or `nutrition_data_per` columns, so `name` uses `product_name` and `unit` is inferred from the pack `quantity` text.

## Running it

```
bin/publish.sh            # download, build, create the GitHub Release, prune to 8
python3 bin/build-off-uk.py --download /path/to/workdir --outdir /path/to/out   # build only
python3 bin/build-off-uk.py --input export.csv.gz --outdir out                  # from a local copy
```

Needs Python 3.9+ (standard library only) and, for `publish.sh`, an authenticated `gh` and `systemd-run --user` (the build runs in a 1.5 GB memory-capped cgroup). The raw download is deleted after a successful build.

## Changelog

- **1.0.3**: kcal, `serving_qty` and the 1 dp / 2 dp nutrients round half away from zero on the decimal text. Before, Python's `round()` (kcal, serving) and `%.1f` / `%.2f` (grams) rounded ties to even on the binary value, so 80.5 kcal gave 80 and 0.25 g gave 0.2, which disagreed with the live lookup and the API contract. Adds `tests/test_rounding.py`.
- **1.0.2**: `salt` is written to 2 dp (was 1 dp, which lost values like 0.05 g). Other grams stay 1 dp, kcal an integer.
- **1.0.1**: GTIN-14 (trade-unit) barcodes are dropped.
- **1.0.0**: first release.

## Licence

- The data is derived from Open Food Facts and is made available under the [Open Database License (ODbL) 1.0](LICENSE-DATA.md); individual contents under the [Database Contents License (DbCL) 1.0](https://opendatacommons.org/licenses/dbcl/1-0/).
- **Attribution:** Contains data from Open Food Facts, available under the Open Database License. See https://world.openfoodfacts.org/data.
- The scripts in this repository are MIT licensed ([LICENSE](LICENSE)).
