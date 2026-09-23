#!/usr/bin/env bash
# ROS2 workspace 建置 + launch 啟動器。
# 用法: setup_ws.sh [package launch_file]   預設: drone_bringup launch_phase0.py
set -u

source /opt/ros/jazzy/setup.bash || { echo "FATAL: can't source ROS2"; exit 1; }
cd /root/disaster_drone_ws/src || { echo "FATAL: workspace missing"; exit 1; }

if [ ! -d install ]; then
  colcon build --symlink-install --event-handlers console_cohesion+ \
    || { echo "colcon build failed"; exit 1; }
fi
source /root/disaster_drone_ws/src/install/setup.bash

PKG="${1:-drone_bringup}"
LAUNCH="${2:-launch_phase0.py}"
shift 2 2>/dev/null || true

exec ros2 launch "$PKG" "$LAUNCH" "$@"