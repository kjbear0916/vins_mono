#!/bin/bash
set +u
echo "== all process errors in log =="
grep -aE '\[ERROR\]|process has died|Traceback|SIG|What|terminate|assert' /tmp/full_system.log | sort -u | head -30
echo
echo "== pose_fusion trace (search for exception context) =="
grep -aB2 -A12 'Traceback' /tmp/full_system.log | head -60
echo
echo "== nodes alive now =="
source /opt/ros/jazzy/setup.bash
source /workspace/disaster_drone_ws/install/setup.bash
ros2 node list 2>/dev/null