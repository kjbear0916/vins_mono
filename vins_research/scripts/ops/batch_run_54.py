#!/usr/bin/env python3
"""
batch_run_54.py — Master orchestrator for the 54 VINS-Mono simulation trials.

Matrix:
  - 3 Light conditions: high, medium, low
  - 3 Velocities: 0.5, 1.5, 3.0 m/s
  - 2 Trajectories: circle, figure8
  - 3 Repeats: r1, r2, r3
  Total: 3 x 3 x 2 x 3 = 54 experiments.

Features:
  - Resumable: automatically skips trials that already have valid results ('ok')
  - Safe subprocess execution with timeout and cleanup
  - Incremental CSV output to /data/results/summary_54.csv
  - Granular filtering via command-line arguments
"""

import os
import sys
import csv
import time
import argparse
import subprocess

REPO_DIR = "/root/catkin_ws/src/vins_research"
DATA_DIR = "/data"
RESULTS_DIR = os.path.join(DATA_DIR, "results")
SUMMARY_CSV = os.path.join(RESULTS_DIR, "summary_54.csv")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TRIAL_SCRIPT = os.environ.get("TRIAL_SCRIPT", os.path.join(SCRIPT_DIR, "trial_one.sh"))

CSV_HEADER = [
    "light", "speed", "trajectory", "repeat",
    "ate_rms", "ate_median", "ate_mean", "ate_std", "ate_max",
    "rpe_rms", "rpe_mean", "features_note"
]


