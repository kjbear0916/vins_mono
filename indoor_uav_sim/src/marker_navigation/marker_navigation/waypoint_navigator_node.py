#!/usr/bin/env python3
"""Waypoint navigator: marker-map waypoint state machine with floor lift.

State machine (SPEC.md section 8.5):
  IDLE -> CHECK_OCCLUSION_ZONE -> (DEPLOY_ANCHOR) -> ALIGNING ->
  MOVING_TO_WAYPOINT -> ARRIVED -> NEXT

Floor transitions use the open stairwell/atrium shaft: at a
`stairwell_entry` waypoint the drone hovers over the shaft centre, then
VERTICAL_TRANSITION climbs/descends to the target floor cruise altitude
while keeping XY, then resumes lateral navigation to the exit marker.

Target altitude is DECOUPLED from marker pose: marker z is floor-mounted
(marker_map.yaml), flight altitude = (floor-1)*3 + 0.2 + cruise_offset
(navigation_params.yaml). Yaw is not actively tracked in this phase
(angular velocity left at 0; heading follows MAVSDK defaults).

Publishing: desired velocity on /drone/cmd_vel_raw. It flows through the
obstacle avoider, which publishes the fused /drone/cmd_vel consumed by
drone_control (MAVSDK offboard).
"""
import yaml
from pathlib import Path
from enum import Enum, auto

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist

from drone_msgs.msg import (FusedPose, MissionStatus, MarkerPose,
                            AnchorDeployment)


class NavState(Enum):
    IDLE = auto()
    CHECK_OCCLUSION_ZONE = auto()
    DEPLOY_ANCHOR = auto()
    ALIGNING = auto()
    MOVING_TO_WAYPOINT = auto()
    ARRIVED = auto()
    VERTICAL_TRANSITION = auto()
    MISSION_COMPLETE = auto()


