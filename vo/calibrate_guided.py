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
  NEAR/MID/FAR   depth buckets, each axis normalised by its own frame
                 dimension: NEAR = board spans >=70% of frame width OR
                 >=70% of frame height, MID 35-70%, FAR <35%. Comparing the
                 vertical span against the *horizontal* frame width made
                 NEAR unreachable on a 6x5 board in QVGA (224px tall puts
                 the inner corners ~8px from the top/bottom edges, so
                 detection fails before the bucket can ever turn green).
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
F_W, F_H = 320, 240  # the stream (live and offline) is fixed QVGA
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


_CLAHE = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(4, 4))


def find_board(gray, pattern):
    """Locate the chessboard with a glare / screen-moire fallback chain.

    findChessboardCornersSB is tried first and on every preprocessing pass.
    The classic detector was silently the weak link here: on these QVGA views
    it "succeeds" with corners displaced by ~5 px, and the planar solve then
    lands on fx=134-163 against a truth of 474 with RMS 4.95 -- for every
    noise level and with or without the JPEG wire. SB gives RMS 0.32 and fx
    within 2% on the identical frames, so a solved calibration that disagrees
    with the truth was the detector, not the operator.

    A board shown on a display additionally loses contrast to specular
    reflection and LCD subpixel moire, so each pass is retried on CLAHE and on
    an adaptive-threshold binarisation before giving up. Returns
    (found, corners, method) with method in {"sb", "sb-clahe", "sb-adaptive",
    "classic", "classic-clahe", "classic-adaptive", "-"}.
    """
    chains = (
        ("", gray),
        ("-clahe", _CLAHE.apply(gray)),
        ("-adaptive", cv2.adaptiveThreshold(gray, 255,
                                            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                            cv2.THRESH_BINARY, 11, 2)),
    )
    for suffix, img in chains:
        try:
            found, cc = cv2.findChessboardCornersSB(img, pattern)
        except cv2.error:
            found, cc = False, None
        if found:
            return True, cc, "sb" + suffix
    for suffix, img in chains:
        found, cc = cv2.findChessboardCorners(img, pattern)
        if found:
            return True, cc, "classic" + suffix
    return False, None, "-"


def final_gates(K, rms, z_ok=True):
    """Final calibration gates as (name, ok) pairs.

    Square-pixel assumption: fx must match fy. A stretched display (image
    viewer filling the screen instead of letterboxing) or non-square print
    scaling makes the cells rectangular, which biases fx against fy and
    leaves the residual to be absorbed by the distortion terms -- the
    signature is fx/fy far from 1 with a garbage dist and high rms, not a
    plausible focal. Measured 798.7/645.0 = 1.24 on a 320x240 QVGA stream.
    """
    fx, fy = float(K[0, 0]), float(K[1, 1])
    cx = float(K[0, 2])
    hfov = 2.0 * math.degrees(math.atan(cx / max(1e-6, fx)))
    aniso = fx / max(1e-6, fy)
    gates = [
        ("rms %.3f < 2.0" % rms, rms < 2.0),
        ("fx  %.0f in [200,1200]" % fx, 200.0 <= fx <= 1200.0),
        ("HFOV %.1f deg in [25,75]" % hfov, 25.0 <= hfov <= 75.0),
        ("fx/fy %.3f in [0.90,1.10] (square cells)" % aniso,
         0.90 <= aniso <= 1.10),
    ]
    return gates, aniso, hfov


_OBJECT_GRID_CACHE = {}


def object_grid(pattern, square):
    """Board-plane object points for one pattern, as (N,3) float64."""
    key = (tuple(pattern), float(square))
    if key not in _OBJECT_GRID_CACHE:
        cols, rows = pattern
        g = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2) * float(square)
        _OBJECT_GRID_CACHE[key] = np.column_stack(
            [g, np.zeros(cols * rows)]).astype(np.float64)
    return _OBJECT_GRID_CACHE[key]


