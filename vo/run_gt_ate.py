import argparse
import csv

import cv2
import numpy as np


def umeyama_sim3(P, Q):
    P = np.asarray(P, np.float64).reshape(-1, 3)
    Q = np.asarray(Q, np.float64).reshape(-1, 3)
    muP = P.mean(axis=0)
    muQ = Q.mean(axis=0)
    X = P - muP
    Y = Q - muQ
    cov = X.T @ Y
    U, d, Vt = np.linalg.svd(cov)
    S = np.eye(3)
    if np.linalg.det(U @ Vt) < 0:
        S[2, 2] = -1
    R = Vt.T @ S @ U.T
    c = np.sum(d * np.diag(S)) / np.sum(X ** 2)
    t = muQ - c * R @ muP
    return c, R, t


def center_of(R, t):
    c = -R.T @ t.reshape(3, 1)
    return c[0, 0], c[1, 0], c[2, 0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default=r"D:\Things\vo\real_seq.avi")
    ap.add_argument("--calib", default=r"D:\Things\vo\calibration_esp32_qvga.npz")
    ap.add_argument("--pattern", default=None,
                    help="chessboard inner corners WxH; from calib if omitted")
    ap.add_argument("--square-mm", type=float, default=None,
                    help="chessboard square size in mm; from calib if omitted")
    ap.add_argument("--out", default=r"D:\Things\vo\real_gt_ate.csv")
    ap.add_argument("--traj", required=True,
                    help="official *_traj.csv (test_incr_pnp.py output) with "
                         "pre/post camera centres per keyframe. REQUIRED: ATE "
                         "must use the exact same trajectory as the gate "
                         "pipeline -- re-running VO internally (from the "
                         "class API) drifted to 2-13 kfs vs the script's 16 "
                         "and silently produced invalid ATE.")
    args = ap.parse_args()

    d = np.load(args.calib)
    K = d["camera_matrix"]
    calib_size = d.get("image_size")
    if d.get("pattern") is not None:
        p = np.asarray(d["pattern"]).ravel()
        pat_str = "x".join(str(int(x)) for x in p) if p.size == 2 else str(p)
    else:
        pat_str = "9x6"
    pattern = args.pattern or pat_str
    square_mm = args.square_mm or float(np.asarray(d["square"]).ravel()[0])

    cols, rows = (int(x) for x in pattern.lower().split("x"))
    objp = np.zeros((rows * cols, 3), np.float32)
    objp[:, :2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2)
    objp *= square_mm

    cap = cv2.VideoCapture(args.video)

    frames = []
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        if len(fr.shape) == 3:
            g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
        else:
            g = fr
        frames.append(g)
    cap.release()
    print("loaded %d frames" % len(frames))

    if calib_size is not None and len(frames):
        h, w = frames[0].shape[:2]
        cw, ch = (int(calib_size[0]), int(calib_size[1]))
        w_scaled = abs(w - cw) / max(cw, w)
        h_scaled = abs(h - ch) / max(ch, h)
        if w_scaled > 0.02 or h_scaled > 0.02:
            print("WARN: calib %dx%d but video %dx%d -- scale mismatch, "
                  "ATE may be wrong" % (cw, ch, w, h))
    print("chessboard pattern %s, square %.1f mm (calib %s)"
          % (pattern, square_mm, args.calib))

    gt_by_i = {}
    found = 0
    for i, g in enumerate(frames):
        ok, corners = cv2.findChessboardCorners(
            g, (cols, rows), None,
            cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE)
        if not ok:
            continue
        corners = cv2.cornerSubPix(
            g, corners, (5, 5), (-1, -1),
            (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01))
        ok2, rvec, tvec = cv2.solvePnP(objp, corners, K, None)
        if not ok2:
            continue
        R, _ = cv2.Rodrigues(rvec)
        gt_by_i[i] = (R.astype(np.float64), tvec.reshape(3, 1).astype(np.float64))
        found += 1
    print("chessboard GT poses: %d frames" % found)
    if found < 4:
        print("not enough GT. Need chessboard visible + kept in most frames.")
        return

    pre_all = np.zeros((len(frames), 3))
    post_all = np.zeros((len(frames), 3))
    have_pose = np.zeros(len(frames), bool)
    rows = list(csv.DictReader(open(args.traj, newline="")))
    for r in rows:
        fno = int(r["frame"])
        pre_all[fno] = [float(r["pre_x"]), float(r["pre_y"]),
                        float(r["pre_z"])]
        post_all[fno] = [float(r["post_x"]), float(r["post_y"]),
                         float(r["post_z"])]
        have_pose[fno] = True
    print("traj %s: %d poses (official gate pipeline)" %
          (args.traj, int(have_pose.sum())))

    idxs = [i for i in range(len(frames)) if have_pose[i] and i in gt_by_i]
    print("VO kfs with GT: %d" % len(idxs))
    if len(idxs) < 4:
        print("too few aligned keyframes. Make chessboard visible throughout motion.")
        return

    gt_ctr = np.array([center_of(*gt_by_i[i]) for i in idxs])
    pre_ctr = pre_all[idxs]
    post_ctr = post_all[idxs]

    def ates(P):
        c, R, t = umeyama_sim3(P, gt_ctr)
        ali = (c * R @ P.T).T + t
        e = np.linalg.norm(ali - gt_ctr, axis=1)
        return float(np.sqrt(np.mean(e ** 2))), c

    e_pre, sc_pre = ates(pre_ctr)
    e_post, sc_post = ates(post_ctr)
    print("alignment scales: pre %.4g  post %.4g (mm/unit)" % (sc_pre, sc_post))
    print("ATE pre-BA : %.2f mm" % e_pre)
    print("ATE post-BA: %.2f mm" % e_post)
    if e_pre > 0:
        print("improvement: %.1f%%" % (100.0 * (1.0 - e_post / e_pre)))

    with open(args.out, "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["kf", "frame", "gt_x", "gt_y", "gt_z",
                     "pre_x", "pre_y", "pre_z", "post_x", "post_y", "post_z"])
        c_al_pre, R_al_pre, t_al_pre = umeyama_sim3(pre_ctr, gt_ctr)
        c_al_post, R_al_post, t_al_post = umeyama_sim3(post_ctr, gt_ctr)
        for j, i in enumerate(idxs):
            row = [j, i] + list(gt_ctr[j])
            a = (c_al_pre * R_al_pre @ pre_ctr[j]) + t_al_pre
            b = (c_al_post * R_al_post @ post_ctr[j]) + t_al_post
            row += list(a) + list(b)
            wr.writerow(row)
    print("wrote %s" % args.out)


if __name__ == "__main__":
    main()