class WaypointNavigatorNode(Node):
    def __init__(self):
        super().__init__("waypoint_navigator")

        pkg_dir = Path(__file__).resolve().parent.parent.parent
        cfg = pkg_dir / "drone_bringup" / "config"

        self.declare_parameter("marker_map_file", str(cfg / "marker_map.yaml"))
        self.declare_parameter("mission_file", str(cfg / "mission_waypoints.yaml"))
        self.declare_parameter("occlusion_zones_file", str(cfg / "occlusion_zones.yaml"))
        self.declare_parameter("nav_params_file", str(cfg / "navigation_params.yaml"))

        self.marker_map = self._yaml(self.get_parameter("marker_map_file").value)
        self.mission_data = self._yaml(self.get_parameter("mission_file").value)
        self.occlusion_zones = self._occlusion_zones(
            self.get_parameter("occlusion_zones_file").value)
        nav = self._yaml(self.get_parameter("nav_params_file").value).get("navigation", {})

        self.storey = float(nav.get("storey_height", 3.0))
        self.slab_top = float(nav.get("slab_top", 0.2))
        self.cruise_offset = float(nav.get("cruise_offset", 1.2))
        self.kp = float(nav.get("position_kp", 0.8))
        self.max_h = float(nav.get("max_horizontal_speed", 1.5))
        self.max_v = float(nav.get("max_vertical_speed", 1.0))
        self.pos_tol = float(nav.get("position_tolerance", 0.3))
        self.stair_radius = float(nav.get("stairwell_align_radius", 1.0))

        markers = self.marker_map.get("markers", {})
        self._marker_pose = {int(k): v for k, v in markers.items()}
        self.waypoints = self._build_waypoints()
        self.get_logger().info(f"Loaded {len(self.waypoints)} mission waypoints")

        self.state = NavState.IDLE
        self.idx = 0
        self.floor = 1
        self.fused = None
        self.seen_marker_id = None
        self.anchor_this_zone = False

        self.fused_sub = self.create_subscription(
            FusedPose, "/drone/pose/fused", self.on_fused, 10)
        self.marker_sub = self.create_subscription(
            MarkerPose, "/drone/marker/pose", self.on_marker, 10)

        self.cmd_pub = self.create_publisher(Twist, "/drone/cmd_vel_raw", 10)
        self.status_pub = self.create_publisher(MissionStatus, "/mission/status", 10)
        self.deploy_pub = self.create_publisher(
            AnchorDeployment, "/drone/uwb/deploy_request", 10)

        self.timer = self.create_timer(0.1, self.loop)
        self.status_timer = self.create_timer(1.0, self.emit_status)
        self.get_logger().info(f"Navigator ready, state={self.state.name}")

    # ---- helpers ----------------------------------------------------------
    def _yaml(self, path: str) -> dict:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            self.get_logger().error(f"Failed to load {path}: {e}")
            return {}

    def _occlusion_zones(self, path: str) -> dict:
        data = self._yaml(path)
        return {int(z["trigger_waypoint"]): z
                for z in data.get("zones", []) if "trigger_waypoint" in z}

    def _build_waypoints(self):
        wps = self.mission_data.get("mission", {}).get("waypoints", [])
        out = []
        for w in wps:
            marker_id = int(w["marker_id"])
            pose = self._marker_pose.get(marker_id, {"x": 0.0, "y": 0.0, "yaw": 0.0})
            out.append({
                "id": int(w["id"]),
                "floor": int(w.get("floor", 1)),
                "marker_id": marker_id,
                "action": w.get("action", "navigate"),
                "vertical": bool(w.get("vertical", False)),
                "x": float(pose.get("x", 0.0)),
                "y": float(pose.get("y", 0.0)),
                "yaw": float(pose.get("yaw", 0.0)),
            })
        return out

    def _cruise(self, floor: int) -> float:
        return (floor - 1) * self.storey + self.slab_top + self.cruise_offset

    def _wp(self):
        if not self.waypoints or self.idx >= len(self.waypoints):
            return None
        return self.waypoints[self.idx]

    def on_fused(self, msg: FusedPose):
        self.fused = msg.pose.pose
        self._loc = msg.source or "unknown"

    def on_marker(self, msg):
        self.seen_marker_id = msg.marker_id

    # ---- state handlers ---------------------------------------------------
    def loop(self):
        h = {
            NavState.IDLE: self._h_idle,
            NavState.CHECK_OCCLUSION_ZONE: self._h_check,
            NavState.DEPLOY_ANCHOR: self._h_deploy,
            NavState.ALIGNING: self._h_align,
            NavState.MOVING_TO_WAYPOINT: self._h_move,
            NavState.ARRIVED: self._h_arrived,
            NavState.VERTICAL_TRANSITION: self._h_vertical,
            NavState.MISSION_COMPLETE: self._h_stop,
        }
        h[self.state]()

    def _h_idle(self):
        if not self.waypoints:
            self.state = NavState.MISSION_COMPLETE
            return
        self.get_logger().info(f"Mission start: {len(self.waypoints)} waypoints")
        self.state = NavState.CHECK_OCCLUSION_ZONE

    def _h_check(self):
        wp = self._wp()
        if wp is None:
            self.state = NavState.MISSION_COMPLETE
            return
        zone = self.occlusion_zones.get(wp["marker_id"])
        if zone and zone.get("risk_level") == "high" and not self.anchor_this_zone:
            self.get_logger().info(
                f"Occlusion zone '{zone['id']}' ahead (wp {wp['id']}) -> "
                "deploying anchor at current ArUco-trusted position")
            self.state = NavState.DEPLOY_ANCHOR
            return
        self.anchor_this_zone = False
        self.state = NavState.ALIGNING

    def _h_deploy(self):
        if self.fused is None:
            return
        dep = AnchorDeployment()
        dep.anchor_id = -1                      # id assigned by anchor_manager
        dep.x = self.fused.position.x
        dep.y = self.fused.position.y
        dep.z = self.fused.position.z
        dep.deploy_time = float(self.get_clock().now().nanoseconds) / 1e9
        dep.trigger_zone = "occlusion_front"
        self.deploy_pub.publish(dep)
        self.get_logger().info(
            f"Deploy request @ ({dep.x:.2f}, {dep.y:.2f}, {dep.z:.2f})")
        self.anchor_this_zone = True
        self.state = NavState.ALIGNING

    def _h_align(self):
        wp = self._wp()
        if wp is None or self.fused is None:
            return
        if wp["vertical"]:
            # already over the shaft centre (or within align radius of it):
            # engage the vertical climb directly
            self.state = NavState.VERTICAL_TRANSITION
            return
        dz = self._cruise(wp["floor"]) - self.fused.position.z
        dx = wp["x"] - self.fused.position.x
        dy = wp["y"] - self.fused.position.y
        if abs(dz) < self.pos_tol and (dx**2 + dy**2) ** 0.5 < self.pos_tol:
            self.state = NavState.ARRIVED
        else:
            self.state = NavState.MOVING_TO_WAYPOINT

    def _h_move(self):
        wp = self._wp()
        if wp is None or self.fused is None:
            return
        target_z = self._cruise(wp["floor"])
        dx = wp["x"] - self.fused.position.x
        dy = wp["y"] - self.fused.position.y
        dz = target_z - self.fused.position.z

        if (abs(dz) < self.pos_tol
                and (dx**2 + dy**2) ** 0.5 < self.pos_tol):
            self.cmd_pub.publish(Twist())
            self.state = NavState.ARRIVED
            return

        cmd = Twist()
        cmd.linear.x = self.kp * dx
        cmd.linear.y = self.kp * dy
        cmd.linear.z = self.kp * dz
        self._limit(cmd)
        self.cmd_pub.publish(cmd)

    def _limit(self, cmd: Twist):
        h = (cmd.linear.x**2 + cmd.linear.y**2) ** 0.5
        if h > self.max_h:
            s = self.max_h / h
            cmd.linear.x *= s
            cmd.linear.y *= s
        if abs(cmd.linear.z) > self.max_v:
            cmd.linear.z = self.max_v * (1 if cmd.linear.z > 0 else -1)

    def _h_arrived(self):
        wp = self._wp()
        if wp is None:
            self.state = NavState.MISSION_COMPLETE
            return
        self.get_logger().info(
            f"Arrived wp {wp['id']} marker {wp['marker_id']} "
            f"floor {wp['floor']} action {wp['action']}")
        if wp["action"] == "land":
            self.state = NavState.MISSION_COMPLETE
            return
        self.floor = wp["floor"]
        self.idx += 1
        self.anchor_this_zone = False
        self.seen_marker_id = None
        self.state = NavState.CHECK_OCCLUSION_ZONE

    def _h_vertical(self):
        wp = self._wp()
        if wp is None or self.fused is None:
            return

        # horizontal align to the shaft centre BEFORE climbing: the entry
        # marker (e.g. 109) is at the shaft centre on F1; on F2/F3 the exit
        # marker sits beside the opening, so we climb at the entry XY.
        dx = wp["x"] - self.fused.position.x
        dy = wp["y"] - self.fused.position.y
        hdist = (dx**2 + dy**2) ** 0.5
        target_z = self._cruise(wp["floor"])
        dz = target_z - self.fused.position.z

        if hdist > self.stair_radius:
            cmd = Twist()
            cmd.linear.x = self.kp * dx
            cmd.linear.y = self.kp * dy
            self._limit(cmd)
            self.cmd_pub.publish(cmd)
            return

        if abs(dz) < self.pos_tol:
            self.cmd_pub.publish(Twist())
            self.get_logger().info(
                f"Vertical transition done: floor {self.floor} -> {wp['floor']}")
            # stay on this waypoint; lateral navigation to the exit marker XY
            # happens in ALIGNING/MOVING
            self.state = NavState.ALIGNING
            return

        cmd = Twist()
        cmd.linear.z = self.kp * dz
        self._limit(cmd)
        self.cmd_pub.publish(cmd)

    def _h_stop(self):
        self.cmd_pub.publish(Twist())

    def emit_status(self):
        if not hasattr(self, "_status_t0"):
            self._status_t0 = self.get_clock().now()
        wp = self._wp()
        s = MissionStatus()
        s.current_floor = self.floor
        s.current_waypoint_id = wp["id"] if wp else -1
        s.mission_phase = self.state.name
        s.num_anchors_deployed = -1
        s.num_survivors_found = -1
        s.localization_source = getattr(self, "_loc", "unknown")
        s.elapsed_time = (self.get_clock().now() - self._status_t0).nanoseconds / 1e9
        self.status_pub.publish(s)


def main(args=None):
    rclpy.init(args=args)
    node = WaypointNavigatorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()