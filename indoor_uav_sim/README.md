# 室內大樓救災無人機模擬系統 (Indoor Building Disaster Drone Simulation)

ROS2 Jazzy + Gazebo Harmonic + PX4 SITL 的多樓層室內搜救模擬。規格來源：`SPEC.md`（唯一規格，請以它為準）。

## 架構總覽

```
navigator ──/drone/cmd_vel_raw──► obstacle_avoider ──/drone/cmd_vel──► drone_control ──(MAVSDK offboard NED)──► PX4 SITL
    │                                                                      ▲
    │                                                                    /mission/command (land)
    │
    └─FusedPose(誤差)─► uwb_ranging_sim ──UwbRange──► uwb_trilateration ──/drone/uwb/pose──┐
marker_detector ──/drone/marker/pose (ArUco 無人機 world pose)──────────────┼──► pose_fusion ──/drone/pose/fused
                                                                             │
survivor_detector ──/drone/survivor/report──► mission_planner ──/mission/status /mission/command
anchor_manager ──(gz model spawn 動態錨點)──► /drone/uwb/deploy_request ──► mission_planner

gz bridge (ros_gz_bridge): sensor_nadir/image→/drone/camera/nadir/image_raw
                           sensor_front/image→/drone/camera/front/image_raw
                           sensor_lidar/scan →/drone/lidar/scan
```

10 個 ROS2 package（`drone_msgs` 定義 7 個 msg）：`drone_bringup`、`marker_localization`、`marker_navigation`、`pose_fusion`、`uwb_localization`（anchor_manager / uwb_ranging_sim / uwb_trilateration 三 node）、`obstacle_avoidance`、`survivor_detection`、`mission_control`、`drone_control`。

## 關鍵假設（spec §4 之實作對應）

| 項目 | 值 / 說明 |
|---|---|
| 樓層 | 3 層，層高 3.0 m，樓板厚 0.2 m（marker 地面 z = 0.25 / 3.25 / 6.25） |
| Marker | ArUco `DICT_7X7_1000`，500mm，**地板安裝**（nadir 相機向下看） |
| 生還者 | ID 900–999（901/902/903 座標在 `marker_map.yaml`） |
| 巡航高度 | 與 marker 座標**脫勾**：`z = (floor-1)*3.0 + 0.2 + 1.2` → 1.4 / 4.4 / 7.4 m |
| 換層 | 樓梯井中心 (-7,-2)（寬 2.8m × 長 2.8m、F2/F3 樓板開洞）：先水平對齊井口再垂直爬升 |
| 定位 | 預設 ArUco；連續 5 幀失鎖 → UWB fallback（4 錨點 LM 三維解）；恢復 3 幀 → 切回 |
| UWB | range 15 m、測距雜訊 N(0, 0.2²) m；**≥4 錨點**才有唯一 3D 解 |
| 控制 | cmd_vel 為 ENU（x=east,y=north,z=up），drone_control 轉 NED `(vy, vx, -vz)` |
| 世界座標原點 | F1 地面西南角為正？否：F1 樓板中面 z=0.1、東向 x、北向 y |

## 位置標記命名

- `ABC`：A=樓層(1-3)、B=區域(0=大廳/樓梯東側,1=西北,2=東北,3=南側)、C=編號
- `x09` / `x2y`：樓梯井入口/出口 marker
- `9x1–903`：生還者

## 目錄

- `spec/SPEC.md`（v2 全文）
- `doc/` — 系統設計、topic 清單、spec traceability（maps 於 `doc/*.md`）
- `tools/generate_marker_models.py` — 產生 marker SDF model + PNG texture 至 `src/drone_bringup/models/`
- `tools/gen_world.py` — 由 `marker_map.yaml` 產生 `src/drone_bringup/worlds/three_floor_building.sdf`
- `tools/patch_px4_model.py` — 注入 nadir/front camera + 2D lidar 至 PX4 x500 model（在容器內執行）
- `src/drone_bringup/config/` — marker_map / mission_waypoints / occlusion_zones / navigation_params / uwb_params / deployed_anchors / ros_bridge
- `test/` — 單元測試（trilateration 等）

## 容器建置與執行（在容器內）

```bash
docker compose up -d gazebo          # PX4 SITL + Gazebo Harmonic
docker compose up -d ros_nodes       # ROS2 工作區 + perception stack
docker compose exec ros bash
# 容器內：
source /opt/ros/jazzy/setup.bash
source install/setup.bash
python3 /workspace/disaster_drone_ws/tools/patch_px4_model.py   # 注入感測器（一次）
ros2 launch drone_bringup full_system.launch.py
```

> 感測器 bridge 的實際 gz topic 名以 `gz topic -l` 驗證，必要時調整 `config/ros_bridge.yaml`。

Phase 化執行（漸進驗收，規格 §9）：

```bash
ros2 launch marker_localization phase1_corridor.launch.py     # Phase 1：單走廊 marker 偵測
ros2 launch marker_navigation phase24_multifloor.launch.py    # Phase 2/4：多樓層導航
ros2 launch uwb_localization phase5_uwb.launch.py             # Phase 5：UWB 測距/定位
ros2 launch survivor_detection phase6_survivor.launch.py      # Phase 6：生還者偵測
ros2 launch drone_bringup full_system.launch.py               # Phase 7：全系統整合
```

Phase 0（takeoff/hover 驗收）在 `phase0/takeoff_hover_test.py`，連 `udpin://0.0.0.0:14540`。

## 驗證

```bash
python test/test_trilateration.py    # 4-anchor 最小二乘（host 可直接跑）
```

新增/修改 Python 後以 `python -c "import ast; ast.parse(...)"` 驗證語法（workspace rule）。