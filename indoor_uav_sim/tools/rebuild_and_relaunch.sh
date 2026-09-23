#!/bin/bash
set +u
source /opt/ros/jazzy/setup.bash

# Rebuild drone_msgs + all dependent packages
cd /workspace/disaster_drone_ws
colcon build --packages-up-to drone_msgs --cmake-args -DCMAKE_BUILD_TYPE=Release 2>&1 | tail -20

# Verify AnchorDeployment exists
python3 -c "from drone_msgs.msg import AnchorDeployment; print('AnchorDeployment OK')" 2>&1

# Kill current ROS nodes
pkill -f full_system.launch.py 2>/dev/null
pkill -f ros2 2>/dev/null
pkill -f rclcpp 2>/dev/null
pkill -f rclpy 2>/dev/null
pkill -f drone_control 2>/dev/null
pkill -f marker_detector 2>/dev/null
pkill -f obstacle_avoider 2>/dev/null
pkill -f survivor_detector 2>/dev/null
pkill -f uwb 2>/dev/null
pkill -f pose_fusion 2>/dev/null
sleep 2

source install/setup.bash

# Relaunch
ros2 launch drone_bringup full_system.launch.py > /tmp/full_system2.log 2>&1 &
echo "launch pid $!"
sleep 15
echo "== errors =="
grep -aE '\[ERROR\]|Traceback|process has died|ImportError|AssertionError|SIGABRT|assert|terminate' /tmp/full_system2.log | head -30
echo "== nodes =="
ros2 node list 2>/dev/null
echo "== topics =="
ros2 topic list 2>/dev/null | head -30