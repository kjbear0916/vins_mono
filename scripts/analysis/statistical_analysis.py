#!/usr/bin/env python3
"""
Statistical analysis of experiment results.

Performs:
  - One-way ANOVA on ATE by light level
  - One-way ANOVA on ATE by speed
  - Two-way ANOVA (light × speed) if sufficient data
  - Summary statistics per condition
"""
import argparse
import os
import sys
import pandas as pd
import numpy as np
from scipy import stats
from scipy.stats import f_oneway


def anova_summary(groups, group_labels):
    """One-way ANOVA + post-hoc reporting."""
    f, p = f_oneway(*groups)
    means = [np.mean(g) for g in groups]
    print(f"\n  ANOVA: F={f:.3f}, p={p:.4f}")
    for label, m in zip(group_labels, means):
        print(f"    {label}: mean ATE = {m:.4f} m")
    if p < 0.05:
        print(f"  → STATISTICALLY SIGNIFICANT (p < 0.05)")
    else:
        print(f"  → Not significant (p >= 0.05)")
    return f, p


def main():
    parser = argparse.ArgumentParser(description='Statistical analysis of results')
    parser.add_argument('--summary', default='data/results/summary.csv',
                        help='Summary CSV path')
    parser.add_argument('--output', default='data/results/',
                        help='Output directory')
    args = parser.parse_args()

    if not os.path.exists(args.summary):
        print(f"ERROR: Summary CSV not found: {args.summary}")
        sys.exit(1)

    df = pd.read_csv(args.summary)
    df['ate_rms'] = pd.to_numeric(df['ate_rms'], errors='coerce')
    df = df.dropna(subset=['ate_rms'])

    print("═" * 60)
    print("  STATISTICAL ANALYSIS — VINS-Mono Simulation Experiments")
    print("═" * 60)

    # ─── Summary statistics ───
    print("\n── Summary statistics per condition ──")
    summary = df.groupby(['light', 'speed']).agg(
        ate_mean=('ate_rms', 'mean'),
        ate_std=('ate_rms', 'std'),
        ate_median=('ate_rms', 'median'),
        n=('ate_rms', 'count')
    ).round(4)
    print(summary.to_string())

    summary.to_csv(os.path.join(args.output, 'summary_stats.csv'))

    # ─── One-way ANOVA: effect of light ───
    print("\n── Effect of Light Level on ATE ──")
    light_groups = [df[df['light'] == l]['ate_rms'].values
                    for l in ['high', 'medium', 'low']]
    anova_summary(light_groups, ['high', 'medium', 'low'])

    # ─── One-way ANOVA: effect of speed ──
    print("\n── Effect of Flight Speed on ATE ──")
    speed_groups = [df[df['speed'] == s]['ate_rms'].values
                    for s in ['0.5', '1.5', '3.0']]
    anova_summary(speed_groups, ['0.5 m/s', '1.5 m/s', '3.0 m/s'])

    # ─── Two-way ANOVA ──
    print("\n── Two-way ANOVA (light × speed) ──")
    try:
        import statsmodels.api as sm
        from statsmodels.formula.api import ols

        model = ols('ate_rms ~ C(light) * C(speed)', data=df).fit()
        two_way = sm.stats.anova_lm(model, typ=2)
        print(two_way.to_string())
        two_way.to_csv(os.path.join(args.output, 'anova_2way.csv'))
    except ImportError:
        print("  statsmodels not installed — skipping two-way ANOVA")
        print("  Install with: pip3 install statsmodels")

    # ─── Pairwise comparisons ───
    print("\n── Pairwise t-tests (light levels) ──")
    for a, b in [('high', 'medium'), ('high', 'low'), ('medium', 'low')]:
        ga = df[df['light'] == a]['ate_rms']
        gb = df[df['light'] == b]['ate_rms']
        t, p = stats.ttest_ind(ga, gb)
        print(f"  {a} vs {b}: t={t:.3f}, p={p:.4f} {'*' if p < 0.05 else ''}")

    print("\n── Pairwise t-tests (speed levels) ──")
    for a, b in [('0.5', '1.5'), ('0.5', '3.0'), ('1.5', '3.0')]:
        ga = df[df['speed'] == a]['ate_rms']
        gb = df[df['speed'] == b]['ate_rms']
        t, p = stats.ttest_ind(ga, gb)
        print(f"  {a} vs {b} m/s: t={t:.3f}, p={p:.4f} {'*' if p < 0.05 else ''}")

    # ─── Hypothesis verification ───
    print("\n══ HYPOTHESIS VERIFICATION ══")
    high_mean = df[df['light'] == 'high']['ate_rms'].mean()
    low_mean = df[df['light'] == 'low']['ate_rms'].mean()
    delta = (low_mean - high_mean) / high_mean * 100
    print(f"H1: Light intensity ↓ → ATE ↑")
    print(f"    High-light mean ATE: {high_mean:.4f} m")
    print(f"    Low-light mean ATE:  {low_mean:.4f} m")
    print(f"    Change: {delta:+.1f}%")
    print(f"    → {'CONFIRMED' if delta > 0 else 'REJECTED'}")

    slow_mean = df[df['speed'] == '0.5']['ate_rms'].mean()
    fast_mean = df[df['speed'] == '3.0']['ate_rms'].mean()
    delta = (fast_mean - slow_mean) / slow_mean * 100
    print(f"\nH2: Speed ↑ → RPE/ATE ↑")
    print(f"    Slow (0.5 m/s) mean ATE: {slow_mean:.4f} m")
    print(f"    Fast (3.0 m/s) mean ATE: {fast_mean:.4f} m")
    print(f"    Change: {delta:+.1f}%")
    print(f"    → {'CONFIRMED' if delta > 0 else 'REJECTED'}")

    print("\nDone. Results saved to " + args.output)


if __name__ == '__main__':
    main()