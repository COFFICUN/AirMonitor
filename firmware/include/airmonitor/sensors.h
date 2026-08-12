#pragma once

#include <Adafruit_SHT31.h>
#include <Plantower_PMS7003.h>

#include <cstdint>

#include "airmonitor/firmware_logic.h"

namespace airmonitor {

class SensorManager {
 public:
  bool begin();
  void poll(std::uint32_t now_ms);
  const SensorSnapshot& snapshot() const;

 private:
  static constexpr std::uint32_t kShtReadIntervalMs = 2000U;
  static constexpr std::uint32_t kPmsTimeoutMs = 15000U;

  void read_sht();
  void poll_pms(std::uint32_t now_ms);

  Plantower_PMS7003 pms_{};
  Adafruit_SHT31 sht_{};
  SensorSnapshot snapshot_{};
  std::uint32_t last_sht_read_ms_ = 0;
  std::uint32_t last_pms_frame_ms_ = 0;
  std::uint32_t started_at_ms_ = 0;
  bool sht_initialized_ = false;
};

}  // namespace airmonitor
