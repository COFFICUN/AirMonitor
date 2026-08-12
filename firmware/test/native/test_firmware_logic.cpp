#include "airmonitor/firmware_logic.h"

#include <cassert>
#include <cstring>
#include <iostream>

using airmonitor::DeliveryDisposition;
using airmonitor::PendingMeasurement;
using airmonitor::PendingQueue;
using airmonitor::PmsFrame;
using airmonitor::PmsStatus;
using airmonitor::ResponseBodyStatus;
using airmonitor::RunState;
using airmonitor::SessionState;

namespace {

PendingMeasurement measurement(std::uint32_t session_id, const char* id) {
  PendingMeasurement value{};
  value.session_id = session_id;
  std::strncpy(
      value.source_message_id,
      id,
      sizeof(value.source_message_id) - 1U);
  return value;
}

template <std::size_t Capacity>
bool capture_for_confirmed_session(
    SessionState& session,
    PendingQueue<Capacity>& queue,
    const char* source_message_id) {
  if (!airmonitor::can_capture_measurement(session, true, false, true)) {
    return false;
  }
  queue.push(measurement(session.confirmed_session_id(), source_message_id));
  return true;
}

void test_delivery_classification() {
  assert(airmonitor::classify_delivery(201, nullptr) ==
         DeliveryDisposition::delivered);
  assert(airmonitor::classify_delivery(409, "duplicate_source_message") ==
         DeliveryDisposition::delivered);
  assert(airmonitor::classify_delivery(-1, nullptr) ==
         DeliveryDisposition::retry);
  assert(airmonitor::classify_delivery(408, nullptr) ==
         DeliveryDisposition::retry);
  assert(airmonitor::classify_delivery(429, nullptr) ==
         DeliveryDisposition::retry);
  assert(airmonitor::classify_delivery(503, nullptr) ==
         DeliveryDisposition::retry);
  assert(airmonitor::classify_delivery(404, "active_session_not_found") ==
         DeliveryDisposition::session_ended);
  assert(airmonitor::classify_delivery(409, "active_session_mismatch") ==
         DeliveryDisposition::session_ended);
  assert(airmonitor::classify_delivery(
             409,
             "active_session_mismatch",
             ResponseBodyStatus::read_error) ==
         DeliveryDisposition::retry);
  assert(airmonitor::classify_delivery(
             409,
             nullptr,
             ResponseBodyStatus::too_large) ==
         DeliveryDisposition::permanent_failure);
  assert(airmonitor::classify_delivery(409, "invalid_timestamp") ==
         DeliveryDisposition::permanent_failure);
  assert(airmonitor::classify_delivery(422, "request_validation_error") ==
         DeliveryDisposition::permanent_failure);
}

void test_retry_backoff_is_capped() {
  assert(airmonitor::retry_backoff_ms(1) == 2000U);
  assert(airmonitor::retry_backoff_ms(2) == 4000U);
  assert(airmonitor::retry_backoff_ms(3) == 8000U);
  assert(airmonitor::retry_backoff_ms(4) == 16000U);
  assert(airmonitor::retry_backoff_ms(5) == 30000U);
  assert(airmonitor::retry_backoff_ms(20) == 30000U);
}

void test_millis_deadline_handles_wraparound() {
  assert(airmonitor::deadline_reached(100U, 100U));
  assert(!airmonitor::deadline_reached(99U, 100U));
  assert(airmonitor::deadline_reached(5U, 0xFFFFFFF0U));
}

void test_timestamp_is_utc_iso8601() {
  char timestamp[airmonitor::kTimestampCapacity]{};
  assert(airmonitor::format_utc_timestamp(1786436130, timestamp, sizeof(timestamp)));
  assert(std::strcmp(timestamp, "2026-08-11T08:15:30Z") == 0);
  assert(!airmonitor::format_utc_timestamp(0, timestamp, sizeof(timestamp)));
}

void test_source_message_id_is_stable_and_bounded() {
  char first[airmonitor::kSourceMessageIdCapacity]{};
  char second[airmonitor::kSourceMessageIdCapacity]{};
  assert(airmonitor::build_source_message_id(
      17U, 0x11223344A1B2C3D4ULL, 42U, first, sizeof(first)));
  assert(airmonitor::build_source_message_id(
      17U, 0x11223344A1B2C3D4ULL, 42U, second, sizeof(second)));
  assert(std::strcmp(
             first,
             "am2-00000017-11223344a1b2c3d4-0000002a") == 0);
  assert(std::strcmp(first, second) == 0);
  char too_small[8]{};
  assert(!airmonitor::build_source_message_id(
      17U, 0x11223344A1B2C3D4ULL, 42U, too_small, sizeof(too_small)));
}

void test_queue_is_fifo_and_drops_oldest_when_full() {
  PendingQueue<2> queue;
  assert(!queue.push(measurement(7U, "one")));
  assert(!queue.push(measurement(7U, "two")));
  assert(queue.push(measurement(7U, "three")));
  assert(queue.size() == 2U);
  assert(queue.dropped() == 1U);
  assert(std::strcmp(queue.front()->source_message_id, "two") == 0);
  queue.pop();
  assert(std::strcmp(queue.front()->source_message_id, "three") == 0);
}

void test_queue_can_reject_only_one_stale_session() {
  PendingQueue<4> queue;
  queue.push(measurement(10U, "old-1"));
  queue.push(measurement(11U, "new-1"));
  queue.push(measurement(10U, "old-2"));
  assert(queue.discard_session(10U) == 2U);
  assert(queue.size() == 1U);
  assert(queue.dropped() == 2U);
  assert(queue.front()->session_id == 11U);
}

void test_discarded_delivery_is_counted() {
  PendingQueue<2> queue;
  queue.push(measurement(7U, "invalid"));
  queue.discard_front();
  assert(queue.empty());
  assert(queue.dropped() == 1U);
}

void test_state_resolution_is_session_driven() {
  assert(airmonitor::resolve_run_state(false, false, false, false, false) ==
         RunState::wifi_unavailable);
  assert(airmonitor::resolve_run_state(true, false, false, false, false) ==
         RunState::time_unsynchronized);
  assert(airmonitor::resolve_run_state(true, true, false, false, false) ==
         RunState::time_unsynchronized);
  assert(airmonitor::resolve_run_state(true, false, false, true, false) ==
         RunState::api_unavailable);
  assert(airmonitor::resolve_run_state(true, true, false, true, false) ==
         RunState::device_rejected);
  assert(airmonitor::resolve_run_state(true, true, true, true, false) ==
         RunState::waiting_for_session);
  assert(airmonitor::resolve_run_state(true, true, true, true, true) ==
         RunState::measuring);
}

void test_temporary_wifi_outage_keeps_confirmed_session_and_fifo_identity() {
  SessionState session;
  PendingQueue<8> queue;
  assert(session.confirm_active(41U));
  assert(capture_for_confirmed_session(session, queue, "x-1"));

  session.invalidate_remote();
  assert(!session.remote_session_active());
  assert(session.confirmed_session_id() == 41U);
  assert(capture_for_confirmed_session(session, queue, "x-2"));
  assert(capture_for_confirmed_session(session, queue, "x-3"));
  assert(queue.size() == 3U);

  assert(!session.confirm_active(41U));
  const char* expected_ids[] = {"x-1", "x-2", "x-3"};
  for (const char* expected_id : expected_ids) {
    assert(queue.front() != nullptr);
    assert(queue.front()->session_id == 41U);
    assert(std::strcmp(queue.front()->source_message_id, expected_id) == 0);
    queue.pop();
  }
  assert(queue.empty());
}

void test_temporary_api_outage_keeps_measurement_context() {
  SessionState session;
  PendingQueue<4> queue;
  assert(session.confirm_active(51U));
  session.invalidate_remote();
  assert(capture_for_confirmed_session(session, queue, "api-offline-1"));
  assert(queue.front()->session_id == 51U);
  assert(!session.confirm_active(51U));
  assert(session.remote_session_active());
}

void test_stale_session_is_rejected_without_rebinding_to_replacement() {
  SessionState session;
  PendingQueue<6> queue;
  assert(session.confirm_active(61U));
  session.invalidate_remote();
  assert(capture_for_confirmed_session(session, queue, "x-old-1"));
  assert(capture_for_confirmed_session(session, queue, "x-old-2"));

  assert(session.confirm_active(62U));
  assert(capture_for_confirmed_session(session, queue, "y-new-1"));
  assert(queue.front()->session_id == 61U);
  assert(airmonitor::classify_delivery(
             409,
             "active_session_mismatch",
             ResponseBodyStatus::complete) ==
         DeliveryDisposition::session_ended);

  const std::uint32_t stale_session_id = queue.front()->session_id;
  assert(queue.discard_session(stale_session_id) == 2U);
  assert(!session.reject_session(stale_session_id));
  assert(session.confirmed_session_id() == 62U);
  assert(queue.size() == 1U);
  assert(queue.front()->session_id == 62U);
  assert(std::strcmp(queue.front()->source_message_id, "y-new-1") == 0);
}

void test_no_server_queue_before_first_confirmed_session() {
  SessionState session;
  PendingQueue<4> queue;
  session.invalidate_remote();
  assert(!capture_for_confirmed_session(session, queue, "must-not-exist"));
  assert(queue.empty());
}

void test_queue_capacity_is_bounded_and_overflow_is_observable() {
  SessionState session;
  PendingQueue<2> queue;
  assert(session.confirm_active(71U));
  assert(capture_for_confirmed_session(session, queue, "capacity-1"));
  assert(capture_for_confirmed_session(session, queue, "capacity-2"));
  assert(queue.push(measurement(71U, "capacity-3")));
  assert(queue.size() == 2U);
  assert(queue.dropped() == 1U);
  assert(std::strcmp(queue.front()->source_message_id, "capacity-2") == 0);
}

void test_bounded_response_body_known_and_unknown_lengths() {
  airmonitor::BoundedResponseBody<8> body;
  assert(body.append("okay", 4U));
  assert(std::strcmp(body.c_str(), "okay") == 0);
  assert(airmonitor::finalize_response_body(4, 4, body.overflowed()) ==
         ResponseBodyStatus::complete);
  assert(airmonitor::finalize_response_body(-1, 4, body.overflowed()) ==
         ResponseBodyStatus::complete);
}

void test_bounded_response_body_empty_oversized_and_read_error() {
  airmonitor::BoundedResponseBody<8> empty;
  assert(airmonitor::finalize_response_body(0, 0, empty.overflowed()) ==
         ResponseBodyStatus::complete);
  assert(std::strcmp(empty.c_str(), "") == 0);

  airmonitor::BoundedResponseBody<8> oversized;
  assert(oversized.append("12345678", 8U));
  assert(!oversized.append("9", 1U));
  assert(oversized.overflowed());
  assert(airmonitor::finalize_response_body(-1, 8, oversized.overflowed()) ==
         ResponseBodyStatus::too_large);

  assert(airmonitor::finalize_response_body(10, -11, false) ==
         ResponseBodyStatus::read_error);
  assert(airmonitor::finalize_response_body(10, 4, false) ==
         ResponseBodyStatus::read_error);
}

void test_http_chunk_size_parser_is_bounded_and_accepts_extensions() {
  std::size_t chunk_size = 99U;
  assert(airmonitor::parse_http_chunk_size("4", 1U, &chunk_size));
  assert(chunk_size == 4U);
  assert(airmonitor::parse_http_chunk_size(
      "a;extension=value", 17U, &chunk_size));
  assert(chunk_size == 10U);
  assert(airmonitor::parse_http_chunk_size("0", 1U, &chunk_size));
  assert(chunk_size == 0U);
  assert(!airmonitor::parse_http_chunk_size("", 0U, &chunk_size));
  assert(!airmonitor::parse_http_chunk_size("-1", 2U, &chunk_size));
  assert(!airmonitor::parse_http_chunk_size("xyz", 3U, &chunk_size));
}

PmsFrame valid_pms_frame() {
  PmsFrame frame{};
  frame.pm1 = 9U;
  frame.pm25 = 11U;
  frame.pm10 = 14U;
  frame.pc0_3 = 1572U;
  frame.pc0_5 = 476U;
  frame.pc1_0 = 34U;
  frame.pc2_5 = 10U;
  frame.pc5_0 = 4U;
  frame.pc10 = 2U;
  return frame;
}

void test_pms_frames_are_ignored_during_warmup() {
  const PmsFrame frame = valid_pms_frame();
  assert(airmonitor::classify_pms_frame(frame, 29999U, 0U) ==
         PmsStatus::warming_up);
  assert(airmonitor::classify_pms_frame(frame, 30000U, 0U) ==
         PmsStatus::ready);
}

void test_pms_warmup_handles_millis_wraparound() {
  const PmsFrame frame = valid_pms_frame();
  assert(airmonitor::classify_pms_frame(
             frame, 0x00001000U, 0xFFFFF000U) ==
         PmsStatus::warming_up);
  assert(airmonitor::classify_pms_frame(
             frame, 0x00008000U, 0xFFFFF000U) ==
         PmsStatus::ready);
}

void test_pms_inconsistent_mass_concentrations_are_rejected() {
  PmsFrame frame = valid_pms_frame();
  frame.pm1 = 20U;
  frame.pm25 = 10U;
  assert(airmonitor::classify_pms_frame(frame, 30000U, 0U) ==
         PmsStatus::invalid_frame);
}

void test_pms_inconsistent_particle_counters_are_rejected() {
  PmsFrame frame = valid_pms_frame();
  frame.pc0_5 = frame.pc0_3 + 1U;
  assert(airmonitor::classify_pms_frame(frame, 30000U, 0U) ==
         PmsStatus::invalid_frame);
}

void test_pms_high_but_consistent_reading_is_not_clipped() {
  PmsFrame frame = valid_pms_frame();
  frame.pm1 = 700U;
  frame.pm25 = 1000U;
  frame.pm10 = 1200U;
  frame.pc0_3 = 65000U;
  frame.pc0_5 = 50000U;
  frame.pc1_0 = 30000U;
  frame.pc2_5 = 10000U;
  frame.pc5_0 = 1000U;
  frame.pc10 = 100U;
  assert(airmonitor::classify_pms_frame(frame, 30000U, 0U) ==
         PmsStatus::ready);
}

void test_pms_snapshot_uses_latest_valid_frame_without_accumulation() {
  airmonitor::SensorSnapshot snapshot{};
  PmsFrame frame = valid_pms_frame();
  frame.pm1 = 700U;
  frame.pm25 = 1000U;
  frame.pm10 = 1200U;
  assert(airmonitor::update_pms_snapshot(snapshot, frame, 30000U, 0U) ==
         PmsStatus::ready);
  assert(snapshot.pm25 == 1000.0F);

  frame = valid_pms_frame();
  assert(airmonitor::update_pms_snapshot(snapshot, frame, 32000U, 0U) ==
         PmsStatus::ready);
  assert(snapshot.pm1 == 9.0F);
  assert(snapshot.pm25 == 11.0F);
  assert(snapshot.pm10 == 14.0F);
  assert(snapshot.pc0_3 == 1572);
  assert(snapshot.pms_ok);
}

void test_invalid_pms_frame_does_not_replace_last_good_values() {
  airmonitor::SensorSnapshot snapshot{};
  PmsFrame frame = valid_pms_frame();
  assert(airmonitor::update_pms_snapshot(snapshot, frame, 30000U, 0U) ==
         PmsStatus::ready);

  frame.pm1 = 500U;
  frame.pm25 = 100U;
  assert(airmonitor::update_pms_snapshot(snapshot, frame, 32000U, 0U) ==
         PmsStatus::invalid_frame);
  assert(snapshot.pm1 == 9.0F);
  assert(snapshot.pm25 == 11.0F);
  assert(!snapshot.pms_ok);
}

void test_capture_waits_for_pms_warmup_but_allows_later_partial_data() {
  airmonitor::SensorSnapshot snapshot{};
  snapshot.sht_ok = true;
  snapshot.pms_status = PmsStatus::warming_up;
  assert(!airmonitor::has_captureable_sensor_data(snapshot));

  snapshot.pms_status = PmsStatus::stale;
  assert(airmonitor::has_captureable_sensor_data(snapshot));

  snapshot.sht_ok = false;
  assert(!airmonitor::has_captureable_sensor_data(snapshot));
  snapshot.pms_ok = true;
  snapshot.pms_status = PmsStatus::ready;
  assert(airmonitor::has_captureable_sensor_data(snapshot));
}

}  // namespace

