#pragma once

#include <cstddef>
#include <cstdint>
#include <cstring>
#include <ctime>

namespace airmonitor {

constexpr std::size_t kTimestampCapacity = 21;
constexpr std::size_t kSourceMessageIdCapacity = 48;
constexpr std::uint8_t kMaxDeliveryAttempts = 6;
constexpr std::uint32_t kPmsWarmupMs = 30000U;

enum class DeliveryDisposition {
  delivered,
  retry,
  permanent_failure,
  session_ended,
};

enum class ResponseBodyStatus {
  complete,
  too_large,
  read_error,
};

enum class RunState {
  wifi_unavailable,
  api_unavailable,
  device_rejected,
  time_unsynchronized,
  waiting_for_session,
  measuring,
};

enum class PmsStatus {
  warming_up,
  ready,
  invalid_frame,
  stale,
};

struct PmsFrame {
  std::uint16_t pm1 = 0;
  std::uint16_t pm25 = 0;
  std::uint16_t pm10 = 0;
  std::uint16_t pc0_3 = 0;
  std::uint16_t pc0_5 = 0;
  std::uint16_t pc1_0 = 0;
  std::uint16_t pc2_5 = 0;
  std::uint16_t pc5_0 = 0;
  std::uint16_t pc10 = 0;
};

struct SensorSnapshot {
  float temperature = 0.0F;
  float humidity = 0.0F;
  float pm1 = 0.0F;
  float pm25 = 0.0F;
  float pm10 = 0.0F;
  std::int32_t pc0_3 = 0;
  std::int32_t pc0_5 = 0;
  std::int32_t pc1_0 = 0;
  std::int32_t pc2_5 = 0;
  std::int32_t pc5_0 = 0;
  std::int32_t pc10 = 0;
  bool sht_ok = false;
  bool pms_ok = false;
  PmsStatus pms_status = PmsStatus::warming_up;
};

struct PendingMeasurement {
  std::uint32_t session_id = 0;
  char measured_at[kTimestampCapacity] = {};
  char source_message_id[kSourceMessageIdCapacity] = {};
  SensorSnapshot sensors{};
  std::uint8_t delivery_attempts = 0;
  std::uint32_t next_attempt_at_ms = 0;
};

class SessionState {
 public:
  bool confirm_active(std::uint32_t session_id);
  void confirm_no_active();
  void invalidate_remote();
  void clear();
  bool reject_session(std::uint32_t session_id);

  bool has_confirmed_session() const {
    return confirmed_session_id_ > 0U;
  }
  std::uint32_t confirmed_session_id() const {
    return confirmed_session_id_;
  }
  bool remote_session_active() const {
    return remote_session_fresh_ && remote_active_session_id_ > 0U;
  }
  std::uint32_t remote_active_session_id() const {
    return remote_active_session_id_;
  }

 private:
  std::uint32_t confirmed_session_id_ = 0;
  std::uint32_t remote_active_session_id_ = 0;
  bool remote_session_fresh_ = false;
};

DeliveryDisposition classify_delivery(
    int http_status,
    const char* error_code,
    ResponseBodyStatus response_body_status = ResponseBodyStatus::complete);
ResponseBodyStatus finalize_response_body(
    int expected_length,
    int bytes_read,
    bool overflowed);
bool parse_http_chunk_size(
    const char* line,
    std::size_t line_length,
    std::size_t* chunk_size);
std::uint32_t retry_backoff_ms(std::uint8_t failed_attempts);
bool deadline_reached(std::uint32_t now_ms, std::uint32_t deadline_ms);
bool format_utc_timestamp(
    std::time_t epoch_seconds,
    char* output,
    std::size_t output_size);
bool build_source_message_id(
    std::uint32_t device_id,
    std::uint64_t boot_nonce,
    std::uint32_t sequence,
    char* output,
    std::size_t output_size);
RunState resolve_run_state(
    bool wifi_connected,
    bool api_available,
    bool device_accepted,
    bool time_synchronized,
    bool active_session);
PmsStatus classify_pms_frame(
    const PmsFrame& frame,
    std::uint32_t now_ms,
    std::uint32_t sensor_started_at_ms);
PmsStatus update_pms_snapshot(
    SensorSnapshot& snapshot,
    const PmsFrame& frame,
    std::uint32_t now_ms,
    std::uint32_t sensor_started_at_ms);
bool has_captureable_sensor_data(const SensorSnapshot& snapshot);
bool can_capture_measurement(
    const SessionState& session,
    bool time_synchronized,
    bool locally_paused,
    bool interval_ready);

template <std::size_t Capacity>
class BoundedResponseBody {
 public:
  static_assert(Capacity > 0, "Response capacity must be positive");

  void clear() {
    size_ = 0;
    overflowed_ = false;
    data_[0] = '\0';
  }

  bool append(const char* data, std::size_t length) {
    if (data == nullptr && length > 0U) {
      return false;
    }
    if (length > Capacity - size_) {
      overflowed_ = true;
      return false;
    }
    if (length > 0U) {
      std::memcpy(data_ + size_, data, length);
      size_ += length;
      data_[size_] = '\0';
    }
    return true;
  }

  const char* c_str() const { return data_; }
  std::size_t size() const { return size_; }
  std::size_t remaining() const { return Capacity - size_; }
  bool overflowed() const { return overflowed_; }
  void mark_overflowed() { overflowed_ = true; }

 private:
  char data_[Capacity + 1U]{};
  std::size_t size_ = 0;
  bool overflowed_ = false;
};

template <std::size_t Capacity>
class PendingQueue {
 public:
  static_assert(Capacity > 0, "PendingQueue capacity must be positive");

  bool empty() const { return size_ == 0; }
  std::size_t size() const { return size_; }
  std::uint32_t dropped() const { return dropped_; }

  PendingMeasurement* front() {
    return empty() ? nullptr : &items_[head_];
  }

  const PendingMeasurement* front() const {
    return empty() ? nullptr : &items_[head_];
  }

  void pop() {
    if (empty()) {
      return;
    }
    head_ = (head_ + 1U) % Capacity;
    --size_;
  }

  bool discard_front() {
    if (empty()) {
      return false;
    }
    pop();
    ++dropped_;
    return true;
  }

  bool push(const PendingMeasurement& measurement) {
    bool overflowed = false;
    if (size_ == Capacity) {
      pop();
      ++dropped_;
      overflowed = true;
    }
    const std::size_t tail = (head_ + size_) % Capacity;
    items_[tail] = measurement;
    ++size_;
    return overflowed;
  }

  std::size_t discard_session(std::uint32_t session_id) {
    const std::size_t original_size = size_;
    std::size_t discarded = 0;
    for (std::size_t index = 0; index < original_size; ++index) {
      const PendingMeasurement current = *front();
      pop();
      if (current.session_id == session_id) {
        ++discarded;
      } else {
        push(current);
      }
    }
    dropped_ += static_cast<std::uint32_t>(discarded);
    return discarded;
  }

  std::size_t discard_all() {
    const std::size_t discarded = size_;
    dropped_ += static_cast<std::uint32_t>(size_);
    head_ = 0;
    size_ = 0;
    return discarded;
  }

 private:
  PendingMeasurement items_[Capacity]{};
  std::size_t head_ = 0;
  std::size_t size_ = 0;
  std::uint32_t dropped_ = 0;
};

}  // namespace airmonitor
