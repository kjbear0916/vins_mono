# 專題進度總表(修正版)

## 研究定位

**題目:** 室內無人機自動導航系統之感知定位子系統——純視覺Bundle Adjustment軌跡估計與驗證

**路線說明:** 原規劃EKF+IMU融合+Loop Closure,實際執行後改走**純視覺增量PnP + Bundle Adjustment**路線。VINS路線經評估後不採用,列未來工作。

---

## 進度總表

| 模組 | 完成度 | 實際產出物 | 狀態說明 |
|---|---|---|---|
| **硬體韌體/傳輸** | 95%(+軌道二雛形) | `esp32_cam_server.ino`(WIFI_AP_STA雙模,內建STA連線邏輯)、`video_source.py`、`firmware/src/imu_driver.*`(IMU雛形) | 影像傳輸正常;IMU 未實體接入,但雛形已寫好(`IMU_ENABLED=0` 預設關閉,MPU6050/SDA14/SCL38/Core0/UDP3333) |
| **VO前端(增量PnP+Local Map)** | 100% | `vo_local_map.py`、`vo_core.py` | Bootstrap死鎖、id錯位、視差角過濾等bug已修完 |
| **~~EKF融合~~(已改路線)** | — | — | 原規劃項目,由BA取代;**因韌體從未實作IMU傳輸,EKF這條路線實際上從未具備執行條件** |
| **Bundle Adjustment全局優化** | 100% | `vo_bundle.py`、`run_offline_ba.py`、`run_ba_kfvo.py` | drift從~3577px降到~26px |
| **時間同步** | 100% | `drone_sync.py` | 偏移校正、n_cam修正、searchsorted查姿完成 |
| **7道自動化驗證閘門** | 100% | `validate_traj_pass.py`、`run_clean_seq_check.py` | 正負對照組驗證完畢 |
| **合成資料驗證** | 100% | `gen_synth_seq.py`、`synth_clean_01.avi`等 | 7/7閘門全過,ATE 2.4–2.8mm |
| **核心bug修正** | 100% | umeyama_sim3修正、class/script drift收束 | 19/19 regression全過 |
| **協議安全邊界(加碼)** | 100% | `adversarial_search.py`、`gate_redundancy.py`、`shape_metric_analysis.py`、`shape_gauge_probe.py`、`imu_gate_probe.py`、`VO_METHODOLOGY_ABSTRACTION.md` | 對抗搜尋找到 7 閘門全 PASS 但 ATE 20.06mm;形狀/干預統計 rho≤0.43 抓不到;誤差為非剛體形變;IMU 旋轉一致性閘門(yaw-drift)合成先驗 PASS→FAIL |
| **相機標定** | 100% | `calibration_esp32_qvga.npz`(另有`esp32.npz`) | RMS 0.259px |
| **真機硬體連線** | 100% | — | 家用WiFi AP模式固定IP 192.168.1.200,stream/status/control 全通 |
| **真機乾淨序列實錄** | 100% | `seq_real_08~14.avi` + meta | **seq_real_10 達成核心4閘門全過(P1/P2/P6/P7);seq_real_14 達成棋盤全程入鏡(108/201 幀 GT)** |
| **真機ATE量測** | ⚠️ 量級結論兩層分流(§4.6) | `seq_real_14_ate.csv` | **層1:154mm 對 cy=30.6 異常強健**(留存資料换三組 K 重跑,cy=120/主點置中後 post-BA ATE 154.16–161.12mm,變異≤4.5%)。**層2:對 focal 假說高度敏感**——ATE=fx-282→154 / 474→291 / 900→566 / 948→606mm;儲存 fx=282 於壞 imageSize 擬合、未獨立證實,真實 QVGA 內參(OV3660:full-FOV 縮放~474 vs 視窗裁切~948)僅能由專用多姿態 QVGA 標定 shoot 決定;從 seq_real_14 重估內參失敗(姿態多樣性不足,focal 被換進畸變,k3≈1640),`recalibrate_from_frames.py` + 擴充 `calib_sanity.py`(focal 帶+dist 爆炸檢查)已拒收垃圾 K。公制尺度(mm/unit)同待定(870→745→2152 視 K)。誤差成因架構(GT 噪聲~50%+非剛體~30%)不受影响,見 FINAL_REPORT §4.5–4.6** |
| **~~Loop Closure~~** | — | — | 未執行 |
| **~~VINS~~** | — | — | 不採用,列未來工作 |
| **文件/日誌** | 100% | `VO_REAL_SEQ_VALIDATION.md`、`DRONE_SYNC.md`、`TRACK2_IMU_PLAN.md`、`VO_METHODOLOGY_ABSTRACTION.md`、觀察日誌0001–0010 | 協議安全邊界分析(§2-5)與真機 ATE 數據已全部寫入報告 |
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

