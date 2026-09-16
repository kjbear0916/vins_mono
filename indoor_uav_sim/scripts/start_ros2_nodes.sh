#!/bin/bash
# Phase 7 startup script: Full ROS2 node system
# Run after PX4 SITL + Gazebo is running.

set -e

echo "=== Phase 7: Starting Full ROS2 Disaster Drone System ==="

source /opt/ros/jazzy/setup.bash
source /root/disaster_drone_ws/install/setup.bash
source /opt/PX4-Autopilot/Tools/simulation/gz/setup-gz.bash

export ROS_DOMAIN_ID=0

echo "Waiting 10s for PX4 to be ready..."
sleep 10

echo "Launching full system..."
ros2 launch drone_bringup full_system.launch.py
