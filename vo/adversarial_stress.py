# -*- coding: utf-8 -*-
"""Stress the SB + canonical chain against field-like image degradation.

Renders the REQ-satisfying guided pose set (gen_guided_pose_set.build) through
the same truth intrinsics (fx=fy=474, k1=-0.18, k2=0.05) and pushes every
frame down the acceptance path the live tool really records under: find_board
SB-only, the Laplacian --blur-min sharpness gate, then canonical_corners ->
classify_detection -> REQCollector. Each condition adds a degradation a
hand-held indoor shoot can actually produce:

  gradient : softbox-style brightness falloff across the image (light falloff)
  shadow   : a soft cast-shadow dimming region of the board (occlusion by hand)
  blur     : 5 px horizontal box blur (motion / out-of-focus shake)
  combined : gradient + shadow + blur at once (worst plausible hand holding)

For every condition the probe reports how many poses still pass SB detection,
where the rejects go (lattice / off-frame / bad-size / detect / blur), whether
the 30-bucket REQ panel still closes all-green, and what fx/RMS a
calibrateCamera solve over the *accepted* samples recovers. Nothing here needs
the camera.

  python vo/adversarial_stress.py            # all conditions
  python vo/adversarial_stress.py --cond blur --cond combined
  python vo/adversarial_stress.py --sweep    # push strength until the chain breaks

Findings (truth fx = 474): light gradient and cast shadow are not a threat even
at extreme strength (SB 46/47, zero rejects, fx error <= 4%). Horizontal motion
blur IS: at >=9 px the corners smear along x, solve fx silently drifts to
617-652 (+30-37%) while every gate -- REQ panel, final gates, and the
Laplacian --blur-min 30 sharpness gate (variance stays 350-700 on JPEG-decoded
frames) -- stays green. A blurred session therefore passes as "valid" with a
wrong calibration; the sweep exists to make that boundary measurable.
"""
import argparse
import sys

import cv2
import numpy as np

import calibrate_guided as cg
import gen_guided_pose_set as gp
import gen_synth_calib_shoot as gs

K = np.array([[474.0, 0, 160.0], [0, 474.0, 120.0], [0, 0, 1.0]])
DIST = np.array([-0.18, 0.05, 0.0, 0.0, 0.0])
SQ = 25.0
PATTERN = gs.PATTERN
NOISE = 3.0
TRUTH_FX = float(K[0, 0])
BLUR_MIN = 30.0


def degrade(gray, condition, rng, K, s=1.0):
    """Apply one condition to a rendered (unclipped) float frame.

    s is the strength multiplier: ramp gain / shadow depth / blur width scale
    linearly with it, so the sweep can push a condition until the chain breaks.
    """
    H, W = gray.shape
    g = gray.astype(np.float32)
    if condition == "gradient":
        ramp = np.linspace(-1.0, 1.0, W, dtype=np.float32)
        g = g * (1.0 + min(0.95, 0.35 * s) * ramp)
    elif condition == "shadow":
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        cx, cy = W * 0.55, H * 0.45
        sig = 90.0
        spot = np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * sig * sig))
        g = g * (1.0 - min(0.9, 0.45 * s) * spot)
    elif condition == "blur":
        k = max(3, int(round(5.0 * s)) | 1)
        g = cv2.blur(g, (k, 1))
    elif condition == "combined":
        ramp = np.linspace(-1.0, 1.0, W, dtype=np.float32)
        g = g * (1.0 + min(0.95, 0.35 * s) * ramp)
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        spot = np.exp(-((xx - W * 0.55) ** 2 + (yy - H * 0.45) ** 2) /
                      (2 * 90.0 ** 2)).astype(np.float32)
        g = g * (1.0 - min(0.9, 0.45 * s) * spot)
        k = max(3, int(round(5.0 * s)) | 1)
        g = cv2.blur(g, (k, 1))
    g = g + rng.normal(0.0, NOISE, g.shape)
    return np.clip(g, 0, 255).astype(np.uint8)


def run_condition(name, poses, local, K, dist, collector, s=1.0):
    """Run the acceptance path the *live* tool really records under: SB-only
    corners plus a Laplacian minimum-sharpness gate (calibrate_guided
    --blur-min 30). Rejects land in stats rather than the collector, exactly
    like the HUD's reason histogram."""
    rng = np.random.default_rng(20260929)
    stats = {"steps": len(poses), "sb": 0, "classic": 0, "miss": 0,
             "lattice": 0, "off-frame": 0, "bad-size": 0, "blurred": 0,
             "done_at": None}
    for step, p in enumerate(poses, 1):
        R = gp.rot(p["pitch"], p["yaw"], p["roll"])
        t = gp.project_centre(p["z"], p["pu"], p["pv"], K)
        gray = np.zeros((gs.H, gs.W), np.uint8)
        if not gs.render_board(gray, K, dist, local, R, t):
            stats["miss"] += 1
            continue
        deg = degrade(gray, name, rng, K, s)
        work = gp.wire_roundtrip(deg)          # what the MJPEG loop decodes
        sharp = float(cv2.Laplacian(work, cv2.CV_64F).var()) >= BLUR_MIN
        found, cc, how = cg.find_board(work, PATTERN)
        if not found or not how.startswith("sb"):
            if how.startswith("classic"):
                stats["classic"] += 1
            else:
                stats["miss"] += 1
            continue
        stats["sb"] += 1
        if not sharp:
            stats["blurred"] += 1
            continue
        d = cg.classify_detection(cc, PATTERN, SQ, 8.0, 60.0)
        rej = d.get("reject")
        if rej:
            stats[rej] = stats.get(rej, 0) + 1
            continue
        collector.add(d)
        if collector.done() and stats["done_at"] is None:
            stats["done_at"] = step
    return stats


