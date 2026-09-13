"""Indoor-GPS live/video localisation: detect markers, solve pose, fuse.

Pipeline for one frame:
  1. histogram-equalise the ESP32 MJPEG frame (required for detection),
  2. detectMarkers (with cornerSubPix) -- DICT_4X4_50,
  3. for every detected marker that is in marker_positions.json, solve the
     marker->camera rigid transform and derive the camera ABSOLUTE position
     (marker_loc.camera_abs_position),
  4. fuse the per-marker camera positions with a per-axis median (robust to a
     single marker whose planar-P4P root flipped, see obs #0015), and report
     the number of observations and the spread as quality flags.

The marker table is loaded via marker_positions.load_markers.

`--self-test` renders a synthetic ESP32-like scene: two wall markers at known
world poses and a camera walking a straight line with a small yaw, then runs
the exact same processing core and compares the fused trajectory to the known
ground truth.
"""
import argparse
import csv
import os

import cv2
import numpy as np

from marker_loc import (estimate_marker_poses, IMG_W, IMG_H,
                        camera_abs_position, load_calibration)
from marker_positions import load_markers
from video_source import create_source


def _make_detector():
    d = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    det = cv2.aruco.ArucoDetector(d, cv2.aruco.DetectorParameters())
    p = det.getDetectorParameters()
    p.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    p.cornerRefinementWinSize = 5
    det.setDetectorParameters(p)
    return det


DETECTOR = None


def process_frame(im, K, dist, table, marker_m):
    """Detect + pose + fuse for one image (BGR or gray).

    Returns dict with keys: ids, obs (list of (id, pos, rms_px, n_obs)),
    fused ((3,) or None), spread (per-axis median abs. dev in mm) and
    marker_ids.
    """
    global DETECTOR
    if DETECTOR is None:
        DETECTOR = _make_detector()
    if im.ndim == 3:
        g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    else:
        g = im
    eq = cv2.equalizeHist(g)
    corners, ids, _ = DETECTOR.detectMarkers(eq)
    obs = []
    if ids is not None:
        for mid, c in zip(ids.ravel(), corners):
            mid = int(mid)
            if mid not in table:
                continue
            poses = estimate_marker_poses([c], np.array([[mid]]), marker_m,
                                          K, dist)
            if mid in poses:
                pos = camera_abs_position(poses[mid]["rvec"],
                                          poses[mid]["tvec"],
                                          table[mid]["p"], table[mid]["R"])
                obs.append((mid, pos.reshape(3), poses[mid]["rms_px"],
                            poses[mid]["gap_px"], poses[mid]["conditioned"]))
    fused = spread = None
    n_amb = 0
    if obs:
        arr = np.array([o[1] for o in obs], np.float64)
        fused = np.median(arr, axis=0)
        spread = np.median(np.abs(arr - fused), axis=0) * 1000.0  # mm
        n_amb = sum(0 if o[4] else 1 for o in obs)
    return {"ids": [o[0] for o in obs], "obs": obs,
            "fused": fused, "spread": spread,
            "n_obs": len(obs), "n_ambiguous": n_amb}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--video", help="recorded .avi file (file source)")
    ap.add_argument("--stream", help="ESP32 MJPEG URL, e.g. "
                    "http://192.168.4.1:81/stream")
    ap.add_argument("--calib", default=r"D:\Things\vo\calibration_esp32_qvga.npz")
    ap.add_argument("--markers", default=r"D:\Things\vo\marker_positions.json")
    ap.add_argument("--marker-m", type=float, default=0.15,
                    help="printed marker edge length in metres (measured)")
    ap.add_argument("--out", default=r"D:\Things\vo\indoor_gps_traj.csv")
    ap.add_argument("--every", type=int, default=1, help="process every Nth frame")
    ap.add_argument("--max-frames", type=int, default=0)
    ap.add_argument("--save-debug", help="dir for annotated frames")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        raise SystemExit(_selftest())

    if bool(args.video) + bool(args.stream) <= 0:
        print("need --video or --stream (or --self-test)")
        return
    if args.stream:
        src = create_source("esp32", url=args.stream)
    else:
        src = create_source("file", path=args.video)
    K, dist = load_calibration(args.calib)
    table = load_markers(args.markers)
    print("marker table: %s" % sorted(table.keys()))

    with open(args.out, "w", newline="") as fh:
        wr = csv.writer(fh)
        wr.writerow(["frame", "x", "y", "z", "n_obs", "n_ambiguous",
                     "spread_x_mm", "spread_y_mm", "spread_z_mm",
                     "conditioned",
                     "marker_ids"])
        i = 0
        while True:
            ok, im = src.read()
            if not ok:
                break
            if args.every > 1 and i % args.every != 0:
                i += 1
                continue
            r = process_frame(im, K, dist, table, args.marker_m)
            ids_txt = "".join(str(x) for x in r["ids"]) or ""
            row = [i]
            if r["fused"] is not None:
                row += list(np.round(r["fused"], 6))
                row += [r["n_obs"], r["n_ambiguous"]]
                row += list(np.round(r["spread"], 3))
                row += ["1" if r["n_ambiguous"] == 0 else "0"]
            else:
                row += ["", "", "", "", 0, 0, "", "", "", ""]
            row += [ids_txt]
            wr.writerow(row)
            if args.save_debug and r["ids"]:
                im_d = im.copy()
                cv2.putText(im_d, ids_txt, (8, 16),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 0), 1)
                cv2.imwrite(os.path.join(args.save_debug, "f%05d.jpg" % i),
                            im_d)
            i += 1
            if args.max_frames and i >= args.max_frames:
                break
    src.release()
    print("wrote %s" % args.out)


