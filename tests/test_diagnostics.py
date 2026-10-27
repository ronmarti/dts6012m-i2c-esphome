"""Compile the production component against a deterministic Wire/scheduler harness."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
HEADERS = {
    "Arduino.h": r"""
#pragma once
#include <cstdint>
#include <cstddef>
inline uint32_t clock_ms = 0;
""",
    "Wire.h": r"""
#pragma once
#include "Arduino.h"
#include <deque>
#include <vector>
#include <cstdlib>
class TwoWire {
 public:
  std::vector<std::vector<uint8_t>> writes;
  std::vector<uint8_t> pending;
  std::deque<int> rx;
  std::deque<uint8_t> statuses;
  uint16_t sample = 600;
  size_t received = 2;
  bool underrun = false;
  bool available_short = false;
  bool queue_failure = false;
  int requests = 0;
  uint32_t started_at = 0;
  void beginTransmission(uint8_t address) {
    if (address != 0x51) std::abort();
    pending.clear();
  }
  size_t write(uint8_t value) {
    pending.push_back(value);
    return queue_failure ? 0 : 1;
  }
  uint8_t endTransmission(bool stop = true) {
    if (!stop) std::abort();
    writes.push_back(pending);
    if (pending == std::vector<uint8_t>{2, 1}) started_at = clock_ms;
    if (statuses.empty()) return 0;
    auto status = statuses.front(); statuses.pop_front(); return status;
  }
  size_t requestFrom(uint8_t address, size_t count) {
    if (address != 0x51 || count != 2 || pending != std::vector<uint8_t>{0}) std::abort();
    if (clock_ms - started_at < 20) std::abort();
    ++requests;
    rx.clear();
    if (received >= 1) rx.push_back(sample >> 8);
    if (received >= 2 && !available_short) rx.push_back(sample & 255);
    return received;
  }
  int available() { return static_cast<int>(rx.size()); }
  int read() {
    if (underrun || rx.empty()) return -1;
    int value = rx.front(); rx.pop_front(); return value;
  }
};
inline TwoWire Wire;
""",
    "esphome/core/log.h": r"""
#pragma once
#include <cstdarg>
#include <cstdio>
#include <string>
#include <vector>
inline std::vector<std::string> logs;
inline void trace_log(const char *format, ...) {
  char buffer[1024];
  va_list args;
  va_start(args, format);
  vsnprintf(buffer, sizeof(buffer), format, args);
  va_end(args);
  logs.emplace_back(buffer);
}
#define ESP_LOGD(tag, ...) trace_log(__VA_ARGS__)
#define ESP_LOGW(tag, ...) trace_log(__VA_ARGS__)
#define ESP_LOGE(tag, ...) trace_log(__VA_ARGS__)
#define ESP_LOGCONFIG(tag, ...) trace_log(__VA_ARGS__)
""",
    "esphome/core/hal.h": r"""
#pragma once
#include "Arduino.h"
#include <string>
#include <vector>
namespace esphome {
class GPIOPin {
 public:
  std::vector<bool> values;
  void setup() {}
  void digital_write(bool value) { values.push_back(value); }
  std::string dump_summary() const { return "test pin"; }
};
}
""",
    "esphome/core/component.h": r"""
#pragma once
#include "Arduino.h"
#include <functional>
#include <string>
#include <stdexcept>
namespace esphome {
class PollingComponent {
 public:
  explicit PollingComponent(uint32_t interval) : interval_(interval) {}
  virtual ~PollingComponent() = default;
  virtual void setup() {}
  virtual void update() {}
  virtual void dump_config() {}
  virtual void on_shutdown() {}
  uint32_t get_update_interval() const { return interval_; }
  void set_timeout(const std::string &name, uint32_t delay, std::function<void()> callback) {
    if (name != "measurement") throw std::runtime_error("unexpected timer");
    due = clock_ms + delay;
    pending = callback;
  }
  bool cancel_timeout(const std::string &) {
    bool had = static_cast<bool>(pending); pending = nullptr; return had;
  }
  void status_set_warning() { warning = true; }
  void status_clear_warning() { warning = false; }
  void tick() {
    if (!pending) throw std::runtime_error("missing callback");
    clock_ms = due;
    auto callback = pending; pending = nullptr; callback();
  }
  void drain() {
    int count = 0;
    while (pending) {
      if (++count > 30) throw std::runtime_error("unbounded retry");
      tick();
    }
  }
  bool warning = false;
  uint32_t due = 0;
  std::function<void()> pending;
 private:
  uint32_t interval_;
};
}
""",
    "esphome/components/sensor/sensor.h": r"""
