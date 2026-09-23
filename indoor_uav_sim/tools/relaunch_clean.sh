#!/bin/bash
set +u
source /opt/ros/jazzy/setup.bash
source /workspace/disaster_drone_ws/install/setup.bash
for p in $(ros2 node list 2>/dev/null | sed 's|^/||' | sort -u); do
  pkill -9 -f "$p" 2>/dev/null
done
pkill -9 -f full_system.launch 2>/dev/null
pkill -9 -f "ros2 launch" 2>/dev/null
sleep 3
echo "== nodes after kill: $(ros2 node list 2>/dev/null | wc -l)"
ros2 launch drone_bringup full_system.launch.py > /tmp/full_system6.log 2>&1 &
echo "launch pid $!"
sleep 15
echo "== distinct nodes =="
ros2 node list 2>/dev/null | sort -u
echo "== drone_control log =="
grep -a 'drone_control' /tmp/full_system6.log | tail -5