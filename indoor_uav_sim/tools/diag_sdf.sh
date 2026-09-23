#!/bin/bash
set -u
echo "===== /opt/PX4-Autopilot/Tools/simulation/gz/worlds/default.sdf ====="
cat /opt/PX4-Autopilot/Tools/simulation/gz/worlds/default.sdf
echo
echo "===== our world tags (unique) ====="
grep -oE '<[a-zA-Z/!][a-zA-Z0-9_-]*' /workspace/disaster_drone_ws/src/drone_bringup/worlds/three_floor_building.sdf | sort -u