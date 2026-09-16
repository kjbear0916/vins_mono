# 室內大樓救災無人機模擬系統 — 技術規格書 v2

用途：交給 AI coding agent（如 opencode）直接依此規格實作。v2 已整合所有確認過的設計決策（樓梯中廊換層、ArUco+UWB 混合定位、動態錨點部署）。

## 0. 複雜度提醒（誠實說明）

這份規格現在包含：多樓層 3D 建模、視覺定位、無 GPS 飛控定位來源替換、避障、生還者偵測、加上一套自製的動態 UWB 錨點部署與定位備援系統。最後一項本質上是在做一個小型 SLAM-like 定位基礎設施，不是隨手可以生出來的功能。建議不要期待 agent 一次生成就能跑，而是照第 9 節的階段規劃、一段一段驗收。

## 1. 專案目標

在 ROS2 + Gazebo + PX4 SITL 環境中模擬一台四旋翼無人機，於多樓層大樓室內環境中：

- 用 ArUco marker 定位並沿航點自動導航（主要定位來源）
- 在視覺可能失效的區域（轉角、大開放空間、樓梯中廊）主動部署 UWB 錨點，作為定位備援
- 用 LiDAR / 深度相機做即時避障
- 透過開放式樓梯中廊在樓層間垂直飛行
- 模擬偵測「生還者」標記並回報座標，部署的 UWB 錨點作為給後續救援單位使用的臨時定位基礎建設留在原地

## 2. 技術棧與版本

| 項目 | 選擇 | 理由 |
|---|---|---|
| OS | Ubuntu 24.04（Docker 容器內） | 開發環境現況不確定，容器化確保可重現 |
| ROS2 | Jazzy Jalisco | 與 Gazebo Harmonic 是官方預編譯二進位配對 |
| 模擬器 | Gazebo Harmonic（LTS 支援至 2028/09） | PX4/ArduPilot 官方教學目前指向 Harmonic |
| 飛控 | PX4-Autopilot（最新穩定 release）SITL | 官方 x500 模型 + 深度相機/LiDAR 外掛 |
| 橋接 | ros_gz（ros_gz_bridge, ros_gz_sim） | 官方標準橋接 |
| 無人機控制 | MAVSDK-Python | async API 適合搭配 ROS2 狀態機 |
| 視覺 | opencv-contrib-python（cv2.aruco） | ArUco 偵測與 solvePnP |
| UWB 模擬 | 自製 Python 節點（無 Gazebo 原生 UWB 感測器） | 讀取 Gazebo ground truth 距離 + 高斯雜訊模擬測距 |

## 3. 系統架構

```
                    ┌────────────────────┐
                    │   Gazebo Harmonic   │  多樓層大樓 + 開放樓梯中廊 + PX4 x500
                    │  (world + models)   │  (下視相機／前視深度相機／2D LiDAR)
                    └─────────┬───────────┘
                              │ ros_gz_bridge
                    ┌─────────▼───────────┐
                    │      ROS2 Jazzy      │
                    └─────────┬───────────┘
   ┌───────────┬──────────┬──┴───────┬───────────┬───────────┐
   ▼           ▼          ▼          ▼           ▼           ▼
marker_    uwb_        obstacle_  survivor_   mission_    drone_
localiz.   localization avoidance detection   control     bringup
   │           │           │          │           │
   └── pose ───┴─ pose ────┴─ cmd_vel/setpoint ───┘
              (pose_fusion 依信心度切換來源)
                        │
                  MAVSDK-Python
                        │
                   PX4 SITL（MAVLink）
```

## 4. Docker 容器建置重點

- Base image：osrf/ros:jazzy-desktop
- 安裝：ros-jazzy-ros-gz、PX4-Autopilot（make px4_sitl）、gz-harmonic
- Python：mavsdk、opencv-contrib-python、numpy、transforms3d、scipy（trilateration 用最小平方法）
- 用 docker-compose.yml 拆成 Gazebo+PX4 一個 service、ROS2 nodes 一個 service

## 5. 場景設計：多樓層大樓

### 5.1 建議規模

- 先建 3 層樓，每層 2–3 個房間 + 走廊，加 1 座開放式樓梯中廊貫穿全部樓層
- 每層樓高 3m；樓梯中廊為挑空設計，無人機可從中廊空間垂直穿越各樓層平台間隙（不需要真的沿樓梯踏步飛，是走中間挑空的垂直通道）

### 5.2 Marker ID 編碼規則

- `marker_id = 樓層(1位數) * 100 + 房間(1位數) * 10 + 該房間內航點序號(1位數)`
- 例：203 → 2樓、房間0（走廊）、第3個航點
- 樓梯中廊固定用 房間編號 9（例：109, 209, 309 = 各樓層進入中廊的入口點）
- 保留 900–999 給「生還者」標記
- `marker_map.yaml`：每個 marker ID 對應世界座標 (x, y, z, yaw)

