# Hardware Phase Runbook — Marker 室內定位 + QVGA 標定

本文件是「軟體已完成、硬體未開始」的執行順序。每一步都標出命令、期望輸出、
失敗時的處置。所有 clip 檔存到 `D:\Things\vo\` 下（與其他 t 一致）。

前置檢查（PC 端離線，無需硬體）：
  python -m unittest vo.test_regression        # 30/30 應全過
    → 09-18 為 26/26（含 1 項合成標定封閉測試，證明校正管線
      能從已知 K 恢復 fx 後才值得錄影）；09-23 新增 3 項
      calibrate_guided REQ 門控純函數測試 → 29/29；09-28 修正
      NEAR 桶量綱（改量棋盤外框）並新增該情境測試 → 30/30（267.974s）。

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
`tilt >=15deg (n)`、`sample n/30`、`NEAR/MID/FAR`、`GRID 3x3`；**全綠才會自動存檔
並列印 gate 明細 + `OK PASS`**。按 q 提前離開會在終端印出 MISSING 清單
（如缺 `edge-fill(near)`=棋盤沒近到貼邊，回去補拍）。

**上機前先跑本機合成 dry run**（不需要相機、不經網路，直接在行程內
渲染同一組姿勢；2026-09-28 起取代原本的 MJPEG 路徑）：
  python vo/dryrun_guided_d.py
    → 期望 `MISSING: none` + `DRY RUN PASS`。
    → 最近一次實測：47 姿勢涵蓋 NEAR/MID/FAR、9/9 格、tilt 23；
      recovered fx=471.5（真值 474，誤差 0.5%）、RMS 0.320，
      `calib_sanity` 判 PASS。
  這條路徑**不驗證串流傳輸層**。串流傳輸層另由離線回放證實
  （`python vo/mjpeg_replay_test.py`）：把 synth server 串流量錄成位元流，
  再用 `video_source.mjpeg_frames` 原樣回放 → 275 frames 全解析、30/30
  樣本全綠、decode+detect 91 fps 離線 PASS。
  曾把「MJPEG 讀取只有 2 fps」歸咎於 TCP Nagle/延遲 ACK，但 root cause 是
  **parser 的 `\r\n\r\n` 終止符搜尋從 regex 結尾起找，漏掉真正的分隔符，
  落在 JPEG 體內隨機位置的假分隔符上，導致整串 frame 對位錯開、imdecode
  大部分失敗**；已在 `mjpeg_frames` 修復（regex 吞掉完整 `\r\n\r\n`，
byte-exact 18/18 對上 server 端編碼輸出）。上機後 HUD 若長時間不前進，
   才考慮 ESP32 端 Wi-Fi 實際吞吐。
   偵測/分類鏈對場地式劣化的安全邊界由 `python vo/adversarial_stress.py
   --sweep` 量化（同 47 姿勢、SB-only + Laplacian 閘，與 live 收樣路徑一致）：
   - **光梯度／半邊陰影不是威脅**：×3.0 劣化（亮度落差 ±0.95、陰影砍到只剩
     10% 殘光）仍 SB 46/47、零 reject、panel ~step 31 收齊，fx 誤差 ≤4%。
   - **橫向動態模糊是唯一危險軸**：≥9px（box blur）SB 仍過、REQ panel 仍是
     全綠、`rms 0.37` 也過 final gates、連 Laplacian `--blur-min 30` 都判
     sharp——但角點被抹成橫向條紋，解得 fx 617–652（真值 474，+30~37%）。
     **這是「靜默錯誤標定」**：所有閘全綠卻拿到錯的 intrinsic。Laplacian
     variance 在 JPEG 解壓後的 QVGA 上恆在 350–700（blur 到 13px 也降不下來），
     所以這個預設 30 的閘在現實模糊下形同虛設。
   - 操作對策：姿勢之間**不要甩動**、保持手穩；錄完若 solved fx 偏離
     FX_GUESS=474 超過 10%（出現 ~550+ 或 ~400-）就作廢重錄——現有 final
     gates 抓不到這個偏離，只能靠 fx 與已知先驗對賬。不要把 blur 閘當保護。

即時引導錄影：
  python vo/calibrate_guided.py --url http://192.168.4.1:81/stream ^
      --pattern 5x4 --square 25 --samples 30 ^
      --out D:\Things\vo\calibration_esp32_qvga_v2.npz
    → HUD 上 3x3 dots 全綠 + z bins 全綠 + SAMPLE 到 30 即自動存。

  NEAR 的定義是**棋盤外框**占畫面 >=70%（任一軸，逐軸除以該軸畫面尺寸；
  內角跨距會先乘 (C+1)/(C-1)、(R+1)/(R-1) 換算成外框）。QVGA 320x240 上
  6x5 棋盤外框寬需 ≈224px 才會亮，約等於相機距 16mm 方格板 163mm。
  收錄視窗 `--ppm-min/--ppm-max`（預設 8/60 px per square）必須放得下
  NEAR 所需的 ≈37 px/square，否則近距離姿勢會在進場前就被丟棄。
  HUD 頂端 `det=sb|sb-clahe|sb-adaptive` 顯示實際生效的偵測通道。
  **只有 SB（`findChessboardCornersSB`）的角點會被採用**；
  classic 通道只留作診斷，畫面上會顯示但不記錄樣本。合成比對證據：
  classic RMS≈4.95 / fx 115~163（真值 474），SB RMS≈0.32 / fx 466~474。
  若 HUD 長期停在 classic，代表該幀被丟棄，姿勢永遠收不滿。
  長期顯示 clahe/adaptive 表示螢幕反光或摩爾吃掉對比（改用列印紙）。

**tilt 指標是「板面離開正面平行多少度」，不是長度比**（2026-09-28 修正）：
  舊指標是首尾兩排的長度比，需 70~80° 傾角才到 0.12，手持根本做不到，
  等於 REQ 面板永遠點不亮。現在由 object-grid 單應矩陣分解求板面法線
  與光軸夾角，HUD 顯示 `tilt=Ndeg`，門檻 `--tilt-min 15`（度）。
  傾 20°~36°（pitch）即可輕鬆滿足；`tilt 2/2` 綠燈即為此值。

角點編號已正規化（`canonical_corners`）：把 20 點量化到 5x4 晶格並
  驗證每格恰好一點，軸向固定為 +x/+y。SB 在不同姿勢下會把同一組點
  編成正序或逆序，錯配時 planar solve 會崩到 RMS 3.3 / fx 77，
  連帶 ang / tilt / cell 全部失真。量化不成立時該幀直接拒絕（`bad-lattice`），
  不會被記成錯誤樣本。

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