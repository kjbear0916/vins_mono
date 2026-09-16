#!/usr/bin/env python3
"""UWB Ranging Simulation node.

Reads Gazebo ground truth distance between the drone and each deployed
UWB anchor, adds Gaussian noise, and publishes UwbRange messages.
"""
import math

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped

from drone_msgs.msg import UwbAnchor, UwbRange, FusedPose


class UwbRangingSimNode(Node):
    def __init__(self):
        super().__init__("uwb_ranging_sim")

        self.declare_parameter("effective_range", 15.0)
        self.declare_parameter("noise_std", 0.2)

        self.eff_range = self.get_parameter("effective_range").value
        self.noise_std = self.get_parameter("noise_std").value

        self.anchors: list[dict] = []
        self.drone_pose = None

        self.anchor_sub = self.create_subscription(
            UwbAnchor, "/drone/uwb/anchors", self.anchor_callback, 10
        )
        self.fused_sub = self.create_subscription(
            FusedPose, "/drone/pose/fused", self.pose_callback, 10
        )

        self.range_pub = self.create_publisher(
            UwbRange, "/drone/uwb/ranges", 10
        )

        self.timer = self.create_timer(0.2, self.simulate_ranges)

        self.get_logger().info("UWB ranging simulator started")

    def anchor_callback(self, msg: UwbAnchor):
        existing = next(
            (a for a in self.anchors if a["id"] == msg.anchor_id), None
        )
        anchor_data = {
            "id": msg.anchor_id,
            "x": msg.x,
            "y": msg.y,
            "z": msg.z,
        }
        if existing:
            existing.update(anchor_data)
        else:
            self.anchors.append(anchor_data)
            self.get_logger().info(
                f"Tracking anchor #{msg.anchor_id} at "
                f"({msg.x:.2f}, {msg.y:.2f}, {msg.z:.2f})"
            )

    def pose_callback(self, msg: FusedPose):
        self.drone_pose = msg.pose.pose

    def simulate_ranges(self):
        if self.drone_pose is None or not self.anchors:
            return

        dx = self.drone_pose.position.x
        dy = self.drone_pose.position.y
        dz = self.drone_pose.position.z

        import numpy as np

        for anchor in self.anchors:
            dist = math.sqrt(
                (dx - anchor["x"]) ** 2
                + (dy - anchor["y"]) ** 2
                + (dz - anchor["z"]) ** 2
            )

            if dist > self.eff_range:
                continue

            noisy_dist = dist + np.random.normal(0, self.noise_std)
            noisy_dist = max(0.0, noisy_dist)

            variance = self.noise_std**2

            msg = UwbRange()
            msg.anchor_id = int(anchor["id"])
            msg.distance = round(noisy_dist, 4)
            msg.variance = round(variance, 6)
            self.range_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = UwbRangingSimNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
