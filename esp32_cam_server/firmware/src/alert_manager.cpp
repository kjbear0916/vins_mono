#include "alert_manager.h"
#include "config/config.h"
#include <WiFiClientSecure.h>

// Telegram API 端點
#define TELEGRAM_API "https://api.telegram.org/bot%s"

AlertManager::AlertManager()
    : _enabled(ALERT_ENABLED)
    , _cooldown_ms(ALERT_COOLDOWN_MS)
    , _last_alert_time(0)
    , _alert_count(0)
    , _callback(NULL)
    , _telegram_enabled(TELEGRAM_ENABLED)
    , _telegram_token(TELEGRAM_BOT_TOKEN)
    , _telegram_chat_id(TELEGRAM_CHAT_ID)
    , _email_enabled(EMAIL_ENABLED)
    , _smtp_server(SMTP_SERVER)
    , _smtp_port(SMTP_PORT)
    , _smtp_username(EMAIL_SENDER)
    , _smtp_password(EMAIL_PASSWORD)
    , _email_recipient(EMAIL_RECIPIENT)
    , _webhook_enabled(WEBHOOK_ENABLED)
    , _webhook_url(WEBHOOK_URL) {
}

AlertManager::~AlertManager() {
}

bool AlertManager::begin() {
    Serial.println("[Alert] Alert Manager initialized");
    
    if (_telegram_enabled) {
        Serial.printf("[Alert] Telegram: token=%s, chat_id=%s\n", 
                      _telegram_token.c_str(), _telegram_chat_id.c_str());
    }
    
    if (_email_enabled) {
        Serial.printf("[Alert] Email: server=%s:%d, to=%s\n", 
                      _smtp_server.c_str(), _smtp_port, _email_recipient.c_str());
    }
    
    if (_webhook_enabled) {
        Serial.printf("[Alert] Webhook: %s\n", _webhook_url.c_str());
    }
    
    return true;
}

bool AlertManager::sendAlert(alert_type_t type, const char* title, const char* message) {
    return sendAlertWithImage(type, title, message, NULL, 0);
}

bool AlertManager::sendAlertWithImage(alert_type_t type, const char* title, const char* message,
                                     uint8_t* image_data, size_t image_length) {
    if (!_enabled) {
        Serial.println("[Alert] Alerts disabled");
        return false;
    }

    if (!checkCooldown()) {
        Serial.println("[Alert] Alert cooldown active, skipped");
        return false;
    }
    
    Serial.printf("[Alert] Sending alert: %s - %s\n", title, message);
    
    bool success = false;
    
    // 發送到所有啟用的通道
    if (_telegram_enabled) {
        if (image_data && image_length > 0) {
            success |= sendTelegramPhoto(image_data, image_length, message);
        } else {
            success |= sendTelegram(message);
        }
    }
    
    if (_email_enabled) {
        if (image_data && image_length > 0) {
            success |= sendEmailWithAttachment(title, message, image_data, image_length);
        } else {
            success |= sendEmail(title, message);
        }
    }
    
    if (_webhook_enabled) {
        success |= sendWebhook(message, image_data, image_length);
    }
    
    _last_alert_time = millis();
    _alert_count++;
    
    return success;
}

bool AlertManager::sendTelegram(const char* message) {
    if (!_telegram_enabled) return false;
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("[Alert] WiFi not connected");
        return false;
    }
    
    Serial.println("[Alert] Sending Telegram message...");
    
    // 建構 API URL
    char url[512];
    snprintf(url, sizeof(url), TELEGRAM_API, _telegram_token.c_str());
    
    // 建構 POST body
    String body = "chat_id=" + _telegram_chat_id + "&text=" + String(message);
    
    // URL 編碼訊息
    body.replace(" ", "%20");
    body.replace("\n", "%0A");
    body.replace("&", "%26");
    
    _http.begin(url);
    _http.addHeader("Content-Type", "application/x-www-form-urlencoded");
    
    int http_code = _http.POST(body);
    
    if (http_code == HTTP_CODE_OK) {
        Serial.println("[Alert] Telegram message sent successfully");
        _http.end();
        return true;
    } else {
        Serial.printf("[Alert] Telegram send failed: HTTP %d\n", http_code);
        _http.end();
        return false;
    }
}

bool AlertManager::sendTelegramPhoto(uint8_t* image_data, size_t image_length, const char* caption) {
    if (!_telegram_enabled) return false;
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("[Alert] WiFi not connected");
        return false;
    }
    
    Serial.println("[Alert] Sending Telegram photo...");
    
    // 建構 API URL
    char url[512];
    snprintf(url, sizeof(url), TELEGRAM_API "/sendPhoto", _telegram_token.c_str());
    
    // 使用 multipart/form-data
    String boundary = "----ESP32Boundary";
    String body;
    
    // chat_id
    body += "--" + boundary + "\r\n";
    body += "Content-Disposition: form-data; name=\"chat_id\"\r\n\r\n";
    body += _telegram_chat_id + "\r\n";
    
    // caption
    body += "--" + boundary + "\r\n";
    body += "Content-Disposition: form-data; name=\"caption\"\r\n\r\n";
    body += String(caption) + "\r\n";
    
    // photo
    body += "--" + boundary + "\r\n";
    body += "Content-Disposition: form-data; name=\"photo\"; filename=\"capture.jpg\"\r\n";
    body += "Content-Type: image/jpeg\r\n\r\n";
    
    // 建構完整 body
    String full_body = body;
    
    _http.begin(url);
    _http.addHeader("Content-Type", "multipart/form-data; boundary=" + boundary);
    
    // 計算總長度
    size_t body_len = body.length() + image_length + boundary.length() + 6;
    
    Serial.printf("[Alert] Sending %d bytes photo\n", image_length);
    
    int http_code = _http.POST(body);
    
    if (http_code == HTTP_CODE_OK) {
        Serial.println("[Alert] Telegram photo sent successfully");
        _http.end();
        return true;
    } else {
        Serial.printf("[Alert] Telegram photo send failed: HTTP %d\n", http_code);
        _http.end();
        return false;
    }
}

