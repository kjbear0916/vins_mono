#!/usr/bin/env python3
"""
Scale gate for monocular-VINS matrix runs — flag trials whose trajectory
shape/size collapsed relative to GT.

For each trial row in a summary CSV, loads the corresponding VINS and GT
trajectory files and computes:
  - path ratio        : len(VINS path) / len(GT path)
  - span ratio (x,y)  : (Vmax-Vmin) / (Gmax-Gmin) per horizontal axis

A monocular scale-collapse (failed initialization on a planar / degenerate
scene) shows up as a path ratio far below 1 (e.g. 0.2-0.3) while healthy
repeats of the same cell sit at 0.9-1.05.  This is the cheap, decisive
first diagnostic for outliers in monocular-SLAM experiments, before
blaming light/scene/velocity.

Conventions expected (matching trial_one.sh / batch_run_54.py):
  - summary CSV columns: light, speed, trajectory, repeat (+ ATE col)
  - per-trial result dir   : <results>/trial_<light>_<speed>ms_<traj>_r<rep>/
  - VINS trajectory file   : <dir>/trajectories/<trial_name>_vins.txt  (evo TUM)
  - GT  trajectory file    : <dir>/trajectories/<trial_name>_gt.tum     (evo TUM)

Usage:
    python3 scale_gate.py --summary data/results/summary_54.csv \
        --results data/results --ate-col ate_rms --verbose

Exit code 0 = all trials pass the gate; 1 = at least one flagged.
"""
import argparse
import os
import sys
import numpy as np
import pandas as pd

#: path ratio below this is flagged as a scale-collapse failure
PATH_RATIO_FAIL = 0.6
#: per-axis span ratio floor (only enforced when GT span > 1 m to avoid tiny runs)
SPAN_RATIO_FAIL = 0.6
#: minimum GT path length (m) below which ratios are unreliable / not reported
MIN_GT_PATH = 5.0


def load_xyz(path):
    """Read an evo TUM-format trajectory (t x y z ...); return xyz (N,3) or None."""
    if not os.path.isfile(path):
        return None
    rows = []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) >= 4:
                rows.append([float(parts[1]), float(parts[2]), float(parts[3])])
    if not rows:
        return None
    return np.array(rows)


def path_length(xyz):
    return float(np.linalg.norm(np.diff(xyz, axis=0), axis=1).sum())


def span_xy(xyz):
    return (float(xyz[:, 0].max() - xyz[:, 0].min()),
            float(xyz[:, 1].max() - xyz[:, 1].min()))


def trial_name(row):
    return f"{row['light']}_{row['speed']}ms_{row['trajectory']}_r{row['repeat'][1:]}"


def analyze(results_dir, rows, verbose=False):
    """Return (report_lines, flagged_rows)."""
    lines = []
    lines.append(f"{'trial':<40s} {'ATE':>8s} {'V/G path':>9s} "
                 f"{'spanX':>6s} {'spanY':>6s}  note")
    flagged = []
    for _, row in rows.iterrows():
        tn = trial_name(row)
        td = os.path.join(results_dir, f"trial_{tn}", "trajectories")
        vins = load_xyz(os.path.join(td, f"{tn}_vins.txt"))
        gt = load_xyz(os.path.join(td, f"{tn}_gt.tum"))
        ate = float(row.get('ate_rms', float('nan')) if 'ate_rms' in row.index else 0.0)
        if vins is None or gt is None:
            lines.append(f"{tn:<40s} {'?':>8s} {'missing':>9s} "
                         f"{'':>6s} {'':>6s}  MISSING_TRAJ")
            flagged.append(row)
            continue
        gd = path_length(gt)
        vd = path_length(vins)
        pr = vd / gd if gd > 0 else float("nan")
        sx, sy = span_xy(vins)
        gx, gy = span_xy(gt)
        rx = sx / gx if gx > 1.0 else float("nan")
        ry = sy / gy if gy > 1.0 else float("nan")
        fail = gd >= MIN_GT_PATH and (
            pr < PATH_RATIO_FAIL or
            (np.isfinite(rx) and rx < SPAN_RATIO_FAIL) or
            (np.isfinite(ry) and ry < SPAN_RATIO_FAIL))
        note = "scale-collapse" if fail else "ok"
        lines.append(f"{tn:<40s} {ate:8.3f} {pr:9.2f} "
                     f"{('' if not np.isfinite(rx) else f'{rx:6.2f}')} "
                     f"{('' if not np.isfinite(ry) else f'{ry:6.2f}')}  {note}")
        if fail:
            flagged.append(row)
    return lines, flagged


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--summary", required=True, help="path to summary_54.csv")
    ap.add_argument("--results", required=True, help="root dir holding trial_* dirs")
    ap.add_argument("--ate-col", default="ate_rms", help="ATE column (default: ate_rms)")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    df = pd.read_csv(args.summary)
    lines, flagged = analyze(args.results, df, args.verbose)
    print("\n".join(lines))
    print(f"\nFlagged {len(flagged)} / {len(df)} trials as scale-collapse "
          f"(path ratio < {PATH_RATIO_FAIL} or span ratio < {SPAN_RATIO_FAIL}).")
    sys.exit(1 if flagged else 0)


if __name__ == "__main__":
    main()