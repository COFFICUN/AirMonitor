#pragma once

#include <Arduino.h>

#include "airmonitor/firmware_logic.h"

namespace airmonitor {

constexpr std::size_t kApiErrorCodeCapacity = 48;
constexpr std::size_t kMaximumApiResponseBytes = 2048;

struct ApiResult {
  int http_status = 0;
  char error_code[kApiErrorCodeCapacity] = {};
  ResponseBodyStatus response_body_status = ResponseBodyStatus::complete;
};

struct HealthCheck {
  ApiResult result{};
  bool healthy = false;
};

struct DeviceVerification {
  ApiResult result{};
  bool response_valid = false;
  bool accepted = false;
  bool active = false;
};

struct ActiveSessionCheck {
  ApiResult result{};
  bool active = false;
  std::uint32_t session_id = 0;
};

class ApiClient {
 public:
  ApiClient(
      const char* base_url,
      std::uint32_t device_id,
      const char* expected_device_uid,
      const char* ca_certificate,
      std::uint16_t timeout_ms);

  bool configuration_valid() const;
  HealthCheck check_health();
  DeviceVerification verify_device();
  ActiveSessionCheck get_active_session();
  ApiResult post_measurement(const PendingMeasurement& measurement);

 private:
  enum class Method { get, post };

  ApiResult request(
      Method method,
      const String& path,
      const String* request_body,
      String& response_body);
  String device_path(const char* suffix) const;

  String base_url_;
  std::uint32_t device_id_;
  String expected_device_uid_;
  const char* ca_certificate_;
  std::uint16_t timeout_ms_;
  BoundedResponseBody<kMaximumApiResponseBytes> response_buffer_{};
  bool uses_tls_ = false;
  bool configuration_valid_ = false;
};

}  // namespace airmonitor
