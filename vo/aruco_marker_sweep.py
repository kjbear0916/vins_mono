"""Synthetic detection-limit sweep for the ESP32 QVGA marker pipeline.

Whereas the printed-marker hardware test (aruco_detect_test.py) needs the
ESP32 + printed markers, this tool answers the same question earlier and
headlessly: at what apparent marker size (px) and camera-to-marker tilt does
DICT_4X4_50 detection stop being reliable on a 320x240 frame, when run through
the exact low-contrast pipeline used in production (grayscale + equalizeHist)?

It renders the marker with a pinhole projection (focal from
calibration_esp32_qvga.npz, aspect-corrected), tilts it like a wall-mounted
marker seen off-axis, drops it into a textured room-like background, JPEG-
compresses like the ESP32 feed, then reports detection rate + rejected
candidates per (size_px, tilt_deg).

The size_px axis doubles as a distance axis: with printed edge L, distance
d = fx * L / size_px. The summary table prints that mapping for L =
60/80/100/120 mm so the printed-marker test can be aimed at the reliable band.

Usage:
  python aruco_marker_sweep.py [--sizes 12,16,20,24,30,40,60,90,120]
"""
import argparse

import cv2
import numpy as np

CALIB = r"D:\Things\vo\calibration_esp32_qvga.npz"
W, H = 320, 240
DICT_ID = cv2.aruco.DICT_4X4_50


def make_scene(marker_bgr, side_px, tilt_deg, rng, fx, fy, cx, cy,
               clutter=True):
    d = 1.0
    half = d * side_px / (2.0 * fx)
    y_off = rng.uniform(-0.15, 0.35)
    corners3d = np.array([
        [-half, -half + y_off, d],
        [half, -half + y_off, d],
        [half, half + y_off, d],
        [-half, half + y_off, d],
    ], dtype=np.float64)
    tilt = np.radians(tilt_deg)
    cy_mat = np.cos(tilt)
    sy_mat = np.sin(tilt)
    R = np.array([
        [cy_mat, 0.0, sy_mat],
        [0.0, 1.0, 0.0],
        [-sy_mat, 0.0, cy_mat],
    ])
    center = np.array([0.0, y_off, d])
    cam = (R @ (corners3d - center).T).T + center
    u = fx * cam[:, 0] / cam[:, 2] + cx
    v = fy * cam[:, 1] / cam[:, 2] + cy
    dst = np.column_stack([u, v]).round().astype(np.float32)
    if not ((dst[:, 0] > 2).all() and (dst[:, 0] < W - 3).all()
            and (dst[:, 1] > 2).all() and (dst[:, 1] < H - 3).all()):
        return None
    src = np.array([[0, 0], [side_px, 0], [side_px, side_px], [0, side_px]],
                   dtype=np.float32)
    M = cv2.getPerspectiveTransform(src, dst)

    scene = rng.integers(80, 175, (H, W, 3), dtype=np.uint8)
    smooth = cv2.GaussianBlur(scene, (0, 0), 11)
    shade = rng.integers(-45, 45, (H, W, 3), dtype=np.int16)
    background = np.clip(smooth.astype(np.int16) + shade, 0, 255).astype(
        np.uint8)
    scene = background.copy()
    if clutter:
        for _ in range(rng.integers(1, 3)):
            bw, bh = rng.integers(25, 80), rng.integers(25, 80)
            bx, by = rng.integers(5, W - bw), rng.integers(5, H - bh)
            tint = int(rng.integers(90, 175))
            patch = np.full((bh, bw, 3), tint, np.uint8)
            patch = cv2.GaussianBlur(patch, (0, 0), 3)
            scene[by:by + bh, bx:bx + bw] = \
                cv2.addWeighted(scene[by:by + bh, bx:bx + bw], 0.5,
                                patch, 0.5, 0)

    if side_px > 6:
        warped = cv2.warpPerspective(marker_bgr, M, (W, H),
                                     flags=cv2.INTER_NEAREST)
        mask = np.clip(cv2.warpPerspective(
            np.full((side_px, side_px), 255, np.uint8), M, (W, H),
            borderValue=0, flags=cv2.INTER_NEAREST), 0, 255)
        gray_mark = (0.114 * warped[:, :, 0] + 0.587 * warped[:, :, 1]
                     + 0.299 * warped[:, :, 2]).astype(np.uint8)
        scene_g = (0.114 * scene[:, :, 0] + 0.587 * scene[:, :, 1]
                   + 0.299 * scene[:, :, 2]).astype(np.uint8)
        scene_g = np.where(mask > 127, gray_mark, scene_g)
        ok, buf = cv2.imencode(".jpg", scene_g, [cv2.IMWRITE_JPEG_QUALITY, 50])
        scene_g = cv2.imdecode(buf, cv2.IMREAD_GRAYSCALE) if ok else scene_g
        blurred = cv2.GaussianBlur(scene_g, (0, 0), 0.5)
        return blurred
    return scene[:, :, 0]


