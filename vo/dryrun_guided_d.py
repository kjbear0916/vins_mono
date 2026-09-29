# -*- coding: utf-8 -*-
"""Offline dry run of the runbook-D guided calibration, end to end.

Feeds the *unmodified* calibrate_guided.py a synthetic pose set drawn with a
known truth (fx=fy=474, k1=-0.18, k2=0.05), then puts the saved npz through
calib_sanity.

What this proves: the whole D chain -- detection, the NEAR/MID/FAR buckets,
GRID 3x3 coverage, edge-fill and tilt requirements, auto-save, the final gates
and calib_sanity -- reaches OK PASS, and the recovered focal is within 5% of
the truth that drew the frames. Run it before every physical shoot so a
failure afterwards can be attributed to the hardware rather than the tool.

What it cannot prove: the ESP32's real focal, its real distortion, or the
printed board's true square size. Only paper and silicon settle those.
The MJPEG transport itself is now verified offline (mjpeg_replay_test.py
replays a captured stream through the live reader's parser byte-exact and
fills all 30 buckets); the 2 fps figure once attributed to TCP Nagle was a
parser misalignment bug in the `\r\n\r\n` terminator search, fixed in
video_source.mjpeg_frames. Check the real stream's fps when the ESP32 is
back.

  python vo/dryrun_guided_d.py [--samples 30]
"""
import argparse
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TRUTH_FX = 474.0
TOL = 0.05


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--samples", type=int, default=30)
    ap.add_argument("--square", type=float, default=25.0)
    ap.add_argument("--out", default=os.path.join(HERE, "synth_dryrun.npz"))
    a = ap.parse_args()

    cmd = [sys.executable, os.path.join(HERE, "calibrate_guided.py"),
           "--synth", "--synth-fx", str(TRUTH_FX),
           "--pattern", "5x4", "--square", str(a.square),
           "--samples", str(a.samples), "--out", a.out,
           "--save-dir", os.path.join(HERE, "_dryrun_raw")]
    print("running:", " ".join(cmd[1:]), flush=True)
    # a stale npz from an earlier run would be read back as this run's result
    if os.path.exists(a.out):
        os.remove(a.out)
    rc = subprocess.call(cmd)

    print("\n---- calibrate_guided rc=%s ----" % rc, flush=True)
    if not os.path.exists(a.out):
        print("DRY RUN FAIL: no npz written")
        return 1
    d = np.load(a.out)
    fx, fy = float(d["camera_matrix"][0, 0]), float(d["camera_matrix"][1, 1])
    rms = float(d["rms"])
    err = abs(fx - TRUTH_FX) / TRUTH_FX
    print("recovered fx=%.1f fy=%.1f rms=%.3f  truth fx=%.0f  err=%.1f%%"
          % (fx, fy, rms, TRUTH_FX, err * 100.0))
    print("---- calib_sanity ----", flush=True)
    # gate on the sanity verdict, not just on its output: calib_sanity is the
    # check that would catch a height/width swap or a focal band that the fx
    # error alone would sail straight past
    sanity_rc = subprocess.call(
        [sys.executable, os.path.join(HERE, "calib_sanity.py"), a.out])
    ok = rc == 0 and sanity_rc == 0 and err <= TOL
    if sanity_rc != 0:
        print("calib_sanity rejected the calibration (rc=%s)" % sanity_rc)
    print("\n====== DRY RUN %s ======" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
