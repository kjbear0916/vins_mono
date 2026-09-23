#!/bin/bash
set +u
kill -9 18806 2>/dev/null
source /opt/ros/jazzy/setup.bash
source /workspace/disaster_drone_ws/install/setup.bash
echo "== now only one detector? =="
ps aux | grep marker_detector | grep -v grep | awk '{print $2}'
ros2 run rqt_image_view --help >/dev/null 2>&1 || echo "no rqt"
echo "== capture fresh nadir image via subscriber =="
python3 - <<'PY'
import rclpy, cv2, numpy as np
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge

rclpy.init()
node = Node("frame_grabber")
br = CvBridge()
got = {"n": 0, "img": None}
def cb(msg):
    got["n"] += 1
    img = br.imgmsg_to_cv2(msg, desired_encoding="bgr8")
    got["img"] = img
    print("grabbed frame", img.shape, flush=True)
sub = node.create_subscription(Image, "/drone/camera/nadir/image_raw", cb, 1)
t0 = node.get_clock().now().nanoseconds
while got["img"] is None and (node.get_clock().now().nanoseconds - t0) < 10e9:
    rclpy.spin_once(node, timeout_sec=0.5)
if got["img"] is not None:
    cv2.imwrite("/tmp/nadir_frame.png", got["img"])
    print("saved /tmp/nadir_frame.png, frames seen:", got["n"], flush=True)
else:
    print("NO FRAME received", flush=True)
node.destroy_node()
rclpy.shutdown()
PY