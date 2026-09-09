"""Visual validation of incremental PnP + BA trajectory.

Usage:
  python plot_validate_trajectory.py --traj real_incr_traj.csv
      [--out real_incr_validation.png] [--title "my sequence"]

Reads <traj> (kf,frame,pre_x,y,z,post_x,y,z) plus the optional _val.json
sidecar (reproj_pre_px / reproj_post_px), builds a 4-panel figure: XY
top-down, incremental+accumulated displacement, pre/post BA reprojection error
bar, and gap/outlier markers. Also answers directional sanity (forward motion
along dominant axis) and continuity (no NaN, no jumps > threshold).
"""

import argparse
import csv
import json
import os

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

CSV = r"D:\Things\vo\real_incr_traj.csv"
OUT = r"D:\Things\vo\real_incr_validation.png"
FPS = 16.0


def load(csv_path):
    rows = list(csv.DictReader(open(csv_path, newline="")))
    kf = [int(r["kf"]) for r in rows]
    fr = [int(r["frame"]) for r in rows]
    pre = np.array([[float(r["pre_x"]), float(r["pre_y"]), float(r["pre_z"])]
                    for r in rows])
    post = np.array([[float(r["post_x"]), float(r["post_y"]), float(r["post_z"])]
                     for r in rows])
    return kf, fr, pre, post


def load_val(csv_path, title):
    val_path = csv_path.replace(".csv", "_val.json")
    if not os.path.exists(val_path):
        return None, None, None
    with open(val_path) as f:
        val = json.load(f)
    return (val.get("reproj_pre_px"), val.get("reproj_post_px"),
            val.get("n_pts"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--traj", default=CSV)
    ap.add_argument("--out", default=None)
    ap.add_argument("--title", default=None)
    ap.add_argument("--fps", type=float, default=FPS)
    args = ap.parse_args()
    csv_path = args.traj
    OUT = args.out or csv_path.replace(".csv", "_validation.png")
    title = args.title or os.path.basename(csv_path).replace("_traj.csv", "")
    fps = args.fps

    kf, fr, pre, post = load(csv_path)
    e_pre, e_post, n_pts = load_val(csv_path, title)
    n = len(kf)

    # ---- sanity: NaN / inf ----
    bad_nan = int((~np.isfinite(pre)).sum() + (~np.isfinite(post)).sum())

    # running displacement
    dp_pre = np.linalg.norm(np.diff(pre, axis=0), axis=1)
    dp_post = np.linalg.norm(np.diff(post, axis=0), axis=1)
    cum_pre = np.concatenate([[0.0], np.cumsum(dp_pre)])
    cum_post = np.concatenate([[0.0], np.cumsum(dp_post)])

    # increment outliers (jump > 3x median)
    med_pre = float(np.median(dp_pre))
    med_post = float(np.median(dp_post))
    jp_pre = np.where(dp_pre > 3 * max(med_pre, 1e-6))[0] + 1
    jp_post = np.where(dp_post > 3 * max(med_post, 1e-6))[0] + 1

    # dominant direction: axis with largest total |delta|
    tot_pre = np.abs(pre[-1] - pre[0])
    axis = ["x", "y", "z"][int(np.argmax(tot_pre))]
    sign = (post[-1] - post[0])[int(np.argmax(tot_pre))]
    dir_ok = sign > 0  # assume +axis == forward

    # total path length
    len_pre = float(cum_pre[-1])
    len_post = float(cum_post[-1])

    fig, axs = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("VO incremental-PnP + BA trajectory validation (%s)"
                 % title, fontsize=14)

    # ---- 1. XY top-down ----
    ax = axs[0, 0]
    ax.plot(pre[:, 0], pre[:, 1], "o-", ms=3, lw=1, label="pre-BA",
            color="#888", alpha=0.6)
    ax.plot(post[:, 0], post[:, 1], ".-", ms=5, lw=1.4, label="post-BA",
            color="#1f77b4")
    ax.scatter([post[0, 0]], [post[0, 1]], c="g", marker="o", s=80,
               label="start", zorder=5)
    ax.scatter([post[-1, 0]], [post[-1, 1]], c="r", marker="s", s=80,
               label="end", zorder=5)
    ax.set_title("XY top-down (%d kfs)" % n)
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.legend(fontsize=8)
    ax.axis("equal")
    ax.grid(True, alpha=0.3)

    # ---- 2. accumulated displacement ----
    ax = axs[0, 1]
    t = np.asarray(fr) / fps
    ax.plot(t, cum_pre, "-", label="cum pre-BA", color="#888")
    ax.plot(t, cum_post, "-", label="cum post-BA", color="#1f77b4")
    ax.plot(t[1:], dp_pre, "-", lw=0.8, alpha=0.5, label="increm pre",
            color="#ccc")
    ax.plot(t[1:], dp_post, "-", lw=0.8, alpha=0.5, label="increm post",
            color="#9ecae1")
    for k in jp_post:
        ax.axvline(t[k], color="r", lw=0.6, alpha=0.5, zorder=0)
    ax.set_title("displacement: total %.3f -> %.3f" % (len_pre, len_post))
    ax.set_xlabel("time (s)")
    ax.set_ylabel("units")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # ---- 3. pre/post end-to-end distance error per kf ----
    ax = axs[1, 0]
    dist = np.linalg.norm(pre - post, axis=1)
    ax.bar(np.arange(n), dist, color="#d62728", alpha=0.75)
    ax.axhline(np.median(dist), color="k", ls="--", lw=1,
               label="median %.3f" % np.median(dist))
    ax.set_title("pre vs post BA camera-centre distance")
    ax.set_xlabel("keyframe index")
    ax.set_ylabel("distance (units)")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # ---- 4. gaps / anomalies table ----
    ax = axs[1, 1]
    ax.axis("off")
    gap_frames = []          # frame gaps between consecutive kfs (>3x median)
    dk = np.diff(fr)
    med_dk = float(np.median(dk))
    for i, g in enumerate(dk):
        if g > 3 * max(med_dk, 1):
            gap_frames.append((kf[i], kf[i + 1], fr[i], fr[i + 1], int(g)))
    txt = [
        "keys: %d keyframes over %d frames" % (n, fr[-1] - fr[0]),
        "path len pre  : %.3f" % len_pre,
        "path len post : %.3f" % len_post,
        "displacement  : pre %.3f / post %.3f" % (
            float(np.linalg.norm(pre[-1] - pre[0])),
            float(np.linalg.norm(post[-1] - post[0]))),
        "dominant axis : %s (post sign %+.2f -> %s)" % (
            axis, sign, "forward" if dir_ok else "REVERSED"),
        "NaN/inf       : %d" % bad_nan,
        "reproj px     : pre %s / post %s (n_pts=%s)" % (
            "%.2f" % e_pre if e_pre is not None else "n/a",
            "%.2f" % e_post if e_post is not None else "n/a",
            n_pts if n_pts is not None else "n/a"),
        "median increm : pre %.4f / post %.4f" % (med_pre, med_post),
        "jump pts (>3x med): pre %d / post %d" % (len(jp_pre), len(jp_post)),
        "large kf frame-gaps: %d" % len(gap_frames),
    ]
    for g in gap_frames[:8]:
        txt.append("  gap kf%d->kf%d frame %d->%d (+%d)"
                   % g)
    ax.text(0.02, 0.98, "\n".join(txt), va="top", ha="left", fontsize=10,
            family="monospace")

    plt.tight_layout()
    plt.savefig(OUT, dpi=130)
    print("saved", OUT)
    print("\n".join(txt))


if __name__ == "__main__":
    main()