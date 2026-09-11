#include <Arduino.h>
#include "esp_camera.h"
#include <WiFi.h>
#include <WiFiMulti.h>
#include <esp_sleep.h>

// ===========================
// Module includes
// ===========================
#include "board_config.h"
#include "config/config.h"
#include "firmware/src/motion_detector.h"
#include "firmware/src/alert_manager.h"
#include "firmware/src/sd_manager.h"
#include "firmware/src/event_logger.h"
#include "firmware/src/config_manager.h"

#ifdef IMU_ENABLED
#include "firmware/src/imu_driver.h"
#endif

// ===========================
// Global instances
// ===========================
ConfigManager configManager;
MotionDetector motionDetector;
AlertManager alertManager;
SDManager sdManager;
EventLogger eventLogger;

// ===========================
// WiFi credentials
// ===========================
const char *ssid = WIFI_SSID;
const char *password = WIFI_PASSWORD;

// GPIO for PIR sensor
#define PIR_GPIO_NUM 13  // Adjust based on your wiring

void startCameraServer();
void setupLedFlash();

// ===========================
// Camera configuration
// ===========================
void initCamera() {
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = CAMERA_XCLK_FREQ;
  config.frame_size = FRAMESIZE_UXGA;
  config.pixel_format = PIXFORMAT_JPEG;
  config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
  config.fb_location = CAMERA_FB_IN_PSRAM;
  config.jpeg_quality = CAMERA_JPEG_QUALITY_PSRAM;
  config.fb_count = 1;

  // if PSRAM IC present, init with UXGA resolution and higher JPEG quality
  if (config.pixel_format == PIXFORMAT_JPEG) {
    if (psramFound()) {
      config.jpeg_quality = CAMERA_JPEG_QUALITY_PSRAM;
      config.fb_count = 2;
      config.grab_mode = CAMERA_GRAB_LATEST;
    } else {
      config.frame_size = FRAMESIZE_SVGA;
      config.fb_location = CAMERA_FB_IN_DRAM;
    }
  }

  #if defined(CAMERA_MODEL_ESP_EYE)
    pinMode(13, INPUT_PULLUP);
    pinMode(14, INPUT_PULLUP);
  #endif

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed with error 0x%x", err);
    return;
  }

  sensor_t *s = esp_camera_sensor_get();
  // initial sensors are flipped vertically and colors are a bit saturated
  if (s->id.PID == OV3660_PID) {
    s->set_vflip(s, 1);
    s->set_brightness(s, CAMERA_BRIGHTNESS);
    s->set_contrast(s, CAMERA_CONTRAST);
    s->set_saturation(s, CAMERA_SATURATION);
    s->set_exposure_ctrl(s, CAMERA_EXPOSURE_CTRL);
    s->set_aec_value(s, CAMERA_AEC_VALUE);
  }
  // drop down frame size for higher initial frame rate
  if (config.pixel_format == PIXFORMAT_JPEG) {
    s->set_framesize(s, FRAMESIZE_QVGA);
  }

  #if defined(CAMERA_MODEL_M5STACK_WIDE) || defined(CAMERA_MODEL_M5STACK_ESP32CAM)
    s->set_vflip(s, 1);
    s->set_hmirror(s, 1);
  #endif

  #if defined(CAMERA_MODEL_ESP32S3_EYE)
    s->set_vflip(s, 1);
  #endif

  // Setup LED Flash if LED pin is defined in camera_pins.h
  #if defined(LED_GPIO_NUM)
    setupLedFlash();
  #endif
}

// ===========================
// WiFi setup
// ===========================
void setupWiFi() {
  WiFi.mode(WIFI_AP_STA);
  WiFi.softAP(AP_SSID, AP_PASSWORD);
  Serial.printf("[WiFi] AP '%s' started, AP IP=%s\n",
                AP_SSID, WiFi.softAPIP().toString().c_str());

  WiFi.disconnect(true);
  delay(100);
  WiFi.setSleep(false);
  Serial.printf("[WiFi] STA connecting to '%s' ...\n", ssid);
#if WIFI_STATIC_IP_ENABLED
  IPAddress sta_ip, sta_gw, sta_nm;
  sta_ip.fromString(WIFI_STATIC_IP);
  sta_gw.fromString(WIFI_STATIC_GATEWAY);
  sta_nm.fromString(WIFI_STATIC_NETMASK);
  if (WiFi.config(sta_ip, sta_gw, sta_nm)) {
    Serial.printf("[WiFi] STA static IP configured: %s\n", WIFI_STATIC_IP);
  } else {
    Serial.println("[WiFi] WARN: WiFi.config failed, falling back to DHCP");
  }
#endif
  WiFi.begin(ssid, password);

  uint8_t attempt = 0;
  while (WiFi.status() != WL_CONNECTED && attempt < WIFI_MAX_RETRY) {
    delay(WIFI_RETRY_DELAY_MS);
    attempt++;
    Serial.printf("[WiFi] STA attempt %d status=%d\n", attempt, WiFi.status());
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("[WiFi] STA Connected! IP=%s RSSI=%d dBm\n",
                  WiFi.localIP().toString().c_str(), WiFi.RSSI());
  } else {
    Serial.printf("[WiFi] STA failed (final status=%d), AP is still up\n", WiFi.status());
  }
}

