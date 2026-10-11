#!/usr/bin/env python3
"""snapshot/triage a summary_54.csv (master or rerun tree).

Prints: row/note counts, wall-clock outliers, imu_hz stats, RTF stats, and a
per-cell dump of the values the paired comparison needs (ate, wall, sim dur).
"""
import csv
import sys
import statistics


def main():
    p = sys.argv[1] if len(sys.argv) > 1 else "/data/results_rerun54/summary_54.csv"
    rows = list(csv.DictReader(open(p)))
    print(f"file={p}")
    print(f"rows={len(rows)}")
    c = {}
    for r in rows:
        c[r["features_note"]] = c.get(r["features_note"], 0) + 1
    print("notes:", dict(sorted(c.items())))

    def f(r, k):
        try:
            return float(r.get(k, ""))
        except (TypeError, ValueError):
            return None

    print("\nwall_s outliers (>200):")
    for r in rows:
        w = f(r, "wall_s")
        if w is not None and w > 200:
            print(f"  {r['trial_id']}: wall={r['wall_s']} sim={r['bag_sim_dur_s']} "
                  f"imu_hz={r['imu_hz']} rtf={r['rtf']} ate={r['ate_rms']} note={r['features_note']}")

    hz = [f(r, "imu_hz") for r in rows]
    hz = [h for h in hz if h is not None]
    if hz:
        print(f"imu_hz: n={len(hz)} min={min(hz):.2f} median={statistics.median(hz):.2f} max={max(hz):.2f}")

    rtf = [f(r, "rtf") for r in rows]
    rtf = [x for x in rtf if x is not None and x > 0.3]
    if rtf:
        print(f"rtf (time-valid, >0.3): n={len(rtf)} median={statistics.median(rtf):.3f}")

    print("\nper-cell: cell,note,ate,ateX_note_only")
    for r in rows:
        print(f"{r['trial_id']},{r['features_note']},{r['ate_rms']},{r['wall_s']}")


if __name__ == "__main__":
    main()