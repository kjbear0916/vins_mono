#!/usr/bin/env python3
"""run12_subset.py — item #12 high-rate IMU subset, run REP-MAJOR.

6 cells x 3 reps = 18 trials, ordered rep-major (all cells' r1, then r2, then
r3) so host load / clock drift is spread across cells instead of concentrating
on one cell's three consecutive reps.

Reuses batch_run_54's trial machinery so the summary CSV format, metrics
columns, timeout/retry, disk guard and bag cleanup stay identical to the master
matrix. Config is read from the environment (set by run12_imu161.sh):
    VINS_RESULTS_DIR, VINS_SUMMARY_CSV, RUN_TAG, IMU_HZ, VINS_TRIAL_TIMEOUT, ...
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import batch_run_54 as b  # noqa: E402

# Cells span all light levels, both trajectories, all speeds, and include the
# dark/fast corners where the 50 Hz arm was crash-prone.
CELLS = [
    ("high", "0.5", "circle"),
    ("high", "1.5", "figure8"),
    ("medium", "1.5", "circle"),
    ("medium", "3.0", "figure8"),
    ("low", "1.5", "figure8"),
    ("low", "3.0", "circle"),
]


def main():
    os.makedirs(b.RESULTS_DIR, exist_ok=True)
    imu_hz = os.environ.get("IMU_HZ", "50")

    order = []
    for rep in (1, 2, 3):
        for (l, s, t) in CELLS:
            order.append((l, s, t, rep))

    completed = b.load_completed_trials(b.SUMMARY_CSV)
    print(f"#12 subset: {len(order)} trials ({len(CELLS)} cells x 3 reps), REP-MAJOR order")
    print(f"  results_dir={b.RESULTS_DIR}")
    print(f"  summary_csv={b.SUMMARY_CSV}")
    print(f"  run_tag={b.RUN_TAG!r}  imu_hz(requested)={imu_hz}  "
          f"timeout={b.TRIAL_TIMEOUT}s retries={b.TRIAL_RETRIES}")

    fb = b.free_bytes(b.DATA_DIR)
    if fb is not None and fb < b.MIN_FREE_BYTES:
        print(f"ERROR: {fb / 1e9:.2f} GB free < {b.MIN_FREE_BYTES / 1e9:.2f} GB hard floor. Aborting.")
        sys.exit(2)
    if fb is not None:
        print(f"Disk check OK: {fb / 1e9:.2f} GB free (>= {b.MIN_FREE_BYTES / 1e9:.2f} GB).")

    ran = 0
    for idx, (l, s, t, r) in enumerate(order, 1):
        tid = b.trial_id(l, s, t, r)
        if (l, s, t, str(r)) in completed:
            print(f"[{idx}/{len(order)}] skip (already ok): {tid}")
            continue

        fb = b.free_bytes(b.DATA_DIR)
        if fb is not None and fb < b.MIN_FREE_BYTES:
            print(f"ERROR: only {fb / 1e9:.2f} GB free before {tid}; stopping.")
            break

        flight_dur = 55 if s == "0.5" else 45
        print(f"\n>>> [{idx}/{len(order)}] {tid}  (light={l} speed={s} traj={t} r{r})")
        row, status, metrics = b.run_single_trial(l, s, t, r, radius=5.0, alt=3.0, dur=flight_dur)
        mcols = [metrics.get("wall_s", ""), metrics.get("bag_sim_dur_s", ""),
                 metrics.get("imu_hz", ""), metrics.get("rtf", "")]

        if row is not None:
            row = row + mcols
            b.append_result(b.SUMMARY_CSV, row)
            print(f"    -> note={row[11]} ATE={row[4]} RPE={row[9]} "
                  f"wall={mcols[0]}s imu_hz={mcols[2]} rtf={mcols[3]}")
            base = os.path.join(b.DATA_DIR, "rosbags", f"{tid}.bag")
            removed = False
            for bp in (base, base + ".active", base + ".orig.bag"):
                if os.path.exists(bp):
                    os.remove(bp)
                    removed = True
            if removed:
                print(f"    -> cleaned bag/sidecars: {tid}.bag")
        else:
            fb_row = [l, s, t, f"r{r}", "N/A", "N/A", "N/A", "N/A", "N/A",
                      "N/A", "N/A", status, tid,
                      f"light={l}; speed={s}m/s; traj={t}; repeat=r{r}; imu_hz={imu_hz}"] + mcols
            b.append_result(b.SUMMARY_CSV, fb_row)
            print(f"    -> FAILED status={status} (no summary); recorded N/A row")

        ran += 1
        time.sleep(5)

    print(f"\n#12 subset complete: ran/attempted {ran} trials.")
    print(f"Summary: {b.SUMMARY_CSV}")


if __name__ == "__main__":
    main()
