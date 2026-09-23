#!/usr/bin/env python3
import re, math
txt = open('/tmp/dp2.log').read()
for i, block in enumerate(txt.split('name: "x500_0"')[1:], 1):
    m = re.search(r'position \{ x: (-?[\d.]+) y: (-?[\d.]+) z: (-?[\d.]+) \} '
                  r'orientation \{ x: (-?[\d.]+) y: (-?[\d.]+) z: (-?[\d.]+) w: (-?[\d.]+) \}', block)
    if not m:
        print(f"msg{i}: no full match; head:", block[:200].replace('\n',' '))
        continue
    x,y,z,qx,qy,qz,qw = map(float, m.groups())
    roll = math.atan2(2*(qw*qx+qy*qz), 1-2*(qx*qx+qy*qy))*180/math.pi
    pitch = math.asin(max(-1,min(1,2*(qw*qy-qz*qx))))*180/math.pi
    yaw = math.atan2(2*(qw*qz+qx*qy), 1-2*(qy*qy+qz*qz))*180/math.pi
    print(f"msg{i} pos=({x:.2f},{y:.2f},{z:.2f}) rpy=({roll:.1f},{pitch:.1f},{yaw:.1f})")