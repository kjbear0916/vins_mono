#!/usr/bin/env python3
"""Synchronous fresh relaunch + companion2 from the SAME second-0 command.

Why this file exists (obs-driven):
  - wire60.pcap / /tmp/wire60.pcap proved PX4's onboard+companion stream goes
    to 127.0.0.1 (loopback-only) on 14540/14550. Bound-address was NEVER the
    bug. The recurring NO_HB is socket COMPETITION: two listeners (raw monitor
    + companion) alternating on the same loopback port -> kernel delivers UDP
    to only one, the other starves.
  - So the ONLY correct way to catch the fresh-window is: launch sim AND
    companion with exactly ONE UDP listener on 14540 total.

This orchestrates BOTH on one timeline and verifies the companion actually
armed+voted the aircraft. Steps:
  1. kill stale gzserver/px4 (fresh window = full-rate from second-0)
  2. relaunch via the same proven sim_launch.sh path (ros core stays up)
  3. sleep px4 boot (~28s) so many streams exist
  4. run /tmp/companion2.py (the cleaned persistent companion, binds
     0.0.0.0:14540 to mirror the proven raw monitor) and capture its output
Expected: within ~60-90s companion reports PARAM_OK + ARM_ACK + then we
observe vehicle armed via HEARTBEAT.
"""
import subprocess
import sys
import time

def sh(cmd, t=20):
    return subprocess.run(["bash", "-c", cmd], capture_output=True, text=True,
                          timeout=t).stdout

def main():
    print("== PREP ==", flush=True)
    print(sh("pkill -x gzserver; pkill -x px4; pkill -f sitl_run.sh; "
             "pkill -f sim_launch.sh; sleep 4; "
             "ps -eo pid,etimes,cmd | grep -E 'gzserver|/bin/px4' | grep -v grep || echo SIM_DEAD"))
    print("== RELAUNCH ==", flush=True)
    print(sh("cd /root && nohup bash /root/sim_launch.sh > /tmp/sim80.log 2>&1 & echo started; "
             "sleep 30; ps -eo pid,etimes,cmd | grep -E 'gzserver|/bin/px4' | grep -v grep"))
    print("== COMPANION 120s ==", flush=True)
    try:
        out = subprocess.run(["docker", "exec", "vins_research", "python3",
                              "/tmp/companion2.py"], capture_output=True, text=True,
                             timeout=150)
        print(out.stdout, flush=True)
        print("STDERR_TAIL:", out.stderr[-1500:], flush=True)
    except subprocess.TimeoutExpired:
        print("COMPANION_TIMEOUT", flush=True)

if __name__ == "__main__":
    sys.exit(main())
