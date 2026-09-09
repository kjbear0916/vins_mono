"""Convert a stepwise (hand-pushed) recording into a rest-only keyframe AVI.

Hand-pushing a rig produces "displace-stall-displace-stall" motion: sharp rest
frames separated by blurry burst frames. LK and essential-PnP cannot track the
bursts. This script keeps only the frames where a real displacement happens,
measured against the *previous* frame (so small hand steps are caught). The
first frame is always kept; afterwards a frame is kept when the LK flow from
the previous frame is within [lo, hi] px -- big bursts (hi) and near-duplicates
(< lo) are skipped. Output is a displacement-only AVI.

Usage:
  python restify_seq.py --video seq_real_07.avi --out seq_real_07_rest.avi [--lo 2.0 --hi 40.0]
"""

import argparse
import cv2
import numpy as np

LK = dict(winSize=(21, 21), maxLevel=3,
          criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 20, 0.02))


def parse():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--lo", type=float, default=2.0,
                    help="min flow (px) to accept; below = duplicate/noise")
    ap.add_argument("--hi", type=float, default=40.0,
                    help="frames above this flow are blurred bursts, dropped")
    ap.add_argument("--fps", type=float, default=16.0)
    return ap.parse_args()


def main():
    a = parse()
    cap = cv2.VideoCapture(a.video)
    n0 = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    out = cv2.VideoWriter(a.out, cv2.VideoWriter_fourcc(*"MJPG"),
                          a.fps, (w, h), False)

    prev = None
    kept = 0
    dropped_dup = 0
    dropped_burst = 0
    kept_flow = []
    i = 0

    while True:
        ok, fr = cap.read()
        if not ok:
            break
        g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY) if len(fr.shape) == 3 else fr

        if prev is None:
            out.write(g)
            prev = g
            kept += 1
            i += 1
            continue

        flow = 0.0
        p = cv2.goodFeaturesToTrack(prev, 200, 0.01, 6)
        if p is not None and len(p) > 8:
            pp = p.reshape(-1, 1, 2).astype(np.float32)
            nxt, st, err = cv2.calcOpticalFlowPyrLK(prev, g, pp, None, **LK)
            okq = (st.ravel() == 1) & (err.ravel() < 3.0)
            if okq.sum() >= 8:
                flow = float(np.linalg.norm(
                    nxt[okq, 0] - pp[okq, 0].reshape(-1, 2), axis=1).mean())

        if flow < a.lo:
            dropped_dup += 1
        elif flow > a.hi:
            dropped_burst += 1
        else:
            out.write(g)
            kept_flow.append(flow)
            kept += 1
        prev = g
        i += 1

    cap.release()
    out.release()
    print("input %d -> kept %d (dup/noise %d, burst %d)" %
          (n0, kept, dropped_dup, dropped_burst))
    if kept_flow:
        print("kept flow: mean %.2f  max %.2f  min %.2f  n=%d" %
              (np.mean(kept_flow), max(kept_flow), min(kept_flow), len(kept_flow)))


if __name__ == "__main__":
    main()