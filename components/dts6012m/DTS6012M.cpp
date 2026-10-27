#include "DTS6012M.h"
#include "esphome/core/log.h"

bool DTS6012M::begin(bool start_measurement) {
  // ESPHome configures the shared Wire bus; never reset its pins or clock here.
  wire_.beginTransmission(ADDRESS);
  const uint8_t status = wire_.endTransmission();
  if (status != 0) {
    ESP_LOGW("dts6012m", "Sensor probe failed (I2C status %u)", status);
    return false;
  }
  if (!stopLaser())
    return false;
  return !start_measurement || startLaser();
}

bool DTS6012M::startLaser() { return write_register_(0x02, 1); }

bool DTS6012M::stopLaser() { return write_register_(0x02, 0); }

float DTS6012M::getDistance() {
  wire_.beginTransmission(ADDRESS);
  const size_t queued = wire_.write(uint8_t{0x00});
  // Retain the STOP-based register selection used by the working v0.1.2.
  const uint8_t status = wire_.endTransmission();
  if (queued != 1 || status != 0) {
    ESP_LOGW("dts6012m", "Distance register selection failed (queued %u, I2C status %u)",
             static_cast<unsigned>(queued), status);
    return -1.0f;
  }
  const size_t received = wire_.requestFrom(ADDRESS, size_t{2});
  if (received != 2 || wire_.available() < 2) {
    ESP_LOGW("dts6012m", "Incomplete distance response (received %u, available %d)",
             static_cast<unsigned>(received), wire_.available());
    while (wire_.available() > 0)
      wire_.read();
    return -1.0f;
  }
  const int msb = wire_.read();
  const int lsb = wire_.read();
  if (msb < 0 || lsb < 0) {
    ESP_LOGW("dts6012m", "Distance response buffer underrun");
    return -1.0f;
  }
  raw_distance_ = (static_cast<uint16_t>(msb) << 8) | static_cast<uint16_t>(lsb);
  if (raw_distance_ == 0xFFFF) {
    // Outside the specified 20m range; its firmware-specific meaning is unknown.
    ESP_LOGW("dts6012m", "Invalid distance 0xFFFF; not publishing 65.535m");
    return -1.0f;
  }
  return raw_distance_ * 0.001f;
}

bool DTS6012M::write_register_(uint8_t reg, uint8_t value) {
  wire_.beginTransmission(ADDRESS);
  const size_t queued_reg = wire_.write(reg);
  const size_t queued_value = wire_.write(value);
  const uint8_t status = wire_.endTransmission();
  if (queued_reg != 1 || queued_value != 1 || status != 0) {
    ESP_LOGW("dts6012m", "Register 0x%02X write 0x%02X failed (queued %u, I2C status %u)",
             reg, value, static_cast<unsigned>(queued_reg + queued_value), status);
    return false;
  }
  return true;
}
