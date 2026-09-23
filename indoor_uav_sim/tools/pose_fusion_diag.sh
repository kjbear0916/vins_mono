#!/bin/bash
set +u
source /opt/ros/jazzy/setup.bash
source /workspace/disaster_drone_ws/install/setup.bash
python3 /workspace/disaster_drone_ws/install/pose_fusion/lib/pose_fusion/pose_fusion_node.py --ros-args -r __node:=pose_fusion 2>&1 | head -40
echo "exit: $?"