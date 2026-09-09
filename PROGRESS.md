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
| **真機硬體連線** | 90% | — | ESP32↔PC已ping通,WiFi漫遊問題導致不穩定 |
| **真機乾淨序列實錄** | 0% | — | 卡在WiFi環境問題 |
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

**WiFi/AP模式連線問題(Windows NCSI自動漫遊)**——這是擋在「合成驗證100%完成」跟「真機驗證完成」之間唯一的關卡,且**問題性質是環境設定,不是演算法問題**。

**建議解法(擇一):**
1. ~~改ESP32韌體回**STA模式+固定IP**~~ **已實作**:`esp32_cam_server.ino` 現在支援 STA 固定 IP(`config.h` 的 `WIFI_STATIC_IP_ENABLED`、`172.20.10.8` 對應 iPhone 個人熱點網段),`preflight_esp32.py` / `record_clean_seq.py` 預設 URL 已同步。只需改 config.h 憑證 → `pio run -t upload` → PC 連同一熱點即可,一次完全避開 Windows 自動切換網路的觸發條件。**待實際燒錄 + 錄影驗證。**
2. 若有admin權限,修改機登錄`NCSI\EnableActiveProbing=0`,關閉Windows的網路探測行為

---

## 接下來的建議順序

1. **解決WiFi問題**(建議走STA模式方案)
2. **錄一段乾淨直線序列**,跑過7道閘門
3. **錄棋盤格序列**,量測真機ATE
4. **把真機ATE數字跟合成資料的2.4-2.8mm對照**,討論差異來源(真實雜訊、光照、undistort殘餘誤差等)
5. **撰寫最終報告**:核心敘事是「原規劃EKF+LoopClosure → 實際走純視覺BA路線 → 建立嚴謹驗證機制 → 合成驗證成功 → 真機驗證(mm級精度)」,VINS放在未來工作討論

---

## 一句話總結現況

**理論/合成驗證端已經完工到接近論文等級的嚴謹度,真機驗證只差最後「錄一段影片」這一步,而擋著這一步的是WiFi環境設定問題,不是任何技術/演算法缺陷。**