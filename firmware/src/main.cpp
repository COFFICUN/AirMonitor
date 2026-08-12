#include <Arduino.h>
#include <WiFi.h>
#include <esp_system.h>
#include <time.h>

#include <cstring>

#include "airmonitor/api_client.h"
#include "airmonitor/display.h"
#include "airmonitor/firmware_logic.h"
#include "airmonitor/sensors.h"
#include "firmware_config.h"

namespace {

using airmonitor::ActiveSessionCheck;
using airmonitor::ApiClient;
using airmonitor::ApiResult;
using airmonitor::ButtonActions;
using airmonitor::DeliveryDisposition;
using airmonitor::DeviceDisplay;
using airmonitor::DisplayStatus;
using airmonitor::HealthCheck;
using airmonitor::PendingMeasurement;
using airmonitor::PendingQueue;
using airmonitor::RunState;
using airmonitor::SensorManager;
using airmonitor::SessionState;

static_assert(AIRMONITOR_DEVICE_ID > 0U, "AIRMONITOR_DEVICE_ID must be positive");
static_assert(
    AIRMONITOR_HTTP_TIMEOUT_MS > 0U && AIRMONITOR_HTTP_TIMEOUT_MS <= 10000U,
    "AIRMONITOR_HTTP_TIMEOUT_MS must be between 1 and 10000");
static_assert(
    AIRMONITOR_PENDING_QUEUE_CAPACITY > 0U &&
        AIRMONITOR_PENDING_QUEUE_CAPACITY <= 64U,
    "AIRMONITOR_PENDING_QUEUE_CAPACITY must be between 1 and 64");
static_assert(
    AIRMONITOR_MEASUREMENT_INTERVAL_MS >= 1000U,
    "AIRMONITOR_MEASUREMENT_INTERVAL_MS must be at least 1000");

constexpr std::uint32_t kWifiRetryIntervalMs = 10000U;
constexpr std::uint32_t kNtpRetryIntervalMs = 30000U;
constexpr std::uint32_t kHealthIntervalMs = 30000U;
constexpr std::uint32_t kHealthRecoveryIntervalMs = 5000U;
constexpr std::uint32_t kDeviceVerificationIntervalMs = 60000U;
constexpr std::uint32_t kSensorLogIntervalMs = 5000U;

ApiClient api_client(
    AIRMONITOR_API_BASE_URL,
    AIRMONITOR_DEVICE_ID,
    AIRMONITOR_DEVICE_UID,
    AIRMONITOR_API_CA_CERT,
    static_cast<std::uint16_t>(AIRMONITOR_HTTP_TIMEOUT_MS));
SensorManager sensors;
DeviceDisplay display;
PendingQueue<AIRMONITOR_PENDING_QUEUE_CAPACITY> pending_measurements;
SessionState session_state;

bool api_available = false;
bool device_accepted = false;
bool time_synchronized = false;
bool locally_paused = false;
bool sending = false;
std::uint64_t boot_nonce = 0;
std::uint32_t message_sequence = 0;
std::uint32_t delivered_count = 0;
std::uint32_t rejected_count = 0;
std::uint32_t last_success_ms = 0;
std::uint32_t next_wifi_attempt_ms = 0;
std::uint32_t next_ntp_attempt_ms = 0;
std::uint32_t next_health_check_ms = 0;
std::uint32_t next_device_check_ms = 0;
std::uint32_t next_session_poll_ms = 0;
std::uint32_t next_measurement_ms = 0;
std::uint32_t next_sensor_log_ms = 0;
std::uint32_t session_capture_ready_ms = 0;
int last_http_status = 0;

bool same_error_code(const ApiResult& result, const char* code) {
  return std::strcmp(result.error_code, code) == 0;
}

bool is_temporary_api_failure(const ApiResult& result) {
  return result.response_body_status !=
             airmonitor::ResponseBodyStatus::complete ||
         result.http_status <= 0 || result.http_status == 408 ||
         result.http_status == 425 || result.http_status == 429 ||
         (result.http_status >= 500 && result.http_status < 600);
}

bool wifi_connected() {
  return WiFi.status() == WL_CONNECTED;
}

const char* pms_status_name(airmonitor::PmsStatus status) {
  switch (status) {
    case airmonitor::PmsStatus::warming_up:
      return "warmup";
    case airmonitor::PmsStatus::ready:
      return "ok";
    case airmonitor::PmsStatus::invalid_frame:
      return "invalid_frame";
    case airmonitor::PmsStatus::stale:
      return "stale";
  }
  return "unknown";
}

void log_sensor_snapshot(std::uint32_t now_ms) {
  if (!airmonitor::deadline_reached(now_ms, next_sensor_log_ms)) {
    return;
  }
  next_sensor_log_ms = now_ms + kSensorLogIntervalMs;
  const airmonitor::SensorSnapshot& snapshot = sensors.snapshot();
  Serial.printf(
      "[sensors] pms=%s pm1=%.0f pm25=%.0f pm10=%.0f "
      "pc03=%ld sht=%s temp=%.2f humidity=%.2f\n",
      pms_status_name(snapshot.pms_status),
      snapshot.pm1,
      snapshot.pm25,
      snapshot.pm10,
      static_cast<long>(snapshot.pc0_3),
      snapshot.sht_ok ? "ok" : "error",
      snapshot.temperature,
      snapshot.humidity);
}

void invalidate_remote_connectivity() {
  api_available = false;
  device_accepted = false;
  session_state.invalidate_remote();
  next_health_check_ms = 0;
  next_device_check_ms = 0;
  next_session_poll_ms = 0;
}

void maintain_wifi(std::uint32_t now_ms) {
  if (wifi_connected()) {
    return;
  }
  invalidate_remote_connectivity();
  if (!airmonitor::deadline_reached(now_ms, next_wifi_attempt_ms)) {
    return;
  }
  next_wifi_attempt_ms = now_ms + kWifiRetryIntervalMs;
  WiFi.begin(AIRMONITOR_WIFI_SSID, AIRMONITOR_WIFI_PASSWORD);
  Serial.println("[wifi] connection attempt");
}

std::size_t reject_pending_session(
    std::uint32_t session_id,
    const char* reason) {
  const std::size_t discarded =
      pending_measurements.discard_session(session_id);
  rejected_count += static_cast<std::uint32_t>(discarded);
  if (discarded > 0U) {
    Serial.printf(
        "[queue] rejected session=%u count=%u reason=%s\n",
        static_cast<unsigned>(session_id),
        static_cast<unsigned>(discarded),
        reason);
  }
  return discarded;
}

std::size_t reject_all_pending(const char* reason) {
  const std::size_t discarded = pending_measurements.discard_all();
  rejected_count += static_cast<std::uint32_t>(discarded);
  if (discarded > 0U) {
    Serial.printf(
        "[queue] rejected all count=%u reason=%s\n",
        static_cast<unsigned>(discarded),
        reason);
  }
  return discarded;
}

bool reject_front_pending(const char* reason) {
  PendingMeasurement* measurement = pending_measurements.front();
  if (measurement == nullptr) {
    return false;
  }
  const std::uint32_t session_id = measurement->session_id;
  char source_message_id[airmonitor::kSourceMessageIdCapacity]{};
  std::strncpy(
      source_message_id,
      measurement->source_message_id,
      sizeof(source_message_id) - 1U);
  pending_measurements.discard_front();
  ++rejected_count;
  Serial.printf(
      "[queue] rejected session=%u source=%s reason=%s\n",
      static_cast<unsigned>(session_id),
      source_message_id,
      reason);
  return true;
}

void maintain_time(std::uint32_t now_ms) {
  char timestamp[airmonitor::kTimestampCapacity]{};
  time_synchronized = airmonitor::format_utc_timestamp(
      time(nullptr), timestamp, sizeof(timestamp));
  if (time_synchronized || !wifi_connected() ||
      !airmonitor::deadline_reached(now_ms, next_ntp_attempt_ms)) {
    return;
  }
  next_ntp_attempt_ms = now_ms + kNtpRetryIntervalMs;
  configTime(
      0,
      0,
      AIRMONITOR_NTP_SERVER_1,
      AIRMONITOR_NTP_SERVER_2,
      AIRMONITOR_NTP_SERVER_3);
  Serial.println("[time] NTP synchronization requested");
}

void apply_session_check(
    const ActiveSessionCheck& check,
    std::uint32_t now_ms) {
  last_http_status = check.result.http_status;
  if (check.active) {
    const bool session_changed = session_state.confirm_active(check.session_id);
    if (session_changed) {
      session_capture_ready_ms =
          now_ms + AIRMONITOR_MEASUREMENT_INTERVAL_MS;
      next_measurement_ms = session_capture_ready_ms;
      display.show_message("SESSION ACTIVE");
      Serial.printf(
          "[session] active id=%u\n",
          static_cast<unsigned>(check.session_id));
    }
    return;
  }

  if (check.result.http_status == 404 &&
      same_error_code(check.result, "active_session_not_found")) {
    const bool had_confirmed_session = session_state.has_confirmed_session();
    session_state.confirm_no_active();
    const std::size_t discarded =
        reject_all_pending("active_session_not_found");
    if (had_confirmed_session || discarded > 0U) {
      display.show_message("SESSION ENDED");
    }
    session_capture_ready_ms = 0;
    return;
  }

  session_state.invalidate_remote();
  if (same_error_code(check.result, "device_not_found") ||
      same_error_code(check.result, "device_inactive")) {
    device_accepted = false;
    session_state.clear();
    session_capture_ready_ms = 0;
    reject_all_pending(check.result.error_code);
    next_device_check_ms = now_ms;
    return;
  }
  if (is_temporary_api_failure(check.result)) {
    api_available = false;
    next_health_check_ms = now_ms + kHealthRecoveryIntervalMs;
  }
}

// Returns true when this loop performed a bounded HTTP request.
bool service_api(std::uint32_t now_ms) {
  if (!wifi_connected() || !api_client.configuration_valid()) {
    return false;
  }

  if (airmonitor::deadline_reached(now_ms, next_health_check_ms)) {
    const HealthCheck health = api_client.check_health();
    last_http_status = health.result.http_status;
    api_available = health.healthy;
    if (!api_available) {
      device_accepted = false;
      session_state.invalidate_remote();
      next_device_check_ms = now_ms;
      next_session_poll_ms = now_ms;
    }
    next_health_check_ms =
        now_ms + (api_available ? kHealthIntervalMs
                                : kHealthRecoveryIntervalMs);
    return true;
  }

  if (api_available &&
      airmonitor::deadline_reached(now_ms, next_device_check_ms)) {
    const airmonitor::DeviceVerification verification =
        api_client.verify_device();
    last_http_status = verification.result.http_status;
    device_accepted = verification.accepted;
    if (!device_accepted) {
      const bool temporary_failure =
          !verification.response_valid ||
          is_temporary_api_failure(verification.result);
      session_state.invalidate_remote();
      if (temporary_failure) {
        api_available = false;
        next_health_check_ms = now_ms + kHealthRecoveryIntervalMs;
      } else {
        session_state.clear();
        session_capture_ready_ms = 0;
        reject_all_pending("device_verification_rejected");
        display.show_message("DEVICE REJECTED");
      }
    }
    next_device_check_ms = now_ms + kDeviceVerificationIntervalMs;
    return true;
  }

  if (api_available && device_accepted &&
      airmonitor::deadline_reached(now_ms, next_session_poll_ms)) {
    apply_session_check(api_client.get_active_session(), now_ms);
    next_session_poll_ms = now_ms + AIRMONITOR_SESSION_POLL_INTERVAL_MS;
    return true;
  }
  return false;
}

RunState current_run_state() {
  return airmonitor::resolve_run_state(
      wifi_connected(),
      api_available,
      device_accepted,
      time_synchronized,
      session_state.remote_session_active());
}

bool capture_measurement(std::uint32_t now_ms, bool manual) {
  const bool interval_ready =
      airmonitor::deadline_reached(now_ms, session_capture_ready_ms);
  if (!airmonitor::can_capture_measurement(
          session_state,
          time_synchronized,
          locally_paused,
          interval_ready)) {
    if (manual) {
      if (!session_state.has_confirmed_session()) {
        display.show_message("NOT MEASURING");
      } else if (!time_synchronized) {
        display.show_message("SYNC TIME");
      } else if (locally_paused) {
        display.show_message("PAUSED");
      } else {
        display.show_message("WAIT INTERVAL");
      }
    }
    return false;
  }
  const airmonitor::SensorSnapshot snapshot = sensors.snapshot();
  if (!airmonitor::has_captureable_sensor_data(snapshot)) {
    if (manual) {
      display.show_message(
          snapshot.pms_status == airmonitor::PmsStatus::warming_up
              ? "PMS WARMUP"
              : "NO SENSOR DATA");
    }
    return false;
  }

  PendingMeasurement measurement{};
  measurement.session_id = session_state.confirmed_session_id();
  measurement.sensors = snapshot;
  if (!airmonitor::format_utc_timestamp(
          time(nullptr),
          measurement.measured_at,
          sizeof(measurement.measured_at))) {
    time_synchronized = false;
    return false;
  }
  ++message_sequence;
  if (!airmonitor::build_source_message_id(
          AIRMONITOR_DEVICE_ID,
          boot_nonce,
          message_sequence,
          measurement.source_message_id,
          sizeof(measurement.source_message_id))) {
    display.show_message("MESSAGE ID ERR");
    return false;
  }

  measurement.next_attempt_at_ms = now_ms;
  std::uint32_t overflow_session_id = 0;
  char overflow_source_message_id[airmonitor::kSourceMessageIdCapacity]{};
  const PendingMeasurement* previous_oldest = pending_measurements.front();
  if (previous_oldest != nullptr &&
      pending_measurements.size() == AIRMONITOR_PENDING_QUEUE_CAPACITY) {
    overflow_session_id = previous_oldest->session_id;
    std::strncpy(
        overflow_source_message_id,
        previous_oldest->source_message_id,
        sizeof(overflow_source_message_id) - 1U);
  }
  const bool overflowed = pending_measurements.push(measurement);
  Serial.printf(
      "[queue] captured session=%u source=%s size=%u remote=%s\n",
      static_cast<unsigned>(measurement.session_id),
      measurement.source_message_id,
      static_cast<unsigned>(pending_measurements.size()),
      wifi_connected() && api_available && device_accepted &&
              session_state.remote_session_active()
          ? "ready"
          : "offline");
  if (overflowed) {
    Serial.printf(
        "[queue] overflow dropped_oldest session=%u source=%s capacity=%u\n",
        static_cast<unsigned>(overflow_session_id),
        overflow_source_message_id,
        static_cast<unsigned>(AIRMONITOR_PENDING_QUEUE_CAPACITY));
    display.show_message("QUEUE OVERFLOW");
  } else {
    display.show_message(manual ? "CAPTURED" : "QUEUED", 900U);
  }
  return true;
}

void handle_retry(
    PendingMeasurement& measurement,
    std::uint32_t now_ms) {
  ++measurement.delivery_attempts;
  if (measurement.delivery_attempts >= airmonitor::kMaxDeliveryAttempts) {
    reject_front_pending("retry_exhausted");
    display.show_message("RETRY DROPPED");
    return;
  }
  measurement.next_attempt_at_ms =
      now_ms + airmonitor::retry_backoff_ms(measurement.delivery_attempts);
  display.show_message("RETRYING", 900U);
}

void deliver_queue(std::uint32_t now_ms) {
  if (!wifi_connected() || !time_synchronized || !api_available ||
      !device_accepted ||
      !session_state.remote_session_active() || pending_measurements.empty()) {
    return;
  }
  PendingMeasurement* measurement = pending_measurements.front();
  if (measurement == nullptr ||
      !airmonitor::deadline_reached(
          now_ms, measurement->next_attempt_at_ms)) {
    return;
  }

  sending = true;
  const ApiResult result = api_client.post_measurement(*measurement);
  sending = false;
  last_http_status = result.http_status;
  const std::uint32_t attempted_session_id = measurement->session_id;
  const DeliveryDisposition disposition =
      airmonitor::classify_delivery(
          result.http_status,
          result.error_code,
          result.response_body_status);
  Serial.printf(
      "[measurement] http=%d code=%s attempt=%u\n",
      result.http_status,
      result.error_code,
      static_cast<unsigned>(measurement->delivery_attempts + 1U));

  if (disposition == DeliveryDisposition::delivered) {
    pending_measurements.pop();
    ++delivered_count;
    last_success_ms = now_ms;
    display.show_message("SENT OK", 900U);
  } else if (disposition == DeliveryDisposition::retry) {
    handle_retry(*measurement, now_ms);
    if (is_temporary_api_failure(result)) {
      api_available = false;
      session_state.invalidate_remote();
      next_health_check_ms = now_ms + kHealthRecoveryIntervalMs;
      next_session_poll_ms = now_ms;
    }
  } else if (disposition == DeliveryDisposition::session_ended) {
    if (same_error_code(result, "active_session_mismatch")) {
      reject_pending_session(
          attempted_session_id, "active_session_mismatch");
      if (session_state.reject_session(attempted_session_id)) {
        session_capture_ready_ms = 0;
      }
      display.show_message("STALE DROPPED");
    } else {
      session_state.confirm_no_active();
      session_capture_ready_ms = 0;
      reject_all_pending("active_session_not_found");
      display.show_message("SESSION ENDED");
    }
    next_session_poll_ms = now_ms;
  } else {
    const bool identity_error =
        same_error_code(result, "device_inactive") ||
        same_error_code(result, "device_not_found");
    reject_front_pending(
        result.response_body_status ==
                airmonitor::ResponseBodyStatus::too_large
            ? "response_too_large"
            : "permanent_http_rejection");
    display.show_message("PAYLOAD REJECTED");
    if (identity_error) {
      device_accepted = false;
      session_state.clear();
      session_capture_ready_ms = 0;
      reject_all_pending(result.error_code);
    }
  }
}

DisplayStatus build_display_status() {
  DisplayStatus status{};
  status.run_state = current_run_state();
  status.wifi_connected = wifi_connected();
  status.sending = sending;
  status.locally_paused = locally_paused;
  status.last_http_status = last_http_status;
  status.active_session_id = session_state.confirmed_session_id();
  status.delivered_count = delivered_count;
  status.last_success_ms = last_success_ms;
  status.queue_size = pending_measurements.size();
  status.dropped_count = pending_measurements.dropped();
  status.rejected_count = rejected_count;
  return status;
}

}  // namespace

