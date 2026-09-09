#ifndef EVENT_LOGGER_H
#define EVENT_LOGGER_H

#include <Arduino.h>

// 事件類型
typedef enum {
    EVENT_SYSTEM_START,
    EVENT_MOTION_DETECTED,
    EVENT_IMAGE_CAPTURED,
    EVENT_ALERT_SENT,
    EVENT_WIFI_CONNECTED,
    EVENT_WIFI_DISCONNECTED,
    EVENT_SD_MOUNTED,
    EVENT_SD_ERROR,
    EVENT_NTP_SYNC,
    EVENT_SYSTEM_ERROR,
    EVENT_USER_ACTION,
    EVENT_OTHER
} event_type_t;

// 事件記錄
typedef struct {
    event_type_t type;
    uint32_t timestamp;
    uint16_t level;    // 0=INFO, 1=WARN, 2=ERROR
    char description[256];
    uint8_t extra_data[32];
    uint8_t extra_size;
} event_record_t;

// 事件日誌回呼
typedef void (*event_callback_t)(const event_record_t* record);

class EventLogger {
public:
    EventLogger();
    ~EventLogger();

    // 初始化
    void begin(uint16_t max_entries = 100);
    void end();

    // 記錄事件
    void log(event_type_t type, const char* description, uint16_t level = 0);
    void logError(event_type_t type, const char* description);
    void logWarning(event_type_t type, const char* description);
    void logInfo(event_type_t type, const char* description);

    // 事件列表
    uint16_t getEventCount() const;
    bool getEvent(uint16_t index, event_record_t* record);
    void clearEvents();

    // 匯出
    bool exportToJSON(char* buffer, size_t max_len);
    size_t exportToCSV(char* buffer, size_t max_len);

    // 回呼
    void onEvent(event_callback_t callback);

    // 統計
    uint32_t getMotionEvents() const;
    uint32_t getErrorEvents() const;
    uint32_t getAlertEvents() const;
    uint32_t getTotalEvents() const;

    // 序列化
    static const char* eventTypeToString(event_type_t type);
    static const char* levelToString(uint16_t level);

private:
    event_record_t* _events;
    uint16_t _max_entries;
    uint16_t _count;
    uint16_t _head;
    event_callback_t _callback;
    
    uint32_t _motion_events;
    uint32_t _error_events;
    uint32_t _alert_events;

    // 內部方法
    void addEvent(const event_record_t* record);
    const char* getEventDescription(event_type_t type) const;
};

#endif // EVENT_LOGGER_H
