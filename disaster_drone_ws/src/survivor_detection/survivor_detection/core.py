#!/usr/bin/env python3
# Copyright 2026. disaster_drone_ws survivor detection core (ROS-free, host-testable).
"""Survivor-marker detection & report aggregation (spec SS8.8).

A survivor is a marker in the 900-999 id range whose ``kind`` is
``survivor`` in marker_map.yaml. The core class dedupes by marker id, requires
a minimum confidence, records first-seen time, and emits
``SurvivorReport.msg``-shaped dicts. No rclpy.
"""


class SurvivorNotFound(RuntimeError):
    pass


class SurvivorTracker:
    def __init__(self, marker_map, min_confidence=0.5, first_report=True):
        self.marker_map = marker_map
        self.min_conf = float(min_confidence)
        self._seen = {}       # id -> dict(first_seen_t, n, last_conf)
        self._reported = set()

    def classify(self, marker_id):
        """'survivor' | 'waypoint' | 'unknown' by marker kind."""
        m = self.marker_map.get(int(marker_id))
        if m is None:
            return "unknown"
        return m.get("kind", "unknown")

    def update(self, detections, t_s):
        """detections: iterable of dicts with marker_id/confidence/x/y/z.
        Returns a list of new SurvivorReport-shaped dicts (first confirmed
        detection per survivor), or [] when nothing new."""
        reports = []
        for d in detections:
            mid = int(d["marker_id"])
            conf = float(d.get("confidence", 0.0))
            if self.classify(mid) != "survivor":
                continue
            if conf < self.min_conf:
                continue
            prev = self._seen.get(mid)
            if prev is None:
                self._seen[mid] = {"first_seen_t": float(t_s), "n": 1,
                                   "last_conf": conf}
            else:
                prev["n"] += 1
                prev["last_conf"] = max(prev["last_conf"], conf)
            if mid not in self._reported:
                m = self.marker_map[mid]
                self._reported.add(mid)
                reports.append({
                    "marker_id": mid,
                    "confidence": conf,
                    "x": float(d.get("x", m.get("x", 0.0))),
                    "y": float(d.get("y", m.get("y", 0.0))),
                    "z": float(d.get("z", m.get("z", 0.0))),
                    "floor": _floor_from_z(d.get("z", m.get("z", 0.0))),
                    "first_seen_t": float(t_s),
                    "n_detections": prev["n"] if prev is not None else 1,
                })
        return reports

    def seen_ids(self):
        return sorted(self._seen)

    def reported_ids(self):
        return sorted(self._reported)

    def count(self):
        return len(self._seen)


def _floor_from_z(z, slab=0.30, floor_h=3.0):
    """Floor from world z using scene_gen slab heights (1F top 0.35, 2F 3.35..)."""
    return max(1, int(float(z) // floor_h) + 1)