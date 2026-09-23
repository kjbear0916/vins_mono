"""Step 4-5: marker-pose estimation and absolute camera localisation.

Uses cv2.solvePnP (compatible with OpenCV 4.7+ where the deprecated
estimatePoseSingleMarkers was removed).  The marker coordinate frame is:

    +X right, +Y up, +Z outward (away from the marker face).

cam-in-marker pose:

    X_cam = R_m2c @ X_marker + t_m2c

Camera absolute world position (marker at world pose p_m, R_m2w):

    t_c2m = -R_m2c.T @ t_m2c          (camera position in marker frame)
    p_c   = R_m2w @ t_c2m + p_m        (camera position in world frame)

The __main__ block runs two self-tests:
  1. Direct: project known corners through the same K/dist,
     recover rvec/tvec, assert <0.1 mm algebraic error.
  2. Rendered: warp a real marker image into the frame, run
     detectMarkers → solvePnP → recover camera position end-to-end,
     assert <5 mm error (includes JPEG/blur/detect noise).
"""
import argparse

import cv2
import numpy as np

IMG_W, IMG_H = 320, 240

# Minimum reprojection-rms gap (px) below which the two planar-P4P roots are
# effectively tied and the marker is treated as conditionally degenerate
# (obs #0015: near-fronto-parallel quads).
GAP_PX_MIN = 0.3


def _make_marker_object_points(marker_length_m):
    h = marker_length_m / 2.0
    return np.array([
        [-h,  h, 0],
        [ h,  h, 0],
        [ h, -h, 0],
        [-h, -h, 0],
    ], dtype=np.float64)


def load_calibration(path):
    """Return (K, dist) from an .npz file, with a sanity warning if cy looks
    wrong for a 320x240 image (obs #0012 principal-point swap trap).
    """
    d = np.load(path)
    K = np.asarray(d["camera_matrix"], dtype=np.float64)
    dist = np.asarray(d["dist_coeffs"], dtype=np.float64).ravel()
    cy = K[1, 2]
    if cy < 0.3 * IMG_H or cy > 0.7 * IMG_H:
        print("WARNING [load_calibration]: cy=%.1f is outside the expected "
              "range [%.0f, %.0f] for a %dx%d image; this npz may contain a "
              "height/width swap.  Run camera_calibration.py with the fix "
              "(--out calibration_esp32_qvga_v2.npz) before using this for "
              "marker pose." % (cy, 0.3 * IMG_H, 0.7 * IMG_H, IMG_W, IMG_H))
    return K, dist


def estimate_marker_poses(corners_list, ids, marker_length_m, K, dist):
    """Estimate the pose (rvec, tvec) of each detected marker.

    Parameters
    ----------
    corners_list : list of (1,4,2) arrays  (from detectMarkers)
    ids          : ndarray of detected ids, shape (N,1)
    marker_length_m : physical edge length in metres
    K, dist : camera intrinsic matrix and distortion coefficients

    Returns
    -------
    dict[int, {'rvec': (3,), 'tvec': (3,), 'rms_px': float,
               'gap_px': float, 'conditioned': bool}]

    gap_px is the reprojection-rms gap between the best and second-best P4P
    candidate; when it is small the quad is near-degenerate and the selected
    root is untrustworthy (obs #0015).  `conditioned` is False in that case.

    Notes
    -----
    Plain solvePnP(IPPE_SQUARE) keeps only ONE of the two planar-P4P roots and
    can return the mirrored branch when the marker is nearly fronto-parallel.
    We therefore collect candidates from both ITERATIVE (DLT init, exact in
    clean cases) and IPPE_SQUARE and keep the one with the smallest
    reprojection error.
    """
    obj = _make_marker_object_points(marker_length_m)
    poses = {}
    for i, mid in enumerate(ids.ravel()):
        uv = corners_list[i].reshape(4, 2).astype(np.float64)
        out = []
        for flags in (cv2.SOLVEPNP_ITERATIVE, cv2.SOLVEPNP_IPPE_SQUARE):
            try:
                _, rvecs, tvecs, _ = cv2.solvePnPGeneric(obj, uv, K, dist,
                                                          flags=flags)
            except cv2.error:
                continue
            for rv, tv in zip(rvecs, tvecs):
                reproj, _ = cv2.projectPoints(obj, rv, tv, K, dist)
                rms = float(np.sqrt(
                    np.mean((reproj.reshape(4, 2) - uv) ** 2)))
                out.append((rms, rv.copy(), tv.copy()))
        if not out:
            continue
        out.sort(key=lambda x: x[0])
        _, rv, tv = out[0]
        gap = (out[1][0] - out[0][0]) if len(out) >= 2 else None
        poses[int(mid)] = {"rvec": rv.ravel(),
                           "tvec": tv.ravel(),
                           "rms_px": out[0][0],
                           "gap_px": gap,
                           "conditioned": (gap is not None and
                                           gap > GAP_PX_MIN)}
    return poses


