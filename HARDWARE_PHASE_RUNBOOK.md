# Hardware Phase Runbook — Marker 室內定位 + QVGA 標定

本文件是「軟體已完成、硬體未開始」的執行順序。每一步都標出命令、期望輸出、
失敗時的處置。所有 clip 檔存到 `D:\Things\vo\` 下（與其他 t 一致）。

前置檢查（PC 端離線，無需硬體）：
  python -m unittest vo.test_regression        # 26/26 應全過
    → 原本是 25/25；26 是合成標定封閉測試（見下第 3 步背景），
      證明校正管線能從已知 K 恢復 fx 後才值得錄影。

---

## 順序總覽

  A. 印製 marker + 實量邊長（--marker-m）
  B. 建立 test room + PC 連 ESP32 AP
  C. PC 連線偵測測試（aruco_detect_test --snapshot 60）
  D. **QVGA 棋盤標定錄影（最先決，obs #0024 守則）**
  E. 標定 NPZ 驗證（calib_sanity --clip --z-hint）
  F. 佈署 marker → 量測絕對座標 → 更新 marker_positions.json
  G. 實測 marker 定位 → ATE 定案（focal 假說收斂）

**建議真正動手順序：D 最先**（它決定 fx，影響 G 的 ATE 與 marker 距離準度），
然後才印 marker。印表機排程不好時 A/D 可對調，但絶不要先跑 G 再補 D。

---

## A. 印製 marker + 實量邊長

印出 `D:\Things\markers\marker_00.png` ~ `marker_05.png`（6 個 DICT_4X4_50）。
建議每張列印在白紙，量 **黑色實心外框的邊長**（不是整張紙，是黑色框的
外緣）。

換算：如果 PNG 設計邊長是 15cm，印出後往往有 ±1-2mm 縮放。

記錄：
  marker_00 黑色框邊長 = ____ mm
  marker_01 .. 05（同紙材/印表機下應一致，逐張量 0 號 + 抽 1 張）

輸入到 G 步：`tests/test_marker_detect.py --marker-length <m>` 與
`localise_video.py --marker-m` 需用**量到的**值，不是 0.15。

完成判據：6 張皆印出，黑色框完整、無白邊遮蓋，邊長已實量並記錄。

---

## B. test room + ESP32 AP

架設（依 PROGRESS.md 已規劃）：
  test room ~2.5 x 3.0 x 2.2 m（與 marker_positions.json placeholder 對應）
  ESP32-CAM 上電 → 預設 AP 模式 `RatMonitor_Setup`（firmware 預設）

PC 連上該 AP（無網際網路的純 AP），測通：
  ping 192.168.4.1

完成判據：PC 可 ping 通 ESP32。

---

## C. PC 連線偵測測試（marker 印好之前可用現成圖檔）

連線存活：
  python vo/aruco_detect_test.py --snapshot 60 --url http://192.168.4.1:81/stream
    → 期望：snapshot 統計、detection rate >80%，exit 0

判讀（程式內建標準）：
  >80% → 穩定，可進下一步
  50-80% → 邊緣：調整光照/加強對比後再測
  <50% → 先改善（加大 marker / 改善光照 / 檢查焦點）

無硬體時的離線預演（不連 ESP32）：
  python vo/aruco_detect_test.py --snapshot 60 --url D:\Things\markers\marker_00.png
    → 改跑單張圖檔模式，驗證 detector 在 D:\Things\vo 目錄下能載入即可
    （此節僅驗證軟體路徑，實際仍待真機）

常用 GUI 檢查（鏡頭/影片來源）：
  python markers/test_marker_detect.py --source webcam
  python markers/test_marker_detect.py --source video D:\Things\vo\<clip>.avi

完成判據：真機 60 幀偵測率 >80%，且各 ID 都偵測得到。

---

## D. QVGA 棋盤標定錄影（最先決）

目標 clip：`calibration_esp32_qvga_v2.npz`（取代現有 fx=282/cy=30.6 損壞者）。
工具：`vo/calibrate_guided.py`（即時 HUD 引導 30 樣本）或
      `vo/recalibrate_from_frames.py`（離線批處理錄影）。

錄影內容（**obs #0024 守則，最重要**）：
  1. **近距離**：讓棋盤外框**幾乎填滿整個 320px 畫面**（最外圍 corner
     靠近影像邊緣；r_max → 影像角落）。
     → 沒有接近邊緣的幀，fx 與 k1/k2/k3 不可分離，即便姿態多樣性閘門
       全過也會得到 fx~2000 的偽裝解（合成已驗證）。
  2. 覆蓋 5 個 zone：左上 / 右上 / 中央 / 左下 / 右下。
  3. 傾斜 ±30-45°（板法線遠離光軸）。
  4. 近 / 中 / 遠 三種距離（**近=填滿畫面**，遠=棋盤約 1.5m 外，縮小到
     約 1/4 畫面）。
  5. 曝光/對比穩定，無運動模糊（錄影時慢移）。

**畫面右側 REQ 面板**逐項列出完成要求：`edge-fill`(外角貼邊<24px)、
`tilt>=2`、`sample n/30`、`NEAR/MID/FAR`、`GRID 3x3`；**全綠才會自動存檔
並列印 gate 明細 + `OK PASS`**。按 q 提前離開會在終端印出 MISSING 清單
（如缺 `edge-fill(near)`=棋盤沒近到貼邊，回去補拍）。

即時引導錄影：
  python vo/calibrate_guided.py --url http://192.168.4.1:81/stream ^
      --pattern 5x4 --square 25 --samples 30 ^
      --out D:\Things\vo\calibration_esp32_qvga_v2.npz
    → HUD 上 3x3 dots 全綠 + z bins 全綠 + SAMPLE 到 30 即自動存。

離線（若先錄 .avi）：
  python vo/recalibrate_from_frames.py --video vo/<calib_v2>.avi ^
      --pattern 5x4 --square 25 --samples 30 ^
      --out vo/calibration_esp32_qvga_v2.npz
    → 應先印出「pose-diversity gate PASSED」；若 REJECTED 代表錄影
      姿態多樣性不足（含邊緣覆蓋不足），回到上述守則重錄。

錄後把關（calib_sanity 閘門，recalibrate 已內建）：
  python vo/calib_sanity.py vo/calibration_esp32_qvga_v2.npz ^
      --clip vo/<calib_v2>.avi --z-hint <m>
    → 期望 PASS: all checks OK + consistent with the independent distance
    → --z-hint 是錄影當下的板距獨立估計（例如 rig 幾何 0.8m）；
      fx 錯誤時 median solvePnP z 會偏離（fx 越高 z 越低）。

完成判據：v2 npz 產生、**`calibrate_guided` 印出 `OK PASS`**、calib_sanity 全
PASS、fx 落在合理帶（約 282-900，以 59°~20° HFOV 合理區間 + z-hint 交叉
驗證後定案）。

---

## E. 標定 NPZ 驗證（獨立於錄影腳本的檢查）

  python vo/calib_sanity.py vo/calibration_esp32_qvga_v2.npz --width 320 --height 240
    → PASS: all checks OK（無 cy<0.3h / HFOV<25° / dist>50 警告）

z-hint 交叉驗證（若 v2 錄影保留 z 參考）：
  python vo/calib_sanity.py vo/calibration_esp32_qvga_v2.npz ^
      --clip vo/<calib_v2>.avi --pattern 5x4 --square 25 --z-hint <m>
    → 「consistent with the independent distance reference」

完成判據：上述皆 PASS。此步取代「fx 假說二擇一」，直接以錄影閉鎖。

---

## F. 佈署 marker 量測絕對座標 → 更新 marker_positions.json

辦公室/家中選擇房間對應 placeholder：
  0 door wall (z=0) 面向 +Z、1 back wall (z=3) 面向 -Z、
  2 left wall (x=0) 面向 +X、3 right wall (x=2.5) 面向 -X、
  4 ceiling (y=2.1) 面向 -Y、(5 floor 選用)

量測每個 marker **中心（黑色框幾何中心）**的 (x, y, z)，單位公尺。
捲尺讀數 -> JSON 值替換 `vo/marker_positions.json` 的 placeholder。

marker 方向 ry/rx_deg：讓 marker 正面面向房間內部（如 0 號門牆 z=0
ry_deg=0，其正面法線朝 +Z）。貼牆中心高度 ~1.2m。

完成判據：JSON 內 6 個 marker 的 x/y/z 都是實量值（`_note` 的
「placeholders — REPLACE」已移除），`measurement_error_mm` 反映捲尺精度
（通常 3-8 mm）。

---

## G. 實測 marker 定位 → ATE 定案

先決：D（K 正確）、F（座標正確）、A（邊長正確）。

鏡頭不動單張偵測 → 絕對座標輸出：
  python vo/aruco_detect_test.py --url http://192.168.4.1:81/stream
    （以 # 鍵 / GUI 確認 ID + 距離貼標正常）

定量（以 clip 或單張圖為來源測定位誤差）：
  python vo/run_indoor_gps_validation.py
    → 完成後會比對 marker 估到 camera 絕對位置 與 marker_positions 真值。

輸出判定（對照 PROGRESS.md 歷史數值）：
  - sx/cy 若沿用舊 npz 則 sx=282 家族低估距離（fx 越高距離越近）……
    現用 v2 後直接以錄影 fx 為準。
  - 預期：近距（板滿畫面）marker 定位誤差 <100mm 甚至 <50mm（合成測試
    ~52mm）；遠距（2.5m）會隨 corner noise 放大（obs 資料：0.25px →
    ~312mm@1.2m / ~812mm@2.5m）。這是鏡頭解析度的物理上限，非軟體 bug。

完成判據：以 v2 內參的 marker 絕對定位誤差被記錄進 PROGRESS（取代
154/291/606 假說區間），若 <~100mm 則整套 Marker 室內定位驗收。

---

## 失敗時的常見處置表

| 現象                              | 處置 |
|-----------------------------------|------|
| calibrate gate REJECTED           | 重錄：補邊緣覆蓋/傾斜/近遠，見 D |
| calib_sanity HFOV<25° / dist>50   | fx 被畸變換走了（obs 0018/0019/0024），重錄近距填滿畫面 |
| fx 收斂 ~2000                    | corner 沒到邊緣，回 D 守則 1 |
| aruco 偵測率 <50%                | 光照 / 放大 marker / 對焦（ESP32-CAM 需鎖焦） |
| solvePnP z 不符 z-hint（>2x）     | fx 錯，K 不可信任，回 D |
| marker 定位 ATE 遠距爆高          | 屬解析度物理上限，護欄內距離（<1.2m）再取樣 |

---

## 壓縮版（貼在牆上）

D（標定錄影: 近距填滿畫面→5 區→±30-45°→近中遠）→ calib_sanity PASS
→ A 印量 marker → B ping AP → C 偵測率>80% → F 量座標進 JSON → G validation