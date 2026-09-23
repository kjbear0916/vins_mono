#!/bin/bash
set +u
export GZ_SIM_SYSTEM_PLUGIN_PATH=/usr/lib/x86_64-linux-gnu/gz-sim-8/plugins
timeout 5 gz topic -i -t /model/x500_0/odometry_with_covariance 2>&1 | head -8
echo "== existing bridge yaml =="
cat /workspace/disaster_drone_ws/src/drone_bringup/config/ros_bridge.yaml