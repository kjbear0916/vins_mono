#include "motion_detector.h"
#include "config/config.h"

MotionDetector::MotionDetector() 
    : _state(MOTION_STATE_IDLE)
    , _sensitivity(50)
    , _cooldown_ms(5000)
    , _min_area(100)
    , _diff_threshold(30)
    , _trigger_count(3)
    , _current_trigger_count(0)
    , _last_motion_time(0)
    , _motion_count(0)
    , _pir_enabled(PIR_ENABLED)
    , _previous_frame(NULL)
    , _callback(NULL) {
}

MotionDetector::~MotionDetector() {
    if (_previous_frame) {
        esp_camera_fb_return(_previous_frame);
        _previous_frame = NULL;
    }
}

bool MotionDetector::begin(uint8_t sensitivity, uint32_t cooldown_ms) {
    _sensitivity = sensitivity;
    _cooldown_ms = cooldown_ms;

    // 初始化 PIR 感測器
    if (_pir_enabled) {
        pinMode(PIR_PIN, INPUT);
        Serial.println("[Motion] PIR sensor initialized");
    }

    Serial.printf("[Motion] Initialized: sensitivity=%d, cooldown=%lu ms\n", 
                  _sensitivity, _cooldown_ms);
    return true;
}

bool MotionDetector::update() {
    // 檢查冷卻時間
    if (_state == MOTION_STATE_COOLDOWN) {
        if (millis() - _last_motion_time >= _cooldown_ms) {
            _state = MOTION_STATE_IDLE;
            _current_trigger_count = 0;
        }
        return false;
    }

    // 檢查 PIR 觸發
    if (_pir_enabled && isPIRPinHigh()) {
        Serial.println("[Motion] PIR triggered");
        _state = MOTION_STATE_DETECTING;
    }

    return false;
}

bool MotionDetector::detectMotion(camera_fb_t* frame) {
    if (!frame || !frame->buf) {
        return false;
    }

    bool motion_detected = false;

    // 如果有 PIR 觸發或已處於偵測狀態
    if (_state == MOTION_STATE_DETECTING || _pir_enabled) {
        if (_previous_frame) {
            // 比較幀差
            if (compareFrames(frame, _previous_frame)) {
                _current_trigger_count++;
                
                if (_current_trigger_count >= _trigger_count) {
                    motion_detected = true;
                    _state = MOTION_STATE_TRIGGERED;
                    _last_motion_time = millis();
                    _motion_count++;
                    
                    Serial.printf("[Motion] Motion detected! Count: %lu, Trigger: %d\n", 
                                  _motion_count, _current_trigger_count);
                }
            } else {
                _current_trigger_count = 0;
                if (_state == MOTION_STATE_DETECTING) {
                    _state = MOTION_STATE_IDLE;
                }
            }
            
            // 釋放之前的幀
            esp_camera_fb_return(_previous_frame);
        }
        
        // 保存當前幀作為參考
        _previous_frame = frame;
    }

    // 如果偵測到運動，執行回呼
    if (motion_detected && _callback) {
        motion_result_t result;
        result.motion_detected = true;
        result.timestamp = millis();
        result.motion_area = 0;
        result.confidence = calculateConfidence(0, _current_trigger_count);
        result.frame = frame;
        _callback(&result);
    }

    return motion_detected;
}

bool MotionDetector::compareFrames(camera_fb_t* current, camera_fb_t* previous) {
    if (!current || !previous) return false;
    if (current->len != previous->len) return false;

    // 簡單的幀差比較
    // 將影像轉換為灰階並計算差異
    uint8_t* curr_buf = current->buf;
    uint8_t* prev_buf = previous->buf;
    size_t len = current->len;

    uint32_t diff_sum = 0;
    uint16_t pixel_count = 0;

    // 每隔幾個像素取樣以提高效能
    const uint16_t sample_step = 4;
    
    for (size_t i = 0; i < len; i += sample_step) {
        // JPEG 格式直接比較原始位元組
        // 雖然不完美，但對於運動偵測已經足夠
        int diff = abs((int)curr_buf[i] - (int)prev_buf[i]);
        if (diff > _diff_threshold) {
            diff_sum += diff;
            pixel_count++;
        }
    }

    // 計算差異比例
    float diff_ratio = (float)diff_sum / (float)(len / sample_step);
    
    // 根據靈敏度調整閾值
    float threshold = (float)(100 - _sensitivity) / 100.0f * 0.5f;
    
    return diff_ratio > threshold;
}

