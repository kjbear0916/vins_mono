"""Synthetic POSITIVE-CONTROL sequence for the VO validation gate.

Renders a scene of glowing points through the ESP32 QVGA calibration K
(320x240), with a perfect straight-line camera translation and zero motion
outside the move phase -- the "clean sequence" the recording script is
supposed to capture on hardware. The gate run on this output is the reference
for what a PASS should look like, and doubles as a no-hardware regression
test.

Phases mirror record_clean_seq.py:
  HOLD0 (static)  ->  MOVE (steady +z translation)  ->  HOLD1 (static)
Output: <prefix>.avi (grayscale MJPG, 16 fps) + <prefix>_meta.json in the
same schema as the recorder, so validate_traj_pass.py --meta works verbatim.

Usage:
  python gen_synth_seq.py --out vo/synth_clean_01.avi [--seed 7]
"""

import argparse
import json

import cv2
import numpy as np

CALIB = r"D:\Things\vo\calibration_esp32_qvga.npz"
FPS = 16.0
HOLD_S = 3.0
STEP = 0.16          # world units per MOVE frame along +z (flow ~6 px)
MOVE_S = 6.0
NOISE = 1.5


def make_scene(rng, n=900):
    z = np.exp(rng.uniform(np.log(1.8), np.log(30), n))
    u = rng.uniform(0, 319, n)
    v = rng.uniform(0, 239, n)
    K = np.load(CALIB)["camera_matrix"]
    x = (u - K[0, 2]) / K[0, 0] * z
    y = (v - K[1, 2]) / K[1, 1] * z
    return np.stack([x, y, z], axis=1).T


def render(K, gray, pts_world, t_wc, rng, noise):
    gray[:] = 0
    X_c = pts_world + t_wc.reshape(3, 1)
    z = X_c[2, :]
    keep = (z > 0.3) & (z < 60)
    if np.count_nonzero(keep) < 20:
        return
    u = K[0, 0] * (X_c[0, keep] / z[keep]) + K[0, 2]
    v = K[1, 1] * (X_c[1, keep] / z[keep]) + K[1, 2]
    vis = (u >= 0) & (u < 320) & (v >= 0) & (v < 240)
    uv = np.round(np.stack([u[vis], v[vis]], axis=1)).astype(int)
    from collections import defaultdict
    pts_at = defaultdict(int)
    for px, py in uv:
        pts_at[(px, py)] += 1
    for (px, py), cnt in pts_at.items():
        glow = int(rng.integers(120, 256)) + 6 * min(cnt, 3)
        rad = int(max(1, round(rng.uniform(2, 5))))
        cv2.circle(gray, (int(px), int(py)), rad, min(glow, 255), -1,
                   cv2.LINE_AA)
    cv2.GaussianBlur(gray, (5, 5), 0, gray)
    gray += rng.normal(0.0, noise, gray.shape).astype(np.float32)


