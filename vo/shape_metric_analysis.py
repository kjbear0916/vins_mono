"""Candidate P9 (shape) metrics over adversarial trajectories.

Goal: pick the post-BA trajectory statistic that best EXPLAINS the ATE gap
(the off-axis drift the current gates miss).  For every *_traj.csv in the
adversarial set we compute several shape metrics; against the rows that also
have ATE (blind rows + straight controls) we report correlation with ATEpost
so the P9 definition is data-driven, not hand-picked.

Metrics (all invariant to global rotation/translation, NOT to scale -- that's
the point, scale drift is P8's job):
  pca_lat    : (lambda2+lambda3)/sum(lambdas)  -- off-principal-axis energy
  bend       : RMS distance of points from their PCA axis-1 line / path len
  netpath    : net/path (P3 metric, reference)
  maxret     : P4-style worst retreat (reference)
  osc_eff    : number of sign flips of lateral component per unit path
  path_len   : raw path length (for labeling only)
"""
import csv
import os
import re
import sys

import numpy as np

VO = os.path.dirname(os.path.abspath(__file__))
ADV = os.path.join(VO, "_adv")


def load_traj(path):
    rows = list(csv.DictReader(open(path, newline="")))
    pre = np.array([[float(r["pre_x"]), float(r["pre_y"]),
                     float(r["pre_z"])] for r in rows])
    post = np.array([[float(r["post_x"]), float(r["post_y"]),
                      float(r["post_z"])] for r in rows])
    return pre, post


def shape(P):
    """PCA lateral energy fraction + bending (centroid-free where needed)."""
    C = P - P.mean(0)
    e = np.linalg.eigh(C.T @ C / len(C))[0]
    pca = (e[0] + e[1]) / e.sum() if e.sum() > 1e-12 else 0.0
    v1 = np.linalg.svd(C, compute_uv=True)[2][0]
    dist = np.linalg.norm(np.cross(v1, C), axis=1) if np.linalg.norm(v1) > 1e-9 \
        else np.linalg.norm(C, axis=1)
    path = float(np.linalg.norm(np.diff(P, axis=0), axis=1).sum())
    bend = float(dist.mean() / max(path, 1e-9))
    return pca, bend


def metrics(pre, post):
    pre_pca, pre_bend = shape(pre)
    post_pca, post_bend = shape(post)
    net = float(np.linalg.norm(post[-1] - post[0]))
    path = float(np.linalg.norm(np.diff(post, axis=0), axis=1).sum())
    # lateral energy recovery: does BA keep the off-axis energy it was given?
    recovery = post_pca / max(pre_pca, 1e-9)
    # BA intervention: how much did the optimizer move the trajectory?
    if len(pre) == len(post):
        inter = float(np.linalg.norm(post - pre, axis=1).sum()) / max(path, 1e-9)
    else:
        inter = float("nan")
    return dict(pre_pca=pre_pca, post_pca=post_pca, recovery=recovery,
                pre_bend=pre_bend, post_bend=post_bend,
                netpath=net / max(path, 1e-9), inter=inter, path=path)


def main():
    ate = {}
    bpath = os.path.join(ADV, "adv_blind.csv")
    if os.path.exists(bpath):
        for r in csv.DictReader(open(bpath, newline="")):
            ate[r["tag"]] = float(r["ATEpost_mm"])
    gpath = os.path.join(ADV, "adv_grid.csv")
    if os.path.exists(gpath):
        for r in csv.DictReader(open(gpath, newline="")):
            if r["result"] == "PASS" and r["ATEpost_mm"]:
                ate[r["tag"]] = float(r["ATEpost_mm"])

    rows = []
    for f in sorted(os.listdir(ADV)):
        if not f.endswith("_traj.csv") or f.startswith("dbg"):
            continue
        tag = f[:-len("_traj.csv")]
        try:
            pre, post = load_traj(os.path.join(ADV, f))
        except Exception:
            continue
        if len(post) < 5:
            continue
        m = metrics(pre, post)
        m["tag"] = tag
        m["ate"] = ate.get(tag, float("nan"))
        rows.append(m)
    rows.sort(key=lambda r: (np.isnan(r["ate"]), -r["ate"]))
    print("%-26s %8s %8s %7s %7s %8s" %
          ("tag", "interv", "netpath", "prepca", "recov", "ATEmm"))
    for r in rows:
        print("%-26s %8.3f %7.3f %7.4f %7.3f %8.2f" %
              (r["tag"], r["inter"], r["netpath"], r["pre_pca"],
               r["recovery"], r["ate"]))
    # correlation of each metric with ATE over rows that have ATE
    X = np.array([[r[k] for k in
                   ("pre_pca", "post_pca", "recovery", "netpath", "inter")]
                  for r in rows if not np.isnan(r["ate"])])
    y = np.array([r["ate"] for r in rows if not np.isnan(r["ate"])])
    if len(y) >= 5:
        print("\ncorrelation with ATEmm over %d rows:" % len(y))
        for i, k in enumerate(("pre_pca", "post_pca", "recovery", "netpath",
                               "inter")):
            rr = np.corrcoef(X[:, i], y)[0, 1]
            print("  %-10s rho=%.2f" % (k, rr))


if __name__ == "__main__":
    sys.exit(main())