# -*- coding: utf-8 -*-
"""Generate a pose set that can actually satisfy calibrate_guided's REQ panel.

gen_synth_calib_shoot's pose list is tuned for the offline recalibration clip
and passes its translation straight in as (pu, pv, z) without inverting the
projection, so the board never lands where it was aimed. Driven through
calibrate_guided it yielded 8 accepted poses / 4 unique buckets, with NEAR,
FAR, edge-fill and tilt>=2 all unreachable -- a dry run against it times out
with the panel still red.

This module searches poses against the tool's own gates (depth_label,
board_pose, corner_margin, missing_list) and keeps one representative per
bucket key (depth, in-plane angle, tilt, 3x3 cell), in priority order:

  1. one pose per 3x3 cell, at the depth that fits that cell best
  2. the hard requirements: NEAR bucket, edge-fill, tilt>=2, FAR bucket
  3. fill up to --samples unique buckets, spreading across depths

  python vo/gen_guided_pose_set.py --check        # gates satisfiable?
  python vo/gen_guided_pose_set.py --out poses.json
"""
import argparse
import json
import os

import cv2
import numpy as np

import calibrate_guided as cg
import gen_synth_calib_shoot as gs

PATTERN = (5, 4)
CELL_N = 3
CELL_W, CELL_H = gs.W / CELL_N, gs.H / CELL_N


def rot(pitch_deg, yaw_deg, roll_deg):
    a, b, c = (np.radians(pitch_deg), np.radians(yaw_deg),
               np.radians(roll_deg))
    Rx = np.array([[1, 0, 0], [0, np.cos(a), -np.sin(a)],
                   [0, np.sin(a), np.cos(a)]])
    Ry = np.array([[np.cos(b), 0, np.sin(b)], [0, 1, 0],
                   [-np.sin(b), 0, np.cos(b)]])
    Rz = np.array([[np.cos(c), -np.sin(c), 0], [np.sin(c), np.cos(c), 0],
                   [0, 0, 1]])
    return Rx @ Ry @ Rz


def project_centre(z, pu, pv, K):
    """Camera-frame translation that puts the board centre at pixel (pu,pv)."""
    fx, fy, cx, cy = K[0, 0], K[1, 1], K[0, 2], K[1, 2]
    return np.array([(pu - cx) * z / fx, (pv - cy) * z / fy, float(z)])


def render(gray, K, dist, local, R, t):
    return gs.render_board(gray, K, dist, local, R, t)


def wire_roundtrip(gray, noise=0.0, rng=None, quality=90):
    """Send the frame through the same path the live loop sees it.

    calibrate_guided decodes MJPEG JPEGs to BGR and converts back to gray, and
    the frames that arrive there already carry sensor noise, so corners (and
    therefore ppm) shift against a clean render. Poses accepted on the clean
    image but rejected on the wire -- the FAR poses sitting at ppm 7.1 against
    a floor of 8 -- stall the panel with no reachable fix, so gate evaluation
    has to run on what the loop will actually read.
    """
    src = gray
    if noise > 0.0:
        src = np.clip(gray.astype(np.float32) +
                      (rng or np.random).normal(0.0, noise, gray.shape),
                      0, 255).astype(np.uint8)
    bgr = cv2.cvtColor(src, cv2.COLOR_GRAY2BGR)
    ok, buf = cv2.imencode(".jpg", bgr, [int(cv2.IMWRITE_JPEG_QUALITY),
                                          quality])
    if not ok:
        return gray
    img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


# Gate margins. The server redraws the same pose with fresh noise on every
# cycle, so a pose that only just clears a threshold fails on some repeats and
# the panel never closes. Keep every gate this far inside its own limit.
PPM_SAFE = 1.15


def evaluate(gray, K, dist, local, R, t, square, edge_px, tilt_min, ppm_lo,
             ppm_hi, wire=True, noise=0.0, rng=None):
    """Render one pose and report whether the tool would accept it.

    Returns (bucket, depth, tilt_deg, margin, ppm) or None when the pose is
    unusable (off-frame render, detection failure, or a rejected gate).
    """
    if not render(gray, K, dist, local, R, t):
        return None
    work = wire_roundtrip(gray, noise, rng) if wire else gray
    found, cc, how = cg.find_board(work, PATTERN)
    if not found or not how.startswith("sb"):
        return None
    # no cornerSubPix here: SB refines to subpixel internally, and re-running
    # the classic refinement over its corners drifts them by about 5 px
    cc = cg.canonical_corners(cc, PATTERN, square)
    if cc is None:
        return None
    z_cm, ang, tilt_deg, cell = cg.board_pose(cc, PATTERN, square)
    xys = cc.reshape(-1, 2)
    mn, mx = xys.min(axis=0), xys.max(axis=0)
    in_frame = mn[0] >= 2 and mx[0] <= 317 and mn[1] >= 2 and mx[1] <= 237
    if not in_frame:
        return None
    ppm = cg.FX_GUESS * square / (z_cm * 10.0)
    if not (ppm_lo * PPM_SAFE <= ppm <= ppm_hi):
        return None
    depth = cg.depth_label(mn, mx, PATTERN)
    return (cg.bucket_for(depth, ang, tilt_deg, cell), depth, tilt_deg,
            cg.corner_margin(xys), ppm)


