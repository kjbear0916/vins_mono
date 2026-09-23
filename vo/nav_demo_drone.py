"""Professional indoor-GPS + UAV navigation simulation for professor demos.

Enhanced version of nav_demo.py with:
  - realistic quadcopter drone model (animated rotors, camera cone, shadow)
  - simulated camera-view inset (what the drone's camera sees, marker perspective)
  - flight dashboard (altitude, speed, heading, battery, distance)
  - smooth interpolated flight path
  - click-to-set-goal interaction

Input: the localise_video.py CSV, or --demo synthetic walk.
"""
import argparse
import csv
import json
import math
import os
import time

import cv2
import drone3d
import numpy as np


WIN_W, WIN_H = 1080, 860
MAP_X0, MAP_Y0, MAP_W, MAP_H = 60, 100, 600, 540
DASH_X, DASH_Y, DASH_W, DASH_H = 690, 86, 370, 182
UAV_X, UAV_Y, UAV_W, UAV_H = 690, 290, 370, 248
CAM_X, CAM_Y, CAM_W, CAM_H = 690, 546, 370, 226
ROOM_W, ROOM_D = 2.5, 3.0
ALT_DEFAULT = 1.2
ROTOR_PHASES = [0.0, 0.4, 0.8, 1.2]


def load_marker_table(path):
    with open(path, encoding="utf-8") as fh:
        d = json.load(fh)
    return {int(k): {"x": float(v["x"]), "z": float(v["z"]),
                      "y": float(v.get("y", 1.2))}
            for k, v in d.items() if k.lstrip("-").isdigit()}


def parse_waypoints(spec, table):
    out = []
    if spec:
        for part in spec.replace(" ", "").split(","):
            if part.startswith("id:") and part[3:].isdigit():
                mid = int(part[3:])
                if mid in table:
                    out.append((table[mid]["x"], table[mid]["z"],
                                table[mid]["y"], "M%d" % mid))
                continue
            try:
                x, z = (float(v) for v in part.split(","))
                out.append((x, z, ALT_DEFAULT, "G"))
            except ValueError:
                pass
    if not out:
        for mid in sorted(table):
            out.append((table[mid]["x"], table[mid]["z"],
                        table[mid]["y"], "M%d" % mid))
    return out


def load_traj(path):
    rows = []
    with open(path, newline="") as fh:
        for r in csv.DictReader(fh):
            if r.get("x", "") == "":
                rows.append(None)
                continue
            try:
                rows.append((int(float(r["frame"])),
                             float(r["x"]), float(r["z"]),
                             int(r["n_obs"] or 0),
                             float(r["spread_x_mm"] or 0.0)))
            except (KeyError, ValueError):
                rows.append(None)
    return rows


def synth_traj(table, waypoints, n=600, speed=0.30, fps_rev=10, seed=11):
    rng = np.random.default_rng(seed)
    pts = [(wp[0], wp[1]) for wp in waypoints]
    xs, zs, nobs = [], [], []
    cur = np.array(pts[0], np.float64)
    i_wp = 0
    step = speed / fps_rev
    for _ in range(n):
        tgt = np.array(pts[i_wp], np.float64)
        d = np.linalg.norm(tgt - cur)
        if d < step:
            cur = tgt.copy()
            i_wp = (i_wp + 1) % len(pts)
        else:
            cur += (tgt - cur) / d * (step * rng.uniform(0.85, 1.15))
        cur += rng.normal(0.0, 0.008, 2)
        xs.append(float(cur[0]))
        zs.append(float(cur[1]))
        nobs.append(0 if rng.random() < 0.04 else int(rng.choice([1, 2])))
    rows = []
    for i, (xz, zo) in enumerate(zip(zip(xs, zs), nobs)):
        if zo == 0:
            rows.append(None)
            continue
        rows.append((i, xz[0], xz[1], zo, float(rng.uniform(3, 18))))
    return rows


def smooth_path(rows, win=5):
    coords = []
    for r in rows:
        if r is None:
            coords.append(None)
        else:
            coords.append((r[1], r[2]))
    out = []
    for i, c in enumerate(coords):
        if c is None:
            out.append(None)
            continue
        window = [c]
        for j in range(1, win + 1):
            if i - j >= 0 and coords[i - j] is not None:
                window.append(coords[i - j])
            if i + j < len(coords) and coords[i + j] is not None:
                window.append(coords[i + j])
        ax = np.mean([p[0] for p in window])
        az = np.mean([p[1] for p in window])
        out.append((ax, az))
    return out