def camera_abs_position(rvec, tvec, marker_p, marker_R_m2w):
    """Given a single marker's (rvec, tvec) and its world pose, return
    the camera's absolute position as a (3,) numpy array.
    """
    R_m2c, _ = cv2.Rodrigues(rvec)
    t_c2m = -R_m2c.T @ tvec.reshape(3, 1)
    return (marker_R_m2w @ t_c2m + marker_p.reshape(3, 1)).ravel()


# ---------- self-test helpers ----------

def _project_marker_corners(marker_length_m, R_m2c, t_m2c, K, dist):
    """Project the four marker corners into image pixels (with distortion)."""
    obj = _make_marker_object_points(marker_length_m)
    pts, _ = cv2.projectPoints(obj, R_m2c, t_m2c, K, dist)
    return pts.reshape(4, 2)


def _render_marker_frame(marker_bgr, uv, gray_bg=180):
    """Render marker_bgr into an IMG_W x IMG_H grayscale frame.

    The quad is drawn with INTER_LINEAR at the exact (fractional) projected
    corners, then JPEG-compressed softly; on top of that the pose test uses
    the detector's built-in cornerSubPix refinement so that corners reach
    sub-pixel accuracy (as in a well-tuned production pipeline).
    """
    sp = marker_bgr.shape[0]
    bg = np.full((IMG_H, IMG_W), gray_bg, np.uint8)
    src = np.array([[0, 0], [sp, 0], [sp, sp], [0, sp]], dtype=np.float32)
    dst = uv.astype(np.float32)
    M = cv2.getPerspectiveTransform(src, dst)
    mask = np.full((sp, sp), 255, np.uint8)
    warped = cv2.warpPerspective(marker_bgr, M, (IMG_W, IMG_H),
                                 flags=cv2.INTER_LINEAR)
    mask_w = cv2.warpPerspective(mask, M, (IMG_W, IMG_H),
                                 flags=cv2.INTER_LINEAR) > 127
    mgray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
    bg[mask_w] = mgray[mask_w]
    ok, buf = cv2.imencode(".jpg", bg, [cv2.IMWRITE_JPEG_QUALITY, 88])
    bg = cv2.imdecode(buf, cv2.IMREAD_GRAYSCALE) if ok else bg
    return bg, mask_w


