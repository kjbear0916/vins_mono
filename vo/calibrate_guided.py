"""guided chessboard calibration capture with a live requirements HUD.

Shows the ESP32 stream live, auto-classifies every detected board pose into
diversity buckets (near/mid/far depth, 3x3 frame-location grid, and
in-plane/out-of-plane tilt), and only keeps a sample when it adds a
combination not seen yet -- so you move the board until the HUD is all
green instead of shooting hundreds of near-duplicate poses.

HUD (upscaled window):
  SAMPLE n/30        how many unique poses kept
  + z: 近/中/遠       depth buckets still missing
  + loc 3x3 dots     green = a pose covered that part of the frame
  + tilt meter       wide out each axis -> more tilt diversity
  when a frame ADDS a sample it flashes "ADD" in green; when the set is
  complete it saves the NPZ and prints RMS automatically.

Controls:
  q / ESC   quit now and calibrate with samples so far
  a         force-add current pose even if it duplicates a bucket
  s         save the raw current frame to --save-dir
"""
import argparse
import os
import re
import time

import cv2
import numpy as np

FX_GUESS = 380.0  # true fx (from printed/measured 30mm-board run); z binning


def parse_pattern(s):
    if isinstance(s, (tuple, list)):
        s = "x".join(str(int(x)) for x in s)
    return tuple(int(x) for x in re.findall(r"\d+", s))


def stream_frames(url):
    import requests
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


