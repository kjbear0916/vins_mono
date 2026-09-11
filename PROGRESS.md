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
| **真機乾淨序列實錄** | 70% | `seq_real_08~12.avi` + meta | **seq_real_10:P1/P2(2.69px)/P6(17kfs/146pts)/P7(0.04/1.77) 全過**——真機核心4閘門首次全綠;P3-P5 為手推rig物理天花板(量化:三序列三種失敗模式,見4.4) |
| **真機ATE量測** | 0%(合成2.4–2.8mm) | seq_real_13 實測 0/198 幀 GT | 待重錄(棋盤擺位修正 + ESP32 換 WiFi) |
| **~~Loop Closure~~** | — | — | 未執行 |
| **~~VINS~~** | — | — | 不採用,列未來工作 |
| **文件/日誌** | 90% | `VO_REAL_SEQ_VALIDATION.md`、`DRONE_SYNC.md`、`TRACK2_IMU_PLAN.md`、觀察日誌0001–0008 | |
| **git版本控制** | 已建立 | commit `d4e5e58`~`f74d53c`(16 commits) | — |
| **最終報告撰寫** | 90% | `FINAL_REPORT.md`(v1 定稿) | 4.5 真機ATE為開放事項,§5追蹤 |

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

---

## 接下來的建議順序

1. **軌道一**:真機棋盤 ATE(rig 上裝 5x4/25mm 棋盤全程入鏡,跑 `run_gt_ate.py`)→ 收尾文件
2. **軌道二(選擇性)**:IMU(MPU6050+ESP32)補回,時間資源允許才做
3. **撰寫最終報告**:核心敘事是「原規劃EKF+LoopClosure → 實際走純視覺BA路線 → 建立嚴謹驗證機制(7閘門) → 合成 17/17 全過 + ATE 2.4–2.8mm → 真機節點驗證(P1/P2/P6 全過 + P7 修正後全過)+ P3-P5 標註手推rig硬體限制」,VINS放在未來工作討論

---

## 一句話總結現況

**合成驗證端已完工到論文等級嚴謹度(17/17 閘門、ATE mm 級),真機端跨過 WiFi 關卡後錄出可用的乾淨序列:核心閘門 P1/P2/P6/P7 全部通過,剩餘 P3-P5 是手推 rig 的物理天花板(三序列三種失敗模式量化佐證)——最終以「局部達標 + 硬體限制標註」收尾,軌道一待補棋盤 ATE。**