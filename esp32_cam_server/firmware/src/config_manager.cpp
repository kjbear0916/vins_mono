#include "config_manager.h"
#include "config/config.h"

static void prefsGetString(Preferences& p, const char* key, char* buf, size_t len, const char* dflt) {
    String s = p.getString(key, dflt);
    strncpy(buf, s.c_str(), len - 1);
    buf[len - 1] = '\0';
}

ConfigManager::ConfigManager() {
    setDefaultConfig();
}

ConfigManager::~ConfigManager() {
    end();
}

bool ConfigManager::begin() {
    Serial.println("[Config] Initializing...");

    // 開啟 NVS 存儲
    if (!_preferences.begin("ratmonitor", false)) {
        Serial.println("[Config] Failed to open NVS");
        return false;
    }

    // 檢查是否有現有配置
    if (_preferences.isKey("configured") && _preferences.getBool("configured", false)) {
        load();
        Serial.println("[Config] Configuration loaded from NVS");
    } else {
        Serial.println("[Config] No saved config, using defaults");
        loadDefault();
        save();
    }

    printConfig();
    return true;
}

void ConfigManager::end() {
    _preferences.end();
}

bool ConfigManager::load() {
    // WiFi
    prefsGetString(_preferences,"wifi_ssid", _config.wifi_ssid, sizeof(_config.wifi_ssid), WIFI_SSID);
    prefsGetString(_preferences,"wifi_password", _config.wifi_password, sizeof(_config.wifi_password), WIFI_PASSWORD);
    prefsGetString(_preferences,"ap_ssid", _config.ap_ssid, sizeof(_config.ap_ssid), AP_SSID);
    prefsGetString(_preferences,"ap_password", _config.ap_password, sizeof(_config.ap_password), AP_PASSWORD);

    // 攝影機
    _config.framesize = _preferences.getUChar("framesize", 10);
    _config.quality = _preferences.getUChar("quality", 10);
    _config.brightness = _preferences.getChar("brightness", CAMERA_BRIGHTNESS);
    _config.contrast = _preferences.getChar("contrast", CAMERA_CONTRAST);
    _config.saturation = _preferences.getChar("saturation", CAMERA_SATURATION);

    // 運動偵測
    _config.motion_enabled = _preferences.getBool("motion_en", MOTION_DETECTION_ENABLED);
    _config.motion_sensitivity = _preferences.getUChar("motion_sen", MOTION_SENSITIVITY);
    _config.motion_cooldown_ms = _preferences.getULong("motion_cd", MOTION_COOLDOWN_MS);
    _config.motion_trigger_count = _preferences.getUChar("motion_trg", MOTION_TRIGGER_COUNT);

    // PIR
    _config.pir_enabled = _preferences.getBool("pir_en", PIR_ENABLED);
    _config.pir_pin = _preferences.getUChar("pir_pin", PIR_PIN);

    // 拍照
    _config.capture_on_motion = _preferences.getBool("cap_motion", CAPTURE_ON_MOTION);
    _config.capture_quality = _preferences.getUChar("cap_quality", CAPTURE_QUALITY);
    _config.capture_flash = _preferences.getBool("cap_flash", CAPTURE_FLASH);
    _config.capture_count = _preferences.getUChar("cap_count", CAPTURE_COUNT);

    // 紅外 LED
    _config.ir_led_enabled = _preferences.getBool("ir_en", IR_LED_ENABLED);
    _config.ir_led_duty = _preferences.getUChar("ir_duty", IR_LED_MAX_DUTY);

    // SD 卡
    _config.sd_enabled = _preferences.getBool("sd_en", SD_ENABLED);
    _config.auto_delete = _preferences.getBool("sd_autodel", SD_AUTO_DELETE);
    _config.delete_after_days = _preferences.getULong("sd_days", SD_DELETE_OLDER_DAYS);

    // 告警
    _config.alert_enabled = _preferences.getBool("alert_en", ALERT_ENABLED);
    _config.telegram_enabled = _preferences.getBool("tg_en", TELEGRAM_ENABLED);
    prefsGetString(_preferences,"tg_token", _config.telegram_token, sizeof(_config.telegram_token), TELEGRAM_BOT_TOKEN);
    prefsGetString(_preferences,"tg_chatid", _config.telegram_chat_id, sizeof(_config.telegram_chat_id), TELEGRAM_CHAT_ID);
    _config.email_enabled = _preferences.getBool("em_en", EMAIL_ENABLED);
    prefsGetString(_preferences,"em_server", _config.smtp_server, sizeof(_config.smtp_server), SMTP_SERVER);
    _config.smtp_port = _preferences.getUShort("em_port", SMTP_PORT);
    prefsGetString(_preferences,"em_sender", _config.email_sender, sizeof(_config.email_sender), EMAIL_SENDER);
    prefsGetString(_preferences,"em_pass", _config.email_password, sizeof(_config.email_password), EMAIL_PASSWORD);
    prefsGetString(_preferences,"em_recip", _config.email_recipient, sizeof(_config.email_recipient), EMAIL_RECIPIENT);
    _config.webhook_enabled = _preferences.getBool("wh_en", WEBHOOK_ENABLED);
    prefsGetString(_preferences,"wh_url", _config.webhook_url, sizeof(_config.webhook_url), WEBHOOK_URL);
    _config.alert_cooldown_ms = _preferences.getULong("alert_cd", ALERT_COOLDOWN_MS);

    // 電源
    _config.deep_sleep_enabled = _preferences.getBool("sleep_en", DEEP_SLEEP_ENABLED);
    _config.sleep_duration_us = _preferences.getULong("sleep_us", SLEEP_DURATION_US);

    // 系統
    _config.ntp_enabled = _preferences.getBool("ntp_en", NTP_ENABLED);
    _config.ntp_gmt_offset = _preferences.getChar("ntp_gmt", NTP_GMT_OFFSET);
    prefsGetString(_preferences,"sys_name", _config.system_name, sizeof(_config.system_name), SYSTEM_NAME);

    Serial.println("[Config] Configuration loaded");
    return true;
}

