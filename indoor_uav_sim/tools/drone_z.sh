#!/bin/bash
set +u
timeout 5 gz topic -e -t /world/three_floor_building/pose/info -n 20 > /tmp/loop_pose.log 2>&1
python3 - <<'PY'
import re
txt = open('/tmp/loop_pose.log').read()
# get the header-separated messages; find each message's x500_0 block
for i, msg in enumerate(txt.split('name: "x500_0"')[1:], 1):
    m = re.search(r'pose \{ position \{[^}]*\} ', msg)
    if m:
        seg = m.group(0)
        xs = re.search(r'x:\s*(-?[\d.]+)', seg)
        ys = re.search(r'y:\s*(-?[\d.]+)', seg)
        zs = re.search(r'z:\s*(-?[\d.]+)', seg)
        print(f"msg{i:2d} x={xs.group(1) if xs else '?'} y={ys.group(1) if ys else '?'} z={zs.group(1) if zs else '?'}", seg.replace("\n"," ")[:120])
PY