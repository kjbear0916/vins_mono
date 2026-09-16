#!/bin/bash
# Container entrypoint: bring ROS2 + PX4 gz tooling + workspace into PATH.
set -e

if command -v rclpy >/dev/null 2>&1; then
  :
else
  . /opt/ros/jazzy/setup.sh
fi

# PX4 gz trunk (sets gz version overrides, PX4_GZ_MODEL defaults, etc.)
if [ -f /opt/PX4-Autopilot/Tools/simulation/gz/tools/setup_gz.bash ]; then
  . /opt/PX4-Autopilot/Tools/simulation/gz/tools/setup_gz.bash >/dev/null 2>&1 || true
fi

# Workspace overlays (may not exist until colcon build ran)
for ws in /workspace/disaster_drone_ws/install/setup.bash \
          /root/disaster_drone_ws/install/setup.bash; do
  if [ -f "$ws" ]; then
    . "$ws" >/dev/null 2>&1 || true
  fi
done

export GZ_SIM_RESOURCE_PATH="/opt/PX4-Autopilot/Tools/simulation/gz/models"

exec "$@"