#pragma once
#include <vector>
namespace esphome { namespace sensor {
class Sensor {
 public:
  std::vector<float> published;
  void publish_state(float value) { published.push_back(value); }
};
}}
""",
}

HARNESS = r"""
#include "dts6012m_component.h"
#include <cassert>
#include <iostream>
using esphome::dts6012m::DTS6012MComponent;
bool contains(const std::string &text) {
  for (const auto &line : logs) if (line.find(text) != std::string::npos) return true;
  return false;
}
void check(bool value, const char *description) {
  if (value) return;
  for (const auto &line : logs) std::cerr << line << "\n";
  std::cerr << description << "\n"; std::exit(1);
}
int main(int argc, char **argv) {
  assert(argc == 2);
  std::string test = argv[1];
  esphome::sensor::Sensor sensor;
  esphome::GPIOPin power;
  const bool continuous = test == "continuous" || test == "continuous-failure";
  DTS6012MComponent component(500, 3, 20, 250, !continuous);
  component.set_distance_sensor(&sensor);
  if (test == "power" || test == "power-failure" || test == "power-shutdown")
    component.set_power_pin(&power);
  component.setup();
  check(Wire.writes.empty(), "no setup transaction before settling");
  if (test == "startup-shutdown") {
    component.on_shutdown(); component.drain();
    check(Wire.requests == 0 && !component.pending, "startup callback cancelled");
    component.update();
    check(!component.pending, "shutdown prevents new work");
    return 0;
  }
  if (test == "missing-sensor") {
    DTS6012MComponent missing;
    missing.setup(); missing.drain(); missing.update();
    check(missing.warning && contains("No distance sensor"), "missing sensor reported");
    return 0;
  }
  if (test == "initialization-failure") Wire.statuses = {2};
  component.drain();
  if (test == "initialization-failure") {
    check(component.warning, "failed setup warns");
    component.update(); component.drain();
    check(!component.warning && sensor.published.size() == 1, "failed setup recovers on next poll");
    return 0;
  }
  if (!power.values.empty())
    check(power.values == std::vector<bool>{false}, "power-gated setup leaves power off");
  else if (!continuous)
    check(Wire.writes == std::vector<std::vector<uint8_t>>{{}, {2, 0}}, "standby setup probes/stops");

  if (test == "short-read" || test == "power-failure" || test == "continuous-failure") Wire.received = 1;
  if (test == "underrun") Wire.underrun = true;
  if (test == "available-short") Wire.available_short = true;
  if (test == "invalid-ffff") Wire.sample = 65535;
  if (test == "select-failure") Wire.statuses = {0, 2, 2, 2, 0};
  if (test == "start-failure") Wire.statuses = {3, 0};
  if (test == "stop-failure") Wire.statuses = {0, 0, 3};
  if (test == "queue-failure") Wire.queue_failure = true;
  const auto before = clock_ms;
  const auto writes_before = Wire.writes.size();
  component.update();
  if (test == "warmup-shutdown") {
    component.on_shutdown(); component.drain();
    check(sensor.published.empty() && Wire.requests == 0, "shutdown cancels warmup before reading");
    check(Wire.writes.back() == std::vector<uint8_t>{2, 0}, "shutdown stops pending ranging");
    return 0;
  }
  if (test == "retry-shutdown") {
    // Fail the first read, then shut down while the retry is pending.
    Wire.received = 1;
    component.tick();
    check(Wire.requests == 1 && component.pending, "retry is pending");
    component.on_shutdown(); component.drain();
    check(Wire.requests == 1 && sensor.published.empty(), "shutdown cancels retries without late publication");
    return 0;
  }
  if (test == "retry-success") {
    Wire.received = 1;
    component.tick();
    check(component.due == clock_ms + 10 && sensor.published.empty(), "failed read schedules 10ms retry");
    Wire.received = 2;
  }
  if (test == "power-shutdown") {
    component.on_shutdown(); component.drain();
    check(power.values.back() == false && sensor.published.empty(), "shutdown powers down and cancels work");
    return 0;
  }
  if (test == "standby" || test == "power") {
    check(clock_ms == before && sensor.published.empty(), "update returns without blocking or early publication");
    auto size = Wire.writes.size();
    component.update();
    check(Wire.writes.size() == size, "overlapping update is skipped");
    if (test == "power") {
      check(component.due == before + 250 && size == writes_before, "power settling precedes I2C");
      component.tick();
    }
    check(component.due == clock_ms + 20, "warmup is scheduled after START");
  }
  component.drain();
  const bool failure = test == "short-read" || test == "power-failure" ||
      test == "underrun" || test == "available-short" || test == "invalid-ffff" ||
      test == "select-failure" || test == "start-failure" || test == "stop-failure" ||
      test == "queue-failure" || test == "continuous-failure";
  check(sensor.published.size() == 1, "one publication per completed cycle");
  if (failure) {
    check(std::isnan(sensor.published.back()) && component.warning, "failure publishes unavailable and sets warning");
    if (test == "invalid-ffff" || test == "short-read")
      check(Wire.requests == 3, "read attempts bounded at three");
    if (test == "select-failure") check(Wire.requests == 0, "selection failure never requests data");
    if (test == "invalid-ffff") check(contains("0xFFFF"), "invalid raw response explicitly logged");
    Wire.received = 2; Wire.underrun = false; Wire.available_short = false;
    Wire.queue_failure = false; Wire.sample = 700;
    component.update(); component.drain();
    check(!component.warning && std::fabs(sensor.published.back() - 0.7f) < 0.00001f,
          "next cycle reinitializes and clears warning after recovery");
  } else {
    check(!component.warning && std::fabs(sensor.published.back() - 0.6f) < 0.00001f, "valid sample converted");
    component.update(); component.drain();
    check(sensor.published.size() == 2 && sensor.published[0] == sensor.published[1], "stationary values remain valid");
  }
  if (test == "continuous") {
    for (size_t i = writes_before; i < Wire.writes.size(); ++i)
      check(Wire.writes[i] == std::vector<uint8_t>{0}, "continuous polls only read distance");
  }
  if (test == "power" || test == "power-failure")
    check(power.values.back() == false, "power off after every cycle");
  component.on_shutdown();
  check(!component.pending && Wire.writes.back() == std::vector<uint8_t>{2, 0}, "shutdown leaves no pending work and stops");
  if (test == "standby") {
    DTS6012MComponent next_boot;
    next_boot.set_distance_sensor(&sensor);
    next_boot.setup(); next_boot.drain(); next_boot.update(); next_boot.drain();
    check(sensor.published.size() == 3 && !next_boot.warning, "new MCU boot can initialize the shared sensor again");
    next_boot.on_shutdown();
  }
  std::cout << "PASS " << test << "\n";
}
"""


class ProductionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = os.environ.get("CXX") or shutil.which("g++") or shutil.which("clang++")
        if not compiler:
            raise RuntimeError("A native C++17 compiler (g++ or clang++) is required")
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        directory = Path(cls.temp.name)
        for name, text in HEADERS.items():
            path = directory / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        harness = directory / "production.cpp"
        harness.write_text(HARNESS, encoding="utf-8")
        cls.binary = directory / ("production.exe" if os.name == "nt" else "production")
        subprocess.run(
            [compiler, "-std=c++17", "-Wall", "-Wextra", "-Werror",
             "-I", str(directory), "-I", str(ROOT / "components" / "dts6012m"),
             str(harness), str(ROOT / "components" / "dts6012m" / "DTS6012M.cpp"),
             "-o", str(cls.binary)],
            check=True,
        )

    def test_lifecycle_and_failures(self):
        for scenario in (
            "standby", "continuous", "power", "initialization-failure",
            "short-read", "available-short", "underrun", "invalid-ffff",
            "select-failure", "start-failure", "stop-failure", "queue-failure",
            "power-failure", "startup-shutdown", "power-shutdown",
            "continuous-failure", "warmup-shutdown", "retry-shutdown",
            "retry-success", "missing-sensor",
        ):
            with self.subTest(scenario=scenario):
                result = subprocess.run([str(self.binary), scenario], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


@unittest.skipUnless(shutil.which("esphome"), "ESPHome CLI is required for schema tests")
class ConfigurationTests(unittest.TestCase):
    def test_supported_modes_and_invalid_configuration(self):
        source = (ROOT / "components").as_posix()
        base = f"""
