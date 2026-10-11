#!/usr/bin/env python3
"""plot_suspect_cells.py — 5-arm ATE bar chart for the 2 suspect cells (log y)."""

import csv
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

GATE = (0.96, 1.03)
CELLS = [("high/0.5/circle", "high", "0.5", "circle"),
         ("medium/3.0/figure8", "medium", "3.0", "figure8")]
ARMS = [
    ("master",  "/data/results/summary_54.csv",         "/data/results/scale_sweep.csv",            ""),
    ("repo54",  "/data/results_rerun54/summary_54.csv",  "/data/results_rerun54/scale_sweep_repo54.csv", "_repo54"),
    ("imu161",  "/data/results_imu161/summary_54.csv",   "/data/results_imu161/scale_imu161.csv",   ""),
    ("imu161r", "/data/results_imu161r/summary_54.csv",  "/data/results_imu161r/scale.csv",         ""),
    ("ctl50",   "/data/results_ctl50/summary_54.csv",    "/data/results_ctl50/scale.csv",           ""),
]
COLORS = ["#4c72b0", "#dd8452", "#55a868", "#c44e52", "#8172b2"]
REPS = ["r1", "r2", "r3"]


def load_sum(path):
    rows = {}
    if not os.path.exists(path):
        return rows
    with open(path) as f:
        for r in csv.DictReader(f):
            rows[(r["light"], r["speed"], r["trajectory"], r["repeat"])] = r
    return rows


def load_scale(path, strip=""):
    out = {}
    if not os.path.exists(path):
        return out
    with open(path) as f:
        for r in csv.DictReader(f):
            tid = r["trial_id"]
            if strip and tid.endswith(strip):
                tid = tid[: -len(strip)]
            out[tid] = float(r["sim3_scale"]) if r["sim3_scale"] else None
    return out


def main():
    data = {a: load_sum(p) for a, p, _, _ in ARMS}
    scales = {a: load_scale(p, s) for a, _, p, s in ARMS}

    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))
    width = 0.15
    for ax, (title, l, sp, tr) in zip(axes, CELLS):
        for ai, (a, _, _, _) in enumerate(ARMS):
            for ri, rep in enumerate(REPS):
                r = data[a].get((l, sp, tr, rep))
                if not r:
                    continue
                tid = r["trial_id"]
                s = scales[a].get(tid if a != "repo54" else tid.replace("_repo54", ""))
                ate = float(r["ate_rms"])
                in_gate = s is not None and GATE[0] <= s <= GATE[1]
                x = ri + (ai - 2) * width
                bar = ax.bar(x, ate, width, color=COLORS[ai], alpha=0.9,
                             edgecolor="black", linewidth=0.4)
                ax.text(x, ate * 1.12, f"{ate:.2f}", ha="center", va="bottom",
                        fontsize=7, rotation=0)
                if s is not None and not in_gate:
                    ax.plot(x, ate * 0.42, "x", color="red", markersize=8,
                            markeredgewidth=2)
        ax.set_title(title, fontsize=12)
        ax.set_yscale("log")
        ax.set_ylim(0.08, 12)
        ax.set_xticks(range(3))
        ax.set_xticklabels(REPS)
        ax.set_ylabel("ATE RMS (m, log)", fontsize=9)
        ax.grid(axis="y", which="both", alpha=0.3)
    handles = [plt.Rectangle((0, 0), 1, 1, color=COLORS[i]) for i in range(len(ARMS))]
    fig.legend(handles, [a for a, *_ in ARMS], loc="lower center",
               ncol=5, fontsize=9, frameon=False)
    fig.suptitle("Suspect cells, 5 arms | same-session rerun pairs imu161r-vs-ctl50\n"
                 "red x = Sim3 scale out of [0.96, 1.03]", fontsize=11)
    fig.tight_layout(rect=[0, 0.06, 1, 0.92])
    out = "/data/plots/suspect_cells_5arms.png"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    fig.savefig(out, dpi=150)
    print("saved", out)


if __name__ == "__main__":
    main()