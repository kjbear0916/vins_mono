#!/usr/bin/env python3
"""LiDAR/depth-camera obstacle avoidance node.

Subscribes to /drone/lidar/scan and /drone/pose/fused.
When obstacles are detected within safety distance, modifies
cmd_vel to steer away from obstacles.
"""
import math

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
from geometry_msgs.msg import Twist

from drone_msgs.msg import FusedPose


class ObstacleAvoiderNode(Node):
    def __init__(self):
        super().__init__("obstacle_avoider")

        self.declare_parameter("safety_distance", 1.5)
        self.declare_parameter("slow_distance", 2.5)
        self.declare_parameter("max_avoidance_vel", 0.8)
        self.declare_parameter("avoidance_gain", 1.5)

        self.safety_dist = self.get_parameter("safety_distance").value
        self.slow_dist = self.get_parameter("slow_distance").value
        self.max_vel = self.get_parameter("max_avoidance_vel").value
        self.gain = self.get_parameter("avoidance_gain").value

        self.current_pose = None
        self.cmd_in = Twist()
        self.has_cmd = False

        self.scan_sub = self.create_subscription(
            LaserScan, "/drone/lidar/scan", self.scan_callback, 10
        )
        self.fused_sub = self.create_subscription(
            FusedPose, "/drone/pose/fused", self.pose_callback, 10
        )
        self.cmd_sub = self.create_subscription(
            Twist, "/drone/cmd_vel_raw", self.cmd_callback, 10
        )

        self.cmd_pub = self.create_publisher(Twist, "/drone/cmd_vel", 10)

        self.get_logger().info("Obstacle avoider started")

    def pose_callback(self, msg: FusedPose):
        self.current_pose = msg.pose.pose

    def cmd_callback(self, msg: Twist):
        self.cmd_in = msg
        self.has_cmd = True

    def scan_callback(self, msg: LaserScan):
        ranges = msg.ranges
        n = len(ranges)
        if n == 0:
            return

        angle_min = msg.angle_min
        angle_inc = msg.angle_increment

        min_dist = float("inf")
        min_angle = 0.0
        sectors = {}
        sector_size = max(1, n // 8)

        for i, r in enumerate(ranges):
            if not math.isfinite(r) or r <= 0:
                continue
            angle = angle_min + i * angle_inc
            sector = i // sector_size
            if sector not in sectors or r < sectors[sector][0]:
                sectors[sector] = (r, angle)
            if r < min_dist:
                min_dist = r
                min_angle = angle

        avoidance = Twist()

        if min_dist < self.slow_dist:
            force_x = 0.0
            force_y = 0.0
            for sector, (r, angle) in sectors.items():
                if r < self.slow_dist:
                    strength = self.gain * (1.0 / max(r, 0.1) - 1.0 / self.slow_dist)
                    strength = min(strength, self.max_vel)
                    force_x -= strength * math.cos(angle)
                    force_y -= strength * math.sin(angle)

            speed = math.sqrt(force_x**2 + force_y**2)
            if speed > self.max_vel:
                scale = self.max_vel / speed
                force_x *= scale
                force_y *= scale

            avoidance.linear.x = force_x
            avoidance.linear.y = force_y

            if min_dist < self.safety_dist:
                speed_factor = min_dist / self.safety_dist
                avoidance.linear.x *= speed_factor
                avoidance.linear.y *= speed_factor
                self.get_logger().warn(
                    f"Obstacle very close: {min_dist:.2f}m, "
                    f"reducing speed factor to {speed_factor:.2f}"
                )

        if self.has_cmd:
            final = Twist()
            final.linear.x = self.cmd_in.linear.x + avoidance.linear.x
            final.linear.y = self.cmd_in.linear.y + avoidance.linear.y
            final.linear.z = self.cmd_in.linear.z
            final.angular = self.cmd_in.angular

            self.cmd_pub.publish(final)
        else:
            self.cmd_pub.publish(avoidance)


def main(args=None):
    rclpy.init(args=args)
    node = ObstacleAvoiderNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