**後續(依兩軌道計畫)**:**軌道一**= 真機棋盤 ATE(待 rig 可裝棋盤)→ 收尾文件;
**軌道二(選擇性)**= IMU(MPU6050+ESP32)補回,時間資源允許才做。

**09-11 加碼完成(純軟件,報告已同步)**:協議安全邊界的完整刻畫——
(1) 對抗搜尋證明存在 7 閘門全 PASS 但 ATE 20.06mm 的合成序列;
(2) 閘門冗餘分析 rho(P2,P3)=0.79、rho(P3,P4)=0.78;
(3) 反結果:軌跡內生統計(形狀/干預)與 ATE 相關 ≤0.43,誤差為
**非剛體形變**(Umeyama Sim3 對齊後仍殘留);
(4) IMU 旋轉一致性閘門合成首驗`imu_gate_probe.py`:yaw-drift 序列
7 閘門 PASS 但 IMU gate FAIL(12.45°>5°),證明外部參考正交性。
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
剩餘硬體步驟:印標記並實量邊長(--marker-m)、PC 連 `RatMonitor_Setup` AP、
實測 `aruco_detect_test.py --snapshot 60`、**多姿態 QVGA 棋盤標定錄影**得
`calibration_esp32_qvga_v2.npz`(現 npz 之 cy=30.6 為寬高顛倒殘骸 + fx=282
未獲獨立證實,obs #0012;產生器已修,需重標定才有正確內參)。

---

## 接下來的建議順序

1. **軌道一**:真機棋盤 ATE(rig 上裝 5x4/25mm 棋盤全程入鏡,跑 `run_gt_ate.py`)→ 收尾文件
2. **軌道二(選擇性)**:IMU(MPU6050+ESP32)補回,時間資源允許才做
3. **撰寫最終報告**:核心敘事是「原規劃EKF+LoopClosure → 實際走純視覺BA路線 → 建立嚴謹驗證機制(7閘門) → 合成 17/17 全過 + ATE 2.4–2.8mm → 真機節點驗證(P1/P2/P6 全過 + P7 修正後全過)+ P3-P5 標註手推rig硬體限制」,VINS放在未來工作討論

---

## 一句話總結現況

**合成驗證端已完工到論文等級嚴謹度(17/17 閘門、ATE 2.4–2.8 mm,合成 GT 完美無雜訊);真機端跨過 WiFi 關卡後錄出可用的乾淨序列:核心閘門 P1/P2/P6/P7 全部通過,剩餘 P3-P5 是手推 rig 的物理天花板(三序列三種失敗模式量化佐證);真機 ATE 首次有效量測 154mm(以儲存 fx=282 為前提;cy=30.6 異常已證實影響 <4.5%,但 focal 假說未定,154→606mm 跨假說,精確數值須待專用 QVGA 標定 v2,見 §4.6);成因已分析(GT 偵測雜訊主導,非 VO 演算法缺陷);室內 GPS(ArUco 標記絕對定位)步驟 1–7 純軟件全部 5/5 自測通過(e2e 合成均誤 52mm,pose 包絡表定量刻畫深度×雜訊),剩餘硬體驗證待印 15–20cm 標記+多姿態重標定——最終以「局部達標 + 硬體限制標註 + ATE 成因誠實說明 + 室內 GPS 已就緒待硬體」收尾。**