def canonical_corners(cc, pattern, square=30.0):
    """Reorder detected corners into a fixed row-major order, or None.

    findChessboardCornersSB does not hold one corner order across poses: on
    this pose set it numbered the same 20 points in order on some frames and
    reversed on others (the in-plane angle alternated 0 / 180 between adjacent
    pitches while the classic detector held at 0). Every misnumbered corner
    then takes the wrong object point, and the planar solve collapses -- RMS
    3.3 and fx 77 against a truth of 474, with no image quality problem to
    explain it. board_pose reads ang / tilt / cell out of this same order,
    which is why the tilt requirement broke at the same moment.

    Sorting the cloud is not enough: a plain lexsort assumes the first `cols`
    points form a row, and under tilt they do not, which silently inflated the
    measured pixels-per-square to 84 where the truth was 37 and pushed every
    near pose out through the size gate. So the cloud is instead *quantised
    onto a cols x rows lattice* in its own principal axes, and each point is
    placed at the cell it lands in. That either fills all cols*rows cells
    exactly once, which proves the numbering, or it does not fit and the frame
    is refused rather than recorded wrong.

    The board is 180-degree symmetric, so which end is row 0 is arbitrary --
    but it has to be the *same* arbitrary choice for every sample, which
    ascending projection guarantees.
    """
    pts = cc.reshape(-1, 2).astype(np.float64)
    cols, rows = pattern
    q = pts - pts.mean(axis=0)
    vt = lattice_axes(cc)
    a, b = q @ vt[0], q @ vt[1]

    best = None
    for ai, bi, na, nb in ((a, b, cols, rows), (b, a, rows, cols)):
        span_a = float(ai.max() - ai.min())
        span_b = float(bi.max() - bi.min())
        if span_a < 1e-6 or span_b < 1e-6:
            continue
        step_a, step_b = span_a / (na - 1), span_b / (nb - 1)
        ca = np.rint((ai - ai.min()) / step_a).astype(np.int64)
        rb = np.rint((bi - bi.min()) / step_b).astype(np.int64)
        if ca.min() < 0 or ca.max() >= na or rb.min() < 0 or rb.max() >= nb:
            continue
        idx = rb * na + ca
        if len(np.unique(idx)) != na * nb:
            continue
        resid = float(np.abs(ai - ai.min() - ca * step_a).sum()
                      + np.abs(bi - bi.min() - rb * step_b).sum())
        if best is None or resid < best[0]:
            out = np.empty((na * nb, 2))
            out[idx] = pts
            best = (resid, out, na, nb)

    if best is None:
        return None
    _, out, na, nb = best
    if (na, nb) != (cols, rows):        # came out transposed
        out = out.reshape(nb, na, 2).transpose(1, 0, 2).reshape(-1, 2)
    return out.reshape(-1, 1, 2)


def lattice_axes(cc):
    """Principal axes of the corner cloud, pinned to the image axes.

    SVD leaves each row of vt up to a sign, and the sign follows the order the
    points arrived in, so an unpinned "ascending" end flipped between frames
    and the same board scored 0 then 180 degrees of in-plane rotation from one
    pose to the next. Anchoring on +x and +y makes the convention "left to
    right, top to bottom" instead of whatever the factorisation felt like this
    frame.
    """
    q = cc.reshape(-1, 2).astype(np.float64)
    q = q - q.mean(axis=0)
    _, _, vt = np.linalg.svd(q, full_matrices=False)
    for axis, comp in ((0, 0), (1, 1)):
        e = vt[axis]
        for c in (comp, 1 - comp):
            if abs(e[c]) > 1e-9:
                if e[c] < 0:
                    vt[axis] = -e
                break
    return vt


