#!/bin/bash
set +u
source /opt/ros/jazzy/setup.bash
source /workspace/disaster_drone_ws/install/setup.bash
ros2 topic pub -1 /mission/command std_msgs/msg/String "{data: takeoff}" 2>&1 | tail -1
echo "== wait 30s, check gz drone pose =="
sleep 30
export GZ_SIM_SYSTEM_PLUGIN_PATH=/usr/lib/x86_64-linux-gnu/gz-sim-8/plugins
export GZ_PARTITION=default
timeout 3 gz topic -e -t /model/x500_0/odometry_with_covariance -n 2 >/tmp/odo.log 2>&1
python3 - <<'PY'
import re
txt = open('/tmp/odo.log').read()
for m in re.finditer(r'pose[^}]*(?:x:|y:|z:)', txt, re.S):
    pass
pos = re.findall(r'position \{ name: "[^"]*"\s*position \{ x: (-?[\d.]+) y: (-?[\d.]+) z: (-?[\d.]+)', txt)
for p in pos[:3]:
    print("pos x=%s y=%s z=%s" % p)
PY
echo "== drone_control log =="
grep -a 'drone_control' /tmp/full_system6.log | tail -8