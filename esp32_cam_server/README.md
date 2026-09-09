# 鼠患智能監控系統 (Smart Rat Infestation Monitoring System)

基於 ESP32-CAM 的低成本、高效能鼠患監控解決方案。

## 系統架構

```
┌─────────────────────────────────────────────────────────────┐
│                    鼠患智能監控系統                            │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │  ESP32-CAM  │◄───│  PIR 感測器  │    │  紅外補光燈  │     │
│  │  (主控板)   │    │  (運動偵測) │    │  (夜間照明) │     │
│  └──────┬──────┘    └─────────────┘    └─────────────┘     │
│         │                                                   │
│         ▼                                                   │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │  WiFi/AP    │───►│  Web 面板   │    │  SD 卡      │     │
│  │  (網路連接) │    │  (遠端監控) │    │  (影像存儲) │     │
│  └─────────────┘    └─────────────┘    └─────────────┘     │
│         │                                                   │
│         ▼                                                   │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │  Telegram   │    │  Email      │    │  本地記憶體  │     │
│  │  推播通知   │    │  告警郵件   │    │  (事件日誌) │     │
│  └─────────────┘    └─────────────┘    └─────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

## 功能特性

### 核心功能
- **即時影像串流**: MJPEG 串流，支援多種解析度
- **運動偵測**: PIR 感測器觸發 + 影像差異檢測
- **智慧拍照**: 偵測到運動時自動拍照並存儲
- **夜間監控**: 紅外 LED 補光，全天候監控
- **Web 遠端監控**: 手機/電腦瀏覽器即可查看

### 告警系統
- **Telegram 推播**: 即時接收偵測通知
- **Email 告警**: 傳送偵測影像至指定郵箱
- **Web 面板通知**: 本地瀏覽器推送

### 數據管理
- **SD 卡存儲**: 自動儲存偵測影像
- **事件日誌**: 記錄所有偵測事件
- **統計分析**: 偵測次數、時間分佈

## 硬體需求

| 項目 | 規格 | 數量 | 備註 |
|------|------|------|------|
| ESP32-S3-CAM | GOOUUU ESP32-S3-CAM + OV3660 | 1 | 主控板，需帶 PSRAM |
| PIR 感測器 | HC-SR501 | 1 | 運動偵測觸發 |
| 紅外 LED | 850nm IR LED | 2-4 | 夜間補光 |
| MicroSD 卡 | 32GB+ Class 10 | 1 | 影像存儲 |
| USB 電源 | 5V/2A | 1 | 供電 |
| 電源模組 | AMS1117-3.3V | 1 | 可選，外部供電 |

## 快速開始

### 1. 環境準備

安裝 Arduino IDE 或 PlatformIO：
```bash
# PlatformIO (推薦)
pip install platformio

# 或使用 Arduino IDE
# 安裝 ESP32 開發板支援包
```

### 2. 配置設定

編輯 `config/config.h`：
```cpp
// WiFi 設定
#define WIFI_SSID "你的WiFi名稱"
#define WIFI_PASSWORD "你的WiFi密碼"

// Telegram 設定
#define TELEGRAM_BOT_TOKEN "你的Bot Token"
#define TELEGRAM_CHAT_ID "你的Chat ID"

// Email 設定 (可選)
#define SMTP_SERVER "smtp.gmail.com"
#define SMTP_PORT 465
#define EMAIL_SENDER "your-email@gmail.com"
#define EMAIL_PASSWORD "your-app-password"
#define EMAIL_RECIPIENT "recipient@example.com"
```

### 3. 燒錄固件

```bash
# 使用 PlatformIO
pio run -t upload

# 或使用 Arduino IDE
# 選擇開發板: ESP32S3 Dev Module
# 選擇分割表: 自訂 (partitions.csv)
# 上傳程式碼
```

### 4. 首次啟動

1. 上電後 ESP32 會建立 AP 熱點：`RatMonitor_Setup`
2. 連接該熱點，瀏覽器打開 `http://192.168.4.1`
3. 在 Web 面板設定 WiFi 和通知參數
4. 設定完成後重啟，ESP32 會連接你的 WiFi

## 使用方式

### Web 監控面板

連接同一網路後，訪問：
```
http://[ESP32_IP地址]
```

