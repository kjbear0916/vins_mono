#!/usr/bin/env python3
"""UWB Trilateration node.

Subscribes to UwbRange messages and anchor positions.
When >= 3 anchors are in range, performs trilateration using
least-squares optimization to estimate drone position.
"""
import math
import numpy as np
from scipy.optimize import least_squares

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseWithCovariance

from drone_msgs.msg import UwbAnchor, UwbRange


class UwbTrilaterationNode(Node):
    def __init__(self):
        super().__init__("uwb_trilateration")

        self.declare_parameter("min_anchors", 4)
        self.declare_parameter("max_iterations", 100)
        self.declare_parameter("residual_threshold", 0.5)

        self.min_anchors = self.get_parameter("min_anchors").value
        self.max_iter = self.get_parameter("max_iterations").value
        self.res_thresh = self.get_parameter("residual_threshold").value

        self.anchors: dict[int, dict] = {}
        self.ranges: dict[int, float] = {}
        self.variances: dict[int, float] = {}

        self.anchor_sub = self.create_subscription(
            UwbAnchor, "/drone/uwb/anchors", self.anchor_callback, 10
        )
        self.range_sub = self.create_subscription(
            UwbRange, "/drone/uwb/ranges", self.range_callback, 10
        )

        self.pose_pub = self.create_publisher(
            PoseWithCovariance, "/drone/uwb/pose", 10
        )

        self.get_logger().info("UWB trilateration node started")

    def anchor_callback(self, msg: UwbAnchor):
        self.anchors[msg.anchor_id] = {
            "x": msg.x,
            "y": msg.y,
            "z": msg.z,
        }

    def range_callback(self, msg: UwbRange):
        self.ranges[msg.anchor_id] = msg.distance
        self.variances[msg.anchor_id] = msg.variance
        self._try_trilaterate()

    def _try_trilaterate(self):
        available = [
            aid for aid in self.ranges if aid in self.anchors
        ]

        if len(available) < self.min_anchors:
            return

        anchor_positions = np.array([
            [self.anchors[a]["x"], self.anchors[a]["y"], self.anchors[a]["z"]]
            for a in available
        ])
        distances = np.array([self.ranges[a] for a in available])
        weights = np.array([
            1.0 / max(self.variances.get(a, 0.04), 0.001) for a in available
        ])

        result = self._trilaterate_least_squares(
            anchor_positions, distances, weights
        )

        if result is not None:
            pose = PoseWithCovariance()
            pose.pose.position.x = float(result[0])
            pose.pose.position.y = float(result[1])
            pose.pose.position.z = float(result[2])
            pose.pose.orientation.w = 1.0

            pose.covariance = [
                0.1, 0, 0, 0, 0, 0,
                0, 0.1, 0, 0, 0, 0,
                0, 0, 0.1, 0, 0, 0,
                0, 0, 0, 0, 0, 0,
                0, 0, 0, 0, 0, 0,
                0, 0, 0, 0, 0, 0,
            ]

            self.pose_pub.publish(pose)

    def _trilaterate_least_squares(
        self,
        anchors: np.ndarray,
        distances: np.ndarray,
        weights: np.ndarray,
    ) -> np.ndarray | None:
        def residuals(pos):
            dists = np.linalg.norm(anchors - pos, axis=1)
            return weights * (dists - distances)

        x0 = np.mean(anchors, axis=0)

        try:
            result = least_squares(
                residuals,
                x0,
                method="lm",
                max_nfev=self.max_iter,
            )

            if result.cost < self.res_thresh * len(distances):
                self.get_logger().debug(
                    f"Trilateration converged: cost={result.cost:.4f}, "
                    f"pos=({result.x[0]:.2f}, {result.x[1]:.2f}, "
                    f"{result.x[2]:.2f})"
                )
                return result.x
            else:
                self.get_logger().warn(
                    f"Trilateration residual too high: {result.cost:.4f}"
                )
                return None
        except Exception as e:
            self.get_logger().error(f"Trilateration failed: {e}")
            return None


def main(args=None):
    rclpy.init(args=args)
    node = UwbTrilaterationNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
