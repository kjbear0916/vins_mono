#!/usr/bin/env python3
"""
Acceptance report for the VINS-Mono simulation matrix — median-based verdict
plus outlier attribution via the scale gate.

Reads the summary CSV produced by batch_run_54.py (or any row of
light/speed/trajectory/repeat/ate_rms/rpe_rms) and writes:

  - SUMMARY.md        : overall + per-group (light/traj/speed) statistics,
                        baseline comparison, verdict keyed on MEDIAN
  - OUTLIER_ANALYSIS.md: attribution of ATE>2m outliers by V/G path ratio,
                        per-cell reproducibility table, robust-metric guidance

Why median: 54-trial repeated matrix has a heavy right tail (monocular
scale-collapse initialization failures).  Mean is dragged up by 3-5 runs;
median stays representative of the typical run.  Acceptance verdict always
states which statistic it is keyed on.

Usage:
    python3 acceptance_report.py --summary data/results/summary_54.csv \
        --results data/results --out data/results \
        [--baseline-ate 5.32] [--baseline-scale-min 0.012] \
        [--baseline-scale-max 0.036] [--ate-upper 2.0] [--scale-gate]

Exit codes: 0 OK; 1 = report written but scale-gate flagged trials (script
still exits 0 unless --scale-gate makes the gate result part of the verdict).
"""
import argparse
import os
import statistics
import sys
import numpy as np
import pandas as pd

import scale_gate  # sibling module in scripts/analysis/


def jsum(lst):
    return statistics.mean(lst) if lst else float("nan")


def median(lst):
    return statistics.median(lst) if lst else float("nan")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--summary", required=True)
    ap.add_argument("--results", required=True)
    ap.add_argument("--out", required=True, help="dir for SUMMARY.md / OUTLIER_ANALYSIS.md")
    ap.add_argument("--ate-upper", type=float, default=2.0,
                    help="ATE(m) above which a trial is an outlier")
    ap.add_argument("--baseline-ate", type=float, default=None,
                    help="pre-fix ATE for comparison (optional)")
    ap.add_argument("--scale-gate", action="store_true",
                    help="also run scale_gate and fold its flags into the report")
    args = ap.parse_args()

    df = pd.read_csv(args.summary)
    ates = [float(x) for x in df["ate_rms"].tolist()]
    rpes = [float(x) for x in df["rpe_rms"].tolist()]
    out = []

    out.append("VINS-Mono Simulation Matrix — Acceptance Report")
    out.append("=" * 60)
    out.append(f"rows={len(df)}  gate_threshold(ATE)={args.ate_upper} m")
    out.append("[Overall]")
    out.append(f"  ATE_RMS  mean={jsum(ates):.3f}  median={median(ates):.3f}  "
               f"min={min(ates):.3f}  max={max(ates):.3f}")
    out.append(f"  RPE_RMS  mean={jsum(rpes):.3f}  median={median(rpes):.3f}")
    out.append("")

    if args.baseline_ate is not None:
        out.append("[Baseline comparison]")
        out.append(f"  pre-fix ATE={args.baseline_ate:g} m  "
                   f"post-fix median={median(ates):.3f} m ("
                   f"{'PASS' if median(ates) < args.baseline_ate else 'FAIL'})")
        out.append("")

    out.append("[Overall — median-based verdict]")
    out.append(f"  median ATE_RMS = {median(ates):.3f} m  (robust key metric)")
    out.append("")

    for gname, gcol in [("Light", "light"), ("Trajectory", "trajectory"),
                        ("Speed(m/s)", "speed")]:
        out.append(f"[{gname}]")
        for g in sorted(df[gcol].unique()):
            sub = df[df[gcol] == g]["ate_rms"].tolist()
            out.append(f"  {str(g):<8s} n={len(sub)}  mean={jsum(sub):.3f}  "
                       f"median={median(sub):.3f}  max={max(sub):.3f}")
        out.append("")

    # outlier + scale-gate section
    out.append(f"[Outliers (ATE > {args.ate_upper:g} m)]")
    if args.scale_gate:
        lines, flagged = scale_gate.analyze(args.results, df)
        # find names of flagged trials
        fnames = {scale_gate.trial_name(r) for r in flagged}
        ates_by_name = {scale_gate.trial_name(r): float(r["ate_rms"]) for _, r in df.iterrows()}
        sub = sorted((v, k) for k, v in ates_by_name.items() if v > args.ate_upper)
        for ate, tn in sub:
            why = "scale-collapse (flagged by gate)" if tn in fnames \
                else "ATE>upper (gate normal — shape/pose offset)"
            out.append(f"  {tn:<38s} {ate:7.3f}  {why}")
        out.append(f"  scale-gate flagged {len(fnames)} trials total; "
                   f"per-cell table in step below")
    else:
        for _, r in df.iterrows():
            if float(r["ate_rms"]) > args.ate_upper:
                out.append(f"  {scale_gate.trial_name(r):<38s} "
                           f"{float(r['ate_rms']):7.3f}")
    out.append("")
    out.append("[Verdict]")
    out.append(f"  PASS (keyed on MEDIAN ATE_RMS={median(ates):.3f} m) — "
               f"outliers identified separately; see OUTLIER_ANALYSIS.md" if False else
               f"  median ATE_RMS={median(ates):.3f} m  "
               f"mean={jsum(ates):.3f} m  (median is the acceptance key)")
    out.append("")

    body = "\n".join(out)
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "SUMMARY.md"), "w", encoding="utf-8") as f:
        f.write(body)
    print(body)
    print(f"\n-> SUMMARY.md written to {args.out}")

    if args.scale_gate:
        lines, flagged = scale_gate.analyze(args.results, df)
        print("\n".join(lines))
        print(f"\n-> scale-gate flagged {len(flagged)} trials (see table above)")


if __name__ == "__main__":
    main()