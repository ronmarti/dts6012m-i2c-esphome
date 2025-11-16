#pragma once
#include "esphome/core/component.h"
#include "esphome/components/sensor/sensor.h"
#include "esphome/core/log.h"
#include "DTS6012M.h"

namespace esphome {
namespace dts6012m {

class DTS6012MComponent : public PollingComponent {
 public:
  DTS6012MComponent(uint32_t interval = 500, int retries = 3)
      : PollingComponent(interval), retries_(retries) {}

  void set_distance_sensor(sensor::Sensor *s) { distance_sensor_ = s; }

  void setup() override {
    Wire.begin();
    DTS6012M_Init(&sensor_);
    DTS6012M_StartLaser();
    ESP_LOGI("dts6012m", "Sensor initialized");
  }

  void update() override {
    if (!distance_sensor_)
      return;

    float dist = -1;
    for (int i = 0; i < retries_; i++) {
      dist = DTS6012M_GetDistance(&sensor_);
      if (dist >= 0) break;
      delay(10);
    }

    if (dist >= 0)
      distance_sensor_->publish_state(dist);
  }

 protected:
  DTS6012M sensor_;
  sensor::Sensor *distance_sensor_{nullptr};
  int retries_;
};

}  // namespace dts6012m
}  // namespace esphome
