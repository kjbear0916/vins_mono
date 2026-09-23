#!/bin/bash
set -u
export DISPLAY=:0
export LIBGL_ALWAYS_SOFTWARE=1
export MESA_GL_VERSION_OVERRIDE=4.0
export GZ_SIM_SYSTEM_PLUGIN_PATH=/usr/lib/x86_64-linux-gnu/gz-sim-8/plugins
export GZ_SIM_RESOURCE_PATH=/workspace/disaster_drone_ws/src/drone_bringup/models:/workspace/disaster_drone_ws/src/drone_bringup/worlds:/opt/PX4-Autopilot/Tools/simulation/gz/models

trial() {
  name="$1"; world="$2"
  echo "===== $name : $world ====="
  timeout 30 gz sim -s -v 2 -r "$world" >/tmp/trial.log 2>&1 &
  sleep 28
  echo "-- loaded systems:"
  grep -E 'Loaded system \[gz' /tmp/trial.log | sed -E 's/.*Loaded system \[([^]]+)\].*/\1/'
  echo "-- failures:"
  grep -E 'Failed to load' /tmp/trial.log || true
  echo "-- exit/status: $(pgrep -f "gz sim -s -v 2 -r $world" >/dev/null && echo RUNNING || echo EXITED)"
  timeout -s KILL 3 gz sim >/dev/null 2>&1
  pkill -9 -f "gz sim -s -v 2 -r $world" 2>/dev/null
  sleep 2
}

trial default "/opt/PX4-Autopilot/Tools/simulation/gz/worlds/default.sdf"
trial empty "/usr/share/gz/gz-sim8/worlds/empty.sdf"