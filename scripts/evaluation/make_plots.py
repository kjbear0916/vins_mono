#!/usr/bin/env python3
"""
Generate visualization plots from experiment results.

Produces:
  - ATE boxplots by light level
  - ATE boxplots by speed
  - Error over time curves
  - Trajectory overlay plots (GT vs estimated)
"""
import argparse
import os
import sys
import glob
import json
import csv
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

from evo.tools import plot as evo_plot
from evo.core import trajectory as evo_trajectory
from evo.tools.settings import SETTINGS


STYLE_OPTS = {
    'font.size': 11,
    'axes.titlesize': 12,
    'axes.labelsize': 11,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'legend.fontsize': 9,
    'figure.titlesize': 13,
}
plt.rcParams.update(STYLE_OPTS)
sns.set_style('whitegrid')

LIGHT_COLORS = {'high': '#2ecc71', 'medium': '#f39c12', 'low': '#e74c3c'}
SPEED_COLORS = {'0.5': '#3498db', '1.5': '#9b59b6', '3.0': '#e74c3c'}
TRAJ_MARKERS = {'circle': 'o', 'figure8': '^'}


def parse_summary(csv_path):
    """Load summary CSV into DataFrame."""
    return pd.read_csv(csv_path)


def plot_ate_boxplot_by_light(df, output_dir):
    """ATE boxplot grouped by light level."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # By light level
    sns.boxplot(data=df, x='light', y='ate_rms', order=['high', 'medium', 'low'],
                hue='speed', ax=axes[0])
    axes[0].set_title('ATE by Light Level')
    axes[0].set_xlabel('Light Level')
    axes[0].set_ylabel('ATE RMSE (m)')

    # By speed
    sns.boxplot(data=df, x='speed', y='ate_rms', hue='light', ax=axes[1])
    axes[1].set_title('ATE by Flight Speed')
    axes[1].set_xlabel('Speed (m/s)')
    axes[1].set_ylabel('ATE RMSE (m)')

    # Combined effect
    piv = df.pivot_table(values='ate_rms', index='light', columns='speed', aggfunc='mean')
    fig2, ax = plt.subplots(figsize=(8, 5))
    piv.plot(kind='bar', ax=ax)
    ax.set_title('Mean ATE RMSE: Light × Speed Interaction')
    ax.set_xlabel('Light Level')
    ax.set_ylabel('ATE RMSE (m)')
    ax.legend(title='Speed (m/s)')
    plt.tight_layout()
    fig2.savefig(os.path.join(output_dir, 'ate_light_speed.png'), dpi=150)
    plt.close(fig2)

    axes[0].legend(title='Speed (m/s)', loc='upper left')
    plt.tight_layout()
    fig.savefig(os.path.join(output_dir, 'ate_boxplots.png'), dpi=150)
    plt.close(fig)
    print(f"Saved: {output_dir}/ate_boxplots.png, ate_light_speed.png")


def plot_rpe_boxplot(df, output_dir):
    """RPE boxplots."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    sns.boxplot(data=df, x='light', y='rpe_rms', order=['high', 'medium', 'low'],
                hue='speed', ax=axes[0])
    axes[0].set_title('RPE by Light Level')
    axes[0].set_xlabel('Light Level')
    axes[0].set_ylabel('RPE RMSE (m)')

    sns.boxplot(data=df, x='speed', y='rpe_rms', hue='light', ax=axes[1])
    axes[1].set_title('RPE by Flight Speed')
    axes[1].set_xlabel('Speed (m/s)')
    axes[1].set_ylabel('RPE RMSE (m)')

    plt.tight_layout()
    fig.savefig(os.path.join(output_dir, 'rpe_boxplots.png'), dpi=150)
    plt.close(fig)
    print(f"Saved: {output_dir}/rpe_boxplots.png")


def plot_feature_stats(df, output_dir):
    """Feature count statistics (if available in CSV)."""
    if 'features_note' not in df.columns:
        return
    # Placeholder: feature analysis comes from VINS logs
    print("Feature count analysis requires VINS log parsing (see analysis/scan_vins_logs.py)")


def main():
    parser = argparse.ArgumentParser(description='Generate result visualizations')
    parser.add_argument('--summary', default='data/results/summary.csv',
                        help='Summary CSV path')
    parser.add_argument('--traj-dir', default='data/results/trajectories',
                        help='Trajectory directory')
    parser.add_argument('--output', default='data/plots',
                        help='Output plot directory')
    args = parser.parse_args()

    if not os.path.exists(args.summary):
        print(f"ERROR: Summary CSV not found: {args.summary}")
        sys.exit(1)

    os.makedirs(args.output, exist_ok=True)

    df = parse_summary(args.summary)
    df['ate_rms'] = pd.to_numeric(df['ate_rms'], errors='coerce')
    df['rpe_rms'] = pd.to_numeric(df['rpe_rms'], errors='coerce')
    df = df.dropna(subset=['ate_rms', 'rpe_rms'])

    print(f"Loaded {len(df)} experiment results")

    # Generate plots
    plot_ate_boxplot_by_light(df, args.output)
    plot_rpe_boxplot(df, args.output)

    print(f"\nAll plots saved to {args.output}")


if __name__ == '__main__':
    main()