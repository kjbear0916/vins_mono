#!/bin/bash
set -u
python3 -c "import xml.dom.minidom as m; m.parse('/workspace/disaster_drone_ws/src/drone_bringup/worlds/three_floor_building.sdf'); print('XML OK')"
pkill -9 -f "gz sim" 2>/dev/null; sleep 2
export DISPLAY=:0
export LIBGL_ALWAYS_SOFTWARE=1
export MESA_GL_VERSION_OVERRIDE=4.0
export GZ_SIM_SYSTEM_PLUGIN_PATH=/usr/lib/x86_64-linux-gnu/gz-sim-8/plugins
export GZ_SIM_RESOURCE_PATH=/workspace/disaster_drone_ws/src/drone_bringup/models:/workspace/disaster_drone_ws/src/drone_bringup/worlds:/opt/PX4-Autopilot/Tools/simulation/gz/models

gz sim -s -v 4 -r /workspace/disaster_drone_ws/src/drone_bringup/worlds/three_floor_building.sdf >/tmp/trial_tri.log 2>&1 &
echo "gz pid $!"
sleep 20
echo "== Loaded systems:"
grep -E 'Loaded system \[' /tmp/trial_tri.log | sed -E 's/.*Loaded system \[([^]]+)\].*/\1/' | sort -u
echo "== Failed:"
grep -E 'Failed to load' /tmp/trial_tri.log || echo none
echo "== world init:"
grep -E 'World \[|initialized with' /tmp/trial_tri.log | head -2
echo "== pose_topic test:"
gz topic -e -t /world/three_floor_building/pose/info -n 2 >/tmp/pose_sample.log 2>&1 &
sleep 3
kill %1 2>/dev/null
wc -l /tmp/pose_sample.log 2>/dev/null
echo "== alive: $(pgrep -f 'gz sim -s -v 4' >/dev/null && echo YES || echo NO)"
pkill -9 -f "gz sim -s -v 4" 2>/dev/null
exit 0