esphome:
  name: dts-production-test
esp32:
  board: denky32
  framework:
    type: arduino
logger:
i2c:
  sda: 21
  scl: 18
external_components:
  - source: {source}
    components: [dts6012m]
dts6012m:
  retries: 3
  sleep_between_updates: true
  distance:
    name: Test distance
"""
        cases = [
            ("standby", base, None),
            ("continuous", base.replace("sleep_between_updates: true", "sleep_between_updates: false"), None),
            ("power", base.replace("  retries: 3", "  power_pin: GPIO23\n  retries: 3"), None),
            ("no-attempts", base.replace("retries: 3", "retries: 0"), "at least 1"),
            ("negative-attempts", base.replace("retries: 3", "retries: -1"), "at least 1"),
            ("excessive-attempts", base.replace("retries: 3", "retries: 11"), "at most 10"),
            ("esp-idf", base.replace("type: arduino", "type: esp-idf"), "arduino"),
            ("multiple-buses", base.replace(
                "i2c:\n  sda: 21\n  scl: 18",
                "i2c:\n  - sda: 21\n    scl: 18\n  - sda: 22\n    scl: 19",
            ), "exactly one I2C bus"),
            ("missing-bus", base.replace("i2c:\n  sda: 21\n  scl: 18\n", ""), "requires component i2c"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.yaml"
            for name, config, error in cases:
                with self.subTest(configuration=name):
                    path.write_text(config, encoding="utf-8")
                    result = subprocess.run(
                        ["esphome", "config", str(path)], capture_output=True, text=True,
                    )
                    output = result.stdout + result.stderr
                    if error is None:
                        self.assertEqual(result.returncode, 0, output)
                    else:
                        self.assertNotEqual(result.returncode, 0, output)
                        self.assertIn(error.lower(), output.lower())


if __name__ == "__main__":
    unittest.main()
