#!/bin/bash
set +u
source /opt/ros/jazzy/setup.bash
source /workspace/disaster_drone_ws/install/setup.bash
echo "== sending takeoff =="
ros2 topic pub -1 /mission/command std_msgs/msg/String "{data: takeoff}" 2>&1 | tail -2
sleep 25
echo "== fused pose now =="
timeout 3 ros2 topic echo /drone/pose/fused --once 2>&1 | grep -A6 'position:'
echo "== marker pose =="
timeout 3 ros2 topic echo /drone/marker/pose --once 2>&1 | head -12
echo "== drone_control log =="
grep -aE 'takeoff|armed|manual|state|failed|error|ERROR' /tmp/full_system4.log | tail -10