#!/bin/bash
# run5_ctl_pair.sh — same-session 50 Hz control + rerun of the 2 suspect cells.
# Drives scripts/ops/rerun_pair.py (12 trials: 2 cells x 3 reps x {50Hz,~125Hz}).
set +e
source /opt/ros/noetic/setup.bash 2>/dev/null
source /root/catkin_ws/devel/setup.bash 2>/dev/null
export HEADLESS=1 NO_PXH=1
unset DISPLAY
cd /root/catkin_ws/src/vins_research || exit 1
python3 -u scripts/ops/rerun_pair.py