void setup() {
  display.begin();
  Serial.begin(115200);

  WiFi.mode(WIFI_STA);
  boot_nonce =
      (static_cast<std::uint64_t>(esp_random()) << 32U) | esp_random();
  WiFi.persistent(false);
  WiFi.setAutoReconnect(true);
  WiFi.begin(AIRMONITOR_WIFI_SSID, AIRMONITOR_WIFI_PASSWORD);

  const bool sht_initialized = sensors.begin();
  Serial.printf(
      "[boot] firmware=v2 device_id=%u sht=%s api_config=%s\n",
      static_cast<unsigned>(AIRMONITOR_DEVICE_ID),
      sht_initialized ? "ok" : "error",
      api_client.configuration_valid() ? "ok" : "error");
  if (!api_client.configuration_valid()) {
    display.show_message("CONFIG ERROR", 5000U);
  }
  display.render(millis(), sensors.snapshot(), build_display_status(), true);
}

void loop() {
  const std::uint32_t now_ms = millis();
  sensors.poll(now_ms);
  log_sensor_snapshot(now_ms);

  const ButtonActions buttons = display.poll_buttons();
  if (buttons.pause_toggled) {
    locally_paused = !locally_paused;
    display.show_message(locally_paused ? "PAUSED" : "RESUMED");
  }

  maintain_wifi(now_ms);
  maintain_time(now_ms);
  const bool api_request_performed = service_api(now_ms);

  if (buttons.manual_capture) {
    capture_measurement(now_ms, true);
  }
  if (airmonitor::deadline_reached(now_ms, next_measurement_ms)) {
    next_measurement_ms = now_ms + AIRMONITOR_MEASUREMENT_INTERVAL_MS;
    capture_measurement(now_ms, false);
  }
  if (!api_request_performed) {
    deliver_queue(now_ms);
  }

  display.render(now_ms, sensors.snapshot(), build_display_status());
  delay(5);
}