bool ConfigManager::save() {
    // WiFi
    _preferences.putString("wifi_ssid", _config.wifi_ssid);
    _preferences.putString("wifi_password", _config.wifi_password);
    _preferences.putString("ap_ssid", _config.ap_ssid);
    _preferences.putString("ap_password", _config.ap_password);

    // 攝影機
    _preferences.putUChar("framesize", _config.framesize);
    _preferences.putUChar("quality", _config.quality);
    _preferences.putChar("brightness", _config.brightness);
    _preferences.putChar("contrast", _config.contrast);
    _preferences.putChar("saturation", _config.saturation);

    // 運動偵測
    _preferences.putBool("motion_en", _config.motion_enabled);
    _preferences.putUChar("motion_sen", _config.motion_sensitivity);
    _preferences.putULong("motion_cd", _config.motion_cooldown_ms);
    _preferences.putUChar("motion_trg", _config.motion_trigger_count);

    // PIR
    _preferences.putBool("pir_en", _config.pir_enabled);
    _preferences.putUChar("pir_pin", _config.pir_pin);

    // 拍照
    _preferences.putBool("cap_motion", _config.capture_on_motion);
    _preferences.putUChar("cap_quality", _config.capture_quality);
    _preferences.putBool("cap_flash", _config.capture_flash);
    _preferences.putUChar("cap_count", _config.capture_count);

    // 紅外 LED
    _preferences.putBool("ir_en", _config.ir_led_enabled);
    _preferences.putUChar("ir_duty", _config.ir_led_duty);

    // SD 卡
    _preferences.putBool("sd_en", _config.sd_enabled);
    _preferences.putBool("sd_autodel", _config.auto_delete);
    _preferences.putULong("sd_days", _config.delete_after_days);

    // 告警
    _preferences.putBool("alert_en", _config.alert_enabled);
    _preferences.putBool("tg_en", _config.telegram_enabled);
    _preferences.putString("tg_token", _config.telegram_token);
    _preferences.putString("tg_chatid", _config.telegram_chat_id);
    _preferences.putBool("em_en", _config.email_enabled);
    _preferences.putString("em_server", _config.smtp_server);
    _preferences.putUShort("em_port", _config.smtp_port);
    _preferences.putString("em_sender", _config.email_sender);
    _preferences.putString("em_pass", _config.email_password);
    _preferences.putString("em_recip", _config.email_recipient);
    _preferences.putBool("wh_en", _config.webhook_enabled);
    _preferences.putString("wh_url", _config.webhook_url);
    _preferences.putULong("alert_cd", _config.alert_cooldown_ms);

    // 電源
    _preferences.putBool("sleep_en", _config.deep_sleep_enabled);
    _preferences.putULong("sleep_us", _config.sleep_duration_us);

    // 系統
    _preferences.putBool("ntp_en", _config.ntp_enabled);
    _preferences.putChar("ntp_gmt", _config.ntp_gmt_offset);
    _preferences.putString("sys_name", _config.system_name);

    _preferences.putBool("configured", true);

    Serial.println("[Config] Configuration saved");
    return true;
}

