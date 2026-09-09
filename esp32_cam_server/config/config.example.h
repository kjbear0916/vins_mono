// ===========================================
// 鼠患智能監控系統 - 配置範例
// 複製此檔案為 config.h 並填入你的設定
// ===========================================
#ifndef CONFIG_H
#define CONFIG_H

// ===========================
// WiFi 設定
// ===========================
#define WIFI_SSID "YOUR_WIFI_SSID"
#define WIFI_PASSWORD "YOUR_WIFI_PASSWORD"

// WiFi 重試設定
#define WIFI_MAX_RETRY 10
#define WIFI_RETRY_DELAY_MS 500

// STA 固定 IP(選用;iPhone 個人熱點網段 172.20.10.0/28,
// gateway 172.20.10.1、host .2 ~ .14)。設 0 走 DHCP。
#define WIFI_STATIC_IP_ENABLED 0
#define WIFI_STATIC_IP "172.20.10.8"
#define WIFI_STATIC_GATEWAY "172.20.10.1"
#define WIFI_STATIC_NETMASK "255.255.255.240"

// ===========================
// AP 熱點設定（設定模式）
// ===========================
#define AP_SSID "RatMonitor_Setup"
#define AP_PASSWORD "12345678"

// ===========================
// 開發板設定 - 只保留一個
// ===========================
//#define CAMERA_MODEL_AI_THINKER      // ESP32-CAM
#define CAMERA_MODEL_ESP32S3_EYE     // GOOUUU ESP32-S3-CAM  <-- 預設
//#define CAMERA_MODEL_WROVER_KIT
//#define CAMERA_MODEL_ESP_EYE

// ===========================
// 攝影機設定
// ===========================
#define CAMERA_XCLK_FREQ 20000000
#define CAMERA_JPEG_QUALITY_PSRAM 10
#define CAMERA_JPEG_QUALITY_NO_PSRAM 12

// ===========================
// PIR 感測器設定
// ===========================
#define PIR_ENABLED true
#define PIR_PIN GPIO_NUM_13

// ===========================
// 運動偵測設定
// ===========================
#define MOTION_DETECTION_ENABLED true
#define MOTION_SENSITIVITY 50
#define MOTION_COOLDOWN_MS 5000
#define MOTION_TRIGGER_COUNT 3

// ===========================
// 拍照設定
// ===========================
#define CAPTURE_ON_MOTION true
#define CAPTURE_QUALITY 10
#define CAPTURE_FLASH true
#define CAPTURE_COUNT 3

// ===========================
// 紅外 LED 設定
// ===========================
#define IR_LED_ENABLED true
#define IR_LED_PIN GPIO_NUM_22

// ===========================
// SD 卡設定
// ===========================
#define SD_ENABLED true
#define SD_AUTO_DELETE true
#define SD_DELETE_OLDER_DAYS 30

// ===========================
// Telegram 通知設定
// ===========================
#define TELEGRAM_ENABLED true
#define TELEGRAM_BOT_TOKEN "YOUR_BOT_TOKEN"
#define TELEGRAM_CHAT_ID "YOUR_CHAT_ID"

// ===========================
// Email 通知設定（可選）
// ===========================
#define EMAIL_ENABLED false
#define SMTP_SERVER "smtp.gmail.com"
#define SMTP_PORT 465
#define EMAIL_SENDER "your-email@gmail.com"
#define EMAIL_PASSWORD "your-app-password"
#define EMAIL_RECIPIENT "recipient@example.com"

// ===========================
// Webhook 通知設定（可選）
// ===========================
#define WEBHOOK_ENABLED false
#define WEBHOOK_URL ""

// ===========================
// 告警冷卻時間
// ===========================
#define ALERT_ENABLED true
#define ALERT_COOLDOWN_MS 60000

// ===========================
// NTP 時間同步
// ===========================
#define NTP_ENABLED true
#define NTP_SERVER "pool.ntp.org"
#define NTP_GMT_OFFSET 8     // 台灣 GMT+8
#define NTP_DAYLIGHT_OFFSET 0

// ===========================
// 電源管理
// ===========================
#define POWER_SAVE_ENABLED false
#define DEEP_SLEEP_ENABLED false
#define SLEEP_DURATION_US 30000000

// ===========================
// 除錯設定
// ===========================
#define DEBUG_ENABLED true
#define DEBUG_BAUD_RATE 115200
#define DEBUG_LOG_LEVEL 3

// ===========================
// 系統資訊
// ===========================
#define SYSTEM_NAME "RatMonitor"
#define SYSTEM_VERSION "1.0.0"

#endif // CONFIG_H
