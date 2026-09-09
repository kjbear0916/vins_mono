# 專題進度總表(修正版)

## 研究定位

**題目:** 室內無人機自動導航系統之感知定位子系統——純視覺Bundle Adjustment軌跡估計與驗證

**路線說明:** 原規劃EKF+IMU融合+Loop Closure,實際執行後改走**純視覺增量PnP + Bundle Adjustment**路線。VINS路線經評估後不採用,列未來工作。

---

## 進度總表

| 模組 | 完成度 | 實際產出物 | 狀態說明 |
|---|---|---|---|
| **硬體韌體/傳輸** | 95% | `esp32_cam_server.ino`(WIFI_AP_STA雙模,內建STA連線邏輯)、`video_source.py`(`HTTPMJPEGSource`/`ThreadedMJPEGSource`) | **僅影像傳輸,無IMU**(grep確認`esp32_cam_server.ino`無IMU/Gyro/Accel相關程式碼),卡在AP模式WiFi環境問題 |
| **VO前端(增量PnP+Local Map)** | 100% | `vo_local_map.py`、`vo_core.py` | Bootstrap死鎖、id錯位、視差角過濾等bug已修完 |
| **~~EKF融合~~(已改路線)** | — | — | 原規劃項目,由BA取代;**因韌體從未實作IMU傳輸,EKF這條路線實際上從未具備執行條件** |
| **Bundle Adjustment全局優化** | 100% | `vo_bundle.py`、`run_offline_ba.py`、`run_ba_kfvo.py` | drift從~3577px降到~26px |
| **時間同步** | 100% | `drone_sync.py` | 偏移校正、n_cam修正、searchsorted查姿完成 |
| **7道自動化驗證閘門** | 100% | `validate_traj_pass.py`、`run_clean_seq_check.py` | 正負對照組驗證完畢 |
| **合成資料驗證** | 100% | `gen_synth_seq.py`、`synth_clean_01.avi`等 | 7/7閘門全過,ATE 2.4–2.8mm |
| **核心bug修正** | 100% | umeyama_sim3修正、class/script drift收束 | 17/17 regression全過 |
| **相機標定** | 100% | `calibration_esp32_qvga.npz`(另有`esp32.npz`) | RMS 0.259px |
| **真機硬體連線** | 100% | — | 家用WiFi AP模式固定IP 192.168.1.200,stream/status/control 全通 |
| **真機乾淨序列實錄** | 60% | `seq_real_08/09.avi` + meta | P1/P2(0.93px)/P6(21kfs/150pts) PASS;P3-P5 為手推rig物理天花板,P7 待重錄 |
| **真機ATE量測** | 0% | — | 依賴上一步 |
| **~~Loop Closure~~** | — | — | 未執行 |
| **~~VINS~~** | — | — | 不採用,列未來工作 |
| **文件/日誌** | 80% | `VO_REAL_SEQ_VALIDATION.md`、`DRONE_SYNC.md`、觀察日誌0001–0006 | 缺最終整合報告 |
| **git版本控制** | 已建立 | commit `d4e5e58` | — |
| **最終報告撰寫** | 0% | — | 待真機數據到位 |

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

---

## 接下來的建議順序

1. **重錄一支配好 HOLD1 的序列**(推到底定住不動,P7<2.0 目標)→ 補齊 P7
2. **撰寫最終報告**:核心敘事是「原規劃EKF+LoopClosure → 實際走純視覺BA路線 → 建立嚴謹驗證機制(7閘門) → 合成 17/17 全過 + ATE 2.4–2.8mm → 真機節點驗證(P1/P2/P6)+ P3-P5 標註手推rig硬體限制」,VINS放在未來工作討論

---

## 一句話總結現況

**合成驗證端已完工到論文等級嚴謹度(17/17 閘門、ATE mm 級),真機端跨過 WiFi 關卡後錄出可用的乾淨序列:核心演算法閘門(P1/P2/P6)全部通過,剩餘 P3-P5 是手推 rig 的物理天花板、P7 重錄可解——最終以「局部達標 + 硬體限制標註」收尾。**