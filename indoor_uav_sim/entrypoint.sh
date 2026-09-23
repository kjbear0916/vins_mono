#!/bin/bash
# Container entrypoint: bring ROS2 + PX4 gz tooling + workspace into PATH.
set -e

if command -v rclpy >/dev/null 2>&1; then
  :
else
  . /opt/ros/jazzy/setup.sh
fi

# ros_gz_bridge/ros_gz_sim ship as a deb (not in the desktop image). Install
# idempotently at start; skip apt entirely once present (obs #0025: never
# chain `|| true &&`, gate the failure explicitly).
if [ ! -d /opt/ros/jazzy/share/ros_gz_bridge ] && command -v apt-get >/dev/null 2>&1; then
  apt-get update >/dev/null 2>&1 || true
  DEBIAN_FRONTEND=noninteractive apt-get install -y -q ros-jazzy-ros-gz >/dev/null 2>&1 || \
    echo "warning: apt-install of ros-jazzy-ros-gz failed" >&2
fi

if [ -d /opt/ros/jazzy/share/ros_gz_bridge ]; then
  :
else
  echo "warning: ros_gz_bridge not present; full_system.launch.py will fail" >&2
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

export GZ_SIM_RESOURCE_PATH="/workspace/disaster_drone_ws/src/drone_bringup/models:/workspace/disaster_drone_ws/src/drone_bringup/worlds:${GZ_SIM_RESOURCE_PATH:-/opt/PX4-Autopilot/Tools/simulation/gz/models}"

exec "$@"