def lattice_ang_deg(cc):
    """In-plane rotation of the board's 5-corner axis, in [0, 180).

    Taken off the principal axis rather than the first row's endpoint
    difference. A pitched board tilts each row by a hair -- 1e-5 degrees at
    these depths -- and the sign of that hair flips between renders, so
    arctan2 handed back -0.00001 and the modulo wrapped it to 179.99999. That
    is the same board at the same angle, yet it landed in a different dedupe
    bucket every time and read as detector instability.
    """
    e1 = lattice_axes(cc)[0]
    return float(np.degrees(np.arctan2(e1[1], e1[0])) % 180.0)


def draw_corners(img, pattern, cc):
    """Overlay the corners, tolerating an order cv2 cannot draw.

    drawChessboardCorners walks the pattern out of corner 0 and asserts
    internally, so one transposed or duplicated numbering takes the whole
    capture down with it. The overlay is diagnostic; losing it is cheaper than
    losing the run.
    """
    try:
        cv2.drawChessboardCorners(img, pattern, cc, True)
    except cv2.error:
        cv2.rectangle(img, (0, 0), (319, 239), (0, 0, 255), 1)


def board_tilt_deg(cc, pattern, square=30.0):
    """Angle in degrees between the board plane and the image plane.

    From the object-grid homography: the board normal is r1 x r2 with
    r1, r2 the first two columns of K^-1 H.

    This replaces the old |top_row - bot_row| / (top_row + bot_row) ratio,
    which was not a usable gate. That measure reaches 0.02 at a 52 degree
    pitch and needs 70-80 degrees to reach the 0.12 threshold, so the REQ
    panel demanded poses no one can hold by hand -- and it looked like the
    detector had gone deaf to tilt once SB replaced the classic one. Degrees
    off fronto-parallel is what an operator can actually judge and aim for.
    """
    src = object_grid(pattern, square)[:, :2].astype(np.float32)
    dst = cc.reshape(-1, 2).astype(np.float32)
    H, _ = cv2.findHomography(src, dst, 0)
    if H is None or not np.isfinite(H).all():
        return 0.0
    k0 = np.array([[FX_GUESS, 0.0, 160.0], [0.0, FX_GUESS, 120.0],
                   [0.0, 0.0, 1.0]])
    M = np.linalg.inv(k0) @ (H / H[2, 2])
    nrm = np.cross(M[:, 0], M[:, 1])
    ln = float(np.linalg.norm(nrm))
    if ln < 1e-12:
        return 0.0
    nrm = nrm / ln
    return math.degrees(math.acos(min(1.0, abs(float(nrm[2])))))


def board_pose(cc, pattern, square=30.0):
    """Return (z_cm, rot_deg_inplane, tilt_deg, loc_cell) for dedupe bins.

    z_cm       rough depth from average pixels-per-square (no K needed)
    rot_deg    in-plane rotation of the first board row, 0..180
    tilt_deg   angle between the board plane and the image plane
    loc_cell   (col,row) in the 3x3 frame grid the board centroid lands in
    """
    cc = cc.reshape(-1, 2)
    cols, rows = pattern
    row_pts = [cc[i * cols:(i + 1) * cols] for i in range(rows)]
    ppm = float(np.mean([
        np.linalg.norm(row_pts[r][1:] - row_pts[r][:-1], axis=1).mean()
        for r in range(rows)]))
    z_cm = FX_GUESS * square / ppm / 10.0
    ang = lattice_ang_deg(cc)
    tilt_deg = board_tilt_deg(cc, pattern, square)
    h, w = F_H, F_W  # stream is fixed QVGA
    cy = int(cc.mean(axis=0)[1] / (h / 3))
    cx = int(cc.mean(axis=0)[0] / (w / 3))
    return z_cm, ang, tilt_deg, (min(cx, 2), min(cy, 2))


