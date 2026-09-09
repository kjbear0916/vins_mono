"""Sweep synthetic coverage: step (flow) x noise x board, collect gate results.

Usage:
  python sweep_synth.py                 # default matrix
  python sweep_synth.py --steps 0.10 0.16 0.24 --noises 1.5 4.0
"""
import argparse
import json
import os
import re
import subprocess
import sys

VO = os.path.dirname(os.path.abspath(__file__))
SCRATCH = os.path.join(VO, "_cov")
os.makedirs(SCRATCH, exist_ok=True)

STEPS = [0.06, 0.10, 0.16, 0.22, 0.28, 0.36]
NOISES = [0.5, 1.5, 3.0, 5.0, 8.0]
BOARD_CFGS = [  # (z, board_size)
    (10.0, 4.5),
    (12.0, 5.5),
    (14.0, 6.5),
]
SEED = 7


def run(cmd):
    r = subprocess.run(cmd, cwd=VO, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout + r.stderr)


def gen(out, step, noise, board_z=None, board_size=None):
    cmd = [sys.executable, os.path.join(VO, "gen_synth_seq.py"),
           "--out", out, "--step", str(step), "--noise", str(noise),
           "--seed", str(SEED)]
    if board_z is not None:
        cmd += ["--board", "--board-z", str(board_z),
                "--board-grid", "6x5", "--board-size", str(board_size or 6.0)]
    return run(cmd)


def gate(video, prefix, meta):
    cmd = [sys.executable, os.path.join(VO, "run_clean_seq_check.py"),
           "--video", video, "--out-prefix", prefix, "--meta", meta]
    rc, out = run(cmd)
    bits = {}
    for m in re.finditer(r"^(.+?)\s+\[(\d+)\]\s+(.*)$", out, re.M):
        bits[m.group(1)] = (m.group(2), m.group(3).strip())
    passed = "RESULT: PASS" in out
    return rc, passed, bits


def gate_full(video, prefix, meta):
    """Return list of (step, noise, phasename, status, detail) gate rows."""
    rc, passed, bits = gate(video, prefix, meta)
    rows = []
    for k, (st, dt) in bits.items():
        rows.append((k, st, dt))
    return passed, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", nargs="*", type=float, default=STEPS)
    ap.add_argument("--noises", nargs="*", type=float, default=NOISES)
    a = ap.parse_args()

    results = []
    print("== flow/noise matrix (no board) ==")
    for step in a.steps:
        for noise in a.noises:
            tag = "s%02d_n%02d" % (int(round(step * 100)),
                                   int(round(noise * 10)))
            video = os.path.join(SCRATCH, tag + ".avi")
            prefix = os.path.join(SCRATCH, tag)
            meta = video.replace(".avi", "_meta.json")
            rc1, o1 = gen(video, step, noise)
            if "'error:" in o1 or "Traceback" in o1:
                results.append((tag, step, noise, "GENFAIL", "", o1.strip()[-200:]))
                continue
            passed, rows = gate_full(video, prefix, meta)
            line = "step=%-4.2f noise=%-3.1f  -> %s" % (
                step, noise, "PASS" if passed else "FAIL")
            for k, st, dt in rows:
                line += "\n    %-14s [%s] %s" % (k, st, dt)
            print(line)
            results.append((tag, step, noise, "PASS" if passed else "FAIL",
                            "; ".join("%s:%s" % (k, st) for k, st, _ in rows), ""))

    print("== board ATE matrix (official pipeline + --traj) ==")
    for z, bsize in BOARD_CFGS:
        for noise in [1.5, 5.0]:
            tag = "b_z%02d_n%02d" % (int(z), int(round(noise * 10)))
            video = os.path.join(SCRATCH, tag + ".avi")
            prefix = os.path.join(SCRATCH, tag)
            meta = video.replace(".avi", "_meta.json")
            rc1, o1 = gen(video, 0.16, noise, board_z=z, board_size=bsize)
            if "'error:" in o1 or "Traceback" in o1:
                results.append((tag, 0.16, noise, "GENFAIL",
                                "", o1.strip()[-200:]))
                continue
            rc2, o2 = run([sys.executable, os.path.join(VO, "test_incr_pnp.py"),
                           "--video", video, "--out", prefix + "_traj.csv"])
            if rc2 != 0:
                results.append((tag, 0.16, noise, "VOFALL",
                                "", o2.strip()[-200:]))
                continue
            rc3, o3 = run([sys.executable, os.path.join(VO, "run_gt_ate.py"),
                           "--video", video, "--traj", prefix + "_traj.csv",
                           "--out", prefix + "_ate.csv"])
            ate = re.findall(r"ATE (?:pre|post)-BA\s*:\s*([0-9.]+) mm", o3)
            kfs_gt = re.findall(r"VO kfs with GT:\s*(\d+)", o3)
            escala = re.findall(r"alignment scales: pre ([0-9.]+e?[0-9]*) "
                                 r"post ([0-9.]+e?[0-9]*) \(mm/unit\)", o3)
            pre_mm, post_mm = (ate if len(ate) >= 2 else ["?", "?"])[:2]
            kk = (kfs_gt[0] if kfs_gt else "?")
            sc = ("; scale %s" % "/".join(escala[-1])) if escala else ""
            print("board z=%4.1f size=%3.1f noise=%-3.1f kfs/GT=%s "
                  "ATE pre=%s post=%s%s" % (z, bsize, noise, kk,
                                            pre_mm, post_mm, sc))
            results.append((tag, 0.16, noise,
                            "ATE pre=%s post=%s kfs_gt=%s%s"
                            % (pre_mm, post_mm, kk, sc), "", ""))

    # compact CSV
    csv_path = os.path.join(VO, "_cov", "sweep_summary.csv")
    with open(csv_path, "w", newline="") as f:
        import csv as _csv
        w = _csv.writer(f)
        w.writerow(["tag", "step", "noise", "result", "gates"])
        for tag, step, noise, res, gates, _ in results:
            w.writerow([tag, step, noise, res, gates])
    print("\nwrote", csv_path)


if __name__ == "__main__":
    sys.exit(main())