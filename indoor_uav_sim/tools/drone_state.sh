#!/bin/bash
set +u
timeout 6 gz topic -e -t /world/three_floor_building/dynamic_pose/info -n 3 > /tmp/dp2.log 2>&1
python3 - <<'PY'
import re
txt = open('/tmp/dp2.log').read()
for i, block in enumerate(txt.split('name: "x500_0"')[1:], 1):
    m = re.search(r'position \{[^}]*\}'
                  r'[^}]*\}'
                  r'[^}]*\}'
                  r'position \{ x: (-?[\d.]+)\s'
                  r'y: (-?[\d.]+)\s'
                  r'z: (-?[\d.]+)\s'
                  r'\}\s'
                  r'orientation \{ x: (-?[\d.]+)\s'
                  r'y: (-?[\d.]+)\s'
                  r'z: (-?[\d.]+)\s'
                  r'w: (-?[\d.]+)', block)
    if m:
        x,y,z,qx,qy,qz,qw = map(float, m.groups())
        import math
        roll = math.atan2(2*(qw*qx+qy*qz), 1-2*(qx*qx+qy*qy))*180/math.pi
        pitch = math.asin(max(-1,min(1,2*(qw*qy-qz*qx))))*180/math.pi
        yaw = math.atan2(2*(qw*qz+qx*qy), 1-2*(qy*qy+qz*qz))*180/math.pi
        print(f"msg{i} pos=({x:.2f},{y:.2f},{z:.2f}) rpy=({roll:.1f},{pitch:.1f},{yaw:.1f})")
    else:
        print(f"msg{i} parse failed", block[:120].replace("\n"," "))
PY