int main() {
  test_delivery_classification();
  test_retry_backoff_is_capped();
  test_millis_deadline_handles_wraparound();
  test_timestamp_is_utc_iso8601();
  test_source_message_id_is_stable_and_bounded();
  test_queue_is_fifo_and_drops_oldest_when_full();
  test_queue_can_reject_only_one_stale_session();
  test_discarded_delivery_is_counted();
  test_state_resolution_is_session_driven();
  test_temporary_wifi_outage_keeps_confirmed_session_and_fifo_identity();
  test_temporary_api_outage_keeps_measurement_context();
  test_stale_session_is_rejected_without_rebinding_to_replacement();
  test_no_server_queue_before_first_confirmed_session();
  test_queue_capacity_is_bounded_and_overflow_is_observable();
  test_bounded_response_body_known_and_unknown_lengths();
  test_bounded_response_body_empty_oversized_and_read_error();
  test_http_chunk_size_parser_is_bounded_and_accepts_extensions();
  test_pms_frames_are_ignored_during_warmup();
  test_pms_warmup_handles_millis_wraparound();
  test_pms_inconsistent_mass_concentrations_are_rejected();
  test_pms_inconsistent_particle_counters_are_rejected();
  test_pms_high_but_consistent_reading_is_not_clipped();
  test_pms_snapshot_uses_latest_valid_frame_without_accumulation();
  test_invalid_pms_frame_does_not_replace_last_good_values();
  test_capture_waits_for_pms_warmup_but_allows_later_partial_data();
  std::cout << "firmware logic tests passed\n";
  return 0;
}
