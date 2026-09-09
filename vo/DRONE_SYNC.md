# 無人機 VO 時間同步骨架(drone_sync.py)

## 動機

ESP32 相機經 WiFi 串流到 PC,`record_clean_seq.py` 存下的 AVI 本身**沒有
逐幀時間戳**(僅 meta 記 fps)。接收端(無人機飛控/OSD/IMU 記錄)有自己的
wall-clock。WiFi 延遲可變 → 錄到「外觀像第 k 幀」的畫面不一定是 log 寫 timestamp
那一刻的畫面。

需要一層「log 時間 ↔ 相機幀 ↔ VO keyframe」的對齊,融合/BA 才能在共同時間軸
上作業。

## 介面契約(檔案格式)

1. **接收端 log**(CSV,表頭:ts_ms, roll_deg, pitch_deg, yaw_deg, alt_m,
   vx, vy, vz)。`ts_ms` 是接收端的毫秒紀元。
2. **相機 meta**(`record_clean_seq.py` 輸出的 `*_meta.json`):`fps`、
   `frames.{HOLD0,MOVE,HOLD1}`。假設幀 i 的時刻 = i/fps(原點 0)。
3. **VO 軌跡**(`test_incr_pnp.py` 輸出的 `*_traj.csv`):每列有 `frame`
   (幀號)與 `pre_x/pre_y/pre_z`(BA 前相機中心)。

## 對齊策略

- `align_frames(log_ts, cam_ts)`:雙向 nearest-neighbour(`searchsorted`,
  純 numpy)。回傳 `log_to_cam`(每條 log 落在哪一幀)與 `cam_to_log`。
- `SyncTrajectory.sync_points()`:以 log 節奏輸出
  `(t_sec, x, y, z, roll, pitch, yaw)`,每個 log 行:log↔cam 幀號 → 找最近
  VO keyframe 取 pose + log 的姿態角 → 融合成一條流。

## 已知限制(這個 skeleton 先不處理)

- ~~相機幀時鐘只從 fps/kf 推導~~ → **已解決**:`record_clean_seq.py` 現在把每幀
  `wall_t` 寫進 meta 的 `per_frame_ts`;`SyncTrajectory` 看到它就優先使用(它
  保留真實掉幀的時序),沒有才退回 `i/fps`。
- 未做系統時鐘同步(log 與 PC 各走各的時鐘):skeleton 用「同 0 原點」假設,
  實務需抓頭尾 HOLD 校正 offset(掛鉤 `align_frames` 已備)。
- 未接 IMU 預積分 / 視覺-慣性緊耦合:此骨架只做「時間對齊 + pose 提取」,
  供下游 BA/fusion 使用。

## 驗證

`align_frames` 純函數 + `SyncTrajectory` 端到端(假 log/meta/traj,含
`per_frame_ts` 優先與 n_cam 全 phase 合計)由 regression 覆蓋:
```
python -m unittest vo.test_regression.TestSyncTrajectoryE2E -v
```

## 下一步(有實錄後)

1. `record_clean_seq.py` 的逐幀 `wall_t` 改為↔ 共享 clock(PC 端與飛控
   NTP/PTP or GPS-PPS),消除剩餘的「PC 端單一時鐘」近似;再抓頭尾 HOLD 用
   `align_frames` 校正 log↔frame 的固定 offset。
2. 用一段 real_seq(含 log)跑 `SyncTrajectory` 產 fused CSV,餵
   `run_offline_ba.py` 做同步後 BA,比較對齊前後 reproj。