def board_pose(cc, pattern, square=30.0):
    """Return (z_cm, rot_deg_inplane, tilt01, loc_cell) for dedupe bins.

    z_cm       rough depth from average pixels-per-square (no K needed)
    rot_deg    in-plane rotation of the first board row, 0..180
    tilt01     |top_row - bot_row| / (top_row + bot_row), 0=flat 1=extreme
    loc_cell   (col,row) in the 3x3 frame grid the board centroid lands in
    """
    cc = cc.reshape(-1, 2)
    cols, rows = pattern
    n = len(cc)
    row_pts = [cc[i * cols:(i + 1) * cols] for i in range(rows)]
    top_len = np.linalg.norm(row_pts[0][0] - row_pts[0][-1])
    bot_len = np.linalg.norm(row_pts[-1][0] - row_pts[-1][-1])
    ppm = float(np.mean([
        np.linalg.norm(row_pts[r][1:] - row_pts[r][:-1], axis=1).mean()
        for r in range(rows)]))
    z_cm = FX_GUESS * square / ppm / 10.0
    ang = np.degrees(np.arctan2(
        *(row_pts[0][-1] - row_pts[0][0])[::-1])) % 180.0
    tilt01 = abs(top_len - bot_len) / max(1e-6, top_len + bot_len)
    h, w = 240, 320  # stream is fixed QVGA
    cy = int(cc.mean(axis=0)[1] / (h / 3))
    cx = int(cc.mean(axis=0)[0] / (w / 3))
    return z_cm, ang, tilt01, (min(cx, 2), min(cy, 2))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url", default=r"http://192.168.4.1:81/stream")
    ap.add_argument("--pattern", default="5x4")
    ap.add_argument("--square", type=float, default=30.0, help="mm")
    ap.add_argument("--samples", type=int, default=30)
    ap.add_argument("--out", default=r"D:\Things\vo\calibration_esp32_qvga_v2.npz")
    ap.add_argument("--save-dir", default=r"D:\Things\vo\guided_raw")
    ap.add_argument("--blur-min", type=float, default=30.0)
    ap.add_argument("--z-hint", type=float, default=None,
                    help="if set, stop only after all 9 loc cells AND z bins "
                         "are covered (then cross-check vs this distance)")
    a = ap.parse_args()

    os.makedirs(a.save_dir, exist_ok=True)
    cols, rows = parse_pattern(a.pattern)
    pattern = (cols, rows)
    obj = np.zeros((cols * rows, 3), np.float32)
    obj[:, :2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2) * a.square

    win = "guided calib -- q quit, a force-add, s save"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win, 960, 720)

    samples = {}          # bucket-tuple -> (obj_points entry, frame jpg)
    uncovered_cells = {(c, r) for r in range(3) for c in range(3)}
    z_bins = {"近20-35": False, "中35-50": False, "遠50-65": False}
    n_add = 0
    n_seen = 0
    saved = 0
    last_stat = ""
    t_prev = time.time()

    for img in stream_frames(a.url):
        t_now = time.time()
        fps = 1.0 / max(1e-6, t_now - t_prev)
        t_prev = t_now
        n_seen += 1

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        found, cc = cv2.findChessboardCorners(gray, pattern)
        is_sharp = blur >= a.blur_min

        if found:
            cc = cv2.cornerSubPix(
                gray, cc, (11, 11), (-1, -1),
                (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001))
            z_cm, ang, tilt01, cell = board_pose(cc, pattern, a.square)
            zb = "近20-35" if z_cm < 35 else ("中35-50" if z_cm < 50 else "遠50-65")

            # ---- quality gates: only a clean, in-frame, well-sized board
            # ---- is allowed to enter the sample pool
            xys = cc.reshape(-1, 2)
            mn, mx = xys.min(axis=0), xys.max(axis=0)
            in_frame = mn[0] >= 2 and mx[0] <= 317 and mn[1] >= 2 and mx[1] <= 237
            ppm_ok = 10.0 <= (FX_GUESS * a.square / (z_cm * 10.0)) <= 38.0
            gate_ok = is_sharp and in_frame and ppm_ok
            if gate_ok:
                bucket = (zb, round(ang / 22.5) * 22.5, round(tilt01 * 8) / 8, cell)
            else:
                bucket = None

            added = False
            if gate_ok and bucket not in samples:
                samples[bucket] = (obj.copy(), cc.copy())
                n_add += 1
                uncovered_cells.discard(cell)
                z_bins[zb] = True
                added = True
                last_stat = "ADD %s z=%.0fcm tilt=%.2f cell%s" % (
                    zb, z_cm, tilt01, cell)
            elif not gate_ok:
                reason = ("" if is_sharp else "blur ") + (
                    "" if in_frame else "off-frame ") + (
                    "" if ppm_ok else "bad-size ")
                last_stat = "reject(%s)%s z=%.0fcm" % (reason, zb, z_cm)
            else:
                last_stat = "dup %s z=%.0fcm tilt=%.2f cell%s" % (
                    zb, z_cm, tilt01, cell)

            cv2.drawChessboardCorners(img, pattern, cc, found)
        else:
            last_stat = "no board"

        # ---- HUD ----
        cv2.rectangle(img, (0, 0), (319, 12), (0, 0, 0), -1)
        cv2.putText(img, "SAMPLE %d/%d fps=%.0f blur=%.0f" % (
            n_add, a.samples, fps, blur),
            (4, 10), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 0), 1)

        # 3x3 location dots
        ox, oy = 4, 20
        for cy in range(3):
            for cx in range(3):
                done = (cx, cy) not in uncovered_cells
                col = (60, 215, 60) if done else (60, 60, 255)
                cv2.circle(img, (ox + cx * 12 + 6, oy + cy * 12 + 6),
                           4, col, -1)
        cv2.putText(img, "cells", (ox + 46, oy + 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1)

        # z bins
        yy = 46
        for i, (k, v) in enumerate(z_bins.items()):
            col = (60, 215, 60) if v else (200, 200, 60)
            cv2.putText(img, k, (4, yy + i * 12),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, col, 1)

        # hint + status
        need_z = [k for k, v in z_bins.items() if not v]
        if uncovered_cells or need_z:
            hint = "MOVE: 缺 " + ", ".join(need_z)
            if uncovered_cells:
                hint += " + 補 " + ",".join(
                    "L%dT%d" % (c + 1, r + 1) for (c, r)
                    in sorted(uncovered_cells))
            cv2.putText(img, hint, (4, 100), cv2.FONT_HERSHEY_SIMPLEX,
                        0.4, (0, 220, 255), 1)
        cv2.putText(img, last_stat[:54], (4, 114),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        cv2.putText(img, "q quit | a force-add | s save", (4, 128),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (128, 128, 128), 1)

        cv2.imshow(win, img)
        key = cv2.waitKey(1) & 0xFF
        if key in (27, ord("q")):
            break
        if key == ord("s"):
            name = os.path.join(a.save_dir,
                                f"raw_{time.strftime('%H%M%S')}.jpg")
            cv2.imwrite(name, img, [cv2.IMWRITE_JPEG_QUALITY, 90])
            saved += 1
            print("saved", name, flush=True)
        if key == ord("a") and bucket is not None:
            bucket = tuple(("force",) + bucket[1:])
            if bucket not in samples:
                samples[bucket] = (obj.copy(), cc.copy())
                n_add += 1
                last_stat = "FORCE-ADD"
                print(f"force add -> {n_add} samples", flush=True)

        if n_add >= a.samples and not uncovered_cells and not need_z:
            print("ALL REQUIREMENTS MET - calibrating...", flush=True)
            break

    cv2.destroyAllWindows()

    N = len(samples)
    if N < 5:
        print("Too few samples (%d). Run again and cover the grid." % N)
        return 1
    obj_p = np.array([v[0] for v in samples.values()])
    img_p = np.array([v[1] for v in samples.values()])
    try:
        rms, K, dist, _, _ = cv2.calibrateCamera(
            obj_p, img_p, (320, 240), None, None)
    except cv2.error as e:
        print("calibrateCamera error:", e)
        print("obj_p", obj_p.shape, "img_p", img_p.shape)
        print("this should not happen; sample buckets must be (obj, corners)")
        return 1
    print("\nunique poses=%d  RMS(pix)=%.4f" % (N, rms))
    print("K =\n%s" % K)
    print("dist = %s" % np.round(dist.ravel(), 6))
    np.savez(a.out, camera_matrix=K, dist_coeffs=dist, rms=rms,
             image_size=np.array([320, 240]),
             pattern=np.array(pattern), square=np.array([a.square]))
    print("saved", a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())