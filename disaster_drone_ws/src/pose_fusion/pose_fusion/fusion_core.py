# Copyright 2026. disaster_drone_ws pose fusion core (ROS-free, host-testable).
"""Localisation-source switching state machine (spec SS8.4).

ArUco is the primary source. UWB takes over when markers go missing for
``miss_threshold`` consecutive frames while inside a marked occlusion zone;
detection for ``reentry_frames`` consecutive frames flips back. The
downstream consumer only ever sees the fused output.
"""

SOURCE_ARUCO = "aruco"
SOURCE_UWB = "uwb"


class FusionEngine:
    def __init__(self, miss_threshold=10, reentry_frames=3, require_zone=True):
        self.miss_threshold = int(miss_threshold)
        self.reentry_frames = int(reentry_frames)
        self.require_zone = bool(require_zone)
        self.source = SOURCE_ARUCO
        self._miss = 0
        self._seen = 0
        self.lost_seconds = 0.0
        self.last_reason = "init"

    def update(self, marker_detected, near_zone=None, dt_s=0.1):
        """Feed one detection frame; returns the active source after update."""
        made = False
        if marker_detected:
            self._miss = 0
            self._seen += 1
            if self.source == SOURCE_UWB:
                if self._seen >= self.reentry_frames:
                    self.source = SOURCE_ARUCO
                    self.last_reason = "marker re-acquired"
                    made = True
            else:
                made = True
        else:
            self._seen = 0
            self._miss += 1
            self.lost_seconds += dt_s
            if ((self.require_zone and near_zone) or (not self.require_zone and near_zone is not False)) \
                    and self.source == SOURCE_ARUCO and self._miss >= self.miss_threshold:
                self.source = SOURCE_UWB
                self.last_reason = "markers lost inside occlusion zone"
                made = True
        return self.source

    def reset(self):
        self.source = SOURCE_ARUCO
        self._miss = 0
        self._seen = 0
        self.lost_seconds = 0.0
        self.last_reason = "reset"

    def status(self):
        return {"source": self.source, "miss_frames": self._miss,
                "seen_frames": self._seen, "lost_seconds": round(self.lost_seconds, 2)}


def near_risk_zone(x, y, z, zones, marker_map, radius_factor=1.0):
    """True when (x, y, z) sits within a zone's radius of its trigger marker.

    A zone is 'active' when the drone is within ``radius*radius_factor`` of
    the trigger waypoint's known pose. Zones without radius default to 2.5 m.
    """
    for zz in zones:
        mid = int(zz.get("trigger_waypoint", -1))
        mpose = marker_map.get(mid)
        if mpose is None:
            continue
        r = float(zz.get("radius_m", 2.5)) * radius_factor
        d = ((x - mpose["x"]) ** 2 + (y - mpose["y"]) ** 2 + (z - mpose["z"]) ** 2) ** 0.5
        if d <= r:
            return True
    return False


def fuse(aruco, uwb, source):
    """Pick the drive pose. Returns (pose, source_label, confidence)."""
    if source == SOURCE_ARUCO:
        return aruco, SOURCE_ARUCO, aruco.get("confidence", 1.0) if aruco else 0.0
    return uwb, SOURCE_UWB, uwb.get("confidence", 0.7) if uwb else 0.0