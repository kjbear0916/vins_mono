#ifndef MOTION_DETECTOR_H
#define MOTION_DETECTOR_H

#include <Arduino.h>
#include "esp_camera.h"

// 運動偵測狀態
typedef enum {
    MOTION_STATE_IDLE,
    MOTION_STATE_DETECTING,
    MOTION_STATE_TRIGGERED,
    MOTION_STATE_COOLDOWN
} motion_state_t;

// 運動偵測結果
typedef struct {
    bool motion_detected;
    uint32_t timestamp;
    uint16_t motion_area;
    uint8_t confidence;
    camera_fb_t* frame;
} motion_result_t;

// 回呼函數類型
typedef void (*motion_callback_t)(motion_result_t* result);

class MotionDetector {
public:
    MotionDetector();
    ~MotionDetector();

    // 初始化
    bool begin(uint8_t sensitivity = 50, uint32_t cooldown_ms = 5000);

    // 主要功能
    bool update();
    bool detectMotion(camera_fb_t* frame);
    void reset();

    // 設定
    void setSensitivity(uint8_t sensitivity);
    void setCooldown(uint32_t cooldown_ms);
    void setMinArea(uint16_t area);
    void setDiffThreshold(uint8_t threshold);
    void setTriggerCount(uint8_t count);

    // 取得狀態
    motion_state_t getState() const;
    uint8_t getSensitivity() const;
    uint32_t getLastMotionTime() const;
    uint32_t getMotionCount() const;

    // PIR 感測器
    bool pirTriggered() const;
    void enablePIR(bool enable);

    // 回呼函數
    void onMotion(motion_callback_t callback);

    // 除錯
    void printStatus();

private:
    motion_state_t _state;
    uint8_t _sensitivity;
    uint32_t _cooldown_ms;
    uint16_t _min_area;
    uint8_t _diff_threshold;
    uint8_t _trigger_count;
    uint8_t _current_trigger_count;

    uint32_t _last_motion_time;
    uint32_t _motion_count;
    bool _pir_enabled;

    camera_fb_t* _previous_frame;
    motion_callback_t _callback;

    // 內部方法
    bool compareFrames(camera_fb_t* current, camera_fb_t* previous);
    uint16_t calculateMotionArea(uint8_t* diff_map, uint16_t width, uint16_t height);
    uint8_t calculateConfidence(uint16_t motion_area, uint8_t trigger_count);
    void updateState();
    bool isPIRPinHigh() const;
};

#endif // MOTION_DETECTOR_H