bool ConfigManager::loadDefault() {
    setDefaultConfig();
    return true;
}

void ConfigManager::printConfig() {
    Serial.println("=== System Configuration ===");
    Serial.printf("WiFi SSID: %s\n", _config.wifi_ssid);
    Serial.printf("AP SSID: %s\n", _config.ap_ssid);
    Serial.printf("Framesize: %d\n", _config.framesize);
    Serial.printf("Quality: %d\n", _config.quality);
    Serial.printf("Motion Detection: %s\n", _config.motion_enabled ? "ON" : "OFF");
    Serial.printf("PIR: %s\n", _config.pir_enabled ? "ON" : "OFF");
    Serial.printf("Capture on Motion: %s\n", _config.capture_on_motion ? "ON" : "OFF");
    Serial.printf("IR LED: %s\n", _config.ir_led_enabled ? "ON" : "OFF");
    Serial.printf("SD Card: %s\n", _config.sd_enabled ? "ON" : "OFF");
    Serial.printf("Alerts: %s / Telegram: %s\n",
                  _config.alert_enabled ? "ON" : "OFF",
                  _config.telegram_enabled ? "ON" : "OFF");
    Serial.println("==============================");
}

app_config_t* ConfigManager::getConfig() {
    return &_config;
}

bool ConfigManager::setAndSave(const char* key, const char* value) {
    if (!key || !value) return false;

    bool changed = false;

    // WiFi 設定
    if (strcmp(key, "wifi_ssid") == 0) {
        strncpy(_config.wifi_ssid, value, sizeof(_config.wifi_ssid) - 1);
        changed = true;
    } else if (strcmp(key, "wifi_password") == 0) {
        strncpy(_config.wifi_password, value, sizeof(_config.wifi_password) - 1);
        changed = true;
    } else if (strcmp(key, "ap_ssid") == 0) {
        strncpy(_config.ap_ssid, value, sizeof(_config.ap_ssid) - 1);
        changed = true;
    } else if (strcmp(key, "ap_password") == 0) {
        strncpy(_config.ap_password, value, sizeof(_config.ap_password) - 1);
        changed = true;

    // 攝影機設定
    } else if (strcmp(key, "framesize") == 0) {
        _config.framesize = (uint8_t)atoi(value);
        changed = true;
    } else if (strcmp(key, "quality") == 0) {
        _config.quality = (uint8_t)atoi(value);
        changed = true;
    } else if (strcmp(key, "brightness") == 0) {
        _config.brightness = (int8_t)atoi(value);
        changed = true;
    } else if (strcmp(key, "contrast") == 0) {
        _config.contrast = (int8_t)atoi(value);
        changed = true;
    } else if (strcmp(key, "saturation") == 0) {
        _config.saturation = (int8_t)atoi(value);
        changed = true;

    // 運動偵測設定
    } else if (strcmp(key, "motion_enabled") == 0) {
        _config.motion_enabled = (strcmp(value, "1") == 0 || strcmp(value, "true") == 0);
        changed = true;
    } else if (strcmp(key, "motion_sensitivity") == 0) {
        _config.motion_sensitivity = (uint8_t)atoi(value);
        changed = true;
    } else if (strcmp(key, "motion_cooldown") == 0) {
        _config.motion_cooldown_ms = atol(value);
        changed = true;
    } else if (strcmp(key, "motion_trigger_count") == 0) {
        _config.motion_trigger_count = (uint8_t)atoi(value);
        changed = true;

    // PIR 設定
    } else if (strcmp(key, "pir_enabled") == 0) {
        _config.pir_enabled = (strcmp(value, "1") == 0 || strcmp(value, "true") == 0);
        changed = true;
    } else if (strcmp(key, "pir_pin") == 0) {
        _config.pir_pin = (uint8_t)atoi(value);
        changed = true;

    // 拍照設定
    } else if (strcmp(key, "capture_on_motion") == 0) {
        _config.capture_on_motion = (strcmp(value, "1") == 0 || strcmp(value, "true") == 0);
        changed = true;
    } else if (strcmp(key, "capture_quality") == 0) {
        _config.capture_quality = (uint8_t)atoi(value);
        changed = true;
    } else if (strcmp(key, "capture_flash") == 0) {
        _config.capture_flash = (strcmp(value, "1") == 0 || strcmp(value, "true") == 0);
        changed = true;
    } else if (strcmp(key, "capture_count") == 0) {
        _config.capture_count = (uint8_t)atoi(value);
        changed = true;

    // 紅外 LED
    } else if (strcmp(key, "ir_led_enabled") == 0) {
        _config.ir_led_enabled = (strcmp(value, "1") == 0 || strcmp(value, "true") == 0);
        changed = true;
    } else if (strcmp(key, "ir_led_duty") == 0) {
        _config.ir_led_duty = (uint8_t)atoi(value);
        changed = true;

    // SD 卡
    } else if (strcmp(key, "sd_enabled") == 0) {
        _config.sd_enabled = (strcmp(value, "1") == 0 || strcmp(value, "true") == 0);
        changed = true;
    } else if (strcmp(key, "auto_delete") == 0) {
        _config.auto_delete = (strcmp(value, "1") == 0 || strcmp(value, "true") == 0);
        changed = true;
    } else if (strcmp(key, "delete_after_days") == 0) {
        _config.delete_after_days = atol(value);
        changed = true;

    // 告警設定
    } else if (strcmp(key, "alert_enabled") == 0) {
        _config.alert_enabled = (strcmp(value, "1") == 0 || strcmp(value, "true") == 0);
        changed = true;
    } else if (strcmp(key, "telegram_enabled") == 0) {
        _config.telegram_enabled = (strcmp(value, "1") == 0 || strcmp(value, "true") == 0);
        changed = true;
    } else if (strcmp(key, "telegram_token") == 0) {
        strncpy(_config.telegram_token, value, sizeof(_config.telegram_token) - 1);
        changed = true;
    } else if (strcmp(key, "telegram_chat_id") == 0) {
        strncpy(_config.telegram_chat_id, value, sizeof(_config.telegram_chat_id) - 1);
        changed = true;
    } else if (strcmp(key, "email_enabled") == 0) {
        _config.email_enabled = (strcmp(value, "1") == 0 || strcmp(value, "true") == 0);
        changed = true;
    } else if (strcmp(key, "smtp_server") == 0) {
        strncpy(_config.smtp_server, value, sizeof(_config.smtp_server) - 1);
        changed = true;
    } else if (strcmp(key, "smtp_port") == 0) {
        _config.smtp_port = (uint16_t)atoi(value);
        changed = true;
    } else if (strcmp(key, "email_sender") == 0) {
        strncpy(_config.email_sender, value, sizeof(_config.email_sender) - 1);
        changed = true;
    } else if (strcmp(key, "email_password") == 0) {
        strncpy(_config.email_password, value, sizeof(_config.email_password) - 1);
        changed = true;
    } else if (strcmp(key, "email_recipient") == 0) {
        strncpy(_config.email_recipient, value, sizeof(_config.email_recipient) - 1);
        changed = true;
    } else if (strcmp(key, "webhook_enabled") == 0) {
        _config.webhook_enabled = (strcmp(value, "1") == 0 || strcmp(value, "true") == 0);
        changed = true;
    } else if (strcmp(key, "webhook_url") == 0) {
        strncpy(_config.webhook_url, value, sizeof(_config.webhook_url) - 1);
        changed = true;
    } else if (strcmp(key, "alert_cooldown") == 0) {
        _config.alert_cooldown_ms = atol(value);
        changed = true;

    // 電源管理
    } else if (strcmp(key, "deep_sleep_enabled") == 0) {
        _config.deep_sleep_enabled = (strcmp(value, "1") == 0 || strcmp(value, "true") == 0);
        changed = true;
    } else if (strcmp(key, "sleep_duration") == 0) {
        _config.sleep_duration_us = atoll(value);
        changed = true;

    // 系統設定
    } else if (strcmp(key, "ntp_enabled") == 0) {
        _config.ntp_enabled = (strcmp(value, "1") == 0 || strcmp(value, "true") == 0);
        changed = true;
    } else if (strcmp(key, "ntp_gmt_offset") == 0) {
        _config.ntp_gmt_offset = (int8_t)atoi(value);
        changed = true;
    } else if (strcmp(key, "system_name") == 0) {
        strncpy(_config.system_name, value, sizeof(_config.system_name) - 1);
        changed = true;
    }

    if (changed) {
        return save();
    }

    return false;
}

