"""Synthetic POSITIVE-CONTROL chessboard calibration clip.

Renders a 5x4 chessboard (25 mm squares) through a KNOWN camera matrix with
a KNOWN lens distortion, over a pose set that deliberately satisfies the
pose-diversity gate in recalibrate_from_frames.py:

  * board centre visits all 5 zones (TL/TR/BL/BR/C)
  * board is tilted +/-30-45 deg out of the image plane
  * near/mid/far depth coverage (>=1.5x pixel-size spread)

The clip is then used as a no-hardware regression test for the offline
calibration pipeline: recalibrate_from_frames.py must recover K and dist
close to the ground truth used to render it. This mirrors gen_synth_seq.py's
positive-control role for the VO validation gate.

Usage:
  python gen_synth_calib_shoot.py --out vo/synth_calib_gt.avi --fx 474 \
      --k1 -0.18 --seed 7
"""
import argparse
import os

import cv2
import numpy as np

FPS = 16.0
W, H = 320, 240
SQ = 25.0          # mm, target square size for the calibration pattern
PATTERN = (5, 4)   # inner corners (cols, rows) -> 6x5 cells
NOISE = 3.0


def distort_pts(u, v, fx, fy, cx, cy, k):
    x = (u - cx) / fx
    y = (v - cy) / fy
    r2 = x * x + y * y
    k1, k2, p1, p2, k3 = (float(k[i]) if i < len(k) else 0.0
                          for i in range(5))
    r4 = r2 * r2
    r6 = r4 * r2
    rad = 1.0 + k1 * r2 + k2 * r4 + k3 * r6
    ud = x * rad + 2.0 * p1 * x * y + p2 * (r2 + 2.0 * x * x)
    vd = y * rad + p1 * (r2 + 2.0 * y * y) + 2.0 * p2 * x * y
    return fx * ud + cx, fy * vd + cy


def render_board(gray, K, dist, corners3d, R_bc, t_bc):
    """Draw the board cells onto a 320x240 frame.

    corners3d: (cols+1)*(rows+1) cell corners in board-local (x,y,0).
    Board pose given by (R_bc, t_bc): X_c = R_bc @ X_local + t_bc.
    """
    fx, fy = K[0, 0], K[1, 1]
    cx, cy = K[0, 2], K[1, 2]
    X_c = (R_bc @ corners3d.T).T + t_bc.reshape(1, 3)
    if float(X_c[:, 2].min()) < 50.0:
        return False
    u = fx * X_c[:, 0] / X_c[:, 2] + cx
    v = fy * X_c[:, 1] / X_c[:, 2] + cy
    ud, vd = distort_pts(u, v, fx, fy, cx, cy, dist)
    if not bool((np.isfinite(ud) & np.isfinite(vd)).all()):
        return False
    if not (ud.min() >= -40 and ud.max() <= W + 40
            and vd.min() >= -40 and vd.max() <= H + 40):
        return False
    cols, rows = PATTERN
    n_sq_x, n_sq_y = cols + 1, rows + 1
    # white backing board
    pts = np.stack([ud, vd], axis=1).astype(np.int32)
    gray[:] = 235
    cv2.fillConvexPoly(gray, pts, 255)
    for j in range(n_sq_y):
        for i in range(n_sq_x):
            if (i + j) % 2 == 0:
                continue  # black squares only at (i+j) odd
            idx = np.array([j * (n_sq_x + 1) + i,
                            j * (n_sq_x + 1) + i + 1,
                            (j + 1) * (n_sq_x + 1) + i + 1,
                            (j + 1) * (n_sq_x + 1) + i])
            cv2.fillConvexPoly(gray, pts[idx], 25)
    return True


def board_corners_local():
    cols, rows = PATTERN          # internal corners (5,4)
    n_sq_x, n_sq_y = cols + 1, rows + 1   # squares: 6 wide x 5 tall
    pts = []
    for j in range(n_sq_y + 1):
        for i in range(n_sq_x + 1):
            pts.append(((i - n_sq_x / 2.0) * SQ, (j - n_sq_y / 2.0) * SQ, 0.0))
    return np.array(pts, np.float64)


