#!/bin/bash
set +u
source /opt/ros/jazzy/setup.bash
source /workspace/disaster_drone_ws/install/setup.bash

echo "== overlay chain =="
echo "$AMENT_PREFIX_PATH" | tr ':' '\n'

echo "== geometry_msgs in workspace install =="
ls /workspace/disaster_drone_ws/install/geometry_msgs/lib/python3.12/site-packages/geometry_msgs/msg/_pose_s.cpython-312-x86_64-linux-gnu.so 2>/dev/null || echo "(not in install)"

echo "== geometry_msgs from apt =="
python3 -c "import geometry_msgs.msg; print(geometry_msgs.msg.Pose.__module__); import geometry_msgs._pose_s; print(geometry_msgs._pose_s.__file__)"

echo "== pose_fusion's installed dep chain =="
pip show geometry_msgs 2>/dev/null | head -5
python3 -c "import geometry_msgs; print(geometry_msgs.__path__)"