def recover_fx(collector):
    if collector.n_add == 0:
        return None
    real = [v[0] for v in collector.samples.values()]
    img = [v[1] for v in collector.samples.values()]
    rms, K_, d, rvecs, tvecs = cv2.calibrateCamera(
        real, img, (gs.W, gs.H), None, None,
        flags=cv2.CALIB_FIX_PRINCIPAL_POINT)
    return float(K_[0, 0]), float(rms)


def pass_condition(name, poses, local, s=1.0):
    obj = cg.object_grid(PATTERN, SQ)
    collector = cg.REQCollector(obj, 30, 2, 15.0)
    stats = run_condition(name, poses, local, K, DIST, collector, s)
    fxr = recover_fx(collector)
    ok = False
    if collector.done() and fxr is not None:
        fx, _ = fxr
        ok = abs(fx - TRUTH_FX) / TRUTH_FX <= 0.10
    return dict(ok=ok, stats=stats, collector=collector, fxr=fxr)


def fmt_row(name, r, strength=None):
    stats = r["stats"]
    c = r["collector"]
    fxr = r["fxr"]
    miss = c.missing()
    fx = "%.0f" % fxr[0] if fxr else "-"
    err = "%.0f%%" % (abs(fxr[0] - TRUTH_FX) / TRUTH_FX * 100) if fxr else "-"
    rms = "%.3f" % fxr[1] if fxr else "-"
    da = str(stats["done_at"]) if stats["done_at"] else "-"
    verdict = "OK" if r["ok"] else "FAIL"
    if not r["ok"] and r["fxr"] is not None and c.done():
        verdict = "FAIL fx err"
    lbl = "%s x%.2f" % (name, strength) if strength else name
    return ("%-13s %5d %5d %5d %7d %7d %7d %6d %7d %7d %7s %5s %6s %7s  %s"
            % (lbl, stats["steps"], stats["sb"], stats["miss"],
               stats["classic"], stats.get("blurred", 0), stats["lattice"],
               stats["off-frame"], stats["bad-size"], c.n_add,
               (fx if c.n_add else "-"), err, rms, da, verdict))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cond", action="append",
                    default=["gradient", "shadow", "blur", "combined"])
    ap.add_argument("--sweep", action="store_true",
                    help="push each condition until the chain breaks and "
                         "report the PASS/FAIL boundary")
    a = ap.parse_args()

    local = gs.board_corners_local()
    poses = gp.build(K, DIST, SQ, 24.0, 15.0, 8.0, 60.0, 30, noise=NOISE)
    print("pose set: %d poses (REQ-satisfying on clean+noise path), truth "
          "fx=%.0f" % (len(poses), K[0, 0]))
    cols = ["condition", "steps", "sb%", "miss", "classic", "blur",
            "lattice", "off-fr", "bad-sz", "samples", "fx", "err%", "rms",
            "doneAt", "verdict"]
    print("%-13s %5s %5s %5s %7s %7s %7s %6s %7s %7s %7s %5s %6s %7s  %s"
          % tuple(cols))

    strengths = {
        "gradient": [0.5, 1.0, 2.0, 2.7, 3.0],
        "shadow":   [0.5, 1.0, 2.0, 3.0],
        "blur":     [0.6, 1.0, 1.6, 2.0, 2.4],
        "combined": [0.5, 1.0, 1.5, 2.0, 2.5],
    }
    all_ok = True
    for name in a.cond:
        if not a.sweep:
            r = pass_condition(name, poses, local)
            all_ok = all_ok and r["ok"]
            print(fmt_row(name, r))
            continue
        boundary = None
        last_pass = None
        for s in strengths.get(name, [1.0]):
            r = pass_condition(name, poses, local, s)
            print(fmt_row(name, r, s))
            all_ok = all_ok and r["ok"]
            if r["ok"]:
                last_pass = s
                continue
            boundary = s
            break
        if boundary is None:
            print("  -> no failure up to s=%.2f" % strengths[name][-1])
        elif last_pass is None:
            print("  -> %s breaks already at s=%.2f (weakest tested)"
                  % (name, boundary))
        else:
            print("  -> %s survives up to s=%.2f, breaks at s=%.2f"
                  % (name, last_pass, boundary))
    print("ALL CONDITIONS %s" % ("PASS" if all_ok else "FAIL"))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())