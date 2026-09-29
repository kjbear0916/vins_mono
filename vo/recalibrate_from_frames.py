"""Headless camera recalibration from an existing chessboard clip.

Re-derives K from a recorded video, using the SAME corner path and SAME
requirements as the live guided tool (vo/calibrate_guided.py):

  * detections go through find_board() -- findChessboardCornersSB only, with
    the classic detector relegated to diagnostics exactly as in live mode
    (the classic corners are ~5 px out and collapse the solve: RMS 3.3,
    fx 77 against a truth of 474);
  * corners are canonicalised (canonical_corners, a cols x rows lattice
    quantise that refuses any frame that does not fit);
  * acceptance runs classify_detection + REQCollector -- the same bucket
    keys, NEAR/MID/FAR depth bins, tilt>=N degrees, edge-fill, all nine 3x3
    cells, sample count.

A clip that cannot satisfy the REQ checklist prints MISSING and exits,
exactly like a live session that never turned the panel green.

Usage:
  python vo/recalibrate_from_frames.py --video vo/seq_real_14.avi \
      --pattern 5x4 --square 25 --samples 30 --out vo/calibration_esp32_qvga_v2.npz
"""
import argparse
import os

import cv2
import numpy as np

from calibrate_guided import (F_H, F_W, classify_detection, find_board,
                              final_gates, REQCollector)
from video_source import create_source


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--video", required=True)
    ap.add_argument("--pattern", default="5x4")
    ap.add_argument("--square", type=float, default=25.0)
    ap.add_argument("--samples", type=int, default=30,
                    help="poses to collect before the REQ panel turns green")
    ap.add_argument("--tilt-min", type=float, default=15.0,
                    help="degrees off fronto-parallel for a tilted pose")
    ap.add_argument("--tilt-count", type=int, default=2,
                    help="how many tilted poses are required")
    ap.add_argument("--ppm-min", type=float, default=8.0)
    ap.add_argument("--ppm-max", type=float, default=60.0)
    ap.add_argument("--out", default="calibration_esp32_qvga_v2.npz")
    ap.add_argument("--fix-pp", action="store_true",
                    help="fix principal point at image centre (stable when pose "
                         "diversity is low; prevents degenerate huge-focal K)")
    ap.add_argument("--force", action="store_true",
                    help="save even if calib_sanity flags the result")
    args = ap.parse_args()

    cols, rows = (int(x) for x in args.pattern.lower().split("x"))
    pattern = (cols, rows)
    obj = np.zeros((cols * rows, 3), np.float32)
    obj[:, :2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2) * args.square

    src = create_source("file", path=args.video)
    collector = REQCollector(obj, args.samples, args.tilt_count,
                             args.tilt_min)
    frame_no = 0
    frame_size = None
    frame_stats = {"sb-detect": 0, "lattice": 0, "off-frame": 0,
                   "bad-size": 0, "dup": 0}
    while True:
        ok, fr = src.read()
        if not ok or fr is None:
            break
        frame_size = fr.shape[1], fr.shape[0]
        if frame_size != (F_W, F_H):
            print("offline path expects a QVGA (320x240) clip, got %dx%d; "
                  "resize or use the live tool for other resolutions"
                  % frame_size)
            raise SystemExit(1)
        found, cc, how = find_board(
            cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY), pattern)
        if not found or not how.startswith("sb"):
            frame_no += 1
            continue
        frame_stats["sb-detect"] += 1
        d = classify_detection(cc, pattern, args.square,
                               args.ppm_min, args.ppm_max)
        reject = d.get("reject")
        if reject:
            frame_stats[reject] = frame_stats.get(reject, 0) + 1
            frame_no += 1
            continue
        if not collector.add(d):
            frame_stats["dup"] += 1
        frame_no += 1
        if collector.done():
            break
    src.release()

    print("detected SB board in %d/%d frames (lattice-rejected %d, "
          "off-frame %d, bad-size %d, dup %d)"
          % (frame_stats["sb-detect"], frame_no, frame_stats["lattice"],
             frame_stats["off-frame"], frame_stats["bad-size"],
             frame_stats["dup"]))
    if frame_size is None:
        print("no readable frames in", args.video)
        raise SystemExit(1)

    missing = collector.missing()
    if missing:
        print("REQ PANEL NOT SATISFIED: %s" % "; ".join(missing))
        print("  -> this clip cannot feed the same gates the live tool uses; "
              "re-record: board to all 4 edges at near distance, +/-20-45 deg "
              "tilt, near/mid/far, board across all 9 frame zones.")
        raise SystemExit(3)

    # one evenly-spread pose per bucket is already guaranteed by the collector
    # (first occurrence per bucket); order does not matter to the solve
    obj_p = np.array([v[0] for v in collector.samples.values()])
    img_p = np.array([v[1] for v in collector.samples.values()], np.float32)
    calib_flags = cv2.CALIB_FIX_PRINCIPAL_POINT if args.fix_pp else None
    rms, K, dist, _, _ = cv2.calibrateCamera(
        obj_p, img_p, (F_W, F_H), None, None, flags=calib_flags)

    print("\nunique poses=%d  RMS(pix)=%.4f  [%s]"
          % (len(collector.samples), rms,
             " came from %dx%d clip" % frame_size))
    print("K =\n%s" % K)
    print("dist = %s" % np.round(dist.ravel(), 6))

    gates, aniso, hfov = final_gates(K, rms)
    for name, ok in gates:
        print("  [%s] %s" % ("PASS" if ok else "FAIL", name))
    if not 0.90 <= aniso <= 1.10:
        print("  -> board cells are not square on screen/paper: a cell measures "
              "%.2fx wider than tall.\n     Print the board, or use a viewer "
              "that letterboxes instead of stretching to fill." % aniso)
    if not all(ok for _, ok in gates):
        print("RESULT: FAIL -- redo D")
        raise SystemExit(2)

    np.savez(args.out, camera_matrix=K, dist_coeffs=dist, rms=rms,
             image_size=np.array(frame_size),
             pattern=np.array(pattern), square=np.array([args.square]),
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
              "Re-record with a dedicated multi-orientation chessboard shoot, "
              "or --force to keep it anyway.")
        raise SystemExit(2)
    print("\n====== OK PASS ======")


if __name__ == "__main__":
    main()