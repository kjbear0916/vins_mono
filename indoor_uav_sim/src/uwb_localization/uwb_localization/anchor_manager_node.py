#!/usr/bin/env python3
"""UWB Anchor Manager node.

Manages dynamic deployment of UWB anchors. When a deployment request
is received and the current position is from a trusted ArUco source,
deploys a new anchor at the current position.

Maintains the deployed anchor list and writes to deployed_anchors.yaml.
Spawns Gazebo visual models for each anchor.
"""
import time
import yaml
from pathlib import Path

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped

from drone_msgs.msg import UwbAnchor, AnchorDeployment, FusedPose


class AnchorManagerNode(Node):
    def __init__(self):
        super().__init__("anchor_manager")

        self.declare_parameter("deployed_anchors_file", "")
        self.declare_parameter("spawn_gz_models", True)

        pkg_dir = Path(__file__).resolve().parent.parent.parent
        self.anchors_file = self.get_parameter("deployed_anchors_file").value
        if not self.anchors_file:
            self.anchors_file = str(
                pkg_dir / "drone_bringup" / "config" / "deployed_anchors.yaml"
            )

        self.spawn_gz = self.get_parameter("spawn_gz_models").value

        self.deployed_anchors: list[dict] = []
        self.current_pose = None
        self.current_source = "unknown"
        self.next_anchor_id = 1

        self._load_existing_anchors()

        self.deploy_sub = self.create_subscription(
            AnchorDeployment,
            "/drone/uwb/deploy_request",
            self.deploy_callback,
            10,
        )
        self.fused_sub = self.create_subscription(
            FusedPose, "/drone/pose/fused", self.pose_callback, 10
        )

        self.anchor_pub = self.create_publisher(
            UwbAnchor, "/drone/uwb/anchors", 10
        )

        self.timer = self.create_timer(1.0, self.publish_anchors)

        self.get_logger().info(
            f"Anchor manager started, "
            f"{len(self.deployed_anchors)} existing anchors"
        )

    def _load_existing_anchors(self):
        try:
            if Path(self.anchors_file).exists():
                with open(self.anchors_file, "r") as f:
                    data = yaml.safe_load(f)
                self.deployed_anchors = data.get("anchors", [])
                if self.deployed_anchors:
                    max_id = max(a.get("anchor_id", 0) for a in self.deployed_anchors)
                    self.next_anchor_id = max_id + 1
                self.get_logger().info(
                    f"Loaded {len(self.deployed_anchors)} existing anchors"
                )
        except Exception as e:
            self.get_logger().warn(f"Could not load existing anchors: {e}")

    def pose_callback(self, msg: FusedPose):
        self.current_pose = msg.pose.pose
        self.current_source = msg.source

    def deploy_callback(self, msg: AnchorDeployment):
        if self.current_pose is None:
            self.get_logger().warn("Cannot deploy anchor: no pose available")
            return

        if self.current_source != "aruco":
            self.get_logger().warn(
                f"Anchor deployment rejected: current source is "
                f"'{self.current_source}', need 'aruco' for reliable position"
            )
            return

        anchor = {
            "anchor_id": self.next_anchor_id,
            "x": round(self.current_pose.position.x, 4),
            "y": round(self.current_pose.position.y, 4),
            "z": round(self.current_pose.position.z, 4),
            "deploy_time": time.time(),
            "is_active": True,
            "trigger_zone": msg.trigger_zone,
        }

        self.deployed_anchors.append(anchor)
        self.next_anchor_id += 1

        self.get_logger().info(
            f"Deployed anchor #{anchor['anchor_id']} at "
            f"({anchor['x']:.2f}, {anchor['y']:.2f}, {anchor['z']:.2f})"
        )

        self._save_anchors()

        if self.spawn_gz:
            self._spawn_gz_model(anchor)

    def _save_anchors(self):
        try:
            data = {"anchors": self.deployed_anchors}
            with open(self.anchors_file, "w") as f:
                yaml.dump(data, f, default_flow_style=False)
            self.get_logger().info(
                f"Saved {len(self.deployed_anchors)} anchors to {self.anchors_file}"
            )
        except Exception as e:
            self.get_logger().error(f"Failed to save anchors: {e}")

    def _spawn_gz_model(self, anchor: dict):
        model_sdf = f"""
        <sdf version="1.12">
          <model name="uwb_anchor_{anchor['anchor_id']}">
            <static>true</static>
            <pose>{anchor['x']} {anchor['y']} {anchor['z']} 0 0 0</pose>
            <link name="link">
              <visual name="visual">
                <geometry>
                  <cylinder>
                    <radius>0.05</radius>
                    <length>0.1</length>
                  </cylinder>
                </geometry>
                <material>
                  <ambient>0 0.8 0 1</ambient>
                  <diffuse>0 1 0 1</diffuse>
                  <emissive>0 0.5 0 1</emissive>
                </material>
              </visual>
              <collision name="collision">
                <geometry>
                  <cylinder>
                    <radius>0.05</radius>
                    <length>0.1</length>
                  </cylinder>
                </geometry>
              </collision>
            </link>
          </model>
        </sdf>
        """
        try:
            import subprocess
            sdf_path = f"/tmp/anchor_{anchor['anchor_id']}.sdf"
            with open(sdf_path, "w") as f:
                f.write(model_sdf)
            subprocess.Popen(
                ["gz", "spawn", "-s", "-f", sdf_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            self.get_logger().warn(f"Could not spawn GZ model: {e}")

    def publish_anchors(self):
        for anchor in self.deployed_anchors:
            msg = UwbAnchor()
            msg.anchor_id = int(anchor["anchor_id"])
            msg.x = float(anchor["x"])
            msg.y = float(anchor["y"])
            msg.z = float(anchor["z"])
            msg.deploy_time = float(anchor["deploy_time"])
            msg.is_active = bool(anchor.get("is_active", True))
            self.anchor_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = AnchorManagerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