def run(sizes, tilts, n_per):
    d = np.load(CALIB)
    K = d["camera_matrix"]
    fx, fy = float(K[0, 0]), float(K[1, 1])
    cx, cy = W / 2.0, H / 2.0
    ad = cv2.aruco.getPredefinedDictionary(DICT_ID)
    det = cv2.aruco.ArucoDetector(ad, cv2.aruco.DetectorParameters())

    print("focal py from calibration: fx=%.1f (320-wide), using optical "
          "centre (%d,%d)" % (fx, W // 2, H // 2))
    print("synthetic floor; excludes hand-held motion blur and lens blur, "
          "so treat as the OPTIMISTIC bound")
    print("%-9s %-6s %-12s %-12s %-10s %-10s" %
          ("size_px", "tilt", "clean%", "clutter%", "cl.rej/fr",
           "clutter.rej/fr"))
    for side_px in sizes:
        marker_bgr = cv2.cvtColor(
            cv2.aruco.generateImageMarker(ad, 3, side_px),
            cv2.COLOR_GRAY2BGR)
        for tilt in tilts:
            stats = {"clean": [0, 0.0], "clutter": [0, 0.0]}
            rng = np.random.default_rng(1000 + side_px * 17 + tilt)
            for _ in range(n_per):
                for name, clutter in (("clean", False), ("clutter", True)):
                    scene = None
                    for _ in range(60):
                        scene = make_scene(marker_bgr, side_px, tilt,
                                           rng, fx, fy, cx, cy,
                                           clutter=clutter)
                        if scene is not None:
                            break
                    if scene is None:
                        continue
                    scene = cv2.equalizeHist(scene)
                    corners, ids, rejected = det.detectMarkers(scene)
                    stats[name][1] += len(rejected)
                    if ids is not None and any(int(i) == 3
                                               for i in ids.ravel()):
                        stats[name][0] += 1
            clean_rate = 100.0 * stats["clean"][0] / n_per
            clut_rate = 100.0 * stats["clutter"][0] / n_per
            bands = []
            for rate in (clean_rate, clut_rate):
                bands.append("RELIABLE" if rate >= 90 else (
                    "MARGINAL" if rate >= 40 else "UNRELIABLE"))
            print("%-9d %-6d %-12.0f %-12.0f %-10.2f %-10.2f   %s/%s" %
                  (side_px, tilt, clean_rate, clut_rate,
                   stats["clean"][1] / n_per, stats["clutter"][1] / n_per,
                   bands[0], bands[1]))

    print("\ndistance (m) where detection degrades, by printed edge L; "
          "d = fx*L/size_px at the %d-wide QVGA image:" % W)
    print("%-9s %s" % ("size_px", " ".join("L=%dmm" % L for L in
                                           (60, 80, 100, 120))))
    for side_px in sizes:
        row = " ".join("%.2f" % (fx * L / 1000.0 / side_px)
                       for L in (60, 80, 100, 120))
        print("%-9d %s" % (side_px, row))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", default="12,16,20,24,30,40,60,90,120")
    ap.add_argument("--tilts", default="0,15,30,45")
    ap.add_argument("--n-per", type=int, default=30)
    a = ap.parse_args()
    sizes = [int(s) for s in a.sizes.split(",")]
    tilts = [int(t) for t in a.tilts.split(",")]
    run(sizes, tilts, a.n_per)