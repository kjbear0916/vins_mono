#!/usr/bin/env python3
"""compare_suspect_cells.py — 5-arm view of the 2 suspect cells.

Arms on the 2 flagged cells (high/0.5/circle, medium/3.0/figure8):
  master, repo54      : 50 Hz, earlier sessions (results / results_rerun54)
  imu161 (orig)       : ~125 Hz, the 18-run (results_imu161)
  imu161r / ctl50     : ~125 Hz / 50 Hz, SAME session rerun (results_imu161r / results_ctl50)

Per-rep ATE + Sim3 scale + gate flag, then medians per arm per cell.
"""

import csv
import os
import statistics

GATE = (0.96, 1.03)
CELLS = [("high", "0.5", "circle"), ("medium", "3.0", "figure8")]
ARMS = [
    ("master",   "/data/results/summary_54.csv",            "/data/results/scale_sweep.csv",            ""),
    ("repo54",   "/data/results_rerun54/summary_54.csv",     "/data/results_rerun54/scale_sweep_repo54.csv", "_repo54"),
    ("imu161",   "/data/results_imu161/summary_54.csv",      "/data/results_imu161/scale_imu161.csv",    ""),
    ("imu161r",  "/data/results_imu161r/summary_54.csv",     "/data/results_imu161r/scale.csv",          ""),
    ("ctl50",    "/data/results_ctl50/summary_54.csv",       "/data/results_ctl50/scale.csv",            ""),
]


def load_sum(path):
    rows = {}
    if not os.path.exists(path):
        return rows
    with open(path) as f:
        for r in csv.DictReader(f):
            rows[(r["light"], r["speed"], r["trajectory"], r["repeat"])] = r
    return rows


def load_scale(path, strip=""):
    out = {}
    if not os.path.exists(path):
        return out
    with open(path) as f:
        for r in csv.DictReader(f):
            tid = r["trial_id"]
            if strip and tid.endswith(strip):
                tid = tid[: -len(strip)]
            out[tid] = float(r["sim3_scale"]) if r["sim3_scale"] else None
    return out


def main():
    data = {a: load_sum(p) for a, p, _, _ in ARMS}
    scales = {a: load_scale(p, s) for a, _, p, s in ARMS}
    tid_of = {}

    for cell in CELLS:
        (l, sp, tr) = cell
        print(f"\n=== {l}/{sp}/{tr} : per-rep ATE (m)  [key: gate* = in, OG = out-of-gate by Sim3 scale] ===")
        print(f"{'rep':>4} | " + " | ".join(f"{a:>7}" for a, *_ in ARMS) + " |")
        for rep in ("r1", "r2", "r3"):
            vals = []
            for a, _, _, _ in ARMS:
                r = data[a].get((l, sp, tr, rep))
                if not r:
                    vals.append("------")
                    continue
                tid = r["trial_id"]
                s = scales[a].get(tid if a != "repo54" else tid.replace("_repo54", ""))
                mark = ""
                if s is not None:
                    mark = " in" if GATE[0] <= s <= GATE[1] else " OG"
                vals.append(f"{float(r['ate_rms']):6.2f}{mark}")
            print(f"{rep:>4} | " + " | ".join(vals) + " |")

        med = {}
        for a, _, _, _ in ARMS:
            ates = [float(r["ate_rms"]) for r in data[a].values()
                    if (r["light"], r["speed"], r["trajectory"]) == cell and r.get("features_note") == "ok"] or \
                   [float(r["ate_rms"]) for r in data[a].values()
                    if (r["light"], r["speed"], r["trajectory"]) == cell]
            med[a] = statistics.median(ates) if ates else float("nan")
        print(f"median | " + " | ".join(f"{med[a]:6.2f}  " for a, *_ in ARMS) + " |")


if __name__ == "__main__":
    main()