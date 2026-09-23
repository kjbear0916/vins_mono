#!/bin/bash
set +u
source /opt/ros/jazzy/setup.bash
source /workspace/disaster_drone_ws/install/setup.bash
echo "== recent px4 status lines =="
tr '\r' '\n' < /tmp/px4_sitl.log | grep -aE 'ekf|attitude|offboard|failsafe|arm|land|status|vehicle|commander|preflight' | tail -20
echo
echo "== kp and gain in navigator =="
grep -nE 'kp|max_h|max_v|pos_tol' /workspace/disaster_drone_ws/src/marker_navigation/marker_navigation/waypoint_navigator_node.py | head -10
echo
echo "== recent cmd_vel =="
timeout 4 ros2 topic echo /drone/cmd_vel --once 2>&1 | head -10
echo
echo "== fused source =="
timeout 3 ros2 topic echo /drone/pose/fused --once 2>&1 | grep -aE 'source|confidence|frame_id' | head -5
echo
echo "== recent px4 gyro/ekf warnings =="
tr '\r' '\n' < /tmp/px4_sitl.log | grep -aE 'missing|data|ekf|accel|gyro|baro|compass|estimator' | tail -15