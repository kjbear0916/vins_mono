#!/bin/bash
set +u
source /opt/ros/jazzy/setup.bash
source /workspace/disaster_drone_ws/install/setup.bash
python3 -X faulthandler - <<'PY' 2>&1 | tail -25
import faulthandler; faulthandler.enable()
import rclpy
from rclpy.node import Node
from drone_msgs.msg import FusedPose
from geometry_msgs.msg import Pose, Point, Quaternion
from std_msgs.msg import Header
rclpy.init()
n = rclpy.node.Node("t")
pub = n.create_publisher(FusedPose, "/test_fused", 10)
m = FusedPose()
m.header = Header()
m.header.frame_id = "world"
m.pose = Pose()          # correct field type
m.pose.position = Point(x=1.0, y=2.0, z=3.0)
m.pose.orientation = Quaternion(w=1.0)
m.source = "none"
m.confidence = 0.5
pub.publish(m)
print("FusedPose publish OK")
rclpy.shutdown()
PY