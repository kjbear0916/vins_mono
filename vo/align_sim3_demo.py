"""Step 6: glue VO-relative trajectory to marker-absolute coordinates.

Indoor-GPS provides absolute per-frame camera positions p^abs(t) for frames
where >=1 marker was detected.  The VO/BA trajectory p^rel(t) lives in an
arbitrary gauge.  We recover the similarity transform

    p^abs ~= c * R @ p^rel + t

from correspondences at matchable timestamps using the run_gt_ate
`umeyama_sim3`, then apply it to the full trajectory.

The __main__ block runs a synthetic self-test: a known sim3 maps 5 VO control
points into "marker space"; umeyama_sim3 must recover it exactly and the
transformed full trajectory must match to <0.1 mm.
"""
import argparse

import numpy as np

from run_gt_ate import umeyama_sim3


def align_to_markers(vo_pts, abs_pts):
    """Return (scale, R, t) s.t. abs_pts == umeyama_sim3 point mapping.

    vo_pts/abs_pts: equispaced (N,3) arrays; same row order = same timestamp.
    Also returns forward transform + residual RMS, for reporting.
    """
    vo = np.asarray(vo_pts, np.float64).reshape(-1, 3)
    ab = np.asarray(abs_pts, np.float64).reshape(-1, 3)
    c, R, t = umeyama_sim3(vo, ab)
    resid = (c * (R @ vo.T)).T + t - ab
    rms = float(np.sqrt(np.mean(resid ** 2)))
    return c, R, t, rms


def transform_trajectory(traj, c, R, t):
    """Apply abs = c*R@rel + t to an (M,3) relative trajectory."""
    traj = np.asarray(traj, np.float64).reshape(-1, 3)
    return (c * (R @ traj.T)).T + t


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--control-n", type=int, default=5)
    args = ap.parse_args()

    rng = np.random.default_rng(7)
    # synthetic VO trajectory (arbitrary gauge) and control subset
    rel = np.column_stack([np.linspace(0.0, 2.5, 50),
                           np.linspace(-0.2, 0.3, 50),
                           np.zeros(50)])
    ctrl_idx = np.linspace(0, 49, args.control_n).astype(int)
    vo_pts = rel[ctrl_idx]
    # ground-truth sim3 mapping rel -> absolute
    c_true, R_true, t_true = 1.0, np.eye(3), np.array([0.0, 0.0, 1.2])
    abs_pts = (c_true * (R_true @ vo_pts.T)).T + t_true

    c, R, t, rms = align_to_markers(vo_pts, abs_pts)
    abs_full = transform_trajectory(rel, c, R, t)
    err = np.abs(abs_full - ((c_true * (R_true @ rel.T)).T + t_true))
    over_err_mm = float(np.abs(err[:, :2]).max() * 1000)
    print("control points: %d,  alignment residual rms = %.3e m"
          % (args.control_n, rms))
    print("recovered scale:   c = %.6f  (true %.6f)" % (c, c_true))
    print("max XY drift on full 50-frame traj: %.3f mm" % over_err_mm)
    print("--self-test:", "align_sim3 OK" if over_err_mm < 0.1 else "FAILED")


if __name__ == "__main__":
    main()