import argparse
import csv
import os
import time

import cv2
import matplotlib.pyplot as plt
import numpy as np

from video_source import create_source


def load_calibration(path):
    data = np.load(path)
    K = data["camera_matrix"]
    dist = data["dist_coeffs"].ravel()
    return K, dist


def good_features(gray, max_corners, quality, min_distance, block_size):
    pts = cv2.goodFeaturesToTrack(gray, max_corners, quality,
                                  min_distance, blockSize=block_size)
    if pts is None:
        return np.empty((0, 1, 2), np.float32)
    return pts


def track_points(prev_gray, prev_pts, gray, lk_params):
    next_pts, status, _ = cv2.calcOpticalFlowPyrLK(
        prev_gray, gray, prev_pts, None, **lk_params)
    good_old = prev_pts[status.ravel() == 1]
    good_new = next_pts[status.ravel() == 1]
    return good_old, good_new


def estimate_pose(good_old, good_new, K):
    info = {"reset": True, "inliers": 0, "disp": 0.0}
    if len(good_old) < 5:
        return None, info
    E, mask = cv2.findEssentialMat(good_old, good_new, K, cv2.RANSAC, 0.999, 1.0)
    if E is None:
        return None, info
    mask = (mask.ravel() == 1)
    old_in = good_old[mask]
    new_in = good_new[mask]
    info["inliers"] = len(old_in)
    ok_pose, R_rel, t_rel, _ = cv2.recoverPose(E, old_in, new_in, K)
    info["disp"] = float(np.linalg.norm(new_in - old_in, axis=1).mean())
    if ok_pose < 0:
        info["reset"] = False
        return None, info
    return (R_rel, t_rel, old_in, new_in), info


def update_pose(R_wc, t_wc, R_rel, t_rel, scale):
    new_R = R_rel @ R_wc
    new_t = t_rel * scale + R_rel @ t_wc
    return new_R, new_t


def rotation_step_deg(R_now, R_prev):
    cos = (np.trace(R_now.T @ R_prev) - 1.0) / 2.0
    return float(np.degrees(np.arccos(np.clip(cos, -1.0, 1.0))))


def motion_consistent(R_rel, last_R_rel, max_step_deg):
    if last_R_rel is None:
        return True
    return rotation_step_deg(R_rel, last_R_rel) <= max_step_deg


class KeyframeMonoVO:
    """Sparse monocular VO with a keyframe baseline.

    Feature points are tracked against a reference ("keyframe") frame.
    Frames are skipped until the tracked-flow between the reference and the
    current frame reaches `keyframe_disp` pixels -- small steps are too
    weakly conditioned for a reliable essential matrix, so accumulating a
    larger baseline between measurements cuts the translation-direction
    noise seen with per-frame E estimation.
    """

    def __init__(self, K, scale=1.0, max_corners=200, quality=0.01,
                 min_distance=10, block_size=7, min_track=40,
                 min_inliers=12, keyframe_disp=4.0, max_rot_step_deg=10.0):
        self.K = K
        self.scale = scale
        self.max_corners = max_corners
        self.quality = quality
        self.min_distance = min_distance
        self.block_size = block_size
        self.min_track = min_track
        self.min_inliers = min_inliers
        self.keyframe_disp = keyframe_disp
        self.max_rot_step_deg = max_rot_step_deg
        self.R_cur2w = np.eye(3)
        self.t_cur2w = np.zeros((3, 1))
        self.kf_gray = None
        self.kf_pts = None
        self.last_R_rel = None

    def _refresh(self, gray):
        self.kf_pts = good_features(gray, self.max_corners, self.quality,
                                    self.min_distance, self.block_size)
        self.kf_gray = gray
        self.last_R_rel = None

    def step(self, gray, lk_params):
        """Feed one grayscale frame.

        Returns (updated, R_cur2w, t_cur2w, info). R/t are the world->cam
        pose of the current frame. info carries diagnostics; when updated is
        True the current frame became a keyframe and the pose advanced.
        """
        info = {"tracked": 0, "inliers": 0, "disp": 0.0}
        if self.kf_gray is None or self.kf_pts is None or \
                len(self.kf_pts) < self.min_track:
            self._refresh(gray)
            return False, self.R_cur2w.copy(), self.t_cur2w.copy(), info

        good_old, good_new = track_points(self.kf_gray, self.kf_pts, gray,
                                          lk_params)
        info["tracked"] = len(good_old)
        if len(good_old) < self.min_inliers:
            self._refresh(gray)
            return False, self.R_cur2w.copy(), self.t_cur2w.copy(), info

        disp = float(np.linalg.norm(good_new - good_old, axis=1).mean())
        info["disp"] = disp
        if disp < self.keyframe_disp:
            return False, self.R_cur2w.copy(), self.t_cur2w.copy(), info

        res, einfo = estimate_pose(good_old, good_new, self.K)
        if res is None:
            self._refresh(gray)
            return False, self.R_cur2w.copy(), self.t_cur2w.copy(), info
        R_rel, t_rel, old_in, new_in = res
        info["inliers"] = einfo["inliers"]
        if einfo["inliers"] < self.min_inliers or \
                not motion_consistent(R_rel, self.last_R_rel,
                                      self.max_rot_step_deg):
            self._refresh(gray)
            return False, self.R_cur2w.copy(), self.t_cur2w.copy(), info

        self.R_cur2w, self.t_cur2w = update_pose(
            self.R_cur2w, self.t_cur2w, R_rel, t_rel, self.scale)
        self.last_R_rel = R_rel.copy()
        info["old_in"] = old_in
        info["new_in"] = new_in
        self._refresh(gray)
        return True, self.R_cur2w.copy(), self.t_cur2w.copy(), info


