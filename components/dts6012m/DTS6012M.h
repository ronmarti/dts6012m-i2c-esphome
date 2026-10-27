#pragma once

#include <Arduino.h>
#include <Wire.h>

class DTS6012M {
 public:
  explicit DTS6012M(TwoWire &wire = Wire) : wire_(wire) {}

  bool begin(bool start_measurement = true);
  bool startLaser();
  bool stopLaser();
  float getDistance();
  uint16_t getRawDistance() const { return raw_distance_; }

 private:
  bool write_register_(uint8_t reg, uint8_t value);

  static constexpr uint8_t ADDRESS = 0x51;
  TwoWire &wire_;
  uint16_t raw_distance_{0};
};
