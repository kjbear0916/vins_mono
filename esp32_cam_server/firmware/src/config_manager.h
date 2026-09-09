#ifndef CONFIG_MANAGER_H
#define CONFIG_MANAGER_H

#include <Arduino.h>
#include <Preferences.h>

// 應用程式配置結構
typedef struct {
    // WiFi
    char wifi_ssid[32];
    char wifi_password[64];
    char ap_ssid[32];
    char ap_password[32];

    // 攝影機
    uint8_t framesize;
    uint8_t quality;
    int8_t brightness;
    int8_t contrast;
    int8_t saturation;

    // 運動偵測
    bool motion_enabled;
    uint8_t motion_sensitivity;
    uint32_t motion_cooldown_ms;
    uint8_t motion_trigger_count;

    // PIR
    bool pir_enabled;
    uint8_t pir_pin;

    // 拍照
    bool capture_on_motion;
    uint8_t capture_quality;
    bool capture_flash;
    uint8_t capture_count;

    // 紅外補光
    bool ir_led_enabled;
    uint8_t ir_led_duty;

    // SD 卡
    bool sd_enabled;
    bool auto_delete;
    uint32_t delete_after_days;

    // 告警
    bool alert_enabled;
    bool telegram_enabled;
    char telegram_token[64];
    char telegram_chat_id[32];
    bool email_enabled;
    char smtp_server[64];
    uint16_t smtp_port;
    char email_sender[64];
    char email_password[64];
    char email_recipient[64];
    bool webhook_enabled;
    char webhook_url[256];
    uint32_t alert_cooldown_ms;

    // 電源
    bool deep_sleep_enabled;
    uint32_t sleep_duration_us;

    // 系統
    bool ntp_enabled;
    int8_t ntp_gmt_offset;
    char system_name[32];
} app_config_t;

class ConfigManager {
public:
    ConfigManager();
    ~ConfigManager();

    // 初始化
    bool begin();
    void end();

    // 載入/儲存
    bool load();
    bool save();
    bool loadDefault();
    void printConfig();

    // 取得/設定
    app_config_t* getConfig();
    
    // 單項設定
    bool setAndSave(const char* key, const char* value);
    String get(const char* key);

    // 重置
    void resetAll();

    // 驗證
    bool validate();
    bool isValidWifiConfig() const;
    bool isConfigured();

private:
    app_config_t _config;
    Preferences _preferences;
    
    // 序反
    void serialize(char* buffer, size_t max_len);
    bool deserialize(const char* buffer);
    void setDefaultConfig();
};

#endif // CONFIG_MANAGER_H
