import time
import cv2
import numpy as np

from video_source import create_source

URL = r"http://172.20.10.2:81/stream"
CALIB = r"D:\Things\vo\calibration_esp32_qvga.npz"
OUT = r"D:\Things\vo\real_seq.avi"

def secs(s):
    return float(s)

import argparse
ap = argparse.ArgumentParser()
ap.add_argument("--seconds", type=secs, default=30.0)
ap.add_argument("--out", default=r"D:\Things\vo\real_seq.avi")
args = ap.parse_args()
SECONDS = args.seconds
OUT = args.out
FPS = 16.0

d = np.load(CALIB)
K = d["camera_matrix"]
dist = d["dist_coeffs"].ravel()

src = create_source("esp32", url=URL)


def grab(timeout=6.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        ok, fr = src.read()
        if ok and fr is not None:
            return fr
    return None


f0 = grab()
if f0 is None:
    print("stream down")
    raise SystemExit(1)
h, w = f0.shape[:2]
map1, map2 = cv2.initUndistortRectifyMap(
    K, dist, None, K, (w, h), cv2.CV_32FC1)
out = cv2.VideoWriter(OUT, cv2.VideoWriter_fourcc(*"MJPG"), FPS, (w, h), False)

lk = dict(winSize=(21, 21), maxLevel=2,
          criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 20, 0.03))
prev_disp = 0.0
disp_total = 0.0
disp_cnt = 0
MAX_FLOW = 30.0  # drop frames moving further than this in one step

print("recording %ds to %s -- MOVE SLOWLY & STEADILY NOW" % (SECONDS, OUT))
t_start = time.time()
n = 0
t_last = time.time()
fr0 = None
dropped = 0
while time.time() - t_start < SECONDS:
    t_now = time.time()
    if t_now - t_last < 1.0 / FPS:
        time.sleep(0.005)
        continue
    fr = grab()
    if fr is None:
        print("stream dropped at %d frames" % n)
        break
    g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
    g = cv2.remap(g, map1, map2, cv2.INTER_LINEAR)

    if fr0 is not None:
        p = cv2.goodFeaturesToTrack(fr0, maxCorners=80, qualityLevel=0.01,
                                    minDistance=10)
        if p is not None and len(p) > 8:
            pp = p.reshape(-1, 1, 2).astype(np.float32)
            nxt, st, err = cv2.calcOpticalFlowPyrLK(fr0, g, pp, None, **lk)
            okq = (st.ravel() == 1) & (err.ravel() < 3)
            if okq.sum():
                d = np.linalg.norm(nxt[okq, 0] - pp[okq, 0], axis=1).mean()
                prev_disp = d
                disp_total += d
                disp_cnt += 1

    if fr0 is not None and prev_disp > MAX_FLOW:
        dropped += 1
        disp = cv2.cvtColor(g, cv2.COLOR_GRAY2BGR)
        cv2.putText(disp, "flow %6.2f DROPPED" % prev_disp, (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        cv2.imshow("RECORDING - MOVE me, watch flow", disp)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
        fr0 = g
        continue

    out.write(g)

    disp = cv2.cvtColor(g, cv2.COLOR_GRAY2BGR)
    cv2.putText(disp, "flow %6.2f px  (live)" % prev_disp, (10, 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    cv2.imshow("RECORDING - MOVE me, watch flow", disp)
    key = cv2.waitKey(1) & 0xFF
    if key == ord("q"):
        break
    fr0 = g
    n += 1
    t_last = time.time()

if disp_cnt:
    print("MEAN FLOW over recording: %.2f px/frame" % (disp_total / disp_cnt))
print("dropped %d bad-motion frames, wrote %d" % (dropped, n))

out.release()
src.release()
print("recorded %d frames -> %s" % (n, OUT))