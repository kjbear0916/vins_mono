#!/bin/bash
set +u
export GZ_SIM_SYSTEM_PLUGIN_PATH=/usr/lib/x86_64-linux-gnu/gz-sim-8/plugins
timeout 5 gz topic -e -t /world/three_floor_building/dynamic_pose/info -n 4 > /tmp/dynpose.log 2>&1
python3 - <<'PY'
import re
txt = open('/tmp/dynpose.log').read()
for m in re.finditer(r'name: "(x500_0[^"]*)"[^}]*?pose \{[^}]*?position \{\s*x: (-?[\d.]+)\s*y: (-?[\d.]+)\s*z: (-?[\d.]+)', txt, re.S):
    print(f"{m.group(1).ljust(25)} x={m.group(2)} y={m.group(3)} z={m.group(4)}")
PY
echo "== drone_control complete log =="
grep -a 'drone_control_node.py-10' /tmp/full_system7.log | grep -aE 'INFO|WARN|ERROR' | tail -15