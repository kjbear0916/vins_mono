#!/bin/bash
set +u
source /opt/ros/jazzy/setup.bash
source /workspace/disaster_drone_ws/install/setup.bash
echo "== fused pose =="
timeout 4 ros2 topic echo /drone/pose/fused --once 2>&1 | grep -aE 'x:|y:|z:|w:' | head -4
echo "== mission status =="
timeout 4 ros2 topic echo /mission/status --once 2>&1 | head -30
echo "== waypoint nav line =="
grep -a 'waypoint_navigator' /tmp/full_system7.log | tail -6