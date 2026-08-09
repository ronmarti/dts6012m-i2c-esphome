#pragma once
#include "esphome/core/component.h"
#include "esphome/components/sensor/sensor.h"
#include "esphome/core/log.h"
#include "DTS6012M.h"

namespace esphome {
namespace dts6012m {

class DTS6012MComponent : public PollingComponent {
 public:
  DTS6012MComponent(uint32_t interval = 500, int retries = 3,
                    uint32_t wakeup_time_ms = 20)
      : PollingComponent(interval), retries_(retries), wakeup_time_ms_(wakeup_time_ms) {}

  void set_distance_sensor(sensor::Sensor *s) { distance_sensor_ = s; }

  void setup() override {
    Wire.begin();
    DTS6012M_Init(&sensor_);
    // Keep sensor idle until an update cycle requests a measurement.
    DTS6012M_StopLaser();
    ESP_LOGI("dts6012m", "Sensor initialized in low-power idle mode");
  }

  void update() override {
    if (!distance_sensor_)
      return;

    DTS6012M_StartLaser();
    if (wakeup_time_ms_ > 0)
      delay(wakeup_time_ms_);

    float dist = -1;
    for (int i = 0; i < retries_; i++) {
      dist = DTS6012M_GetDistance(&sensor_);
      if (dist >= 0) break;
      delay(10);
    }

    DTS6012M_StopLaser();

    if (dist >= 0)
      distance_sensor_->publish_state(dist);
  }

 protected:
  DTS6012M sensor_;
  sensor::Sensor *distance_sensor_{nullptr};
  int retries_;
  uint32_t wakeup_time_ms_;
};

}  // namespace dts6012m
}  // namespace esphome
