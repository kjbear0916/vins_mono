#include "event_logger.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

EventLogger::EventLogger()
    : _events(NULL)
    , _max_entries(100)
    , _count(0)
    , _head(0)
    , _callback(NULL)
    , _motion_events(0)
    , _error_events(0)
    , _alert_events(0) {
}

EventLogger::~EventLogger() {
    end();
}

void EventLogger::begin(uint16_t max_entries) {
    end();  // 清理舊資料
    
    _max_entries = max_entries;
    _events = (event_record_t*)calloc(max_entries, sizeof(event_record_t));
    
    if (!_events) {
        Serial.println("[EventLog] Failed to allocate memory");
        _max_entries = 0;
        return;
    }
    
    _count = 0;
    _head = 0;
    
    Serial.printf("[EventLog] Initialized: %d entries\n", _max_entries);
    
    logInfo(EVENT_SYSTEM_START, "Event logger initialized");
}

void EventLogger::end() {
    if (_events) {
        free(_events);
        _events = NULL;
        _max_entries = 0;
        _count = 0;
    }
}

void EventLogger::logInfo(event_type_t type, const char* description) {
    log(type, description, 0);
}

void EventLogger::logWarning(event_type_t type, const char* description) {
    log(type, description, 1);
}

void EventLogger::logError(event_type_t type, const char* description) {
    log(type, description, 2);
}

void EventLogger::log(event_type_t type, const char* description, uint16_t level) {
    if (!_events || !description) return;
    
    event_record_t record;
    memset(&record, 0, sizeof(record));
    
    record.type = type;
    record.timestamp = millis();
    record.level = level;
    strncpy(record.description, description, sizeof(record.description) - 1);
    
    // 統計
    switch (type) {
        case EVENT_MOTION_DETECTED:
            _motion_events++;
            break;
        case EVENT_SYSTEM_ERROR:
            _error_events++;
            break;
        case EVENT_ALERT_SENT:
            _alert_events++;
            break;
        default:
            break;
    }
    
    if (level == 2) _error_events++;
    
    // 序列化輸出
    Serial.printf("[Event:%d|%d] %s\n", 
                  eventTypeToString(type), level, description);
    
    addEvent(&record);
}

void EventLogger::addEvent(const event_record_t* record) {
    if (!_events) return;
    
    uint16_t index;
    
    if (_count < _max_entries) {
        index = _count;
        _count++;
    } else {
        index = _head;
        _head = (_head + 1) % _max_entries;
    }
    
    _events[index] = *record;
    
    // 觸發回呼
    if (_callback) {
        _callback(record);
    }
}

uint16_t EventLogger::getEventCount() const {
    return _count;
}

bool EventLogger::getEvent(uint16_t index, event_record_t* record) {
    if (!_events || index >= _count || !record) return false;
    
    uint16_t actual = (_head + index) % _max_entries;
    *record = _events[actual];
    return true;
}

void EventLogger::clearEvents() {
    if (_events) {
        memset(_events, 0, _max_entries * sizeof(event_record_t));
    }
    _count = 0;
    _head = 0;
    _motion_events = 0;
    _error_events = 0;
    _alert_events = 0;
    
    logInfo(EVENT_USER_ACTION, "Event log cleared");
}

bool EventLogger::exportToJSON(char* buffer, size_t max_len) {
    if (!buffer || max_len == 0) return false;
    
    size_t pos = 0;
    
    pos += snprintf(buffer + pos, max_len - pos, "{\"events\":[");
    
    for (uint16_t i = 0; i < _count; i++) {
        event_record_t record;
        if (getEvent(i, &record)) {
            pos += snprintf(buffer + pos, max_len - pos,
                "%s{\"type\":%d,\"ts\":%lu,\"level\":%d,\"desc\":\"%s\"}",
                (i > 0) ? "," : "",
                record.type, record.timestamp, record.level, record.description);
        }
    }
    
    pos += snprintf(buffer + pos, max_len - pos, "]");
    
    // 加入統計
    pos += snprintf(buffer + pos, max_len - pos,
        ",\"stats\":{\"total\":%u,\"motion\":%lu,\"errors\":%lu,\"alerts\":%lu}",
        _count, _motion_events, _error_events, _alert_events);
    
    pos += snprintf(buffer + pos, max_len - pos, "}");
    
    return pos > 0;
}

size_t EventLogger::exportToCSV(char* buffer, size_t max_len) {
    if (!buffer || max_len == 0) return 0;
    
    size_t pos = 0;
    
    pos += snprintf(buffer + pos, max_len - pos, "type,timestamp,level,description\n");
    
    for (uint16_t i = 0; i < _count; i++) {
        event_record_t record;
        if (getEvent(i, &record)) {
            pos += snprintf(buffer + pos, max_len - pos,
                "%d,%lu,%d,\"%s\"\n",
                record.type, record.timestamp, record.level, record.description);
        }
    }
    
    return pos;
}

void EventLogger::onEvent(event_callback_t callback) {
    _callback = callback;
}

uint32_t EventLogger::getMotionEvents() const { return _motion_events; }
uint32_t EventLogger::getErrorEvents() const { return _error_events; }
uint32_t EventLogger::getAlertEvents() const { return _alert_events; }
uint32_t EventLogger::getTotalEvents() const { return _count; }

const char* EventLogger::eventTypeToString(event_type_t type) {
    switch (type) {
        case EVENT_SYSTEM_START:      return "SYSTEM_START";
        case EVENT_MOTION_DETECTED:   return "MOTION_DETECTED";
        case EVENT_IMAGE_CAPTURED:    return "IMAGE_CAPTURED";
        case EVENT_ALERT_SENT:        return "ALERT_SENT";
        case EVENT_WIFI_CONNECTED:    return "WIFI_CONNECTED";
        case EVENT_WIFI_DISCONNECTED: return "WIFI_DISCONNECTED";
        case EVENT_SD_MOUNTED:        return "SD_MOUNTED";
        case EVENT_SD_ERROR:          return "SD_ERROR";
        case EVENT_NTP_SYNC:          return "NTP_SYNC";
        case EVENT_SYSTEM_ERROR:      return "SYSTEM_ERROR";
        case EVENT_USER_ACTION:       return "USER_ACTION";
        default:                      return "OTHER";
    }
}

const char* EventLogger::levelToString(uint16_t level) {
    switch (level) {
        case 0: return "INFO";
        case 1: return "WARN";
        case 2: return "ERROR";
        default: return "UNKNOWN";
    }
}
