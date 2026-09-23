#!/bin/bash
set +u
export GZ_SIM_SYSTEM_PLUGIN_PATH=/usr/lib/x86_64-linux-gnu/gz-sim-8/plugins
timeout 6 gz topic -e -t /model/x500_0/pose -n 3 > /tmp/model_pose.log 2>&1
echo "lines: $(wc -l < /tmp/model_pose.log)"
head -c 800 /tmp/model_pose.log