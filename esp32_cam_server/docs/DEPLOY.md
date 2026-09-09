// ===========================================
// 鼠患智能監控系統 - 安裝與部署指南
// ===========================================

# 安裝部署指南

本文件說明如何從零開始設置鼠患智能監控系統。

## 目錄

1. [準備工作](#1-準備工作)
2. [硬體組裝](#2-硬體組裝)
3. [軟體環境設置](#3-軟體環境設置)
4. [程式燒錄](#4-程式燒錄)
5. [首次啟動設定](#5-首次啟動設定)
6. [系統測試](#6-系統測試)
7. [部署安裝](#7-部署安裝)
8. [日常維護](#8-日常維護)

---

## 1. 準備工作

### 1.1 所需硬體

請參考 **[HARDWARE.md](HARDWARE.md)** 準備以下元件：

- [ ] ESP32-S3-CAM 開發板
- [ ] PIR 感測器 (HC-SR501)
- [ ] 紅外 LED 補光燈
- [ ] MicroSD 卡 (32GB)
- [ ] 5V/2A USB 電源
- [ ] 杜邦線 / 電線
- [ ] USB-TTL 轉換器

### 1.2 軟體工具

- [ ] 安裝 [Arduino IDE](https://www.arduino.cc/en/software) 或 [PlatformIO](https://platformio.org/)
- [ ] 安裝 ESP32 開發板支援
- [ ] 安裝 USB-TTL 驅動程式

---

## 2. 硬體組裝

請參考 **[WIRING.md](WIRING.md)** 進行接線。

### 2.1 基本接線

1. PIR 感測器連接到 ESP32：
   - VCC → 3.3V
   - GND → GND
   - OUT → GPIO 13

2. 紅外 LED 連接到 GPIO 22（需串聯 330Ω 電阻）

3. 插入 MicroSD 卡

### 2.2 檢查清單

- [ ] 所有接線正確
- [ ] 電源正負極正確
- [ ] 無短路或接觸不良
- [ ] SD 卡已格式化為 FAT32

---

## 3. 軟體環境設置

### 3.1 Arduino IDE 設置

1. **添加 ESP32 開發板支援**：
   - 開啟 Arduino IDE
   - `File → Preferences`
   - 在 "Additional boards manager URLs" 添加：
     ```
     https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
     ```
   - `Tools → Board → Boards Manager`
   - 搜尋 "esp32" 並安裝

2. **選擇開發板**：
   - `Tools → Board → esp32 → ESP32S3 Dev Module`

3. **PSRAM 設定**：
   - `Tools → PSRAM → OPI PSRAM`
   - 或 `Tools → PSRAM → Enabled`

4. **分割表設定**：
   - `Tools → Partition Scheme → Custom` 
   - 使用專案內的 `partitions.csv`

5. **其他設定**：
   - Flash Size: 16MB
   - Flash Mode: QIO
   - Upload Speed: 921600

### 3.2 PlatformIO 設置

1. **安裝 PlatformIO**：
   ```bash
   pip install platformio
   # 或安裝 VSCode 擴充
   ```

2. **建立專案**：
   ```bash
   # 複製專案到工作目錄
   cp -r esp32_cam_server ~/my-rat-monitor
   cd ~/my-rat-monitor
   ```

3. **確認 platformio.ini**：
   ```ini
   [env:esp32s3]
   platform = espressif32
   board = esp32-s3-devkitc-1
   framework = arduino
   board_build.partitions = partitions.csv
   board_build.flash_size = 16MB
   monitor_speed = 115200
   ```

---

## 4. 程式燒錄

### 4.1 PlatformIO 燒錄

```bash
# 確認端口
pio device list

# 燒錄
pio run -t upload

# 監控 Serial 輸出
pio device monitor
```

### 4.2 Arduino IDE 燒錄

1. 連接 ESP32 到電腦
2. 選擇正確的端口
3. `Upload` 按鈕
4. 按住 BOOT 按鈕直到開始燒錄

### 4.3 燒錄後檢查

預期 Serial 輸出：
```
RatMonitor v1.0.0
================================
[Config] Configuration loaded from NVS
[EventLog] Initialized: 200 entries
[EventLog] [SYSTEM_START|0] System starting
Initializing camera...
[SD] Card Mounted Successfully
[Motion] PIR sensor initialized
[Alert] Alert Manager initialized
Time synchronized
Starting camera server...
Use 'http://192.168.1.100' to connect
================================
System ready
```

---

## 5. 首次啟動設定

### 5.1 標準模式

1. **連接電源**：插入 USB 電源
2. **等待啟動**：約 10-15 秒
3. **記下 IP 位址**：從 Serial 螢幕中查看
4. **開啟 Web 面板**：瀏覽器訪問 `http://[IP]`

### 5.2 AP 模式（沒有 WiFi 時）

如果無法連接 WiFi，ESP32 會建立 AP：

1. **連接熱點**：搜尋 `RatMonitor_Setup`
2. **密碼**：`12345678`
3. **開啟 Web 面板**：訪問 `http://192.168.4.1`

### 5.3 設定通知

1. **Telegram**：
   - 用 @BotFather 建立 bot
   - 取得 token 和 chat ID
   - 透過 Web 面板設定

2. **Email**：
   - 透過 Web 面板設定 SMTP

---

## 6. 系統測試

### 6.1 基本功能測試

- [ ] Web 面板可以開啟
- [ ] 即時影像正常顯示
- [ ] 拍照功能正常
- [ ] 解析度/品質調整正常

### 6.2 偵測功能測試

- [ ] PIR 感測器有反應
- [ ] 運動偵測會觸發拍照
- [ ] Telegram 通知收到
- [ ] SD 卡有影像儲存

### 6.3 夜間測試

- [ ] IR LED 正常運作
- [ ] 夜間畫面清晰
- [ ] 自動曝光調整正常

---

## 7. 部署安裝

### 7.1 安裝位置建議

| 位置 | 優點 | 注意事項 |
|------|------|----------|
| 天花板角落 | 視野佳，不易被破壞 | 需要走線 |
| 牆角地面 | 接近鼠類活動區域 | 容易被遮擋 |
| 儲藏室內部 | 直接監控目標區域 | 空間可能狹小 |
| 廚房角落 | 常見鼠患區域 | 需注意防水防潮 |

### 7.2 固定方式

1. **螺絲固定**：使用不鏽鋼螺絲
2. **3M 雙面膠**：適合輕量安裝
3. **束帶固定**：適合管線或支架

### 7.3 防水處理

如果在潮濕環境：
- 使用 IP65 防水外殼
- 所有接線接口需防水
- 電源線需固定避免鬆脫

### 7.4 供電方案

| 方案 | 適用場景 | 優點 | 缺點 |
|------|----------|------|------|
| USB 供電 | 室內固定位置 | 簡單穩定 | 需要插座 |
| 行動電源 | 臨時安裝 | 便攜 | 需要充電 |
| 太陽能+電池 | 戶外長期使用 | 免維護 | 成本較高 |

---

## 8. 日常維護

### 8.1 定期檢查

- [ ] 每週確認系統正常運作
- [ ] 每兩週清潔鏡頭
- [ ] 每月檢查 SD 卡空間
- [ ] 每月檢查電池/電源

### 8.2 檔案管理

```cpp
// 在 config.h 設定
#define SD_AUTO_DELETE true   // 自動刪除舊檔案
#define SD_DELETE_OLDER_DAYS 30  // 保留 30 天
```

### 8.3 系統更新

```bash
# 更新 PlatformIO
pio update

# 更新 ESP32 核心
pio pkg update

# 重新燒錄
pio run -t upload
```

### 8.4 資料備份

1. **定期下載**：透過 Web 面板下載重要影像
2. **SD 卡抽換**：更換新的 SD 卡
3. **雲端同步**：設定自動上傳到雲端

---

## 附錄：常用指令速查

```bash
# PlatformIO
pio run               # 編譯
pio run -t upload     # 燒錄
pio device monitor    # Serial 監控
pio device list       # 查看端口

# 測試 Web
curl http://[IP]/status
curl http://[IP]/capture -o test.jpg
curl http://[IP]/stream

# 測試控制
curl "http://[IP]/control?var=quality&val=10"
curl "http://[IP]/control?var=framesize&val=11"

# 測試通知
curl http://[IP]/test/telegram
```
