"""Step-3 loader: read and validate the per-marker world pose file.

The file is a simple JSON dictionary keyed by marker id (string):

    {
      "0": {"x": 0.0, "y": 0.0, "z": 1.2, "measurement_error_mm": 5,
            "rx_deg": 90, "ry_deg": 0, "rz_deg": 0},
      ...
    }

rx_deg / ry_deg / rz_deg are optional; they define the rotation from the
marker coordinate frame to the world frame (marker mounted on a wall, its
outward-facing axis rotated into the room).  When omitted R_m2w = I.

Load + sanity checks:
  - each marker must have x,y,z and measurement_error_mm
  - any error_mm > 20 generates a warning (likely a measurement mistake)
  - at least 4 markers recommended (plan step-3 text)
"""
import json

import numpy as np


def _euler_deg_to_R(rx, ry, rz):
    """Z-Y-X intrinsic: first rotate rz about Z, then ry about Y, then rx about X."""
    cx, sx = np.cos(np.radians(rx)), np.sin(np.radians(rx))
    cy, sy = np.cos(np.radians(ry)), np.sin(np.radians(ry))
    cz, sz = np.cos(np.radians(rz)), np.sin(np.radians(rz))
    # rotation matrices (row-vector convention: applied as right-multiply)
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return Rz @ Ry @ Rx


def _marker_world(entry):
    """Parse one marker entry dict, return (p, R, error_mm)."""
    for key in ("x", "y", "z", "measurement_error_mm"):
        if key not in entry:
            raise ValueError("missing field %r" % key)
    p = np.array([float(entry["x"]), float(entry["y"]), float(entry["z"])],
                 dtype=np.float64)
    error_mm = float(entry["measurement_error_mm"])
    if "R" in entry:
        R = np.asarray(entry["R"], dtype=np.float64)
        if R.shape != (3, 3):
            raise ValueError("R shape must be (3,3), got %s" % (R.shape,))
    else:
        R = _euler_deg_to_R(
            float(entry.get("rx_deg", 0)),
            float(entry.get("ry_deg", 0)),
            float(entry.get("rz_deg", 0)),
        )
    return p, R, error_mm


def load_markers(path, warn_threshold_mm=20.0, min_count=4):
    """Load marker world-poses from *path*.

    Returns dict[int, {'p': (3,), 'R': (3,3), 'error_mm': float}].
    Emits warnings to stdout on suspicious data but does not abort.
    """
    with open(path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    out = {}
    warnings = []
    for k, v in raw.items():
        try:
            mid = int(k)
        except (TypeError, ValueError):
            continue              # allow note/comment keys
        p, R, err = _marker_world(v)
        if err > warn_threshold_mm:
            warnings.append(
                "marker %d error_mm %.1f > %.1f warning threshold" %
                (mid, err, warn_threshold_mm))
        out[mid] = {"p": p, "R": R, "error_mm": err}
    if len(out) < min_count:
        warnings.append("only %d markers; recommend at least %d"
                        % (len(out), min_count))
    for w in warnings:
        print("WARNING [load_markers]:", w)
    return out