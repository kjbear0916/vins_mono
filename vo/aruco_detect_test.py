"""ArUco detection sanity check for the indoor-GPS (marker absolute pose) build.

Verifies step 1-2 of the marker plan BEFORE any pose math is trusted:
  * is the ESP32 stream up?
  * are printed markers detected at all (DICT_4X4_50)?
  * at a given distance/angle, how stable is detection across N frames?
  * how many candidates get rejected (high => lighting/contrast problem)?

Two modes:
  python aruco_detect_test.py --url http://<esp32>:81/stream          live loop
  python aruco_detect_test.py --snapshot 30                            headless stats

Exit codes (snapshot mode): 0 = detected, 1 = stream down, 2 = no marker.
"""
import argparse
import time

import cv2
import numpy as np

DICT_ID = cv2.aruco.DICT_4X4_50


def make_detector(dict_id):
    d = cv2.aruco.getPredefinedDictionary(dict_id)
    p = cv2.aruco.DetectorParameters()
    return cv2.aruco.ArucoDetector(d, p)


def grab(filename):
    """Return a frame; fall back to an image path if the stream is down."""
    if ".png" in filename.lower() or ".jpg" in filename.lower():
        img = cv2.imread(filename)
        return None if img is None else img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url",
                    default=r"http://192.168.4.1:81/stream",
                    help="ESP32 MJPEG stream (or a path to a test image)")
    ap.add_argument("--snapshot", type=int, default=0,
                    help="run N frames headless and print detection stats "
                         "instead of a live window")
    ap.add_argument("--dict", type=int, default=DICT_ID)
    a = ap.parse_args()

    det = make_detector(a.dict)

    if not any(ch in a.url for ch in (".png", ".jpg")):
        from video_source import create_source
        src = create_source("esp32", url=a.url)
    else:
        src = None
        if any(ch in a.url for ch in (".png", ".jpg")):
            frame = grab(a.url)
            if frame is None:
                print("cannot read", a.url)
                return 2
            src = frame

    det_ids = {}
    total = 0
    rej_total = 0
    t0 = time.time()

    def handle(fr):
        nonlocal total, rej_total
        g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
        # ESP32 MJPEG is low-contrast; equalise first or ArUco misses markers
        # (same fix chessboard_precheck.py needed for the grid).
        g = cv2.equalizeHist(g)
        corners, ids, rejected = det.detectMarkers(g)
        total += 1
        rej_total += len(rejected)
        if ids is not None:
            cv2.aruco.drawDetectedMarkers(fr, corners, ids)
            for i, mid in enumerate(ids.ravel()):
                det_ids[int(mid)] = det_ids.get(int(mid), 0) + 1
        fps_now = total / max(time.time() - t0, 1e-6)
        status = "ids=%s rej=%d fps=%.1f" % (
            list(det_ids) if ids is not None else "none",
            len(rejected), fps_now)
        cv2.putText(fr, status, (6, 18), cv2.FONT_HERSHEY_SIMPLEX,
                    0.5, (0, 255, 0), 1, cv2.LINE_AA)
        return fr

    if isinstance(src, np.ndarray):
        handle(src).copy()
        print("single frame: detected so far", det_ids,
              "fps n/a (static image)")
        return 0 if det_ids else 2

    if a.snapshot > 0:
        ok_n = 0
        t_start = time.time()
        while time.time() - t_start < 20.0 and ok_n < a.snapshot:
            ok, fr = src.read()
            if ok and fr is not None:
                handle(fr)
                ok_n += 1
        src.release()
        print("frames seen: %d, detected ids: %s (counts: %s)"
              % (total, list(sorted(det_ids)), det_ids))
        print("total rejected candidates: %d (%.2f/frame)"
              % (rej_total, rej_total / max(total, 1)))
        if a.snapshot > 0 and total == 0:
            print("stream down at", a.url)
            return 1
        return 0 if det_ids else 2

    while True:
        ok, fr = src.read()
        if not ok or fr is None:
            continue
        fr = handle(fr)
        cv2.imshow("ArUco Test", fr)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
    src.release()
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())