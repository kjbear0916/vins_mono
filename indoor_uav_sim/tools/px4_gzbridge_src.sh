#!/bin/bash
set +u
cd /opt/PX4-Autopilot/src/modules/simulation/gz_bridge
echo "== files =="
ls
echo "== how sensors are discovered/bridged =="
grep -nE 'gazebo/|Subscribe|topic|world|\bworld\b|model_name|IMU|baro|navsat|magnetometer' gz_bridge.cpp 2>/dev/null | head -25
grep -rnE 'SUBSCRIBE_TO_GZ|subscribe|sensor.*topic|"sensor' gz_bridge.cpp gz_sensors*.* 2>/dev/null | head -25