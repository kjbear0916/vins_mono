#!/bin/bash
set -u
M=/opt/PX4-Autopilot/Tools/simulation/gz/models/x500/model.sdf
echo "== sensors declared in $M =="
grep -nE '<sensor|</sensor>|name="[a-z_]+" type' "$M" | head -40
echo
echo "== sensor blocks =="
awk '/<sensor /{f=1} f{print} /<\/sensor>/{f=0}' "$M" | grep -E '<sensor |name="' | head -40
echo
echo "== topics published in gz now =="
export GZ_SIM_SYSTEM_PLUGIN_PATH=/usr/lib/x86_64-linux-gnu/gz-sim-8/plugins
export GZ_SIM_RESOURCE_PATH=/workspace/disaster_drone_ws/src/drone_bringup/models:/workspace/disaster_drone_ws/src/drone_bringup/worlds:/opt/PX4-Autopilot/Tools/simulation/gz/models
gz topic -l | sort