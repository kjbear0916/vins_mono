"""Quick sanity check for camera calibration .npz files.

Prints the intrinsic matrix, flags suspicious values (obs #0012 principal-
point swap), and compares fx/fy to expected ranges for the ESP32 QVGA/VGA
sensors.

Warnings today:
- principal-point out of band (height/width swap residue)
- fx/fy plausible band for the image size
- implausible distortion magnitude (focal-distortion coupling degeneracy:
  a degenerate pose set trades focal error into huge radial terms)
- field-of-view not sensical for a small-board module lens
- optional --clip + --z-hint cross-check: verify the K against an
  INDEPENDENT distance reference (board extent alone cannot decide focal:
  solvePnP z scales inversely with fx, so pixel spans are fx-invariant;
  a wrong focal is only caught vs a known physical distance, obs #0019)
"""
import argparse
import os

import cv2
import numpy as np


def _h_fov_deg(fx, width):
    return 2.0 * np.degrees(np.arctan((width / 2.0) / fx))


def check_clip(npz_path, video, pattern=(5, 4), square_mm=25.0,
               z_hint_m=1.0, max_frames=400, verbose=False):
    """Cross-check K against a chessboard clip using an INDEPENDENT distance
    reference.

    Pixel span alone cannot decide focal: solvePnP scales z inversely with
    fx, so predicted span = fx * size / z is ~invariant (foreshortening
    also biases raw spans).  The only geometry that breaks the fx--z
    degeneracy is a known physical distance `z_hint` (board held ~N m
    away).  Under the true K, per-frame solvePnP z should cluster near
    z_hint; a wrong focal scales z by the same wrong factor and is caught
    (e.g. fx=900 on seq14 pushes z to ~2.4 m vs the actual ~1 m)."""
    K = np.asarray(np.load(npz_path)["camera_matrix"], dtype=np.float64)
    dist = np.asarray(np.load(npz_path)["dist_coeffs"], dtype=np.float64).ravel()
    objp = np.zeros((pattern[0] * pattern[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0:pattern[0], 0:pattern[1]].T.reshape(-1, 2)
    objp *= square_mm
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
    zs = []
    cap = cv2.VideoCapture(video)
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    for i in range(min(n, max_frames)):
        ok, fr = cap.read()
        if not ok:
            break
        g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
        found, c = cv2.findChessboardCorners(g, pattern)
        if not found:
            continue
        c = cv2.cornerSubPix(g, c, (11, 11), (-1, -1), crit)
        try:
            okp, rvec, tvec = cv2.solvePnP(objp, c.reshape(-1, 2),
                                           K, dist, flags=cv2.SOLVEPNP_ITERATIVE)
        except cv2.error:
            continue
        if not okp:
            continue
        z = float(np.asarray(tvec[2]))
        if z <= 0:
            continue
        zs.append(z)
    if not zs:
        print("clip cross-check: no usable chessboard frames in %s" % video)
        return 1
    med_z = float(np.median(zs))
    lo, hi = 0.55 * z_hint_m * 1000, 1.8 * z_hint_m * 1000
    ok = lo <= med_z <= hi
    print("clip cross-check: %d frames, median solvePnP |z|=%.0f mm "
          "(z_hint=%.2f m -> expected %.0f-%.0f mm)" %
          (len(zs), med_z, z_hint_m, lo, hi))
    if not ok:
        print("WARNING: median z deviates from the independent distance "
              "reference by >~2x -- the stored focal is likely wrong "
              "(z scales inversely with fx)")
        return 1
    print("  consistent with the independent distance reference")
    return 0


def check(npz_path, expect_w=320, expect_h=240, clip=None, pattern=(5, 4),
          square_mm=25.0, z_hint_m=1.0):
    d = np.load(npz_path)
    K = np.asarray(d["camera_matrix"], dtype=np.float64)
    dist = np.asarray(d["dist_coeffs"], dtype=np.float64).ravel()
    fx, fy = K[0, 0], K[1, 1]
    cx, cy = K[0, 2], K[1, 2]
    rms = float(d.get("rms", -1))
    img = np.asarray(d.get("image_size", [-1, -1]), dtype=int)
    hfov = _h_fov_deg(fx, expect_w)
    vfov = _h_fov_deg(fy, expect_h)

    print("file   :", npz_path)
    print("stored image_size:", tuple(img), "  expect %dx%d" % (expect_w, expect_h))
    print("rms    :", rms)
    print("K:\n", np.array2string(K, precision=2))
    print("dist   :", np.array2string(dist, precision=5))
    print("fx=%6.1f  fy=%6.1f  cx=%6.1f  cy=%6.1f" % (fx, fy, cx, cy))
    print("HFOV~%.1f deg  VFOV~%.1f deg" % (hfov, vfov))
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
    aniso = abs(fx - fy) / max(fx, fy)
    if aniso > 0.10:
        warnings.append(
            "board cells are not square: fx/fy=%.3f (fx=%.1f fy=%.1f) is %.0f%% "
            "anisotropic. A screen viewer stretching the image to fill the "
            "display, or non-square print scaling, turns the chessboard cells "
            "into rectangles; the tool then biases fx against fy and dumps the "
            "residual into the distortion terms. Print the board, or use a "
            "viewer that letterboxes." % (fx / max(1e-6, fy), fx, fy,
                                           aniso * 100.0))
    if not (0.25 * expect_w <= fx <= 2.5 * expect_w
            and 0.25 * expect_h <= fy <= 2.5 * expect_h):
        warnings.append(
            "focal out of plausible band for %dx%d: fx=%.1f fy=%.1f "
            "(QVGA full-FOV scale ~0.5x, window crop ~1.0x of VGA focal; "
            "flag anything outside 0.25x-2.5x of the image width)" %
            (expect_w, expect_h, fx, fy))
    if hfov < 25.0 or hfov > 115.0:
        warnings.append(
            "field of view implausible for a small-module lens: "
            "HFOV=%.1f deg (ESP32-CAM OV lenses are usually ~35-90 deg; "
            "a <25 deg result usually means focal was over-estimated by a "
            "degenerate pose set, unless a window-crop readout is confirmed)" %
            hfov)
    if dist.size and float(np.abs(dist).max()) > 50.0:
        warnings.append(
            "implausible distortion (max |dist|=%.2f) -- usually an "
            "overfit of a degenerate pose set (focal traded into distortion)" %
            float(np.abs(dist).max()))
    for w in warnings:
        print("WARNING:", w)
    if not warnings:
        print("PASS: all checks OK")
    rc = 0 if not warnings else 1
    if clip:
        rc |= check_clip(npz_path, clip, pattern, square_mm, z_hint_m)
    return rc


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("npz")
    ap.add_argument("--width", type=int, default=320)
    ap.add_argument("--height", type=int, default=240)
    ap.add_argument("--clip", default=None,
                    help="path to a saved chessboard AVI/MOV to cross-check "
                         "the K against an independent distance reference")
    ap.add_argument("--z-hint", type=float, default=1.0,
                    help="independent estimate of board distance in metres "
                         "(e.g. rig geometry) used with --clip")
    ap.add_argument("--pattern", default=(5, 4), type=lambda s: tuple(
        int(x) for x in s.split("x")))
    ap.add_argument("--square", type=float, default=25.0, help="mm")
    a = ap.parse_args()
    raise SystemExit(check(a.npz, a.width, a.height, a.clip, a.pattern,
                           a.square, a.z_hint))
