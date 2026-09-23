#!/bin/bash
set -u
export DISPLAY=:0
export LIBGL_ALWAYS_SOFTWARE=1
export MESA_GL_VERSION_OVERRIDE=4.0
export GZ_SIM_SYSTEM_PLUGIN_PATH=/usr/lib/x86_64-linux-gnu/gz-sim-8/plugins
export GZ_SIM_RESOURCE_PATH=/workspace/disaster_drone_ws/src/drone_bringup/models:/workspace/disaster_drone_ws/src/drone_bringup/worlds:/opt/PX4-Autopilot/Tools/simulation/gz/models

strip() { sed -E 's/\x1b\[[0-9;]*m//g'; }

run_case() {
  name="$1"; world="$2"
  pkill -9 -f "gz sim -s -v 4" 2>/dev/null; sleep 1
  gz sim -s -v 4 -r "$world" >"/tmp/case_$name.log" 2>&1 &
  sleep 14
  echo "=== $name ==="
  echo "loaded:"
  grep -a 'Loaded system \[' "/tmp/case_$name.log" | strip | sed -E 's/.*Loaded system \[([^]]+)\].*/\1/' | sort -u
  echo "failed:"
  grep -a 'Failed to load' "/tmp/case_$name.log" | strip | sed -E 's/.*plugin \[([^]]+)\].*/\1/' | sort -u
  echo "(world-init: $(grep -a 'initialized with' /tmp/case_$name.log | strip | head -1))"
  pkill -9 -f "gz sim -s -v 4" 2>/dev/null; sleep 1
}

run_case "A_plus_plugin" /tmp/A_plus_plugin.sdf
run_case "C_minimal" /tmp/C_minimal.sdf