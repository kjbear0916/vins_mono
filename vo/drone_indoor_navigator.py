"""
drone_indoor_navigator.py — 室內無人機第一人稱視角（載具座標系）示教與相對導航系統
=================================================================================
【核心邏輯升級：第一人稱載具座標系 (Body/Camera-Centric Navigation)】
  1. 解決轉向問題：相機旋轉時，導航向量透過相機旋轉矩陣 R_w2c 即時投影到相機「當前視角」。
  2. 動態導引：
     - 當相機朝向目標時，箭頭永遠指向上方（正前方）。
     - 當相機轉動時，箭頭與轉向角度即時聯動（向左轉、向右轉、向後轉身）。
  3. 純相對位置：起點自動歸零為 (0, 0, 0)，所有航點與運動距離皆為相對公制。
  4. 抵達判定：走到目標半徑（預設 20cm）內，自動切換至下一個航點！
"""
import argparse
import math
import os
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from marker_loc import (estimate_marker_poses, IMG_W, IMG_H,
                        load_calibration)
from marker_positions import load_markers
from video_source import create_source


def make_detector():
    d = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    det = cv2.aruco.ArucoDetector(d, cv2.aruco.DetectorParameters())
    p = det.getDetectorParameters()
    p.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    p.cornerRefinementWinSize = 5
    det.setDetectorParameters(p)
    return det


def solve_camera_world_pose(rvec, tvec, marker_p, marker_R_m2w):
    """
    計算相機在世界座標中的位置 (p_c) 與旋轉矩陣 (R_c2w、R_w2c)。
    OpenCV 相機座標系：+X 畫面右、+Y 畫面下、+Z 視線正前方。
    """
    R_m2c, _ = cv2.Rodrigues(rvec)
    # 相機相對於標記的平移與旋轉
    R_c2m = R_m2c.T
    t_c2m = -R_c2m @ tvec.reshape(3, 1)

    # 相機在世界座標系的位置
    p_c_world = (marker_R_m2w @ t_c2m + marker_p.reshape(3, 1)).ravel()

    # 相機到世界的旋轉矩陣 R_c2w，以及世界到相機的旋轉矩陣 R_w2c
    R_c2w = marker_R_m2w @ R_c2m
    R_w2c = R_c2w.T

    return p_c_world, R_w2c, R_c2w


