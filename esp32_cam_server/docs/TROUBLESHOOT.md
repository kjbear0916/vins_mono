# 故障排除指南

## VO 實錄：STA 模式 + 固定 IP(避開 Windows NCSI 漫遊)

**症狀**:ESP32 開 AP(`RatMonitor_Setup`)時,Windows 因該網路「無網際網路」
被 NCSI 主動探測判死,自動跳回其他 WiFi,連線數秒後斷。

**解法(不需 admin)**:改用 STA 模式,讓 ESP32 加入手機熱點/路由器,
PC 也連同一熱點,雙方同在一個正常(有網際網路)網路,不再觸發 NCSI。

1. `config/config.h` 設好熱點憑證:
   ```c
   #define WIFI_SSID "iPhone"
   #define WIFI_PASSWORD "12345678"
   #define WIFI_STATIC_IP_ENABLED 1
   #define WIFI_STATIC_IP "172.20.10.8"       // iPhone 個人熱點網段 172.20.10.0/28
   #define WIFI_STATIC_GATEWAY "172.20.10.1"
   #define WIFI_STATIC_NETMASK "255.255.255.240"
   ```
   換其他熱點時先 `ipconfig /all` 看網段,再改固定 IP 三宏。
2. 重新燒錄:`pio run -t upload`
3. PC 也連同一熱點;燒錄後 Serial 應印 `STA Connected! IP=172.20.10.8`
4. 驗證:`python esp32_cam_server/preflight_esp32.py --url http://172.20.10.8`
5. 錄製:`python vo/record_clean_seq.py --url http://172.20.10.8:81/stream ...`

> 若固定 IP 與熱點分配的 DHCP 位址衝突,ESP32 會連不上,改一個
> 未被佔用的 host(如 `172.20.10.9`)重燒即可。

## 常見問題與解決方案

### 1. 無法連接 WiFi

**症狀**：
- 設備提示 "WiFi connecting" 但一直無法連接
- Web 面板顯示離線

**可能原因與解決方法**：

| 原因 | 解決方法 |
|------|----------|
| SSID 或密碼錯誤 | 檢查 `config/config.h` 中設定 |
| 使用 5GHz WiFi | ESP32 只支援 2.4GHz，需要切換 |
| 訊號太弱 | 增加路由器距離或使用 WiFi 延伸器 |
| 路由器 MAC 過濾 | 在路由器中加入 ESP32 的 MAC 位址 |
| 連線數限制 | 檢查路由器最大連線數設定 |

**檢查指令**：
```bash
# 確認 ESP32 的 MAC 位址
# 登入 ESP32 的 AP 模式或查看 Serial 輸出
```

### 2. 攝影機初始化失敗

**症狀**：
- Serial 輸出：`Camera init failed with error 0x...`
- 無法開啟 `/stream` 或 `/capture`

**錯誤碼對照**：

| 錯誤碼 | 原因 | 解決方法 |
|--------|------|----------|
| 0x20001 | 記憶體不足 | 啟用 PSRAM |
| 0x20002 | 時脈錯誤 | 降低 XCLK 頻率 |
| 0x20003 | 感測器初始化失敗 | 檢查 I2C 接線 |
| 0x20004 | 幀緩衝問題 | 降低解析度或品質 |

**解決方法**：
1. 確認開發板型號正確（`board_config.h`）
2. 確認已啟用 PSRAM：
   ```
   Arduino IDE → Tools → PSRAM → 啟用
   ```
   ```
   PlatformIO：
   build_flags = -DBOARD_HAS_PSRAM
   ```

### 3. 無法燒錄程式

**症狀**：
- Arduino IDE 顯示 "Connecting..._________"
- 燒錄失敗

**解決方法**：
1. 按住 BOOT/IO0 按鈕再上電
2. 確認 USB-TTL 驅動已安裝：
   - CP2102 → https://www.silabs.com/developers/usb-to-uart-bridge-vcp-drivers
   - CH340 → 搜尋 CH340 driver
3. 確認在燒錄前先按 Reset

**常用燒錄指令**：
```bash
# PlatformIO
pio run -t upload

# esptool.py
esptool.py --chip esp32s3 --port COM3 write_flash -z 0x1000 firmware.bin

# 查看可用端口
pio device list
```

### 4. 串流畫面模糊或品質差

**解決方法**：

1. **調整解析度**：
   ```bash
   # 改用較低解析度
   GET /control?var=framesize&val=11  # VGA
   GET /control?var=framesize&val=13  # QVGA
   ```

2. **調整品質**：
   ```bash
   # 品質值越低，畫質越好，但檔案越大
   GET /control?var=quality&val=8
   GET /control?var=quality&val=12
   ```

3. **調整影像參數**：
   ```bash
   GET /control?var=brightness&val=-1
   GET /control?var=contrast&val=2
   GET /control?var=saturation&val=-1
   ```

4. **改善光照**：
   - 確保光線充足
   - 使用紅外 LED 補光
   - 避免強背光

### 5. 夜間看不到影像

**解決方法**：
1. 確認 IR LED 已連接且正常運作
2. 調整 IR LED 亮度：
   ```bash
   GET /control?var=led_intensity&val=200
   ```
