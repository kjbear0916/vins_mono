#!/usr/bin/env python3
"""Mission control node.

Coordinates the overall mission: monitoring exploration progress,
tracking survivors, and issuing return-to-home when exploration is complete.
"""
import time
import yaml
from pathlib import Path

import rclpy
from rclpy.node import Node

from std_msgs.msg import String
from drone_msgs.msg import (
    MissionStatus, SurvivorReport, FusedPose, AnchorDeployment
)


class MissionPlannerNode(Node):
    def __init__(self):
        super().__init__("mission_planner")

        self.declare_parameter("mission_file", "")

        pkg_dir = Path(__file__).resolve().parent.parent.parent
        mission_file = self.get_parameter("mission_file").value
        if not mission_file:
            mission_file = str(
                pkg_dir / "drone_bringup" / "config" / "mission_waypoints.yaml"
            )

        self.mission_data = self._load_yaml(mission_file)
        self.survivors: list[dict] = []
        self.anchors_deployed = 0
        self.current_floor = 1
        self.current_phase = "idle"
        self.start_time = time.time()

        self.survivor_sub = self.create_subscription(
            SurvivorReport,
            "/drone/survivor/report",
            self.survivor_callback,
            10,
        )
        self.status_sub = self.create_subscription(
            MissionStatus, "/mission/status", self.status_callback, 10
        )
        self.fused_sub = self.create_subscription(
            FusedPose, "/drone/pose/fused", self.pose_callback, 10
        )
        self.anchor_dep_sub = self.create_subscription(
            AnchorDeployment,
            "/drone/uwb/deploy_request",
            self.anchor_deploy_callback,
            10,
        )

        self.status_pub = self.create_publisher(
            MissionStatus, "/mission/status", 10
        )
        self.command_pub = self.create_publisher(
            String, "/mission/command", 10
        )
        self._land_sent = False

        self.timer = self.create_timer(2.0, self.publish_summary)

        self.get_logger().info("Mission planner started")

    def _load_yaml(self, path: str) -> dict:
        try:
            with open(path, "r") as f:
                return yaml.safe_load(f)
        except Exception as e:
            self.get_logger().error(f"Failed to load {path}: {e}")
            return {}

    def survivor_callback(self, msg: SurvivorReport):
        if msg.marker_id not in [s.get("marker_id") for s in self.survivors]:
            self.survivors.append({
                "marker_id": msg.marker_id,
                "x": msg.x,
                "y": msg.y,
                "z": msg.z,
                "confidence": msg.confidence,
            })
            self.get_logger().info(
                f"Survivor #{msg.marker_id} recorded "
                f"(total: {len(self.survivors)})"
            )

    def status_callback(self, msg: MissionStatus):
        self.current_floor = msg.current_floor
        self.current_phase = msg.mission_phase

    def anchor_deploy_callback(self, msg: AnchorDeployment):
        self.anchors_deployed += 1

    def pose_callback(self, msg: FusedPose):
        pass

    def publish_summary(self):
        elapsed = time.time() - self.start_time
        status = MissionStatus()
        status.current_floor = self.current_floor
        status.current_waypoint_id = -1
        status.mission_phase = self.current_phase
        status.num_anchors_deployed = self.anchors_deployed
        status.num_survivors_found = len(self.survivors)
        status.localization_source = "unknown"
        status.elapsed_time = round(elapsed, 1)
        self.status_pub.publish(status)

        if self.current_phase == "MISSION_COMPLETE":
            self._print_final_report()
            if not self._land_sent:
                cmd = String()
                cmd.data = "land"
                self.command_pub.publish(cmd)
                self._land_sent = True
                self.get_logger().info("issued land command")

    def _print_final_report(self):
        self.get_logger().info("=" * 60)
        self.get_logger().info("FINAL MISSION REPORT")
        self.get_logger().info(f"  Survivors found: {len(self.survivors)}")
        for s in self.survivors:
            self.get_logger().info(
                f"    #{s['marker_id']}: ({s['x']:.2f}, {s['y']:.2f}, "
                f"{s['z']:.2f}) conf={s['confidence']:.3f}"
            )
        self.get_logger().info(
            f"  UWB anchors deployed: {self.anchors_deployed}"
        )
        elapsed = time.time() - self.start_time
        self.get_logger().info(f"  Mission duration: {elapsed:.1f}s")
        self.get_logger().info("=" * 60)


def main(args=None):
    rclpy.init(args=args)
    node = MissionPlannerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
