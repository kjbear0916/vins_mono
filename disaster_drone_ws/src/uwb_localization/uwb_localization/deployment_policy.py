# Copyright 2026. disaster_drone_ws deployment policy (ROS-free) v1.
"""Decides when and where to deploy UWB anchors (spec SS8.2).

Policy:
  - deploy only while localising via ArUco (high confidence),
  - and the next target waypoint carries a high-risk occlusion zone,
  - and no existing anchor is already within ``min_spacing_m`` of here.
The anchor is placed at the *current* fused pose, which is trusted at that
instant because the source is ArUco.
"""

SOURCE_ARUCO = "aruco"
SOURCE_UWB = "uwb"

HIGH_RISK = ("high", "manual")


def should_deploy(source, next_waypoint_id, zones, current_pose,
                  existing_anchors, min_spacing_m=0.5,
                  acceptable_levels=HIGH_RISK):
    """Returns (should_deploy: bool, reason: str)."""
    if source != SOURCE_ARUCO:
        return False, f"source is {source}, not aruco"
    zone = next(z for z in zones if int(z.get("trigger_waypoint", -1)) == int(next_waypoint_id)) \
        if any(int(z.get("trigger_waypoint", -1)) == int(next_waypoint_id) for z in zones) else None
    if zone is None:
        return False, "no occlusion zone at next waypoint"
    if zone.get("risk_level") not in acceptable_levels:
        return False, f"risk {zone.get('risk_level')} not deployable"
    for a in existing_anchors:
        d = ((a["x"] - current_pose[0]) ** 2 +
             (a["y"] - current_pose[1]) ** 2 +
             (a["z"] - current_pose[2]) ** 2) ** 0.5
        if d <= min_spacing_m:
            return False, f"anchor {a['id']} already within {d:.2f} m"
    return True, f"zone {zone.get('id')} requires pre-deployment"