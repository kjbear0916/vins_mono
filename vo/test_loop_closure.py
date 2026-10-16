import os
import sys
import unittest

import numpy as np
import cv2

VO = os.path.dirname(os.path.abspath(__file__))
if VO not in sys.path:
    sys.path.insert(0, VO)

import vo_loop_closure as lc

FRAME_A = os.path.join(VO, "debug_seq14_0.jpg")
OTHER = os.path.join(VO, "_uav3d_0.jpg")
WARP_H = np.array([[0.95, 0.03, 10.0], [0.01, 0.96, -6.0],
                   [3e-5, 2e-5, 1.0]], float)


def rectangle_centers(n=48):
    pts = []
    for k in range(n):
        s = k / n * 4.0
        if s < 1:
            c = (0, 0, 10 * s)
        elif s < 2:
            c = (6 * (s - 1), 0, 10)
        elif s < 3:
            c = (6, 0, 10 * (3 - s))
        else:
            c = (6 * (4 - s), 0, 0)
        pts.append(c)
    return np.array(pts, float)


def _gray(path):
    return cv2.imread(path, cv2.IMREAD_GRAYSCALE)


def _intr(w, h):
    return np.array([[500.0, 0, w / 2.0], [0, 500.0, h / 2.0], [0, 0, 1.0]])


class TestPoseGraphClosure(unittest.TestCase):
    def test_loop_edge_reduces_drift(self):
        C = rectangle_centers(48)
        N = len(C)
        R_id = np.eye(3)
        yaw = np.deg2rad(1.5)
        bias = np.array([0.02, 0.0, 0.0])

        odom = [(R_id, -C[0])]
        for k in range(1, N):
            dt_gt = (-C[k]) - R_id @ (-C[k - 1])
            R_m = R_id @ lc.exp_so3([0, yaw, 0])
            t_m = dt_gt + bias
            Rp, tp = odom[-1]
            odom.append((R_m @ Rp, t_m + R_m @ tp))

        odom_C = np.array([lc.camera_center(R, t) for R, t in odom])
        ate_before = lc.align_ate(odom_C, C)

        pg = lc.PoseGraphSE3()
        for R, t in odom:
            pg.add_node(R, t)
        for k in range(N - 1):
            dR = odom[k + 1][0] @ odom[k][0].T
            dt = odom[k + 1][1] - dR @ odom[k][1]
            pg.add_odom(k, k + 1, dR, dt)
        pg.add_loop(0, N - 1, R_id, [0, 0, 1], 0.0)
        pg.optimize(fixed=(0,), max_iter=60)

        ate_after = lc.align_ate(pg.centers(), C)
        self.assertLess(ate_after, 0.25 * ate_before,
                        "loop closure should cut ATE by >75%% (%.4f -> %.4f)"
                        % (ate_before, ate_after))


class TestPlaceRecognition(unittest.TestCase):
    def test_revisit_matches(self):
        A = _gray(FRAME_A)
        if A is None:
            self.skipTest("missing %s" % FRAME_A)
        A_w = cv2.warpPerspective(A, WARP_H, (A.shape[1], A.shape[0]))
        pa, da = lc.orb_features(A)
        pb, db = lc.orb_features(A_w)
        m = lc.match_ratio(da, db)
        v = lc.verify_relpose(pa, pb, m, _intr(A.shape[1], A.shape[0])) if len(m) >= 8 else None
        self.assertIsNotNone(v, "revisit should verify")
        self.assertGreaterEqual(v["inliers"], 15,
                                "revisit inliers too low: %r" % (v and v["inliers"]))

    def test_different_scene_no_match(self):
        A = _gray(FRAME_A)
        B = _gray(OTHER)
        if A is None or B is None:
            self.skipTest("missing test images")
        pa, da = lc.orb_features(A)
        pb, db = lc.orb_features(B)
        m = lc.match_ratio(da, db)
        self.assertLess(len(m), 15,
                        "unrelated scene produced %d matches" % len(m))


class TestDetectLoops(unittest.TestCase):
    def test_revisit_detected_other_ignored(self):
        A = _gray(FRAME_A)
        other = _gray(OTHER)
        if A is None or OTHER is None or _gray(OTHER) is None:
            self.skipTest("missing image assets")
        A_w = cv2.warpPerspective(A, WARP_H, (A.shape[1], A.shape[0]))
        K = _intr(A.shape[1], A.shape[0])

        def kf(frame, img):
            pts, desc = lc.orb_features(img)
            return {"frame": frame, "pts": pts, "desc": desc,
                    "R": np.eye(3), "t": np.zeros(3)}

        kfs = [kf(0, A), kf(1, other), kf(20, A_w)]
        loops = lc.detect_loops(kfs, K, min_gap=10, min_inliers=15, min_matches=20)
        self.assertTrue(any(e.i == 0 and e.j == 2 for e in loops),
                        "expected loop 0<->2; got %r"
                        % [(e.i, e.j, e.inliers) for e in loops])
        self.assertFalse(any(e.i == 1 and e.j == 2 for e in loops),
                         "unrelated keyframe must not be linked")


if __name__ == "__main__":
    unittest.main(verbosity=2)