String ConfigManager::get(const char* key) {
    if (strcmp(key, "wifi_ssid") == 0) return _config.wifi_ssid;
    if (strcmp(key, "wifi_password") == 0) return _config.wifi_password;
    if (strcmp(key, "framesize") == 0) return String(_config.framesize);
    if (strcmp(key, "quality") == 0) return String(_config.quality);
    if (strcmp(key, "motion_enabled") == 0) return String(_config.motion_enabled ? 1 : 0);
    if (strcmp(key, "motion_sensitivity") == 0) return String(_config.motion_sensitivity);
    if (strcmp(key, "telegram_enabled") == 0) return String(_config.telegram_enabled ? 1 : 0);
    if (strcmp(key, "telegram_token") == 0) return _config.telegram_token;
    if (strcmp(key, "telegram_chat_id") == 0) return _config.telegram_chat_id;
    if (strcmp(key, "email_enabled") == 0) return String(_config.email_enabled ? 1 : 0);
    if (strcmp(key, "alert_enabled") == 0) return String(_config.alert_enabled ? 1 : 0);
    if (strcmp(key, "sd_enabled") == 0) return String(_config.sd_enabled ? 1 : 0);
    if (strcmp(key, "ntp_enabled") == 0) return String(_config.ntp_enabled ? 1 : 0);

    return String("");
}

