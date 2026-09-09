"""Visualize the flow/noise sweep matrix from _cov/sweep_summary.csv.

Draws one heatmap of PASS(1)/FAIL(0) over (step -> optical-flow guidance) x
(noise).  Also annotates each cell with P2-reproj and P6-structure status so
the PASS band is interpretable.

Usage:  python plot_sweep_heatmap.py  (reads vo/_cov/sweep_summary.csv)
"""
import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

VO = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(VO, "_cov", "sweep_summary.csv")
OUT = os.path.join(VO, "_cov", "sweep_heatmap.png")

STEPS = [0.06, 0.10, 0.16, 0.22, 0.28, 0.36]
NOISES = [0.5, 1.5, 3.0, 5.0, 8.0]


def main():
    rows = {}
    with open(CSV, newline="") as f:
        for r in csv.DictReader(f):
            tag = r.get("tag", "")
            if not tag.startswith("s") or (
                    tag.startswith("s") and tag[1].isdigit()):
                try:
                    step = float(r["step"])
                    noise = float(r["noise"])
                except (TypeError, ValueError):
                    continue
                rows[(step, noise)] = r

    pass_map = np.zeros((len(STEPS), len(NOISES)), int)
    note_map = np.empty((len(STEPS), len(NOISES)), dtype=object)
    for i, step in enumerate(STEPS):
        for j, noise in enumerate(NOISES):
            r = rows.get((step, noise))
            if r is None:
                note_map[i, j] = ""
                continue
            pass_map[i, j] = 1 if r["result"] == "PASS" else 0
            gates = dict(g.split(":", 1) for g in r["gates"].split(";")
                         if ":" in g)
            bits = (gates.get("P2 reproj-BA", "?")[:1],
                    gates.get("P6 structure", "?")[:1])
            note_map[i, j] = "P2%s P6%s" % bits

    fig, ax = plt.subplots(figsize=(9, 5.5))
    im = ax.imshow(pass_map, cmap="RdYlGn", vmin=0, vmax=1,
                   aspect="auto", origin="upper")
    ax.set_xticks(range(len(NOISES)))
    ax.set_xticklabels([str(n) for n in NOISES])
    ax.set_yticks(range(len(STEPS)))
    ax.set_yticklabels([str(s) for s in STEPS])
    ax.set_xlabel("noise (px)")
    ax.set_ylabel("step (world units/frame -> ~optical flow)")
    for i in range(len(STEPS)):
        for j in range(len(NOISES)):
            t = note_map[i, j]
            if not t:
                continue
            ax.text(j, i, t, ha="center", va="center", fontsize=9,
                    color="black",
                    weight="bold" if pass_map[i, j] else "normal")
    cbar = fig.colorbar(im, ticks=[0, 1], shrink=0.8)
    cbar.ax.set_yticklabels(["FAIL", "PASS"])
    ax.set_title("sweep: clean clips (no board), gen_synth_seq\n"
                 "green = all 7 gates pass; labels show P2/P6 gate bits")
    fig.tight_layout()
    fig.savefig(OUT, dpi=130)
    print("wrote", OUT)


if __name__ == "__main__":
    main()