def depth_label(mn, mx, pattern=(5, 4), frame_w=320, frame_h=240):
    """Bucket a pose by how much of the frame the board covers.

    mn/mx are the *inner-corner* extent that findChessboardCorners returns,
    but what the operator controls (and what "near" means) is how much of the
    frame the *board* covers. A C x R inner-corner pattern has (C+1) x (R+1)
    outer squares, and its inner extent spans (C-1) x (R-1) of them, so the
    outer extent is the inner extent scaled by (C+1)/(C-1) and (R+1)/(R-1).

    Without that scale-up the gate is mathematically unreachable on a 6x5
    board in QVGA: the inner corners can span at most 4/6 = 0.667 of the
    frame width (3/5 = 0.600 of its height) even when the board fills the
    frame edge to edge, so the NEAR gate at 0.70 could never turn green at
    any camera distance. Each axis is normalised by its own frame dimension
    so a board taller than the frame is wide still buckets on the vertical.
    """
    cols, rows = pattern
    fx = float(cols + 1) / float(cols - 1)
    fy = float(rows + 1) / float(rows - 1)
    ratio_x = float(mx[0] - mn[0]) * fx / frame_w
    ratio_y = float(mx[1] - mn[1]) * fy / frame_h
    ratio = max(ratio_x, ratio_y)
    if ratio >= 0.70:
        return "NEAR"
    if ratio >= 0.35:
        return "MID"
    return "FAR"


def corner_margin(xys):
    return min(float(xys[:, 0].min()), (F_W - 1) - xys[:, 0].max(),
               float(xys[:, 1].min()), (F_H - 1) - xys[:, 1].max())


def bucket_for(depth, ang, tilt_deg, cell):
    """The dedupe key the live tool, the pose generator and the offline
    re-calibrator must share. It bins depth, in-plane rotation (wrapped so
    179.9 and 0.1 are the same bin), tilt and the 3x3 coverage cell."""
    return (depth, round(ang / 22.5) * 22.5 % 180.0,
            round(tilt_deg / 5.0) * 5.0, cell)


def classify_detection(cc, pattern, square, ppm_min=8.0, ppm_max=60.0):
    """Run the acceptance chain shared by every collector.

    Takes freshly-detected corners and returns a dict. A dict with
    `reject` set names why the frame must not be recorded ("lattice",
    "off-frame" or "bad-size"); one without it also carries the canonicalised
    corners, the dedupe bucket and the measures the REQ panel counts, so
    every collector -- live HUD, synthetic dry run, offline clip -- grades
    the same way.
    """
    cc = canonical_corners(cc, pattern, square)
    if cc is None:
        return dict(reject="lattice")
    z_cm, ang, tilt_deg, cell = board_pose(cc, pattern, square)
    xys = cc.reshape(-1, 2)
    mn, mx = xys.min(axis=0), xys.max(axis=0)
    in_frame = mn[0] >= 2 and mx[0] <= 317 and mn[1] >= 2 and mx[1] <= 237
    ppm = FX_GUESS * square / (z_cm * 10.0)
    if not in_frame:
        return dict(reject="off-frame")
    if not (ppm_min <= ppm <= ppm_max):
        return dict(reject="bad-size", ppm=ppm)
    depth = depth_label(mn, mx, pattern)
    return dict(bucket=bucket_for(depth, ang, tilt_deg, cell), cc=cc,
                z_cm=z_cm, tilt_deg=tilt_deg, depth=depth, cell=cell,
                margin=corner_margin(xys))


