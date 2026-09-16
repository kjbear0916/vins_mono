#!/bin/bash
# Phase 0 startup script: PX4 SITL + Gazebo
# Run this in one terminal, then full_system.launch.py in another.

set -e

echo "=== Phase 0: Starting PX4 SITL with Gazebo Harmonic ==="

source /opt/ros/jazzy/setup.bash
source /opt/PX4-Autopilot/Tools/simulation/gz/setup-gz.bash

export GZ_SIM_RESOURCE_PATH=/opt/PX4-Autopilot/Tools/simulation/gz/models:${GZ_SIM_RESOURCE_PATH:-}

cd /opt/PX4-Autopilot

echo "Launching PX4 SITL with x500 model..."
make px4_sitl gz_x500 --world=/root/disaster_drone_ws/src/drone_bringup/worlds/indoor_building.sdf