### 5.3 佈置密度

密集佈署：走廊/房間每 1–2 公尺一個 marker，確保定位穩定

### 5.4 視覺遮蔽風險區標記（新增）

新增 `occlusion_zones.yaml`，標記哪些航點/區域「進入前」要先部署 UWB 錨點：

```yaml
zones:
  - id: corner_2F_A
    type: corner
    trigger_waypoint: 212       # 到這個 marker 附近就要先部署錨點
    risk_level: high
  - id: stairwell_atrium
    type: open_space
    trigger_waypoint: 109
    risk_level: high
  # 轉角、樓梯中廊入口、大開放空間都列進來
```

### 5.5 相機配置

- 下視相機（nadir）：地板 marker 精確定位
- 前視深度相機 或 2D LiDAR：避障
- 前視 RGB 相機：生還者標記偵測

## 6. ROS2 Package 結構

```
disaster_drone_ws/
└── src/
    ├── drone_bringup/         # launch files, world/model, marker_map.yaml, occlusion_zones.yaml
    ├── marker_localization/   # ArUco 偵測 + solvePnP + pose 發布
    ├── uwb_localization/      # 【新增】錨點部署管理 + 測距模擬 + trilateration
    │   ├── anchor_manager     # 判斷何時部署新錨點、維護已部署清單、寫入 deployed_anchors.yaml
    │   ├── uwb_ranging_sim    # 對範圍內已部署錨點模擬測距（ground truth 距離 + 雜訊）
    │   └── uwb_trilateration  # 用 ≥3 個錨點測距做最小平方法定位
    ├── pose_fusion/           # 【新增】依 ArUco 是否可信，在 ArUco pose 與 UWB pose 間切換/融合
    ├── marker_navigation/     # waypoint 狀態機，含樓層轉換（經樓梯中廊）邏輯
    ├── obstacle_avoidance/    # LiDAR/深度相機避障
    ├── survivor_detection/    # 生還者標記偵測 + 回報
    ├── mission_control/       # 任務協調（探索順序、換層、彙整回報）
    └── drone_msgs/            # MarkerPose, UwbAnchor, UwbRange, FusedPose, SurvivorReport, MissionStatus
```

## 7. Topic / 訊息設計

| Topic | 型別 | 發布者 → 訂閱者 | 說明 |
|---|---|---|---|
| /drone/camera/nadir/image_raw | sensor_msgs/Image | Gazebo → marker_localization | 下視相機畫面 |
| /drone/marker/pose | drone_msgs/MarkerPose | marker_localization → pose_fusion | 偵測到的 marker 世界座標 + 信心度 |
| /drone/uwb/anchors | drone_msgs/UwbAnchor[] | anchor_manager → uwb_ranging_sim, mission_control | 目前已部署錨點清單（含永久記錄） |
| /drone/uwb/ranges | drone_msgs/UwbRange[] | uwb_ranging_sim → uwb_trilateration | 模擬測距結果（含雜訊） |
| /drone/uwb/pose | geometry_msgs/PoseWithCovariance | uwb_trilateration → pose_fusion | UWB 推算位置 |
| /drone/pose/fused | geometry_msgs/PoseWithCovariance | pose_fusion → marker_navigation, obstacle_avoidance | 最終採用的定位（ArUco 優先，UWB 備援） |
| /drone/lidar/scan | sensor_msgs/LaserScan | Gazebo → obstacle_avoidance | 避障掃描資料 |
| /drone/survivor/report | drone_msgs/SurvivorReport | survivor_detection → mission_control | 生還者座標＋信心度 |
| /mission/status | drone_msgs/MissionStatus | mission_control → 全域 | 目前樓層/航點/任務階段/已部署錨點數 |

## 8. 核心演算法邏輯

### 8.1 Marker 定位

cv2.aruco.detectMarkers → solvePnP 得相機座標系相對姿態 → 查 marker_map.yaml → 轉換為世界座標 → 發布 /drone/marker/pose

### 8.2 動態 UWB 錨點部署（新增核心邏輯）

```
IF 目前定位來源 == ArUco（信心度高）
   AND 下一個目標航點在 occlusion_zones.yaml 中被標記為高風險
THEN
   在目前位置（此刻仍是 ArUco 信任的座標）部署一顆新錨點：
     - anchor_id = 遞增序號
     - anchor_pose = 目前 fused_pose（此刻來源是 ArUco，可信）
     - 寫入 /drone/uwb/anchors，並 append 進 deployed_anchors.yaml（永久記錄）
     - 在 Gazebo 中 spawn 一個錨點視覺化模型（方便除錯，也象徵留給其他救援單位的實體裝置）
   才繼續往高風險航點移動
```