3. 手動曝光調整：
   ```bash
   GET /control?var=aec&val=0  # 關閉自動曝光
   GET /control?var=aec_value&val=800  # 手動曝光
   ```
4. 增加圖像增益：
   ```bash
   GET /control?var=agc&val=1
   GET /control?var=gainceiling&val=5
   ```

### 6. PIR 感測器沒有反應

**診斷步驟**：

1. **檢查接線**：
   - VCC 連到 3.3V（不要用 5V）
   - GND 正確接地
   - OUT 連到 GPIO 13

2. **檢查 Serial 輸出**：
   ```
   [Motion] PIR sensor initialized
   ```
   如果沒看到這行，表示 PIR 未初始化

3. **測試 PIR 訊號**：
   ```cpp
   // 測試程式
   void setup() {
     Serial.begin(115200);
     pinMode(13, INPUT);
   }
   void loop() {
     Serial.println(digitalRead(13));
     delay(500);
   }
   ```
   - 無人在附近時：應輸出 0
   - 人經過時：應輸出 1

4. **調整 PIR 設定**：
   - 調整靈敏度電阻
   - 確認跳線設定為 Repeatable (H)

### 7. SD 卡無法使用

**症狀**：
- Serial 輸出：`[SD] Card Mount Failed`
- 無法儲存影像

**解決方法**：

1. **格式化 SD 卡**：
   - 使用 SD Card Formatter 工具
   - 格式：FAT32
   - 容量限制：≤ 32GB
   - 官方工具：https://www.sdcard.org/downloads/formatter/

2. **檢查接線**：
   - 確認 SD 卡方向正確
   - 檢查焊接/連接是否牢固

3. **Windows 格式化提示**：
   ```powershell
   # 使用 diskpart
   diskpart
   list disk
   select disk X
   clean
   create partition primary
   format fs=fat32 quick
   ```

### 8. Telegram 通知收不到

**診斷步驟**：

1. **確認 Bot Token 是否正確**：
   - 與 @BotFather 重新確認
   - Token 格式：`123456789:ABC...`

2. **確認 Chat ID 是否正確**：
   ```bash
   # 獲取 Chat ID
   curl "https://api.telegram.org/bot<TOKEN>/getUpdates"
   ```
   - 先給 Bot 發一條訊息
   - 在回應中找到 `chat.id`

3. **確認 Bot 已啟動**：
   - 發送 `/start` 給 Bot

4. **確認網路連接**：
   - 執行測試：`GET /test/telegram`
   - 查看 Serial 輸出

5. **防火牆/WiFi 限制**：
   - 確認 443 port 對外開放
   - 某些公共 WiFi 需要特殊設定

### 9. Web 介面無法開啟

**排查步驟**：

1. **確認 ESP32 已連上 WiFi**：
   - Serial 輸出應顯示 IP 位址
   - `http://[IP位址]`

2. **確認 IP 位址正確**：
   ```bash
   # Windows
   ipconfig
   
   # Linux/Mac
   ifconfig
   ```
   確保與 ESP32 在同一網段

3. **確認端口**：
   - Web 面板：80
   - 串流：81
   - 都應能訪問

4. **瀏覽器相容性**：
   - 推薦 Chrome / Firefox / Safari 最新版本
   - 確認未使用代理

### 10. 系統運行不穩定 / 當機

**可能原因**：
- 記憶體不足
- WiFi 斷線
- 電源不穩定
- 溫度過高

**解決方法**：
1. 檢查記憶體使用：
   ```bash
   # 查看 Serial 輸出中的記憶體資訊
   # 確認 free heap 不為負數
   ```
2. 穩定供電：
   - 使用 2A 以上電源
   - 電源線不要太長
3. 散熱：
   - 避免在高溫環境
   - 加裝散熱片
4. 更新韌體：
   - 解決已知 bug

## 診斷工具

### Serial 監控

```bash
# PlatformIO
pio device monitor

# Arduino IDE
# Tools → Serial Monitor
```

**啟動時應看到的正常輸出**：
```
RatMonitor v1.0.0
================================
[Config] Configuration loaded from NVS
[EventLog] Initialized: 200 entries
[EventLog] [SYSTEM_START|0] System starting
Initializing camera...
[SD] Card Mount Failed        ← SD 卡未連接
[Motion] PIR sensor initialized
[Alert] Alert Manager initialized
Time synchronized
Starting camera server...
Use 'http://192.168.1.100' to connect
================================
  System ready
```

### Web 介面排查

```bash
# 測試 Web 連接
curl http://[IP]
curl http://[IP]/status

# 測試串流
curl -N http://[IP]/stream
```

### 重設為出廠設定

如果系統完全無法運作，可以透過以下方式重置：

1. **軟體重置**：透過 Web 面板或 API
   ```
   POST /reset
   ```

2. **清除 NVS**：
   ```cpp
   // 在 setup() 中加入
   nvs_flash_erase();
   ```

3. **重新燒錄**：重新上傳完整的固件

## 聯繫支援

如果以上方法都無法解決，請準備以下資訊以便除錯：

1. ESP32 型號
2. 攝影機感測器型號（OV2640 / OV3660 / OV5640）
3. Arduino/PlatformIO 版本
4. 完整 Serial 輸出
5. 使用的電源類型
6. 是否曾經成功運作過
