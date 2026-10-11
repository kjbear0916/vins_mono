#!/usr/bin/env python3
"""List cells whose rtf/wall are outside the time-valid gate (suspect clock
freeze / stale-wall) so they are reported but excluded from RTF+diffs."""
import csv

PAIRED = "/data/results_rerun54/paired_master_repo54.csv"

for row in csv.DictReader(open(PAIRED, newline="")):
    w = float(row["wall_s"])
    rf = float(row["rtf"])
    if not (0.3 <= rf <= 3.0 and 100 <= w <= 1200):
        print("%s  rtf=%s  wall=%s" % (row["cell"], row["rtf"], row["wall_s"]))