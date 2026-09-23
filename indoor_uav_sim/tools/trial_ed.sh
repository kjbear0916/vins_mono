#!/bin/bash
set -u
pkill -9 -f "gz sim" 2>/dev/null; sleep 2
export DISPLAY=:0
export LIBGL_ALWAYS_SOFTWARE=1
export MESA_GL_VERSION_OVERRIDE=4.0
export GZ_SIM_SYSTEM_PLUGIN_PATH=/usr/lib/x86_64-linux-gnu/gz-sim-8/plugins
export GZ_SIM_RESOURCE_PATH=/workspace/disaster_drone_ws/src/drone_bringup/models:/workspace/disaster_drone_ws/src/drone_bringup/worlds:/opt/PX4-Autopilot/Tools/simulation/gz/models

gz sim -s -v 4 -r /workspace/disaster_drone_ws/src/drone_bringup/worlds/three_floor_building.sdf >/tmp/tri_ed.log 2>&1 &
echo "gz pid $!"
sleep 18
grep -aE '\[Dbg\]|\[Msg\]|\[Err\]|\[Erm\]' /tmp/tri_ed.log > /tmp/tri_ed_clean.log
echo "== every system/plugin line:"
grep -aE 'system|plugin|Physics|physics' /tmp/tri_ed_clean.log | head -40
echo "== errors/warnings:"
grep -aE '\[Erm\]|\[Err\]' /tmp/tri_ed_clean.log | grep -avE 'Failed to load|timed' | head -20 || true
echo "== include/spawn:"
grep -aE 'include|spawn|Created|Loaded level' /tmp/tri_ed_clean.log | head -20
echo "== live-check: (server runs?) =="
sleep 3
pgrep -f "gz sim -s -v 4" >/dev/null && echo YES || echo NO