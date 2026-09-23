#!/bin/bash
set +u
source /opt/ros/jazzy/setup.bash
source /workspace/disaster_drone_ws/install/setup.bash
python3 -X faulthandler - <<'PY' 2>&1 | tail -25
import faulthandler; faulthandler.enable()
import rclpy
from geometry_msgs.msg import Pose, PoseStamped, Quaternion, Point
from std_msgs.msg import Header
rclpy.init()
from rclpy.node import Node
n = Node("t")
pub = n.create_publisher(Pose, "/pose0", 10)
m = Pose()
pub.publish(m)
print("plain Pose publish OK")

pub2 = n.create_publisher(PoseStamped, "/pose1", 10)
m2 = PoseStamped(); m2.header = Header(); m2.header.frame_id="w"; m2.pose = m
pub2.publish(m2)
print("PoseStamped publish OK")
rclpy.shutdown()
print("ALL OK")
PY