#!/bin/bash
set +u
echo "== full_system6 log (drone_control lines) =="
grep -a 'drone_control' /tmp/full_system6.log | tail -20
echo
echo "== mavlink config in current px4 =="
tr '\r' '\n' < /tmp/px4_sitl.log | grep -aE 'mavlink|MAVLINK' | tail -20
echo
echo "== px4 mavlink topic dig =="
cd /opt/PX4-Autopilot
export PX4_SIM_MODEL=gz_x500
timeout 5 ./build/px4_sitl_default/bin/px4 mavlink status 2>&1 | head -20 || true