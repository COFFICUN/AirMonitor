#include "airmonitor/firmware_logic.h"

#include <cstdio>
#include <cstring>
#include <limits>

namespace airmonitor {

namespace {

constexpr std::time_t kMinimumSynchronizedEpoch = 1704067200;
constexpr std::uint32_t kMaximumBackoffMs = 30000U;

}  // namespace

DeliveryDisposition classify_delivery(
    int http_status,
    const char* error_code,
    ResponseBodyStatus response_body_status) {
  if (http_status >= 200 && http_status < 300) {
    return DeliveryDisposition::delivered;
  }
  if (response_body_status == ResponseBodyStatus::read_error) {
    return DeliveryDisposition::retry;
  }
  if (http_status == 409 && error_code != nullptr &&
      std::strcmp(error_code, "duplicate_source_message") == 0) {
    return DeliveryDisposition::delivered;
  }
  if (http_status == 404 && error_code != nullptr &&
      std::strcmp(error_code, "active_session_not_found") == 0) {
    return DeliveryDisposition::session_ended;
  }
  if (http_status == 409 && error_code != nullptr &&
      std::strcmp(error_code, "active_session_mismatch") == 0) {
    return DeliveryDisposition::session_ended;
  }
  if (http_status <= 0 || http_status == 408 || http_status == 425 ||
      http_status == 429 || (http_status >= 500 && http_status < 600)) {
    return DeliveryDisposition::retry;
  }
  return DeliveryDisposition::permanent_failure;
}

ResponseBodyStatus finalize_response_body(
    int expected_length,
    int bytes_read,
    bool overflowed) {
  if (overflowed) {
    return ResponseBodyStatus::too_large;
  }
  if (bytes_read < 0 ||
      (expected_length >= 0 && bytes_read != expected_length)) {
    return ResponseBodyStatus::read_error;
  }
  return ResponseBodyStatus::complete;
}

bool parse_http_chunk_size(
    const char* line,
    std::size_t line_length,
    std::size_t* chunk_size) {
  if (line == nullptr || chunk_size == nullptr || line_length == 0U) {
    return false;
  }

  std::size_t value = 0;
  std::size_t digits = 0;
  for (std::size_t index = 0; index < line_length; ++index) {
    const char character = line[index];
    if (character == ';' || character == ' ' || character == '\t') {
      break;
    }
    unsigned int digit = 0;
    if (character >= '0' && character <= '9') {
      digit = static_cast<unsigned int>(character - '0');
    } else if (character >= 'a' && character <= 'f') {
      digit = static_cast<unsigned int>(character - 'a' + 10);
    } else if (character >= 'A' && character <= 'F') {
      digit = static_cast<unsigned int>(character - 'A' + 10);
    } else {
      return false;
    }
    if (value >
        (std::numeric_limits<std::size_t>::max() - digit) / 16U) {
      return false;
    }
    value = value * 16U + digit;
    ++digits;
  }
  if (digits == 0U) {
    return false;
  }
  *chunk_size = value;
  return true;
}

bool SessionState::confirm_active(std::uint32_t session_id) {
  if (session_id == 0U) {
    invalidate_remote();
    return false;
  }
  const bool changed = confirmed_session_id_ != session_id;
  confirmed_session_id_ = session_id;
  remote_active_session_id_ = session_id;
  remote_session_fresh_ = true;
  return changed;
}

void SessionState::confirm_no_active() {
  confirmed_session_id_ = 0;
  remote_active_session_id_ = 0;
  remote_session_fresh_ = true;
}

void SessionState::invalidate_remote() {
  remote_active_session_id_ = 0;
  remote_session_fresh_ = false;
}

void SessionState::clear() {
  confirmed_session_id_ = 0;
  invalidate_remote();
}

bool SessionState::reject_session(std::uint32_t session_id) {
  const bool rejected_confirmed_session =
      session_id > 0U && confirmed_session_id_ == session_id;
  if (rejected_confirmed_session) {
    confirmed_session_id_ = 0;
  }
  if (session_id > 0U && remote_active_session_id_ == session_id) {
    invalidate_remote();
  }
  return rejected_confirmed_session;
}

std::uint32_t retry_backoff_ms(std::uint8_t failed_attempts) {
  if (failed_attempts == 0U) {
    failed_attempts = 1U;
  }
  const std::uint8_t shift = failed_attempts > 5U ? 4U : failed_attempts - 1U;
  const std::uint32_t delay_ms = 2000U << shift;
  return delay_ms > kMaximumBackoffMs ? kMaximumBackoffMs : delay_ms;
}

bool deadline_reached(std::uint32_t now_ms, std::uint32_t deadline_ms) {
  return static_cast<std::int32_t>(now_ms - deadline_ms) >= 0;
}

bool format_utc_timestamp(
    std::time_t epoch_seconds,
    char* output,
    std::size_t output_size) {
  if (output == nullptr || output_size < kTimestampCapacity ||
      epoch_seconds < kMinimumSynchronizedEpoch) {
    return false;
  }

  std::tm utc{};
#if defined(_WIN32)
  if (gmtime_s(&utc, &epoch_seconds) != 0) {
    return false;
  }
#else
  if (gmtime_r(&epoch_seconds, &utc) == nullptr) {
    return false;
  }
#endif
  return std::strftime(
             output,
             output_size,
             "%Y-%m-%dT%H:%M:%SZ",
             &utc) == kTimestampCapacity - 1U;
}

bool build_source_message_id(
    std::uint32_t device_id,
    std::uint64_t boot_nonce,
    std::uint32_t sequence,
    char* output,
    std::size_t output_size) {
  if (output == nullptr || output_size == 0U || device_id == 0U) {
    return false;
  }
  const int written = std::snprintf(
      output,
      output_size,
      "am2-%08u-%016llx-%08x",
      static_cast<unsigned int>(device_id),
      static_cast<unsigned long long>(boot_nonce),
      static_cast<unsigned int>(sequence));
  return written > 0 && static_cast<std::size_t>(written) < output_size;
}

RunState resolve_run_state(
    bool wifi_connected,
    bool api_available,
    bool device_accepted,
    bool time_synchronized,
    bool active_session) {
  if (!wifi_connected) {
    return RunState::wifi_unavailable;
  }
  if (!time_synchronized) {
    return RunState::time_unsynchronized;
  }
  if (!api_available) {
    return RunState::api_unavailable;
  }
  if (!device_accepted) {
    return RunState::device_rejected;
  }
  return active_session ? RunState::measuring
                        : RunState::waiting_for_session;
}

PmsStatus classify_pms_frame(
    const PmsFrame& frame,
    std::uint32_t now_ms,
    std::uint32_t sensor_started_at_ms) {
  if (now_ms - sensor_started_at_ms < kPmsWarmupMs) {
    return PmsStatus::warming_up;
  }
  if (frame.pm1 > frame.pm25 || frame.pm25 > frame.pm10) {
    return PmsStatus::invalid_frame;
  }
  if (frame.pc0_3 < frame.pc0_5 || frame.pc0_5 < frame.pc1_0 ||
      frame.pc1_0 < frame.pc2_5 || frame.pc2_5 < frame.pc5_0 ||
      frame.pc5_0 < frame.pc10) {
    return PmsStatus::invalid_frame;
  }
  return PmsStatus::ready;
}

PmsStatus update_pms_snapshot(
    SensorSnapshot& snapshot,
    const PmsFrame& frame,
    std::uint32_t now_ms,
    std::uint32_t sensor_started_at_ms) {
  const PmsStatus status =
      classify_pms_frame(frame, now_ms, sensor_started_at_ms);
  snapshot.pms_status = status;
  snapshot.pms_ok = status == PmsStatus::ready;
  if (!snapshot.pms_ok) {
    return status;
  }

  snapshot.pm1 = frame.pm1;
  snapshot.pm25 = frame.pm25;
  snapshot.pm10 = frame.pm10;
  snapshot.pc0_3 = frame.pc0_3;
  snapshot.pc0_5 = frame.pc0_5;
  snapshot.pc1_0 = frame.pc1_0;
  snapshot.pc2_5 = frame.pc2_5;
  snapshot.pc5_0 = frame.pc5_0;
  snapshot.pc10 = frame.pc10;
  return status;
}

bool has_captureable_sensor_data(const SensorSnapshot& snapshot) {
  if (snapshot.pms_status == PmsStatus::warming_up) {
    return false;
  }
  return snapshot.sht_ok || snapshot.pms_ok;
}

bool can_capture_measurement(
    const SessionState& session,
    bool time_synchronized,
    bool locally_paused,
    bool interval_ready) {
  return session.has_confirmed_session() && time_synchronized &&
         !locally_paused && interval_ready;
}

}  // namespace airmonitor
