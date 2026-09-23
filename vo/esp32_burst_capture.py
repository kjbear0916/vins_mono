"""grab a burst of raw frames from the ESP32 MJPEG stream for offline reading.

The camera AP drops clients on any hiccup, so this retries the HTTP
connection and keeps appending frames until the target count is reached.
Raw JPEGs land in --out as frame_XXXX.jpg; a summary is printed at the end.
"""
import argparse
import os
import re
import time

import cv2
import numpy as np
import requests

DICT_ID = cv2.aruco.DICT_4X4_50


def make_detector(dict_id):
    d = cv2.aruco.getPredefinedDictionary(dict_id)
    p = cv2.aruco.DetectorParameters()
    return cv2.aruco.ArucoDetector(d, p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=r"http://192.168.4.1:81/stream")
    ap.add_argument("--out", default=r"D:\Things\vo\burst")
    ap.add_argument("--n", type=int, default=20, help="frames to save")
    ap.add_argument("--every", type=int, default=1, help="save every Nth frame")
    ap.add_argument("--hold", type=float, default=180, help="max seconds to try")
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    det = make_detector(DICT_ID)
    saved = 0
    seen = 0
    ids_all = {}
    t_start = time.time()

    while saved < a.n and time.time() - t_start < a.hold:
        try:
            r = requests.get(a.url, stream=True, timeout=10)
        except Exception as e:
            print(f"[{time.time()-t_start:6.1f}s] connect err {e}", flush=True)
            time.sleep(0.5)
            continue
        buf = b""
        try:
            for chunk in r.iter_content(chunk_size=8192):
                if time.time() - t_start > a.hold:
                    break
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
                    if not jpeg:
                        continue
                    img = cv2.imdecode(np.frombuffer(jpeg, np.uint8),
                                       cv2.IMREAD_COLOR)
                    if img is None:
                        continue
                    seen += 1
                    if saved >= a.n:
                        return
                    if seen % a.every == 0:
                        name = os.path.join(a.out, f"frame_{saved:04d}.jpg")
                        ok = cv2.imwrite(name, img)
                        if ok:
                            saved += 1
                            if saved % 5 == 0 or saved == a.n:
                                print(f"saved {saved}/{a.n} @ {time.time()-t_start:.1f}s", flush=True)
                    if seen % 5 == 1:
                        corners, ids, _ = det.detectMarkers(img)
                        if ids is not None:
                            for i in ids.flatten():
                                ids_all[i] = ids_all.get(i, 0) + 1
        except Exception as e:
            print(f"stream error: {e}", flush=True)
        finally:
            try:
                r.close()
            except Exception:
                pass
        time.sleep(0.4)

    h, w = img.shape[:2] if "img" in dir() else (0, 0)
    print(f"RESULT seen={seen} saved={saved} size={w}x{h} "
          f"ids={sorted(ids_all.items()) if ids_all else 'none'}")


if __name__ == "__main__":
    main()