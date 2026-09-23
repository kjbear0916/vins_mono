#!/usr/bin/env python3
"""Real-hardware harness: run the fly-inspired (LPLC2) looming detector
against a live ESP32-CAM MJPEG stream.

Usage:
    python tools/fly_vision_live.py --url http://192.168.4.1:81/stream
    python tools/fly_vision_live.py --url http://<esp32-ip>:81/stream --threshold 0.35

Point the camera at an approaching object (or walk toward it): score rises
and azimuth points at the threat. Laterally translating objects should stay
quiet. Triggers only after score stays above threshold for --confirm-frames
consecutive frames; q / ESC quits.
"""
import argparse
import re
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "obstacle_avoidance"))

from obstacle_avoidance.fly_vision import LoomingDetector  # noqa: E402


def stream_frames(url, timeout=3.0, max_retries=3):
    retries = 0
    while True:
        try:
            r = requests.get(url, stream=True, timeout=timeout)
        except Exception as e:
            retries += 1
            print(f"connect err ({retries}/{max_retries}): {e}", flush=True)
            if retries >= max_retries:
                print(
                    "camera unreachable. check: power, WiFi association, and that "
                    "the IP is right (AP mode = 192.168.4.1; STA = camera LAN IP). "
                    "Verify with: curl.exe http://<ip>:81/status",
                    flush=True,
                )
                return
            time.sleep(1.0)
            continue
        retries = 0
        buf = b""
        try:
            for chunk in r.iter_content(chunk_size=8192):
                buf += chunk
                while True:
                    m = re.search(br"\r\nContent-Length:\s*(\d+)\r\n", buf)
                    if not m:
                        if len(buf) > 65536:
                            buf = b""
                        break
                    n_bytes = int(m.group(1))
                    j_start = buf.find(b"\r\n\r\n", m.end())
                    if j_start < 0:
                        if len(buf) > 65536:
                            buf = b""
                        break
                    j_start += 4
                    j_end = j_start + n_bytes
                    if len(buf) < j_end:
                        break
                    jpeg = buf[j_start:j_end]
                    buf = buf[j_end:]
                    img = cv2.imdecode(
                        np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR
                    )
                    if img is not None:
                        yield img
        except Exception as e:
            retries += 1
            print(f"stream err ({retries}/{max_retries}): {e}", flush=True)
            if retries >= max_retries:
                return
        finally:
            try:
                r.close()
            except Exception:
                pass
        time.sleep(0.4)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=r"http://192.168.4.1:81/stream")
    ap.add_argument("--hfov-deg", type=float, default=62.0)
    ap.add_argument("--threshold", type=float, default=0.35)
    ap.add_argument("--grid-nx", type=int, default=24)
    ap.add_argument("--grid-ny", type=int, default=18)
    ap.add_argument("--leak", type=float, default=0.6)
    ap.add_argument("--confirm-frames", type=int, default=3)
    ap.add_argument("--no-window", action="store_true")
    ap.add_argument("--timeout", type=float, default=3.0)
    ap.add_argument("--max-retries", type=int, default=3)
    a = ap.parse_args()

    det = LoomingDetector(
        nx=a.grid_nx, ny=a.grid_ny, leak=a.leak
    )
    hfov = a.hfov_deg * np.pi / 180.0

    window = None
    if not a.no_window:
        window = "fly looming -- q quit"
        cv2.namedWindow(window, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window, 960, 720)

    n_frames = 0
    warned = False
    peak = 0.0
    confirm = 0
    az_sm = 0.0
    el_sm = 0.0
    t_prev = time.time()

    print(
        f"fly looming live -- url={a.url} threshold={a.threshold} "
        f"hfov={a.hfov_deg} deg confirm={a.confirm_frames}",
        flush=True,
    )

    for img in stream_frames(a.url, timeout=a.timeout, max_retries=a.max_retries):
        t_now = time.time()
        dt = t_now - t_prev
        t_prev = t_now
        n_frames += 1
        fps = 1.0 / max(1e-6, dt)

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        report = det.process(gray, hfov=hfov, dt=min(dt, 0.5))

        score = report["score"]
        az_raw = float(np.degrees(report["azimuth"]))
        el_raw = float(np.degrees(report["elevation"]))
        w = 0.15 + 0.55 * min(1.0, score / max(a.threshold, 1e-6))
        az_sm += w * (az_raw - az_sm)
        el_sm += w * (el_raw - el_sm)
        az_deg, el_deg = az_sm, el_sm
        peak = max(peak, score)

        confirm = confirm + 1 if score >= a.threshold else 0
        if confirm >= a.confirm_frames and not warned:
            warned = True
            print(f"LOOMING TRIGGER frame={n_frames} score={score:.2f} "
                  f"az={az_deg:+.1f} el={el_deg:+.1f}",
                  flush=True)
        elif score < a.threshold * 0.5:
            warned = False

        print(
            f"[{n_frames:5d}] fps={fps:5.1f} score={score:.3f} "
            f"az={az_deg:+7.1f} el={el_deg:+6.1f} exp={report['expansion']:.3f} "
            f"peak={peak:.3f}",
            flush=True,
        )

        if window is not None:
            status = 1 if warned else 0
            color = (60, 60, 255) if status else (60, 215, 60)
            cv2.putText(
                img,
                f"score={score:.2f} az={az_deg:+.1f} exp={report['expansion']:.2f}",
                (8, 24),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                color,
                2,
                cv2.LINE_AA,
            )
            cv2.putText(
                img,
                f"fps={fps:.1f} arm={min(confirm, a.confirm_frames)}/{a.confirm_frames} "
                f"peak={peak:.2f}",
                (8, 50),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )
            cv2.imshow(window, img)
            if cv2.waitKey(1) & 0xFF in (27, ord("q")):
                break

    if window is not None:
        cv2.destroyAllWindows()
    print(f"DONE frames={n_frames} peak_score={peak:.3f}")


if __name__ == "__main__":
    main()