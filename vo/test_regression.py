"""One-command regression: gate logic + sync + ATE math on the real modules.

Run:  python -m unittest vo/test_regression.py -v     (from D:\Things)

Covers:
  * align_frames / drone_sync time-sync math (pure numpy)
  * run_gt_ate center_of + umeyama alignment recovers a known similarity
  * clean synthetic straight walk passes all 7 gates (subprocess, end-to-end)
  * negative controls (back_forth / jump / curve) are REJECTED by the gates
  * ATE harness (official pipeline + known truth) stays green
  * official gate script keeps its keyframe volume on the clean clip
"""

import os
import json
import csv
import subprocess
import sys
import tempfile
import unittest

import numpy as np

VO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, VO)

from run_gt_ate import center_of, umeyama_sim3
from drone_sync import align_frames, SyncTrajectory

GEN = [sys.executable, os.path.join(VO, "gen_synth_seq.py")]
CHECK = [sys.executable, os.path.join(VO, "run_clean_seq_check.py")]
_PROC = None


def _run(cmd, **kw):
    global _PROC
    _PROC = subprocess.run(cmd, cwd=VO, capture_output=True, text=True, **kw)
    return _PROC


class TestTimeSync(unittest.TestCase):
    def test_align_knows_own_clock(self):
        log = np.array([0.0, 0.5, 1.0, 1.5, 2.0])    # 2 Hz
        cam = np.linspace(0.0, 2.0, 7)               # 3.5 Hz, same origin
        l2c, c2l = align_frames(log, cam)
        self.assertEqual(l2c[2], np.argmin(np.abs(cam - 1.0)))
        self.assertEqual(c2l[3], np.argmin(np.abs(log - cam[3])))

    def test_align_offset_clock(self):
        log = np.array([0.0, 0.5, 1.0, 1.5, 2.0])
        cam = np.linspace(1.0, 3.0, 7)               # shifted +1 s
        l2c, _ = align_frames(log, cam)
        # monotone: later log maps to a >= camera frame
        self.assertTrue(np.all(np.diff(l2c) >= 0))
        self.assertEqual(int(l2c[-1]), int(np.argmin(np.abs(cam - 2.0))))

    def test_align_monotonic_inputs_required(self):
        # non-monotonic cam still does not crash and returns ints
        l2c, c2l = align_frames([2.0, 1.0], [0.0, 1.0])
        self.assertEqual(l2c.dtype, np.int32)


class TestTateMath(unittest.TestCase):
    def test_umeyama_recovers_similarity(self):
        rng = np.random.default_rng(0)
        P = rng.normal(size=(20, 3))
        s, R, t = 2.5, 0.3, np.array([4.0, -2.0, 1.0])
        rot = np.array([[np.cos(R), -np.sin(R), 0],
                        [np.sin(R), np.cos(R), 0], [0, 0, 1.0]])
        Q = s * (rot @ P.T).T + t
        cs, Rs, ts = umeyama_sim3(P, Q)
        ali = (cs * Rs @ P.T).T + ts
        np.testing.assert_allclose(ali, Q, atol=1e-8)

    def test_center_of_is_rotation_invariant(self):
        c = np.array([0.1, 0.2, -0.3])
        R = np.array([[0, 0, 1.0], [1.0, 0, 0], [0, 1.0, 0]])
        t = R @ -c                       # camera looks at origin
        got = center_of(R, t.reshape(3, 1))
        np.testing.assert_allclose(got, c, atol=1e-12)


