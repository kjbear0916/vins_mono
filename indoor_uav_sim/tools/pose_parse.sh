#!/bin/bash
set +u
timeout 5 gz topic -e -t /world/three_floor_building/pose/info -n 3 > /tmp/poseinfo.log 2>&1
echo "lines: $(wc -l < /tmp/poseinfo.log)"
python3 - <<'PY'
import re
txt = open('/tmp/poseinfo.log').read()
name = None
for m in re.finditer(r'name: "([^"]+)"', txt):
    name = m.group(1)
    print("name:", name)
pos = re.findall(r'position \{[^}]*\}', txt)
for p in pos[:8]:
    print(p[:120])
PY