def draw_trajectory(canvas, trajectory):
    if not trajectory:
        return
    pts = np.array(trajectory[-20000:])[:, 1:4]
    x = pts[:, 0]
    z = pts[:, 2]
    lo_x, hi_x = x.min(), x.max()
    lo_z, hi_z = z.min(), z.max()
    span_x = max(hi_x - lo_x, 1e-6)
    span_z = max(hi_z - lo_z, 1e-6)
    h, w = canvas.shape[:2]
    col = (w - 1) * (x - lo_x) / span_x
    row = (h - 1) * (1.0 - (z - lo_z) / span_z)
    arr = np.round(np.stack([col, row], axis=1)).astype(np.int32)
    canvas[:] = 0
    cv2.polylines(canvas, [arr], False, (0, 220, 60), 1, cv2.LINE_AA)


def main():
    parser = argparse.ArgumentParser(
        description="Monocular visual odometry, tuned for testing with a webcam "
                    "before the ESP32-CAM hardware arrives."
    )
    parser.add_argument("--source", choices=["webcam", "file", "esp32"], default="webcam")
    parser.add_argument("--device", type=int, default=0, help="webcam index")
    parser.add_argument("--path", help="video file path when --source file")
    parser.add_argument("--url", default="http://192.168.1.100:81/stream",
                        help="ESP32-CAM MJPEG URL when --source esp32")
    parser.add_argument("--width", type=int, help="force webcam width")
    parser.add_argument("--height", type=int, help="force webcam height")
    parser.add_argument("--fps", type=int, help="force webcam fps")
    parser.add_argument("--calib", default="calibration.npz",
                        help="output of camera_calibration.py")
    parser.add_argument("--maxCorners", type=int, default=200, help="Shi-Tomasi max corners")
    parser.add_argument("--quality", type=float, default=0.01,
                        help="Shi-Tomasi quality level (0..1)")
    parser.add_argument("--minDistance", type=int, default=10,
                        help="minimum pixel distance between detected corners")
    parser.add_argument("--blockSize", type=int, default=7, help="Shi-Tomasi block size")
    parser.add_argument("--winSize", type=int, default=21, help="LK search window size")
    parser.add_argument("--maxLevel", type=int, default=2, help="LK pyramid levels")
    parser.add_argument("--minTrack", type=int, default=40,
                        help="re-detect features below this many matched points")
    parser.add_argument("--minInliers", type=int, default=12,
                        help="skip frames with fewer RANSAC inliers than this")
    parser.add_argument("--keyframe-disp", type=float, default=4.0,
                        help="measure between reference and current frame only "
                             "once the tracked flow reaches this many pixels "
                             "(0 = estimate every frame). A ~4px baseline keeps "
                             "the essential-matrix estimation well conditioned.")
    parser.add_argument("--scale", type=float, default=1.0,
                        help="monocular scale is ambiguous; try a measured scale factor")
    parser.add_argument("--maxFrames", type=int, default=0,
                        help="stop after this many frames (0 = unlimited)")
    parser.add_argument("--out", default="trajectory.csv")
    parser.add_argument("--no-undistort", action="store_true",
                        help="skip distortion removal for speed")
    parser.add_argument("--plotEvery", type=int, default=5,
                        help="refresh the OpenCV trajectory view every N frames")
    parser.add_argument("--show", action="store_true",
                        help="show a blocking matplotlib trajectory window at the end")
    parser.add_argument("--skip", type=int, default=0,
                        help="process every Nth frame (drop others) to run faster")
    parser.add_argument("--maxRotStep", type=float, default=10.0,
                        help="reject frames whose rotation jumped more than this "
                             "many degrees between consecutive measurements")
    args = parser.parse_args()

    if not os.path.exists(args.calib):
        print("calibration file %s not found. Run camera_calibration.py first: "
              "monocular pose is meaningless without camera intrinsics." % args.calib)
        raise SystemExit(1)
    K, dist = load_calibration(args.calib)

    source_kwargs = {}
    if args.source == "webcam":
        source_kwargs.update(device=args.device, width=args.width,
                             height=args.height, fps=args.fps)
    elif args.source == "file":
        source_kwargs["path"] = args.path
    elif args.source == "esp32":
        source_kwargs["url"] = args.url

    source = create_source(args.source, **source_kwargs)

    lk_params = dict(winSize=(args.winSize, args.winSize),
                     maxLevel=args.maxLevel,
                     criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01))

    vo = KeyframeMonoVO(
        K, scale=args.scale, max_corners=args.maxCorners,
        quality=args.quality, min_distance=args.minDistance,
        block_size=args.blockSize, min_track=args.minTrack,
        min_inliers=args.minInliers, keyframe_disp=args.keyframe_disp,
        max_rot_step_deg=args.maxRotStep)

    mapx = None
    mapy = None
    t_last = time.perf_counter()

    trajectory = []

    traj_view = np.zeros((600, 600), np.uint8)

    frame_no = 0

    while True:
        ok, frame = source.read()
        if not ok or frame is None:
            break
        frame_no += 1
        if args.skip and frame_no % (args.skip + 1) != 0:
            continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if mapx is None and not args.no_undistort:
            mapx, mapy = cv2.initUndistortRectifyMap(
                K, dist, None, K,
                (gray.shape[1], gray.shape[0]), cv2.CV_32FC1)
        if mapx is not None:
            gray = cv2.remap(gray, mapx, mapy, cv2.INTER_LINEAR)

        updated, R_cur2w, t_cur2w, info = vo.step(gray, lk_params)

        debug = gray.copy()
        if info.get("new_in") is not None:
            for p in info["new_in"]:
                cv2.circle(debug, tuple(p[0].astype(int)), 3, (0, 0, 255), -1)
        cv2.putText(debug, "tracked %d  inliers %d  disp %.2f  frame %d%s" %
                    (info["tracked"], info["inliers"], info["disp"], frame_no,
                     "  KEYFRAME" if updated else ""), (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        cv2.imshow("vo-features - q to quit", debug)

        if updated:
            center = -R_cur2w.T @ t_cur2w
            trajectory.append((frame_no, center[0, 0], center[1, 0],
                               center[2, 0]))

            if frame_no % args.plotEvery == 0:
                draw_trajectory(traj_view, trajectory)
                cv2.imshow("trajectory (x vs z)", traj_view)

        if frame_no % 30 == 0:
            now = time.perf_counter()
            fps = 30.0 / (now - t_last)
            t_last = now
            print("frame %d  tracked %d  inliers %d  keyframes %d  fps %.1f" %
                  (frame_no, info["tracked"], info["inliers"],
                   len(trajectory), fps))

        if args.maxFrames and frame_no >= args.maxFrames:
            break
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break

    source.release()
    cv2.destroyAllWindows()

    if trajectory:
        with open(args.out, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["frame", "x", "y", "z"])
            writer.writerows(trajectory)
        print("wrote %d poses to %s" % (len(trajectory), args.out))
        print("trajectory is scale-ambiguous (monocular). Shape is meaningful, "
              "distance is not.")
    else:
        print("no poses accumulated. Check that the scene has texture and that "
              "you keep moving the camera (pure rotation is degenerate for VO).")

    if trajectory and args.show:
        pts = np.array(trajectory)[:, 1:4]
        plt.figure()
        plt.plot(pts[:, 2], pts[:, 1])
        plt.title("trajectory (top-down, camera x vs z)")
        plt.xlabel("z")
        plt.ylabel("x")
        plt.show()
    print("run finished")


if __name__ == "__main__":
    main()