def render_board(K, gray, cells, z_board, t_wc, dark=30.0):
    """Draw a flat chessboard at world z=z_board, fronto-parallel.

    cells = (cols, rows, square, offset3)
    The board's white background is filled first, then dark squares.
    """
    cols, rows, square, off = cells
    zc = z_board + t_wc[2]
    if zc <= 0.3:
        return

    def proj(x, y):
        return (K[0, 0] * x / zc + K[0, 2],
                K[1, 1] * y / zc + K[1, 2])

    x0, y0 = off[0], off[1]
    x1, y1 = x0 + cols * square, y0 + rows * square

    # white background rectangle
    u0, v0 = proj(x0, y0)
    u1, v1 = proj(x1, y1)
    rect = np.array([[u0, v0], [u1, v0], [u1, v1], [u0, v1]])
    cv2.fillPoly(gray, [np.round(rect).astype(np.int32)], 255)

    for j in range(rows):
        for i in range(cols):
            if (i + j) % 2 == 0:
                continue
            w = np.array(
                [[i, j, 0.0], [i + 1, j, 0.0], [i + 1, j + 1, 0.0],
                 [i, j + 1, 0.0]]) * square + off
            w[:, 2] = z_board
            X_c = w + t_wc.reshape(1, 3)
            u, v = proj(X_c[:, 0], X_c[:, 1])
            uv = np.stack([u, v], axis=1)
            if np.isfinite(uv).all():
                cv2.fillPoly(gray, [np.round(uv).astype(np.int32)], dark)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=r"D:\Things\vo\synth_clean_01.avi")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--fps", type=float, default=FPS)
    ap.add_argument("--noise", type=float, default=NOISE)
    ap.add_argument("--step", type=float, default=STEP,
                    help="world units per MOVE frame (controls optical flow)")
    ap.add_argument("--move-s", type=float, default=MOVE_S)
    ap.add_argument("--board", action="store_true",
                    help="render a fronto-parallel chessboard for ATE GT")
    ap.add_argument("--board-grid", default="10x7",
                    help="chessboard squares WxH (cells)")
    ap.add_argument("--board-z", type=float, default=14.0,
                    help="world z of the board plane")
    ap.add_argument("--board-size", type=float, default=4.5,
                    help="board width in world units (square = size/grid_cols)")
    ap.add_argument("--board-px", type=float, default=None,
                    help="projected board-centre u (px); default = image centre")
    ap.add_argument("--board-py", type=float, default=None,
                    help="projected board-centre v (px); default = image centre")
    ap.add_argument("--motion", default="straight",
                    choices=["straight", "back_forth", "jump", "curve",
                             "sway"],
                    help="negative-control trajectories: straight (clean), "
                         "back_forth (P4), jump (P5), curve (P3), "
                         "sway (lateral snake at constant fwd speed)")
    ap.add_argument("--sway-amp", type=float, default=0.30,
                    help="lateral amplitude of the sway motion (world units)")
    ap.add_argument("--sway-cycles", type=float, default=3.0,
                    help="number of full lateral oscillations over MOVE")
    ap.add_argument("--hold-jitter", type=float, default=0.0,
                    help="per-frame random translation to add during HOLD "
                         "phases (world units) -> P7 static-tail FAIL")
    a = ap.parse_args()

    rng = np.random.default_rng(a.seed)
    K = np.load(CALIB)["camera_matrix"]
    scene = make_scene(rng)

    bcols, brows = (int(x) for x in a.board_grid.lower().split("x"))
    bsquare = a.board_size / bcols
    bh = brows * bsquare
    # aim board centre so it projects near image centre at T0 (K principal
    # point is (130, 31) -- off-centre for this QVGA calibration)
    z0 = a.board_z  # world z plane, camera at t_wc=(0,0,0) at T0
    if a.board_px is not None:
        bxc = (a.board_px - K[0, 2]) * z0 / K[0, 0]
        byc = (a.board_py - K[1, 2]) * z0 / K[1, 1]
    else:
        cx = (160.0 - K[0, 2]) * z0 / K[0, 0]
        cy = (120.0 - K[1, 2]) * z0 / K[1, 1]
        bxc, byc = cx, cy
    board_off = np.array([bxc - a.board_size / 2.0, byc - bh / 2.0, 0.0])

    n_hold = int(round(HOLD_S * a.fps))
    n_move = int(round(a.move_s * a.fps))

    gray = np.zeros((240, 320), np.float32)
    t_wc = np.zeros(3)
    writer = cv2.VideoWriter(a.out, cv2.VideoWriter_fourcc(*"MJPG"),
                             a.fps, (320, 240), False)

    phases = [("HOLD0", n_hold, None),
              ("MOVE", n_move, a.step),
              ("HOLD1", n_hold, None)]
    meta_phases = []
    for name, nf, step in phases:
        zsum = []
        disp_sum = 0.0
        for k in range(nf):
            base = step if step is not None else 0.0
            dz = base
            if name == "MOVE" and a.motion == "back_forth":
                # forward first half, back second half  => retreats ~100%
                dz = base if k < nf // 2 else -base
            elif name == "MOVE" and a.motion == "jump":
                # normal walk except a sustained 5-frame burst (3x speed)
                # around k=3/4  => P5 detects a giant single-step jump
                jump0, jumpn = int(nf * 0.70), int(nf * 0.70) + 5
                dz = base * 3.0 if jump0 <= k < jumpn else base
            elif name == "MOVE" and a.motion == "curve":
                # curvature: z straight but x=y kicks following an arc  => P3
                t = k / max(1, nf - 1)
                dz = base
            elif name == "MOVE" and a.motion == "sway":
                # lateral sine snake: fwd speed constant, x oscillates.
                # P3/P4 look at net/path and the dominant axis only, so a
                # low-amplitude snake can stay GREEN even though the rig is
                # not a straight line -- potential protocol blind spot.
                dz = base
                t_wc[0] = a.sway_amp * np.sin(2.0 * np.pi *
                                              a.sway_cycles * k / max(1, nf - 1))
            jit = np.zeros(3)
            if name.startswith("HOLD") and a.hold_jitter > 0.0:
                # P7 negative control: random walk on the camera pose while
                # nominally holding still -> HOLD mean_flow_px exceeds 2
                jit = rng.normal(0.0, a.hold_jitter, size=3)
            t_wc[0] += jit[0]
            t_wc[1] += jit[1]
            t_wc[2] = t_wc[2] - dz + jit[2]
            disp_sum += float(np.hypot(dz + jit[2], np.hypot(jit[0], jit[1])))
            if a.motion == "curve" and name == "MOVE":
                # arc: lateral offset grows quadratically so the path ends
                # far off the forward axis  => net/path clearly < 0.6 (P3)
                t = k / max(1, nf - 1)
                t_wc[0] = 2.5 * a.move_s * a.step * t * t
                t_wc[1] = 0.6 * a.step * t
            render(K, gray, scene, t_wc, rng, a.noise)
            if a.board:
                render_board(K, gray, (bcols, brows, bsquare, board_off),
                             a.board_z, t_wc)
            frame_u8 = np.clip(gray, 0, 255).astype(np.uint8)
            writer.write(frame_u8)
            zc = scene[2] + t_wc[2]
            zok = zc[(zc > 0.3) & (zc < 60)]
            if len(zok):
                zsum.append(float(zok.mean()))
        if disp_sum > 0.0 and zsum:
            mean_flow = float(K[0, 0] * (disp_sum / nf) / np.mean(zsum))
        else:
            mean_flow = 0.0
        meta_phases.append({"name": name, "dropped": 0,
                            "mean_flow_px": round(mean_flow, 3)})
        print("%s : %d frames, mean ~%.2f px" % (name, nf, mean_flow))

    writer.release()

    meta = {"out": a.out, "url": "synthetic", "fps": a.fps,
            "frames": {p[0]: p[1] for p in phases},
            "size": [320, 240], "phases": meta_phases}
    meta_path = a.out.replace(".avi", "_meta.json")
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    print("metadata ->", meta_path)
    print("WROTE %s" % a.out)


if __name__ == "__main__":
    main()