#ifndef ALERT_MANAGER_H
#define ALERT_MANAGER_H

#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>

// 告警類型
typedef enum {
    ALERT_TYPE_MOTION,
    ALERT_TYPE_CAPTURE,
    ALERT_TYPE_TEMPERATURE,
    ALERT_TYPE_HEARTBEAT,
    ALERT_TYPE_ERROR
} alert_type_t;

// 告警通道
typedef enum {
    ALERT_CHANNEL_TELEGRAM,
    ALERT_CHANNEL_EMAIL,
    ALERT_CHANNEL_WEBHOOK,
    ALERT_CHANNEL_NONE
} alert_channel_t;

// 告警訊息
typedef struct {
    alert_type_t type;
    alert_channel_t channel;
    const char* title;
    const char* message;
    uint8_t* image_data;
    size_t image_length;
    uint32_t timestamp;
} alert_message_t;

// 回呼函數類型
typedef void (*alert_callback_t)(alert_message_t* message);

class AlertManager {
public:
    AlertManager();
    ~AlertManager();

    // 初始化
    bool begin();
    
    // 告警功能
    bool sendAlert(alert_type_t type, const char* title, const char* message);
    bool sendAlertWithImage(alert_type_t type, const char* title, const char* message,
                           uint8_t* image_data, size_t image_length);
    
    // Telegram
    bool sendTelegram(const char* message);
    bool sendTelegramPhoto(uint8_t* image_data, size_t image_length, const char* caption);

    // Email
    bool sendEmail(const char* subject, const char* body);
    bool sendEmailWithAttachment(const char* subject, const char* body,
                                uint8_t* image_data, size_t image_length);

    // Webhook
    bool sendWebhook(const char* message, uint8_t* image_data = NULL, size_t image_length = 0);

    // 設定
    void setTelegramConfig(const char* token, const char* chat_id);
    void setEmailConfig(const char* server, uint16_t port, const char* username, 
                       const char* password, const char* recipient);
    void setWebhookConfig(const char* url);
    void setCooldownPeriod(uint32_t cooldown_ms);
    void enableChannel(alert_channel_t channel, bool enable);

    // 狀態
    bool isEnabled() const;
    bool isTelegramEnabled() const;
    bool isEmailEnabled() const;
    bool isWebhookEnabled() const;
    uint32_t getAlertCount() const;
    uint32_t getLastAlertTime() const;

    // 回呼
    void onAlert(alert_callback_t callback);

    // 測試
    bool testTelegram();
    bool testEmail();
    bool testWebhook();

private:
    bool _enabled;
    uint32_t _cooldown_ms;
    uint32_t _last_alert_time;
    uint32_t _alert_count;
    alert_callback_t _callback;

    // Telegram 設定
    bool _telegram_enabled;
    String _telegram_token;
    String _telegram_chat_id;

    // Email 設定
    bool _email_enabled;
    String _smtp_server;
    uint16_t _smtp_port;
    String _smtp_username;
    String _smtp_password;
    String _email_recipient;

    // Webhook 設定
    bool _webhook_enabled;
    String _webhook_url;

    // 內部方法
    bool checkCooldown();
    HTTPClient _http;
};

#endif // ALERT_MANAGER_H