def make_poses(rng):
    """Build a diverse pose list: aim pixels x depths x tilts.

    Near depth deliberately lets the outer corners reach near the image
    edge -- that radial coverage is what separates fx from distortion
    (obs: a pose set confined to the central ~150px leaves fx--dist
    unconstrained and calibrateCamera slips to fx~2000+)."""
    targets = {"TL": (56, 44), "TR": (264, 44), "C": (160, 120),
               "BL": (56, 196), "BR": (264, 196)}
    depths = [220.0, 600.0, 1400.0]      # mm near/mid/far
    tilts = [(-40, 0), (35, 0), (0, 33), (0, -38),
             (28, 28), (-30, -25), (20, -35), (-25, 30)]
    poses = []
    for z in depths:
        for zn, (pu, pv) in targets.items():
            for (ang_p, ang_y) in tilts:
                poses.append((z, pu, pv, ang_p, ang_y))
    rng.shuffle(poses)
    return poses


def pose6(p):
    """Normalise a pose entry to a 6-tuple (z, pu, pv, pitch, yaw, roll).

    Accepts the legacy 5-tuple from make_poses or a dict carrying the
    gen_guided_pose_set fields (z, pu, pv, pitch, yaw, optional roll).
    """
    if isinstance(p, dict):
        return (float(p["z"]), float(p["pu"]), float(p["pv"]),
                float(p["pitch"]), float(p["yaw"]), float(p.get("roll", 0)))
    roll = 0.0 if len(p) < 6 else float(p[5])
    return (float(p[0]), float(p[1]), float(p[2]), float(p[3]),
            float(p[4]), roll)


def guided_poses(a, Kt, dist_t):
    """Pose set that satisfies the REQ panel of calibrate_guided (tilt>=15deg
    x2, NEAR/MID/FAR, GRID 3x3, edge-filled) -- the same list the guided dry
    run uses. The legacy make_poses set does NOT satisfy those gates and the
    REQ-gated offline tool rejects it, so REQ-satisfying clips must be
    rendered from here.
    """
    import gen_guided_pose_set as gp
    poses = gp.build(Kt, dist_t, SQ, 24.0, 15.0, 8.0, 60.0, 30, noise=NOISE)
    return [pose6(p) for p in poses]


