# 專題進度總表(修正版)

## 研究定位

**題目:** 室內無人機自動導航系統之感知定位子系統——純視覺Bundle Adjustment軌跡估計與驗證

**路線說明:** 原規劃EKF+IMU融合+Loop Closure,實際執行後改走**純視覺增量PnP + Bundle Adjustment**路線。VINS路線經評估後不採用,列未來工作。

---

## 進度總表

| 模組 | 完成度 | 實際產出物 | 狀態說明 |
|---|---|---|---|
| **硬體韌體/傳輸** | 95% | `esp32_cam_server.ino`(GOOUUU ESP32-S3-CAM＋OV3660,WIFI_AP_STA雙模,內建STA連線邏輯)、`video_source.py` | 影像傳輸正常(AP模式 192.168.4.1 / STA 固定 IP 192.168.1.200);**IMU 路線已關閉不採用(MPU6050 撤除,見下方決策)** |
| **VO前端(增量PnP+Local Map)** | 100% | `vo_local_map.py`、`vo_core.py` | Bootstrap死鎖、id錯位、視差角過濾等bug已修完 |
| **~~EKF融合~~(已改路線)** | — | — | 原規劃項目,由BA取代;**因韌體從未實作IMU傳輸,EKF這條路線實際上從未具備執行條件** |
| **Bundle Adjustment全局優化** | 100% | `vo_bundle.py`、`run_offline_ba.py`、`run_ba_kfvo.py` | drift從~3577px降到~26px |
| **時間同步** | 100% | `drone_sync.py` | 偏移校正、n_cam修正、searchsorted查姿完成 |
| **7道自動化驗證閘門** | 100% | `validate_traj_pass.py`、`run_clean_seq_check.py` | 正負對照組驗證完畢 |
| **合成資料驗證** | 100% | `gen_synth_seq.py`、`synth_clean_01.avi`等 | 7/7閘門全過,ATE 2.4–2.8mm |
| **核心bug修正** | 100% | umeyama_sim3修正、class/script drift收束 | 19/19 regression全過 |
| **協議安全邊界(加碼)** | 100% | `adversarial_search.py`、`gate_redundancy.py`、`shape_metric_analysis.py`、`shape_gauge_probe.py`、`imu_gate_probe.py`、`VO_METHODOLOGY_ABSTRACTION.md` | 對抗搜尋找到 7 閘門全 PASS 但 ATE 20.06mm;形狀/干預統計 rho≤0.43 抓不到;誤差為非剛體形變;IMU 旋轉一致性閘門(yaw-drift)合成先驗 PASS→FAIL |
| **相機標定** | ⚠️ v2 進行中 | 舊 `calibration_esp32_qvga.npz`(fx=282,壞 imageSize 擬合,obs #0012)RMS 0.259px;重標定定案方案:螢幕棋盤法 | `gen_screen_board.py`(每格 45mm 預設,`--sq-mm` 可調)+ `calibrate_guided.py --samples 20`(AP 直連免路由器掉偵)+ `calib_sanity.py` 八閘門 → 產 `calibration_esp32_qvga_v2.npz` 並 `OK PASS` |
| **真機硬體連線** | 100% | — | 家用WiFi AP模式固定IP 192.168.1.200,stream/status/control 全通 |
| **真機乾淨序列實錄** | 100% | `seq_real_08~14.avi` + meta | **seq_real_10 達成核心4閘門全過(P1/P2/P6/P7);seq_real_14 達成棋盤全程入鏡(108/201 幀 GT)** |
| **真機ATE量測** | ⚠️ 量級結論兩層分流(§4.6) | `seq_real_14_ate.csv` | **層1:154mm 對 cy=30.6 異常強健**(留存資料换三組 K 重跑,cy=120/主點置中後 post-BA ATE 154.16–161.12mm,變異≤4.5%)。**層2:對 focal 假說高度敏感**——ATE=fx-282→154 / 474→291 / 900→566 / 948→606mm;儲存 fx=282 於壞 imageSize 擬合、未獨立證實,真實 QVGA 內參(OV3660:full-FOV 縮放~474 vs 視窗裁切~948)僅能由專用多姿態 QVGA 標定 shoot 決定;從 seq_real_14 重估內參失敗(姿態多樣性不足,focal 被換進畸變,k3≈1640),`recalibrate_from_frames.py` + 擴充 `calib_sanity.py`(focal 帶+dist 爆炸檢查)已拒收垃圾 K。公制尺度(mm/unit)同待定(870→745→2152 視 K)。誤差成因架構(GT 噪聲~50%+非剛體~30%)不受影响,見 FINAL_REPORT §4.5–4.6** |
| **~~Loop Closure~~** | — | — | 未執行 |
| **~~VINS~~** | — | — | 不採用,列未來工作 |
| **文件/日誌** | 100% | `VO_REAL_SEQ_VALIDATION.md`、`DRONE_SYNC.md`、`TRACK2_IMU_PLAN.md`(封存)、`VO_METHODOLOGY_ABSTRACTION.md`、觀察日誌0001–0010 | 協議安全邊界分析(§2-5)與真機 ATE 數據已全部寫入報告 |
| **推甄備審交付** | 90%(待 ATE 定值) | `推甄_無人機專題完整報告.md`、`推甄自傳_無人機專題段落.md`、`推甄報告\build_docx.py` 管線 | 22 頁/12 圖/119 檢查 PASS;首頁成果亮點卡、文獻比較表、複現附錄、參考文獻[1]–[6]、圖10 模擬 3D、圖2 標定實驗(見 09-26 段) |
| **git版本控制** | 已建立 | commit `d4e5e58`~`3f03f5e` | 完整程式碼與驗證腳本管理 |
| **最終報告撰寫** | 95%(ATE 成因分析已補入) | `FINAL_REPORT.md` | §4.5 補齊真機 ATE 實測數據與矛盾成因分析,§5 追蹤表已更新 |

---

## 報告論述重點(與修正配套)

原本的敘事「規劃EKF融合IMU → 實測發現BA效果更好 → 改走BA路線」暗示兩條路都有實際嘗試、是比較後選擇。但**IMU傳輸從未被實作**,沒有EKF對照實驗。正確敘事應為:

> 規劃階段設計了EKF+IMU方案 → 開發過程中優先聚焦純視覺前端(增量PnP+Local Map)與BA優化的驗證 → IMU整合因時間/硬體資源限制尚未實作 → 最終選擇純視覺路線並建立完整驗證機制。

這與「不做VINS」的理由(時間成本、成果完整性優先)論述一致,避免自相矛盾。

---

## 目前唯一的阻塞點

**真機手推 rig 對 P3(straight)/P4(monotonic)/P5(no-jumps) 的物理天花板。**
手推產生 stepwise(單幀跳 10–60px 後停)+ 來回微動,essential 弱視差下
scale 爆炸(已加 degenerate-rejection 15×median 守衛將 path len 11665→209
救回);但單向性/單調性/無跳變是運動本身的物理性質,演算法修不了。
P7(static tail)是錄製問題(HOLD1 未停穩),重錄可解。

**決策(2026-09-10):報告採「合成 17/17 為主 + 真機 P1/P2/P6 節點通過 +
P3-P5 標註硬體限制」。**

**09-10 追加實測(seq_real_10/11/12):P7 已靠「6s MOVE + 推到定位即全程定住」
修好(HOLD1 1.77px < 2),真機達成 P1/P2/P6/P7 四閘門全過(seq_real_10,
P2 2.69px/17kfs/146pts)。P3-P5 三序列呈三種互補失敗模式(見 VO_REAL_SEQ_
VALIDATION.md 4.4):seq_real_10「stepwise→尾段退化跳點」、seq_real_12「過度
守衛→尺度塌縮」、seq_real_11「視差不足→kfs 不足」——共同結論是手推本身
無法滿足 P3/P4/P5 運動前提,非演算法缺陷;P3-P5 至此在真機案列為閉案。

**後續(依定案順序)**:① 螢幕棋盤多姿態標定 **已完成 (2026-10-13)** → v2 `OK PASS`(fx=628.9/fy=619.1/cx=159.5/cy=119.5,RMS 0.625px,`calib_sanity` 全過)→ 報告真機 ATE 由「154→606mm 區間」**收斂至約 40mm(37–49mm;真值關鍵影格僅 5,樣本受限)**;報告全鏈已重跑 `RESULT: PASS`(26 頁/12 圖/122 檢查)。② 印 ArUco 15–20cm 標記實量邊長,實測室內 GPS 收斂第四章硬體缺口(to-do)。**IMU(MPU6050)已決定不採用,軌道二關閉**。

**09-11 加碼完成(純軟件,報告已同步)**:協議安全邊界的完整刻畫——
(1) 對抗搜尋證明存在 7 閘門全 PASS 但 ATE 20.06mm 的合成序列;
(2) 閘門冗餘分析 rho(P2,P3)=0.79、rho(P3,P4)=0.78;
(3) 反結果:軌跡內生統計(形狀/干預)與 ATE 相關 ≤0.43,誤差為
**非剛體形變**(Umeyama Sim3 對齊後仍殘留);
(4) IMU 旋轉一致性閘門合成首驗`imu_gate_probe.py`:yaw-drift 序列
7 閘門 PASS 但 IMU gate FAIL(23.33°>5° at drift 0.30),證明外部參考
正交性(obs #0021 後 gyro 只在 VO keyframe bracket 積分,0.15 慢速旋轉
2.59° 合法 PASS;0.30 才暴露 VO 追蹤崩壞)。
所有發現 codified 進 regression(20/20 全過)。

**09-13 加碼完成(純軟件,室內 GPS 標記定位,報告已同步)**:以 ESP32-CAM
+AruCo 4x4_50 標記建立室內絕對定位(與既有 VO 軌跡的 Sim3 尺度基準整合)。
全部步驟 1–7 於合成/離線完成並 5/5 驗證通過,等待實體硬體驗證:
(1) `gen_markers.py`/`aruco_detect_test.py`/`aruco_marker_sweep.py`:標記生成、
實測偵測、偵測極限掃描——10cm 標記 >0.4m 不可靠,建議印 15–20cm;
(2) `marker_positions.py` + `marker_positions.json`:牆/天花板/地板朝向(roll/pitch/
yaw per-marker deg)正確載入與索引(6 標記示範);
(3) `marker_loc.py`(步驟 4–5 核心):`estimate_marker_poses` 以 cv2 5.0
`solvePnPGeneric`(ITERATIVE + IPPE_SQUARE)雙候選取最小重投影誤差,並回傳
`rms_px`/`gap_px`/`conditioned`(obs #0015:近正面四邊形 P4P 雙根退化,間距
<0.3px 視為不可信);`camera_abs_position` = R_m2w@(-R_m2c^T·tvec)+p_m;
自測三層(直接 0.000mm/斜角渲染 102.77mm/正面雜訊掃描);
(4) `align_sim3_demo.py`(步驟 6):沿用 `run_gt_ate.umeyama_sim3` 對齊,
合成 5 控制點全軌跡漂移 0.000mm——證實標記絕對基準可作 VO 尺度真相;
(5) `localise_video.py`(步驟 7 端):錄影/ESP32 串流→detect→pose→多標記
中位數融合→CSV(frame,x,y,z,n_obs,n_ambiguous,spread,conditioned,ids),
合成 e2e 6/6 融合(5/6 雙標記)均誤 52mm;esp32 低對比需 `equalizeHist`;
(6) `run_indoor_gps_validation.py`(步驟 7 收斂):單一入口跑全部 5 個階段自測
+ 15cm 標記 pose 誤差包絡表(深度×角點雜訊 σ)——σ=0.5px 時 0.4m 20mm,
0.6m 85mm,1.0m 225mm;σ=0.1px(subpix 理想)0.6m 14mm。行動建議:印 ≥15cm、
0.5–1m 內操作、多標記平均、yaw >8°;
(7) 已併入 regression(`test_regression.py` 新增 `TestIndoorGps` 5 項:
偵測探針/pose 自測/sim3 恒等/管線自測/calib-sanity 正對照),**全套
25/25 全過(25 tests,466s)**——之後改共用座標數學不再需要單獨手跑。
09-13 追補:`align_sim3_demo.py` 自測從恒等 sim3/共用面點集升級為
非平凡 sim3(scale 0.8、斜軸旋轉 37°、平移)＋三維分部點集,真正考驗
縮放/旋轉恢復(obs #0021b;原恒等自測對縮放/旋轉恢復毫無壓力);
`TestImuGateEndToEnd` 的 yaw-drift 參數 0.15→0.30(ob #0021 修正公平
bracket 後,0.15 差距 2.59° 合法 PASS,0.30 才觸發 VO 追蹤崩壞 FAIL)。
(8) **09-13 補查(重要)**:嘗試直接從 seq_real_14 的 109 幀棋盤視圖重估
    QVGA v2 內參失敗——主點置中後 fx 收斂到 899、dist k3=-1640,低 RMS
    卻不合理(focal 被換進畸變);**對照 VGA 標定(calibration_esp32.npz,
    fx=948)與 firmware(FRAMESIZE_QVGA)衍生兩個物理假說**:
    full-FOV 縮放(fx≈474)→ATE 291mm vs 視窗裁切(fx≈948)→ATE 606mm;
    而舊 fx=282(壞 imageSize 擬合)下 ATE=154mm。**結論:154mm 對 cy 穩健,
    但對 focal 假說敏感到 154→606mm**,精確 ATE 只能由專用多姿態 QVGA
    標定錄影定案;`recalibrate_from_frames.py` 已加 calib_sanity 守衛
    (審核 focal 帶+dist 爆炸),SEO 此類「低 RMS 卻垃圾 K」的陷阱(見
    FINAL_REPORT §4.6)。
(9) **09-13 晚**:試圖用棋盤像素跨度定案 fx 失敗——發現 **fx–z 退化**
    (solvePnP 的 z 與 fx 反向縮放:fx=282→z≈800mm vs fx=900→z≈2431mm,
    預測跨度對 fx 幾乎不變+被透視縮短污染),像素跨度無法排除任何 focal 假說,
    必須靠**獨立距離參考**。`calib_sanity.py` 新增 **FOV 快速篩子**
    (282→59°=ESP32-CAM 典型 vs 900→20° 不合理)與 **`--clip --z-hint`
    交叉驗證**(獨立距離檢驗 solvePnP 中位數 z)。物理傾向(59°+~1m rig+800mm)
    支持 fx≈282 家族,但僅條件式——最終仍待多姿態標定錄影 + 錄後雙重把關
    (見 FINAL_REPORT §7.5-3)。
(10) **09-13(合成封閉測試,obs #0024)**:建立 `gen_synth_calib_shoot.py`
     ——用**已知 K** 渲染 5x4/25mm 棋盤、含畸形 k1=-0.18 的姿態多樣錄影,
     跑 `recalibrate_from_frames.py` 封閉驗證。**關鍵發現:姿態多樣性閘門
     （5 zones+tilt+spread）全過仍讓 fx 逃逸到 2077/904、dist 補償到
     169/2461——因為 5 個 zone 全在畫面中央 ~150px 盤內,corner 從未
     靠近圖像邊緣(r_max≈150px < 影像半對角線 200px),fx–畸變在內部
     區域完全可交換(病根正是 #0018/#0019);無畸變同姿態即完美恢復
     (fx 475.4)。**修法:近距拍攝讓最外圍 corner 接近畫面邊緣**——
     近距 220-300mm + 近/中/遠後,所有 flags(free5/k1-only/fix-pp)都
     恢復 fx≈477(誤差<1%)。已將此封閉測試收進 regression(26/26)與
     `gen_synth_calib_shoot.py --selftest`。**錄影 SOP 守則:棋盤靠近鏡頭
     直到外框幾乎填滿畫面→近/中/遠→±30-45° 傾斜;`calibrate_guided.py`
     的即時 HUD 應補「邊緣覆蓋」限制(zone 覆蓋≠徑向覆蓋)**。
剩餘硬體步驟:印標記並實量邊長(--marker-m)、PC 連 `RatMonitor_Setup` AP、
實測 `aruco_detect_test.py --snapshot 60`、**多姿態 QVGA 棋盤標定錄影**得
`calibration_esp32_qvga_v2.npz`(現 npz 之 cy=30.6 為寬高顛倒殘骸 + fx=282
未獲獨立證實,obs #0012;產生器已修,需重標定才有正確內參)。
**執行順序請照 `HARDWARE_PHASE_RUNBOOK.md`**(D 標定錄影最優先,守則:
棋盤填滿畫面→5 區→±30-45°→近中遠;obs #0024 邊緣覆蓋缺失會讓 fx 逃逸)。

(11) **09-18(軟體收尾至定稿,交付物重 build v1.2)**:完成主專題軟體側最後收尾——
     ① `report_content.py` 升 **v1.2**:回歸測試數字統一為 **26/26**(原正文 20/20、
     疊代版 25/25 兩處殘留,與實跑 `test_regression.py` 26 tests 一致,同步更新
     `verify_docx.py` 的 4 處斷言);② 摘要與 5.2 的真機 ATE **明確標註「以儲存
     fx=282 為前提,跨 focal 假說為 154→606mm 區間」**,硬體 D 步定案前不得當
     定值引用;③ 4.4.1 表 4-2 敏感度表**補齊 focal 假說欄**(fx=282→154.19 /
     fx=474→290.81 / fx=900→565.82 / fx=948→605.80 mm)並以文字敘述「fx–z
     退化 + FOV/z-hint 交叉驗證」,口試稿同步 25/25→26/26。**重新產出四件套
     (md/docx/pdf/pptx)並全數通過 verify**:docx 84/84、pdf 34 頁 A4 PASS、
     pptx 18 頁無重疊(focal 假說新斷言皆 PASS)。
     ④ **硬體可印資產補齊**:`vo/gen_print_board.py` 產 `markers/chessboard_print_A4.png`
     (300dpi A4、5x4 棋盤、**25mm 方格 + 內建 100mm 比例尺**,cv2 偵測 20/20 角
     點全過);`vo/gen_marker_sheet.py` 產 6 張單張 **15cm A4 marker**(id 0–5 各自
     偵測正確)+ `marker_sheet_6up_A4.png` 速掃版(單頁 6 個 id 全中)。
     **剩餘硬體步驟僅剩**:**印資產**→實量邊長/比例尺(--marker-m)→DPC 連
     `RatMonitor_Setup` AP→**D 標定錄影**(`calibration_esp32_qvga_v2.npz`)→
     E sanity→F 量座標入 `marker_positions.json`→G validation,全程照 RUNBOOK。
     regression 09-18 實跑 **26/26 PASS**(288.6s)。

(12) **09-23(軟體補完 obs #0024 的 HUD「邊緣覆蓋」限制)**:`calibrate_guided.py`
     升級為 **REQ 面板門控**——右側面板逐項列出必須完成條件(`edge-fill`(外角距
     邊緣 <24px)、`tilt >=2`(≈30° 斜)、`sample n/30`、`NEAR/MID/FAR`、
     `GRID 3x3`),全綠才自動存檔、跑 8 條閘門(rms<2.0、fx∈[200,1200]、
     HFOV∈[25,75]、z-hint 交叉驗證)並輸出 **`OK PASS`/`FAIL`**;fx/HFOV 閘門
     剛好拒收 >900 的壞 focal 族(與 FOV 篩子一致),`--out` 預設即
     `calibration_esp32_qvga_v2.npz`。純函數門控(depth_label/corner_margin/
     missing_list)以 **3 項新測試**收進 `test_regression.py`,**實跑
     29/29 全過**(125.9s);報告 v1.2 之 26/26 保留為 09-18 快照,`HARDWARE_
     PHASE_RUNBOOK.md` 完成條件同步改為「REQ 全綠 + OK PASS」。

(13) **09-26(推甄備審交付 + 硬體敘事定案 + 標定方案)。**
     ① **推甄交付完成**:`推甄_無人機專題完整報告.md` 發展出可自動驗證管線
     (`推甄報告\gen_charts.py`→`layout_preflight.py`→`build_docx.py`→
     `export_pdf.py`→`verify_pdf.py`),全鏈 **22 頁/12 圖/119 檢查 PASS、
     0 FAIL/0 WARN**。新增:首頁「成果亮點(30 秒導覽)」卡+一句話定位+分頁;
     四章文獻比較表(本系統合成 2.6mm/真機 154–606 / ORB-SLAM3 約30 /
     ORB-SLAM2 約80 / VINS-Mono 約90 / OpenVINS 約50,含跨資料集免責段;
     ORB-SLAM3 0.033m、VINS-Mono 89–144mm、OpenVINS ~50mm 均經網路查證);
     附錄:複現指令三組 fenced 命令塊;參考文獻 [1]–[6] 與正文內文引用;
     4.2 末對抗搜尋預告、二章達標/未達標宣告、4.4 精髓檢討(experiment time,
     特定假說→檢定→修正/保留);**圖10 模擬圖改 3D**(Axes3D,elev 26°/azim
     −132°,標記 z=0.25/3.25/6.25 與巡航線 1.4/4.4/7.4 讀 marker_map.yaml),
     **圖2 標定實驗照**(calib HUD 與棋盤偵測照)、圖3×2 ATE 數據圖;頁碼/頁眉
     (PAGE 欄位,驗 1/2/11/22 正確),`build_docx` 支援 `<!-- pagebreak -->`
     與圍欄程式碼渲染。
     ② **硬體敘事定案**:板子定為 **GOOUUU ESP32-S3-CAM(OV3660)**(原
     `ESP32-S3-EYE` 只是 firmware camera-model 巨集),全部文件已更名一致;
     **MPU6050 撤除**、IMU 閘門維持合成先驗、未來工作刪 IMU 條、4.3 註明
     實體 IMU 不納入範圍;P3–P5 維持「手推 rig 物理天花板」閉案敘述。
     ③ **標定方案定案(替代印表機棋盤)**:`gen_screen_board.py` 讀螢幕真實
     pixel pitch 產生全螢幕棋盤,預設每格 45mm(原 30mm 板太小,NEAR/edge-fill
     要貼到失焦;`--sq-mm` 可調),`show_board_fullscreen.py` 全螢幕顯示;
     `calibrate_guided --samples 20`(**AP 直連 http://192.168.4.1:81/stream
     免路由器→不掉偵**);標定前先跑 `chessboard_precheck.py`(90 秒省一輪
     白錄);`verify_pdf.py` 頁數下限 4→18。
     ④ obs #0068/#0069(資料誠實圖＋圖例取代內聯標註;3D preflight 陷阱＋
     摘要卡/比較表/複現附錄三件套)已寫入 task-observer 觀察日誌。
      **剩餘硬體步驟僅剩**:**螢幕棋盤多姿態標定**(`calibration_esp32_qvga_v2
      .npz` + OK PASS,守則:外角到畫面邊緣→5 區→±30–45°→近中遠)→E sanity
      →報告 ATE 定值→印 ArUco 15–20cm→實量邊長→室內 GPS 實測。
      ⑤ **v2 重校正嘗試(2026-10-11)**:直接從既有 `seq_real_14.avi` 抽幀
      重校正 → **覆蓋度不足,失敗**:偵測到棋盤 112/201 幀但有效樣本僅
      **10/30**、傾斜樣本 **0/2**,`REQ PANEL NOT SATISFIED`,未產生
      candidate npz。→ 決議**不覆蓋**預設內參,維持 ATE 區間 154–606 mm
      誠實呈現,並把「既有序列不足以重標定、須重錄」寫入報告第七節未來工作。
      ⑥ **報告定稿(推甄備審,2026-10-11)**:第七節未來工作改寫為完整條列
      (標定定值/ArUco 實體驗證/marker_positions.json 佔位說明/3D demo 示意/
      動力滑台/封面資訊/驗證圖可讀性),`charts/seq_real_14_validation.png`
      已置入 charts;**全鏈重跑 PASS:23 頁/12 圖/119 檢查/0 FAIL 0 WARN**,
      已複製至 `推甄提交\` 與桌面。
      ⑦ **封面頁(2026-10-13)**:`build_docx.py` 新增封面區塊(`# 標題` 後
      插入姓名/學號/指導教授/系所/日期 五行),資料讀 `推甄報告\cover_info.txt`
      (留空顯示【請填寫】,樣板已建立);`# 標題` 後加 `doc.add_page_break()`。
       **全鏈重跑 PASS:27 頁/12 圖/122 檢查/0 FAIL 0 WARN**,已複製至
       `推甄提交\` 與桌面。
      ⑧ **真機 ATE 誠實重測 (2026-10-13)**:撤除「約 40mm(樣本受限)」,改以
      **0.15–0.5m** 呈現。`run_gt_ate.py` 修 `gap` bug 並加 `--interp/--max-gap`;
      量化門檻 12/8/3 與 GT 覆蓋對照(見上),根因=棋盤距鏡頭 ~1.9m 反 SOP。
      改動:主稿 5/14/63/109/122/128/138/211/222-223、`gen_charts.py` fig_ate/fig0、
      `build_docx.py` 圖5 圖說、`verify_pdf.py` REQUIRED_TEXT(樣本受限→0.15/0.5 公尺/
      145 毫米/1.9 公尺)。**全鏈重跑 PASS:28 頁/12 圖/125 檢查/0 FAIL 0 WARN**,
      已複製至 `推甄提交\` 與桌面。

---

## 接下來的建議順序

1. ~~真機標定 v2~~ **已完成 (2026-10-13)**:螢幕棋盤多姿態標定(gen_screen_board→show_board_fullscreen→calibrate_guided→`OK PASS`,fx=628.9/fy=619.1/cx=159.5/cy=119.5,RMS 0.625px,`calib_sanity` 全過)→ 報告真機 ATE **已改以誠實值 0.15–0.5 m 呈現**(見 ⑧),`verify_pdf` 已回寫並 PASS
   - 實測:以 v2 內參重測,真機 ATE 對關鍵影格門檻與棋盤真值覆蓋高度敏感——門檻 12→9kf/39mm(僅 5 真值 kf)、門檻 3→18kf/145mm(全部真值幀內插 248mm)、門檻 8→25kf/503mm;根因是本序列棋盤距鏡頭約 1.9m(超過 SOP 建議 0.4–1.2m),真值雜訊大且棋盤可見段與關鍵影格不對齊。判定真機 ATE 誠實值為 **0.15–0.5m**(與舊 fx=282 的 154mm 同數量級),須依 SOP 重錄方能定案
2. **室內 GPS 硬體閉環**:印 ArUco 15–20cm 標記→實量 `--marker-m`→`marker_positions.json`(目前為佔位值)→`localise_video.py` 實測補 4.4 硬體缺口
3. **推甄備審交付**:已完成 **28 頁/12 圖/125 檢查 PASS**(含封面頁 `cover_info.txt` 待填),已置 `推甄提交\` 與桌面;若系所有頁數上限再評估精簡版
4. **回環偵測 + 位姿圖最佳化 (2026-10-13,軟體)**:新增 `vo/vo_loop_closure.py`(ORB 描述子 + 比例測試 + essential 幾何驗證的地點辨識;SE(3) 位姿圖 LM,數值 Jacobian,沿用 vo_bundle 風格)與 `vo/test_loop_closure.py`(4 測試全過:位姿圖閉環把合成漂移 ATE 由 1.30→0.14、真機幀重訪 52 匹配/51 內點、異場景 0 匹配、detect_loops 正確連 0↔2 且不誤連)。**限制**:週期性紋理(棋盤↔房間)會產生假陽性內點(已記錄);端到端驗證需一段「有迴環且具可追蹤紋理」的序列,現有 glow 合成場景無 ORB 特徵、真機序列無迴環,故此項為基礎建設、部分仍屬未來工作。
5. **第一人稱相對導航原型 (2026-10-16,軟體)**:新增 `vo/drone_indoor_navigator.py`(載具座標系示教/導航:SPACE 記錄航點、N 切 TEACH/NAV、`R_w2c` 把目標向量投影到相機當前視角、360° 指南針 + 平移/直行指令、20cm 抵達自動前進),依 `marker_loc`/`marker_positions`/`video_source`;補 **可信度閘門**(近正面雙根之 `conditioned=False` 預設剔除,`--allow-ambiguous` 可覆寫)與 `--video` 離線來源。**驗證**:`--selftest` 純幾何自測 PASS(還原相機世界座標誤差 <1e-9、右偏目標航向為正,與 `marker_loc.camera_abs_position` 交叉一致),已印製 ArUco ID 0–5 偵測全中;真機串流端到端待硬體。`localise_video.py` 之 `--calib` 改為 required(經 `calib_sanity` 把關)+ 每幀印相機 3D 位置;`markers/test_marker_detect.py` 加 mission 面板(ID 0–5 完成度)+ ESP32 來源 + 每標記距離。**已寫入報告 §8**(第一人稱相對導航原型,標為已實作待真機);報告全鏈重跑 **PASS(28 頁/12 圖/125 檢查)**並複製交付。commit `4ca8905`。

---

## 一句話總結現況

**合成驗證端已完工到論文等級嚴謹度(7/7 閘門、ATE 2.4–2.8 mm,合成 GT 完美無雜訊);真機端核心閘門 P1/P2/P6/P7 全過、P3-P5 為手推 rig 物理天花板(閉案);真機內參已以專用多姿態 QVGA 標定定案(fx=628.9,`calib_sanity` 全過),真機 ATE 以 v2 內參誠實重測為 **0.15–0.5m**(對關鍵影格門檻與棋盤真值覆蓋高度敏感;根因:本序列棋盤距鏡頭 ~1.9m 反 SOP,真值段與關鍵影格不對齊);推甄備審交付已完成並全鏈 PASS(28 頁/12 圖/125 檢查,含封面頁/文獻比較表/複現附錄/模擬 3D 圖/成果亮點卡);IMU(MPU6050)已撤除關閉。後續以依 SOP 重錄一段棋盤全程可見序列把 ATE 收斂為穩固單值,並推進室內 GPS 硬體閉環,最終以「局部達標 + 硬體限制標註 + ATE 成因誠實說明 + 室內 GPS 已就緒待硬體」收尾。**