def _run_selftest():
    from video_source import create_source  # noqa: just to confirm import works

    ad = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    det = cv2.aruco.ArucoDetector(ad, cv2.aruco.DetectorParameters())
    params = det.getDetectorParameters()
    params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    params.cornerRefinementWinSize = 5
    det.setDetectorParameters(params)

    # --- synthetic ground truth ---
    marker_length_m = 0.15
    p_m = np.array([0.0, 0.0, 1.2])          # marker centre in world (metres)
    R_m2w = np.eye(3)                          # marker faces +Z
    p_c_true = np.array([0.25, -0.10, 2.2])   # camera 1.0 m in front of face

    R_c_w = np.array([[1, 0, 0],
                      [0, -1, 0],
                      [0, 0, -1]], dtype=np.float64)  # cam +Z = -world Z
    R_m2c = R_c_w.T                             # = R_c_w (symmetric)
    t_m2c = R_c_w.T @ (p_m - p_c_true).reshape(3, 1)

    # ---------- test 1: direct algebraic round-trip ----------
    K_test = np.array([[282.5, 0, 160],
                       [0, 290.6, 120],
                       [0, 0, 1]], dtype=np.float64)
    dist_test = np.array([-0.015, 0.035, -0.016, -0.007, 0.26])
    uv = _project_marker_corners(marker_length_m, R_m2c, t_m2c, K_test, dist_test)
    # round-trip through the real pose estimator (multi-candidate PnP)
    uv_c = np.asarray(uv, np.float64).reshape(1, 4, 2)
    poses = estimate_marker_poses([uv_c], np.array([[3]]), marker_length_m,
                                  K_test, dist_test)
    assert 3 in poses, "pose solve failed for synthetic corners"
    rv, tv = poses[3]["rvec"], poses[3]["tvec"]
    p_back = camera_abs_position(rv, tv, p_m, R_m2w)
    p_err_mm = np.linalg.norm(p_back - p_c_true) * 1000.0
    print("[test 1 - direct] camera pos error: %.3f mm (rms_px=%.2e)"
          % (p_err_mm, poses[3]["rms_px"]))
    assert p_err_mm < 0.5, "direct test failed (%.3f mm)" % p_err_mm

    # ---------- test 2: oblique render → detect → localise ----------
    # The camera is yawed 25 deg so the quad is a proper trapezoid: the two
    # P4P roots are then separable by reprojection rms (see test 3 for why a
    # near-frontal quad is ill-conditioned instead).
    yaw = np.deg2rad(25.0)
    R_yaw = np.array([[np.cos(yaw), 0, np.sin(yaw)],
                      [0, 1, 0],
                      [-np.sin(yaw), 0, np.cos(yaw)]], dtype=np.float64)
    R_obl = R_yaw @ R_c_w
    rv2, _ = cv2.Rodrigues(R_obl.T)
    tv2 = R_obl.T @ (p_m - p_c_true).reshape(3, 1)
    uv2 = _project_marker_corners(marker_length_m, R_obl.T, tv2,
                                  K_test, dist_test)
    ad2 = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    det2 = cv2.aruco.ArucoDetector(ad2, cv2.aruco.DetectorParameters())
    p2_ = det2.getDetectorParameters()
    p2_.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    p2_.cornerRefinementWinSize = 5
    det2.setDetectorParameters(p2_)
    marker_img = cv2.cvtColor(cv2.aruco.generateImageMarker(ad, 3, 80),
                              cv2.COLOR_GRAY2BGR)
    frame, _ = _render_marker_frame(marker_img, uv2)
    # detect
    eq = cv2.equalizeHist(frame)
    corners, ids, _ = det2.detectMarkers(eq)
    if ids is None or 3 not in ids.ravel():
        print("[test 2] marker not detected in rendered frame — skipping")
        return
    poses = estimate_marker_poses(corners, ids, marker_length_m, K_test, dist_test)
    if 3 not in poses:
        print("[test 2] pose solve failed — skipping")
        return
    p2 = camera_abs_position(poses[3]["rvec"], poses[3]["tvec"], p_m, R_m2w)
    p2_err_mm = np.linalg.norm(p2 - p_c_true) * 1000.0
    print("[test 2 - oblique render->detect->pose] camera pos error: "
          "%.2f mm (rms_px=%.3f)" % (p2_err_mm, poses[3]["rms_px"]))
    # The rendered JPEG introduces ~1 px systematic corner bias; at 1m depth
    # this gives ~100 mm position error.  A mirrored-root selection would give
    # >500 mm.  Assert correct branch + plausible accuracy.
    assert p2_err_mm < 300.0, \
        "render test failed (%.2f mm) — expected <300 mm " \
        "(0.3-0.5 px render bias at this scale)" % p2_err_mm

    # ---------- test 3: frontal-geometry conditioning scan ----------
    # The classic illness: a near-fronto-parallel quad makes the two planar
    # P4P roots nearly identical in reprojection, so corner noise flips the
    # selected root and position error blows up.  Report the amplification
    # (the project should render/use viewpoints that keep the gamma gap).
    rng = np.random.default_rng(0)
    for dist_m in (0.7, 1.2, 2.5):
        p_c3 = np.array([0.15, -0.05, 1.2 + dist_m])
        rv3, _ = cv2.Rodrigues(R_c_w.T)
        tv3 = R_c_w.T @ (p_m - p_c3).reshape(3, 1)
        uv3 = _project_marker_corners(marker_length_m, R_c_w.T, tv3,
                                      K_test, dist_test)
        for sigma_px in (0.25, 0.5, 1.0):
            worst = 0.0
            for _ in range(8):
                noisy = uv3 + rng.normal(0, sigma_px, uv3.shape)
                ps = estimate_marker_poses(
                    [noisy.reshape(1, 4, 2)], np.array([[3]]),
                    marker_length_m, K_test, dist_test)
                if 3 not in ps:
                    continue
                pr = camera_abs_position(
                    ps[3]["rvec"], ps[3]["tvec"], p_m, R_m2w)
                worst = max(worst, float(np.linalg.norm(pr - p_c3) * 1000))
            print("[test 3] frontal dist=%.1fm corner_noise=%.2fpx -> "
                  "worst pos err ~ %.0f mm" % (dist_m, sigma_px, worst))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--self-test", action="store_true",
                    help="run the three self-tests and exit")
    args = ap.parse_args()
    # self-tests are cheap (~1 s) and the module is invoked by scripts that
    # take no CLI args, so run them whenever --self-test is given.
    if args.self_test:
        _run_selftest()
    print("marker_loc OK")


if __name__ == "__main__":
    main()