"""Record a *clean single-direction translation* sequence for VO GT tests.

Three phases, guided on-screen:
  HOLD  : keep the camera still (3 s)  -- baseline/drift reference
  MOVE  : push the rig steadily ONE direction (~N s) -- no pause, no reversal
  HOLD  : stop and hold still (3 s)    -- end drift reference

The script live-checks optical flow: if the camera jolts between frames
(flow > MAX_FLOW px) the frame is skipped and counted; the on-screen overlay
shows current flow + phase so the operator can keep the pace gentle and
steady. Output is undistorted grayscale AVI + a metadata JSON (fps, per-phase
flow stats, dropped frames, wall-clock timestamps) that the validation stage
reads.

Usage:
  python record_clean_seq.py --seconds 12 --out vo/seq_clean_01.avi
  python record_clean_seq.py --url http://172.20.10.8:81/stream --seconds 20   # STA 固定 IP
  python record_clean_seq.py --url http://192.168.4.1:81/stream --seconds 20  # ESP32 AP 模式
"""

import argparse
import json
import time

import cv2
import numpy as np

from video_source import create_source

CALIB = r"D:\Things\vo\calibration_esp32_qvga.npz"
MAX_FLOW = 30.0        # px/frame; frames beyond this are dropped (jolt)
MIN_FLOW_LIVE = 1.0    # overlay hint only
FPS = 16.0
HOLD_S = 3.0


def parse():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url",
                    default=r"http://172.20.10.8:81/stream",
                    help="ESP32 stream URL (STA fixed IP by default; AP = http://192.168.4.1:81/stream)")
    ap.add_argument("--seconds", type=float, default=12.0,
                    help="duration of the MOVE phase")
    ap.add_argument("--out", default=r"D:\Things\vo\seq_clean_01.avi")
    ap.add_argument("--calib", default=CALIB)
    ap.add_argument("--fps", type=float, default=FPS)
    return ap.parse_args()


def grab(src, timeout=6.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        ok, fr = src.read()
        if ok and fr is not None:
            return fr
    return None


def main():
    a = parse()
    d = np.load(a.calib)
    K = d["camera_matrix"]
    dist = d["dist_coeffs"].ravel()

    src = create_source("esp32", url=a.url)
    f0 = grab(src)
    if f0 is None:
        print("stream down at", a.url)
        raise SystemExit(1)
    h, w = f0.shape[:2]
    map1, map2 = cv2.initUndistortRectifyMap(
        K, dist, None, K, (w, h), cv2.CV_32FC1)

    out = cv2.VideoWriter(a.out, cv2.VideoWriter_fourcc(*"MJPG"),
                          a.fps, (w, h), False)
    lk = dict(winSize=(21, 21), maxLevel=2,
              criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT,
                        20, 0.03))

    def frames_g():
        while True:
            fr = grab(src)
            if fr is None:
                return
            g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
            yield cv2.remap(g, map1, map2, cv2.INTER_LINEAR)

    phases = [("HOLD0", HOLD_S), ("MOVE", a.seconds), ("HOLD1", HOLD_S)]
    stats = {p[0]: {"flow_sum": 0.0, "flow_n": 0, "frames": 0,
                    "dropped": 0} for p in phases}

    prev = None
    it = frames_g()
    frame_ts = []          # wall-clock sec for EVERY written AVI frame
    for key, dur in phases:
        phase = key if not key.startswith("HOLD") else "HOLD"
        print("PHASE %s for %.0fs -- %s" %
              (phase, dur, {"HOLD": "STAY STILL",
                            "MOVE": "PUSH STEADILY ONE DIRECTION"}[phase]))
        t_start = time.time()
        while time.time() - t_start < dur:
            g = next(it, None)
            if g is None:
                print("stream ended mid-%s" % phase)
                out.release(); src.release()
                return
            flow = 0.0
            if prev is not None:
                p = cv2.goodFeaturesToTrack(prev, maxCorners=80,
                                            qualityLevel=0.01, minDistance=10)
                if p is not None and len(p) > 8:
                    pp = p.reshape(-1, 1, 2).astype(np.float32)
                    nxt, st, err = cv2.calcOpticalFlowPyrLK(prev, g, pp,
                                                            None, **lk)
                    okq = (st.ravel() == 1) & (err.ravel() < 3)
                    if okq.sum():
                        flow = float(np.linalg.norm(
                            nxt[okq, 0] - pp[okq, 0], axis=1).mean())

            if phase == "MOVE" and prev is not None and flow > MAX_FLOW:
                stats[key]["dropped"] += 1
                disp = cv2.cvtColor(g, cv2.COLOR_GRAY2BGR)
                cv2.putText(disp, "flow %6.2f DROPPED" % flow, (10, 25),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                cv2.imshow("RECORD %s" % phase, disp)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    out.release(); src.release()
                    cv2.destroyAllWindows()
                    return
                prev = g
                continue

            out.write(g)
            frame_ts.append(time.time())
            s = stats[key]
            s["frames"] += 1
            if flow:
                s["flow_sum"] += flow
                s["flow_n"] += 1

            disp = cv2.cvtColor(g, cv2.COLOR_GRAY2BGR)
            el = time.time() - t_start
            frac = min(el / max(dur, 1e-9), 1.0)
            col = (0, 255, 0) if flow <= MAX_FLOW else (0, 0, 255)
            cv2.putText(disp, "%s  t=%4.1f/%4.1fs  flow %5.2f" %
                        (phase, el, dur, flow), (10, 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, col, 2)
            bar_x = 10
            bar_w = int(200 * frac)
            cv2.rectangle(disp, (bar_x, 40), (bar_x + bar_w, 48),
                          col, -1)
            cv2.imshow("RECORD %s" % phase, disp)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                out.release(); src.release()
                cv2.destroyAllWindows()
                return
            prev = g
            if phase != "MOVE":
                time.sleep(1.0 / a.fps)

    out.release()
    src.release()
    cv2.destroyAllWindows()

    meta = {"out": a.out, "url": a.url, "fps": a.fps, "frames": {},
            "size": [w, h], "phases": [],
            "per_frame_ts": [round(t, 6) for t in frame_ts]}
    for key, _ in phases:
        s = stats[key]
        mean_flow = (s["flow_sum"] / s["flow_n"]) if s["flow_n"] else 0.0
        meta["frames"][key] = s["frames"]
        meta["phases"].append({"name": key, "dropped": s["dropped"],
                               "mean_flow_px": round(mean_flow, 3)})
        print("%s : %d frames, dropped %d, mean flow %.2f px/frame" %
              (key, s["frames"], s["dropped"], mean_flow))

    meta_path = a.out.replace(".avi", "_meta.json")
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    print("metadata ->", meta_path)
    print("RECORDING COMPLETE ->", a.out)


if __name__ == "__main__":
    main()