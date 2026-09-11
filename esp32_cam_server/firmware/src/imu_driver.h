#ifndef IMU_DRIVER_H
#define IMU_DRIVER_H

#include <Arduino.h>
#include <Wire.h>
#include <WiFiUdp.h>

// MPU6050 裸寄存器(不依賴外部 library;±250°/s ±2g 預設量程)
#define IMU_REG_WHO_AM_I    0x75
#define IMU_REG_PWR_MGMT_1  0x6B
#define IMU_REG_ACCEL_XOUT  0x3B

// 每組樣本原始值+時間戳(ESP32 millis,與影像 meta 同源)
typedef struct {
  uint32_t ts_ms;
  int16_t  ax, ay, az;   // accel LSB(±2g → 16384 LSB/g)
  int16_t  gx, gy, gz;   // gyro  LSB(±250°/s → 131 LSB/°/s)
} imu_sample_t;

class ImuDriver {
 public:
  // Wire 初始化 + MPU6050 喚醒;回傳 true = OK
  bool begin(int sda_pin, int scl_pin, uint32_t i2c_freq = 400000);
  // 單次讀取(無阻塞,失敗回傳 false)
  bool readSample(imu_sample_t& out);
  // Core-0 高優先級 task 進入點:以固定 HZ 取樣並 UDP 廣播 CSV
  static void taskLoop(void* arg);
  // 每筆樣本透過 UDP 送出  IMU,<ts_ms>,gx,gy,gz,ax,ay,az
  static bool udpSend(WiFiUDP& udp, const imu_sample_t& s);

 private:
  static bool readRegs(uint8_t reg, uint8_t* buf, size_t n);
  int addr_;
};

// 全域單例(在 ino 或本檔定義)
extern ImuDriver imuDriver;

#endif  // IMU_DRIVER_H