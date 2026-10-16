"""
test_marker_detect.py  — ArUco 偵測穩定性測試（Step 2）
用法：
    python test_marker_detect.py                    # 用 ESP32 串流
    python test_marker_detect.py --source webcam    # 用筆電鏡頭測試
    python test_marker_detect.py --source video D:\Things\vo\seq_real_14.avi

視窗操作：
    q → 離開
    s → 截圖存到 markers\ 目錄
    r → 重設偵測統計
"""
import argparse, sys, time, os, json
import cv2
import numpy as np

sys.path.insert(0, r"D:\Things\vo")

ESP32_URL = "http://192.168.4.1:81/stream"  # 純 AP 模式

def make_source(source_type, path=None):
    if source_type == "esp32":
        from video_source import create_source
        return create_source("esp32", url=ESP32_URL)
    elif source_type == "webcam":
        return cv2.VideoCapture(0)
    elif source_type == "video":
        return cv2.VideoCapture(path)
    else:
        raise ValueError(f"unknown source: {source_type}")

def read_frame(src, source_type):
    ok, frame = src.read()
    return frame if ok else None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="esp32", choices=["esp32","webcam","video"])
    ap.add_argument("--video", default=None)
    ap.add_argument("--marker-length", type=float, default=None,
                    help="實際印出的 marker 黑色邊長（公尺）。填了才能算距離。")
    ap.add_argument("--calib",
                    default=r"D:\Things\vo\calibration_esp32_qvga.npz")
    ap.add_argument("--dict", default="DICT_4X4_50")
    args = ap.parse_args()

    # ArUco 設定
    dict_id = getattr(cv2.aruco, args.dict)
    aruco_dict   = cv2.aruco.getPredefinedDictionary(dict_id)
    detector_params = cv2.aruco.DetectorParameters()
    detector = cv2.aruco.ArucoDetector(aruco_dict, detector_params)

    # 相機標定（若要測距離）
    K, dist_coeff = None, None
    if args.marker_length and os.path.exists(args.calib):
        d = np.load(args.calib)
        K = d["camera_matrix"].astype(np.float64)
        dist_coeff = d["dist_coeffs"].astype(np.float64)
        print(f"[calib] K loaded, marker_length={args.marker_length} m")
    elif args.marker_length:
        print(f"[WARN] --marker-length 設定了，但找不到 {args.calib}，跳過姿態估算")

    # 來源
    src = make_source(args.source, args.video)
    OUT_DIR = r"D:\Things\markers"

    # 統計
    total_frames   = 0
    detected_frames= 0
    per_id_counts  = {}  # id -> 偵測到的幀數
    rejected_total = 0
    t_start = time.time()

    print("開始偵測，按 q 離開、s 截圖、r 重設統計")

    while True:
        frame = read_frame(src, args.source)
        if frame is None:
            break
        total_frames += 1

        if len(frame.shape) == 2:
            gray = frame
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        else:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # histogram equalize（ESP32 低對比）
        gray_eq = cv2.equalizeHist(gray)

        corners, ids, rejected = detector.detectMarkers(gray_eq)
        rejected_total += len(rejected) if rejected else 0

        overlay = frame.copy()

        if ids is not None:
            detected_frames += 1
            cv2.aruco.drawDetectedMarkers(overlay, corners, ids)

            poses = {}
            if K is not None and args.marker_length:
                from marker_loc import estimate_marker_poses
                poses = estimate_marker_poses(corners, ids, args.marker_length, K, dist_coeff)

            for i, mid in enumerate(ids.flatten()):
                mid_int = int(mid)
                per_id_counts[mid_int] = per_id_counts.get(mid_int, 0) + 1
                cx = int(corners[i][0][:, 0].mean())
                cy = int(corners[i][0][:, 1].mean())

                if mid_int in poses:
                    rvec = poses[mid_int]['rvec']
                    tvec = poses[mid_int]['tvec']
                    dist_m = float(np.linalg.norm(tvec))

                    # 畫座標軸
                    cv2.drawFrameAxes(overlay, K, dist_coeff, rvec, tvec,
                                      args.marker_length * 0.5)

                    # 標距離
                    cv2.putText(overlay, f"ID{mid_int}: {dist_m:.3f}m",
                                (cx - 40, cy - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                else:
                    cv2.putText(overlay, f"ID{mid_int}",
                                (cx - 10, cy - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 0), 2)

        # 側邊任務面板 (寬 200px)
        H, W = overlay.shape[:2]
        PANEL_W = 200
        canvas = np.zeros((H, W + PANEL_W, 3), dtype=np.uint8)
        canvas[:, :W] = overlay
        canvas[:, W:] = (30, 30, 30)  # 深灰背景

        # 面板標題
        cv2.line(canvas, (W, 0), (W, H), (80, 80, 80), 1)
        cv2.putText(canvas, "MISSION: ID 0-5", (W + 12, 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 1, cv2.LINE_AA)

        # 檢查 0-5 標記收集進度
        current_seen_ids = set(ids.flatten().astype(int)) if ids is not None else set()
        completed_count = 0

        for idx, target_id in enumerate(range(6)):
            box_y = 38 + idx * 28
            is_live = target_id in current_seen_ids
            has_seen = target_id in per_id_counts and per_id_counts[target_id] > 0

            if is_live:
                completed_count += 1
                # 當前畫面正看到 (亮綠高光)
                cv2.rectangle(canvas, (W + 8, box_y), (W + PANEL_W - 8, box_y + 24), (0, 180, 0), -1)
                dist_txt = f"{poses[target_id]['tvec'][2]:.2f}m" if target_id in poses else "SEEN"
                txt = f"[LIVE] ID {target_id} ({dist_txt})"
                color = (0, 0, 0)
            elif has_seen:
                completed_count += 1
                # 之前已成功辨識過 (綠色完成框)
                cv2.rectangle(canvas, (W + 8, box_y), (W + PANEL_W - 8, box_y + 24), (0, 70, 0), -1)
                cv2.rectangle(canvas, (W + 8, box_y), (W + PANEL_W - 8, box_y + 24), (0, 200, 0), 1)
                txt = f"[PASS] ID {target_id} (OK)"
                color = (0, 255, 150)
            else:
                # 尚未辨識 (灰色待解)
                cv2.rectangle(canvas, (W + 8, box_y), (W + PANEL_W - 8, box_y + 24), (45, 45, 45), -1)
                cv2.rectangle(canvas, (W + 8, box_y), (W + PANEL_W - 8, box_y + 24), (70, 70, 70), 1)
                txt = f"[    ] ID {target_id}"
                color = (130, 130, 130)

            cv2.putText(canvas, txt, (W + 16, box_y + 17),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)

        # 底部總體進度
        prog_y = 212
        if completed_count == 6:
            cv2.rectangle(canvas, (W + 8, prog_y - 2), (W + PANEL_W - 8, prog_y + 20), (0, 200, 255), -1)
            cv2.putText(canvas, "ALL 0-5 CLEAR!", (W + 16, prog_y + 14),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2, cv2.LINE_AA)
        else:
            cv2.putText(canvas, f"Progress: {completed_count}/6", (W + 14, prog_y + 12),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1, cv2.LINE_AA)

        # 左側視頻 HUD
        elapsed = max(time.time() - t_start, 1e-3)
        det_rate = detected_frames / max(total_frames, 1) * 100
        fps_str  = f"{total_frames/elapsed:.1f} fps"
        cv2.putText(canvas, f"FPS: {fps_str}  Det: {det_rate:.0f}%", (6, 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1, cv2.LINE_AA)

        # 放大為 1.5 倍方便觀看 (780 x 360)
        display_win = cv2.resize(canvas, ((W + PANEL_W) * 3 // 2, H * 3 // 2), interpolation=cv2.INTER_NEAREST)

        cv2.imshow("ArUco Test", display_win)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        elif key == ord("s"):
            ts = time.strftime("%H%M%S")
            p  = os.path.join(OUT_DIR, f"snapshot_{ts}.png")
            cv2.imwrite(p, canvas)
            print(f"[snap] {p}")
        elif key == ord("r"):
            total_frames = detected_frames = rejected_total = 0
            per_id_counts.clear()
            t_start = time.time()
            print("[reset] statistics cleared")

    cv2.destroyAllWindows()

    # 輸出統計摘要
    print("\n========== 偵測統計摘要 ==========")
    print(f"總幀數     : {total_frames}")
    print(f"有偵測幀數 : {detected_frames} ({detected_frames/max(total_frames,1)*100:.1f}%)")
        
    print(f"rejected 累計: {rejected_total}")
    print("各 ID 偵測幀數:")
    for mid in sorted(per_id_counts):
        r = per_id_counts[mid] / max(total_frames, 1) * 100
        print(f"  ID {mid}: {per_id_counts[mid]} frames ({r:.1f}%)")
    print("===================================")
    print("\n判讀標準:")
    print("  偵測率 >80%  → 穩定，可繼續步驟 3-4")
    print("  偵測率 50-80% → 邊緣，調整光照或放大 marker")
    print("  偵測率 <50%  → 不穩定，需要先改善（加大 marker / 改善光照）")

if __name__ == "__main__":
    main()