功能：
- 即時影像串流
- 運動偵測設定
- 偵測歷史記錄
- 系統設定
- 影像回放

### Telegram 通知

1. 建立 Telegram Bot：
   - 搜尋 `@BotFather`
   - 發送 `/newbot` 建立機器人
   - 取得 Bot Token

2. 取得 Chat ID：
   - 將機器人加入群組或直接對話
   - 訪問 `https://api.telegram.org/bot<TOKEN>/getUpdates`
   - 找到 `chat.id`

3. 填入 `config/config.h` 或透過 Web 面板設定

### API 端點

| 端點 | 方法 | 說明 |
|------|------|------|
| `/` | GET | Web 面板首頁 |
| `/capture` | GET | 拍攝一張照片 |
| `/stream` | GET | MJPEG 影像串流 |
| `/status` | GET | 系統狀態 JSON |
| `/control?var=xxx&val=yyy` | GET | 控制參數 |
| `/events` | GET | 偵測事件列表 |
| `/events?clear=1` | GET | 清除事件記錄 |

## 專案結構

```
esp32_cam_server/
├── README.md                    # 本文件
├── esp32_cam_server.ino         # 主程式
├── board_config.h               # 開發板配置
├── camera_pins.h                # 腳位定義
├── camera_index.h               # Web 介面 HTML
├── app_httpd.cpp                # HTTP 伺服器
├── partitions.csv               # 自訂分割表
├── ci.yml                       # CI 配置
│
├── config/
│   ├── config.h                 # 系統配置
│   └── config.example.h         # 配置範例
│
├── firmware/
│   └── src/
│       ├── motion_detector.h    # 運動偵測模組
│       ├── motion_detector.cpp
│       ├── alert_manager.h      # 告警管理模組
│       ├── alert_manager.cpp
│       ├── sd_manager.h         # SD 卡管理模組
│       ├── sd_manager.cpp
│       ├── event_logger.h       # 事件記錄模組
│       └── event_logger.cpp
│
├── web/
│   ├── index.html               # 主控面板
│   ├── css/
│   │   └── style.css            # 樣式表
│   └── js/
│       └── app.js               # 前端腳本
│
├── docs/
│   ├── HARDWARE.md              # 硬體安裝指南
│   ├── WIRING.md                # 接線圖
│   ├── TROUBLESHOOT.md          # 故障排除
│   └── API.md                   # API 文檔
│
└── tools/
    └── flash.bat                # 燒錄腳本
```

## 進階設定

### 運動偵測靈敏度

```cpp
// config.h 中調整
#define MOTION_SENSITIVITY 50      // 1-100，越高越靈敏
#define MOTION_COOLDOWN_MS 5000    // 冷卻時間（毫秒）
#define MOTION_TRIGGER_COUNT 3     // 觸發所需連續幀數
```

### 拍照設定

```cpp
#define CAPTURE_RESOLUTION FRAMESIZE_VGA  // 拍照解析度
#define CAPTURE_QUALITY 10                // JPEG 品質 (0-63)
#define CAPTURE_FLASH true                // 拍照時開閃光燈
```

### 低功耗模式

```cpp
#define DEEP_SLEEP_ENABLED false    // 啟用深度睡眠
#define SLEEP_DURATION_US 30000000  // 睡眠時間（微秒）
#define WAKEUP_PIN GPIO_NUM_13      // 喚醒腳位
```

## 故障排除

### 常見問題

**Q: WiFi 無法連接**
- 確認 SSID 和密碼正確
- 確認 WiFi 為 2.4GHz（ESP32 不支援 5GHz）
- 檢查訊號強度

**Q: 攝影機初始化失敗**
- 確認開發板型號正確（`board_config.h`）
- 確認 PSRAM 已啟用
- 檢查接線是否正確

**Q: Telegram 通知收不到**
- 確認 Bot Token 正確
- 確認 Chat ID 正確
- 確認機器人已被啟動（發送 `/start`）

**Q: SD 卡無法寫入**
- 確認 SD 卡格式為 FAT32
- 確認 SD 卡容量 ≤ 32GB
- 確認 SD 卡未鎖定

## 授權條款

本專案採用 Apache License 2.0 授權條款。

## 聯繫方式

如有問題或建議，歡迎聯繫。
