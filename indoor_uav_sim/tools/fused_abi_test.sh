#!/bin/bash
set +u
source /opt/ros/jazzy/setup.bash
source /workspace/disaster_drone_ws/install/setup.bash
python3 -X faulthandler - <<'PY' 2>&1 | tail -40
import faulthandler
faulthandler.enable()
import rclpy
from drone_msgs.msg import FusedPose
from geometry_msgs.msg import PoseWithCovariance
from std_msgs.msg import Header
rclpy.init()
from rclpy.node import Node
n = Node("t")
pub = n.create_publisher(FusedPose, "/t", 10)
m = FusedPose()
m.header = Header()
m.pose = PoseWithCovariance()
m.pose.pose.position.x = 1.0
for i in range(3):
    pub.publish(m)
    print("publish", i, "ok")
rclpy.spin_once(n, timeout_sec=0.1)
rclpy.shutdown()
print("DONE")
PY