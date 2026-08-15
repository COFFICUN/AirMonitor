#include "airmonitor/api_client.h"

#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <WiFiClient.h>
#include <WiFiClientSecure.h>

#include <cstring>

namespace airmonitor {

namespace {

constexpr std::size_t kResponseReadChunkBytes = 128;
constexpr std::size_t kChunkHeaderCapacity = 32;
constexpr char kTransferEncodingHeader[] = "Transfer-Encoding";

bool read_stream_byte(
    WiFiClient& stream,
    std::uint32_t deadline_ms,
    std::uint8_t& value) {
  while (!deadline_reached(millis(), deadline_ms)) {
    if (stream.available() > 0U) {
      const int received = stream.read();
      if (received >= 0) {
        value = static_cast<std::uint8_t>(received);
        return true;
      }
    } else if (!stream.connected()) {
      return false;
    }
    delay(1);
  }
  return false;
}

bool read_stream_exact(
    WiFiClient& stream,
    std::uint32_t deadline_ms,
    std::uint8_t* output,
    std::size_t length) {
  for (std::size_t index = 0; index < length; ++index) {
    if (!read_stream_byte(stream, deadline_ms, output[index])) {
      return false;
    }
  }
  return true;
}

ResponseBodyStatus read_chunk_header(
    WiFiClient& stream,
    std::uint32_t deadline_ms,
    std::size_t& chunk_size) {
  char header[kChunkHeaderCapacity]{};
  std::size_t length = 0;
  while (true) {
    std::uint8_t value = 0;
    if (!read_stream_byte(stream, deadline_ms, value)) {
      return ResponseBodyStatus::read_error;
    }
    if (value == '\n') {
      if (length > 0U && header[length - 1U] == '\r') {
        --length;
      }
      return parse_http_chunk_size(header, length, &chunk_size)
                 ? ResponseBodyStatus::complete
                 : ResponseBodyStatus::read_error;
    }
    if (length >= sizeof(header) - 1U) {
      return ResponseBodyStatus::too_large;
    }
    header[length++] = static_cast<char>(value);
  }
}

ResponseBodyStatus read_chunked_response(
    WiFiClient& stream,
    std::uint32_t deadline_ms,
    BoundedResponseBody<kMaximumApiResponseBytes>& body) {
  while (true) {
    std::size_t chunk_size = 0;
    const ResponseBodyStatus header_status =
        read_chunk_header(stream, deadline_ms, chunk_size);
    if (header_status != ResponseBodyStatus::complete) {
      return header_status;
    }
    if (chunk_size == 0U) {
      return ResponseBodyStatus::complete;
    }
    if (chunk_size > body.remaining()) {
      body.mark_overflowed();
      return ResponseBodyStatus::too_large;
    }

    std::size_t remaining = chunk_size;
    std::uint8_t chunk[kResponseReadChunkBytes]{};
    while (remaining > 0U) {
      const std::size_t read_size =
          remaining > sizeof(chunk) ? sizeof(chunk) : remaining;
      if (!read_stream_exact(
              stream, deadline_ms, chunk, read_size) ||
          !body.append(
              reinterpret_cast<const char*>(chunk), read_size)) {
        return finalize_response_body(-1, -1, body.overflowed());
      }
      remaining -= read_size;
    }

    std::uint8_t trailing[2]{};
    if (!read_stream_exact(
            stream, deadline_ms, trailing, sizeof(trailing)) ||
        trailing[0] != '\r' || trailing[1] != '\n') {
      return ResponseBodyStatus::read_error;
    }
  }
}

ResponseBodyStatus read_identity_response(
    HTTPClient& http,
    int expected_length,
    std::uint32_t deadline_ms,
    BoundedResponseBody<kMaximumApiResponseBytes>& body) {
  WiFiClient* stream = http.getStreamPtr();
  if (stream == nullptr) {
    return ResponseBodyStatus::read_error;
  }

  std::uint8_t chunk[kResponseReadChunkBytes]{};
  int bytes_read = 0;
  while (expected_length < 0 || bytes_read < expected_length) {
    const std::size_t available = stream->available();
    if (available > 0U) {
      if (body.remaining() == 0U) {
        body.append("x", 1U);
        return ResponseBodyStatus::too_large;
      }
      std::size_t read_size = available;
      if (read_size > sizeof(chunk)) {
        read_size = sizeof(chunk);
      }
      if (read_size > body.remaining()) {
        read_size = body.remaining();
      }
      if (expected_length >= 0) {
        const std::size_t expected_remaining =
            static_cast<std::size_t>(expected_length - bytes_read);
        if (read_size > expected_remaining) {
          read_size = expected_remaining;
        }
      }

      const int received = stream->read(chunk, read_size);
      if (received <= 0 ||
          !body.append(
              reinterpret_cast<const char*>(chunk),
              static_cast<std::size_t>(received))) {
        return finalize_response_body(
            expected_length, received, body.overflowed());
      }
      bytes_read += received;
      continue;
    }

    if (expected_length < 0 && !stream->connected()) {
      break;
    }
    if (deadline_reached(millis(), deadline_ms)) {
      return ResponseBodyStatus::read_error;
    }
    delay(1);
  }
  return finalize_response_body(
      expected_length, bytes_read, body.overflowed());
}

ResponseBodyStatus read_response_body(
    HTTPClient& http,
    std::uint16_t timeout_ms,
    BoundedResponseBody<kMaximumApiResponseBytes>& body) {
  body.clear();
  const int expected_length = http.getSize();
  if (expected_length >
      static_cast<int>(kMaximumApiResponseBytes)) {
    return ResponseBodyStatus::too_large;
  }
  if (expected_length == 0) {
    return ResponseBodyStatus::complete;
  }

  WiFiClient* stream = http.getStreamPtr();
  if (stream == nullptr) {
    return ResponseBodyStatus::read_error;
  }
  const std::uint32_t deadline_ms = millis() + timeout_ms;

  const String transfer_encoding = http.header(kTransferEncodingHeader);
  if (transfer_encoding.equalsIgnoreCase("chunked")) {
    return read_chunked_response(*stream, deadline_ms, body);
  }
  return read_identity_response(http, expected_length, deadline_ms, body);
}

void copy_error_code(ApiResult& result, const JsonDocument& document) {
  const char* code = document["error"]["code"] | "";
  std::strncpy(
      result.error_code,
      code,
      sizeof(result.error_code) - 1U);
}

bool parse_response(const String& body, JsonDocument& document) {
  return !body.isEmpty() && deserializeJson(document, body) ==
                                DeserializationError::Ok;
}

const char* pms_validation_note(PmsStatus status) {
  switch (status) {
    case PmsStatus::warming_up:
      return "PMSA003 warming up";
    case PmsStatus::invalid_frame:
      return "PMSA003 inconsistent frame";
    case PmsStatus::stale:
      return "PMSA003 data stale";
    case PmsStatus::ready:
      return "PMSA003 unavailable";
  }
  return "PMSA003 unavailable";
}

void set_sensor_payload(
    JsonDocument& document,
    const SensorSnapshot& sensors) {
  if (sensors.sht_ok) {
    document["temperature"] = sensors.temperature;
    document["humidity"] = sensors.humidity;
  } else {
    document["temperature"] = nullptr;
    document["humidity"] = nullptr;
  }

  if (sensors.pms_ok) {
    document["pm1"] = sensors.pm1;
    document["pm25"] = sensors.pm25;
    document["pm10"] = sensors.pm10;
    document["pc0_3"] = sensors.pc0_3;
    document["pc0_5"] = sensors.pc0_5;
    document["pc1_0"] = sensors.pc1_0;
    document["pc2_5"] = sensors.pc2_5;
    document["pc5_0"] = sensors.pc5_0;
    document["pc10"] = sensors.pc10;
  } else {
    document["pm1"] = nullptr;
    document["pm25"] = nullptr;
    document["pm10"] = nullptr;
    document["pc0_3"] = nullptr;
    document["pc0_5"] = nullptr;
    document["pc1_0"] = nullptr;
    document["pc2_5"] = nullptr;
    document["pc5_0"] = nullptr;
    document["pc10"] = nullptr;
  }

  document["latitude"] = nullptr;
  document["longitude"] = nullptr;
  document["is_valid"] = sensors.sht_ok && sensors.pms_ok;
  if (sensors.sht_ok && sensors.pms_ok) {
    document["validation_note"] = nullptr;
  } else if (!sensors.sht_ok) {
    document["validation_note"] = "SHT30 unavailable";
  } else {
    document["validation_note"] = pms_validation_note(sensors.pms_status);
  }
}

}  // namespace

ApiClient::ApiClient(
    const char* base_url,
    std::uint32_t device_id,
    const char* expected_device_uid,
    const char* ca_certificate,
    std::uint16_t timeout_ms)
    : base_url_(base_url == nullptr ? "" : base_url),
      device_id_(device_id),
      expected_device_uid_(
          expected_device_uid == nullptr ? "" : expected_device_uid),
      ca_certificate_(ca_certificate == nullptr ? "" : ca_certificate),
      timeout_ms_(timeout_ms) {
  while (base_url_.endsWith("/")) {
    base_url_.remove(base_url_.length() - 1U);
  }
  uses_tls_ = base_url_.startsWith("https://");
  const bool supported_scheme =
      uses_tls_ || base_url_.startsWith("http://");
  configuration_valid_ =
      supported_scheme && device_id_ > 0U && !expected_device_uid_.isEmpty() &&
      timeout_ms_ > 0U && (!uses_tls_ || ca_certificate_[0] != '\0');
}

bool ApiClient::configuration_valid() const {
  return configuration_valid_;
}

HealthCheck ApiClient::check_health() {
  HealthCheck check{};
  String response;
  check.result = request(Method::get, "/health", nullptr, response);
  JsonDocument document;
  check.healthy = check.result.http_status == 200 &&
                  parse_response(response, document) &&
                  String(document["status"] | "") == "ok";
  return check;
}

DeviceVerification ApiClient::verify_device() {
  DeviceVerification verification{};
  String response;
  verification.result =
      request(Method::get, device_path(""), nullptr, response);
  JsonDocument document;
  verification.response_valid = parse_response(response, document);
  if (verification.response_valid) {
    if (verification.result.http_status >= 400) {
      copy_error_code(verification.result, document);
    } else if (verification.result.http_status == 200) {
      const std::uint32_t response_id = document["id"] | 0U;
      const String response_uid = document["device_uid"] | "";
      verification.active = document["is_active"] | false;
      verification.accepted = response_id == device_id_ &&
                              response_uid == expected_device_uid_ &&
                              verification.active;
    }
  }
  return verification;
}

ActiveSessionCheck ApiClient::get_active_session() {
  ActiveSessionCheck check{};
  String response;
  check.result = request(
      Method::get,
      device_path("/sessions/active"),
      nullptr,
      response);
  JsonDocument document;
  if (!parse_response(response, document)) {
    return check;
  }
  if (check.result.http_status >= 400) {
    copy_error_code(check.result, document);
    return check;
  }
  const String status = document["status"] | "";
  const std::uint32_t response_device_id = document["device_id"] | 0U;
  check.session_id = document["id"] | 0U;
  check.active = check.result.http_status == 200 && status == "active" &&
                 response_device_id == device_id_ && check.session_id > 0U;
  return check;
}

ApiResult ApiClient::post_measurement(
    const PendingMeasurement& measurement) {
  if (!measurement.sensors.sht_ok && !measurement.sensors.pms_ok) {
    ApiResult invalid{};
    invalid.http_status = 422;
    std::strncpy(
        invalid.error_code,
        "no_valid_sensor_data",
        sizeof(invalid.error_code) - 1U);
    return invalid;
  }

  JsonDocument document;
  document["session_id"] = measurement.session_id;
  document["measured_at"] = measurement.measured_at;
  document["source_message_id"] = measurement.source_message_id;
  set_sensor_payload(document, measurement.sensors);
  String payload;
  serializeJson(document, payload);

  String response;
  ApiResult result = request(
      Method::post,
      device_path("/measurements"),
      &payload,
      response);
  JsonDocument response_document;
  if (result.http_status >= 400 &&
      parse_response(response, response_document)) {
    copy_error_code(result, response_document);
  }
  return result;
}

ApiResult ApiClient::request(
    Method method,
    const String& path,
    const String* request_body,
    String& response_body) {
  ApiResult result{};
  if (!configuration_valid_) {
    result.http_status = 400;
    std::strncpy(
        result.error_code,
        "firmware_configuration_invalid",
        sizeof(result.error_code) - 1U);
    return result;
  }

  HTTPClient http;
  http.setConnectTimeout(timeout_ms_);
  http.setTimeout(timeout_ms_);
  const String url = base_url_ + path;
  WiFiClient plain_client;
  WiFiClientSecure secure_client;
  bool began = false;
  if (uses_tls_) {
    secure_client.setCACert(ca_certificate_);
    began = http.begin(secure_client, url);
  } else {
    began = http.begin(plain_client, url);
  }
  if (!began) {
    result.http_status = -1;
    return result;
  }

  const char* response_headers[] = {kTransferEncodingHeader};
  http.collectHeaders(response_headers, 1U);

  http.addHeader("Accept", "application/json");
  if (method == Method::post) {
    http.addHeader("Content-Type", "application/json");
    result.http_status = http.POST(
        request_body == nullptr ? String("{}") : *request_body);
  } else {
    result.http_status = http.GET();
  }

  if (result.http_status > 0) {
    result.response_body_status =
        read_response_body(http, timeout_ms_, response_buffer_);
    if (result.response_body_status == ResponseBodyStatus::complete) {
      response_body = response_buffer_.c_str();
    } else {
      response_body = "";
    }
  } else {
    result.response_body_status = ResponseBodyStatus::read_error;
  }
  http.end();
  return result;
}

String ApiClient::device_path(const char* suffix) const {
  String path = "/api/v1/devices/";
  path += device_id_;
  path += suffix;
  return path;
}

}  // namespace airmonitor
