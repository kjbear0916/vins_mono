#!/bin/bash
set +u
cd /opt/PX4-Autopilot/src/modules/simulation/gz_bridge
echo "== server.config =="
cat server.config
echo
echo "== GZBridge.cpp key parts =="
grep -nE 'sensor|imu|baro|navsat|mag|subscribe|Advertise|topic|Topic' GZBridge.cpp | head -30
echo
echo "== which PX4 modules subscribe to sim sensors =="
grep -rlnE 'sensor_imu|sensor_baro|sensor_gz|gazebo' /opt/PX4-Autopilot/src/modules/simulation/ 2>/dev/null | head