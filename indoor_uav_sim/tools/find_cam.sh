#!/bin/bash
set +u
echo "== where is sensor_nadir defined? =="
grep -rlnE 'sensor_nadir' /workspace/disaster_drone_ws/src/ /opt/PX4-Autopilot/Tools/simulation/gz/models/ 2>/dev/null
echo
echo "== the x500_0 spawned model file =="
find / -name 'x500_base*' -path '*gz/models*' 2>/dev/null | head
echo "== check uRDF/other spawn =="
grep -rnE 'x500_base' /opt/PX4-Autopilot/build/px4_sitl_default/ 2>/dev/null | head -5