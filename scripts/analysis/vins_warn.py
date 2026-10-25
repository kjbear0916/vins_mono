#!/usr/bin/env python3
"""Scan per-trial VINS logs for time-jump / tracking-dissolution signals."""
import os
import re

PATS = re.compile(
    r"jump|drop|reset|td_|time shift|excitation|parallax|feature|fail|least squares|solve",
    re.I)
WANT = [
    "high_1.5ms_figure8_r3_repo54", "low_0.5ms_circle_r2_repo54",
    "low_0.5ms_figure8_r3_repo54", "medium_1.5ms_figure8_r2_repo54",
    "high_0.5ms_circle_r3_repo54", "low_3.0ms_figure8_r3_repo54",
]


def main():
    for t in WANT:
        p = "/tmp/vins_%s.log" % t
        print("--- %s ---" % t)
        if not os.path.exists(p):
            print("  no vins log")
            continue
        hits = []
        for line in open(p, errors="ignore"):
            if PATS.search(line):
                hits.append(line.strip()[:110])
        print("  matching lines: %d" % len(hits))
        for l in hits[:8]:
            print("   ", l)


if __name__ == "__main__":
    main()