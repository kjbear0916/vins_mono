#!/bin/bash
set +u
source /opt/ros/jazzy/setup.bash
source /workspace/disaster_drone_ws/install/setup.bash
echo "== marker detector log =="
grep -a 'marker_detector' /tmp/full_system7.log | tail -15
echo
echo "== fused pose current =="
timeout 3 ros2 topic echo /drone/pose/fused --once 2>&1 | grep -aE 'x:|y:|z:|w:|frame_id' | head -8
echo
echo "== uwb pose =="
timeout 3 ros2 topic echo /drone/uwb/pose --once 2>&1 | grep -aE 'x:|y:|z:|w:|frame_id' | head -8
echo
echo "== mission status =="
timeout 3 ros2 topic echo /mission/status --once 2>&1 | grep -aE 'phase|waypoint|floor|anchor|survivor|source|elapsed' | head -8
echo
echo "== marker pose =="
timeout 3 ros2 topic echo /drone/marker/pose --once 2>&1 | grep -aE 'x:|y:|z:|w:|frame_id|marker' | head -8