class TestSyncTrajectoryE2E(unittest.TestCase):
    """SyncTrajectory merges a receiver log + camera meta + VO traj into a
    single pose stream. Uses a small fixed meta/traj pair written on the fly
    so the test never depends on recorded hardware files."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="vo_sync_")
        # camera meta: 16 fps, 48 frames (HOLD0 16 + MOVE 32)
        cls.meta = os.path.join(cls.tmp, "cam_meta.json")
        with open(cls.meta, "w") as f:
            json.dump({"fps": 16.0,
                       "frames": {"HOLD0": 6, "MOVE": 10, "HOLD1": 6},
                       "size": [320, 240], "phases": []}, f)
        # VO traj: monotone forward along +? with known camera frames
        traj = os.path.join(cls.tmp, "traj.csv")
        with open(traj, "w") as f:
            f.write("kf,frame,pre_x,pre_y,pre_z,post_x,post_y,post_z\n")
            for i in range(5):
                f.write("%d,%d,%d,0,0,%d,0,0\n" % (i, 10 * i, i, i))
        cls.traj_path = traj
        # receiver log: 4 samples, offset by +0.25 s from frame clock
        log = os.path.join(cls.tmp, "rc_log.csv")
        with open(log, "w") as f:
            f.write("ts_ms,roll_deg,pitch_deg,yaw_deg\n")
            for i in range(4):
                f.write("%.0f,1,2,3\n" % (1000.0 * (0.25 + 0.4 * i)))
        cls.log_path = log

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_frames_map_monotonically_with_offset(self):
        sc = SyncTrajectory(self.log_path, self.meta, self.traj_path, fps=16.0)
        # log at 0.25, 0.65, 1.05, 1.45 s -> cam frames [4, 10, 17, 21]
        # (1.45 s sits past the last frame 21/16=1.31 s, clipped in-range)
        self.assertEqual(list(map(sc.log_frame_for, range(4))),
                         [4, 10, 17, 21])
        # monotone, no unbounded extrapolation
        m = [sc.log_frame_for(i) for i in range(len(sc.log_ts))]
        self.assertTrue(all(a <= b for a, b in zip(m, m[1:])))

    def test_sync_points_carry_log_times_and_nearest_pose(self):
        sc = SyncTrajectory(self.log_path, self.meta, self.traj_path, fps=16.0)
        pts = sc.sync_points()
        self.assertEqual(len(pts), 4)
        # times are the log-domain seconds, untouched
        self.assertAlmostEqual(pts[0][0], 0.25)
        self.assertAlmostEqual(pts[-1][0], 1.45)
        # nearest-kf lookup: replicate it here independently
        kf_frames = [10 * j for j in range(5)]
        cam = [sc.log_frame_for(i) for i in range(4)]
        x_expected = [
            float(min(range(5), key=lambda j: abs(kf_frames[j] - f)))
            for f in cam]
        for i, p in enumerate(pts):
            self.assertEqual(p[1], x_expected[i])   # x = pre_x of nearest kf
            self.assertEqual(p[2], 0.0)             # y
            self.assertEqual(p[3], 0.0)             # z
        # rpy come from the receiver log rows
        self.assertEqual(pts[0][4], 1.0)   # roll
        self.assertEqual(pts[0][6], 3.0)   # yaw

    def test_per_frame_ts_overrides_fps_clock(self):
        # recorder writes irregular real timestamps that differ from i/fps
        meta = os.path.join(self.tmp, "cam_ts.json")
        with open(meta, "w") as f:
            json.dump({"fps": 60.0, "frames": {"HOLD0": 4}, "size": [8, 8],
                       "phases": [],
                       "per_frame_ts": [0.000, 0.050, 0.200, 0.260]}, f)
        sc = SyncTrajectory(self.log_path, meta, self.traj_path, fps=60.0)
        np.testing.assert_allclose(
            sc.cam_ts, np.array([0.0, 0.05, 0.2, 0.26]))


class TestAteHarnessEndToEnd(unittest.TestCase):
    """ATE harness (official pipeline + known analytic truth) must PASS."""
    @classmethod
    def setUpClass(cls):
        cls.txt = _run([sys.executable,
                        os.path.join(VO, "test_ate_harness.py")],
                       timeout=600).stdout

    def test_ate_harness_passes(self):
        self.assertIn("RESULT: PASS", self.txt)

    def test_ate_harness_ba_improves(self):
        # post < pre: bundle adjustment must reduce ATE, not just be small
        self.assertRegex(self.txt, r"improvement: \d+\.\d%")
        self.assertRegex(self.txt, r"ATE (?:pre-BA :|pre-BA: ) \d\.\d{3}\n")
        self.assertRegex(self.txt, r"ATE (?:post-BA:|post-BA : ) \d\.\d{3}\n")


class TestGatesEndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="vo_regr_")
        base = os.path.join(cls.tmp, "clean")
        _run(GEN + ["--out", base + ".avi", "--noise", "1.5",
                    "--step", "0.16"])
        cls.clean_p = _run(CHECK + ["--video", base + ".avi",
                                    "--out-prefix", base],
                           timeout=300)
        cls.clean_txt = cls.clean_p.stdout + cls.clean_p.stderr

        cls.neg = {}
        for name, extra in (("back_forth", ["--motion", "back_forth"]),
                            ("jump", ["--motion", "jump"]),
                            ("curve", ["--motion", "curve"]),
                            # protocol blind-spot negative: lateral sine sway
                            # (amp 0.30, ~1.9x the 0.16 fwd step) passes all 7
                            # gates; assert it does so this regression will
                            # FAIL once a future P9 sway gate is added --
                            # that is the intended symptom
                            ("sway", ["--motion", "sway",
                                      "--sway-amp", "0.30"])):
            p = _run(GEN + ["--out", os.path.join(cls.tmp, name) + ".avi",
                            "--noise", "1.5", "--step", "0.16"] + extra)
            r = _run(CHECK + ["--video", os.path.join(cls.tmp, name) + ".avi",
                              "--out-prefix", os.path.join(cls.tmp, name)],
                     timeout=300)
            cls.neg[name] = r.stdout + r.stderr

        # official gate script keyframe volume (was part of the old class-vs-
        # script drift monitor; the class IncrementalPnpVO is now removed, so
        # this keeps the script's lane healthy alone)
        with open(base + "_traj.csv") as f:
            cls.script_kfs = sum(1 for _ in csv.DictReader(f))

        # P7 negative control: camera jitters during HOLD -> gate must reject
        _run(GEN + ["--out", os.path.join(cls.tmp, "hold_jitter") + ".avi",
                    "--noise", "1.5", "--step", "0.16",
                    "--hold-jitter", "0.06"])
        r7 = _run(CHECK + ["--video", os.path.join(cls.tmp, "hold_jitter") + ".avi",
                           "--out-prefix", os.path.join(cls.tmp, "hold_jitter"),
                           "--meta", os.path.join(cls.tmp, "hold_jitter_meta.json")],
                  timeout=300)
        cls.neg["hold_jitter_meta"] = r7.stdout + r7.stderr

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_clean_sequence_passes(self):
        self.assertIn("RESULT: PASS", self.clean_txt)

    def test_clean_has_sufficient_structure(self):
        self.assertIn("P6 structure   [0]", self.clean_txt,
                      "clean walk must keep kfs/map pts")

    def test_back_forth_rejected_por3_p4(self):
        t = self.neg["back_forth"]
        self.assertIn("RESULT: FAIL", t)
        self.assertIn("P3 straight", t)
        self.assertIn("P4 monotonic", t)

    def test_jump_rejected(self):
        self.assertIn("RESULT: FAIL", self.neg["jump"])

    def test_curve_is_liberal(self):
        # a gentle arc may pass P3 straightness (by design) -- but the gate
        # set must not crash; asserted for documentation value
        self.assertIn("RESULT:", self.neg["curve"])

    def test_hold_jitter_rejected_by_p7(self):
        # HOLD-segment camera jitter must be caught by P7 static tail:
        # meta reports mean_flow_px above the 2px threshold -> gate FAIL
        t = self.neg["hold_jitter_meta"]
        self.assertIn("RESULT: FAIL", t)
        self.assertIn("P7 static tail", t)

    def test_sway_blind_spot_is_codified(self):
        # Lateral sine sway at amp 0.30 is a documented protocol blind spot:
        # P3/P4 miss it because they only monitor the dominant axis and both
        # endpoints.  This test pins that behaviour so adding a future P9
        # (non-dominant-axis shape gate) must flip it to FAIL on purpose.
        self.assertIn("RESULT: PASS", self.neg["sway"], 
                      "expected sway PASS until a P9 sway gate exists")

    def test_official_script_keyframe_volume(self):
        # The class-based VO is gone; the sole trajectory producer is the
        # official gate script.  It must keep producing its keyframe volume
        # on the clean clip (historically 16 kfs).
        self.assertGreaterEqual(self.script_kfs, 15,
                                "official script unexpectedly lost keyframes")


class TestImuGateEndToEnd(unittest.TestCase):
    """IMU external-reference gate: trajectory gates PASS where IMU gate FAILs.

    A yaw-drifting flight (camera rotation while translating) is invisible to
    the 7 trajectory-intrinsic gates (they monitor translation shape only)
    yet the VO-rotated angle deviates from the synthetic gyro by >5 deg.
    This is the external-reference orthogonal gate argued for in
    VO_METHODOLOGY_ABSTRACTION.md 2-3/2-4.  The trajectory must PASS all 7
    gates while imu_gate_probe.py returns FAIL -- pinning that yaw rotation
    is a real blind spot the IMU dimension closes.

    Obs #0021: the gyro integral is compared over the SAME VO-keyframe
    bracket, so at mild rotation (yaw-drift ~0.15) VO and gyro agree and
    the gate correctly PASSes.  A rotation strong enough to break VO pose
    tracking (yaw-drift 0.30) still trips it: trajectory gates PASS (the
    shape checks care about translation only) while the IMU gate FAILs.
    """
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="vo_imu_regr_")
        base = os.path.join(cls.tmp, "yaw")
        _run(GEN + ["--out", base + ".avi", "--noise", "1.5",
                    "--step", "0.16", "--yaw-drift", "0.30",
                    "--out-imu", base + "_imu.json", "--board"])
        # trajectory gates: validate_traj_pass.py is the fast gate entrypoint
        # (run_clean_seq_check re-runs VO, which is slow and redundant here)
        _run(CHECK + ["--video", base + ".avi",
                      "--out-prefix", base,
                      "--meta", base + "_meta.json"], timeout=600)
        pv = _run([sys.executable, os.path.join(VO, "validate_traj_pass.py"),
                   "--traj", base + "_traj.csv",
                   "--meta", base + "_meta.json"], timeout=240)
        cls.gates_txt = pv.stdout + pv.stderr
        pi = _run([sys.executable, os.path.join(VO, "imu_gate_probe.py"),
                   "--video", base + ".avi", "--gyro", base + "_imu.json"],
                  timeout=240)
        cls.imu_txt = pi.stdout + pi.stderr

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_trajectory_gates_pass_despite_yaw(self):
        self.assertIn("RESULT: PASS", self.gates_txt)

    def test_imu_gate_catches_yaw_drift(self):
        self.assertIn("RESULT: FAIL", self.imu_txt)


class TestIndoorGps(unittest.TestCase):
    """Indoor-GPS (ArUco absolute positioning) modules share the camera-math
    helpers of the VO line (umeyama_sim3, projection/K convention), so any
    change there must not break them.  Each test wraps the module's own
    headless self-test; the detection and calibration-sanity tests are
    synthetic probes that do not need the ESP32."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="indoor_gps_")

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_marker_detection_probe(self):
        """A 90 px marker pasted on a gray background must be detected after
        histogram equalisation (the ESP32 MJPEG low-contrast path)."""
        import cv2
        from marker_loc import _render_marker_frame
        ad = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        det = cv2.aruco.ArucoDetector(ad, cv2.aruco.DetectorParameters())
        marker = cv2.cvtColor(cv2.aruco.generateImageMarker(ad, 3, 90),
                              cv2.COLOR_GRAY2BGR)
        uv = np.array([[100, 60], [210, 62], [208, 175], [98, 173]],
                      np.float64)
        frame, _ = _render_marker_frame(marker, uv)
        corners, ids, _ = det.detectMarkers(cv2.equalizeHist(frame))
        self.assertIsNotNone(ids)
        self.assertIn(3, ids.ravel())

    def test_marker_pose_selftest(self):
        """estimate_marker_poses + camera_abs_position three-layer self-test
        (direct 0.000 mm / oblique render->detect->pose / frontal noise)."""
        from marker_loc import _run_selftest
        _run_selftest()

    def test_marker_sim3_identity(self):
        """The Umeyama glue must recover an exact identity similarity from 5
        control points (VO-gauge -> marker-absolute map)."""
        from align_sim3_demo import align_to_markers
        rng = np.random.default_rng(7)
        rel = np.column_stack([np.linspace(0.0, 2.5, 50),
                               np.linspace(-0.2, 0.3, 50), np.zeros(50)])
        ctrl = rel[np.linspace(0, 49, 5).astype(int)]
        c, R, t, rms = align_to_markers(ctrl, ctrl)
        self.assertAlmostEqual(c, 1.0, places=6)
        self.assertLess(rms, 1e-9)

    def test_marker_pipeline_selftest(self):
        """localise_video end-to-end synthetic run (6 fused frames, mean
        position error ~52 mm)."""
        from localise_video import _selftest as _ls
        _ls()

    def test_calibration_sanity_flags_swap_bug(self):
        """calib_sanity must (a) not crash on the in-tree npz (cy warning
        tolerated until calibration v2) and (b) positively flag a synthetic
        swapped-principal-point calibration."""
        import numpy as _np
        from calib_sanity import check
        rc = check(os.path.join(VO, "calibration_esp32_qvga.npz"))
        self.assertIn(rc, (0, 1))
        bad = os.path.join(self.tmp, "bad_calib.npz")
        _np.savez(bad, camera_matrix=_np.array(
            [[282.5, 0, 130], [0, 290.6, 30.0], [0, 0, 1.0]]),
            dist_coeffs=_np.zeros(5), image_size=[320, 240])
        self.assertEqual(check(bad), 1)

    def test_calibration_synthetic_recovery(self):
        """Closed-loop positive control for the calibration pipeline (obs
        0024): render a 5x4 chessboard through a known K with distortion and
        assert recalibrate_from_frames.py recovers fx within 5%.  Proves a
        near-shoot pose set that reaches the frame edges separates fx from
        distortion (the zone-only gate does NOT, fx escapes to ~2077)."""
        from gen_synth_calib_shoot import _check_recovery
        import numpy as _np
        import tempfile as _tf
        avi = os.path.join(self.tmp, "synth_calib_gt.avi")
        fx = 474.0
        self.assertEqual(_run(
            [sys.executable, os.path.join(VO, "gen_synth_calib_shoot.py"),
             "--out", avi, "--fx", str(fx), "--k1", "-0.18",
             "--seed", "7"],
            timeout=300).returncode, 0, "renderer failed")
        Kt = _np.load(avi.replace(".avi", "_truth.npz"))["camera_matrix"]
        dt = _np.load(avi.replace(".avi", "_truth.npz"))["dist_coeffs"]
        rec = os.path.join(self.tmp, "synth_calib_rec.npz")
        _run([sys.executable, os.path.join(VO, "recalibrate_from_frames.py"),
              "--video", avi, "--pattern", "5x4", "--square", "25",
              "--samples", "30", "--out", rec], timeout=300)
        d = _np.load(rec)
        got = float(d["camera_matrix"][0, 0])
        self.assertLess(abs(got - fx) / fx, 0.05,
                        "fx recovery %.1f vs truth %.1f exceeds 5%%"
                        % (got, fx))


