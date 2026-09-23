#!/usr/bin/env python3
# Copyright 2026. disaster_drone_ws marker localization core (ROS-free, host-testable).
"""ArUco detection -> camera pose -> world pose (spec SS8.1).

Pure numpy/cv2 - no rclpy. The ROS node in this package is only a wrapper
around ``MarkerEstimator``; the math is verified on the host by
``tests/test_marker_localization.py``.
"""

import numpy as np


def _to_np(*vecs):
    return [np.asarray(v, dtype=float) for v in vecs]


def estimate_marker_pose(corners, marker_size_m, camera_matrix, dist_coeffs=None):
    """solvePnP for a single detected marker.

    Args:
        corners: (4,2) image corner pixel coords (top-left, top-right,
                 bottom-right, bottom-left per ArUco marker convention).
        marker_size_m: physical marker side length (m).
        camera_matrix: (3,3) intrinsics.
        dist_coeffs: (k,1) distortion vector or None.

    Returns:
        (ok, tvec_cam, rvec_cam): world(3D)-to-camera translation and
        Rodrigues rotation of the marker frame as seen from the camera.
    """
    corners = np.asarray(corners, dtype=np.float32).reshape(1, 4, 2)
    hw = marker_size_m / 2.0
    obj = np.array([[-hw, hw, 0], [hw, hw, 0],
                    [hw, -hw, 0], [-hw, -hw, 0]],
                   dtype=np.float32)
    dc = np.zeros((5, 1)) if dist_coeffs is None else np.asarray(dist_coeffs, dtype=np.float32)
    ok, rvec, tvec = cv2_solvePnP(obj, corners, np.asarray(camera_matrix, dtype=np.float32), dc)
    return bool(ok), (np.asarray(tvec, dtype=float).ravel()
                      if ok else None), (np.asarray(rvec, dtype=float).ravel() if ok else None)


# Kept out of the hot path so host tests can import the module without cv2
# installed; the node environment always has it.
def _import_cv2():
    import cv2
    return cv2


def cv2_solvePnP(obj, img, cam, dc):
    cv2 = _import_cv2()
    ok, rvec, tvec = cv2.solvePnP(obj, img, cam, dc)
    return ok, rvec, tvec


# Camera optical frame -> ENU world for a level, forward-looking, yaw=0 drone.
# Optical (OpenCV): +x right, +y down, +z forward. Body/world (ENU): +x forward,
# +y left, +z up. Optical +z(fwd)->+x, +x(right)->-y, +y(down)->-z.
R_CAM_TO_LEVEL = np.array([
    [0, 0, 1],
    [-1, 0, 0],
    [0, -1, 0],
], dtype=float)


def world_from_cam_pose(cam_world, tvec_cam, rvec_cam, R_world_from_cam=R_CAM_TO_LEVEL,
                        body_yaw_rad=0.0):
    """Transform a marker's camera-frame pose into world coordinates.

    Args:
        cam_world: (3,) camera optical center in world frame (drone pose).
        tvec_cam:  (3,) marker origin in camera frame.
        rvec_cam:  (3,) Rodrigues rotation, marker axis -> camera axis.
        R_world_from_cam: rotation taking camera-frame vectors to the drone's
            level body frame (identity-corrected default: forward-looking cam).
        body_yaw_rad: drone yaw about world +z, applied as the final frame
            rotation. 0 is north (world +x).

    Returns:
        (tvec_world, yaw_deg): marker origin in world frame and the marker's
        yaw about the world Z axis.
    """
    cam_world, tvec_cam = _to_np(cam_world, tvec_cam)
    cv2 = _import_cv2()
    R_cam_from_marker, _ = cv2.Rodrigues(np.asarray(rvec_cam, dtype=float))
    R_world_from_level = np.array([
        [np.cos(body_yaw_rad), -np.sin(body_yaw_rad), 0],
        [np.sin(body_yaw_rad), np.cos(body_yaw_rad), 0],
        [0, 0, 1]], dtype=float)
    R_world_from_cam = R_world_from_level @ np.asarray(R_world_from_cam, dtype=float)
    tmark = R_world_from_cam @ np.asarray(tvec_cam, dtype=float).ravel() + np.asarray(cam_world, dtype=float).ravel()
    Rm = R_world_from_cam @ R_cam_from_marker
    yaw = float(np.arctan2(Rm[1, 0], Rm[0, 0]))
    return np.asarray(tmark, dtype=float).ravel(), np.degrees(yaw)


def simulated_detection(marker_id, marker_map, drone_world):
    """Ground-truth detection for simulate_detections=true (spec Q1 / §8.1 fallback).

    Returns a fake MarkerPose-shaped dict at the marker's mapped world pose,
    with confidence 1.0 when the marker is within the camera's occlusion-free
    assumption (no opacity modelling here; the zone logic lives in fusion).
    """
    m = marker_map.get(int(marker_id))
    if m is None:
        return None
    _d, drone_reason = simulated_visible(marker_id, marker_map, drone_world)
    return {"marker_id": int(marker_id), "confidence": 1.0 if drone_reason is None else 0.0,
            "x": float(m["x"]), "y": float(m["y"]), "z": float(m["z"]),
            "yaw_deg": float(m.get("yaw", 0.0)), "reason": drone_reason}


def simulated_visible(marker_id, marker_map, drone_world):
    """Visibility rule for the simulation: markers seen only when within a
    generous range and roughly level; survivors (900+) are 'visible' from any
    point in the same room band. Returns (visible_anyway, reason_or_None)."""
    m = marker_map.get(int(marker_id))
    if m is None:
        return False, "unknown marker"
    dx = float(m["x"]) - float(drone_world[0])
    dy = float(m["y"]) - float(drone_world[1])
    d2 = dx * dx + dy * dy
    rng = float(m.get("size", 0.25)) * 40.0  # ~10 m typical line of sight
    if d2 <= rng * rng:
        return True, None
    return False, "out of detection range"


def detect_from_frame(frame, aruco_dict, camera_matrix, marker_map,
                      marker_size_m=0.25, dist_coeffs=None):
    """Full pipeline: detect all ArUco markers in a BGR frame and return
    MarkerPose dicts in world coordinates.

    This is the function the ROS node calls every frame. The math helpers
    above are separated so the transformation logic is unit-testable without
    rendering real markers.
    """
    cv2 = _import_cv2()
    detector = cv2.aruco.ArucoDetector(cv2.aruco.getPredefinedDictionary(aruco_dict))
    corners, ids, _ = detector.detectMarkers(frame)
    out = []
    if ids is None:
        return out
    for c, mid in zip(corners, ids.ravel()):
        ok, tvec, rvec = estimate_marker_pose(c, marker_size_m, camera_matrix, dist_coeffs)
        if not ok:
            continue
        drone_pose = np.array([0.0, 0.0, 0.0])  # set by the node; kept here for math symmetry
        tmark, yaw_deg = world_from_cam_pose(drone_pose, tvec, rvec)
        out.append({"marker_id": int(mid), "confidence": 1.0,
                    "x": float(tmark[0]), "y": float(tmark[1]), "z": float(tmark[2]),
                    "yaw_deg": yaw_deg})
    return out