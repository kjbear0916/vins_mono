#!/usr/bin/env python3
"""Paired comparison of the master 54-matrix vs the repo54 re-run.

Joins two summary CSVs on (light, speed, trajectory, repeat) and reports, per
cell, the ATE for each run and their difference, plus per-arm failure counts and
the distribution of the paired differences.

Usage:
    compare_master_rerun.py MASTER.csv RERUN.csv [--out paired.csv]
"""
import argparse
import csv
import os
import statistics


def load(path):
    rows = {}
    with open(path, "r", newline="") as f:
        for r in csv.DictReader(f):
            key = (r["light"], r["speed"], r["trajectory"], str(r["repeat"]).lstrip("r"))
            rows[key] = r
    return rows


def num(d, k):
    try:
        return float(d.get(k, ""))
    except (TypeError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("master")
    ap.add_argument("rerun")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    M, R = load(a.master), load(a.rerun)
    keys = sorted(set(M) | set(R))

    out_rows = []
    diffs = []
    for k in keys:
        m, r = M.get(k), R.get(k)
        ma = num(m, "ate_rms") if m else None
        ra = num(r, "ate_rms") if r else None
        mn = m.get("features_note", "MISSING") if m else "MISSING"
        rn = r.get("features_note", "MISSING") if r else "MISSING"
        d = (ra - ma) if (ma is not None and ra is not None) else None
        if d is not None:
            diffs.append(d)
        out_rows.append([f"{k[0]}_{k[1]}ms_{k[2]}_r{k[3]}",
                         "" if ma is None else f"{ma:.3f}", mn,
                         "" if ra is None else f"{ra:.3f}", rn,
                         "" if d is None else f"{d:+.3f}",
                         r.get("rtf", "") if r else "",
                         r.get("imu_hz", "") if r else "",
                         r.get("wall_s", "") if r else ""])

    def ok(d):
        return sum(1 for x in d.values() if x.get("features_note") == "ok")

    print("=== paired ATE (master vs repo54) ===")
    print(f"{'cell':34s} {'master':>8s} {'m_note':>12s} {'repo54':>8s} {'r_note':>12s} {'diff':>8s} {'rtf':>7s} {'imu_hz':>7s} {'wall_s':>7s}")
    for row in out_rows:
        print(f"{row[0]:34s} {row[1]:>8s} {row[2]:>12s} {row[3]:>8s} {row[4]:>12s} {row[5]:>8s} {row[6]:>7s} {row[7]:>7s} {row[8]:>7s}")

    print("\n=== summary ===")
    print(f"master ok={ok(M)}/{len(M)}   repo54 ok={ok(R)}/{len(R)}")
    ma_all = [num(M[k], "ate_rms") for k in sorted(M) if num(M[k], "ate_rms") is not None]
    ra_all = [num(R[k], "ate_rms") for k in sorted(R) if num(R[k], "ate_rms") is not None]
    if ma_all:
        print(f"master ATE: n={len(ma_all)} median={statistics.median(ma_all):.3f} min={min(ma_all):.3f} max={max(ma_all):.3f}")
    if ra_all:
        print(f"repo54 ATE: n={len(ra_all)} median={statistics.median(ra_all):.3f} min={min(ra_all):.3f} max={max(ra_all):.3f}")
    if diffs:
        print(f"paired diff (repo54-master): n={len(diffs)} median={statistics.median(diffs):+.3f} "
              f"mean={statistics.mean(diffs):+.3f} min={min(diffs):+.3f} max={max(diffs):+.3f}")
        within = sum(1 for d in diffs if abs(d) <= 0.10)
        print(f"  |diff|<=0.10 m: {within}/{len(diffs)}")

    if a.out:
        with open(a.out, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["cell", "master_ate", "master_note", "rerun_ate", "rerun_note",
                        "diff", "rtf", "imu_hz", "wall_s"])
            w.writerows(out_rows)
        print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
