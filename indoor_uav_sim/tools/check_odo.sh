#!/bin/bash
set +u
timeout 5 gz topic -e -t /model/x500_0/odometry_with_covariance -n 1 > /tmp/odo2.log 2>&1
grep -aE 'x: \S+$|y: \S+$|z: \S+$' /tmp/odo2.log | head -12
echo "--- cmd_vel echo ---"
source /opt/ros/jazzy/setup.bash; source /workspace/disaster_drone_ws/install/setup.bash
timeout 3 ros2 topic echo /drone/cmd_vel --once 2>&1 | head -10