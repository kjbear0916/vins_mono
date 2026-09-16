#!/usr/bin/env python3
"""Survivor detection node.

Detects survivor markers (ArUco IDs 900-999) from the front-facing RGB camera.
Reports their world coordinates via SurvivorReport messages.
"""
import cv2
import numpy as np
from pathlib import Path
import yaml

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from sensor_msgs.msg import Image
from cv_bridge import CvBridge

from drone_msgs.msg import SurvivorReport, FusedPose


ARUCO_PARAMS = cv2.aruco.DetectorParameters()
DICT_7X7_1000 = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_7X7_1000)
SURVIVOR_ID_MIN = 900
SURVIVOR_ID_MAX = 999


class SurvivorDetectorNode(Node):
    def __init__(self):
        super().__init__("survivor_detector")

        self.declare_parameter("camera_topic", "/drone/camera/front/image_raw")
        self.declare_parameter("marker_map_file", "")
        self.declare_parameter("marker_size_m", 0.5)
        self.declare_parameter("min_confidence", 0.4)
        self.declare_parameter("detection_radius", 3.0)

        cam_topic = self.get_parameter("camera_topic").value
        self.marker_size = self.get_parameter("marker_size_m").value
        self.min_conf = self.get_parameter("min_confidence").value
        self.detect_radius = self.get_parameter("detection_radius").value

        map_file = self.get_parameter("marker_map_file").value
        if not map_file:
            pkg_dir = Path(__file__).resolve().parent.parent.parent
            map_file = str(
                pkg_dir / "drone_bringup" / "config" / "marker_map.yaml"
            )

        self.survivor_map = self._load_survivor_positions(map_file)

        self.bridge = CvBridge()
        self.detector = cv2.aruco.ArucoDetector(DICT_7X7_1000, ARUCO_PARAMS)
        self.camera_matrix = None
        self.dist_coeffs = None

        self.current_pose = None
        self.detections: dict[int, SurvivorReport] = {}

        self.fused_sub = self.create_subscription(
            FusedPose, "/drone/pose/fused", self.pose_callback, 10
        )

        qos = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
        )
        self.image_sub = self.create_subscription(
            Image, cam_topic, self.image_callback, qos
        )

        self.report_pub = self.create_publisher(
            SurvivorReport, "/drone/survivor/report", 10
        )

        self.get_logger().info("Survivor detector started")

    def _load_survivor_positions(self, path: str) -> dict:
        try:
            with open(path, "r") as f:
                data = yaml.safe_load(f)
            return {
                int(k): v
                for k, v in data.get("markers", {}).items()
                if SURVIVOR_ID_MIN <= int(k) <= SURVIVOR_ID_MAX
            }
        except Exception:
            return {}

    def pose_callback(self, msg: FusedPose):
        self.current_pose = msg.pose.pose

    def image_callback(self, msg: Image):
        try:
            cv_img = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        except Exception as e:
            self.get_logger().warn(f"CV bridge error: {e}")
            return

        h, w = cv_img.shape[:2]
        self._ensure_camera_matrix(w, h)

        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
        corners, ids, _ = self.detector.detectMarkers(gray)

        if ids is None:
            return

        for i, marker_id in enumerate(ids.flatten()):
            if marker_id < SURVIVOR_ID_MIN or marker_id > SURVIVOR_ID_MAX:
                continue

            marker_corners = corners[i].reshape(4, 2)
            confidence = self._estimate_confidence(marker_corners, w, h)

            if confidence < self.min_conf:
                continue

            if marker_id in self.survivor_map and self.current_pose:
                world = self.survivor_map[marker_id]
                report = SurvivorReport()
                report.marker_id = int(marker_id)
                report.x = float(world["x"])
                report.y = float(world["y"])
                report.z = float(world["z"])
                report.confidence = float(confidence)
                report.timestamp = str(self.get_clock().now().to_msg())

                if marker_id not in self.detections:
                    self.detections[marker_id] = report
                    self.report_pub.publish(report)
                    self.get_logger().info(
                        f"Survivor #{marker_id} detected at "
                        f"({report.x:.2f}, {report.y:.2f}, {report.z:.2f})"
                    )

    def _ensure_camera_matrix(self, w: int, h: int):
        if self.camera_matrix is not None:
            return
        focal = max(w, h)
        self.camera_matrix = np.array(
            [[focal, 0, w / 2.0], [0, focal, h / 2.0], [0, 0, 1]],
            dtype=np.float64,
        )
        self.dist_coeffs = np.zeros((5, 1), dtype=np.float64)

    def _estimate_confidence(self, corners, img_w, img_h):
        area = cv2.contourArea(corners)
        max_area = img_w * img_h * 0.25
        area_score = min(area / (max_area * 0.01), 1.0)

        center = np.mean(corners, axis=0)
        dist = np.linalg.norm(center - np.array([img_w / 2, img_h / 2]))
        max_dist = np.sqrt(img_w**2 + img_h**2) / 2
        center_score = 1.0 - (dist / max_dist)

        return float(0.5 * area_score + 0.5 * center_score)


def main(args=None):
    rclpy.init(args=args)
    node = SurvivorDetectorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
