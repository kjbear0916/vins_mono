#!/bin/bash
set +u
source /opt/ros/jazzy/setup.bash
python3 - <<'PY'
import geometry_msgs.msg
p = geometry_msgs.msg.Pose()
print("Pose create OK:", p)
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Pose
rclpy.init()
n = Node("t")
pub = n.create_publisher(Pose, "/t", 10)
print("pub create OK")
m = Pose()
print("msg2 OK", m)
rclpy.shutdown()
print("ALL OK")
PY