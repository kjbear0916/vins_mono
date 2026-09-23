#!/usr/bin/env python3
"""Fly-inspired looming detector node.

Subscribes to the front-facing RGB camera and publishes an LPLC2-inspired
looming threat estimate on /drone/threat/looming. The obstacle avoider merges
this vision-derived threat into its reactive avoidance output.

Parameters:
    threshold:       score needed to count a confirmed frame (matches the
                     avoider's vision_threat_threshold)
    confirm_frames:  consecutive frames above threshold before publishing a
                     non-zero score; single-frame flicker stays muted
"""
import cv2
import numpy as np

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from sensor_msgs.msg import Image
from cv_bridge import CvBridge

from drone_msgs.msg import LoomingThreat

try:
    from .fly_vision import LoomingDetector
except ImportError:
    from fly_vision import LoomingDetector


class LoomingDetectorNode(Node):
    def __init__(self):
        super().__init__("looming_detector")

        self.declare_parameter("camera_topic", "/drone/camera/front/image_raw")
        self.declare_parameter("publish_topic", "/drone/threat/looming")
        self.declare_parameter("hfov_deg", 80.0)
        self.declare_parameter("grid_nx", 24)
        self.declare_parameter("grid_ny", 18)
        self.declare_parameter("leak", 0.6)
        self.declare_parameter("threshold", 0.35)
        self.declare_parameter("confirm_frames", 3)

        cam_topic = self.get_parameter("camera_topic").value
        pub_topic = self.get_parameter("publish_topic").value
        hfov = self.get_parameter("hfov_deg").value * np.pi / 180.0

        self.bridge = CvBridge()
        self.detector = LoomingDetector(
            nx=self.get_parameter("grid_nx").value,
            ny=self.get_parameter("grid_ny").value,
            leak=self.get_parameter("leak").value,
        )
        self.detector.configure_geometry(640, 480, hfov)

        self._threshold = float(self.get_parameter("threshold").value)
        self._confirm_frames = max(1, int(self.get_parameter("confirm_frames").value))
        self._confirm = 0
        self._az_sm = 0.0
        self._el_sm = 0.0

        qos = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
        )
        self.image_sub = self.create_subscription(
            Image, cam_topic, self.image_callback, qos
        )
        self.threat_pub = self.create_publisher(LoomingThreat, pub_topic, 10)

        self.get_logger().info(
            f"Fly looming detector started (thr={self._threshold} "
            f"confirm={self._confirm_frames})"
        )

    def image_callback(self, msg: Image):
        try:
            cv_img = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        except Exception as e:
            self.get_logger().warn(f"CV bridge error: {e}")
            return

        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
        result = self.detector.process(gray)

        score = float(result["score"])
        az_raw = float(result["azimuth"])
        el_raw = float(result["elevation"])
        w = 0.15 + 0.55 * min(1.0, score / max(self._threshold, 1e-6))
        self._az_sm += w * (az_raw - self._az_sm)
        self._el_sm += w * (el_raw - self._el_sm)

        if score >= self._threshold:
            self._confirm += 1
        elif score < self._threshold * 0.5:
            self._confirm = 0
        confirmed = self._confirm >= self._confirm_frames

        threat = LoomingThreat()
        threat.score = float(score) if confirmed else 0.0
        threat.azimuth = self._az_sm
        threat.elevation = self._el_sm
        threat.expansion = float(result["expansion"]) if confirmed else 0.0
        self.threat_pub.publish(threat)


def main(args=None):
    rclpy.init(args=args)
    node = LoomingDetectorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()