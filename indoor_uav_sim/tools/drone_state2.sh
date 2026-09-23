#!/bin/bash
set +u
timeout 6 gz topic -e -t /world/three_floor_building/dynamic_pose/info -n 3 > /tmp/dp2.log 2>&1
cp /tmp/dp2.log /tmp/dp2_preserved.log
python3 /workspace/disaster_drone_ws/tools/parse_dp.py