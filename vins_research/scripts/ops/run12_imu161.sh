#!/bin/bash
# run12_imu161.sh — item #12: higher-rate IMU subset (6 cells x 3 reps).
#
# PX4's SITL onboard MAVLink link is patched so HIGHRES_IMU is requested at
# IMU_HZ (below: 200). Measured on bag sim-time the achieved rate is a steady
# ~125 Hz (min/median/max 125.0/125.0/126.5; see README #12), so this arm is
# tagged "imu161" to label the achieved rate honestly; sim_launch.sh resets
# the rate to 50 Hz whenever IMU_HZ is unset, so the high-rate setting cannot
# silently persist.
#
# Ordering is rep-major (see run12_subset.py). Bags are cleaned after each
# successful trial (18 x ~450-600 MB >> free space on /data).
set +e

# Single-flight lock via flock: the lock is released automatically when this
# process exits, so a crash can never leave a stale lock that either blocks
# every relaunch or races on manual removal.
exec 9>/tmp/run12_imu161.lock
if ! flock -n 9; then
  echo "run12_imu161.sh already active (lock held); exiting."
  exit 0
fi

source /opt/ros/noetic/setup.bash 2>/dev/null
source /root/catkin_ws/devel/setup.bash 2>/dev/null
export VINS_RESULTS_DIR=/data/results_imu161
export VINS_SUMMARY_CSV=/data/results_imu161/summary_54.csv
export RUN_TAG=imu161
export IMU_HZ=200
export VINS_TRIAL_TIMEOUT=${VINS_TRIAL_TIMEOUT:-720}
export VINS_TRIAL_RETRIES=${VINS_TRIAL_RETRIES:-1}
cd /root/catkin_ws/src/vins_research || exit 1
python3 -u scripts/ops/run12_subset.py
