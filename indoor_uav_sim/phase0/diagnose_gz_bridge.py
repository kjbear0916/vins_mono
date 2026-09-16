#!/usr/bin/env python3
"""
diagnose_gz_bridge.py
Diagnose PX4 SITL <-> Gazebo transport IMU data break.

Hypotheses:
  1. GZ_PARTITION mismatch
  2. Model name mismatch (stale instances)
  3. Sensor plugin not publishing

Usage:
  python3 diagnose_gz_bridge.py
  (Run while PX4 + Gazebo are started and Phase 0 is stuck)
"""
import subprocess
import os
import re
import sys
import time

HOME = os.path.expanduser("~")
os.environ["PATH"] = HOME + "/bin:" + os.environ["PATH"]


def run(cmd, timeout=None):
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return "", "(timeout)"


def section(title):
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


def get_env_var(pid, key):
    try:
        with open(f"/proc/{pid}/environ", "rb") as f:
            env = f.read().decode(errors="ignore")
        for kv in env.split("\x00"):
            if kv.startswith(key + "="):
                return kv.split("=", 1)[1]
        return None
    except Exception as e:
        return f"(read failed: {e})"


def check_processes():
    px4_pids = run("pgrep -f px4_sitl_default")[0].splitlines()
    gz_pids = run("pgrep -f 'gz sim'")[0].splitlines()
    if not px4_pids:
        print("px4_sitl_default not found - PX4 may not be running")
    if not gz_pids:
        print("gz sim not found - Gazebo may not be running")
    return px4_pids, gz_pids


def check_partition(px4_pids, gz_pids):
    section("[Hypothesis 1] GZ_PARTITION consistency")
    shell_partition = os.environ.get("GZ_PARTITION")
    print("Shell GZ_PARTITION:", shell_partition or "(unset -> default)")

    partitions = set()
    for pid in px4_pids:
        p = get_env_var(pid, "GZ_PARTITION")
        print(f"PX4 (pid={pid}) GZ_PARTITION = {p or '(unset -> default)'}")
        partitions.add(p or "default")
    for pid in gz_pids:
        p = get_env_var(pid, "GZ_PARTITION")
        print(f"gz sim (pid={pid}) GZ_PARTITION = {p or '(unset -> default)'}")
        partitions.add(p or "default")

    for pid in px4_pids + gz_pids:
        for key in ("GZ_IP", "GZ_RELAY_ADDRESS", "GZ_DISCOVERY_MSG_PORT"):
            v = get_env_var(pid, key)
            if v:
                print(f"  (pid={pid}) {key} = {v}")

    if len(partitions) > 1:
        print("FAIL: GZ_PARTITION mismatch - discovery cannot find each other")
        return "FAIL"
    else:
        print("OK: partition consistent (all default or same value)")
        return "OK"


def check_model_name(px4_pids):
    section("[Hypothesis 2] model name mismatch / stale instances")
    model_name = None
    for pid in px4_pids:
        v = get_env_var(pid, "PX4_GZ_MODEL_NAME")
        if v:
            model_name = v
            print(f"PX4_GZ_MODEL_NAME (pid={pid}) = {v}")
    if not model_name:
        print("PX4_GZ_MODEL_NAME not set, fallback to default (x500_0)")

    out, err = run("gz topic -l", timeout=5)
    if err and "timeout" in err:
        print(f"'gz topic -l' failed: {err}")
        return "UNKNOWN"

    models = sorted(set(re.findall(r"/world/\w+/model/([^/]+)/", out)))
    print("Models in world:", models if models else "(none found)")

    if len(models) > 1:
        print(f"FAIL: multiple model instances {models} - likely stale")
        print("  Fix: pkill -9 -f 'gz sim' and restart")
        return "FAIL"
    elif model_name and models and model_name not in models:
        print(f"FAIL: PX4 expects '{model_name}' but world has '{models}'")
        return "FAIL"
    else:
        print("OK: no model name conflict detected")
        return "OK"


def check_sensor_publishing():
    section("[Hypothesis 3] sensor plugin actually publishing")
    out, _ = run("gz topic -l", timeout=5)
    imu_topics = [t for t in out.splitlines() if "imu" in t.lower()]
    accel_topics = [t for t in out.splitlines() if "accel" in t.lower()]
    all_sensor_topics = sorted(set(imu_topics + accel_topics))

    if not all_sensor_topics:
        print("No IMU/accel topics found in gz topic list")
        print("  -> sensor plugin may not be loaded in world SDF")
        return "FAIL"

    print("Found topics:", all_sensor_topics)

    any_data = False
    for topic in all_sensor_topics:
        print(f"\nEchoing {topic} (max 5s)...")
        out, err = run(f"timeout 5 gz topic -e -t {topic} -n 1", timeout=7)
        if out:
            print(f"  HAS DATA: {out[:300]}")
            any_data = True
        else:
            print(f"  NO DATA in 5s (stderr: {err[:200]})")

    if any_data:
        print("\nOK: Gazebo is publishing sensor data. Problem is in PX4 bridge subscription.")
        return "OK"
    else:
        print("\nFAIL: Gazebo not publishing IMU/accel data at all.")
        return "FAIL"


def check_gz_bridge_subscribers():
    section("[Extra] Check if PX4 bridge has active gz subscribers")
    out, _ = run("gz topic -l", timeout=5)
    imu_topics = [t for t in out.splitlines() if "imu" in t.lower()]

    for topic in imu_topics:
        print(f"\nChecking subscribers on {topic}...")
        info, _ = run(f"gz topic -i -t {topic}", timeout=5)
        if info:
            print(f"  {info}")
        else:
            print(f"  (no subscriber info available)")

    accel_topics = [t for t in out.splitlines() if "accel" in t.lower()]
    for topic in accel_topics:
        print(f"\nChecking subscribers on {topic}...")
        info, _ = run(f"gz topic -i -t {topic}", timeout=5)
        if info:
            print(f"  {info}")
        else:
            print(f"  (no subscriber info available)")


def main():
    print("PX4 <-> Gazebo IMU data break diagnostic")
    print("Start time:", time.strftime("%Y-%m-%d %H:%M:%S"))

    px4_pids, gz_pids = check_processes()
    if not px4_pids or not gz_pids:
        print("\nPlease start PX4 SITL and gz sim first, then re-run.")
        sys.exit(1)

    r1 = check_partition(px4_pids, gz_pids)
    r2 = check_model_name(px4_pids)
    r3 = check_sensor_publishing()
    check_gz_bridge_subscribers()

    section("Summary")
    results = {
        "H1 (GZ_PARTITION)": r1,
        "H2 (model name)": r2,
        "H3 (sensor plugin)": r3,
    }
    for k, v in results.items():
        mark = "FAIL" if v == "FAIL" else ("OK" if v == "OK" else "?")
        print(f"[{mark}] {k}: {v}")

    if r3 == "FAIL":
        print("\nNext: fix sensor plugin loading (check world SDF, renderer delay)")
    elif r3 == "OK" and (r1 == "FAIL" or r2 == "FAIL"):
        print("\nNext: data source OK, fix PX4 bridge subscription (partition or model name)")
    elif r3 == "OK" and r1 == "OK" and r2 == "OK":
        print("\nNext: all 3 hypotheses排除, need deeper investigation:")
        print("  - gz transport debug logs")
        print("  - PX4 bridge callback logging")
        print("  - lockstep scheduling check")


if __name__ == "__main__":
    main()
