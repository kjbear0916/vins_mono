#!/bin/bash
set +u
export GZ_SIM_SYSTEM_PLUGIN_PATH=/usr/lib/x86_64-linux-gnu/gz-sim-8/plugins
timeout 8 gz topic -e -t /world/three_floor_building/dynamic_pose/info -n 1 > /tmp/dp_pose.log 2>&1
echo "raw size: $(wc -c < /tmp/dp_pose.log)"
python3 - <<'PY'
import re
txt = open('/tmp/dp_pose.log').read()
# find x500_0 blocks: name: "x500_0" then ...
parts = txt.split('name: "x500_0"')
for i, block in enumerate(parts[1:], 1):
    print(f"x500_0 block {i}, length {len(block)}")
    # get next few lines
    for line in block.split('\n')[:15]:
        print('  ', line)
PY