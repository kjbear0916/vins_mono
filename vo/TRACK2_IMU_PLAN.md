# 軌道二:IMU 補回(MPU6050 + ESP32)— 技術文件與接線圖(草案)

狀態:規劃中(時間/資源允許才做;以軌道一為先,不要兩線同時開)。

## 目標

1. 讓 ESP32 在**影像串流同時**送出 MPU6050 的角速度/加速度,與相機幀共享同一
   時基(ESP32 `millis()`,即現有 meta 的 per-frame ts 同源)。
2. 在 VO 軌跡上加入 IMU 約束:相鄰 keyframe 之間的 gyro 角速度積分,作為
   `vo_bundle.py` 的旋轉殘差(weighted),驗證「純視覺 BA vs 視覺+IMU 約束 BA」
   對航向漂移的改善。
3. **不做**完整 VINS / bias 估計 / preintegration——簡化為「角速度積分 + BA
   rotation residual cost」。

## 硬體接線(MPU6050 ↔ ESP32-CAM/S3)

| MPU6050 腳 | 接到 | 備註 |
|---|---|---|
| VCC | 3.3V(↑ 非 5V,否則上電燒) | 行動電源 5V 需經過底板穩壓 3.3V |
| GND | GND | 共地必要 |
| SDA | **GPIO14**(S3-EYE 閒置腳) | camera 已佔 4,5,6..18,勿用其他 S3-EYE camera pin |
| SCL | **GPIO38**(S3-EYE 閒置腳) | 同上 |
| INT(選用) | 任一 GPIO(如 39) | 不接也行,輪詢即可 |
| AD0 | GND(位址 0x68) | 多顆才需要改 |

> 註:先前草案寫 21/22 是 AI-THINKER 慣用腳,與本題 GOOUUU ESP32-S3-EYE
> 不相容。已改為 14/38;若改板子記得重查 `camera_pins.h` 佔用。

電源:MPU6050 平均 <5mA,3.3V 直接吃 ESP32 底板穩壓即可;若底板沒有
3.3V 抽頭,才從行動電源 5V 經 AMS1117-3.3 降壓(注意壓降需求)。

## 韌體架構(esp32_cam_server.ino)

現況:圖片串流在 `app_httpd.cpp`,`loop()` 只有 motion/heartbeat,
**沒有 IMU、沒有 Core 分割**。(grep 已確認無 IMU/Gyro/Accel 程式碼)

**雛形已完成(2026-09-11,未燒錄)**:`firmware/src/imu_driver.h/.cpp`
(裸 I2C 讀 MPU6050、Core-0 task、UDP 3333 廣播 `IMU,<ts_ms>,gx,gy,gz,ax,ay,az`)、
`config.h` 加 `IMU_ENABLED`(預設 0)、`esp32_cam_server.ino` 加
`#if IMU_ENABLED` 的 xTaskCreatePinnedToCore 掛載。IMU_ENABLED=0 時編譯
路徑完全不碰 IMU 程式碼 → 現有功能零風險。接線後設 1 重燒即可。

待辦:200Hz 固定節拍未在真機實測(S3-EYE 40MHz flash、I2C 400kHz,fps 影響待量;
UDP 無 ACK,若 PC 端掉封包需在 CSV 做 time-gap 校正)。

加 IMU 的四個步驟(全部可熱插拔,不影響影像流):
1. **新增 `imu_driver` 模組**(cpp/h):`Wire.begin(21,22,400000)` →
   `MPU6050` init(可由 Adafruit_MPU6050 或寫裸 I2C 寄存器,SDK 不裝新
   太重的 lib)。任務段架 `xTaskCreatePinnedToCore(imuTask, ..., 0)`。
2. **Core 分割**:影像/HTTP 保持現有排程;IMU task 固定 **Core 0**,
   高優先級,`loop()` 型讀 gyro/accel(200~500Hz),打成簡易 struct
   `{ts_ms, gx, gy, gz, ax, ay, az}` 送進 `WiFiUDP`(UDP port 例如
   3333;影像走 HTTP TCP,兩者互不干擾)。