bool AlertManager::sendEmail(const char* subject, const char* body) {
    if (!_email_enabled) return false;
    
    Serial.printf("[Alert] Email sending not available for %s\n", subject);
    Serial.println("[Alert] Email requires SMTP client library (ESP-Mail-Client)");
    
    // TODO: 使用 ESP-Mail-Client 庫實現完整 SMTP 功能
    // 需要安裝 ESP-Mail-Client 庫
    return false;
}

bool AlertManager::sendEmailWithAttachment(const char* subject, const char* body,
                                         uint8_t* image_data, size_t image_length) {
    if (!_email_enabled) return false;
    
    Serial.printf("[Alert] Email with attachment not available for %s\n", subject);
    Serial.println("[Alert] Email requires SMTP client library (ESP-Mail-Client)");
    
    // TODO: 使用 ESP-Mail-Client 庫實現完整 SMTP 功能
    return false;
}

bool AlertManager::sendWebhook(const char* message, uint8_t* image_data, size_t image_length) {
    if (!_webhook_enabled) return false;
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("[Alert] WiFi not connected");
        return false;
    }
    
    Serial.println("[Alert] Sending webhook...");
    
    // 建構 JSON payload
    String json = "{\"message\":\"";
    json += message;
    json += "\",\"timestamp\":";
    json += millis();
    json += ",\"motion_count\":";
    json += _alert_count;
    json += "}";
    
    _http.begin(_webhook_url);
    _http.addHeader("Content-Type", "application/json");
    _http.addHeader("X-ESP32-ID", SYSTEM_NAME);
    
    int http_code = _http.POST(json);
    
    if (http_code == HTTP_CODE_OK || http_code == HTTP_CODE_ACCEPTED) {
        Serial.println("[Alert] Webhook sent successfully");
        _http.end();
        return true;
    } else {
        Serial.printf("[Alert] Webhook send failed: HTTP %d\n", http_code);
        _http.end();
        return false;
    }
}

void AlertManager::setTelegramConfig(const char* token, const char* chat_id) {
    _telegram_token = token;
    _telegram_chat_id = chat_id;
    _telegram_enabled = (strlen(token) > 0 && strcmp(token, "YOUR_BOT_TOKEN_HERE") != 0);
    Serial.printf("[Alert] Telegram config updated: enabled=%d\n", _telegram_enabled);
}

void AlertManager::setEmailConfig(const char* server, uint16_t port, const char* username,
                                 const char* password, const char* recipient) {
    _smtp_server = server;
    _smtp_port = port;
    _smtp_username = username;
    _smtp_password = password;
    _email_recipient = recipient;
    _email_enabled = (strlen(server) > 0 && strlen(username) > 0);
    Serial.printf("[Alert] Email config updated: enabled=%d\n", _email_enabled);
}

void AlertManager::setWebhookConfig(const char* url) {
    _webhook_url = url;
    _webhook_enabled = (strlen(url) > 0);
    Serial.printf("[Alert] Webhook config updated: enabled=%d\n", _webhook_enabled);
}

void AlertManager::setCooldownPeriod(uint32_t cooldown_ms) {
    _cooldown_ms = cooldown_ms;
}

void AlertManager::enableChannel(alert_channel_t channel, bool enable) {
    switch (channel) {
        case ALERT_CHANNEL_TELEGRAM:
            _telegram_enabled = enable;
            break;
        case ALERT_CHANNEL_EMAIL:
            _email_enabled = enable;
            break;
        case ALERT_CHANNEL_WEBHOOK:
            _webhook_enabled = enable;
            break;
        default:
            break;
    }
}

bool AlertManager::isEnabled() const {
    return _enabled;
}

bool AlertManager::isTelegramEnabled() const {
    return _telegram_enabled;
}

bool AlertManager::isEmailEnabled() const {
    return _email_enabled;
}

bool AlertManager::isWebhookEnabled() const {
    return _webhook_enabled;
}

uint32_t AlertManager::getAlertCount() const {
    return _alert_count;
}

uint32_t AlertManager::getLastAlertTime() const {
    return _last_alert_time;
}

void AlertManager::onAlert(alert_callback_t callback) {
    _callback = callback;
}

bool AlertManager::testTelegram() {
    return sendTelegram("✅ 測試成功！鼠患智能監控系統已連線。");
}

bool AlertManager::testEmail() {
    return sendEmail("測試郵件 - 鼠患智能監控系統", "這是一封測試郵件。");
}

bool AlertManager::testWebhook() {
    return sendWebhook("測試 Webhook - 鼠患智能監控系統");
}

bool AlertManager::checkCooldown() {
    return (millis() - _last_alert_time) >= _cooldown_ms;
}
