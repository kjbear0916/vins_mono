"""live preview of the ESP32 stream with detection + quality HUD.

Shows what the camera actually sees, with live ArUco and checkerboard
overlays plus a requirement HUD so you know on the spot whether the view
meets capture criteria -- no need to shoot blind and inspect afterwards.

Controls:
  q / ESC    quit
  s          save current annotated frame into --save-dir
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
    p.adaptiveThreshWinSizeMin = 3
    p.adaptiveThreshWinSizeMax = 23
    p.adaptiveThreshWinSizeStep = 5
    return cv2.aruco.ArucoDetector(d, p)


def stream_frames(url):
    while True:
        try:
            r = requests.get(url, stream=True, timeout=10)
        except Exception as e:
            print("connect err:", e, flush=True)
            time.sleep(0.5)
            continue
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
                    img = cv2.imdecode(np.frombuffer(jpeg, np.uint8),
                                       cv2.IMREAD_COLOR)
                    if img is not None:
                        yield img
        except Exception as e:
            print("stream err:", e, flush=True)
        finally:
            try:
                r.close()
            except Exception:
                pass
        time.sleep(0.4)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=r"http://192.168.4.1:81/stream")
    ap.add_argument("--save-dir", default=r"D:\Things\vo\burst1\preview")
    ap.add_argument("--pattern", default=(5, 4),
                    help="checkerboard corners WxH (e.g. 5x4 or '5 4')")
    ap.add_argument("--blur-min", type=float, default=30,
                    help="Laplacian variance considered sharp")
    a = ap.parse_args()

    os.makedirs(a.save_dir, exist_ok=True)
    det = make_detector(DICT_ID)
    pat = a.pattern
    if isinstance(pat, str):
        pat = tuple(int(x) for x in re.findall(r"\d+", pat))
    while len(pat) < 2:
        pat = pat + (pat[-1],)
    w, h = pat[:2]

    win = "ESP32 live -- q quit, s save"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win, 960, 720)

    n_frames = 0
    n_ids_ever = 0
    n_chess_ever = 0
    last_blur = 0.0
    last_ids = []
    last_chess = False
    t_prev = time.time()

    for img in stream_frames(a.url):
        t_now = time.time()
        fps = 1.0 / max(1e-6, t_now - t_prev)
        t_prev = t_now
        n_frames += 1

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        last_blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())

        corners, ids, _ = det.detectMarkers(img)
        if ids is not None:
            cv2.aruco.drawDetectedMarkers(img, corners, ids)
            last_ids = list(ids.flatten())
            n_ids_ever += len(ids)
        else:
            last_ids = []

        found, _c = cv2.findChessboardCorners(gray, (w, h))
        last_chess = bool(found)
        if found:
            n_chess_ever += 1
            cv2.drawChessboardCorners(img, (w, h), _c, found)

        sharp = last_blur >= a.blur_min
        m_req = bool(last_ids)
        c_req = last_chess
        overall = m_req or c_req or sharp

        ox, oy = 8, 8
        rows = [("AMARKER", m_req), ("ACHESS", c_req),
                ("ASHARP blur=%.0f" % last_blur, sharp),
                ("OVERALL", overall)]
        for i, (txt, good) in enumerate(rows):
            col = (60, 215, 60) if good else (60, 60, 255)
            cv2.putText(img, txt, (ox, oy + i * 22),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, col, 1, cv2.LINE_AA)
        cv2.putText(img, "fps=%.1f ids=%s n_ids=%d n_chess=%d" % (
            fps, last_ids, n_ids_ever, n_chess_ever),
            (ox, oy + 88), cv2.FONT_HERSHEY_SIMPLEX,
            0.5, (255, 255, 255), 1, cv2.LINE_AA)
        cv2.imshow(win, img)

        k = cv2.waitKey(1) & 0xFF
        if k in (27, ord("q")):
            break
        if k == ord("s"):
            name = os.path.join(a.save_dir,
                                f"save_{time.strftime('%H%M%S')}.jpg")
            cv2.imwrite(name, img, [cv2.IMWRITE_JPEG_QUALITY, 90])
            print("saved", name, flush=True)

    cv2.destroyAllWindows()
    print(f"DONE frames={n_frames} marker_frames={n_ids_ever} "
          f"chess_frames={n_chess_ever}")


if __name__ == "__main__":
    main()