void ConfigManager::resetAll() {
    _preferences.clear();
    setDefaultConfig();
    save();
    Serial.println("[Config] All settings reset to defaults");
}

bool ConfigManager::validate() {
    bool valid = true;

    // 驗證 WiFi 設定
    if (strlen(_config.wifi_ssid) == 0) {
        Serial.println("[Config] Invalid: WiFi SSID is empty");
        valid = false;
    }

    // 驗證 Telegram 設定
    if (_config.telegram_enabled &&
        (strlen(_config.telegram_token) == 0 ||
         strcmp(_config.telegram_token, "YOUR_BOT_TOKEN_HERE") == 0)) {
        Serial.println("[Config] Invalid: Telegram token not configured");
        valid = false;
    }

    return valid;
}

bool ConfigManager::isValidWifiConfig() const {
    return strlen(_config.wifi_ssid) > 0;
}

bool ConfigManager::isConfigured() {
    return _preferences.getBool("configured", false);
}

void ConfigManager::setDefaultConfig() {
    // WiFi
    strncpy(_config.wifi_ssid, WIFI_SSID, sizeof(_config.wifi_ssid) - 1);
    strncpy(_config.wifi_password, WIFI_PASSWORD, sizeof(_config.wifi_password) - 1);
    strncpy(_config.ap_ssid, AP_SSID, sizeof(_config.ap_ssid) - 1);
    strncpy(_config.ap_password, AP_PASSWORD, sizeof(_config.ap_password) - 1);

    // 攝影機
    _config.framesize = 10;  // FRAMESIZE_VGA
    _config.quality = 10;
    _config.brightness = CAMERA_BRIGHTNESS;
    _config.contrast = CAMERA_CONTRAST;
    _config.saturation = CAMERA_SATURATION;

    // 運動偵測
    _config.motion_enabled = MOTION_DETECTION_ENABLED;
    _config.motion_sensitivity = MOTION_SENSITIVITY;
    _config.motion_cooldown_ms = MOTION_COOLDOWN_MS;
    _config.motion_trigger_count = MOTION_TRIGGER_COUNT;

    // PIR
    _config.pir_enabled = PIR_ENABLED;
    _config.pir_pin = PIR_PIN;

    // 拍照
    _config.capture_on_motion = CAPTURE_ON_MOTION;
    _config.capture_quality = CAPTURE_QUALITY;
    _config.capture_flash = CAPTURE_FLASH;
    _config.capture_count = CAPTURE_COUNT;

    // 紅外 LED
    _config.ir_led_enabled = IR_LED_ENABLED;
    _config.ir_led_duty = IR_LED_MAX_DUTY;

    // SD 卡
    _config.sd_enabled = SD_ENABLED;
    _config.auto_delete = SD_AUTO_DELETE;
    _config.delete_after_days = SD_DELETE_OLDER_DAYS;

    // 告警
    _config.alert_enabled = ALERT_ENABLED;
    _config.telegram_enabled = TELEGRAM_ENABLED;
    strncpy(_config.telegram_token, TELEGRAM_BOT_TOKEN, sizeof(_config.telegram_token) - 1);
    strncpy(_config.telegram_chat_id, TELEGRAM_CHAT_ID, sizeof(_config.telegram_chat_id) - 1);
    _config.email_enabled = EMAIL_ENABLED;
    strncpy(_config.smtp_server, SMTP_SERVER, sizeof(_config.smtp_server) - 1);
    _config.smtp_port = SMTP_PORT;
    strncpy(_config.email_sender, EMAIL_SENDER, sizeof(_config.email_sender) - 1);
    strncpy(_config.email_password, EMAIL_PASSWORD, sizeof(_config.email_password) - 1);
    strncpy(_config.email_recipient, EMAIL_RECIPIENT, sizeof(_config.email_recipient) - 1);
    _config.webhook_enabled = WEBHOOK_ENABLED;
    strncpy(_config.webhook_url, WEBHOOK_URL, sizeof(_config.webhook_url) - 1);
    _config.alert_cooldown_ms = ALERT_COOLDOWN_MS;

    // 電源
    _config.deep_sleep_enabled = DEEP_SLEEP_ENABLED;
    _config.sleep_duration_us = SLEEP_DURATION_US;

    // 系統
    _config.ntp_enabled = NTP_ENABLED;
    _config.ntp_gmt_offset = NTP_GMT_OFFSET;
    strncpy(_config.system_name, SYSTEM_NAME, sizeof(_config.system_name) - 1);
}