def bearing_deg(dx, dz):
    return (np.degrees(math.atan2(dz, dx)) + 360.0) % 360.0


def draw_drone(img, cx, cy, altitude, heading_rad, rotor_phase, battery):
    """Draw top-down quadcopter with animated rotors."""
    arm_len = 28
    body_r = 8
    angles = [math.pi / 4 + a * math.pi / 2 for a in range(4)]
    for a in angles:
        ex = int(cx + arm_len * math.cos(a))
        ey = int(cy + arm_len * math.sin(a))
        cv2.line(img, (cx, cy), (ex, ey), (80, 80, 80), 3, cv2.LINE_AA)
        rr = int(14 + 3 * math.sin(rotor_phase + a * 2.5))
        cv2.circle(img, (ex, ey), rr, (180, 180, 180), 2, cv2.LINE_AA)
        cv2.circle(img, (ex, ey), 3, (100, 100, 100), -1)
    cv2.circle(img, (cx, cy), body_r, (60, 60, 60), -1, cv2.LINE_AA)
    cv2.circle(img, (cx, cy), body_r, (30, 30, 30), 2, cv2.LINE_AA)
    ld = int(5 * math.cos(heading_rad))
    lm = int(5 * math.sin(heading_rad))
    cv2.circle(img, (cx + ld, cy + lm), 3, (0, 255, 0), -1)
    if battery > 60:
        bc = (0, 220, 0)
    elif battery > 25:
        bc = (0, 200, 255)
    else:
        bc = (0, 0, 255)
    cv2.circle(img, (cx, cy + body_r + 4), 2, bc, -1)
    cam_y = cy + body_r + 10
    cv2.line(img, (cx, cy + body_r), (cx, cam_y), (0, 0, 180), 2)
    cv2.circle(img, (cx, cam_y), 3, (0, 0, 220), -1)


def draw_shadow(img, cx, cy, altitude, s):
    alpha = max(25, min(90, int(80 - altitude * 30)))
    overlay = img.copy()
    sz = max(6, int(16 - altitude * 3))
    cv2.ellipse(overlay, (cx, cy + int(altitude * s * 0.5)),
                (sz + 4, sz - 1), 0, 0, 360, (0, 0, 0), -1)
    cv2.addWeighted(overlay, alpha / 255.0, img, 1 - alpha / 255.0, 0, img)


def draw_camera_cone(img, cx, cy, heading_rad, fov_deg=70, length=45):
    half = math.radians(fov_deg / 2)
    x1 = int(cx + length * math.cos(heading_rad - half))
    y1 = int(cy + length * math.sin(heading_rad - half))
    x2 = int(cx + length * math.cos(heading_rad + half))
    y2 = int(cy + length * math.sin(heading_rad + half))
    pts = np.array([[cx, cy], [x1, y1], [x2, y2]], np.int32)
    overlay = img.copy()
    cv2.fillPoly(overlay, [pts], (0, 120, 255))
    cv2.addWeighted(overlay, 0.15, img, 0.85, 0, img)
    cv2.line(img, (cx, cy), (x1, y1), (0, 120, 255), 1, cv2.LINE_AA)
    cv2.line(img, (cx, cy), (x2, y2), (0, 120, 255), 1, cv2.LINE_AA)


