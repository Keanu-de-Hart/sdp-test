"""Throwaway: inspect the structure of the official reference CSVs."""
import csv
from collections import Counter

BASE = "/home/vmuser/Downloads/repo-references"
FILES = ("cJSON_6d9f2443ab07", "git_5a7d1e8045ce", "redis_b540ca49cba8")

for name in FILES:
    path = f"{BASE}/{name}.csv"
    types = Counter()
    combos = Counter()
    sets = Counter()
    samples = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            ot = row["object_type"]
            types[ot] += 1
            combos[(ot, "author" if row["author"] != "ALL" else "ALL")] += 1
            sets[row["commit_set"]] += 1
            key = (ot, "author" if row["author"] != "ALL" else "ALL")
            if key not in samples:
                samples[key] = dict(row)
    print(f"== {name} ==")
    print("  object_types:", dict(types))
    print("  object x author rows:", dict(combos))
    print("  commit_sets:", dict(sets))
    for key, row in samples.items():
        print(f"  sample {key}:")
        print("   ", {k: v for k, v in row.items() if v})
