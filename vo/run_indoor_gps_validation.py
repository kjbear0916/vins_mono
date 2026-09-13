"""Step 7: consolidated indoor-GPS validation runner.

Runs every pipeline stage self-test (headless, no hardware) and prints a
structured pass/fail table.  Then produces a parametric pose-error envelope
sweep (distance × corner-noise) -- the quantitative data that the report's
step 8 uses to justify the recommended marker size and working distance.

Usage:
  python vo/run_indoor_gps_validation.py
"""
import argparse
import time

import cv2
import numpy as np

from marker_loc import (estimate_marker_poses, camera_abs_position,
                        IMG_W, IMG_H, GAP_PX_MIN)
from marker_positions import load_markers
from run_gt_ate import umeyama_sim3
from run_gt_ate import center_of  # noqa: F401 -- used by other modules
from video_source import create_source
from video_source import HTTPMJPEGSource, WebcamSource, VideoFileSource  # noqa

# ── lightweight helpers ────────────────────────────────────────────────

_calib_npz = r"D:\Things\vo\calibration_esp32_qvga.npz"
_marker_positions_json = r"D:\Things\vo\marker_positions.json"

_marker_m = 0.15
K_env = np.array([[282.5, 0, 160], [0, 290.6, 120], [0, 0, 1]], np.float64)
_dist_env = np.array([-0.015, 0.035, -0.016, -0.007, 0.26])


def _detect_test():
    """Quick detection headless probe: a 90 px marker pasted on a gray
    background (as the camera pipeline sees it, with JPEG), then detected.
    """
    import cv2.aruco as aruco
    from marker_loc import _render_marker_frame
    d = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)
    det = aruco.ArucoDetector(d, aruco.DetectorParameters())
    marker = cv2.cvtColor(aruco.generateImageMarker(d, 3, 90),
                          cv2.COLOR_GRAY2BGR)
    uv = np.array([[100, 60], [210, 62], [208, 175], [98, 173]], np.float64)
    frame, _ = _render_marker_frame(marker, uv)
    corners, ids, _ = det.detectMarkers(cv2.equalizeHist(frame))
    assert ids is not None and 3 in ids.ravel(), \
        "synthetic 90px marker pasted on gray bg not detected"


def _pose_selftest():
    from marker_loc import _run_selftest
    _run_selftest()


def _sim3_selftest():
    import align_sim3_demo as _  # noqa -- its main runs the self-test
    # It calls the test in its __main__ but we can import and call directly
    from align_sim3_demo import align_to_markers, transform_trajectory
    rng = np.random.default_rng(7)
    rel = np.column_stack([np.linspace(0.0, 2.5, 50),
                           np.linspace(-0.2, 0.3, 50),
                           np.zeros(50)])
    ctrl_idx = np.linspace(0, 49, 5).astype(int)
    vo_pts = rel[ctrl_idx]
    abs_pts = vo_pts.copy()  # identity sim3
    c, R, t, rms = align_to_markers(vo_pts, abs_pts)
    assert abs(c - 1.0) < 1e-6, "sim3 scale recovery failed"


def _pipeline_selftest():
    from localise_video import _selftest as _ls
    _ls()


def _calib_sanity():
    """Non-fatal: call calib_sanity.check() and capture warnings."""
    from calib_sanity import check
    try:
        rc = check(_calib_npz)
    except Exception as e:
        return 1, str(e)[:80]
    return rc, "WARN: cy outside sane range" if rc else "OK"


# ── stage runners ──────────────────────────────────────────────────────

def run_tests():
    tests = [
        ("detection (90px synthetic)", _detect_test),
        ("pose self-test (marker_loc)", _pose_selftest),
        ("sim3 alignment", _sim3_selftest),
        ("localise_video pipeline", _pipeline_selftest),
        ("calibration sanity", _calib_sanity),
    ]
    results = []
    for name, fn in tests:
        t0 = time.time()
        try:
            flag = fn()
            ok = (flag == 0 if isinstance(flag, int) else True)
            msg = "PASS" if ok else "WARN"
        except AssertionError as e:
            ok = False
            msg = "FAIL: " + str(e)[:80]
        except Exception as e:
            ok = False
            msg = "ERROR: " + repr(e)[:80]
        dt = time.time() - t0
        results.append((name, msg, dt))
    return results


# ── pose-error envelope sweep ──────────────────────────────────────────

