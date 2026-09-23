#!/bin/bash
set -u
export DISPLAY=:0
export LIBGL_ALWAYS_SOFTWARE=1
export MESA_GL_VERSION_OVERRIDE=4.0
export GZ_SIM_SYSTEM_PLUGIN_PATH=/usr/lib/x86_64-linux-gnu/gz-sim-8/plugins
export GZ_SIM_RESOURCE_PATH=/workspace/disaster_drone_ws/src/drone_bringup/models:/workspace/disaster_drone_ws/src/drone_bringup/worlds:/opt/PX4-Autopilot/Tools/simulation/gz/models

world="${1:-/opt/PX4-Autopilot/Tools/simulation/gz/worlds/default.sdf}"
gz sim -s -v 4 -r "$world" >/tmp/trial4.log 2>&1 &
sleep 30
echo "===== $world ====="
echo "== Loaded systems:"
grep -E 'Loaded system \[' /tmp/trial4.log | sed -E 's/.*Loaded system \[([^]]+)\].*/\1/' | sort -u
echo "== Failed:"
grep -E 'Failed to load' /tmp/trial4.log || true
echo "== clock topics:"
gz topic -l 2>/dev/null | grep -E 'clock|pose' | head
echo "== server alive: $(pgrep -f "gz sim -s -v 4" >/dev/null && echo YES || echo NO)"
pkill -9 -f "gz sim -s -v 4" 2>/dev/null
exit 0