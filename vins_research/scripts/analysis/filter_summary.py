#!/usr/bin/env python3
"""Filter a summary CSV down to note==ok rows (drop crash/hang/empty rows so a
resume cleanly re-runs only those cells). Usage: filter_summary.py FILE.csv
"""
import csv
import sys


def main():
    p = sys.argv[1]
    with open(p, newline="") as f:
        rows = list(csv.DictReader(f))
    keep = [r for r in rows if r["features_note"] == "ok"]
    with open(p, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        for r in keep:
            w.writerow(r)
    print("dropped {} non-ok; kept {}".format(len(rows) - len(keep), len(keep)))


if __name__ == "__main__":
    main()