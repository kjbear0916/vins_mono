"""Adversarial grid search: find gate-PASS trajectories with worst ATE.

Turns "find a protocol blind spot" into an optimisation: maximise ATE under
the constraint that all 7 gates PASS.  A black-box grid over the synthetic
generator's kinematic parameters.

For each parameter combo (motion x step x noise x sway-amp x hold-jitter):
  gen_synth_seq.py --board ... -> run_clean_seq_check.py (gates)
                                            |
                    if all 7 gates PASS  -> test_incr_pnp.py (_traj.csv)
                                          -> run_gt_ate.py  (ATE mm, post-BA)
  -> table row: (params, gate verdict, gate metrics, ATE)

The ATE must reuse the same test_incr_pnp.py *_traj.csv that the gate
pipeline produced (run_gt_ate.py requires it -- it refuses a re-derived
trajectory).  run_clean_seq_check.py invokes test_incr_pnp.py internally
and emits *_traj.csv + *_traj_val.json; we consume those exact files.

Outputs:
  <out-prefix>_grid.csv    one row per combo actually evaluated
  <out-prefix>_blind.csv   only pass-with-ATE rows, sorted by ATE desc
  stdout summary

Usage:
  python adversarial_search.py --board-z 14 --board-size 4.5
  python adversarial_search.py --steps 0.10 0.16 --noises 1.5 4.0
"""

import argparse
import csv
import itertools
import json
import os
import re
import subprocess
import sys

VO = os.path.dirname(os.path.abspath(__file__))
SCRATCH = os.path.join(VO, "_adv")
os.makedirs(SCRATCH, exist_ok=True)

PY = sys.executable


