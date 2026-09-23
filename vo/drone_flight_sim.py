"""Real-time 3D UAV flight simulator (pure simulation, no ESP32).

Opens a window showing a quadcopter flying a looping course with a chase
camera that follows it; the drone banks into turns, pitches with climb/descent,
rotors spin, and the ground grid/markers slide by underneath to sell the depth.

Controls:
    ESC / q   quit
    + / -     speed up / slow down
    gap       pause / resume

Usage:
    python D:\\Things\\vo\\drone_flight_sim.py [--size WxH] [--fps N]
"""
import math
import os
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drone3d


def state(t):
    x = 3.6 * np.sin(0.30 * t)
    y = 2.8 * np.sin(0.47 * t + 1.1)
    z = 2.3 + 0.8 * np.sin(0.62 * t + 0.5)
    return np.asarray([x, y, z], np.float64)


def deriv(pos_fn, t, dt=1e-3):
    return (pos_fn(t + dt) - pos_fn(t - dt)) / (2.0 * dt)


class Camera:
    def __init__(self):
        self.eye = np.zeros(3, np.float64)
        self.tgt = np.zeros(3, np.float64)
        self.ok = False

    def update(self, eye, tgt, k=0.16):
        eye = np.asarray(eye, np.float64)
        tgt = np.asarray(tgt, np.float64)
        if self.ok:
            self.eye += k * (eye - self.eye)
            self.tgt += k * (tgt - self.tgt)
        else:
            self.eye, self.tgt = eye.copy(), tgt.copy()
            self.ok = True


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", default="1280x800")
    ap.add_argument("--fps", type=float, default=0.0)
    args = ap.parse_args()
    try:
        W, H = (int(x) for x in args.size.lower().split("x"))
    except ValueError:
        W, H = 1280, 800

    drone3d.use_model()
    h = drone3d.init(size=(W, H))
    drone3d.use_large_ground(h)  # big ground, sky-blue fog, follow-cam range

    win = "3D UAV FLIGHT SIM"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win, W, H)
    cam = Camera()
    paused = False
    speed = 1.0
    t = 0.0
    prev = time.time()
    fps = max(args.fps, 1.0) if args.fps else 60.0
    phase0 = time.time()
    while True:
        now = time.time()
        dt = min(now - prev, 0.1)
        prev = now
        if not paused:
            t += dt * speed

        pos = state(t)
        v = deriv(state, t)
        heading = math.atan2(v[1], v[0])
        yaw_deg = math.degrees(heading)
        w = (heading - getattr(main, "_h0", heading) + math.pi) % (2 * math.pi) - math.pi
        yaw_rate = w / max(dt, 1e-4)
        main._h0 = heading
        roll = float(np.clip(-yaw_rate * 30.0, -32.0, 32.0))
        pitch = float(np.clip(-v[2] * 26.0, -24.0, 24.0))

        dx, dy = math.cos(heading), math.sin(heading)
        eye = pos + np.array([-dx * 4.2, -dy * 4.2, 1.1], np.float64)
        tgt = pos + np.array([dx * 1.4, dy * 1.4, -0.1], np.float64)
        cam.update(eye, tgt)

        img = drone3d.render_frame(h, W, H, yaw_deg, pitch, roll,
                                   phase=(t * 30.0), eye=cam.eye, target=cam.tgt)
        cv2.putText(img, "3D UAV FLIGHT SIM  speed x%.1f  t=%.1fs"
                    % (speed, t), (12, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                    (255, 255, 255), 2)
        cv2.putText(img, "ESC quit  +/- speed  SPACE pause",
                    (12, H - 14), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                    (255, 255, 255), 1)
        cv2.imshow(win, img)
        k = cv2.waitKey(1) & 0xFF
        if k in (27, ord("q")):
            break
        if k in (ord("+"), ord("=")):
            speed = min(speed * 1.25, 4.0)
        if k == ord("-"):
            speed = max(speed / 1.25, 0.25)
        if k == ord(" "):
            paused = not paused
        target_frame_ns = 1e9 / fps
        spent = (time.time() - now) * 1e9
        if spent < target_frame_ns:
            time.sleep((target_frame_ns - spent) / 1e9)

    cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    sys.exit(main())