class REQCollector:
    """Collect accept-classified frames into the REQ-panel state.

    Exactly the measures the HUD counts: edge-fill, tilted poses, the three
    depth bins, all nine 3x3 cells and the sample count. Making both the live
    loop and the offline video path mutate this one object is what keeps the
    two tools from drifting apart on the definition of a good session.
    """

    def __init__(self, obj, samples_n=30, tilt_need=2, tilt_min=15.0,
                 edge_px=24.0):
        self.obj = np.asarray(obj, np.float32)
        self.samples_n = samples_n
        self.tilt_need = tilt_need
        self.tilt_min = tilt_min
        self.edge_px = edge_px
        self.samples = {}
        self.n_add = 0
        self.edge_near = False
        self.tilt_count = 0
        self.depth_bins = {"NEAR": False, "MID": False, "FAR": False}
        self.uncovered_cells = {(c, r) for r in range(3) for c in range(3)}

    def add(self, d):
        """d comes from classify_detection(). True when it became a new
        sample, False on a dedupe hit."""
        bucket = d["bucket"]
        if bucket in self.samples:
            return False
        self.samples[bucket] = (self.obj.copy(),
                                d["cc"].astype(np.float32), d["z_cm"])
        self.n_add += 1
        self.uncovered_cells.discard(d["cell"])
        self.depth_bins[d["depth"]] = True
        if d["margin"] <= self.edge_px:
            self.edge_near = True
        if d["tilt_deg"] >= self.tilt_min:
            self.tilt_count += 1
        return True

    def missing(self):
        return missing_list(self.edge_near, self.tilt_count, self.tilt_need,
                            self.depth_bins, self.uncovered_cells, self.n_add,
                            self.samples_n)

    def done(self):
        return not self.missing()


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
    row("tilt >=%ddeg (%d)" % (tilt_need, tilt_count),
        tilt_count >= tilt_need)
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


