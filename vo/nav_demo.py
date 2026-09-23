"""Semi-autonomous navigation simulation demo for the indoor-GPS project.

Renders a top-view floor plan of the marker room, replays a localisation
trajectory (the localise_video.py CSV format) as a moving dot, and runs the
"navigation decision" loop on top of it: the operator / professor only moves
the hand-held camera, the system computes b/heading to the next waypoint,
remaining distance, arrival (state machine) and auto-advance -- a demo of
navigation logic without any motor control.

Input: the localise_video.py CSV (header: frame,x,y,z,n_obs,n_ambiguous,
spread_x_mm,spread_y_mm,spread_z_mm,conditioned,marker_ids). Rows with no
position (x empty) become 1-2 frame "gap" in the replay.

If --demo is given (or the positional CSV is missing) a synthetic realistic
walk through the marker waypoints is generated and replayed instead, so the
UI can be exercised before real hardware data exists.

Waypoints come from --waypoints: a comma-separated list of marker ids
("1,3,0") or explicit "x,z" pairs. Default: every marker id in the JSON
table, in ascending order. Clicking on the map appends a temporary goal.

Status line shows: frame, position, current target label, remaining
distance, target bearing (deg from world +X axis), arrival hold count and
the state-machine message (已到達 / 前往下一個目標).

Controls: SPACE play/pause, <- -> single step, click set goal, ESC quit.

--frames-out DIR renders every frame to DIR/fNNNNNN.jpg (headless, no
window) -- used for smoke tests and offline recording.
"""
import argparse
import csv
import json
import os
import time

import cv2
import numpy as np

ARRIVED_TEXT_CN = "已到達 {label} - 前往 {next}"
FINAL_TEXT_CN = "所有目標已到達"

WAYPOINT_LABELS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def load_marker_table(path):
    with open(path, encoding="utf-8") as fh:
        d = json.load(fh)
    return {int(k): {"x": float(v["x"]), "z": float(v["z"])}
            for k, v in d.items() if k.lstrip("-").isdigit()}


def parse_waypoints(spec, table):
    out = []
    if spec:
        for part in spec.replace(" ", "").split(","):
            if ":" in part:
                kind, val = part.split(":", 1)
                if kind == "id":
                    mid = int(val)
                    if mid in table:
                        out.append((float(table[mid]["x"]),
                                    float(table[mid]["z"]),
                                    "M%d" % mid))
                    continue
            try:
                x, z = (float(v) for v in part.split(","))
                out.append((x, z, "G"))
            except ValueError:
                pass
    if not out:
        for mid in sorted(table):
            out.append((table[mid]["x"], table[mid]["z"], "M%d" % mid))
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


def synth_traj(table, waypoints, n=520, fps_rev=8.0, speed=0.30,
               seed=11):
    rng = np.random.default_rng(seed)
    pts = [(wp[0], wp[1]) for wp in waypoints]
    xs, zs, n_obs = [], [], []
    cur = np.array([pts[0][0], pts[0][1]], np.float64)
    i_wp = 0
    step = speed / fps_rev
    for _ in range(n):
        tgt = np.array(pts[i_wp], np.float64)
        d = np.linalg.norm(tgt - cur)
        if d < step:
            cur = tgt.copy()
            i_wp = (i_wp + 1) % len(pts)
        else:
            cur = cur + (tgt - cur) / d * (step * rng.uniform(0.85, 1.15))
        cur += rng.normal(0.0, 0.012, 2)
        xs.append(cur[0])
        zs.append(cur[1])
        n_obs.append(0 if rng.random() < 0.05 else int(rng.choice([1, 2])))
    rows = []
    for i, (xz, zo) in enumerate(zip(zip(xs, zs), n_obs)):
        if zo == 0:
            rows.append(None)
            continue
        rows.append((i, xz[0], xz[1], zo, float(rng.uniform(5, 25))))
    return rows


def world_bounds(table, waypoints, rows, pad=0.25):
    lo = np.array([np.inf, np.inf])
    hi = np.array([-np.inf, -np.inf])
    for v in table.values():
        lo = np.minimum(lo, [v["x"], v["z"]])
        hi = np.maximum(hi, [v["x"], v["z"]])
    for x, z, _ in waypoints:
        lo = np.minimum(lo, [x, z])
        hi = np.maximum(hi, [x, z])
    for r in rows:
        if r:
            lo = np.minimum(lo, [r[1], r[2]])
            hi = np.maximum(hi, [r[1], r[2]])
    lo -= pad
    hi += pad
    return lo, hi


