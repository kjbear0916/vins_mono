#!/bin/bash
set +u
source /opt/ros/jazzy/setup.bash
source /workspace/disaster_drone_ws/install/setup.bash
echo "== nadir image rate =="
timeout 8 ros2 topic hz /drone/camera/nadir/image_raw 2>&1 | head -5
echo "== marker/uwb topic availability =="
timeout 4 ros2 topic info /drone/marker/pose 2>&1 | head -6
echo "== marker detections log =="
grep -aE 'detect|marker|publish' /tmp/full_system7.log | grep -a marker_detector | tail -8
echo "== marker_map markers =="
grep -cE '^\s+[0-9]+:' /workspace/disaster_drone_ws/src/drone_bringup/config/marker_map.yaml 2>/dev/null || true