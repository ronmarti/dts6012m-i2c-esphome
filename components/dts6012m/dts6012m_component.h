#pragma once

#include <cmath>
#include "esphome/core/component.h"
#include "esphome/core/hal.h"
#include "esphome/core/log.h"
#include "esphome/components/sensor/sensor.h"
#include "DTS6012M.h"

namespace esphome {
namespace dts6012m {

class DTS6012MComponent : public PollingComponent {
 public:
  DTS6012MComponent(uint32_t interval = 500, int retries = 3,
                    uint32_t wakeup_time_ms = 20, uint32_t powerup_time_ms = 250,
                    bool sleep_between_updates = true)
      : PollingComponent(interval), retries_(retries), wakeup_time_ms_(wakeup_time_ms),
        powerup_time_ms_(powerup_time_ms), sleep_between_updates_(sleep_between_updates) {}

  void set_distance_sensor(sensor::Sensor *sensor) { distance_sensor_ = sensor; }
  void set_power_pin(GPIOPin *pin) { power_pin_ = pin; }

  void dump_config() override {
    ESP_LOGCONFIG("dts6012m", "DTS6012M (Arduino, address 0x51, STOP-based reads):");
    ESP_LOGCONFIG("dts6012m", "  Mode: %s", power_pin_ != nullptr ? "power-gated" :
                  sleep_between_updates_ ? "standby between updates" : "continuous");
    ESP_LOGCONFIG("dts6012m", "  Interval: %lu ms, attempts: %d",
                  static_cast<unsigned long>(get_update_interval()), retries_);
    ESP_LOGCONFIG("dts6012m", "  Power settling: %lu ms, ranging warmup: %lu ms",
                  static_cast<unsigned long>(powerup_time_ms_), static_cast<unsigned long>(wakeup_time_ms_));
    if (power_pin_ != nullptr)
      ESP_LOGCONFIG("dts6012m", "  Power pin: %s", power_pin_->dump_summary().c_str());
  }

  void setup() override {
    if (power_pin_ != nullptr) {
      power_pin_->setup();
      power_pin_->digital_write(false);
      return;
    }
    powered_ = true;
    busy_ = true;
    this->set_timeout("measurement", powerup_time_ms_, [this]() {
      initialized_ = sensor_.begin(!sleep_between_updates_);
      if (!initialized_) {
        this->status_set_warning();
        ESP_LOGW("dts6012m", "Initialization failed; will retry on next update");
        stop_();
      }
      if (initialized_ && !sleep_between_updates_) {
        this->set_timeout("measurement", wakeup_time_ms_, [this]() { busy_ = false; });
      } else {
        busy_ = false;
      }
    });
  }

  void update() override {
    if (shutting_down_)
      return;
    if (busy_) {
      ESP_LOGD("dts6012m", "Skipping update while initialization or measurement is pending");
      return;
    }
    if (distance_sensor_ == nullptr) {
      this->status_set_warning();
      ESP_LOGE("dts6012m", "No distance sensor configured");
      return;
    }
    busy_ = true;
    attempts_ = 0;
    if (power_pin_ != nullptr) {
      power_pin_->digital_write(true);
      powered_ = true;
      initialized_ = false;
      this->set_timeout("measurement", powerup_time_ms_, [this]() { start_measurement_(); });
    } else {
      start_measurement_();
    }
  }

  void on_shutdown() override {
    shutting_down_ = true;
    this->cancel_timeout("measurement");
    if (powered_)
      stop_();
    if (power_pin_ != nullptr)
      power_pin_->digital_write(false);
    powered_ = false;
    initialized_ = false;
    busy_ = false;
  }

 protected:
  bool stop_() {
    if (sensor_.stopLaser())
      return true;
    initialized_ = false;
    this->status_set_warning();
    ESP_LOGW("dts6012m", "Could not stop ranging");
    return false;
  }

  void start_measurement_() {
    bool started = false;
    if (!initialized_) {
      initialized_ = sensor_.begin(true);
      started = initialized_;
      if (!initialized_) {
        finish_(NAN);
        return;
      }
    } else if (sleep_between_updates_) {
      if (!sensor_.startLaser()) {
        initialized_ = false;
        finish_(NAN);
        return;
      }
      started = true;
    }
    if (started) {
      this->set_timeout("measurement", wakeup_time_ms_, [this]() { read_measurement_(); });
    } else {
      read_measurement_();
    }
  }

  void read_measurement_() {
    ++attempts_;
    const float distance = sensor_.getDistance();
    if (distance >= 0.0f) {
      finish_(distance);
    } else if (attempts_ < retries_) {
      this->set_timeout("measurement", 10, [this]() { read_measurement_(); });
    } else {
      initialized_ = false;
      ESP_LOGW("dts6012m", "Measurement failed after %d attempts; sensor unavailable", attempts_);
      finish_(NAN);
    }
  }

  void finish_(float distance) {
    bool stopped = true;
    if (powered_ && (power_pin_ != nullptr || sleep_between_updates_ || !std::isfinite(distance)))
      stopped = stop_();
    if (!std::isfinite(distance) || !stopped) {
      this->status_set_warning();
      ESP_LOGW("dts6012m", "Measurement cycle failed; publishing unavailable");
      distance = NAN;
    } else {
      this->status_clear_warning();
      ESP_LOGD("dts6012m", "Distance: %.3f m (raw %u mm, attempt %d/%d)",
               distance, sensor_.getRawDistance(), attempts_, retries_);
    }
    if (power_pin_ != nullptr) {
      this->set_timeout("measurement", 10, [this, distance]() {
        power_pin_->digital_write(false);
        powered_ = false;
        initialized_ = false;
        busy_ = false;
        distance_sensor_->publish_state(distance);
      });
    } else {
      busy_ = false;
      distance_sensor_->publish_state(distance);
    }
  }

  DTS6012M sensor_{Wire};
  sensor::Sensor *distance_sensor_{nullptr};
  GPIOPin *power_pin_{nullptr};
  int retries_;
  uint32_t wakeup_time_ms_;
  uint32_t powerup_time_ms_;
  bool sleep_between_updates_;
  int attempts_{0};
  bool initialized_{false};
  bool powered_{false};
  bool busy_{false};
  bool shutting_down_{false};
};

}  // namespace dts6012m
}  // namespace esphome
