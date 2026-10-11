#!/bin/bash
# run11_rerun54.sh — item #11: re-run the full 54-matrix with the FIXED repo
# trial_one.sh, into a SEPARATE results tree so the committed master evidence
# (/data/results/summary_54.csv) is never clobbered.
#
# The master 54 was produced by the container /tmp/trial_one.sh; the repo
# scripts/ops/trial_one.sh differs (22 lines: $REPO paths, bag reindex,
# evaluate_all exit 3/4 handling). This run quantifies whether that difference
# changes the matrix. Bags are cleaned after each successful trial — 54 x ~400 MB
# far exceeds the ~6.7 GB free on /data.
set +e
source /opt/ros/noetic/setup.bash 2>/dev/null
source /root/catkin_ws/devel/setup.bash 2>/dev/null
export VINS_RESULTS_DIR=/data/results_rerun54
export VINS_SUMMARY_CSV=/data/results_rerun54/summary_54.csv
export RUN_TAG=repo54
# Per-trial wall-clock ceiling + single retry (healthy trial ~150-250 s).
export VINS_TRIAL_TIMEOUT=${VINS_TRIAL_TIMEOUT:-720}
export VINS_TRIAL_RETRIES=${VINS_TRIAL_RETRIES:-1}
cd /root/catkin_ws/src/vins_research || exit 1
python3 -u scripts/ops/batch_run_54.py --cleanup
