#!/bin/bash
set +u
source /opt/ros/jazzy/setup.bash
source /workspace/disaster_drone_ws/install/setup.bash
ros2 launch drone_bringup full_system.launch.py > /tmp/full_system5.log 2>&1 &
echo "launch pid $!"
sleep 15
echo "== errors =="
grep -aE '\[ERROR\]|Traceback|process has died|ImportError|AssertionError' /tmp/full_system5.log | grep -avE 'readFromYaml|BridgeConfig' | head -10
echo "== nodes =="
ros2 node list 2>/dev/null
echo "== hz fused pose =="
timeout 5 ros2 topic hz /drone/pose/fused 2>&1 | head -3
echo "== pose echo =="
timeout 4 ros2 topic echo /drone/pose/fused --once 2>&1 | head -20
echo "== send takeoff =="
ros2 topic pub -1 /mission/command std_msgs/msg/String "{data: takeoff}" 2>&1 | tail -2