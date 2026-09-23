#!/bin/bash
set +u
source /opt/ros/jazzy/setup.bash
source /workspace/disaster_drone_ws/install/setup.bash
pkill -9 -f mavsdk_server
for p in market_detector anchor_manager uwb_ranging_sim uwb_trilateration pose_fusion obstacle_avoider survivor_detector waypoint_navigator mission_planner drone_control gz_bridge; do
  pkill -9 -f "run.py.*$p" 2>/dev/null; pkill -9 -f "$p" 2>/dev/null
done
pkill -9 -f "ros2 launch" 2>/dev/null
sleep 3
ros2 launch drone_bringup full_system.launch.py > /tmp/full_system7.log 2>&1 &
echo "launch pid $!"
sleep 20
echo "== distinct nodes =="
ros2 node list 2>/dev/null | sort -u
echo "== drone_control log =="
grep -a 'drone_control' /tmp/full_system7.log | tail -12