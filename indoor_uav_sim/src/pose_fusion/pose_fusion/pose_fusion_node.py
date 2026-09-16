#!/usr/bin/env python3
"""pose_fusion: confidence-based source switching between ArUco and UWB.

/drone/marker/pose (drone_msgs/MarkerPose) now carries the *drone* world
pose estimated from a marker fix (see marker_detector). /drone/uwb/pose
(geometry_msgs/PoseWithCovariance) carries the trilaterated fix.

Rule (SPEC.md section 8.4):
  SOURCE_ARUCO (default) -> after `aruco_lost_frames` consecutive frames
  without a usable marker fix, fall back to SOURCE_UWB_FALLBACK if a UWB
  fix exists. When markers reappear for `aruco_recover_frames` frames,
  switch back to SOURCE_ARUCO.

Downstream consumers only see /drone/pose/fused and never care which
underlying source produced it.
"""
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseWithCovariance
from std_msgs.msg import Header

from drone_msgs.msg import MarkerPose, FusedPose


SOURCE_ARUCO = "aruco"
SOURCE_UWB = "uwb_fallback"


class PoseFusionNode(Node):
    def __init__(self):
        super().__init__("pose_fusion")

        self.declare_parameter("aruco_lost_frames", 5)
        self.declare_parameter("aruco_recover_frames", 3)
        self.declare_parameter("aruco_confidence_min", 0.3)
        self.declare_parameter("uwb_confidence", 0.5)

        self.lost_thresh = int(self.get_parameter("aruco_lost_frames").value)
        self.recover_thresh = int(self.get_parameter("aruco_recover_frames").value)
        self.conf_min = float(self.get_parameter("aruco_confidence_min").value)
        self.uwb_conf = float(self.get_parameter("uwb_confidence").value)

        self.source = SOURCE_ARUCO
        self._frames_no_aruco = 0
        self._frames_recover = 0
        self._aruco = None          # latest usable marker fix (drone pose)
        self._uwb = None            # latest UWB fix
        self._publish_rate = 10.0   # Hz

        self.aruco_sub = self.create_subscription(
            MarkerPose, "/drone/marker/pose", self._on_aruco, 10)
        self.uwb_sub = self.create_subscription(
            PoseWithCovariance, "/drone/uwb/pose", self._on_uwb, 10)

        self.fused_pub = self.create_publisher(FusedPose, "/drone/pose/fused", 10)
        self._timer = self.create_timer(1.0 / self._publish_rate, self._publish)

        self.get_logger().info(
            f"pose_fusion ready (lost={self.lost_thresh}, "
            f"recover={self.recover_thresh}, min_conf={self.conf_min})")

    def _on_aruco(self, msg: MarkerPose):
        if msg.confidence < self.conf_min:
            return
        self._aruco = msg
        self._frames_no_aruco = 0
        if self.source == SOURCE_UWB:
            self._frames_recover += 1
            if self._frames_recover >= self.recover_thresh:
                self.source = SOURCE_ARUCO
                self._frames_recover = 0
                self.get_logger().info("ArUco re-acquired -> SOURCE_ARUCO")

    def _on_uwb(self, msg: PoseWithCovariance):
        self._uwb = msg

    def _publish(self):
        self._frames_no_aruco += 1
        if (self.source == SOURCE_ARUCO
                and self._frames_no_aruco >= self.lost_thresh):
            if self._uwb is not None:
                self.source = SOURCE_UWB
                self._frames_no_aruco = 0
                self._frames_recover = 0
                self.get_logger().warn(
                    f"ArUco lost {self._frames_no_aruco} frames -> "
                    "SOURCE_UWB_FALLBACK")
            elif self._aruco is not None:
                # no UWB fix available yet: hold the last ArUco fix
                self._frames_no_aruco = 1

        fused = FusedPose()
        fused.header = Header()
        fused.header.stamp = self.get_clock().now().to_msg()
        fused.header.frame_id = "world"

        if self.source == SOURCE_ARUCO and self._aruco is not None:
            fused.pose = PoseWithCovariance()
            fused.pose.pose.position.x = self._aruco.x
            fused.pose.pose.position.y = self._aruco.y
            fused.pose.pose.position.z = self._aruco.z
            fused.pose.pose.orientation.w = 1.0
            fused.source = SOURCE_ARUCO
            fused.confidence = self._aruco.confidence
        elif self._uwb is not None:
            fused.pose = self._uwb
            fused.source = SOURCE_UWB
            fused.confidence = self.uwb_conf
        else:
            fused.pose = PoseWithCovariance()
            fused.source = "none"
            fused.confidence = 0.0

        self.fused_pub.publish(fused)


def main(args=None):
    rclpy.init(args=args)
    node = PoseFusionNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()