def synth_frames(square, samples_n, fx=474.0, seed=7, noise=3.0):
    """Yield synthetic frames for an offline rehearsal (no camera, no HTTP).

    The MJPEG path is the one the physical session depends on, and a real
    stream already covers it. What still needs rehearsing offline is the
    gate/solve/save chain; feeding frames straight in leaves the loop, the
    gates and the solve byte-identical to the field path. (The local HTTP
    path's earlier 2 fps turned out to be a parser misalignment in
    video_source.mjpeg_frames -- the `\r\n\r\n` terminator search latched
    onto random hits inside the JPEG body; fixed, and verified byte-exact by
    mjpeg_replay_test.py.)
    """
    import gen_guided_pose_set as gp
    import gen_synth_calib_shoot as gs

    K = np.array([[fx, 0, 160.0], [0, fx, 120.0], [0, 0, 1]], np.float64)
    dist = np.array([-0.18, 0.05, 0.0, 0.0, 0.0], np.float64)
    poses = gp.build(K, dist, square, 24.0, 0.12, 8.0, 60.0, samples_n,
                     noise=noise)
    if not gp.check(poses):
        raise SystemExit("synthetic pose set cannot satisfy the REQ panel")
    local = gs.board_corners_local()
    rng = np.random.default_rng(seed)
    while True:
        for p in poses:
            gray = np.zeros((gs.H, gs.W), np.uint8)
            R = gp.rot(p["pitch"], p["yaw"], p.get("roll", 0))
            t = gp.project_centre(p["z"], p["pu"], p["pv"], K)
            if not gs.render_board(gray, K, dist, local, R, t):
                continue
            g = gray.astype(np.float32)
            if noise > 0:
                g += rng.normal(0.0, noise, g.shape)
            frame = np.clip(g, 0, 255).astype(np.uint8)
            yield cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)


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
    ap.add_argument("--tilt-min", type=float, default=15.0,
                    help="degrees off fronto-parallel for a pose to count as "
                         "tilted. The old metric was a top-row/bottom-row "
                         "length ratio needing 70-80 deg of pitch to reach "
                         "0.12, so this gate was unreachable in the hand")
    ap.add_argument("--tilt-count", type=int, default=2,
                    help="how many tilted poses are required")
    ap.add_argument("--z-hint", type=float, default=None,
                    help="metres; final gate cross-checks median board distance")
    ap.add_argument("--ppm-min", type=float, default=8.0,
                    help="reject far poses below this pixels-per-square")
    ap.add_argument("--ppm-max", type=float, default=60.0,
                    help="reject near poses above this pixels-per-square. The "
                         "NEAR bucket itself needs ~37 px/square on a 6x5 "
                         "board, so a ceiling at 38 left no room to record "
                         "the near poses the REQ panel demands.")
    ap.add_argument("--synth", action="store_true",
                    help="rehearse offline against a synthetic pose set "
                         "instead of a camera; the saved intrinsics then only "
                         "check the solver against the truth that drew the "
                         "frames, not the hardware")
    ap.add_argument("--synth-fx", type=float, default=474.0,
                    help="focal the synthetic frames are drawn with")
    a = ap.parse_args()

    os.makedirs(a.save_dir, exist_ok=True)
    cols, rows = parse_pattern(a.pattern)
    pattern = (cols, rows)
    obj = np.zeros((cols * rows, 3), np.float32)
    obj[:, :2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2) * a.square

    win = "guided calib -- q quit, a force-add, s save"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win, 1180, 600)

    if a.synth:
        print("SYNTHETIC SOURCE (no camera, no network)  truth fx=%.0f "
              "square=%.1fmm -- recovered intrinsics are a self-consistency "
              "check only" % (a.synth_fx, a.square), flush=True)
        frames = synth_frames(a.square, a.samples, a.synth_fx)
    else:
        frames = stream_frames(a.url)

    samples = {}          # bucket-tuple -> (obj_points entry, frame corners, z_cm)
    uncovered_cells = {(c, r) for r in range(3) for c in range(3)}
    depth_bins = {"NEAR": False, "MID": False, "FAR": False}
    edge_near = False
    tilt_count = 0
    n_add = 0
    n_seen = 0
    saved = 0
    last_stat = ""
    det_hist = {}
    last_method = "-"
    reason_hist = {}
    ppm_range = [None, None]
    t_prev = time.time()

    for img in frames:
        t_now = time.time()
        fps = 1.0 / max(1e-6, t_now - t_prev)
        t_prev = t_now
        n_seen += 1

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        found, cc, det_method = find_board(gray, pattern)
        is_sharp = blur >= a.blur_min
        if det_method != "-":
            det_hist[det_method] = det_hist.get(det_method, 0) + 1
            last_method = det_method
        if not found:
            last_method = "-"

        if found:
            if not det_method.startswith("sb"):
                # The classic detector's corners are ~5 px out on these views.
                # Showing them is useful, recording them is not: one bad sample
                # drags the whole solve (RMS 3.34, fx 77 against 474).
                last_stat = "skip %s -- corners not subpixel" % det_method
                draw_corners(img, pattern, cc)
                continue
            cc = canonical_corners(cc, pattern, a.square)
            if cc is None:
                last_stat = "reject lattice -- corners are not a 5x4 grid"
                reason_hist["bad-lattice"] = reason_hist.get("bad-lattice", 0) + 1
                continue
            z_cm, ang, tilt_deg, cell = board_pose(cc, pattern, a.square)
            xys = cc.reshape(-1, 2)
            mn, mx = xys.min(axis=0), xys.max(axis=0)
            depth = depth_label(mn, mx, pattern)

            in_frame = mn[0] >= 2 and mx[0] <= 317 and mn[1] >= 2 and mx[1] <= 237
            ppm = FX_GUESS * a.square / (z_cm * 10.0)
            ppm_ok = a.ppm_min <= ppm <= a.ppm_max
            gate_ok = is_sharp and in_frame and ppm_ok
            if gate_ok:
                bucket = bucket_for(depth, ang, tilt_deg, cell)
            else:
                bucket = None

            added = False
            if not is_sharp:
                reason_hist["blur"] = reason_hist.get("blur", 0) + 1
            if not in_frame:
                reason_hist["off-frame"] = reason_hist.get("off-frame", 0) + 1
            if not ppm_ok:
                reason_hist["bad-size"] = reason_hist.get("bad-size", 0) + 1
                ppm_range = [ppm_range[0] if ppm_range[0] is not None else ppm,
                             ppm_range[1] if ppm_range[1] is not None else ppm]
                ppm_range[0] = min(ppm_range[0], ppm)
                ppm_range[1] = max(ppm_range[1], ppm)
            if gate_ok:
                reason_hist["accepted"] = reason_hist.get("accepted", 0) + 1
            if gate_ok and bucket not in samples:
                samples[bucket] = (obj.copy(), cc.copy(), z_cm)
                n_add += 1
                uncovered_cells.discard(cell)
                depth_bins[depth] = True
                if corner_margin(xys) <= a.edge_px:
                    edge_near = True
                if tilt_deg >= a.tilt_min:
                    tilt_count += 1
                added = True
                last_stat = "ADD %s z=%.0fcm tilt=%.0fdeg edge=%.0fpx cell%s" % (
                    depth, z_cm, tilt_deg, corner_margin(xys), cell)
            elif not gate_ok:
                last_stat = "reject%s%s z=%.0fcm" % (
                    "" if is_sharp else " blur",
                    "" if ppm_ok else " bad-size(ppm=%.1f)" % ppm, z_cm)
            else:
                reason_hist["dup"] = reason_hist.get("dup", 0) + 1
                last_stat = "dup %s z=%.0fcm tilt=%.0fdeg cell%s" % (
                    depth, z_cm, tilt_deg, cell)

            draw_corners(img, pattern, cc)
        else:
            reason_hist["no board"] = reason_hist.get("no board", 0) + 1
            last_stat = "no board"

        missing = missing_list(edge_near, tilt_count, a.tilt_count, depth_bins,
                               uncovered_cells, n_add, a.samples)
        all_ok = not missing

        if n_seen % 150 == 0:
            print("frames=%d added=%d/%d bins=%s missing=[%s] %s%s"
                  % (n_seen, n_add, a.samples,
                     "".join(sorted(depth_bins)), "; ".join(missing),
                     reason_hist,
                     "" if ppm_range[0] is None else
                     "  ppm_seen=%.1f..%.1f" % tuple(ppm_range)),
                  flush=True)

        cv2.rectangle(img, (0, 0), (319, 12), (0, 0, 0), -1)
        cv2.putText(img, "SAMPLE %d/%d fps=%.0f blur=%.0f det=%s %s" % (
            n_add, a.samples, fps, blur, last_method,
            "ALL-PASS!" if all_ok else ""),
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
                if tilt_deg >= a.tilt_min:
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
    # OpenCV 5 wants image points as Point2f. canonical_corners works in
    # float64 (the SVD and the lattice quantise need the headroom), and it
    # used to be handed straight to calibrateCamera, which rejected the
    # format outright: "imagePoints1 should contain vector of vectors of
    # points of type Point2f".
    img_p = np.array([v[1] for v in samples.values()], np.float32)
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
    gates, aniso, hfov = final_gates(K, rms)
    z_ok = True
    if a.z_hint is not None:
        zs = np.median([v[2] for v in samples.values()]) / 100.0
        z_ok = 0.5 * a.z_hint <= zs <= 2.0 * a.z_hint
        print("median board z ~ %.2f m (z-hint %.2f m) -> %s" % (
            zs, a.z_hint, "consistent" if z_ok else "DRIFT"))
        gates.append(("z-hint %.1f m" % a.z_hint, z_ok))

    def gate(name, ok):
        print("  [%s] %s" % ("PASS" if ok else "FAIL", name))

    for name, ok in gates:
        gate(name, ok)
    if not 0.90 <= aniso <= 1.10:
        print("  -> board cells are not square on screen/paper: a cell measures "
              "%.2fx wider than tall.\n     Print the board, or use a viewer "
              "that letterboxes instead of stretching to fill." % aniso)

    all_pass = all(ok for _, ok in gates)
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