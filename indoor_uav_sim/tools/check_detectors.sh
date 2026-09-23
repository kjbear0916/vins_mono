#!/bin/bash
set +u
export GZ_SIM_SYSTEM_PLUGIN_PATH=/usr/lib/x86_64-linux-gnu/gz-sim-8/plugins
source /opt/ros/jazzy/setup.bash
source /workspace/disaster_drone_ws/install/setup.bash
echo "== phys pose via gz topic /model/x500_0 =="
timeout 4 gz topic -e -t /model/x500_0/pose -n 2 > /tmp/x_pose.log 2>&1 || true
grep -aE 'x:|y:|z:|w:' /tmp/x_pose.log | head -8
echo "== odometry topic? =="
timeout 3 gz topic -l | grep -aiE 'pose|odo' | head
echo "== marker hits =="
timeout 3 ros2 topic echo /drone/marker/pose --once 2>&1 | head -12
echo "== detect topic list =="
timeout 3 ros2 topic list | grep -aiE 'marker|detect|uwb|obstacle|survivor|cmd_vel' | head -20