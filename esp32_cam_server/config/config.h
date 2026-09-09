#ifndef CONFIG_H
#define CONFIG_H

// ===========================
// WiFi 設定
// ===========================
#define WIFI_SSID "CHT113405"
#define WIFI_PASSWORD "0933816226"

// WiFi 重試設定
#define WIFI_MAX_RETRY 10
#define WIFI_RETRY_DELAY_MS 500

// STA 固定 IP(建議用於 VO 實錄:避開 DHCP 每次變動,
// 且 PC 端可固定連 http://192.168.1.200:81/stream 不必翻 serial log)
//
// 目前對應家用 WiFi CHT113405(2.4GHz,gateway 192.168.1.1)。
// 固定 IP 選 .200 避開 DHCP 常見分配段;若衝突(連不上)改下一個。
// 設 1 啟用,設 0 走 DHCP
#define WIFI_STATIC_IP_ENABLED 1
#define WIFI_STATIC_IP "192.168.1.200"
#define WIFI_STATIC_GATEWAY "192.168.1.1"
#define WIFI_STATIC_NETMASK "255.255.255.0"

// ===========================
// AP 熱點設定（設定模式）
// ===========================
#define AP_SSID "RatMonitor_Setup"
#define AP_PASSWORD ""
#define AP_CHANNEL 1
#define AP_MAX_CONNECTIONS 4

// ===========================
// 開發板設定
// ===========================
// 選擇你的開發板（取消註釋其中一個）
// #define CAMERA_MODEL_WROVER_KIT
// #define CAMERA_MODEL_ESP_EYE
#define CAMERA_MODEL_ESP32S3_EYE
// #define CAMERA_MODEL_M5STACK_PSRAM
// #define CAMERA_MODEL_M5STACK_V2_PSRAM
// #define CAMERA_MODEL_M5STACK_WIDE
// #define CAMERA_MODEL_M5STACK_ESP32CAM
// #define CAMERA_MODEL_AI_THINKER

// ===========================
// 攝影機設定
// ===========================
#define CAMERA_XCLK_FREQ 20000000
#define CAMERA_DEFAULT_RESOLUTION FRAMESIZE_VGA
#define CAMERA_DEFAULT_QUALITY 10
#define CAMERA_JPEG_QUALITY_PSRAM 10
#define CAMERA_JPEG_QUALITY_NO_PSRAM 12

// 攝影機初始化設定
#define CAMERA_BRIGHTNESS -2
#define CAMERA_CONTRAST 2
#define CAMERA_SATURATION -2
#define CAMERA_EXPOSURE_CTRL 0  // 0=手動, 1=自動
#define CAMERA_AEC_VALUE 500    // 手動曝光值

// ===========================
// PIR 感測器設定
// ===========================
#define PIR_ENABLED false
#define PIR_PIN GPIO_NUM_13         // PIR 感測器腳位
#define PIR_DEBOUNCE_MS 500         // 去抖動時間
#define PIR_HOLD_TIME_MS 3000       // 保持時間

// ===========================
// 運動偵測設定
// ===========================
#define MOTION_DETECTION_ENABLED true
#define MOTION_SENSITIVITY 50       // 1-100，越高越靈敏
#define MOTION_COOLDOWN_MS 5000     // 偵測冷卻時間（毫秒）
#define MOTION_TRIGGER_COUNT 3      // 觸發所需連續幀數
#define MOTION_MIN_AREA 100         // 最小運動區域（像素）
#define MOTION_DIFF_THRESHOLD 30    // 影像差異閾值

// ===========================
// 拍照設定
// ===========================
#define CAPTURE_ON_MOTION false      // 偵測到運動時拍照
#define CAPTURE_RESOLUTION FRAMESIZE_VGA  // 拍照解析度
#define CAPTURE_QUALITY 10          // JPEG 品質 (0-63)
#define CAPTURE_FLASH true          // 拍照時開閃光燈
#define CAPTURE_COUNT 3             // 每次偵測拍照數量
#define CAPTURE_INTERVAL_MS 500     // 拍照間隔（毫秒）

// ===========================
// 紅外 LED 設定
// ===========================
#define IR_LED_ENABLED true
#define IR_LED_PIN GPIO_NUM_22      // 紅外 LED 腳位
#define IR_LED_PWM_CHANNEL 2
#define IR_LED_PWM_FREQ 5000
#define IR_LED_PWM_RESOLUTION 8
#define IR_LED_MAX_DUTY 255

// ===========================
// 閃光燈設定
// ===========================
#define FLASH_ENABLED true
#define FLASH_PIN GPIO_NUM_4        // 閃光燈腳位

// ===========================
// SD 卡設定
// ===========================
#define SD_ENABLED true
#define SD_MOUNT_POINT "/sdcard"
#define SD_MAX_FILES 1000           // 最大存檔數量
#define SD_AUTO_DELETE true         // 自動刪除舊檔案
#define SD_DELETE_OLDER_DAYS 30     // 刪除超過 N 天的檔案

// ===========================
// 告警設定
// ===========================
#define ALERT_ENABLED true
#define ALERT_COOLDOWN_MS 60000     // 告警冷卻時間（毫秒）

// Telegram 設定
#define TELEGRAM_ENABLED true
#define TELEGRAM_BOT_TOKEN "YOUR_BOT_TOKEN_HERE"
#define TELEGRAM_CHAT_ID "YOUR_CHAT_ID_HERE"

// Email 設定（可選）
#define EMAIL_ENABLED false
#define SMTP_SERVER "smtp.gmail.com"
#define SMTP_PORT 465
#define EMAIL_SENDER "your-email@gmail.com"
#define EMAIL_PASSWORD "your-app-password"
#define EMAIL_RECIPIENT "recipient@example.com"

// Webhook 設定（可選）
#define WEBHOOK_ENABLED false
#define WEBHOOK_URL "http://your-server.com/webhook"

// ===========================
// Web 伺服器設定
// ===========================
#define WEB_SERVER_PORT 80
#define STREAM_SERVER_PORT 81
#define WEB_SERVER_MAX_HANDLERS 16

// ===========================
// 時間戳記設定
// ===========================
#define NTP_ENABLED true
#define NTP_SERVER "pool.ntp.org"
#define NTP_GMT_OFFSET 8  // 台灣 GMT+8
#define NTP_DAYLIGHT_OFFSET 0

// ===========================
// 電源管理設定
// ===========================
#define POWER_SAVE_ENABLED false
#define DEEP_SLEEP_ENABLED false
#define SLEEP_DURATION_US 30000000  // 30 秒

// ===========================
// 除錯設定
// ===========================
#define DEBUG_ENABLED true
#define DEBUG_BAUD_RATE 115200
#define DEBUG_LOG_LEVEL 3  // 0=關閉, 1=錯誤, 2=警告, 3=資訊, 4=除錯

// ===========================
// 系統資訊
// ===========================
#define SYSTEM_NAME "RatMonitor"
#define SYSTEM_VERSION "1.0.0"
#define SYSTEM_AUTHOR "Smart Monitoring Team"

#endif // CONFIG_H
