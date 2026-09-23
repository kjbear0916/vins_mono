#!/bin/bash
# Accept-launcher: start gz-sim server on the three_floor_building world.
# Usage: launch_gz_server.sh {start|stop}
set -u
LOG=/tmp/gz_server.log

export DISPLAY=:0
export LIBGL_ALWAYS_SOFTWARE=1
export MESA_GL_VERSION_OVERRIDE=4.0
export GZ_SIM_SYSTEM_PLUGIN_PATH=/usr/lib/x86_64-linux-gnu/gz-sim-8/plugins
export GZ_SIM_RESOURCE_PATH=/workspace/disaster_drone_ws/src/drone_bringup/models:/workspace/disaster_drone_ws/src/drone_bringup/worlds:/opt/PX4-Autopilot/Tools/simulation/gz/models

WORLD=/workspace/disaster_drone_ws/src/drone_bringup/worlds/three_floor_building.sdf

case "${1:-start}" in
  stop)
    pkill -9 -f "gz sim -s -v 4 -r ${WORLD}"
    pkill -9 -x px4
    exit 0
    ;;
  start)
    pkill -9 -f "gz sim -s -v 4 -r ${WORLD}" 2>/dev/null
    sleep 1
    if ! pgrep -f "^Xvfb " >/dev/null; then
      Xvfb :0 -screen 0 1024x768x24 >/tmp/xvfb.log 2>&1 &
      sleep 1
    fi
    nohup gz sim -s -v 4 -r "$WORLD" >"$LOG" 2>&1 &
    echo "gz server pid $!"
    ;;
esac