def render_clip(out, Kt, dist_t, poses, seed=7, noise=NOISE):
    """Render poses to an MJPG clip + write <out stem>_truth.npz.

    poses: iterable of 6-tuples (z, pu, pv, pitch, yaw, roll).  Bytes match
    the legacy main() path (same noise draw + 3x3 GaussianBlur), so the
    recalibration result is comparably clean.
    Returns the number of frames written.
    """
    rng = np.random.default_rng(seed)
    local = board_corners_local()
    fx, fy = Kt[0, 0], Kt[1, 1]
    cx, cy = Kt[0, 2], Kt[1, 2]
    writer = cv2.VideoWriter(out, cv2.VideoWriter_fourcc(*"MJPG"),
                             FPS, (W, H), False)
    rendered = 0
    for z, pu, pv, ang_p, ang_y, ang_r in (pose6(p) for p in poses):
        tx = (pu - cx) / fx * z
        ty = (pv - cy) / fy * z
        tz = z
        p, y, r = (np.radians(ang_p), np.radians(ang_y), np.radians(ang_r))
        cp, sp = np.cos(p), np.sin(p)
        cy_, sy_ = np.cos(y), np.sin(y)
        cr, sr = np.cos(r), np.sin(r)
        Rx = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]], np.float64)
        Ry = np.array([[cy_, 0, sy_], [0, 1, 0], [-sy_, 0, cy_]], np.float64)
        Rr = np.array([[cr, -sr, 0], [sr, cr, 0], [0, 0, 1]], np.float64)
        R_bc = Ry @ Rr @ Rx
        t_bc = np.array([tx, ty, tz], np.float64)

        gray = np.zeros((H, W), np.uint8)
        ok = render_board(gray, Kt, dist_t, local, R_bc, t_bc)
        if not ok:
            continue
        gray = np.clip(gray.astype(np.float32)
                       + rng.normal(0.0, noise, gray.shape), 0, 255).astype(np.uint8)
        cv2.GaussianBlur(gray, (3, 3), 0, gray)
        writer.write(gray)
        rendered += 1
    writer.release()
    np.savez(out.replace(".avi", "_truth.npz"), camera_matrix=Kt,
             dist_coeffs=dist_t)
    return rendered


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=r"D:\Things\vo\synth_calib_gt.avi")
    ap.add_argument("--fx", type=float, default=474.0)
    ap.add_argument("--fy", type=float, default=None)
    ap.add_argument("--cx", type=float, default=160.0)
    ap.add_argument("--cy", type=float, default=120.0)
    # radial distortion coefficients: (k1, k2, p1, p2, k3)
    ap.add_argument("--k1", type=float, default=-0.18)
    ap.add_argument("--k2", type=float, default=0.05)
    ap.add_argument("--p1", type=float, default=0.0)
    ap.add_argument("--p2", type=float, default=0.0)
    ap.add_argument("--k3", type=float, default=0.0)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--guided-poses", action="store_true",
                    help="render the calibrate_guided REQ-satisfying pose set "
                         "instead of the legacy make_poses set (required for "
                         "the REQ-gated offline tool)")
    ap.add_argument("--selftest", action="store_true",
                    help="run the recalibration closed-loop on the clip and "
                         "assert fx recovery within 5%")
    a = ap.parse_args()

    fy = a.fy or a.fx
    Kt = np.array([[a.fx, 0, a.cx], [0, fy, a.cy], [0, 0, 1]], np.float64)
    dist_t = np.array([a.k1, a.k2, a.p1, a.p2, a.k3], np.float64)

    if a.guided_poses:
        poses = guided_poses(a, Kt, dist_t)
    else:
        rng = np.random.default_rng(a.seed)
        poses = [pose6(p) for p in make_poses(rng)]

    rendered = render_clip(a.out, Kt, dist_t, poses, seed=a.seed)
    print("wrote %s (%d rendered poses)  truth fx=%.1f fy=%.1f cx=%.1f cy=%.1f"
          % (a.out, rendered, a.fx, fy, a.cx, a.cy))
    print("truth dist: %s" % np.array2string(dist_t, precision=5))

    if a.selftest:
        _check_recovery(a.out, Kt, dist_t, fy)


def _check_recovery(avi, Kt, dist_t, fy):
    """Closed loop: run recalibrate_from_frames on the clip we just wrote and
    assert the recovered K lands near the truth used to render it.  Raises
    SystemExit(1) if the pipeline cannot recover fx -- i.e. the pose set is
    degenerate even though the diversity gate passed."""
    import subprocess
    import sys
    import tempfile

    out = avi.replace(".avi", "_selftest.npz")
    r = subprocess.run(
        [sys.executable, os.path.join(os.path.dirname(__file__),
                                      "recalibrate_from_frames.py"),
         "--video", avi, "--pattern", "5x4", "--square", str(SQ),
         "--samples", "30", "--out", out],
        capture_output=True, text=True)
    if r.returncode != 0:
        _report("RECALIBRATE EXIT %d (gate rejected the clip?):\n%s\n%s"
                % (r.returncode, r.stdout, r.stderr))
        raise SystemExit(1)
    d = np.load(out)
    fx = float(d["camera_matrix"][0, 0])
    fxe = float(Kt[0, 0])
    if abs(fx - fxe) / fxe > 0.05:
        _report("fx recovery FAILED: truth %.1f, recovered %.1f "
                "(error %.2f%%>" % (fxe, fx, 100 * abs(fx - fxe) / fxe) +
                " 5%%) -- pose set is degenerate for fx--dist")
        raise SystemExit(1)
    _report("closed-loop selftest PASS: fx %.1f -> %.1f (err %.2f%%), "
            "rms=%.3f" % (fxe, fx, 100 * abs(fx - fxe) / fxe,
                          float(d.get("rms", float("nan")))))


def _report(msg):
    import sys
    print(msg, file=sys.stdout)
    sys.stdout.flush()


if __name__ == "__main__":
    main()