def run(cmd, timeout=900):
    r = subprocess.run(cmd, cwd=VO, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    return r.returncode, (r.stdout + r.stderr)


def gen(video, motion, step, noise, sway_amp, hold_jitter, board_z, board_size):
    cmd = [PY, os.path.join(VO, "gen_synth_seq.py"),
           "--out", video, "--motion", motion,
           "--step", str(step), "--noise", str(noise),
           "--seed", "7"]
    if motion == "sway":
        cmd += ["--sway-amp", str(sway_amp)]
    if hold_jitter > 0.0:
        cmd += ["--hold-jitter", str(hold_jitter)]
    if board_z is not None:
        cmd += ["--board", "--board-z", str(board_z),
                "--board-grid", "6x5", "--board-size", str(board_size)]
    return run(cmd)


def gates_from(text):
    """Parse run_clean_seq_check.py output into {gate: (code, detail)}."""
    bits = {}
    for m in re.finditer(r"^(.+?)\s+\[(\d+)\]\s+(.*)$", text, re.M):
        bits[m.group(1).strip()] = (int(m.group(2)), m.group(3).strip())
    return bits


def verdict(text):
    return "PASS" if "RESULT: PASS" in text else "FAIL"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-prefix", default=os.path.join(SCRATCH, "adv"))
    ap.add_argument("--steps", nargs="+", type=float, default=[0.16])
    ap.add_argument("--noises", nargs="+", type=float, default=[1.5])
    ap.add_argument("--motions", nargs="+",
                    choices=["straight", "back_forth", "jump", "curve", "sway"],
                    default=["straight", "sway"])
    ap.add_argument("--sway-amps", nargs="+", type=float,
                    default=[0.10, 0.20, 0.30, 0.40])
    ap.add_argument("--hold-jitters", nargs="+", type=float, default=[0.0])
    ap.add_argument("--board-z", type=float, default=14.0)
    ap.add_argument("--board-size", type=float, default=4.5)
    a = ap.parse_args()

    combos = list(itertools.product(a.steps, a.noises, a.motions,
                                    a.sway_amps, a.hold_jitters))
    print("adversarial grid: %d combos" % len(combos))
    print("%-44s  %-5s %-5s %-6s %-8s %-8s %-8s" %
          ("combo", "gate", "P2px", "P3", "P4%", "ATEpre", "ATEpost"))

    rows = []
    blind = []
    metric_rows = []
    for step, noise, motion, sway_amp, hj in combos:
        tag = "%s_s%d_n%d_a%d_j%d" % (motion, int(step * 100), int(noise * 10),
                                      int(sway_amp * 100), int(hj * 1000))
        pre = os.path.join(SCRATCH, tag)
        video = pre + ".avi"
        rc1, o1 = gen(video, motion, step, noise, sway_amp, hj,
                      a.board_z, a.board_size)
        if "Traceback" in o1 or "error" in o1.lower():
            rows.append((tag, "GENFAIL", "", o1.strip()[-120:]))
            print("%-44s  GENFAIL" % tag)
            continue

        rc2, o2 = run([PY, os.path.join(VO, "run_clean_seq_check.py"),
                       "--video", video, "--out-prefix", pre,
                       "--meta", pre + "_meta.json"])
        gates = gates_from(o2)
        v = verdict(o2)
        p2 = (gates.get("P2 reproj-BA", (0, ""))[1].split("->")[-1]
              .split("px")[0].strip())
        p3 = (gates.get("P3 straight", (0, ""))[1]
              .split("=")[-1].split("/")[0].strip())
        p4 = (gates.get("P4 monotonic", (0, ""))[1])
        m4 = re.search(r"worst retreat=([\d.]+)", p4)
        p4v = m4.group(1) if m4 else ""
        rcA, oA = (0, "")
        if v == "PASS":
            traj = pre + "_traj.csv"
            if os.path.exists(traj):
                rcA, oA = run([PY, os.path.join(VO, "run_gt_ate.py"),
                               "--video", video, "--traj", traj,
                               "--out", pre + "_ate.csv"])
            else:
                oA = "NO TRAJ CSV"
        ate_pre, ate_post = "", ""
        if oA:
            mm = re.findall(r"ATE (?:pre|post)-BA\s*[:\s]*([0-9.]+) mm", oA)
            if len(mm) >= 2:
                ate_pre, ate_post = mm[0], mm[1]
        row = (tag, v, p2, p3, p4v, ate_pre, ate_post)
        rows.append(row)
        print("%-44s  %-5s %-5s %-6s %-8s %-8s %-8s" % row)

        # collect full numeric metrics for gate-redundancy analysis
        m = {"tag": tag, "result": v, "motion": motion, "step": step,
             "noise": noise, "sway_amp": sway_amp}
        g = gates
        for mm, key in (("P2 reproj-BA", "P2"), ("P3 straight", "P3"),
                        ("P4 monotonic", "P4"), ("P5 no jumps", "P5"),
                        ("P6 structure", "P6"), ("P7 static tail", "P7")):
            d = g.get(mm, (None, ""))[1]
            m[key] = d
        m["ATEpost"] = ate_post or ""
        if os.path.exists(pre + "_traj_val.json"):
            try:
                vj = json.load(open(pre + "_traj_val.json"))
                m["npts"] = vj.get("n_pts")
                m["nobs"] = vj.get("n_obs")
            except Exception:
                pass
        metric_rows.append(m)
        if v == "PASS" and ate_post:
            blind.append((tag, step, noise, motion, sway_amp, hj,
                          p2, p3, p4v, ate_pre, ate_post))
            sys.stdout.flush()

    out_csv = a.out_prefix + "_grid.csv"
    with open(out_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["tag", "result", "P2px", "P3", "P4retreat%",
                    "ATEpre_mm", "ATEpost_mm"])
        for row in rows:
            w.writerow(row)
    print("\ngrid csv ->", out_csv)

    if blind:
        blind.sort(key=lambda r: float(r[-1]), reverse=True)
        b_csv = a.out_prefix + "_blind.csv"
        with open(b_csv, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["tag", "step", "noise", "motion", "sway_amp", "hold_jit",
                        "P2px", "P3", "P4%", "ATEpre_mm", "ATEpost_mm"])
            for r in blind:
                w.writerow(r)
        print("\nblind-spot rows (gates PASS but ATE worst), sorted desc:")
        for r in blind:
            print("  ATE post %5s mm  | %s (motion=%s sway=%.2f step=%.2f "
                  "noise=%.1f)" % (r[-1], r[0], r[3], r[4], r[1], r[2]))
        print("blind csv ->", b_csv)
    else:
        print("\nno gate-PASS-with-ATE combo found")

    m_csv = a.out_prefix + "_metrics.csv"
    with open(m_csv, "w", newline="") as f:
        import csv as _c
        w = _c.writer(f)
        w.writerow(["tag", "result", "motion", "step", "noise", "sway_amp",
                    "P2", "P3", "P4", "P5", "P6", "P7", "ATEpost", "npts", "nobs"])
        for m in metric_rows:
            w.writerow([m.get(k, "") for k in
                        ["tag", "result", "motion", "step", "noise", "sway_amp",
                         "P2", "P3", "P4", "P5", "P6", "P7", "ATEpost",
                         "npts", "nobs"]])
    print("metrics csv ->", m_csv)


if __name__ == "__main__":
    sys.exit(main())