def draw_hud_compass(img, center, yaw_error_deg, dist_m, size=40):
    """繪製第一人稱 360° 導航儀表盤與方向指針"""
    cx, cy = center

    # 繪製外環刻度
    cv2.circle(img, (cx, cy), size, (60, 60, 60), 2, cv2.LINE_AA)
    cv2.circle(img, (cx, cy), size // 2, (45, 45, 45), 1, cv2.LINE_AA)

    # 刻度標示：前方(U), 後方(D), 左(L), 右(R)
    cv2.line(img, (cx, cy - size - 4), (cx, cy - size + 4), (0, 255, 0), 2)  # 正前方基準標線
    cv2.line(img, (cx - size - 4, cy), (cx - size + 4, cy), (80, 80, 80), 1)
    cv2.line(img, (cx + size - 4, cy), (cx + size + 4, cy), (80, 80, 80), 1)
    cv2.line(img, (cx, cy + size - 4), (cx, cy + size + 4), (80, 80, 80), 1)

    # 指向目標的動態箭頭
    rad = math.radians(yaw_error_deg)
    ex = int(cx + (size - 6) * math.sin(rad))
    ey = int(cy - (size - 6) * math.cos(rad))

    # 若已對準目標（誤差 < 15 度），箭頭變綠；否則為黃色
    arrow_color = (0, 255, 0) if abs(yaw_error_deg) <= 15 else (0, 220, 255)
    cv2.arrowedLine(img, (cx, cy), (ex, ey), arrow_color, 3, tipLength=0.35)
    cv2.circle(img, (cx, cy), 3, (255, 255, 255), -1)


def run_selftest():
    """Headless check of the body-centric pose math (no camera / no display).

    Builds a known camera<->marker geometry, runs solve_camera_world_pose and
    the guidance yaw, and asserts the recovered world pose, the marker_loc
    cross-check, and the yaw sign.
    """
    R_c2w = np.array([[0.0, 0.0, 1.0],
                      [1.0, 0.0, 0.0],
                      [0.0, 1.0, 0.0]])          # a nontrivial known camera orientation
    p_c = np.array([1.0, 2.0, 0.5])             # known camera position in world
    p_m = np.array([1.6, 2.0, 0.9])             # known marker position in world
    R_m2w = np.eye(3)

    R_m2c = R_c2w.T @ R_m2w
    t_m2c = R_c2w.T @ (p_m - p_c)
    rvec, _ = cv2.Rodrigues(R_m2c)
    tvec = t_m2c.reshape(3, 1)

    p_rec, R_w2c, R_c2w_rec = solve_camera_world_pose(
        rvec.ravel(), tvec.ravel(), p_m, R_m2w)

    from marker_loc import camera_abs_position
    p_cross = camera_abs_position(rvec.ravel(), tvec.ravel(), p_m, R_m2w)

    ok = (np.allclose(p_rec, p_c, atol=1e-9) and
          np.allclose(p_cross, p_c, atol=1e-9) and
          np.allclose(R_c2w_rec, R_c2w, atol=1e-9))

    fwd = R_c2w @ np.array([0.0, 0.0, 1.0])
    right = R_c2w @ np.array([1.0, 0.0, 0.0])
    target = p_c + 1.0 * fwd + 0.5 * right        # target ahead and to the right
    delta_cam = R_w2c @ (target - p_c)
    yaw = math.degrees(math.atan2(delta_cam[0], delta_cam[2]))
    yaw_ok = yaw > 0.0                            # right of view -> positive yaw

    print(f"[selftest] recovered cam pos = {p_rec}, cross-check = {p_cross}")
    print(f"[selftest] expected cam pos   = {p_c}")
    print(f"[selftest] yaw for right-target = {yaw:+.2f} deg (expect > 0)")
    if ok and yaw_ok:
        print("[selftest] PASS")
        return 0
    print("[selftest] FAIL")
    return 1


def main():
    ap = argparse.ArgumentParser(description="Indoor Drone Body-Centric Navigator")
    ap.add_argument("--stream", default="http://192.168.4.1:81/stream", help="ESP32 URL")
    ap.add_argument("--video", help="offline .avi file (file source); overrides --stream")
    ap.add_argument("--calib", default=r"D:\Things\vo\calibration_esp32_qvga_v2.npz")
    ap.add_argument("--markers", default=r"D:\Things\vo\marker_positions.json")
    ap.add_argument("--marker-m", type=float, default=0.15, help="Marker length in metres")
    ap.add_argument("--threshold-m", type=float, default=0.20, help="Arrival radius in metres")
    ap.add_argument("--allow-ambiguous", action="store_true",
                    help="use near-fronto-parallel marker poses flagged not "
                         "conditioned (obs #0015); off by default")
    ap.add_argument("--selftest", action="store_true",
                    help="run the headless pose-math check and exit")
    args = ap.parse_args()

    if args.selftest:
        sys.exit(run_selftest())

    print("[Navigator] Loading calibration & markers...")
    K, dist = load_calibration(args.calib)
    table = load_markers(args.markers)
    detector = make_detector()

    if args.video:
        print(f"[Navigator] Opening video file: {args.video}")
        src = create_source("file", path=args.video)
    else:
        print(f"[Navigator] Connecting to ESP32: {args.stream}")
        src = create_source("esp32", url=args.stream)

    mode = "TEACH"  # "TEACH" (示教模式) 或 "NAV" (自主導引)
    home_pos = None  # 原點 (0, 0, 0)
    current_world_pos = None
    current_R_w2c = None
    last_valid_time = 0

    waypoints = []  # 存相對起點的坐標: [np.array([x, y, z]), ...]
    current_wp_idx = 0
    reach_notification_timer = 0
    reach_notification_text = ""

    WIN_NAME = "Indoor Drone Body-Centric Navigator"
    cv2.namedWindow(WIN_NAME, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WIN_NAME, 960, 540)

    print("\n" + "=" * 60)
    print("【室內無人機第一人稱視角（載具座標系）導航系統已就緒】")
    print("  [空白鍵 SPACE] : 記錄當前位置為航點 (Waypoint)")
    print("  [N 鍵]         : 切換 示教模式 (TEACH) / 自主導航模式 (NAV)")
    print("  [H 鍵]         : 將當前位置重設為起點 Home (0, 0, 0)")
    print("  [R 鍵]         : 清空所有航點重設")
    print("  [Q 鍵]         : 退出程式")
    print("=" * 60 + "\n")

    while True:
        ok, frame = src.read()
        if not ok or frame is None:
            if args.video:
                break
            time.sleep(0.005)
            continue

        if len(frame.shape) == 2:
            gray = frame
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        else:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        eq = cv2.equalizeHist(gray)
        corners, ids, _ = detector.detectMarkers(eq)

        # 解算姿態與旋轉
        fused_pos = None
        best_R_w2c = None
        best_rms = 999.0
        seen_ids = []

        if ids is not None:
            cv2.aruco.drawDetectedMarkers(frame, corners, ids)
            obs_positions = []
            poses = estimate_marker_poses(corners, ids, args.marker_m, K, dist)

            for mid in ids.flatten():
                mid = int(mid)
                if mid in table and mid in poses:
                    if not poses[mid]["conditioned"] and not args.allow_ambiguous:
                        continue
                    pos, R_w2c, R_c2w = solve_camera_world_pose(
                        poses[mid]["rvec"], poses[mid]["tvec"],
                        table[mid]["p"], table[mid]["R"]
                    )
                    obs_positions.append(pos)
                    seen_ids.append(mid)

                    # 選取重投影誤差最小（最可靠）的標記作為當前航向參考
                    if poses[mid]["rms_px"] < best_rms:
                        best_rms = poses[mid]["rms_px"]
                        best_R_w2c = R_w2c

            if obs_positions:
                fused_pos = np.median(obs_positions, axis=0)
                current_world_pos = fused_pos
                current_R_w2c = best_R_w2c
                last_valid_time = time.time()

        # 建立寬版畫布 (左側相機畫面 320x240, 右側儀表資訊板 240x240)
        H, W = frame.shape[:2]
        PANEL_W = 240
        canvas = np.zeros((H, W + PANEL_W, 3), dtype=np.uint8)
        canvas[:, :W] = frame
        canvas[:, W:] = (22, 22, 22)

        # 分隔線
        cv2.line(canvas, (W, 0), (W, H), (65, 65, 65), 1)

        # 處理相對原點 (Home)
        if fused_pos is not None:
            if home_pos is None:
                home_pos = fused_pos.copy()
                print(f"[Home Locked] 起點 (0,0,0) 設定完成於空間坐標: {home_pos}")
            rel_pos = fused_pos - home_pos
        else:
            rel_pos = (current_world_pos - home_pos) if (current_world_pos is not None and home_pos is not None) else None

        # 判斷追蹤狀態
        tracking_alive = (time.time() - last_valid_time < 1.0) and (rel_pos is not None)

        # 頂部即時相對位置條
        if tracking_alive:
            rx, ry, rz = rel_pos
            pos_str = f"REL POS: X:{rx:+.2f}m Y:{ry:+.2f}m Z:{rz:+.2f}m"
            cv2.putText(canvas, pos_str, (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1, cv2.LINE_AA)
            cv2.putText(canvas, f"Tracking: Markers {seen_ids}", (8, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1, cv2.LINE_AA)
        else:
            cv2.putText(canvas, "[!] TRACKING LOST - 請讓鏡頭對準標記", (8, 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 1, cv2.LINE_AA)

        # 右側面板：模式與狀態
        mode_color = (0, 215, 255) if mode == "TEACH" else (0, 255, 120)
        cv2.putText(canvas, f"MODE: {mode}", (W + 12, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.58, mode_color, 2, cv2.LINE_AA)

        # 航點清單 (Waypoints List)
        cv2.putText(canvas, f"WAYPOINTS ({len(waypoints)})", (W + 12, 48),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1, cv2.LINE_AA)

        for i, wp in enumerate(waypoints[:6]):
            box_y = 56 + i * 23
            is_active = (mode == "NAV" and i == current_wp_idx)
            is_passed = (mode == "NAV" and i < current_wp_idx)

            if is_active:
                cv2.rectangle(canvas, (W + 8, box_y), (W + PANEL_W - 8, box_y + 19), (0, 140, 255), -1)
                text_col = (0, 0, 0)
                prefix = ">> NEXT:"
            elif is_passed:
                cv2.rectangle(canvas, (W + 8, box_y), (W + PANEL_W - 8, box_y + 19), (0, 65, 0), -1)
                text_col = (0, 255, 140)
                prefix = "[DONE] "
            else:
                cv2.rectangle(canvas, (W + 8, box_y), (W + PANEL_W - 8, box_y + 19), (38, 38, 38), -1)
                text_col = (170, 170, 170)
                prefix = f"WP {i+1}: "

            wp_txt = f"{prefix}({wp[0]:+.2f}, {wp[2]:+.2f}m)"
            cv2.putText(canvas, wp_txt, (W + 12, box_y + 14),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.36, text_col, 1, cv2.LINE_AA)

        # =========================================================================
        # 【第一人稱載具座標系核心解算 (Body-Centric Guidance)】
        # =========================================================================
        target_info_str = ""
        action_cmd_str = ""
        yaw_error_deg = 0.0

        if mode == "NAV" and waypoints and tracking_alive and current_R_w2c is not None:
            if current_wp_idx < len(waypoints):
                target_wp_rel = waypoints[current_wp_idx]
                target_wp_world = target_wp_rel + home_pos

                # 1. 計算世界座標中的目標向量 Delta_World
                delta_world = target_wp_world - current_world_pos

                # 2. 將目標向量投影至相機第一人稱座標系 Delta_Cam = R_w2c @ Delta_World
                #    X_cam: 相機右側(+)/左側(-)
                #    Y_cam: 相機下方(+)/上方(-)
                #    Z_cam: 相機前方(+)/後方(-)
                delta_cam = current_R_w2c @ delta_world
                dx_c, dy_c, dz_c = delta_cam

                dist_3d = float(np.linalg.norm(delta_cam))
                dist_horiz = math.sqrt(dx_c**2 + dz_c**2)

                # 3. 計算第一人稱視角下的航向偏差角 (Yaw Error)
                #    atan2(dx_c, dz_c)：0度代表在視線正前方，正值偏右，負值偏左
                yaw_error_deg = math.degrees(math.atan2(dx_c, dz_c))

                # 繪製中央無人機 360° 導航儀表盤
                draw_hud_compass(canvas, (W // 2, H // 2), yaw_error_deg, dist_3d, size=38)

                target_info_str = f"TO WP {current_wp_idx+1}: 距離 {dist_3d:.2f} m"

                # 4. 生成人性化運動指引指令（根據相機當前朝向）
                cmds = []
                # 轉向引導
                if abs(yaw_error_deg) <= 15:
                    cmds.append("【已對準目標】")
                elif 15 < yaw_error_deg <= 120:
                    cmds.append(f"【請向右轉 {int(yaw_error_deg)}°】")
                elif -120 <= yaw_error_deg < -15:
                    cmds.append(f"【請向左轉 {int(-yaw_error_deg)}°】")
                else:
                    cmds.append("【目標在身後！請轉身】")

                # 移動引導（沿當前視線前後左右）
                if dz_c > 0.15:
                    cmds.append(f"直行 {dz_c:.1f}m")
                elif dz_c < -0.15:
                    cmds.append(f"倒退 {-dz_c:.1f}m")

                if dx_c > 0.20:
                    cmds.append(f"向右平移 {dx_c:.1f}m")
                elif dx_c < -0.20:
                    cmds.append(f"向左平移 {-dx_c:.1f}m")

                action_cmd_str = " ".join(cmds)

                # 5. 抵達判定 (距離 < 門檻)
                if dist_3d < args.threshold_m:
                    current_wp_idx += 1
                    reach_notification_timer = time.time()
                    reach_notification_text = f"WP {current_wp_idx} REACHED!"
                    print(f"\a[Navigator] >>> 成功抵達航點 {current_wp_idx}！自動切換至下一個目標...")
            else:
                target_info_str = "ALL WAYPOINTS COMPLETED!"
                action_cmd_str = "巡航任務完成！請返回起點 Home"
                cv2.circle(canvas, (W // 2, H // 2), 15, (0, 255, 0), 2)

        # 繪製底層導航指令框
        if mode == "NAV":
            cv2.rectangle(canvas, (6, H - 46), (W - 6, H - 6), (0, 40, 0), -1)
            cv2.rectangle(canvas, (6, H - 46), (W - 6, H - 6), (0, 220, 0), 1)
            cv2.putText(canvas, target_info_str, (12, H - 28),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1, cv2.LINE_AA)
            cv2.putText(canvas, f">> {action_cmd_str}", (12, H - 12),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1, cv2.LINE_AA)

        # 抵達通知橫幅
        if time.time() - reach_notification_timer < 2.0 and reach_notification_text:
            cv2.rectangle(canvas, (W // 2 - 120, H // 2 - 25), (W // 2 + 120, H // 2 + 25), (0, 215, 255), -1)
            cv2.putText(canvas, reach_notification_text, (W // 2 - 105, H // 2 + 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 0), 2, cv2.LINE_AA)

        # 操作提示快捷鍵
        cv2.putText(canvas, "[SPACE] 記錄航點   [N] 模式切換", (W + 10, H - 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (130, 130, 130), 1)
        cv2.putText(canvas, "[H] 起點歸零  [R] 清空  [Q] 離開", (W + 10, H - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (130, 130, 130), 1)

        # 放大為 1.5 倍高解析顯示 (720x360)
        display_win = cv2.resize(canvas, ((W + PANEL_W) * 3 // 2, H * 3 // 2), interpolation=cv2.INTER_LINEAR)
        cv2.imshow(WIN_NAME, display_win)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        elif key == ord(" "):  # 空白鍵記錄航點
            if tracking_alive and rel_pos is not None:
                waypoints.append(rel_pos.copy())
                print(f"[Teach] 航點 {len(waypoints)} 已記錄: 相對起點 X={rel_pos[0]:+.2f}m, Y={rel_pos[1]:+.2f}m, Z={rel_pos[2]:+.2f}m")
            else:
                print("[Teach] 記錄失敗：畫面中沒有辨識到標記，請對準標記後再按空白鍵！")
        elif key == ord("n"):  # 切換模式
            if mode == "TEACH":
                if waypoints:
                    mode = "NAV"
                    current_wp_idx = 0
                    print(f"[Navigator] 切換至【自主導航模式 (NAV)】！開始引導前往航點 1...")
                else:
                    print("[Navigator] 尚未記錄任何航點！請先在示教模式下按 [空白鍵] 記錄至少一個航點。")
            else:
                mode = "TEACH"
                print("[Navigator] 切換回【示教模式 (TEACH)】。")
        elif key == ord("h"):  # 重設起點 Home
            if fused_pos is not None:
                home_pos = fused_pos.copy()
                print(f"[Home Reset] 起點 (0, 0, 0) 已重設為當前位置！")
        elif key == ord("r"):  # 清空重來
            waypoints.clear()
            current_wp_idx = 0
            mode = "TEACH"
            print("[Reset] 航點已全數清空。")

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