# ---------------- synthetic self-test ----------------

def _render_scene(marker_imgs, uvs, gray_bg=180):
    bg = np.full((IMG_H, IMG_W), gray_bg, np.uint8)
    for img, uv in zip(marker_imgs, uvs):
        sp = img.shape[0]
        src = np.array([[0, 0], [sp, 0], [sp, sp], [0, sp]], dtype=np.float32)
        M = cv2.getPerspectiveTransform(src, uv.astype(np.float32))
        mask = np.full((sp, sp), 255, np.uint8)
        warped = cv2.warpPerspective(img, M, (IMG_W, IMG_H),
                                     flags=cv2.INTER_LINEAR)
        mask_w = cv2.warpPerspective(mask, M, (IMG_W, IMG_H),
                                     flags=cv2.INTER_LINEAR) > 127
        bg[mask_w] = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)[mask_w]
    ok, buf = cv2.imencode(".jpg", bg, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return cv2.imdecode(buf, cv2.IMREAD_GRAYSCALE) if ok else bg


def _selftest():
    d = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    marker_m = 0.15
    K = np.array([[282.5, 0, 160], [0, 290.6, 120], [0, 0, 1]], np.float64)
    dist = np.array([-0.015, 0.035, -0.016, -0.007, 0.26])

    # two wall markers at known world poses (faces +Z), ~0.30 m apart, roughly at
    # the camera's height.  Both are within the QVGA FOV for the whole short
    # walk, so the multi-marker fusion path is exercised every frame.
    table = {
        1: {"p": np.array([0.0, 0.0, 1.2]), "R": np.eye(3), "error_mm": 0},
        2: {"p": np.array([0.30, 0.0, 1.15]), "R": np.eye(3), "error_mm": 0},
    }
    rng = np.random.default_rng(3)
    imgs = {m: cv2.cvtColor(cv2.aruco.generateImageMarker(d, m, 90),
                            cv2.COLOR_GRAY2BGR) for m in (1, 2)}
    yaw = np.deg2rad(8.0)
    R_y = np.array([[np.cos(yaw), 0, np.sin(yaw)],
                    [0, 1, 0],
                    [-np.sin(yaw), 0, np.cos(yaw)]], np.float64)
    R_cam = R_y @ np.diag([1.0, -1.0, -1.0])
    obj = np.array([[-marker_m / 2, marker_m / 2, 0],
                    [marker_m / 2, marker_m / 2, 0],
                    [marker_m / 2, -marker_m / 2, 0],
                    [-marker_m / 2, -marker_m / 2, 0]], np.float64)

    def proj(mid, p_c):
        tv = R_cam.T @ (table[mid]["p"] - p_c).reshape(3, 1)
        return tv, cv2.projectPoints(obj, R_cam.T, tv, K, dist)[0].reshape(4, 2)

    # obs #0016b: scene-geometry preflight BEFORE any detection/fusion assert.
    # Markers off-FOV or behind the camera masquerade as "detection failed".
    margin = 4
    for t in range(6):
        p_c = np.array([0.17 + 0.02 * t, -0.05, 1.70])
        for mid in (1, 2):
            tv, uv = proj(mid, p_c)
            assert float(tv[2]) * 1000.0 > 50.0, \
                "marker %d at frame %d is behind/near camera (z=%.0f mm)" \
                % (mid, t, float(tv[2]) * 1000.0)
            x = uv[:, 0]; y = uv[:, 1]
            assert (x >= margin).all() and (x <= IMG_W - 1 - margin).all(), \
                "marker %d at frame %d outside horizontal frame" % (mid, t)
            assert (y >= margin).all() and (y <= IMG_H - 1 - margin).all(), \
                "marker %d at frame %d outside vertical frame" % (mid, t)
    print("scene preflight OK: markers in-frame, in front of camera, all 6 poses")

    errs, seen, seen2 = [], 0, 0
    N = 6
    for t in range(N):
        p_c = np.array([0.17 + 0.02 * t, -0.05, 1.70])
        _, uv1 = proj(1, p_c)
        _, uv2 = proj(2, p_c)
        frame = _render_scene([imgs[1], imgs[2]], [uv1, uv2])
        r = process_frame(frame, K, dist, table, marker_m)
        gt = p_c
        if r["fused"] is not None:
            err = float(np.linalg.norm(r["fused"] - gt) * 1000.0)
            errs.append(err)
            seen += 1
            if r["n_obs"] >= 2:
                seen2 += 1
            print("frame %d markers=%s fused=(%.3f %.3f %.3f) err=%.0f mm"
                  % (t, r["ids"], *(r["fused"]), err))
        else:
            print("frame %d markers=%s (no fusion)" % (t, r["ids"]))
    mean_err = float(np.mean(errs)) if errs else float("inf")
    print("fused frames %d/%d  (>=2 markers: %d)  mean pos err %.0f mm"
          % (seen, N, seen2, mean_err))
    assert seen / N >= 0.5, "coverage too low to exercise fusion"
    assert seen2 >= 4, "multi-marker fusion path never exercised"
    assert mean_err < 120.0, "fused mean error too high (%.0f mm)" % mean_err
    print("localise_video self-test OK")


if __name__ == "__main__":
    main()