def build(K, dist, square, edge_px, tilt_min, ppm_lo, ppm_hi, samples,
          verbose=False, noise=0.0):
    local = gs.board_corners_local()
    gray = np.zeros((gs.H, gs.W), np.uint8)
    kept = {}
    order = []
    rng = np.random.default_rng(12345)

    def try_pose(z, pu, pv, pitch, yaw, roll):
        R = rot(pitch, yaw, roll)
        t = project_centre(z, pu, pv, K)
        got = evaluate(gray, K, dist, local, R, t, square, edge_px, tilt_min,
                       ppm_lo, ppm_hi, noise=noise, rng=rng)
        if got is None:
            return None
        bucket, depth, tilt_deg, margin, ppm = got
        if bucket in kept:
            return None
        kept[bucket] = dict(z=z, pu=pu, pv=pv, pitch=pitch, yaw=yaw,
                            roll=roll, depth=depth, tilt_deg=tilt_deg,
                            margin=margin, ppm=ppm, cell=bucket[3])
        order.append(bucket)
        return kept[bucket]

    depths = {"NEAR": 340.0, "MID": 560.0, "FAR": 1000.0}
    tilts = [0, 12, 20, 28, 36, 44]
    rolls = [0, 20, 45, 70, 110, 150]

    # 1. every 3x3 cell, at a depth where the board fits that cell
    for r in range(CELL_N):
        for c in range(CELL_N):
            pu, pv = (c + 0.5) * CELL_W, (r + 0.5) * CELL_H
            for zn, z in depths.items():
                for pitch in tilts:
                    if try_pose(z, pu, pv, pitch, 0, 0):
                        break
    # 2. the hard requirements
    for zn, z in (("NEAR", 330.0), ("NEAR", 300.0), ("FAR", 1050.0),
                  ("FAR", 1150.0)):
        for pv, pu in ((CELL_H * 0.5, CELL_W * 0.5), (60.0, 45.0),
                       (185.0, 275.0), (40.0, 160.0), (200.0, 160.0)):
            for pitch in (36, 44, 28, 20):
                for roll in (0, 20, 45):
                    if try_pose(z, pu, pv, pitch, 0, roll):
                        break
    # 3. fill the sample count, spreading across depths and cells
    if len(order) < samples:
        for zn, z in depths.items():
            for r in range(CELL_N):
                for c in range(CELL_N):
                    pu, pv = (c + 0.5) * CELL_W, (r + 0.5) * CELL_H
                    for pitch in tilts:
                        for roll in rolls:
                            if len(order) >= samples:
                                break
                            try_pose(z, pu, pv, pitch, 0, roll)
    if verbose:
        for b in order:
            p = kept[b]
            print("  %-5s z=%6.0f ppm=%4.1f tilt=%3.0fdeg margin=%5.1f cell=%s"
                  % (p["depth"], p["z"], p["ppm"], p["tilt_deg"], p["margin"],
                     b[3]))
    return [kept[b] for b in order]


def check(poses):
    depth_bins = {"NEAR": False, "MID": False, "FAR": False}
    edge_near = False
    tilt_count = 0
    cells = set()
    for p in poses:
        depth_bins[p["depth"]] = True
        # the cell the operator's frame coverage is judged on is the one the
        # *detected* board centroid lands in, not the one the render was aimed
        # at: under a tilt the two part company, and check() was grading
        # coverage on the pose it asked for instead of the pose it got
        cells.add(p["cell"])
        if p["margin"] <= 24.0:
            edge_near = True
        if p["tilt_deg"] >= 15.0:
            tilt_count += 1
    miss = cg.missing_list(edge_near, tilt_count, 2, depth_bins,
                           {(c, r) for r in range(3) for c in range(3)
                            if (c, r) not in cells}, len(poses), 30)
    print("poses=%d  depth=%s  cells=%d/9  edge=%s  tilt=%d"
          % (len(poses), [k for k, v in depth_bins.items() if v],
             len(cells), edge_near, tilt_count))
    print("MISSING:", miss if miss else "none")
    return not miss


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fx", type=float, default=474.0)
    ap.add_argument("--cx", type=float, default=160.0)
    ap.add_argument("--cy", type=float, default=120.0)
    ap.add_argument("--k1", type=float, default=-0.18)
    ap.add_argument("--k2", type=float, default=0.05)
    ap.add_argument("--square", type=float, default=gs.SQ)
    ap.add_argument("--samples", type=int, default=30)
    ap.add_argument("--ppm-min", type=float, default=8.0)
    ap.add_argument("--ppm-max", type=float, default=60.0)
    ap.add_argument("--out", default="")
    ap.add_argument("--noise", type=float, default=gs.NOISE,
                    help="match the stream's sensor noise; 0 evaluates on a "
                         "clean render and can hand back poses the live loop "
                         "then rejects")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()
    K = np.array([[a.fx, 0, a.cx], [0, a.fx, a.cy], [0, 0, 1]], np.float64)
    dist = np.array([a.k1, a.k2, 0.0, 0.0, 0.0], np.float64)
    poses = build(K, dist, a.square, 24.0, 0.12, a.ppm_min, a.ppm_max,
                  a.samples, verbose=a.verbose, noise=a.noise)
    ok = check(poses)
    if a.out:
        with open(a.out, "w") as f:
            json.dump(poses, f, indent=1)
        print("wrote", a.out)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
