#!/usr/bin/env python3
"""
Failure case analysis — identify and categorize VINS tracking failures.

Reads the experiment summary CSV plus VINS feature-count statistics,
identifies runs where tracking failed or accuracy degraded sharply,
and produces a failure report.

Usage:
    python3 failure_analysis.py --summary data/results/summary.csv \
        --features data/results/trajectories/vins_log_stats.json
"""
import argparse
import os
import sys
import json
import pandas as pd
import numpy as np


ATH_ABS = 2.0        # m — absolute ATE above this is a failure case
ATH_RATIO = 5.0      # ATE multiple of group median above this = failure


def detect_failures(df, feature_stats=None):
    """Label each run as pass/fail/degraded and summarize."""
    # Column names may differ depending on eval version
    ate_col = 'ate_rms' if 'ate_rms' in df.columns else None
    if ate_col is None:
        print("ERROR: No ATE column in summary CSV")
        return

    df = df.copy()
    df[ate_col] = pd.to_numeric(df[ate_col], errors='coerce')

    medians = df.groupby(['light', 'speed'])[ate_col].transform('median')
    df['_fail'] = (
        (df[ate_col] > ATH_ABS) |
        (df[ate_col] > medians * ATH_RATIO)
    )
    df['_degraded'] = (
        ~df['_fail'] &
        (df[ate_col] > medians * 2.0)
    )

    print("══ FAILURE CASE ANALYSIS ══")
    print(f"  Failure threshold:    ATE > {ATH_ABS} m  OR  ATE > {ATH_RATIO}× group median")
    print(f"  Degraded threshold:   ATE > 2× group median")
    print()

    n_total = len(df)
    n_fail = int(df['_fail'].sum())
    n_degraded = int(df['_degraded'].sum())
    print(f"  Runs analyzed:   {n_total}")
    print(f"  Failures:        {n_fail}  ({100*n_fail/max(n_total,1):.1f}%)")
    print(f"  Degraded:        {n_degraded}  ({100*n_degraded/max(n_total,1):.1f}%)")
    print()

    if feature_stats:
        print("── Feature statistics (from VINS logs) ──")
        for fs in feature_stats:
            fn = fs.get('file', 'unknown')
            mean = fs.get('mean_features', 'N/A')
            mins = fs.get('min_features', 'N/A')
            catches = fs.get('tracking_failures', 0)
            if isinstance(mean, float):
                print(f"  {fn}: mean={mean:.0f} min={mins} track_fail={catches}")
        print()

    if n_fail > 0:
        fails = df[df['_fail']]
        print("── FAILURE CASES ──")
        for _, row in fails.iterrows():
            cond = f"{row['light']}/{row['speed']}m/s/{row['trajectory']}/r{row.get('repeat','?')}"
            print(f"  {cond}: ATE={row[ate_col]:.3f} m  (group median={row.get('_med','?')})")
        print()
        print("Potential causes to inspect for these runs:")
        print("  1. Feature starvation in low light (check /vins feature count logs)")
        print("  2. Motion blur at high speed (reduced feature tracking)")
        print("  3. Tracking loss at figure-8 turn-around points")
    else:
        print("  No failure cases detected within thresholds.")

    # Distribution of failures by condition
    print()
    print("── Failure rate by condition ──")
    if n_total > 0 and n_fail > 0:
        rate = df.groupby(['light', 'speed']).agg(
            n=('_fail', 'sum'),
            total=('_fail', 'count')).reset_index()
        for _, r in rate.iterrows():
            pct = 100 * r['n'] / max(r['total'], 1)
            print(f"  {r['light']:6s} {r['speed']} m/s: {r['n']}/{r['total']} failed ({pct:.0f}%)")


def main():
    parser = argparse.ArgumentParser(description='Failure case analysis')
    parser.add_argument('--summary', required=True,
                        help='Summary CSV path')
    parser.add_argument('--features', default=None,
                        help='Optional JSON of VINS feature statistics')
    parser.add_argument('--output', default=None,
                        help='Output failure report path')
    args = parser.parse_args()

    if not os.path.exists(args.summary):
        print(f"ERROR: Summary CSV not found: {args.summary}")
        sys.exit(1)

    df = pd.read_csv(args.summary)

    feature_stats = None
    if args.features and os.path.exists(args.features):
        with open(args.features) as f:
            feature_stats = json.load(f)

    detect_failures(df, feature_stats)

    # Optionally save marked-up CSV
    if args.output:
        df.to_csv(args.output, index=False)
        print(f"\nSaved annotated results to {args.output}")


if __name__ == '__main__':
    main()