// ===========================
// Time synchronization
// ===========================
void setupTime() {
  if (WiFi.status() == WL_CONNECTED && NTP_ENABLED) {
    configTime(NTP_GMT_OFFSET * 3600, NTP_DAYLIGHT_OFFSET * 3600, NTP_SERVER);
    struct tm timeinfo;
    if (getLocalTime(&timeinfo)) {
      Serial.println("Time synchronized");
      Serial.printf("Current time: %04d-%02d-%02d %02d:%02d:%02d\n",
                    timeinfo.tm_year + 1900, timeinfo.tm_mon + 1, timeinfo.tm_mday,
                    timeinfo.tm_hour, timeinfo.tm_min, timeinfo.tm_sec);
      eventLogger.logInfo(EVENT_NTP_SYNC, "Time synchronized via NTP");
    }
  }
}

// ===========================
// PIR sensor setup
// ===========================
void setupPIR() {
  if (PIR_ENABLED) {
    pinMode(PIR_GPIO_NUM, INPUT);
    Serial.println("PIR sensor initialized");
  }
}

// ===========================
// Motion detection callback
// ===========================
void onMotionDetected(motion_result_t* result) {
  Serial.println("=== MOTION DETECTED ===");
  eventLogger.log(EVENT_MOTION_DETECTED, "Motion detected", 1);
  
  // Capture image
  camera_fb_t* fb = esp_camera_fb_get();
  if (fb) {
    Serial.println("Captured frame for motion event");
    
    // Save to SD card
    if (configManager.getConfig()->sd_enabled) {
      sdManager.saveImage(fb, 1);
    }
    
    // Send alert with photo
    if (configManager.getConfig()->alert_enabled) {
      alertManager.sendAlertWithImage(
        ALERT_TYPE_MOTION,
        "運動偵測告警",
        "偵測到老鼠活動",
        fb->buf, fb->len
      );
    }
    
    esp_camera_fb_return(fb);
  }
}

// ===========================
// Camera setup
// ===========================
void setup() {
  Serial.begin(DEBUG_BAUD_RATE);
  Serial.setDebugOutput(true);
  Serial.println();
  Serial.printf("\n%s v%s\n", SYSTEM_NAME, SYSTEM_VERSION);
  Serial.println("================================");

  // Initialize configuration
  configManager.begin();

  // Initialize event logger
  eventLogger.begin(200);
  eventLogger.logInfo(EVENT_SYSTEM_START, "System starting");

  // Initialize WiFi (before SD manager)
  setupWiFi();

  // Setup camera
  Serial.println("Initializing camera...");
  initCamera();
  eventLogger.logInfo(EVENT_SYSTEM_START, "Camera initialized");

  // Setup SD card
  if (SD_ENABLED) {
    if (sdManager.begin()) {
      eventLogger.logInfo(EVENT_SD_MOUNTED, "SD card mounted");
    } else {
      Serial.println("SD card init failed");
    }
  }

  // Setup PIR sensor
  setupPIR();

  // Setup motion detector
  motionDetector.begin(MOTION_SENSITIVITY, MOTION_COOLDOWN_MS);
  motionDetector.onMotion(onMotionDetected);

  // Setup alert manager
  if (configManager.getConfig()->alert_enabled) {
    alertManager.begin();
    // Test Telegram connection
    if (configManager.getConfig()->telegram_enabled) {
      // 在 setup 中延遲測試，等待 WiFi 穩定
      delay(2000);
      
      // 測試連接
      if (alertManager.isTelegramEnabled()) {
        Serial.println("Testing Telegram...");
        //alertManager.testTelegram();
      }
    }
  }

  // Setup NTP time
  setupTime();

  // Start camera server
  Serial.println("Starting camera server...");
  startCameraServer();

#ifdef IMU_ENABLED
#if IMU_ENABLED
  if (imuDriver.begin(IMU_SDA_PIN, IMU_SCL_PIN, IMU_I2C_FREQ)) {
    // IMU 任務固定 Core 0(影像/HTTP 在預設排程,另一核),高優先級。
    // 預設優先級 1、可被 HTTP 任務搶佔;重要時可調到 3。
    xTaskCreatePinnedToCore(ImuDriver::taskLoop, "imu", 4096, NULL, 1, NULL, 0);
    Serial.println("[IMU] task pinned to Core 0 @ 200Hz");
  }
#endif
#endif

  Serial.println("System ready!");
  Serial.printf("Use 'http://%s' to connect (AP %s)\n",
                WiFi.localIP().toString().c_str(),
                WiFi.softAPIP().toString().c_str());
  Serial.println("================================");
  eventLogger.logInfo(EVENT_SYSTEM_START, "System ready");

  // initial camera feedback
  Serial.println("Camera Ready!");
}

void loop() {
  // Update motion detector (checks PIR state)
  motionDetector.update();

  // Check for motion using camera frame diff (if enabled)
  if (MOTION_DETECTION_ENABLED && configManager.getConfig()->motion_enabled) {
    static uint32_t last_check = 0;
    const uint32_t check_interval = 200;  // Check every 200ms
    
    if (millis() - last_check >= check_interval) {
      last_check = millis();
      
      // Only run motion detection on frame if PIR is high or state is detecting
      if (motionDetector.pirTriggered() || motionDetector.getState() == MOTION_STATE_DETECTING) {
        camera_fb_t* fb = esp_camera_fb_get();
        if (fb) {
          motionDetector.detectMotion(fb);
          // Note: detectMotion returns the previous frame and saves the current.
          // We need to return the frame if detectMotion didn't take ownership
          esp_camera_fb_return(fb);
        }
      }
    }
  }

  // Periodic heartbeat
  static uint32_t last_heartbeat = 0;
  if (millis() - last_heartbeat >= 60000) {  // Every minute
    last_heartbeat = millis();
    eventLogger.logInfo(EVENT_OTHER, "Heartbeat");
  }

  delay(10);  // Small delay to prevent watchdog issues
}
