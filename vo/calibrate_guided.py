"""guided chessboard calibration capture with a live requirements HUD.

Shows the ESP32 stream live, auto-classifies every detected board pose into
diversity buckets (near/mid/far depth, 3x3 frame-location grid, and
in-plane/out-of-plane tilt), and only keeps a sample when it adds a
combination not seen yet -- so you move the board until the HUD is all
green instead of shooting hundreds of near-duplicate poses.

The right-hand REQ panel lists every requirement that must be completed
before the tool auto-saves and prints OK PASS:

  edge-fill      at least one pose with an outer corner < ~24px from a
                 frame edge (obs#0024: without near/edge coverage fx
                 escapes to ~2000 and cannot separate from distortion)
  tilt >=2       at least two poses tilted >=~30deg out of the image plane
  sample n/N     N unique poses kept (default 30)
  NEAR/MID/FAR   depth buckets: NEAR = board spans >=70% of frame width,
                 MID 35-70%, FAR <35%
  GRID 3x3       every 3x3 frame-location cell covered

Left pane = live camera + board + counter + a one-line hint of what to add.
Right pane = REQ checklist; when every dot is green the tool auto-saves,
calibrates, and prints gate lines followed by a final OK PASS / FAIL.

Controls:
  q / ESC   quit now and calibrate with samples so far (prints what's missing)
  a         force-add current pose even if it duplicates a bucket
  s         save the raw current frame to --save-dir
"""
import argparse
import math
import os
import re
import time

import cv2
import numpy as np

FX_GUESS = 380.0  # rough fx used for ppm->z display only; bins are pixel-based
FONT = cv2.FONT_HERSHEY_SIMPLEX
GREEN = (60, 215, 60)
RED = (60, 60, 255)
WHITE = (255, 255, 255)
YELLOW = (0, 220, 255)
GRAY = (200, 200, 200)


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


def depth_label(mn, mx, frame_w=320):
    span = float(max(mx[0] - mn[0], mx[1] - mn[1]))
    ratio = span / frame_w
    if ratio >= 0.70:
        return "NEAR"
    if ratio >= 0.35:
        return "MID"
    return "FAR"


def corner_margin(xys):
    return min(float(xys[:, 0].min()), 319.0 - xys[:, 0].max(),
               float(xys[:, 1].min()), 239.0 - xys[:, 1].max())


def missing_list(edge_near, tilt_count, tilt_need, depth_bins,
                 uncovered_cells, n_add, samples_n):
    m = []
    if not edge_near:
        m.append("edge-fill(near)")
    if tilt_count < tilt_need:
        m.append("tilt %d/%d" % (tilt_count, tilt_need))
    for k, v in depth_bins.items():
        if not v:
            m.append(k)
    if uncovered_cells:
        m.append("grid cells %d" % len(uncovered_cells))
    if n_add < samples_n:
        m.append("sample %d/%d" % (n_add, samples_n))
    return m


