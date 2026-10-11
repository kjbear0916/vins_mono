#!/usr/bin/env python3
"""Sim3 scale sweep over an existing 54-matrix (no re-simulation).

Scale_gate.py reports the V/G path-length ratio, not the 7-DoF Umeyama scale.
The per-trial trajectories are already on disk, so the true Sim3 scale for every
trial can be computed directly and its distribution inspected — this avoids
re-running the sim just to see where a single-cell scale value sits.

Usage: scale_sweep.py [--summary ...] [--results ...] [--out ...]
"""
import argparse
import csv
import os
import statistics
import numpy as np
from evo.tools import file_interface
from evo.core import sync


def path_len(xyz):
    return float(np.linalg.norm(np.diff(xyz, axis=0), axis=1).sum())


def one(gt_path, est_path):
    gt = file_interface.read_tum_trajectory_file(gt_path)
    est = file_interface.read_tum_trajectory_file(est_path)
    gt, est = sync.associate_trajectories(gt, est)
    gl = path_len(gt.positions_xyz)
    el = path_len(est.positions_xyz)
    _r, _t, s = est.align(gt, correct_scale=True, correct_only_scale=False)
    return s, (el / gl if gl else float("nan"))


def find(results, tid):
    """Look for a trial id's trajectories; `tid` is the full effective id (may
    carry a RUN_TAG like ..._repo54). Fall back to legacy _rep2.._rep5 suffix
    labels so the master tree's renamed evidence is still found."""
    for cand in (tid, tid + "_rep2", tid + "_rep3", tid + "_rep4", tid + "_rep5"):
        d = os.path.join(results, "trial_%s" % cand, "trajectories")
        g = os.path.join(d, cand + "_gt.tum")
        v = os.path.join(d, cand + "_vins.txt")
        if os.path.isfile(g) and os.path.isfile(v):
            return g, v
    return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary", default="data/results/summary_54.csv")
    ap.add_argument("--results", default="data/results")
    ap.add_argument("--out", default="data/results/scale_sweep.csv")
    ap.add_argument("--tag", default="",
                    help="RUN_TAG (e.g. repo54) appended to each trial id")
    a = ap.parse_args()
    rows = list(csv.DictReader(open(a.summary, newline="")))
    out, scales = [], []
    for r in rows:
        base = "%s_%sms_%s_r%s" % (
            r["light"], r["speed"], r["trajectory"], r["repeat"].lstrip("r"))
        tid = "%s_%s" % (base, a.tag) if a.tag else base
        g, v = find(a.results, tid)
        if not g:
            out.append((tid, "", "", "MISSING"))
            continue
        try:
            s, ratio = one(g, v)
            scales.append(s)
            out.append((tid, "%.4f" % s, "%.4f" % ratio, "ok"))
        except Exception as e:
            out.append((tid, "", "", "ERR:%s" % e))
    with open(a.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["trial_id", "sim3_scale", "path_ratio", "note"])
        w.writerows(out)
    if scales:
        print("n=%d  min=%.4f  max=%.4f  mean=%.4f  std=%.4f  median=%.4f" % (
            len(scales), min(scales), max(scales), statistics.mean(scales),
            statistics.pstdev(scales), statistics.median(scales)))
        print("span=max-min=%.4f" % (max(scales) - min(scales)))
    non_ok = [o[0] for o in out if o[3] != "ok"]
    print("non-ok (%d): %s" % (len(non_ok), non_ok))
    print("wrote", a.out)


if __name__ == "__main__":
    main()
