#!/bin/bash
set +u
source /opt/ros/jazzy/setup.bash
cd /workspace/disaster_drone_ws
colcon build --packages-up-to drone_msgs --cmake-args -DCMAKE_BUILD_TYPE=Release 2>&1 | tail -3
colcon build --packages-above drone_msgs --cmake-args -DCMAKE_BUILD_TYPE=Release 2>&1 | tail -5
source install/setup.bash

pkill -f full_system.launch 2>/dev/null; sleep 2
ros2 launch drone_bringup full_system.launch.py > /tmp/full_system4.log 2>&1 &
echo "launch pid $!"
sleep 18
echo "== errors =="
grep -aE '\[ERROR\]|Traceback|process has died|ImportError|AssertionError' /tmp/full_system4.log | grep -av readFrom | head -20
echo "== nodes =="
ros2 node list 2>/dev/null | sort -u
echo "== all topics =="
ros2 topic list 2>/dev/null