import argparse
import os

import cv2
import numpy as np

from video_source import create_source


def parse_pattern(text):
    cols, rows = text.split("x")
    return int(cols), int(rows)


def make_object_grid(cols, rows, square):
    obj = np.zeros((cols * rows, 3), np.float32)
    obj[:, :2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2) * square
    return obj


def main():
    parser = argparse.ArgumentParser(
        description="Camera calibration with a chessboard. Uses the same swappable "
                    "image source module as vo_core.py."
    )
    parser.add_argument("--source", choices=["webcam", "file", "esp32"], default="webcam")
    parser.add_argument("--device", type=int, default=0, help="webcam index")
    parser.add_argument("--path", help="video file path when --source file")
    parser.add_argument("--url", default="http://192.168.1.100:81/stream",
                        help="ESP32-CAM MJPEG URL when --source esp32")
    parser.add_argument("--width", type=int, help="force webcam width")
    parser.add_argument("--height", type=int, help="force webcam height")
    parser.add_argument("--fps", type=int, help="force webcam fps")
    parser.add_argument("--pattern", default="9x6", help="inner checkboard corners, e.g. 9x6")
    parser.add_argument("--square", type=float, default=25.0,
                        help="chessboard square size in mm, only used as a scaling hint")
    parser.add_argument("--samples", type=int, default=20,
                        help="number of detected poses to collect before calibrating")
    parser.add_argument("--fast", action="store_true",
                        help="use FAST detection flag (less robust, faster)")
    parser.add_argument("--out", default="calibration.npz")
    args = parser.parse_args()

    cols, rows = parse_pattern(args.pattern)
    pattern_size = (cols, rows)
    obj_grid = make_object_grid(cols, rows, args.square)
    flags = cv2.CALIB_CB_FAST_CHECK if args.fast else 0

    source_kwargs = {}
    if args.source == "webcam":
        source_kwargs.update(device=args.device, width=args.width,
                             height=args.height, fps=args.fps)
    elif args.source == "file":
        source_kwargs["path"] = args.path
    elif args.source == "esp32":
        source_kwargs["url"] = args.url

    source = create_source(args.source, **source_kwargs)

    obj_points = []
    img_points = []
    window_name = "chessboard - q to finish"

    print("Move the board around: change tilt, rotation, scale, and cover the "
          "corners of the view. Collect at least %d good poses." % args.samples)
    print("Press q in the window to stop early (a small sample set makes a poor "
          "calibration unless you also retake it later).")

    frame_size = None
    while True:
        ok, frame = source.read()
        if not ok or frame is None:
            break
        frame_size = frame.shape[1], frame.shape[0]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        found, corners = cv2.findChessboardCorners(gray, pattern_size, flags)
        if found:
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
            corners = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
            obj_points.append(obj_grid)
            img_points.append(corners)
            cv2.drawChessboardCorners(frame, pattern_size, corners, found)

        cv2.putText(frame, "samples: %d / %d" % (len(img_points), args.samples),
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.imshow(window_name, frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        if len(img_points) >= args.samples:
            break

    source.release()
    cv2.destroyAllWindows()

    if len(img_points) < 5:
        print("Too few samples (%d). Run again and collect more poses." % len(img_points))
        raise SystemExit(1)

    rms, K, dist, _, _ = cv2.calibrateCamera(
        obj_points, img_points, frame_size, None, None)

    print("calibration RMS (pixels, lower is better): %.4f" % rms)
    print("camera matrix:\n%s" % K)
    print("distortion coefficients: %s" % np.round(dist.ravel(), 6))

    np.savez(args.out, camera_matrix=K, dist_coeffs=dist, rms=rms,
             image_size=np.array(frame_size),
             pattern=np.array(pattern_size),
             square=np.array([args.square]))
    print("saved to %s" % args.out)


if __name__ == "__main__":
    main()