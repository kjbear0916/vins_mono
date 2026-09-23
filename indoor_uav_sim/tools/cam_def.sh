#!/bin/bash
set +u
echo "== nadir cam definition in px4 x500 model =="
grep -nA14 'sensor_nadir' /opt/PX4-Autopilot/Tools/simulation/gz/models/x500_base/model.sdf | head -40
echo
echo "== gz camera positions/pose in world =="
grep -rnE 'sensor_nadir|sensor_front' /workspace/disaster_drone_ws/src/drone_bringup/worlds/three_floor_building.sdf | head