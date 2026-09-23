#!/bin/bash
# Atomic ops. Kill ONLY the sim chain (keep roscore so model spawns fast),
# relaunch px4 from the CORRECT CWD (build/px4_sitl_default, which holds
# etc/ -> fixes the recurring "Error opening startup file rcS" death),
# and immediately after second-0 single-bound companion3 (0.0.0.0:14540,
# SO_REUSEADDR + continuous HB + OFFBOARD setpoints from the very first
# packet, exactly like the wire-proven monitor, so the link never idles).
set -x
pkill -x gzserver; pkill -x px4
pkill -f sitl_run.sh; pkill -f sitl_run.sh
sleep 4
ps -eo pid,etimes,cmd | grep -E 'gzserver|/bin/px4' | grep -v grep || echo CLEAN
echo ==FRESH==
cd /root/PX4-Autopilot/build/px4_sitl_default
DISPLAY=:99 nohup bash /root/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_run.sh \
  /root/PX4-Autopilot/build/px4_sitl_default/bin/px4 none iris_fpv_cam empty \
  /root/PX4-Autopilot /root/PX4-Autopilot/build/px4_sitl_default \
  > /tmp/sim_fresh60.log 2>&1 &
echo ==WAIT_PX4==
for i in $(seq 1 30); do
  pgrep -x px4 >/dev/null && echo PX4_UP_i=$i && break
  sleep 2
done
pgrep -x px4 >/dev/null || { echo PX4_FAILED; cat /tmp/sim_fresh60.log | tail -20; exit 1; }
et_start=$(cat /proc/$(pgrep -x px4)/stat 2>/dev/null | awk '{print $22}')
echo ==COMPANION_SEC0==
python3 /tmp/companion3.py
echo ==DONE==
