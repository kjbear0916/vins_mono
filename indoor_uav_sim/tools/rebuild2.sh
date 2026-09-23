#!/bin/bash
set +u
source /opt/ros/jazzy/setup.bash
cd /workspace/disaster_drone_ws

# Rebuild drone_msgs and all packages that depend on it
colcon build --packages-up-to drone_msgs --cmake-args -DCMAKE_BUILD_TYPE=Release 2>&1 | tail -8
colcon build --packages-above drone_msgs --cmake-args -DCMAKE_BUILD_TYPE=Release 2>&1 | tail -15

# sanity: python import + publish FusedPose
source install/setup.bash
python3 - <<'PY'
import rclpy
from rclpy.node import Node
from drone_msgs.msg import FusedPose, AnchorDeployment
from geometry_msgs.msg import PoseWithCovariance
from std_msgs.msg import Header
rclpy.init()
n = Node("t")
pub = n.create_publisher(FusedPose, "/test_fused", 10)
m = FusedPose()
m.header = Header(frame_id="world")
m.pose = PoseWithCovariance()
m.pose.pose.position.x = 1.0
pub.publish(m)
print("FusedPose publish OK; AnchorDeployment OK")
rclpy.shutdown()
PY

# kill old stack
pkill -f full_system.launch 2>/dev/null
pkill -f "install/.*/node" 2>/dev/null
pkill -f "rclpy" 2>/dev/null
pkill -f yoake2 2>/dev/null
pkill -f "ros2 launch" 2>/dev/null
sleep 2

# relaunch
ros2 launch drone_bringup full_system.launch.py > /tmp/full_system3.log 2>&1 &
echo "launch pid $!"
sleep 18
echo "== errors =="
grep -aE '\[ERROR\]|Traceback|process has died|ImportError|AssertionError|SIGABRT' /tmp/full_system3.log | head -20
echo "== nodes =="
ros2 node list 2>/dev/null
echo "== bridge topics =="
ros2 topic list 2>/dev/null | grep -E 'camera|lidar|gps'