def bearing_deg(dx, dz):
    return (np.degrees(np.arctan2(dz, dx)) + 360.0) % 360.0


def render(rows, i, table, waypoints, lo, hi, args, wp_i, hold,
           status, goal_click, trail):
    W, H = 900, 780
    s = min((W - 120) / (hi[0] - lo[0]), (H - 110) / (hi[1] - lo[1]))

    def T(x, z):
        return (int(60 + (x - lo[0]) * s), int(H - 60 - (z - lo[1]) * s))

    img = np.full((H, W, 3), 245, np.uint8)
    cv2.rectangle(img, T(lo[0], lo[1]), T(hi[0], hi[1]), (0, 0, 0), 2)
    for gx in np.arange(np.ceil(lo[0]), hi[0], 0.5):
        cv2.line(img, T(gx, lo[1]), T(gx, hi[1]), (215, 215, 215), 1)
    for gz in np.arange(np.ceil(lo[1]), hi[1], 0.5):
        cv2.line(img, T(lo[0], gz), T(hi[0], gz), (215, 215, 215), 1)

    for mid, v in table.items():
        mx, mz = v["x"], v["z"]
        p = np.array(T(mx, mz), np.int32)
        r = 9
        b = np.array([[-r, -r], [r, -r], [r, r], [-r, r]], np.int32) + p
        cv2.polylines(img, [b], True, (0, 0, 255), 2)
        cv2.putText(img, str(mid), (p[0] + 13, p[1] + 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 40, 40), 2)

    for wi, (wx, wz, lab) in enumerate(waypoints):
        p = T(wx, wz)
        col = (0, 210, 0) if wi != wp_i else (0, 255, 0)
        cv2.circle(img, p, 10, col, -1)
        cv2.circle(img, p, 10, (0, 0, 0), 1)
        cv2.putText(img, WAYPOINT_LABELS[wi] if args.labels
                    else lab, (p[0] + 14, p[1] + 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, col, 2)

    if goal_click and wp_i < len(waypoints) <= 0:
        px, py = goal_click
        cv2.circle(img, (px, py), 12, (0, 255, 0), 2)

    if trail:
        pts = np.array([T(x, z) for x, z in trail], np.int32).reshape(-1, 2)
        cv2.polylines(img, [pts], False, (130, 130, 130), 2)

    r = rows[i] if i < len(rows) else None
    if r:
        px, py = T(r[1], r[2])
        cv2.circle(img, (px, py), 9, (0, 140, 255), -1)
        cv2.circle(img, (px, py), 9, (0, 0, 0), 1)
        if wp_i < len(waypoints):
            tx, tz, _ = waypoints[wp_i]
            ax, ay = T(tx, tz)
            d = float(np.hypot(r[1] - tx, r[2] - tz))
            L = min(46.0, max(20.0, d * s))
            u = np.array([tx - r[1], tz - r[2]])
            u /= np.linalg.norm(u)
            tip = np.array([px, py]) + u * L
            orth = np.array([-u[1], u[0]]) * L * 0.22
            cv2.arrowedLine(img, (px, py), tuple(tip.astype(int)),
                            (0, 140, 255), 3, cv2.LINE_AA, 0, 0.35)
            cv2.line(img, (px, py), tuple((tip + orth).astype(int)),
                     (0, 140, 255), 2)
            cv2.line(img, (px, py), tuple((tip - orth).astype(int)),
                     (0, 140, 255), 2)

    cv2.rectangle(img, (0, 0), (W, 60), (240, 240, 240), -1)
    pos_txt = "(%6.2f, %6.2f)" % (r[1], r[2]) if r else "--"
    base = "frame %5d   pos %s" % (i, pos_txt)
    cv2.putText(img, base, (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                (0, 0, 0), 2)
    if r:
        cv2.putText(img, "obs %d  spread %d mm" % (r[3], r[4]),
                    (10, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (80, 80, 80), 1)
        if wp_i < len(waypoints):
            tx, tz, lab = waypoints[wp_i]
            d = float(np.hypot(r[1] - tx, r[2] - tz))
            brng = bearing_deg(tx - r[1], tz - r[2])
            txt = "target %s  %.2f m  bearing %.0f deg (+X=0)" % (
                lab, d, brng)
            cv2.putText(img, txt, (230, 20), cv2.FONT_HERSHEY_SIMPLEX,
                        0.6, (0, 0, 255), 2)
    if status:
        cv2.rectangle(img, (0, 60), (W, 108), (255, 255, 220), -1)
        cv2.putText(img, status, (10, 92), cv2.FONT_HERSHEY_SIMPLEX,
                    0.85, (0, 0, 0), 2)
        if hold > 0:
            cv2.putText(img, "hold %d" % hold, (W - 110, 92),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 120, 0), 2)
    cv2.putText(img, "SPACE pause | arrows step | click new goal | ESC quit",
                (10, H - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                (100, 100, 100), 1)
    return img


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=
                                 argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", nargs="?", default=None)
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--markers", default=r"D:\Things\vo\marker_positions.json")
    ap.add_argument("--waypoints", default="")
    ap.add_argument("--arrived-m", type=float, default=0.25)
    ap.add_argument("--hold-frames", type=int, default=12)
    ap.add_argument("--fps", type=float, default=10.0)
    ap.add_argument("--labels", action="store_true",
                    help="label waypoints A/B/C instead of marker ids")
    ap.add_argument("--frames-out", default="")
    ap.add_argument("--max-frames", type=int, default=0)
    args = ap.parse_args()

    table = load_marker_table(args.markers)
    waypoints = parse_waypoints(args.waypoints, table)

    if args.csv and os.path.exists(args.csv):
        src = args.csv
        rows = load_traj(src)
    elif args.demo or not args.csv:
        src = None
        rows = synth_traj(table, waypoints)
    else:
        print("csv not found:", args.csv)
        return 1

    lo, hi = world_bounds(table, waypoints, rows)
    print("markers %s  waypoints %s  frames %d  bounds x[%.1f,%.1f] z[%.1f,%.1f]"
          % (sorted(table), waypoints, len(rows), lo[0], hi[0], lo[1], hi[1]))

    headless = bool(args.frames_out)
    if headless:
        os.makedirs(args.frames_out, exist_ok=True)

    win = "nav sim demo -- ESC quit"
    if not headless:
        cv2.namedWindow(win)
        cv2.resizeWindow(win, 900, 780)

    i = 0
    wp_i = 0
    hold = 0
    status = ""
    playing = True
    trail = []
    goal_click = None

    def on_mouse(evt, x, y, flags, param):
        nonlocal goal_click
        if evt == cv2.EVENT_LBUTTONDOWN:
            goal_click = (x, y)

    if not headless:
        cv2.setMouseCallback(win, on_mouse)

    t_last = time.time()
    while True:
        if hold > 0:
            hold -= 1
            if hold == 0:
                if wp_i >= len(waypoints) - 1:
                    status = FINAL_TEXT_CN
                else:
                    wp_i += 1
                    status = ARRIVED_TEXT_CN.format(
                        label=WAYPOINT_LABELS[wp_i - 1]
                        if args.labels else "?" ,
                        next=WAYPOINT_LABELS[wp_i] if args.labels else "next")

        r = rows[i] if i < len(rows) else None
        if r:
            trail.append((r[1], r[2]))
            if len(trail) > 4000:
                trail.pop(0)
            if wp_i < len(waypoints) and status != FINAL_TEXT_CN:
                tx, tz, lab = waypoints[wp_i]
                if float(np.hypot(r[1] - tx, r[2] - tz)) < args.arrived_m:
                    if hold <= 0:
                        hold = args.hold_frames
                        status = ("已到達 %s" % lab)

        img = render(rows, i, table, waypoints, lo, hi, args, wp_i, hold,
                     status, goal_click, trail)

        if headless:
            fn = os.path.join(args.frames_out, "f%06d.jpg" % i)
            cv2.imwrite(fn, img, [cv2.IMWRITE_JPEG_QUALITY, 90])
            i += 1
            if i >= len(rows):
                print("rendered %d frames -> %s" % (i, args.frames_out))
                return 0
            if args.max_frames and i >= args.max_frames:
                return 0
            continue

        cv2.imshow(win, img)
        key = cv2.waitKey(1) & 0xFF
        if key in (27, ord("q")):
            break
        if key == ord(" "):
            playing = not playing
        if key in (83, 100) and i < len(rows):      # right / D: step
            i += 1
        if key in (81, 97) and i > 0:               # left / A: step back
            i -= 1
        if playing:
            t_now = time.time()
            dt = t_now - t_last
            t_last = t_now
            n_step = max(1, int(round(dt * args.fps)))
            i = min(i + n_step, len(rows) - 1)
        if i >= len(rows) - 1:
            playing = False

    cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())