錨點視為無限供應（不模擬酬載限制），全部永久留存、寫入 deployed_anchors.yaml，象徵為這棟大樓建立的臨時定位基礎建設。

### 8.3 UWB 測距模擬

對每個已部署且在模擬「有效測距範圍」內（例如 15–20m，可調參數）的錨點：

```
range_measurement = euclidean_distance(drone_ground_truth_pose, anchor_pose) + gaussian_noise(mean=0, std=可調, 例如 0.1~0.3m)
```

≥3 個錨點測距時，uwb_trilateration 用最小平方法（scipy.optimize.least_squares）解出位置估計。

### 8.4 Pose Fusion（定位來源切換）

```
狀態: SOURCE_ARUCO（預設）｜ SOURCE_UWB_FALLBACK
- marker 連續 N 幀（例如 1~2 秒）偵測不到 且 目前在/接近已標記的 occlusion zone
    → 切換到 SOURCE_UWB_FALLBACK，改用 /drone/uwb/pose
- 重新偵測到 marker → 切回 SOURCE_ARUCO
- 發布統一的 /drone/pose/fused 供下游（navigation, avoidance）使用，下游不需要關心目前用哪個來源
```

### 8.5 導航狀態機

IDLE → SEARCHING_MARKER → CHECK_OCCLUSION_ZONE(需要就先部署錨點) → ALIGNING → MOVING_TO_WAYPOINT → ARRIVED → NEXT_WAYPOINT

樓層轉換：航點類型為「中廊入口」時，改為沿樓梯中廊挑空垂直上升/下降到下一樓層對應中廊入口 marker，而非水平飛行

### 8.6 避障

簡單反應式（LiDAR 扇形距離 + 速度向量修正）；跑通後可接 Nav2 local costmap 做進階版本

### 8.7 生還者偵測

特殊 marker/顏色代表待救者 → 記錄 /drone/pose/fused 當下座標 → 發布 SurvivorReport → mission_control 決定繼續探索或立即回報

## 9. 開發階段規劃（務必照順序，每階段獨立可驗收）

| 階段 | 內容 | 驗收標準 |
|---|---|---|
| Phase 0 | Docker + ROS2 Jazzy + PX4 SITL + Gazebo Harmonic 跑通官方 demo | make px4_sitl gz_x500 能起飛懸停 |
| Phase 1 | 單走廊 marker 導航 | 沿 3–4 個 marker 航點自動飛行到終點 |
| Phase 2 | 單樓層多房間 | 依 marker_map.yaml 走完整層路徑 |
| Phase 3 | 避障 | 走廊放障礙物，能繞過不撞牆 |
| Phase 4 | 開放樓梯中廊垂直換層（先做 2 層樓） | 能從 1F 中廊入口垂直飛到 2F 中廊入口並繼續導航 |
| Phase 5 | UWB 錨點部署 + 視覺遮蔽定位備援 | 人工在單一房間製造「marker 遮蔽」情境，驗證會自動部署錨點、切到 UWB 定位、事後切回 ArUco |
| Phase 6 | 生還者偵測與回報 | 場景放生還者標記，任務結束輸出座標清單 |
| Phase 7 | 完整整合：3 層樓完整大樓 + 所有模組 | 完整跑一次「起飛→多樓層搜索（含中廊換層＋UWB備援）→回報→返航」，deployed_anchors.yaml 有完整永久記錄 |

## 10. 給 opencode（或其他 AI coding agent）的執行提醒

- 每個 Phase 都要有獨立可跑的 launch file，不要等全部做完才第一次執行
- 版本號寫死在 requirements.txt / Dockerfile
- Phase 5（UWB）風險最高，建議先寫一個不含 Gazebo 的純 Python 單元測試（假座標）驗證 trilateration 數學邏輯，再接進完整系統
- 按 Phase／模組切 git commit
- 遇到規格未寫清楚的細節（例如 UWB 測距有效範圍的確切數字、雜訊標準差），agent 應該先選一個合理預設值並在 README/commit message 註明假設，而不是卡住不動

## 11. 殘留待確認事項（規格已大致完整，僅剩實作時的微調參數）

- UWB 模擬測距的有效範圍與雜訊標準差確切數值（先用預設 15m / std=0.2m，可事後調）
- 生還者標記的視覺設計（顏色 vs 專屬 ArUco ID 範圍 900–999，建議先用後者，重用同一套偵測管線）
- 3 層樓以外要不要繼續擴充樓層數，等 Phase 7 跑通再決定