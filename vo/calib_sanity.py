"""Quick sanity check for camera calibration .npz files.

Prints the intrinsic matrix, flags suspicious values (obs #0012 principal-
point swap), and compares fx/fy to expected ranges for the ESP32 QVGA/VGA
sensors.
"""
import argparse

import numpy as np


def check(npz_path, expect_w=320, expect_h=240):
    d = np.load(npz_path)
    K = np.asarray(d["camera_matrix"], dtype=np.float64)
    dist = np.asarray(d["dist_coeffs"], dtype=np.float64).ravel()
    fx, fy = K[0, 0], K[1, 1]
    cx, cy = K[0, 2], K[1, 2]
    rms = float(d.get("rms", -1))
    img = np.asarray(d.get("image_size", [-1, -1]), dtype=int)

    print("file   :", npz_path)
    print("stored image_size:", tuple(img), "  expect %dx%d" % (expect_w, expect_h))
    print("rms    :", rms)
    print("K:\n", np.array2string(K, precision=2))
    print("dist   :", np.array2string(dist, precision=5))
    print("fx=%6.1f  fy=%6.1f  cx=%6.1f  cy=%6.1f" % (fx, fy, cx, cy))
    warnings = []
    if cy < 0.3 * expect_h or cy > 0.7 * expect_h:
        warnings.append(
            "cy=%.1f is outside [%.0f, %.0f] for a %d-tall image "
            "(likely height/width swap in calibrateCamera imageSize)" %
            (cy, 0.3 * expect_h, 0.7 * expect_h, expect_h))
    if cx < 0.3 * expect_w or cx > 0.7 * expect_w:
        warnings.append(
            "cx=%.1f is outside [%.0f, %.0f] for a %d-wide image" %
            (cx, 0.3 * expect_w, 0.7 * expect_w, expect_w))
    if abs(fx - fy) / max(fx, fy) > 0.2:
        warnings.append("fx/fy mismatch (non-square pixels?): %.1f / %.1f"
                        % (fx, fy))
    for w in warnings:
        print("WARNING:", w)
    if not warnings:
        print("PASS: all checks OK")
    return 0 if not warnings else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("npz")
    ap.add_argument("--width", type=int, default=320)
    ap.add_argument("--height", type=int, default=240)
    a = ap.parse_args()
    raise SystemExit(check(a.npz, a.width, a.height))