uint16_t MotionDetector::calculateMotionArea(uint8_t* diff_map, uint16_t width, uint16_t height) {
    // 簡化版本：計算差異像素數量
    uint16_t area = 0;
    for (uint16_t i = 0; i < width * height; i++) {
        if (diff_map[i] > _diff_threshold) {
            area++;
        }
    }
    return area;
}

uint8_t MotionDetector::calculateConfidence(uint16_t motion_area, uint8_t trigger_count) {
    // 根據觸發次數計算信心值
    uint8_t confidence = 0;
    
    if (trigger_count >= _trigger_count) {
        confidence = 80 + min((int)((trigger_count - _trigger_count) * 5), 20);
    } else if (trigger_count > 0) {
        confidence = (trigger_count * 80) / _trigger_count;
    }
    
    return min(confidence, (uint8_t)100);
}

void MotionDetector::updateState() {
    switch (_state) {
        case MOTION_STATE_IDLE:
            // 等待觸發
            break;
            
        case MOTION_STATE_DETECTING:
            // 正在偵測
            break;
            
        case MOTION_STATE_TRIGGERED:
            // 已觸發，進入冷卻
            _state = MOTION_STATE_COOLDOWN;
            break;
            
        case MOTION_STATE_COOLDOWN:
            // 冷卻中
            if (millis() - _last_motion_time >= _cooldown_ms) {
                _state = MOTION_STATE_IDLE;
                _current_trigger_count = 0;
            }
            break;
    }
}

bool MotionDetector::isPIRPinHigh() const {
    return digitalRead(PIR_PIN) == HIGH;
}

void MotionDetector::setSensitivity(uint8_t sensitivity) {
    _sensitivity = min(sensitivity, (uint8_t)100);
}

void MotionDetector::setCooldown(uint32_t cooldown_ms) {
    _cooldown_ms = cooldown_ms;
}

void MotionDetector::setMinArea(uint16_t area) {
    _min_area = area;
}

void MotionDetector::setDiffThreshold(uint8_t threshold) {
    _diff_threshold = threshold;
}

void MotionDetector::setTriggerCount(uint8_t count) {
    _trigger_count = max(count, (uint8_t)1);
}

motion_state_t MotionDetector::getState() const {
    return _state;
}

uint8_t MotionDetector::getSensitivity() const {
    return _sensitivity;
}

uint32_t MotionDetector::getLastMotionTime() const {
    return _last_motion_time;
}

uint32_t MotionDetector::getMotionCount() const {
    return _motion_count;
}

bool MotionDetector::pirTriggered() const {
    return _pir_enabled && isPIRPinHigh();
}

void MotionDetector::enablePIR(bool enable) {
    _pir_enabled = enable;
    if (enable) {
        pinMode(PIR_PIN, INPUT);
    }
}

void MotionDetector::onMotion(motion_callback_t callback) {
    _callback = callback;
}

void MotionDetector::reset() {
    _state = MOTION_STATE_IDLE;
    _current_trigger_count = 0;
    _motion_count = 0;
    _last_motion_time = 0;
    
    if (_previous_frame) {
        esp_camera_fb_return(_previous_frame);
        _previous_frame = NULL;
    }
}

void MotionDetector::printStatus() {
    Serial.println("=== Motion Detector Status ===");
    Serial.printf("State: %d\n", _state);
    Serial.printf("Sensitivity: %d\n", _sensitivity);
    Serial.printf("Cooldown: %lu ms\n", _cooldown_ms);
    Serial.printf("Motion Count: %lu\n", _motion_count);
    Serial.printf("Last Motion: %lu ms ago\n", 
                  millis() - _last_motion_time);
    Serial.printf("PIR Enabled: %s\n", _pir_enabled ? "Yes" : "No");
    Serial.printf("PIR Status: %s\n", pirTriggered() ? "HIGH" : "LOW");
    Serial.println("==============================");
}
