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
import json
import time
import signal
import hashlib
import argparse
import shutil
import subprocess

REPO_DIR = "/root/catkin_ws/src/vins_research"
DATA_DIR = "/data"
# Allow a rerun to write to a separate tree / summary so a re-matrix never
# clobbers the committed master evidence. RUN_TAG is forwarded to trial_one.sh
# as its 8th arg so bags + per-trial dirs are suffixed too.
RESULTS_DIR = os.environ.get("VINS_RESULTS_DIR", os.path.join(DATA_DIR, "results"))
SUMMARY_CSV = os.environ.get("VINS_SUMMARY_CSV", os.path.join(RESULTS_DIR, "summary_54.csv"))
RUN_TAG = os.environ.get("RUN_TAG", "").strip()
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TRIAL_SCRIPT = os.environ.get("TRIAL_SCRIPT", os.path.join(SCRIPT_DIR, "trial_one.sh"))


def trial_id(light, speed, traj, rep):
    """Canonical trial id, suffixed with RUN_TAG when this is a re-matrix run."""
    base = f"{light}_{speed}ms_{traj}_r{rep}"
    return f"{base}_{RUN_TAG}" if RUN_TAG else base

#: rough on-disk size of one recorded bag (observed ~400 MB for an 85 s record)
BAG_EST_BYTES = 420 * 1024 * 1024
#: refuse to start unless this many bags' worth of free space is available
#: (a reindex can momentarily double one bag, hence >1x)
MIN_FREE_BAGS = 3
#: hard floor on free space before starting a run / the next recording (1.5 GiB).
#: D: is typically ~98% full, so keep a firm buffer above one bag's worth.
MIN_FREE_BYTES = int(1.5 * 1024 ** 3)

#: per-trial wall-clock timeout and retry count. A healthy trial is ~150-250 s;
#: a hung one was observed at ~2800 s. Default 3x-normal ceiling.
TRIAL_TIMEOUT = int(os.environ.get("VINS_TRIAL_TIMEOUT", "720"))
TRIAL_RETRIES = int(os.environ.get("VINS_TRIAL_RETRIES", "1"))

CSV_HEADER = [
    "light", "speed", "trajectory", "repeat",
    "ate_rms", "ate_median", "ate_mean", "ate_std", "ate_max",
    "rpe_rms", "rpe_mean", "features_note",
    "trial_id", "config_label",
    "wall_s", "bag_sim_dur_s", "imu_hz", "rtf"
]


def free_bytes(path=DATA_DIR):
    """Free bytes on the filesystem holding `path`, or None if unavailable."""
    try:
        return shutil.disk_usage(path).free
    except OSError:
        return None


def _md5(path):
    """Hex md5 of a file, or None if it does not exist / cannot be read."""
    if not os.path.isfile(path):
        return None
    h = hashlib.md5()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
    except OSError:
        return None
    return h.hexdigest()


