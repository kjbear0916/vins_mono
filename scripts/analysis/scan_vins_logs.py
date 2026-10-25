#!/usr/bin/env python3
"""
Scan VINS-Mono logs for feature count statistics and failure indicators.

Usage:
    python3 scan_vins_logs.py --logdir <dir_with_logs>
"""
import argparse
import os
import re
import sys
import json
import glob
import numpy as np


# VINS-Mono log patterns
FEATURE_PATTERN = re.compile(r'^\[INFO\] \[.*\] (\d+)\s+features', re.MULTILINE)
TRACKING_PATTERN = re.compile(r'tracking failure', re.IGNORECASE)
INIT_PATTERN = re.compile(r'init.*fail', re.IGNORECASE)


def parse_vins_log(log_path):
    """Parse a VINS-Mono log file for feature counts and failures."""
    with open(log_path, 'r') as f:
        content = f.read()

    # Feature counts
    features = [int(m) for m in FEATURE_PATTERN.findall(content)]

    # Failures
    tracking_failures = len(TRACKING_PATTERN.findall(content))
    init_failures = len(INIT_PATTERN.findall(content))

    stats = {
        'file': os.path.basename(log_path),
        'samples': len(features),
        'mean_features': np.mean(features) if features else None,
        'median_features': np.median(features) if features else None,
        'min_features': np.min(features) if features else None,
        'max_features': np.max(features) if features else None,
        'std_features': np.std(features) if features else None,
        'tracking_failures': tracking_failures,
        'init_failures': init_failures,
    }
    return stats


def main():
    parser = argparse.ArgumentParser(description='Scan VINS logs')
    parser.add_argument('--logdir', required=True,
                        help='Directory containing VINS log files (*.log)')
    parser.add_argument('--output', default=None,
                        help='Output JSON path')
    args = parser.parse_args()

    if not os.path.isdir(args.logdir):
        print(f"ERROR: Not a directory: {args.logdir}")
        sys.exit(1)

    logs = sorted(glob.glob(os.path.join(args.logdir, '*.log')))
    if not logs:
        print(f"No .log files found in {args.logdir}")
        sys.exit(1)

    results = []
    for log in logs:
        print(f"Parsing: {os.path.basename(log)}")
        stats = parse_vins_log(log)
        results.append(stats)
        print(f"  Features: mean={stats['mean_features']:.1f} "
              f"min={stats['min_features']} "
              f"failures: track={stats['tracking_failures']} "
              f"init={stats['init_failures']}")

    output = args.output or os.path.join(args.logdir, 'vins_log_stats.json')
    with open(output, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved statistics to {output}")


if __name__ == '__main__':
    main()