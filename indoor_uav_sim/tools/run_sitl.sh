#!/bin/bash
set -u
pkill -9 -f "gz sim" 2>/dev/null
pkill -9 -x px4 2>/dev/null
pkill -9 -f "[m]ake px4_sitl" 2>/dev/null
pkill -9 cmake 2>/dev/null
pkill -9 ninja 2>/dev/null
sleep 2

export DISPLAY=:0
export LIBGL_ALWAYS_SOFTWARE=1
export MESA_GL_VERSION_OVERRIDE=4.0
export GZ_SIM_SYSTEM_PLUGIN_PATH=/usr/lib/x86_64-linux-gnu/gz-sim-8/plugins
export GZ_SIM_RESOURCE_PATH=/workspace/disaster_drone_ws/src/drone_bringup/models:/workspace/disaster_drone_ws/src/drone_bringup/worlds:/opt/PX4-Autopilot/Tools/simulation/gz/models

cd /opt/PX4-Autopilot || exit 1
HEADLESS=1 PX4_GZ_WORLD=three_floor_building make px4_sitl gz_x500 >/tmp/px4_sitl.log 2>&1 &
echo "make pid $!"
sleep 55
echo "===== tail of px4 log ====="
tail -c 1800 /tmp/px4_sitl.log
echo
echo "===== running procs ====="
ps aux | grep -E 'px4$|gz sim|make px4' | grep -v grep | head -5
echo "===== gz topics ====="
export DISPLAY=:0
export GZ_SIM_SYSTEM_PLUGIN_PATH=/usr/lib/x86_64-linux-gnu/gz-sim-8/plugins
export GZ_SIM_RESOURCE_PATH=/workspace/disaster_drone_ws/src/drone_bringup/models:/workspace/disaster_drone_ws/src/drone_bringup/worlds:/opt/PX4-Autopilot/Tools/simulation/gz/models
gz topic -l > /tmp/gz_topics.txt 2>&1
wc -l /tmp/gz_topics.txt
grep -aE 'x500|model/|sensor_|world' /tmp/gz_topics.txt | head -20