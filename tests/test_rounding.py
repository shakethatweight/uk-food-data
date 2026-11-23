"""Rounding of the extractor: half away from zero on the decimal text (python3 -I tests/test_rounding.py).

The same table is in the WordPress plugin's tests/run.php (STW_MJ_Food_Off::round_half_up):
the two must agree, so a live lookup and the bulk file give the same row.
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("build_off_uk", os.path.join(HERE, "..", "bin", "build-off-uk.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

TIES = [
    (0.25, 1, "0.3"), (0.35, 1, "0.4"), (0.15, 1, "0.2"), (2.675, 2, "2.68"), (0.125, 2, "0.13"),
    (0.285, 2, "0.29"), (1.005, 2, "1.01"), (0.05, 1, "0.1"), (0.045, 2, "0.05"), (0.04, 1, "0.0"),
    (80.5, 0, "81"), (0.5, 0, "1"), (1.5, 0, "2"), (2.5, 0, "3"), (33.25, 1, "33.3"),
    (12.0, 1, "12.0"), (0.0, 2, "0.00"), (207.0, 1, "207.0"), (99.95, 1, "100.0"),
    (-0.25, 1, "-0.3"), (-0.04, 1, "0.0"), (-2.5, 0, "-3"), (123456.785, 2, "123456.79"),
]

failures = 0
for value, places, expected in TIES:
    actual = format(mod.round_half_up(value, places), "f")
    if actual != expected:
        failures += 1
        print("FAIL round_half_up(%r, %d): expected %s, got %s" % (value, places, expected, actual))


def check(label, actual, expected):
    global failures
    if actual != expected:
        failures += 1
        print("FAIL %s: expected %r, got %r" % (label, expected, actual))


check("g1 tie", mod.g1(0.25), "0.3")
check("g2 tie", mod.g2(0.125), "0.13")
check("g1 unknown", mod.g1(None), "")
check("serving 33.25", mod.serving_text(33.25), "33.3")
check("serving 207", mod.serving_text(207.0), "207")
check("serving 12.0", mod.serving_text(12.0), "12")
check("serving 0.04", mod.serving_text(0.04), "0")
check("serving 2000", mod.serving_text(2000.0), "2000")


def row(**kw):
    base = {"code": "5000157024671", "product_name": "Beanz", "brands": "Heinz", "quantity": "415g",
            "energy-kcal_100g": "80.5", "proteins_100g": "4.25", "carbohydrates_100g": "15.35",
            "fat_100g": "0.4", "sugars_100g": "0.05", "salt_100g": "0.125", "serving_quantity": "33.25",
            "last_modified_t": "1763900000"}
    base.update(kw)
    return base


reason, res = mod.process_row(row())
out = res[1]
check("process_row tie product (kcal, protein, carbs, sugars, salt, serving)",
      [out[4], out[5], out[6], out[7], out[11], out[12]], ["81", "4.3", "15.4", "0.1", "0.13", "33.3"])
reason, res = mod.process_row(row(**{"energy-kcal_100g": "", "energy-kj_100g": "338"}))
check("kJ fallback rounds to 81", res[1][4], "81")

print("%d failures" % failures)
sys.exit(1 if failures else 0)