def write_manifest(trial_dir, light, speed, traj, rep):
    """Record per-trial provenance: md5s of the config (camera pose + RIC),

    the sim launcher (world selection) and the light world file, so a result
    can be tied to the exact inputs that produced it.
    """
    if not os.path.isdir(trial_dir):
        return
    if os.path.exists(os.path.join(trial_dir, "manifest.json")):
        # trial_one.sh already wrote the authoritative (turnkey) manifest.
        return
    world_rel = f"worlds/light_{light}.world"
    manifest = {
        "trial_id": trial_id(light, speed, traj, rep),
        "light": light, "speed": speed, "trajectory": traj, "repeat": rep,
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "vins_world": os.environ.get("VINS_WORLD", "vins_demo"),
        "md5": {
            "config/sim_config.yaml": _md5(os.path.join(REPO_DIR, "config", "sim_config.yaml")),
            "docker/sim_launch.sh": _md5(os.path.join(REPO_DIR, "docker", "sim_launch.sh")),
            world_rel: _md5(os.path.join(REPO_DIR, world_rel)),
        },
    }
    try:
        with open(os.path.join(trial_dir, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, sort_keys=True)
            f.write("\n")
    except OSError as e:
        print(f"Warning: could not write manifest for {manifest['trial_id']}: {e}")


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
                light = row.get("light", "N/A")
                speed = row.get("speed", "N/A")
                traj = row.get("trajectory", "N/A")
                rep = row.get("repeat", "N/A")
                return [
                    light,
                    speed,
                    traj,
                    rep,
                    row.get("ate_rms", "N/A"),
                    row.get("ate_median", "N/A"),
                    row.get("ate_mean", "N/A"),
                    row.get("ate_std", "N/A"),
                    row.get("ate_max", "N/A"),
                    row.get("rpe_rms", "N/A"),
                    row.get("rpe_mean", "N/A"),
                    row.get("features_note", "N/A"),
                    trial_id(light, speed, traj, str(rep).lstrip("r")),
                    f"light={light}; speed={speed}m/s; traj={traj}; repeat={rep}; "
                    f"imu_hz={os.environ.get('IMU_HZ', '50')}"
                ]
    except Exception as e:
        print(f"Error reading trial summary from {sum_csv}: {e}")
    return None


def read_metrics(trial_dir):
    """Read metrics.csv (wall_s, bag_sim_dur_s, imu_hz, rtf) written by trial_one.sh."""
    path = os.path.join(trial_dir, "metrics.csv")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", newline="") as f:
            for row in csv.DictReader(f):
                return row
    except Exception as e:
        print(f"Error reading metrics from {path}: {e}")
    return {}


def preserve_evidence(trial_dir, bag_base, metrics):
    """Save cheap derived evidence before a bag is deleted.

    trial_one.sh already writes the GT/VINS TUM trajectories under
    trial_dir/trajectories (scale_sweep.py reads them to recompute the Sim3
    scale), so the only artifact lost with the bag is the rosbag metadata.
    Dump it plus the runtime metrics so a later audit can still inspect bag
    duration/topics after the recording itself is gone.
    """
    if not os.path.isdir(trial_dir):
        return
    if os.path.exists(bag_base):
        try:
            info = subprocess.run(["rosbag", "info", bag_base],
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, text=True,
                                  timeout=180)
            with open(os.path.join(trial_dir, "bag_info.txt"), "w") as f:
                f.write(info.stdout or "")
        except Exception as e:
            print(f"    -> bag_info dump failed: {e}")
    try:
        with open(os.path.join(trial_dir, "evidence.json"), "w") as f:
            json.dump({"bag": os.path.basename(bag_base),
                       "bag_bytes": (os.path.getsize(bag_base)
                                     if os.path.exists(bag_base) else None),
                       "wall_s": metrics.get("wall_s", ""),
                       "bag_sim_dur_s": metrics.get("bag_sim_dur_s", ""),
                       "imu_hz": metrics.get("imu_hz", ""),
                       "rtf": metrics.get("rtf", "")}, f, indent=2)
    except Exception as e:
        print(f"    -> evidence.json dump failed: {e}")


def cleanup_sim():
    """Kill any lingering simulator/ROS processes left after a timeout."""
    for pat in ("sitl_run.sh", "gzserver", "px4", "mavros_node", "roslaunch",
                "rosbag record", "vins_estimator", "feature_tracker",
                "Xvfb", "xvfb-run"):
        subprocess.run(["pkill", "-9", "-f", pat],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def exec_trial(cmd, timeout):
    """Run a trial, killing its whole process group on timeout.

    Returns (timed_out, elapsed_s, returncode). start_new_session isolates the
    trial in its own process group so the kill also reaps gzserver/px4/mavros.
    """
    start_t = time.monotonic()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True,
                            start_new_session=True)
    try:
        proc.communicate(timeout=timeout)
        return False, time.monotonic() - start_t, proc.returncode
    except subprocess.TimeoutExpired:
        print(f"    -> TIMEOUT after {timeout}s; killing process group {proc.pid}")
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except Exception:
            pass
        try:
            proc.communicate(timeout=30)
        except Exception:
            pass
        cleanup_sim()
        return True, time.monotonic() - start_t, None


def run_single_trial(light, speed, traj, rep, radius=5.0, alt=3.0, dur=45):
    """Execute one trial (one retry on wall-clock timeout).

    Returns (row, status, metrics); status is "ok" | "hang" | "crash".
    """
    cmd = [
        "bash", TRIAL_SCRIPT,
        str(light), str(traj), str(speed),
        str(radius), str(alt), str(dur), str(rep),
    ]
    if RUN_TAG:
        cmd.append(RUN_TAG)

    trial_res_dir = os.path.join(RESULTS_DIR, f"trial_{trial_id(light, speed, traj, rep)}")
    timed_out_any = False
    for attempt in range(1, TRIAL_RETRIES + 2):
        print(f"\n[{time.strftime('%H:%M:%S')}] RUNNING (attempt {attempt}/{TRIAL_RETRIES + 1}): {' '.join(cmd)}")
        timed_out, elapsed, rc = exec_trial(cmd, TRIAL_TIMEOUT)
        timed_out_any = timed_out_any or timed_out
        print(f"[{time.strftime('%H:%M:%S')}] Finished in {elapsed:.1f}s, exit={rc}, timeout={timed_out}")
        write_manifest(trial_res_dir, light, speed, traj, rep)
        if not timed_out:
            break
        if attempt <= TRIAL_RETRIES:
            print("    -> retrying once after timeout")
        else:
            print("    -> timeout again; marking hang")

    row = read_trial_summary(trial_res_dir)
    metrics = read_metrics(trial_res_dir)
    if row is not None:
        status = "ok"
    elif timed_out_any:
        status = "hang"
    else:
        status = "crash"
    return row, status, metrics


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

    # Disk-space guard: refuse to start (and abort mid-run) when the recording
    # target cannot hold MIN_FREE_BAGS bags, so a run never dies half-way with
    # a truncated bag.
    fb = free_bytes(DATA_DIR)
    if fb is not None and fb < MIN_FREE_BYTES:
        print(f"ERROR: {fb / 1e9:.2f} GB free at {DATA_DIR}, need "
              f">= {MIN_FREE_BYTES / 1e9:.2f} GB (hard floor). Aborting.")
        sys.exit(2)
    if fb is not None:
        print(f"Disk check OK: {fb / 1e9:.2f} GB free "
              f"(>= {MIN_FREE_BYTES / 1e9:.2f} GB required).")

    run_count = 0
    for idx, (l, s, t, r) in enumerate(pending, 1):
        if args.limit and run_count >= args.limit:
            print(f"\nReached batch limit ({args.limit}). Stopping.")
            break

        print(f"\n>>> Trial [{idx}/{len(pending)}] Overall: [Done {done_count + run_count}/{total}]")
        print(f"    Setting: Light={l}, Speed={s} m/s, Trajectory={t}, Repeat=r{r}")

        fb = free_bytes(DATA_DIR)
        if fb is not None and fb < MIN_FREE_BYTES:
            print(f"ERROR: only {fb / 1e9:.2f} GB free (< {MIN_FREE_BYTES / 1e9:.2f} GB). "
                  f"Stopping before the next recording.")
            break

        # Choose flight duration based on speed
        # At 0.5 m/s, circle lap takes ~63s; at 1.5 m/s takes ~21s; at 3.0 m/s takes ~10.5s
        flight_dur = 55 if s == "0.5" else 45

        row, status, metrics = run_single_trial(l, s, t, r, radius=5.0, alt=3.0, dur=flight_dur)
        mcols = [metrics.get("wall_s", ""), metrics.get("bag_sim_dur_s", ""),
                 metrics.get("imu_hz", ""), metrics.get("rtf", "")]
        if row is not None:
            row = row + mcols
            append_result(SUMMARY_CSV, row)
            note = row[11]
            ate = row[4]
            rpe = row[9]
            print(f"    -> Result: note={note}, ATE_RMS={ate} m, RPE_RMS={rpe} m, "
                  f"wall={mcols[0]}s sim={mcols[1]}s imu_hz={mcols[2]} rtf={mcols[3]}")
            # Free disk: a successful trial only needs summary/traj/evo artifacts.
            if args.cleanup:
                bag_base = os.path.join(DATA_DIR, "rosbags",
                                        f"{trial_id(l, s, t, r)}.bag")
                trial_res_dir = os.path.join(RESULTS_DIR,
                                             f"trial_{trial_id(l, s, t, r)}")
                preserve_evidence(trial_res_dir, bag_base, metrics)
                removed = False
                for bp in (bag_base, bag_base + ".active", bag_base + ".orig.bag"):
                    if os.path.exists(bp):
                        os.remove(bp)
                        removed = True
                if removed:
                    print(f"    -> Cleaned bag + sidecars: {os.path.basename(bag_base)}")
        else:
            print(f"    -> ERROR: no summary for {trial_id(l, s, t, r)} (status={status})")
            fallback_row = [l, s, t, f"r{r}", "N/A", "N/A", "N/A", "N/A", "N/A",
                            "N/A", "N/A", status,
                            trial_id(l, s, t, r),
                            f"light={l}; speed={s}m/s; traj={t}; repeat=r{r}"] + mcols
            append_result(SUMMARY_CSV, fallback_row)

        run_count += 1
        time.sleep(5)

    print(f"\n==================================================")
    print(f" Batch run completed {run_count} trials.")
    print(f" Master summary: {SUMMARY_CSV}")
    print(f"==================================================")


if __name__ == "__main__":
    main()
