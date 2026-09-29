# -*- coding: utf-8 -*-
"""Serve the synthetic chessboard poses as a live MJPEG stream (dry run).

calibrate_guided.stream_frames() is a generic multipart MJPEG reader, so the
guided capture can be rehearsed end to end -- detection, NEAR/MID/FAR buckets,
GRID 3x3, the final gates and the npz write -- with no ESP32 and no printing,
by pointing it at this server:

  python vo/synth_mjpeg_server.py --port 8099
  python vo/calibrate_guided.py --url http://127.0.0.1:8099/stream ^
      --pattern 5x4 --square 25 --samples 30 --out vo/synth_dryrun.npz

The renderer, the truth intrinsics (fx=fy=474, k1=-0.18, k2=0.05) and the
pose set are reused from gen_synth_calib_shoot, so a dry run that prints
OK PASS proves the pipeline and the operator's capture recipe, not the
toolchain. It cannot prove the ESP32's lens, its real focal or its actual
distortion -- that still needs the physical board.
"""
import argparse
import socket
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2
import numpy as np

import gen_guided_pose_set as gp
from gen_synth_calib_shoot import (FPS, H, NOISE, PATTERN, SQ, W,
                                   board_corners_local, make_poses,
                                   render_board)

BOUNDARY = b"opencodeframe"


def render_loop(a):
    """Yield BGR frames forever, cycling the synthetic pose list."""
    rng = np.random.default_rng(a.seed)
    fy = a.fy or a.fx
    Kt = np.array([[a.fx, 0, a.cx], [0, fy, a.cy], [0, 0, 1]], np.float64)
    dist_t = np.array([a.k1, a.k2, a.p1, a.p2, a.k3], np.float64)
    local = board_corners_local()
    poses = getattr(a, "poses", None)
    if not poses:
        poses = make_poses(rng)
        print("NOTE: falling back to gen_synth_calib_shoot.make_poses, which "
              "cannot satisfy the REQ panel (see gen_guided_pose_set.py)",
              flush=True)
    else:
        poses = [(p["z"], p["pu"], p["pv"], p["pitch"], p["yaw"], p.get("roll", 0))
                 for p in poses]
    print("serving %d poses  truth fx=%.1f cx=%.1f cy=%.1f  (%dx%d, sq=%.0fmm)"
          % (len(poses), a.fx, a.cx, a.cy, W, H, SQ), flush=True)
    n_ok = 0
    while True:
        for (z, pu, pv, ang_p, ang_y, ang_r) in poses:
            gray = np.zeros((H, W), np.uint8)
            R_bc = gp.rot(ang_p, ang_y, ang_r)
            t_bc = gp.project_centre(z, pu, pv, Kt)
            if not render_board(gray, Kt, dist_t, local, R_bc, t_bc):
                continue
            g = gray.astype(np.float32)
            if a.noise > 0:
                g += rng.normal(0.0, a.noise, g.shape)
            frame = np.clip(g, 0, 255).astype(np.uint8)
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
            n_ok += 1
            if n_ok % max(1, len(poses)) == 0:
                print("... %d frames served" % n_ok, flush=True)
            yield frame
            time.sleep(1.0 / a.fps)


def make_handler(a):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def setup(self):
            # TCP_NODELAY used to be blamed for a ~2 fps reader (Nagle /
            # delayed ACK); the actual root cause was the reader's parser
            # misaligning on a stray \r\n\r\n inside the JPEG body
            # (video_source.mjpeg_frames). Keep the socket batching low anyway.
            super().setup()
            self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY,
                                       1)

        def log_message(self, *args):
            pass

        def do_GET(self):
            if not self.path.startswith("/stream"):
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type",
                             "multipart/x-mixed-replace; boundary=%s"
                             % BOUNDARY.decode())
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            try:
                for frame in render_loop(a):
                    ok, jpeg = cv2.imencode(".jpg", frame,
                                            [int(cv2.IMWRITE_JPEG_QUALITY), 90])
                    if not ok:
                        continue
                    payload = jpeg.tobytes()
                    self.wfile.write(b"--" + BOUNDARY +
                                     b"\r\nContent-Length: %d\r\n\r\n"
                                     % len(payload) + payload + b"\r\n")
            except (BrokenPipeError, ConnectionResetError):
                pass
    return Handler


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=8099)
    ap.add_argument("--fps", type=float, default=12.0)
    ap.add_argument("--fx", type=float, default=474.0)
    ap.add_argument("--fy", type=float, default=None)
    ap.add_argument("--cx", type=float, default=160.0)
    ap.add_argument("--cy", type=float, default=120.0)
    ap.add_argument("--k1", type=float, default=-0.18)
    ap.add_argument("--k2", type=float, default=0.05)
    ap.add_argument("--p1", type=float, default=0.0)
    ap.add_argument("--p2", type=float, default=0.0)
    ap.add_argument("--k3", type=float, default=0.0)
    ap.add_argument("--noise", type=float, default=NOISE)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    print("board: %dx%d inner corners, square %.0f mm, frame %dx%d"
          % (PATTERN[0], PATTERN[1], SQ, W, H), flush=True)
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), make_handler(a))
    print("http://127.0.0.1:%d/stream  (ctrl-c to stop)" % a.port, flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("stopped", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
