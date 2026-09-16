#!/usr/bin/env python3
"""ArUco marker detection + drone world-pose estimation.

Sensor model: nadir (downward-facing) camera over *floor-mounted* markers.
Dictionary DICT_7X7_1000 matches tools/generate_marker_models.py and
supports the full id scheme including survivor ids 900..999.

For every detected marker whose id exists in marker_map.yaml:
  solvePnP -> pose of the marker in the camera optical frame
  invert   -> camera pose in the marker frame, then compose with the
              marker's known world pose -> drone world pose estimate
  publish  /drone/marker/pose  (drone_msgs/MarkerPose)

Semantics of MarkerPose (documented in README): marker_id is the marker
that produced the fix; x/y/z/yaw are the *drone's* world pose estimate.

Assumptions (documented, tune in README):
  * camera optical centre == drone position (mount offset ignored)
  * floor markers are level (roll/pitch = 0); yaw of the drone fix is a
    by-product of marker yaw and is only order-of-magnitude accurate.
"""
import cv2
import numpy as np
import yaml
from pathlib import Path

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from sensor_msgs.msg import Image
from cv_bridge import CvBridge

from drone_msgs.msg import MarkerPose


ARUCO_PARAMS = cv2.aruco.DetectorParameters()
DICT_7X7_1000 = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_7X7_1000)


def load_marker_map(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return {int(k): v for k, v in data["markers"].items()}


class MarkerDetectorNode(Node):
    def __init__(self):
        super().__init__("marker_detector")

        self.declare_parameter("camera_topic", "/drone/camera/nadir/image_raw")
        self.declare_parameter("marker_map_file", "")
        self.declare_parameter("marker_size_m", 0.5)
        self.declare_parameter("camera_frame_id", "camera_link")
        self.declare_parameter("min_confidence", 0.3)

        cam_topic = self.get_parameter("camera_topic").value
        map_file = self.get_parameter("marker_map_file").value
        self.marker_size = self.get_parameter("marker_size_m").value
        self.frame_id = self.get_parameter("camera_frame_id").value
        self.min_conf = self.get_parameter("min_confidence").value

        if not map_file:
            pkg_dir = Path(__file__).resolve().parent.parent.parent
            map_file = str(pkg_dir / "drone_bringup" / "config" / "marker_map.yaml")

        self.marker_map = load_marker_map(map_file)
        self.get_logger().info(f"Loaded {len(self.marker_map)} markers from {map_file}")

        self.camera_matrix = None
        self.dist_coeffs = None

        self.bridge = CvBridge()
        self.detector = cv2.aruco.ArucoDetector(DICT_7X7_1000, ARUCO_PARAMS)

        self.pose_pub = self.create_publisher(MarkerPose, "/drone/marker/pose", 10)

        qos = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
        )
        self.image_sub = self.create_subscription(Image, cam_topic, self.image_callback, qos)

        self.get_logger().info("Marker detector (DICT_7X7_1000) started")

    def ensure_camera_matrix(self, width: int, height: int):
        if self.camera_matrix is not None:
            return
        focal = max(width, height)
        self.camera_matrix = np.array(
            [[focal, 0, width / 2.0],
             [0, focal, height / 2.0],
             [0, 0, 1]], dtype=np.float64
        )
        self.dist_coeffs = np.zeros((5, 1), dtype=np.float64)
        self.get_logger().info(
            f"Synthetic intrinsics: fx=fy={focal:.1f}, c=({width / 2:.1f}, {height / 2:.1f})"
        )

    def _object_points(self) -> np.ndarray:
        h = self.marker_size / 2.0
        return np.array([
            [-h,  h, 0], [h,  h, 0], [h, -h, 0], [-h, -h, 0],
        ], dtype=np.float64)

    def image_callback(self, msg: Image):
        try:
            cv_img = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        except Exception as e:
            self.get_logger().warn(f"CV bridge error: {e}")
            return

        h, w = cv_img.shape[:2]
        self.ensure_camera_matrix(w, h)

        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
        corners, ids, _ = self.detector.detectMarkers(gray)

        if ids is None or len(ids) == 0:
            return

        for i, marker_id in enumerate(ids.flatten()):
            if marker_id not in self.marker_map:
                continue

            img_pts = corners[i].reshape(4, 2).astype(np.float64)
            success, rvec, tvec = cv2.solvePnP(
                self._object_points(), img_pts,
                self.camera_matrix, self.dist_coeffs,
                flags=cv2.SOLVEPNP_IPPE_SQUARE,
            )
            if not success:
                continue

            conf = self._estimate_confidence(corners[i], w, h)
            if conf < self.min_conf:
                continue

            drone_pose = self._drone_pose_from_marker(marker_id, rvec, tvec)
            if drone_pose is None:
                continue

            mp = MarkerPose()
            mp.marker_id = int(marker_id)
            mp.x, mp.y, mp.z, mp.yaw, mp.confidence = drone_pose
            mp.source_frame = self.frame_id
            self.pose_pub.publish(mp)

    def _drone_pose_from_marker(self, marker_id: int, rvec, tvec):
        """Camera(=drone) world pose given the marker's world pose.

        rvec/tvec: pose of the marker in the camera optical frame.
        """
        import transforms3d as t3d

        world = self.marker_map[marker_id]
        R_cm = cv2.Rodrigues(rvec)[0]     # marker -> camera rotation
        t_cm = tvec.ravel().astype(float)  # marker origin in camera frame

        # camera pose in the marker frame
        R_mc = R_cm.T                      # camera -> marker rotation
        t_mc = -R_cm.T @ t_cm              # camera origin in marker frame

        # marker world orientation (level, yaw from the map)
        R_wm = t3d.euler.euler2mat(0.0, 0.0, float(world.get("yaw", 0.0)))
        p_wm = np.array([world["x"], world["y"], world["z"]], dtype=float)

        R_wc = R_wm @ R_mc
        p_wc = R_wm @ t_mc + p_wm
        yaw = t3d.euler.mat2euler(R_wc, "sxyz")[2]
        return (float(p_wc[0]), float(p_wc[1]), float(p_wc[2]), float(yaw))

    def _estimate_confidence(self, corners, img_w: int, img_h: int) -> float:
        pts = corners.reshape(4, 2)
        area = cv2.contourArea(pts)
        max_area = img_w * img_h * 0.25
        area_score = min(area / (max_area * 0.01), 1.0)

        center = np.mean(pts, axis=0)
        dist = np.linalg.norm(center - np.array([img_w / 2.0, img_h / 2.0]))
        center_score = 1.0 - dist / (np.sqrt(img_w**2 + img_h**2) / 2.0)

        perimeter = cv2.arcLength(pts, True)
        if perimeter > 0:
            circularity = 4 * np.pi * area / (perimeter * perimeter)
            shape_score = min(circularity, 1.0)
        else:
            shape_score = 0.0

        return float(0.4 * area_score + 0.3 * center_score + 0.3 * shape_score)


def main(args=None):
    rclpy.init(args=args)
    node = MarkerDetectorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()