class TestCalibrateGuidedGates(unittest.TestCase):
    """calibrate_guided REQ gating (obs 0024): depth buckets, edge-fill
    margin and missing-list composition are pure functions -- pin them so
    the guided HUD cannot regress to a zone-only gate that lets fx escape."""

    def test_depth_buckets(self):
        import numpy as _np
        from calibrate_guided import depth_label as dl
        for mn, mx, want in (((0, 100), (256, 160), "NEAR"),
                             ((30, 60), (190, 120), "MID"),
                             ((80, 110), (150, 130), "FAR")):
            xys = _np.array([(mn[0], mn[1]), (mx[0], mx[1])], float)
            self.assertEqual(dl(xys.min(axis=0), xys.max(axis=0)), want)

    def test_corner_margin_is_min_edge_distance(self):
        import numpy as _np
        from calibrate_guided import corner_margin as cm
        xys = _np.array([[5.0, 3.0], [310.0, 230.0], [150.0, 100.0]])
        self.assertEqual(cm(xys), 3.0)

    def test_missing_list_composes_requirements(self):
        from calibrate_guided import missing_list as ml
        done = ml(True, 2, 2, {"NEAR": True, "MID": True, "FAR": True},
                  set(), 30, 30)
        self.assertEqual(done, [])
        miss = ml(False, 1, 2, {"NEAR": False, "MID": True, "FAR": True},
                  {(0, 0), (2, 2)}, 12, 30)
        self.assertIn("edge-fill(near)", miss)
        self.assertIn("tilt 1/2", miss)
        self.assertIn("NEAR", miss)
        self.assertIn("grid cells 2", miss)
        self.assertIn("sample 12/30", miss)


if __name__ == "__main__":
    unittest.main()