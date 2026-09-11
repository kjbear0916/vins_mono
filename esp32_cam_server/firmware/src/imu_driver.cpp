#include "imu_driver.h"
#include "config/config.h"

ImuDriver imuDriver;

// ---------------------------------------------------------------------------
// 支援函式
// ---------------------------------------------------------------------------
bool ImuDriver::readRegs(uint8_t reg, uint8_t* buf, size_t n) {
  Wire.beginTransmission(IMU_ADDR);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) return false;  // NACK
  Wire.requestFrom((uint8_t)IMU_ADDR, (uint8_t)n);
  size_t got = 0;
  while (Wire.available() && got < n) buf[got++] = Wire.read();
  return got == n;
}

bool ImuDriver::begin(int sda_pin, int scl_pin, uint32_t i2c_freq) {
  addr_ = IMU_ADDR;
  Wire.begin(sda_pin, scl_pin, i2c_freq);

  uint8_t who = 0;
  if (!readRegs(IMU_REG_WHO_AM_I, &who, 1) || (who & 0x7E) != 0x68) {
    Serial.printf("[IMU] MPU6050 not found (WHO_AM_I=0x%02X) at pins SDA=%d SCL=%d\n",
                  who, sda_pin, scl_pin);
    return false;
  }
  // 喚醒:清除 PWR_MGMT_1 bit6(SLEEP),選內部 8MHz 時鐘(bits2:0=0x01)
  if (!readRegs(IMU_REG_PWR_MGMT_1, &who, 1)) return false;
  who &= ~(1 << 6);    // clear SLEEP
  who = (who & ~0x07) | 0x01;
  Wire.beginTransmission(addr_);
  Wire.write(IMU_REG_PWR_MGMT_1);
  Wire.write(who);
  if (Wire.endTransmission() != 0) return false;

  Serial.printf("[IMU] MPU6050 OK (WHO_AM_I=0x%02X) @ SDA=%d SCL=%d\n", 0x68, sda_pin, scl_pin);
  return true;
}

bool ImuDriver::readSample(imu_sample_t& out) {
  uint8_t raw[14];  // accel(6) + temp(2) + gyro(6)
  if (!readRegs(IMU_REG_ACCEL_XOUT, raw, sizeof(raw))) return false;
  out.ts_ms = millis();
  // 大端 int16
  out.ax = (int16_t)((raw[0] << 8) | raw[1]);
  out.ay = (int16_t)((raw[2] << 8) | raw[3]);
  out.az = (int16_t)((raw[4] << 8) | raw[5]);
  out.gx = (int16_t)((raw[8] << 8) | raw[9]);
  out.gy = (int16_t)((raw[10] << 8) | raw[11]);
  out.gz = (int16_t)((raw[12] << 8) | raw[13]);
  return true;
}

bool ImuDriver::udpSend(WiFiUDP& udp, const imu_sample_t& s) {
  char line[96];
  snprintf(line, sizeof(line), "IMU,%lu,%d,%d,%d,%d,%d,%d\n",
           (unsigned long)s.ts_ms, s.gx, s.gy, s.gz, s.ax, s.ay, s.az);
  udp.beginPacket(IMU_UDP_TARGET_IP, IMU_UDP_PORT);
  udp.write((const uint8_t*)line, strlen(line));
  return udp.endPacket() == 1;
}

// Core-0 高優先級 task,以固定 HZ 取樣。WiFi 就緒前持續等待。
void ImuDriver::taskLoop(void* arg) {
#ifdef IMU_ENABLED
#if IMU_ENABLED
  WiFiUDP udp;
  udp.begin(IMU_UDP_PORT);

  const uint32_t period_us = 1000000UL / IMU_SAMPLE_HZ;
  uint32_t next_us = micros();
  imu_sample_t s;

  for (;;) {
    // 等 WiFi 連線(影像 server 用同一 WiFi,連上才開始送)
    if (WiFi.status() == WL_CONNECTED && readSample(s)) {
      udpSend(udp, s);
    }
    next_us += period_us;
    int32_t slip = (int32_t)(next_us - micros());
    if (slip > 0) vTaskDelay((TickType_t)(slip / 1000));  // 固定節拍
    // slip<0 表示取樣擠壓(I2C 過慢),不追趕,下周期自動校正
  }
#endif
#endif
}