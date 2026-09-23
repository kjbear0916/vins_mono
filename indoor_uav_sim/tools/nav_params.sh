#!/bin/bash
set +u
echo "== navigator kp/max =="
grep -nE 'kp|max_h|max_v|pos_tol|vertical|speed' /workspace/disaster_drone_ws/src/marker_navigation/marker_navigation/waypoint_navigator_node.py | grep -E 'declare_parameter|self\.' | head -15
echo
echo "== waypoints yaml =="
find /workspace/disaster_drone_ws/src/drone_bringup/config -name '*.yaml' | head
echo
echo "== first waypoints =="
grep -rA2E 'id: 0|id: 1|id: 2|cruise' /workspace/disaster_drone_ws/src/drone_bringup/config/*.yaml 2>/dev/null | head -40