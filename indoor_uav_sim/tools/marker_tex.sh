#!/bin/bash
set +u
cd /workspace/disaster_drone_ws/src/drone_bringup/models/marker_100
echo "== files =="
find . -type f | head
echo "== image info =="
python3 - <<'PY'
from PIL import Image
img = Image.open("materials/textures/marker_100.png")
print("size", img.size, "mode", img.mode, "extent", img.getextrema())
PY