#!/usr/bin/env python3
# Copyright 2026. disaster_drone_ws mission control core (ROS-free, host-testable).
"""Mission-orchestration state machine (spec SS8.6).

Drives the rescue mission phase-by-phase against the scene config:
  - while navigating the route it tracks floor / waypoint progress,
  - transitions to CLIMB at the atrium_climb node, back to NAVIGATE after,
  - tracks deployed-anchor count for the /mission/status topic,
  - exposes a status dict shaped exactly like ``MissionStatus.msg`` so the
    ROS wrapper only copies fields.
No rclpy here.
"""


class MissionFSM:
    STATES = ("IDLE", "TAKEOFF", "NAVIGATE", "CLIMB", "HOLD", "LANDED", "ABORT")

    def __init__(self, route_follower, total_waypoints_hint=None):
        self.route = route_follower
        self.state = "IDLE"
        self.anchor_count = 0
        self.note = "init"
        self._total = int(total_waypoints_hint) if total_waypoints_hint \
            else int(self.route.total_nodes)
        self._floors_visited = {int(self.route.floor)}

    # -- transitions -----------------------------------------------------
    def transition(self, new_state, note=None):
        if new_state not in self.STATES:
            raise ValueError(f"unknown state {new_state}")
        self.state = new_state
        if note:
            self.note = note
        return self.state

    def on_takeoff_complete(self):
        return self.transition("NAVIGATE", "takeoff done")

    def on_anchor_deployed(self, count=None):
        self.anchor_count = (self.anchor_count + 1) if count is None else int(count)
        self.note = f"{self.anchor_count} anchors deployed"
        return self.anchor_count

    def abort(self, reason="aborted by operator"):
        return self.transition("ABORT", reason)

    # -- per-iteration drive --------------------------------------------
    def on_waypoint_update(self, pose_xyz, t_s):
        """Feed the follower; returns (state, waypoint_or_None). The follower
        handles arrival detection and climb staging; we only mirror state."""
        wp = self.route.update(pose_xyz, t_s)
        floor = int(self.route.floor)
        if floor not in self._floors_visited:
            self._floors_visited.add(floor)
            self.note = f"entered floor {floor}"
        if wp is not None and wp.get("climb"):
            if self.state != "CLIMB":
                self.transition("CLIMB", "climbing atrium")
        elif wp is not None:
            if self.state in ("IDLE", "CLIMB"):
                self.transition("NAVIGATE", "navigating route")
        if self.route.completed:
            self.transition("HOLD", "route complete")
            wp = None
        return self.state, wp

    # -- status / report -------------------------------------------------
    def status(self):
        """Emit the MissionStatus.msg-shaped dict."""
        node = self._current_route_node()
        waypoint_id = int(node.get("id")) if (node and node.get("type") == "marker") else -1
        return {
            "state": self.state,
            "current_floor": int(self.route.floor),
            "current_waypoint": waypoint_id,
            "total_waypoints": int(self._total),
            "deployed_anchors": int(self.anchor_count),
            "note": self.note,
        }

    def _current_route_node(self):
        idx = int(self.route.current_index)
        try:
            return self.route._nodes[idx]
        except (AttributeError, IndexError):
            return None