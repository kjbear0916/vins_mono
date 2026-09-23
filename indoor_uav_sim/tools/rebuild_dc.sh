#!/bin/bash
set +u
echo "== is drone_control install symlinked? =="
ls -la /workspace/disaster_drone_ws/install/drone_control/lib/drone_control/drone_control_node.py 2>/dev/null | head -2
cd /workspace/disaster_drone_ws
source /opt/ros/jazzy/setup.bash
colcon build --packages-select drone_control drone_bringup --symlink-install 2>&1 | tail -6