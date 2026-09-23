# disaster_drone_ws — 室內大樓救災無人機模擬系統 v2

ROS2 (Jazzy) + Gazebo (Harmonic) + PX4 SITL 多樓層室內搜救無人機模擬。
依「技術規格書 v2」實作：ArUco 視覺定位 + 動態 UWB 錨點備援 + LiDAR 避障 +
開放式樓梯中廊垂直換層 + 生還者偵測回報。

## 總覽

```
disaster_drone_ws/
├── docker/                 Dockerfile (sim: gz+px4 / ros: 節點) + docker-compose.yml
├── requirements.txt        python 相依 (釘死版本，規格 §10)
├── src/
│   ├── drone_msgs/         自訂訊息型別
│   ├── drone_bringup/      場景產生器、world/model、launch 檔、marker_map / occlusion_zones
│   ├── marker_localization/ ArUco 偵測 + solvePnP + 世界座標轉換 (+ 模擬偵測備援)
│   ├── uwb_localization/   anchor_manager / uwb_ranging_sim / uwb_trilateration
│   ├── pose_fusion/        ArUco ⇄ UWB 定位來源切換
│   ├── marker_navigation/  航點狀態機 (含中廊換層)
│   ├── obstacle_avoidance/ LiDAR 反應式避障
│   ├── survivor_detection/ 生還者標記偵測
│   └── mission_control/    任務協調 + /mission/status
└── tests/                  純 Python 主機可跑單元測試 (trilateration / fusion)
```

## 快速開始

前置：Linux (或 WSL2/Ubuntu 24.04) + Docker + 16 GB RAM、約 40 GB 磁碟。

```bash
cd disaster_drone_ws/docker
docker compose build          # PX4 編譯較久 (ob #25: make px4_sitl 會在 build 期間掛住 → 影像建置只編譯不啟動)
docker compose up sitl        # 起 PX4 SITL + Gazebo Harmonic (headless 預設)
# 另一個終端機:
docker compose up ros         # 建置 + 執行 ROS2 節點 + ros_gz bridge
```

逐 Phase 驗收對應 launch：

| Phase | 內容 | launch |
|-------|------|--------|
| 0 | PX4 SITL + Gazebo 跑通起飛懸停 | `launch_phase0.py`(bridge + MAVSDK takeoff test) |
| 1 | 單走廊 marker 導航 | `launch_phase1.py` |
| 2 | 單樓層多房間 | `launch_phase2.py` |
| 3 | 避障 | `launch_phase3.py` |
| 4 | 中廊垂直換層 (2 層) | `launch_phase4.py` |
| 5 | UWB 錨點部署 + 遮蔽備援 | `launch_phase5.py` |
| 6 | 生還者偵測 | `launch_phase6.py` |
| 7 | 完整整合 (3 層) | `launch_phase7.py` |

主機端（不需要 ROS/容器）即可先驗證 Phase 5 數學：

```bash
python tests/test_trilateration.py
python tests/test_fusion.py
```

## 已知假設 / 決策 (agent 依規格 §10 選定的預設值)

- UWB 有效測距範圍 15 m、雜訊 std = 0.2 m（`drone_bringup/config/drone_params.yaml` 可調）。
- 生還者標記使用專屬 ArUco ID 900–999（規格 §11 建議選項，Reuse 同一條偵測管線）。
- 錨點無限供應、永久留存、全部寫入 `deployed_anchors.yaml`。
- PX4 固定 `v1.16.0` (Harmonic 支援)，Gazebo Harmonic 8 (LTS)，ROS2 Jazzy。
- marker 即為薄盒模型，表面貼由 cv2 產生的 ArUco PNG 紋理；若使用者環境的
  OGRE 材質綁定失敗（Harmonic/ogre2 對 `file://` 紋理較敏感），可用
  `marker_localization.simulate_detections=true` 以 ground truth + 視錐判定代替——
  這是規格未規定、純為讓 Phase 1 可驗收的備援，非主要路徑。
- 視覺遮蔽情境由 `occlusion_zones.yaml` 描述；Phase 5 手動驗證時把對應 marker
  移出相機視野即可觸發 UWB 切換。

## 架構與資料流

見規格 §3/§7。核心差別：本實作把「可驗證邏輯」全部收進 `<pkg>/core.py`
（零 rclpy import），ROS node 只是薄的 wrapper，故 trilateration、融合狀態機、
遮蔽區域解析都能在主機上單元測試；容器內才吃 rclpy。

## 在容器內開發

```bash
docker compose exec ros bash
cd src && colcon build --symlink-install
source install/setup.bash && ros2 launch drone_bringup launch_phase7.py
```

## 除錯筆記（先前實作踩過的坑）

- **PX4 build 會在 build 期間掛住**：`make px4_sitl gz_xxx` 是「編譯＋啟動」，
  不可在 Dockerfile RUN 中執行；先 `make px4_sitl_default` 編譯，啟動交給
  entrypoint（見 `docker/entrypoint_sitl.sh`）。
- **Shell 延續性**：Dockerfile/entrypoint 避免 `|| true &&` 這種先例陷阱
  (ob #26)；用 `cmd1 || { echo fail; exit 1; }` 明確分隔。
- **Harmonic 需要 `--force-version`**：PX4 v1.16 用 gz Harmonic libs
  (transport14 / msgs10)，若同機殘留 Garden libs，命令要鎖版本
  （參照 `indoor_uav_sim/phase0/bin/gz` shim）。
- **pip 與 ROS 打包**：容器內不要 `pip install -U setuptools` 裸奔
  (ob #29)，相依一律走本 repo 的 `requirements.txt` 釘板。

## 里程碑記錄

- 本 commit：完整 v2 規格 scaffold + 全部模組首版實作 + 主機單元測試。
- 尚未在容器內執行過任一 Phase（Windows host，PX4/Gazebo 無法在此驗收）。
  依規格 §0，逐 Phase 在 Linux 機器上驗收；`README` 假設清單已有預設值可調。