def draw_req_panel(panel, n_add, samples_n, edge_near, tilt_count, tilt_need,
                   depth_bins, uncovered_cells, missing):
    panel[:] = (22, 22, 22)
    y = 16
    cv2.putText(panel, "REQUIRED: all green -> SAVE",
                (6, y), FONT, 0.4, WHITE, 1)
    y += 20

    def row(label, ok, fold=(FONT, 0.4)):
        nonlocal y
        col = GREEN if ok else GRAY
        cv2.circle(panel, (12, y + 3), 3, col, -1)
        cv2.putText(panel, label, (22, y + 8), fold[0], fold[1], col, 1)
        y += 18

    row("edge-fill (corner<24px)", edge_near)
    row("tilt >=%d (%d)" % (tilt_need, tilt_count), tilt_count >= tilt_need)
    row("sample %d/%d" % (n_add, samples_n), n_add >= samples_n)
    y += 2
    for k, v in depth_bins.items():
        row(k, v)
    y += 4
    cv2.putText(panel, "GRID 3x3", (6, y), FONT, 0.4, WHITE, 1)
    y += 10
    ox, oy = 12, y
    for r in range(3):
        for c in range(3):
            col = GREEN if (c, r) not in uncovered_cells else RED
            cv2.circle(panel, (ox + c * 12 + 4, oy + r * 12 + 4), 4, col, -1)
    y += 3 * 12 + 10
    if not missing:
        cv2.putText(panel, "ALL PASS", (6, y), FONT, 0.6, GREEN, 2)
    else:
        cv2.putText(panel, "MISSING:", (6, y), FONT, 0.42, YELLOW, 1)
        for i, mline in enumerate(missing[:3]):
            cv2.putText(panel, mline[:21], (6, y + 14 + i * 14),
                        FONT, 0.34, YELLOW, 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url", default=r"http://192.168.4.1:81/stream")
    ap.add_argument("--pattern", default="5x4")
    ap.add_argument("--square", type=float, default=30.0, help="mm")
    ap.add_argument("--samples", type=int, default=30)
    ap.add_argument("--out", default=r"D:\Things\vo\calibration_esp32_qvga_v2.npz")
    ap.add_argument("--save-dir", default=r"D:\Things\vo\guided_raw")
    ap.add_argument("--blur-min", type=float, default=30.0)
    ap.add_argument("--edge-px", type=float, default=24.0,
                    help="outer-corner-to-edge margin counting as near-fill (px)")
    ap.add_argument("--tilt-min", type=float, default=0.12,
                    help="tilt01 threshold for a tilted pose (~30deg)")
    ap.add_argument("--tilt-count", type=int, default=2,
                    help="how many tilted poses are required")
    ap.add_argument("--z-hint", type=float, default=None,
                    help="metres; final gate cross-checks median board distance")
    a = ap.parse_args()

    os.makedirs(a.save_dir, exist_ok=True)
    cols, rows = parse_pattern(a.pattern)
    pattern = (cols, rows)
    obj = np.zeros((cols * rows, 3), np.float32)
    obj[:, :2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2) * a.square

    win = "guided calib -- q quit, a force-add, s save"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win, 1180, 600)

    samples = {}          # bucket-tuple -> (obj_points entry, frame corners, z_cm)
    uncovered_cells = {(c, r) for r in range(3) for c in range(3)}
    depth_bins = {"NEAR": False, "MID": False, "FAR": False}
    edge_near = False
    tilt_count = 0
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
            depth = depth_label(cc.reshape(-1, 2).min(axis=0),
                                cc.reshape(-1, 2).max(axis=0))

            xys = cc.reshape(-1, 2)
            mn, mx = xys.min(axis=0), xys.max(axis=0)
            in_frame = mn[0] >= 2 and mx[0] <= 317 and mn[1] >= 2 and mx[1] <= 237
            ppm_ok = 10.0 <= (FX_GUESS * a.square / (z_cm * 10.0)) <= 38.0
            gate_ok = is_sharp and in_frame and ppm_ok
            if gate_ok:
                bucket = (depth, round(ang / 22.5) * 22.5,
                          round(tilt01 * 8) / 8, cell)
            else:
                bucket = None

            added = False
            if gate_ok and bucket not in samples:
                samples[bucket] = (obj.copy(), cc.copy(), z_cm)
                n_add += 1
                uncovered_cells.discard(cell)
                depth_bins[depth] = True
                if corner_margin(xys) <= a.edge_px:
                    edge_near = True
                if tilt01 >= a.tilt_min:
                    tilt_count += 1
                added = True
                last_stat = "ADD %s z=%.0fcm tilt=%.2f edge=%.0fpx cell%s" % (
                    depth, z_cm, tilt01, corner_margin(xys), cell)
            elif not gate_ok:
                reason = ("" if is_sharp else "blur ") + (
                    "" if in_frame else "off-frame ") + (
                    "" if ppm_ok else "bad-size ")
                last_stat = "reject(%s)%s z=%.0fcm" % (reason, depth, z_cm)
            else:
                last_stat = "dup %s z=%.0fcm tilt=%.2f cell%s" % (
                    depth, z_cm, tilt01, cell)

            cv2.drawChessboardCorners(img, pattern, cc, found)
        else:
            last_stat = "no board"

        missing = missing_list(edge_near, tilt_count, a.tilt_count, depth_bins,
                               uncovered_cells, n_add, a.samples)
        all_ok = not missing

        cv2.rectangle(img, (0, 0), (319, 12), (0, 0, 0), -1)
        cv2.putText(img, "SAMPLE %d/%d fps=%.0f blur=%.0f %s" % (
            n_add, a.samples, fps, blur, "ALL-PASS!" if all_ok else ""),
            (4, 10), FONT, 0.35, GREEN if all_ok else WHITE, 1)

        panel = np.zeros((img.shape[0], 152, 3), np.uint8)
        draw_req_panel(panel, n_add, a.samples, edge_near, tilt_count,
                       a.tilt_count, depth_bins, uncovered_cells, missing)
        canvas = np.hstack((img, panel))

        if all_ok:
            cv2.rectangle(canvas, (0, 0), (canvas.shape[1] - 1,
                                           canvas.shape[0] - 1),
                          GREEN, 3)
        cv2.putText(canvas, last_stat[:60], (4, 130),
                    FONT, 0.4, WHITE, 1)
        cv2.putText(canvas, "q quit | a force-add | s save", (4, 146),
                    FONT, 0.35, GRAY, 1)

        cv2.imshow(win, canvas)
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
                samples[bucket] = (obj.copy(), cc.copy(), z_cm)
                n_add += 1
                depth_bins[depth] = True
                if corner_margin(xys) <= a.edge_px:
                    edge_near = True
                if tilt01 >= a.tilt_min:
                    tilt_count += 1
                last_stat = "FORCE-ADD"
                print(f"force add -> {n_add} samples", flush=True)

        if all_ok:
            print("ALL REQUIREMENTS MET - calibrating...", flush=True)
            break

    cv2.destroyAllWindows()

    missing = missing_list(edge_near, tilt_count, a.tilt_count, depth_bins,
                           uncovered_cells, n_add, a.samples)
    if missing:
        print("WARNING: quit before completing: %s" % "; ".join(missing))

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

    fx = float(K[0, 0])
    cx = float(K[0, 2])
    hfov = 2.0 * math.degrees(math.atan(cx / max(1e-6, fx)))
    rms_ok = rms < 2.0
    fx_ok = 200.0 <= fx <= 1200.0
    hfov_ok = 25.0 <= hfov <= 75.0
    z_ok = True
    if a.z_hint is not None:
        zs = np.median([v[2] for v in samples.values()]) / 100.0
        z_ok = 0.5 * a.z_hint <= zs <= 2.0 * a.z_hint
        print("median board z ~ %.2f m (z-hint %.2f m) -> %s" % (
            zs, a.z_hint, "consistent" if z_ok else "DRIFT"))

    def gate(name, ok):
        print("  [%s] %s" % ("PASS" if ok else "FAIL", name))

    gate("rms %.3f < 2.0" % rms, rms_ok)
    gate("fx  %.0f in [200,1200]" % fx, fx_ok)
    gate("HFOV %.1f deg in [25,75]" % hfov, hfov_ok)
    if a.z_hint is not None:
        gate("z-hint %.1f m" % a.z_hint, z_ok)

    all_pass = rms_ok and fx_ok and hfov_ok and z_ok
    np.savez(a.out, camera_matrix=K, dist_coeffs=dist, rms=rms,
             image_size=np.array([320, 240]),
             pattern=np.array(pattern), square=np.array([a.square]))
    print("saved", a.out)
    if all_pass:
        print("\n====== OK PASS ======")
        print("next: python vo/calib_sanity.py %s --clip <clip> --z-hint <m>" % a.out)
        return 0
    print("\n====== RESULT: FAIL ======")
    print("redo D: board must reach the frame edges (near-fill), keep zones/tilt")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())