3. **UDP 封包格式**(一行 CSV 字串):
   ```
   IMU,<millis>,gx,gy,gz,ax,ay,az
   ```
   與 meta 的 per-frame ESP32 `millis()` 共用時基 → 歸檔後 `drone_sync.py`
   可直接在**同一 clock domain** 對齊,免二次校時。
4. **PC 側接收**:PC 開一個 UDP 收 thread,存 `imu_<seq>.csv`(或併入
   `*_meta.json` 旁);VO 事後讀取→ 驗證。

參考:舊的 `esp32s3_cam_imu.ino`(曾有 IMU 讀取,UDP 送出)可作為語法/
初始化參考,但**不直接複製**——現 repo 的韌體是多模組 C++(`app_httpd.cpp`
`config_manager` 等),直接併檔案比較乾淨。

## drone_sync.py 延伸

`drone_sync.SyncTrajectory` 目前吃 `(log.csv, meta.json, traj.csv)`,
log 假設 `ts_ms,roll,pitch,yaw,...`。新增:
- 接受 IMU 裸 CSV(`ts_ms,gx,gy,gz,ax,ay,az`),一樣以 `ts_ms` 對齊
  ESP32 時基(兩者同源,`searchsorted` 直接做)。
- 產生「每對相鄰 keyframe 的 gyro 累積角動」(兩 kf 幀 idx 之間,
  `dt` 由 meta per-frame ts 或 fps 給)。

## vo_bundle.py 的 IMU rotation residual

簡化方案:

```
residual_r(i,i+1) = Log_so3( R_visual(i,i+1)^T · R_imu_by_integration(i,i+1) )
```

- `R_imu_by_integration` = 對 kf_i→kf_{i+1} 之間每個 IMU 樣本做
  `R += R · skew(g) · dt`。
- 加權:外點權(視 residual 大小 Huber),weight 可調(`--imu-weight 0.0~1.0`,
  `0.0` = 純視覺、`1.0` = 全 IMU)。
- 參數開關:BA 總 cost
  `E = E_reproj + w_imu · Σ E_rot`(不混位置,因為視覺已有 scale 爆守衛;
  gyro 積分只約束**旋轉**,避免 scale 污染)。

## 實驗設計(對照)

| 組合 | 設定 | 預期 |
|---|---|---|
| A | `--imu-weight 0.0`(純視覺,現況) | 當前基準(P2/P6 真機已過) |
| B | `--imu-weight 0.3` | 旋轉漂移略降 |
| C | `--imu-weight 1.0` | 過度約束,若 gyro bias 大可能反壞 |

**合成先行**:`gen_synth_seq.py` 加 `--imu` 旗標,在真值運動上加模擬 IMU
(gx/gy/gz 從真值角速度 + 高斯 bias/noise),先在合成上把 B/C 的
reproj/航向改善量化,確認不會傷 P1-P7,再上真機。

## 驗收

- 合成 regression `test_regression.py` 仍 17/17(預設 `--imu-weight 0.0`)。
- 對照組 A/B/C 的 P1-P7 閘門數與航向 drift(角)比較表。
- 真機:seq_real_10 重跑 B,C 與 A 的漂移對比(至少 P2/P6 保持過、P7 不劣化)。

## 風險

- UDP 與 HTTP 同時在 2.4GHz 搶頻寬 → 影像 drop 可能微增(可把 IMU 降到
  100Hz 或只在錄影模式開)。
- bias:未做成 VINS 等級,angle 漂移累積快,只適合「kf 間幾十毫秒」的短程
  積分,不適合長時間導航→ 屬「驗證輔助」而非「導航核心」。
- 時間成本:韌體 + 對齊 + BA 條款 + 實驗,估 1~2 整天,故排軌道一之後。