def draw_camera_view(img, px, pz, py, heading_rad, table, K, dist):
    view = np.full((CAM_H - 20, CAM_W - 20, 3), 40, np.uint8)
    vw, vh = view.shape[1], view.shape[0]
    fov = 70.0
    fx_cam = vw / (2 * math.tan(math.radians(fov / 2)))
    Kc = np.array([[fx_cam, 0, vw / 2], [0, fx_cam, vh / 2], [0, 0, 1]],
                   np.float64)
    Rc = np.array([[math.cos(heading_rad), 0, math.sin(heading_rad)],
                   [0, 1, 0],
                   [-math.sin(heading_rad), 0, math.cos(heading_rad)]])
    tc = -Rc.T @ np.array([px, py, pz])
    for mid, v in table.items():
        wx, wy, wz = v["x"], v["y"], v["z"]
        p_cam = Rc.T @ np.array([wx - px, wy - py, wz - pz])
        if p_cam[2] <= 0.1:
            continue
        uv = Kc @ p_cam
        uv = uv[:2] / p_cam[2]
        sx, sy = int(uv[0]), int(uv[1])
        sz = max(8, int(50 / p_cam[2]))
        if 0 <= sx < vw and 0 <= sy < vh:
            x0, y0 = max(0, sx - sz), max(0, sy - sz)
            x1, y1 = min(vw, sx + sz), min(vh, sy + sz)
            cv2.rectangle(view, (x0, y0), (x1, y1), (0, 180, 255), -1)
            cv2.rectangle(view, (x0, y0), (x1, y1), (0, 100, 200), 2)
            cv2.putText(view, str(mid), (x0 + 2, y0 + 14),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
    cv2.putText(view, "CAMERA VIEW", (5, 14), cv2.FONT_HERSHEY_SIMPLEX,
                0.45, (0, 200, 255), 1)
    cv2.rectangle(view, (0, 0), (vw - 1, vh - 1), (100, 100, 100), 1)
    img[CAM_Y + 10:CAM_Y + 10 + vh, CAM_X + 10:CAM_X + 10 + vw] = view


def draw_dashboard(img, alt, speed, heading, battery, dist, target_label,
                   n_obs, spread, hold):
    cv2.rectangle(img, (DASH_X, DASH_Y),
                  (DASH_X + DASH_W, DASH_Y + DASH_H), (250, 250, 250), -1)
    cv2.rectangle(img, (DASH_X, DASH_Y),
                  (DASH_X + DASH_W, DASH_Y + DASH_H), (180, 180, 180), 2)
    cv2.putText(img, "FLIGHT DASHBOARD", (DASH_X + 10, DASH_Y + 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (60, 60, 60), 2)
    items = [
        ("ALT", "%.2f m" % alt, (0, 0, 0)),
        ("SPD", "%.2f m/s" % speed, (0, 0, 0)),
        ("HDG", "%.0f deg" % heading, (0, 0, 0)),
        ("BATT", "%d%%" % battery,
         (0, 220, 0) if battery > 60 else
         (0, 200, 255) if battery > 25 else (0, 0, 255)),
        ("TARGET", target_label, (0, 0, 200)),
        ("DIST", "%.2f m" % dist, (0, 0, 0)),
    ]
    yy = DASH_Y + 42
    for name, val, col in items:
        cv2.putText(img, "%-5s" % name, (DASH_X + 10, yy),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.50, (100, 100, 100), 1)
        cv2.putText(img, val, (DASH_X + 80, yy), cv2.FONT_HERSHEY_SIMPLEX,
                    0.52, col, 1)
        yy += 20
    if hold > 0:
        cv2.putText(img, "HOLD %d" % hold, (DASH_X + DASH_W - 80, yy - 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 160, 0), 2)
    cv2.putText(img, "OBS %d  SPREAD %dmm" % (n_obs, spread),
                (DASH_X + 10, DASH_Y + DASH_H - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (120, 120, 120), 1)


def draw_floor_plan(img, lo, hi, table, waypoints, wp_i, smooth, i,
                    trail_data, goal_click):
    sx = MAP_W / (hi[0] - lo[0])
    sy = MAP_H / (hi[1] - lo[1])
    scale = min(sx, sy)

    def T(x, z):
        return (int(MAP_X0 + (x - lo[0]) * scale),
                int(MAP_Y0 + MAP_H - (z - lo[1]) * scale))

    cv2.rectangle(img, (MAP_X0 - 5, MAP_Y0 - 5),
                  (MAP_X0 + MAP_W + 5, MAP_Y0 + MAP_H + 5),
                  (50, 50, 50), 2)
    cv2.rectangle(img, T(lo[0], lo[1]), T(hi[0], hi[1]),
                  (245, 245, 240), -1)
    cv2.rectangle(img, T(lo[0], lo[1]), T(hi[0], hi[1]),
                  (0, 0, 0), 2)
    for gx in np.arange(np.ceil(lo[0] * 2) / 2, hi[0], 0.5):
        cv2.line(img, T(gx, lo[1]), T(gx, hi[1]), (225, 225, 220), 1)
    for gz in np.arange(np.ceil(lo[1] * 2) / 2, hi[1], 0.5):
        cv2.line(img, T(lo[0], gz), T(hi[0], gz), (225, 225, 220), 1)
    for mid, v in table.items():
        p = T(v["x"], v["z"])
        r = 8
        b = np.array([[-r, -r], [r, -r], [r, r], [-r, r]], np.int32) + p
        cv2.fillPoly(img, [b], (0, 80, 180))
        cv2.polylines(img, [b], True, (255, 255, 255), 2)
        cv2.putText(img, str(mid), (p[0] + 12, p[1] + 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 140), 2)
    for wi, (wx, wz, _, lab) in enumerate(waypoints):
        p = T(wx, wz)
        col = (0, 180, 0) if wi != wp_i else (0, 255, 0)
        cv2.circle(img, p, 14, col, 3)
        cv2.circle(img, p, 3, col, -1)
        lbl = chr(65 + wi) if wi < 26 else lab
        cv2.putText(img, lbl, (p[0] + 15, p[1] + 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, col, 2)
    if goal_click:
        cv2.circle(img, goal_click, 12, (0, 255, 0), 2)
    pts_arr = []
    for j in range(max(0, i - 800), min(i + 1, len(smooth))):
        if smooth[j] is not None:
            pts_arr.append(T(smooth[j][0], smooth[j][1]))
    if len(pts_arr) >= 2:
        arr = np.array(pts_arr, np.int32).reshape(-1, 2)
        cv2.polylines(img, [arr], False, (150, 150, 150), 2, cv2.LINE_AA)
    return scale, T


def world_bounds(table, waypoints, rows, pad=0.3):
    lo = np.array([np.inf, np.inf])
    hi = np.array([-np.inf, -np.inf])
    for v in table.values():
        lo = np.minimum(lo, [v["x"], v["z"]])
        hi = np.maximum(hi, [v["x"], v["z"]])
    for x, z, _, _ in waypoints:
        lo = np.minimum(lo, [x, z])
        hi = np.maximum(hi, [x, z])
    for r in rows:
        if r:
            lo = np.minimum(lo, [r[1], r[2]])
            hi = np.maximum(hi, [r[1], r[2]])
    lo -= pad
    hi += pad
    return lo, hi


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=
                                 argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", nargs="?", default=None)
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--markers", default=r"D:\Things\vo\marker_positions.json")
    ap.add_argument("--waypoints", default="")
    ap.add_argument("--arrived-m", type=float, default=0.25)
    ap.add_argument("--hold-frames", type=int, default=14)
    ap.add_argument("--fps", type=float, default=10.0)
    ap.add_argument("--frames-out", default="")
    ap.add_argument("--max-frames", type=int, default=0)
    ap.add_argument("--shots", default="", help="render full frames (with 3D "
                   "panel) to a directory, no window")
    args = ap.parse_args()

    table = load_marker_table(args.markers)
    waypoints = parse_waypoints(args.waypoints, table)

    if args.csv and os.path.exists(args.csv):
        rows = load_traj(args.csv)
    elif args.demo or not args.csv:
        rows = synth_traj(table, waypoints)
    else:
        print("csv not found:", args.csv)
        return 1

    lo, hi = world_bounds(table, waypoints, rows)
    smooth = smooth_path(rows)
    print("markers %d  waypoints %d  frames %d  bounds x[%.1f,%.1f] z[%.1f,%.1f]"
          % (len(table), len(waypoints), len(rows), lo[0], hi[0], lo[1], hi[1]))

    headless = bool(args.frames_out) and not bool(args.shots)
    if args.shots:
        os.makedirs(args.shots, exist_ok=True)
    if headless:
        os.makedirs(args.frames_out, exist_ok=True)

    win = "indoor-GPS UAV demo -- ESC quit"
    if not headless and not args.shots:
        cv2.namedWindow(win)
        cv2.resizeWindow(win, WIN_W, WIN_H)

    i = 0
    wp_i = 0
    hold = 0
    status = ""
    playing = True
    battery = 100
    rotor_t = 0.0
    prev_pos = None
    heading = 0.0
    speed = 0.0
    goal_click = None
    K = np.array([[282.5, 0, 160], [0, 290.6, 120], [0, 0, 1]], np.float64)
    dist_k = np.array([-0.015, 0.035, -0.016, -0.007, 0.26])

    def on_mouse(evt, x, y, flags, param):
        nonlocal goal_click
        if evt == cv2.EVENT_LBUTTONDOWN and MAP_X0 <= x <= MAP_X0 + MAP_W:
            if MAP_Y0 <= y <= MAP_Y0 + MAP_H:
                goal_click = (x, y)

    if not headless and not args.shots:
        cv2.setMouseCallback(win, on_mouse)

    t_last = time.time()
    drone_handle = None
    prev_yaw = 0.0
    roll_est = 0.0
    pitch_est = 0.0
    if not headless or args.shots:
        drone_handle = drone3d.init(size=(UAV_W, UAV_H))
        drone3d.use_model()
    while True:
        if hold > 0:
            hold -= 1
            if hold == 0:
                if wp_i >= len(waypoints) - 1:
                    status = "ALL WAYPOINTS REACHED"
                else:
                    wp_i += 1
                    lbl = chr(65 + wp_i) if wp_i < 26 else "N"
                    status = "EN ROUTE -> %s" % lbl

        r = rows[i] if i < len(rows) else None
        sp = smooth[i] if i < len(smooth) else None
        if r and sp:
            altitude = ALT_DEFAULT
            if prev_pos is not None:
                dx = sp[0] - prev_pos[0]
                dz = sp[1] - prev_pos[1]
                heading = bearing_deg(dx, dz)
                speed = math.hypot(dx, dz) * args.fps
            prev_pos = sp
            battery = max(0, battery - 0.015)
            if wp_i < len(waypoints) and status != "ALL WAYPOINTS REACHED":
                tx, tz, _, lab = waypoints[wp_i]
                if float(math.hypot(r[1] - tx, r[2] - tz)) < args.arrived_m:
                    if hold <= 0:
                        hold = args.hold_frames
                        lbl = chr(65 + wp_i) if wp_i < 26 else lab
                        status = "ARRIVED %s" % lbl
        elif r is None and sp:
            prev_pos = sp

        rotor_t += 0.45
        if prev_pos is not None:
            dyaw = heading - prev_yaw
            if dyaw > 180:
                dyaw -= 360
            elif dyaw < -180:
                dyaw += 360
            roll_est = dyaw * 0.18
            pitch_est = speed * -5.0
            prev_yaw = heading
        if not headless:
            img = np.full((WIN_H, WIN_W, 3), 240, np.uint8)
            cv2.rectangle(img, (0, 0), (WIN_W, 64), (30, 30, 30), -1)
            cv2.putText(img, "INDOOR GPS  -  UAV NAVIGATION SIMULATION",
                        (14, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                        (0, 220, 255), 2)
            cv2.putText(img, "marker-based localisation  |  autonomous "
                        "waypoint navigation  |  real-time telemetry",
                        (14, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        (200, 200, 200), 1)
            scale, T = draw_floor_plan(img, lo, hi, table, waypoints, wp_i,
                                       smooth, i, rows, goal_click)
            if sp is not None and r is not None:
                drone_screen = T(sp[0], sp[1])
                heading_rad = math.radians(heading)
                draw_shadow(img, drone_screen[0], drone_screen[1],
                            altitude, scale)
                draw_camera_cone(img, drone_screen[0], drone_screen[1],
                                heading_rad, 70, 40)
                draw_drone(img, drone_screen[0], drone_screen[1], altitude,
                           heading_rad, rotor_t, battery)
                tx, tz, _, tlab = waypoints[wp_i] if wp_i < len(waypoints) \
                    else (sp[0], sp[1], ALT_DEFAULT, "?")
                dist2 = float(math.hypot(r[1] - tx, r[2] - tz))
                target_lbl = chr(65 + wp_i) if wp_i < 26 else tlab
                draw_dashboard(img, altitude, speed, heading, battery, dist2,
                               target_lbl, r[3], int(r[4]), hold)
                if drone_handle:
                    drone3d.draw_panel(drone_handle, img, UAV_X, UAV_Y,
                                       UAV_W, UAV_H, heading, pitch_est,
                                       roll_est, rotor_t, shadow_alpha=0.5,
                                       t=i / max(1.0, args.fps))
                draw_camera_view(img, sp[0], sp[1], altitude, heading_rad,
                                 table, K, dist_k)
            else:
                draw_dashboard(img, ALT_DEFAULT, 0.0, 0.0, battery,
                               0.0, "--", 0, 0, 0)
                cv2.rectangle(img, (CAM_X + 10, CAM_Y + 10),
                              (CAM_X + CAM_W - 10, CAM_Y + CAM_H - 10),
                              (40, 40, 40), -1)
                cv2.putText(img, "CAMERA VIEW", (CAM_X + 20, CAM_Y + 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 100, 100), 1)
            if status:
                cv2.putText(img, status, (MAP_X0, MAP_Y0 - 12),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 180), 2)
            cv2.putText(img, "SPACE pause | arrows step | click goal | ESC quit",
                        (10, WIN_H - 10), cv2.FONT_HERSHEY_SIMPLEX,
                        0.45, (120, 120, 120), 1)
            if args.shots:
                fn = os.path.join(args.shots, "s%06d.png" % i)
                cv2.imwrite(fn, img)
                print("shot %d" % i, end="\r")
                i += 1
                if i >= len(rows):
                    print("shots done (%d) -> %s" % (i, args.shots))
                    return 0
                if args.max_frames and i >= args.max_frames:
                    print("shots done (max) -> %s" % args.shots)
                    return 0
                continue
            cv2.imshow(win, img)
            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q")):
                break
            if key == ord(" "):
                playing = not playing
            if key in (83, 100) and i < len(rows) - 1:
                i += 1
            if key in (81, 97) and i > 0:
                i -= 1
        else:
            fn = os.path.join(args.frames_out, "f%06d.jpg" % i)
            img = np.full((WIN_H, WIN_W, 3), 240, np.uint8)
            scale, T = draw_floor_plan(img, lo, hi, table, waypoints, wp_i,
                                       smooth, i, rows, goal_click)
            if sp is not None and r is not None:
                drone_screen = T(sp[0], sp[1])
                heading_rad = math.radians(heading)
                draw_shadow(img, drone_screen[0], drone_screen[1],
                            altitude, scale)
                draw_camera_cone(img, drone_screen[0], drone_screen[1],
                                heading_rad, 70, 40)
                draw_drone(img, drone_screen[0], drone_screen[1], altitude,
                           heading_rad, rotor_t, battery)
                tx, tz, _, tlab = waypoints[wp_i] if wp_i < len(waypoints) \
                    else (sp[0], sp[1], ALT_DEFAULT, "?")
                dist2 = float(math.hypot(r[1] - tx, r[2] - tz))
                target_lbl = chr(65 + wp_i) if wp_i < 26 else tlab
                draw_dashboard(img, altitude, speed, heading, battery, dist2,
                               target_lbl, r[3], int(r[4]), hold)
                if drone_handle:
                    drone3d.draw_panel(drone_handle, img, UAV_X, UAV_Y,
                                       UAV_W, UAV_H, heading, pitch_est,
                                       roll_est, rotor_t, shadow_alpha=0.5,
                                       t=i / max(1.0, args.fps))
                draw_camera_view(img, sp[0], sp[1], altitude, heading_rad,
                                 table, K, dist_k)
            else:
                draw_dashboard(img, ALT_DEFAULT, 0.0, 0.0, battery,
                               0.0, "--", 0, 0, 0)
                cv2.rectangle(img, (CAM_X + 10, CAM_Y + 10),
                              (CAM_X + CAM_W - 10, CAM_Y + CAM_H - 10),
                              (40, 40, 40), -1)
            cv2.imwrite(fn, img, [cv2.IMWRITE_JPEG_QUALITY, 92])
            i += 1
            if i >= len(rows):
                print("rendered %d frames -> %s" % (i, args.frames_out))
                return 0
            if args.max_frames and i >= args.max_frames:
                return 0
            continue

        if playing:
            t_now = time.time()
            dt = t_now - t_last
            t_last = t_now
            n_step = max(1, int(round(dt * args.fps)))
            i = min(i + n_step, len(rows) - 1)
        if i >= len(rows) - 1:
            playing = False

    if not headless:
        cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())