def run_envelope():
    """Produce a table: distance (m) × corner-noise σ (px) → worst-case
    position error (mm) over N randomised PnP trials.

    Conditions: marker 15 cm, camera at yaw 8° (mildly oblique), frontal
    depth ``1.2 + d`` metres from a marker at z=1.2 facing +Z.
    """
    d_cam_marker = np.array([0.0, 0.0, 1.2])
    yaw = np.deg2rad(8.0)
    R_y = np.array([[np.cos(yaw), 0, np.sin(yaw)],
                    [0, 1, 0],
                    [-np.sin(yaw), 0, np.cos(yaw)]], np.float64)
    R_cam = R_y @ np.diag([1.0, -1.0, -1.0])

    obj = np.array([[-_marker_m / 2, _marker_m / 2, 0],
                    [_marker_m / 2, _marker_m / 2, 0],
                    [_marker_m / 2, -_marker_m / 2, 0],
                    [-_marker_m / 2, -_marker_m / 2, 0]], np.float64)

    depths = [0.3, 0.4, 0.6, 0.8, 1.0, 1.5, 2.0, 2.5]
    sigmas = [0.1, 0.3, 0.5, 1.0]
    rng = np.random.default_rng(9)
    N = 12

    rows = []
    for d in depths:
        p_c = np.array([0.0, 0.0, 1.2 + d])
        # true corners
        tv = R_cam.T @ (d_cam_marker - p_c).reshape(3, 1)
        uv, _ = cv2.projectPoints(obj, R_cam.T, tv, K_env, _dist_env)
        uv = uv.reshape(4, 2)
        px_size = float(np.linalg.norm(uv[1] - uv[0]))
        worst_per_sigma = []
        for σ in sigmas:
            worsts = []
            for _ in range(N):
                noisy = uv + rng.normal(0, σ, uv.shape)
                ps = estimate_marker_poses([noisy.reshape(1, 4, 2)],
                                           np.array([[0]]), _marker_m,
                                           K_env, _dist_env)
                if 0 not in ps:
                    worsts.append(float("inf"))
                    continue
                pos = camera_abs_position(ps[0]["rvec"], ps[0]["tvec"],
                                          d_cam_marker, np.eye(3))
                worsts.append(float(np.linalg.norm(pos - p_c) * 1000))
            worst_per_sigma.append(int(round(max(worsts))))
        rows.append((d, int(round(px_size)), *worst_per_sigma))
    return depths, sigmas, rows


# ── main ───────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.parse_args()

    print("=" * 72)
    print("Indoor-GPS consolidated validation (step 7)")
    print("=" * 72)

    # ── pipeline stage tests ───────────────────────────────────────────
    print("\n--- pipeline stage tests ---")
    test_results = run_tests()
    widths = [42, 12, 8]
    hdr = ("test".ljust(widths[0]) + "result".ljust(widths[1])
           + "t".rjust(widths[2]))
    print(hdr)
    print("-" * sum(widths))
    all_pass = True
    for name, msg, dt in test_results:
        ok = msg == "PASS"
        all_pass &= ok
        print("%s%s%s" % (name.ljust(widths[0]),
                          msg.ljust(widths[1]),
                          ("%.1fs" % dt).rjust(widths[2])))
    print("-" * sum(widths))
    print("overall: %s" % ("ALL PASS" if all_pass else "FAILURES"))

    # ── pose-error envelope sweep ──────────────────────────────────────
    print("\n--- pose error envelope (15 cm marker, yaw 8°, N=%d) ---" % 12)
    depths, sigmas, rows = run_envelope()
    colw = [10, 8] + [10] * len(sigmas)
    hdr = "depth(m)".ljust(colw[0]) + "px_size".ljust(colw[1])
    for σ in sigmas:
        hdr += ("σ=%.1fpx" % σ).rjust(colw[2])
    print(hdr)
    print("-" * sum(colw))
    for d, px, *worsts in rows:
        line = ("%.1f" % d).ljust(colw[0]) + str(px).ljust(colw[1])
        for w in worsts:
            if w >= 10000:
                line += "  >10m".rjust(colw[2])
            else:
                line += ("%d mm" % w).rjust(colw[2])
        print(line)
    print("-" * sum(colw))

    print("\nactionable: print markers >= 15 cm; use within 0.5 m; "
          "average multi-marker; prefer >8° yaw.")


if __name__ == "__main__":
    main()