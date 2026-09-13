"""Pre-record chessboard sanity check: confirm the AST for ATE (run_gt_ate.py)
will actually find corners BEFORE committing to a recording.

run_gt_ate.py needs the board's inner corners (calib pattern 5x4) visible in
every frame it aligns.  seq_real_13 got 0/198 GT frames, which costs a full
recording cycle.  This tool grabs a single live frame from the ESP32 and
reports:
  * is the stream up?
  * chessboard corners found with the EXACT calibration pattern (5x4)?
  * how many? (need >= 4 frames' worth of GT in the final AVI)
  * corner spread (px) -- too small => board too far/small, reject;
    rows/cols sanity => reports the OpenCV "grid wrong" failure mode.

Usage:
  python chessboard_precheck.py [--url http://192.168.1.200:81/stream]

Exit codes: 0 = board visible & usable, 1 = stream down, 2 = no corners,
3 = wrong pattern, 4 = too small in frame.
"""
import argparse

import cv2
import numpy as np

CALIB = r"D:\Things\vo\calibration_esp32_qvga.npz"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=r"http://192.168.1.200:81/stream")
    ap.add_argument("--n-shots", type=int, default=5,
                    help="grab this many consecutive frames & report the best")
    a = ap.parse_args()

    d = np.load(CALIB)
    K = d["camera_matrix"]
    dist = d["dist_coeffs"].ravel()
    pattern = tuple(int(x) for x in np.asarray(d["pattern"]).ravel()[:2])
    sq = float(np.asarray(d["square"]).ravel()[0])
    cols, rows = pattern
    print("calib: pattern %dx%d corners, square %.1f mm, image 320x240"
          % (cols, rows, sq))

    from video_source import create_source
    src = create_source("esp32", url=a.url)

    def grab(timeout=6.0):
        import time
        t0 = time.time()
        while time.time() - t0 < timeout:
            ok, fr = src.read()
            if ok and fr is not None:
                return fr
        return None

    best = None
    for _ in range(a.n_shots):
        fr = grab()
        if fr is None:
            print("stream down at", a.url)
            src.release()
            return 1
        g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
        if g.shape[:2] != (240, 320):
            map1, map2 = cv2.initUndistortRectifyMap(
                K, dist, None, K, (g.shape[1], g.shape[0]), cv2.CV_32FC1)
            g = cv2.remap(g, map1, map2, cv2.INTER_LINEAR)
        # ESP32 MJPEG is low-contrast; histogram-equalise first or the corner
        # detector misses the grid entirely (empirically required at 320x240).
        g = cv2.equalizeHist(g)
        ok, corners = cv2.findChessboardCorners(
            g, (cols, rows), None,
            cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE)
        if not ok:
            continue
        # count distinct columns/rows spanned by the corners in px
        c = corners.reshape(-1, 2)
        spread = float(np.max(np.abs(np.diff(c[:, 0]))) * np.max(
            np.abs(np.diff(c[:, 1])))) ** 0.5  # ~diagonal span proxy
        # actually use extents
        span_x = float(c[:, 0].max() - c[:, 0].min())
        span_y = float(c[:, 1].max() - c[:, 1].min())
        best = (ok, corners, span_x, span_y)
        if ok:
            break
        print("shot: no full %dx%d corners" % (cols, rows))

    if best is None:
        print("NO chessboard corners found in %d shots. Check:" % a.n_shots)
        print("  * is a %dx%d inner-corner board in view? (5x4 = 4x3 tiles)" %
              (cols, rows))
        print("  * board too close/too far? Move it to 40-120 cm.")
        print("  * glare/reflection breaking corner contrast? Tilt board flat.")
        src.release()
        return 2

    _, corners, span_x, span_y = best
    print("chessboard OK: %dx%d corners, spans %.0fx%.0f px in a 320x240 frame"
          % (cols, rows, span_x, span_y))
    MIN_SPAN = 60.0
    too_small = span_x < MIN_SPAN or span_y < MIN_SPAN
    if too_small:
        print("WARN: board spans < %d px => too far/too small for reliable "
              "ATE. Bring it closer." % MIN_SPAN)
    print("OK to record: push rig STEADILY (flow 3-5 px), hold still for "
          "HOLD0/HOLD1 3s each.")
    src.release()
    return 0 if not too_small else 4


if __name__ == "__main__":
    import sys
    sys.exit(main())