#pragma once
#include "esphome/core/component.h"
#include "esphome/components/sensor/sensor.h"
#include "esphome/core/hal.h"
#include "esphome/core/log.h"
#include "DTS6012M.h"

namespace esphome {
namespace dts6012m {

class DTS6012MComponent : public PollingComponent {
 public:
  DTS6012MComponent(uint32_t interval = 500, int retries = 3,
                    uint32_t wakeup_time_ms = 20,
                    uint32_t powerup_time_ms = 250,
                    bool sleep_between_updates = false)
      : PollingComponent(interval), retries_(retries), wakeup_time_ms_(wakeup_time_ms),
        powerup_time_ms_(powerup_time_ms), sleep_between_updates_(sleep_between_updates) {}

  void set_distance_sensor(sensor::Sensor *s) { distance_sensor_ = s; }
  void set_power_pin(GPIOPin *pin) { power_pin_ = pin; }

  void setup() override {
    Wire.begin();
    if (power_pin_ != nullptr) {
      power_pin_->setup();
      power_pin_->digital_write(false);
      ESP_LOGI("dts6012m", "Sensor configured for GPIO power gating");
      return;
    }

    DTS6012M_Init(&sensor_);
    if (sleep_between_updates_) {
      DTS6012M_StopLaser();
      ESP_LOGI("dts6012m", "Sensor initialized in standby-between-updates mode");
    } else {
      DTS6012M_StartLaser();
      ESP_LOGI("dts6012m", "Sensor initialized in continuous ranging mode");
    }
  }

  void update() override {
    if (!distance_sensor_)
      return;

    prepare_measurement_();

    float dist = -1;
    for (int i = 0; i < retries_; i++) {
      dist = DTS6012M_GetDistance(&sensor_);
      if (dist >= 0) break;
      delay(10);
    }

    finish_measurement_();

    if (dist >= 0)
      distance_sensor_->publish_state(dist);
  }

 protected:
  bool prepare_measurement_() {
    if (power_pin_ != nullptr) {
      power_pin_->digital_write(true);
      if (powerup_time_ms_ > 0)
        delay(powerup_time_ms_);
      DTS6012M_Init(&sensor_);
      DTS6012M_StartLaser();
    } else if (sleep_between_updates_) {
      DTS6012M_StartLaser();
    } else {
      // Some DTS6012M units keep returning a latched value unless ranging is
      // explicitly re-armed before each read cycle.
      DTS6012M_StartLaser();
    }

    if (wakeup_time_ms_ > 0)
      delay(wakeup_time_ms_);

    // Freshly powered or resumed sensors can expose the last latched sample first.
    DTS6012M_GetDistance(&sensor_);
    delay(10);
    return true;
  }

  void finish_measurement_() {
    if (power_pin_ != nullptr) {
      DTS6012M_StopLaser();
      delay(10);
      power_pin_->digital_write(false);
    } else if (sleep_between_updates_) {
      DTS6012M_StopLaser();
    }
  }

  DTS6012M sensor_;
  sensor::Sensor *distance_sensor_{nullptr};
  int retries_;
  uint32_t wakeup_time_ms_;
  uint32_t powerup_time_ms_;
  bool sleep_between_updates_;
  GPIOPin *power_pin_{nullptr};
};

}  // namespace dts6012m
}  // namespace esphome
