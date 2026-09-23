"""Headless camera recalibration from an existing chessboard clip.

Re-derives K from a recorded video (e.g. seq_real_14.avi, which has the 5x4
board in view for 100+ frames while the rig slides past) with the FIXED
calibrateCamera imageSize convention -- so the principal-point swap bug
(cy=30.6, obs #0012) is not propagated into a new calibration.

Poses are sampled evenly across detected frames to keep tilt/parallax
diversity without needing a live GUI session.

Usage:
  python vo/recalibrate_from_frames.py --video vo/seq_real_14.avi \
      --pattern 5x4 --square 25 --samples 30 --out vo/calibration_esp32_qvga_v2.npz
"""
import argparse
import os

import cv2
import numpy as np

from video_source import create_source


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--video", required=True)
    ap.add_argument("--pattern", default="5x4")
    ap.add_argument("--square", type=float, default=25.0)
    ap.add_argument("--samples", type=int, default=30,
                    help="poses to collect (spread evenly over detections)")
    ap.add_argument("--out", default="calibration_esp32_qvga_v2.npz")
    ap.add_argument("--fix-pp", action="store_true",
                    help="fix principal point at image centre (stable when pose "
                         "diversity is low; prevents degenerate huge-focal K)")
    ap.add_argument("--force", action="store_true",
                    help="save even if calib_sanity flags the result")
    args = ap.parse_args()

    cols, rows = (int(x) for x in args.pattern.lower().split("x"))
    pattern_size = (cols, rows)
    obj_grid = np.zeros((cols * rows, 3), np.float32)
    obj_grid[:, :2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2) * args.square

    flags = (cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE)
    src = create_source("file", path=args.video)

    detected = []  # (frame_no, corners)
    frame_no = 0
    frame_size = None
    while True:
        ok, fr = src.read()
        if not ok or fr is None:
            break
        frame_size = fr.shape[1], fr.shape[0]
        g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
        ge = cv2.equalizeHist(g)
        found, corners = cv2.findChessboardCorners(ge, pattern_size, None, flags)
        if found:
            corners = cv2.cornerSubPix(
                g, corners, (5, 5), (-1, -1),
                (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01))
            detected.append((frame_no, corners))
        frame_no += 1
    src.release()
    print("detected board in %d frames" % len(detected))
    if len(detected) < 5:
        print("too few detections; cannot calibrate")
        raise SystemExit(1)

    # Phase 0 gate: the classic focal-distortion degeneracy (fx~900/k3=-1640
    # garbage that still fits a pose set with low RMS, obs #0018/#0019) comes
    # from a pose set with no rotational/parallax diversity. Measure the
    # diversity of the recorded poses BEFORE calibrating: board coverage of
    # image corners+center, board tilt (K-free, from projected pixel geometry),
    # and near/mid/far spread. Reject early so a degenerate clip can never
    # slip a physically-implausible K through the low-RMS door.
    _inset_w = frame_size[0] * 0.1
    _inset_h = frame_size[1] * 0.1
    _zones = {"TL": (_inset_w, _inset_h), "TR": (frame_size[0] - _inset_w, _inset_h),
              "BL": (_inset_w, frame_size[1] - _inset_h),
              "BR": (frame_size[0] - _inset_w, frame_size[1] - _inset_h),
              "C": (frame_size[0] / 2.0, frame_size[1] / 2.0)}
    # nominal intrinsics only for pose rotation estimation (tilt); rotation is
    # robust to focal error unlike tvec/z, so this stays K-free in practice.
    _nomK = np.array([[frame_size[0] / 2.0, 0, frame_size[0] / 2.0],
                      [0, frame_size[1] / 2.0, frame_size[1] / 2.0],
                      [0, 0, 1]], np.float64)
    _hit_zones = set()
    _max_tilt_deg = -1.0
    _spans = []
    for _fn, crn in detected:
        c = crn.reshape(-1, 2).astype(np.float64)
        cx, cy = float(c[:, 0].mean()), float(c[:, 1].mean())
        for zn, (zx, zy) in _zones.items():
            if abs(cx - zx) < frame_size[0] * 0.22 and abs(cy - zy) < frame_size[1] * 0.22:
                _hit_zones.add(zn)
        _spans.append(float(np.max(np.linalg.norm(c - c[0:1], axis=1))))
        oks, _rv, _tv = cv2.solvePnP(obj_grid, c.reshape(-1, 1, 2), _nomK, None,
                                     flags=cv2.SOLVEPNP_ITERATIVE)
        if oks:
            Rm, _ = cv2.Rodrigues(_rv)
            _nz = float(np.abs(Rm[2, 2]))  # cos of tilt vs optical axis
            _max_tilt_deg = max(_max_tilt_deg,
                                float(np.degrees(np.arccos(np.clip(_nz, 0, 1)))))
    _hit_zones = sorted(_hit_zones)
    _dist_ratio = max(_spans) / max(min(_spans), 1.0)

    problems = []
    if len(detected) < 25:
        problems.append("only %d detection frames (want >=25 samples)" % len(detected))
    missing = [z for z in ("TL", "TR", "BL", "BR", "C") if z not in _hit_zones]
    if missing:
        problems.append("board never occupies zones %s (want all 5: four "
                        "corners + centre)" % ",".join(missing))
    if _max_tilt_deg < 30.0:
        problems.append("max board tilt only %.1f deg (want >=30 deg, ideally "
                        "+/-30-45)" % max(_max_tilt_deg, 0.0))
    if _dist_ratio < 1.5:
        problems.append("near/far pixel-size spread %.2fx (want >=1.5x for "
                        "near/mid/far distance coverage)" % _dist_ratio)
    if problems:
        print("POSE-DIVERSITY GATE REJECTED:")
        for p in problems:
            print("  - " + p)
        print("  -> recording lacks pose diversity; the resulting K would fall "
              "into the focal-distortion degeneracy. Re-shoot with board in "
              "all corners + centre, +/-30-45 deg tilt, near/mid/far distances.")
        raise SystemExit(3)
    print("pose-diversity gate PASSED (zones=%s, max tilt=%.1f deg, "
          "near/far spread=%.2fx, %d frames)"
          % (",".join(_hit_zones), _max_tilt_deg, _dist_ratio, len(detected)))
    # keep a pose evenly spread over the detection timeline for diversity
    idxs = np.linspace(0, len(detected) - 1, min(args.samples,
                                                 len(detected))).astype(int)
    idxs = np.unique(idxs)
    obj_points = [obj_grid for _ in idxs]
    img_points = [detected[i][1] for i in idxs]
    frame_nos = [detected[i][0] for i in idxs]
    print("kept %d poses at frames %s" % (len(idxs), frame_nos))

    calib_flags = cv2.CALIB_FIX_PRINCIPAL_POINT if args.fix_pp else None
    rms, K, dist, _, _ = cv2.calibrateCamera(
        obj_points, img_points, frame_size, None, None, flags=calib_flags)

    print("calibration RMS (pixels, lower is better): %.4f" % rms)
    print("camera matrix:\n%s" % np.array2string(K, precision=4))
    print("dist: %s" % np.round(dist.ravel(), 6))

    np.savez(args.out, camera_matrix=K, dist_coeffs=dist, rms=rms,
             image_size=np.array(frame_size),
             pattern=np.array(pattern_size),
             square=np.array([args.square]),
             source=args.video)
    print("saved to %s (frame_size %dx%d)" % (args.out, *frame_size))

    if args.force:
        print("--force: skipping calib_sanity gate")
        return
    from calib_sanity import check
    rc = check(args.out)
    if rc != 0:
        os.remove(args.out)
        print("REJECTED by calib_sanity (implausible K); file removed. "
              "This pose set likely lacks rotational diversity -- use a "
              "dedicated multi-orientation chessboard shoot instead, or "
              "--force to keep it anyway.")
        raise SystemExit(2)


if __name__ == "__main__":
    main()