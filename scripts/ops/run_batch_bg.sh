#!/bin/bash
cd /root/catkin_ws/src/vins_research
nohup python3 /root/catkin_ws/src/vins_research/scripts/ops/batch_run_54.py "$@" > /data/results/batch_run.log 2>&1 &
echo "BATCH_PID=$!"