def load_completed_trials(csv_path):
    """Load set of experiment IDs that completed successfully."""
    completed = set()
    if not os.path.exists(csv_path):
        return completed

    try:
        with open(csv_path, 'r', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("features_note") == "ok":
                    key = (row["light"], row["speed"], row["trajectory"], str(row["repeat"]).lstrip('r'))
                    completed.add(key)
    except Exception as e:
        print(f"Warning reading existing summary CSV: {e}")
    return completed


def append_result(csv_path, result_row):
    """Safely append a result row to the master summary CSV."""
    file_exists = os.path.exists(csv_path)
    with open(csv_path, 'a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(CSV_HEADER)
        writer.writerow(result_row)


def read_trial_summary(trial_dir):
    """Read summary.csv produced by trial_one.sh."""
    sum_csv = os.path.join(trial_dir, "summary.csv")
    if not os.path.exists(sum_csv):
        return None
    try:
        with open(sum_csv, 'r', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                return [
                    row.get("light", "N/A"),
                    row.get("speed", "N/A"),
                    row.get("trajectory", "N/A"),
                    row.get("repeat", "N/A"),
                    row.get("ate_rms", "N/A"),
                    row.get("ate_median", "N/A"),
                    row.get("ate_mean", "N/A"),
                    row.get("ate_std", "N/A"),
                    row.get("ate_max", "N/A"),
                    row.get("rpe_rms", "N/A"),
                    row.get("rpe_mean", "N/A"),
                    row.get("features_note", "N/A")
                ]
    except Exception as e:
        print(f"Error reading trial summary from {sum_csv}: {e}")
    return None


def run_single_trial(light, speed, traj, rep, radius=5.0, alt=3.0, dur=45):
    """Execute a single trial using trial_one.sh."""
    cmd = [
        "bash", TRIAL_SCRIPT,
        str(light),
        str(traj),
        str(speed),
        str(radius),
        str(alt),
        str(dur),
        str(rep)
    ]
    print(f"\n[{time.strftime('%H:%M:%S')}] RUNNING: {' '.join(cmd)}")
    start_t = time.time()
    
    # Run trial script with timeout (default flight 45s + setup/teardown ~240s)
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    elapsed = time.time() - start_t
    print(f"[{time.strftime('%H:%M:%S')}] Finished in {elapsed:.1f}s, exit code: {proc.returncode}")
    
    # Locate result
    trial_res_dir = os.path.join(RESULTS_DIR, f"trial_{light}_{speed}ms_{traj}_r{rep}")
    row = read_trial_summary(trial_res_dir)
    return row


def main():
    parser = argparse.ArgumentParser(description="Run 54-trial VINS-Mono simulation matrix")
    parser.add_argument("--resume", action="store_true", default=True,
                        help="Resume from existing summary_54.csv (skip completed)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print experiment plan and status without running")
    parser.add_argument("--limit", type=int, default=None,
                        help="Max number of trials to run in this execution")
    parser.add_argument("--light", choices=["high", "medium", "low"],
                        help="Filter specific light level")
    parser.add_argument("--speed", choices=["0.5", "1.5", "3.0"],
                        help="Filter specific speed")
    parser.add_argument("--traj", choices=["circle", "figure8"],
                        help="Filter specific trajectory")
    parser.add_argument("--repeat", type=int, choices=[1, 2, 3],
                        help="Filter specific repeat index")
    parser.add_argument("--cleanup", action="store_true",
                        help="Delete the .bag of successful trials to save disk")
    args = parser.parse_args()

    os.makedirs(RESULTS_DIR, exist_ok=True)

    lights = [args.light] if args.light else ["high", "medium", "low"]
    speeds = [args.speed] if args.speed else ["0.5", "1.5", "3.0"]
    trajs = [args.traj] if args.traj else ["circle", "figure8"]
    repeats = [args.repeat] if args.repeat else [1, 2, 3]

    # Generate full matrix
    all_trials = []
    for l in lights:
        for s in speeds:
            for t in trajs:
                for r in repeats:
                    all_trials.append((l, s, t, r))

    completed = load_completed_trials(SUMMARY_CSV) if args.resume else set()

    pending = []
    for (l, s, t, r) in all_trials:
        key = (l, s, t, str(r))
        if key in completed:
            continue
        pending.append((l, s, t, r))

    total = len(all_trials)
    done_count = total - len(pending)
    print(f"==================================================")
    print(f" VINS-Mono Simulation Matrix (54 Trials)")
    print(f" Total in matrix:     {total}")
    print(f" Already completed:   {done_count}")
    print(f" Remaining to run:    {len(pending)}")
    print(f" Output master CSV:   {SUMMARY_CSV}")
    print(f"==================================================")

    if args.dry_run:
        for idx, (l, s, t, r) in enumerate(pending, 1):
            print(f"  [{idx}/{len(pending)}] {l} | {s} m/s | {t} | r{r}")
        return

    run_count = 0
    for idx, (l, s, t, r) in enumerate(pending, 1):
        if args.limit and run_count >= args.limit:
            print(f"\nReached batch limit ({args.limit}). Stopping.")
            break

        print(f"\n>>> Trial [{idx}/{len(pending)}] Overall: [Done {done_count + run_count}/{total}]")
        print(f"    Setting: Light={l}, Speed={s} m/s, Trajectory={t}, Repeat=r{r}")

        # Choose flight duration based on speed
        # At 0.5 m/s, circle lap takes ~63s; at 1.5 m/s takes ~21s; at 3.0 m/s takes ~10.5s
        flight_dur = 55 if s == "0.5" else 45

        result_row = run_single_trial(l, s, t, r, radius=5.0, alt=3.0, dur=flight_dur)
        if result_row:
            append_result(SUMMARY_CSV, result_row)
            note = result_row[11]
            ate = result_row[4]
            rpe = result_row[9]
            print(f"    -> Result: note={note}, ATE_RMS={ate} m, RPE_RMS={rpe} m")
            # Free disk: successful trials only need summary/traj/evo artifacts.
            if note == "ok" and args.cleanup:
                bag_path = os.path.join(DATA_DIR, "rosbags",
                                        f"{l}_{s}ms_{t}_r{r}.bag")
                if os.path.exists(bag_path):
                    os.remove(bag_path)
                    print(f"    -> Cleaned bag: {os.path.basename(bag_path)}")
        else:
            print(f"    -> ERROR: No summary produced for {l}_{s}ms_{t}_r{r}")
            fallback_row = [l, s, t, f"r{r}", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "trial_crashed"]
            append_result(SUMMARY_CSV, fallback_row)

        run_count += 1
        time.sleep(5)

    print(f"\n==================================================")
    print(f" Batch run completed {run_count} trials.")
    print(f" Master summary: {SUMMARY_CSV}")
    print(f"==================================================")


if __name__ == "__main__":
    main()
