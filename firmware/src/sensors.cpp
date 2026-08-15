#include "airmonitor/sensors.h"

#include <Arduino.h>

#include <cmath>

namespace airmonitor {

namespace {

constexpr int kPmsRxPin = 16;
constexpr int kPmsTxPin = 17;
constexpr std::uint32_t kPmsBaud = 9600U;
constexpr std::uint8_t kShtAddress = 0x44;

bool elapsed(
    std::uint32_t now_ms,
    std::uint32_t since_ms,
    std::uint32_t interval_ms) {
  return now_ms - since_ms >= interval_ms;
}

}  // namespace

bool SensorManager::begin() {
  started_at_ms_ = millis();
  last_sht_read_ms_ = started_at_ms_ - kShtReadIntervalMs;
  Serial2.begin(kPmsBaud, SERIAL_8N1, kPmsRxPin, kPmsTxPin);
  pms_.init(&Serial2);
  sht_initialized_ = sht_.begin(kShtAddress);
  return sht_initialized_;
}

void SensorManager::poll(std::uint32_t now_ms) {
  poll_pms(now_ms);
  if (elapsed(now_ms, last_sht_read_ms_, kShtReadIntervalMs)) {
    last_sht_read_ms_ = now_ms;
    read_sht();
  }
}

const SensorSnapshot& SensorManager::snapshot() const {
  return snapshot_;
}

void SensorManager::read_sht() {
  if (!sht_initialized_) {
    snapshot_.sht_ok = false;
    return;
  }
  float temperature = NAN;
  float humidity = NAN;
  // SHT3x single-shot mode returns temperature and humidity as one data pair.
  // Source: https://sensirion.com/media/documents/213E6A3B/63A5A569/Datasheet_SHT3x_DIS.pdf
  const bool received = sht_.readBoth(&temperature, &humidity);
  const bool valid = received && std::isfinite(temperature) &&
                     std::isfinite(humidity) && temperature >= -40.0F &&
                     temperature <= 85.0F && humidity >= 0.0F &&
                     humidity <= 100.0F;
  snapshot_.sht_ok = valid;
  if (valid) {
    snapshot_.temperature = temperature;
    snapshot_.humidity = humidity;
  }
}

void SensorManager::poll_pms(std::uint32_t now_ms) {
  pms_.updateFrame();
  if (pms_.hasNewData()) {
    // PMSA003 Data 4-6 are intended for atmospheric measurements. Data 1-3
    // (the getters without _atmos) are CF=1 factory-environment values.
    // Source: https://www.gotronic.fr/pj2-pmsa003-series-data-manua-english-v2-5-2083.pdf
    PmsFrame frame{};
    frame.pm1 = pms_.getPM_1_0_atmos();
    frame.pm25 = pms_.getPM_2_5_atmos();
    frame.pm10 = pms_.getPM_10_0_atmos();
    frame.pc0_3 = pms_.getRawGreaterThan_0_3();
    frame.pc0_5 = pms_.getRawGreaterThan_0_5();
    frame.pc1_0 = pms_.getRawGreaterThan_1_0();
    frame.pc2_5 = pms_.getRawGreaterThan_2_5();
    frame.pc5_0 = pms_.getRawGreaterThan_5_0();
    frame.pc10 = pms_.getRawGreaterThan_10_0();
    last_pms_frame_ms_ = now_ms;
    update_pms_snapshot(snapshot_, frame, now_ms, started_at_ms_);
  }

  if (!elapsed(now_ms, started_at_ms_, kPmsWarmupMs)) {
    snapshot_.pms_status = PmsStatus::warming_up;
    snapshot_.pms_ok = false;
    return;
  }
  const std::uint32_t reference =
      last_pms_frame_ms_ == 0U ? started_at_ms_ : last_pms_frame_ms_;
  if (elapsed(now_ms, reference, kPmsTimeoutMs)) {
    snapshot_.pms_status = PmsStatus::stale;
    snapshot_.pms_ok = false;
  }
}

}  // namespace airmonitor
