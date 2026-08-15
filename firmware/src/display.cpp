#include "airmonitor/display.h"

#include <M5Stack.h>

namespace airmonitor {

namespace {

constexpr std::uint32_t kUiRefreshMs = 800U;
constexpr std::uint16_t kBackground = BLACK;
constexpr std::uint16_t kText = WHITE;
constexpr std::uint16_t kSubtle = LIGHTGREY;

std::uint16_t orange() { return M5.Lcd.color565(255, 165, 0); }
std::uint16_t blue() { return M5.Lcd.color565(90, 170, 255); }
std::uint16_t green() { return M5.Lcd.color565(70, 220, 120); }
std::uint16_t red() { return M5.Lcd.color565(255, 90, 90); }

const char* run_state_label(RunState state) {
  switch (state) {
    case RunState::wifi_unavailable:
      return "NO WIFI";
    case RunState::api_unavailable:
      return "API ERROR";
    case RunState::device_rejected:
      return "DEVICE ERR";
    case RunState::time_unsynchronized:
      return "SYNC TIME";
    case RunState::waiting_for_session:
      return "WAIT SESSION";
    case RunState::measuring:
      return "MEASURE";
  }
  return "UNKNOWN";
}

const char* pms_status_label(PmsStatus status) {
  switch (status) {
    case PmsStatus::warming_up:
      return "WARMUP";
    case PmsStatus::ready:
      return "OK";
    case PmsStatus::invalid_frame:
      return "FRAME ERR";
    case PmsStatus::stale:
      return "NO DATA";
  }
  return "UNKNOWN";
}

std::uint16_t state_color(const DisplayStatus& status) {
  if (status.sending) return YELLOW;
  if (status.run_state == RunState::measuring) return green();
  if (status.run_state == RunState::waiting_for_session ||
      status.run_state == RunState::time_unsynchronized) {
    return blue();
  }
  return red();
}

void clear_box(int x, int y, int width, int height) {
  M5.Lcd.fillRect(x, y, width, height, kBackground);
}

String short_ago(std::uint32_t timestamp_ms) {
  if (timestamp_ms == 0U) return "never";
  const std::uint32_t seconds = (millis() - timestamp_ms) / 1000U;
  if (seconds < 60U) return String(seconds) + "s";
  return String(seconds / 60U) + "m";
}

}  // namespace

void DeviceDisplay::begin() {
  M5.begin();
  M5.Lcd.setRotation(1);
  M5.Lcd.fillScreen(kBackground);
  static_dirty_ = true;
}

ButtonActions DeviceDisplay::poll_buttons() {
  M5.update();
  ButtonActions actions{};
  if (M5.BtnA.wasPressed()) {
    screen_ = (screen_ + 1) % 3;
    static_dirty_ = true;
    show_message("NEXT SCREEN");
  }
  actions.manual_capture = M5.BtnB.wasPressed();
  actions.pause_toggled = M5.BtnC.wasPressed();
  return actions;
}

void DeviceDisplay::render(
    std::uint32_t now_ms,
    const SensorSnapshot& sensors,
    const DisplayStatus& status,
    bool force) {
  if (!force && now_ms - last_render_ms_ < kUiRefreshMs) {
    return;
  }
  last_render_ms_ = now_ms;
  if (static_dirty_) {
    draw_static();
    static_dirty_ = false;
  }
  if (screen_ == 0) {
    draw_main(sensors, status);
  } else if (screen_ == 1) {
    draw_particles(sensors, status);
  } else {
    draw_system(sensors, status);
  }
}

void DeviceDisplay::show_message(
    const char* message,
    std::uint32_t duration_ms) {
  message_ = message;
  message_until_ms_ = millis() + duration_ms;
}

void DeviceDisplay::draw_static() {
  M5.Lcd.fillScreen(kBackground);
  M5.Lcd.setTextSize(2);
  M5.Lcd.setTextColor(kText, kBackground);
  M5.Lcd.setCursor(8, 4);
  M5.Lcd.print("AirMonitor v2");

  M5.Lcd.setTextSize(1);
  M5.Lcd.setTextColor(DARKGREY, kBackground);
  M5.Lcd.setCursor(10, 202);
  M5.Lcd.print("A Next");
  M5.Lcd.setCursor(116, 202);
  M5.Lcd.print("B Capture");
  M5.Lcd.setCursor(238, 202);
  M5.Lcd.print("C Pause");
}

void DeviceDisplay::draw_top_bar(const DisplayStatus& status) {
  clear_box(215, 0, 105, 22);
  M5.Lcd.setTextSize(1);
  M5.Lcd.setTextColor(kText, kBackground);
  M5.Lcd.setCursor(218, 6);
  M5.Lcd.print(status.wifi_connected ? "WiFi OK" : "WiFi LOST");
  M5.Lcd.fillCircle(307, 12, 5, state_color(status));
}

void DeviceDisplay::draw_bottom_bar(const DisplayStatus& status) {
  clear_box(0, 218, 320, 22);
  M5.Lcd.drawFastHLine(0, 218, 320, DARKGREY);
  M5.Lcd.setTextSize(1);
  M5.Lcd.setTextColor(kText, kBackground);
  M5.Lcd.setCursor(6, 225);
  M5.Lcd.printf("Q %u", static_cast<unsigned>(status.queue_size));
  M5.Lcd.setCursor(55, 225);
  M5.Lcd.print("Last ");
  M5.Lcd.print(short_ago(status.last_success_ms));
  M5.Lcd.setCursor(125, 225);
  if (message_ != nullptr && !deadline_reached(millis(), message_until_ms_)) {
    M5.Lcd.print(message_);
  } else if (status.locally_paused) {
    M5.Lcd.print("PAUSED");
  } else {
    M5.Lcd.print(run_state_label(status.run_state));
  }
}

void DeviceDisplay::draw_main(
    const SensorSnapshot& sensors,
    const DisplayStatus& status) {
  draw_top_bar(status);
  draw_bottom_bar(status);
  M5.Lcd.setTextSize(2);
  M5.Lcd.setTextColor(kSubtle, kBackground);
  M5.Lcd.setCursor(10, 34); M5.Lcd.print("PM2.5 ug/m3");
  M5.Lcd.setCursor(205, 34); M5.Lcd.print("READING");
  M5.Lcd.setCursor(10, 106); M5.Lcd.print("TEMP");
  M5.Lcd.setCursor(170, 106); M5.Lcd.print("HUM");
  M5.Lcd.setCursor(10, 154); M5.Lcd.print("PM1 ug/m3");
  M5.Lcd.setCursor(170, 154); M5.Lcd.print("PM10 ug/m3");

  clear_box(10, 58, 170, 46);
  clear_box(205, 58, 110, 36);
  clear_box(10, 126, 130, 26);
  clear_box(170, 126, 130, 26);
  clear_box(10, 174, 130, 26);
  clear_box(170, 174, 130, 26);

  if (sensors.pms_ok) {
    M5.Lcd.setTextSize(5);
    M5.Lcd.setTextColor(CYAN, kBackground);
    M5.Lcd.setCursor(10, 58);
    M5.Lcd.printf("%.0f", sensors.pm25);
    M5.Lcd.setTextSize(2);
    M5.Lcd.setTextColor(kSubtle, kBackground);
    M5.Lcd.setCursor(205, 64);
    M5.Lcd.print("LIVE");
  } else {
    M5.Lcd.setTextSize(5);
    M5.Lcd.setTextColor(kSubtle, kBackground);
    M5.Lcd.setCursor(10, 58); M5.Lcd.print("--");
    M5.Lcd.setTextSize(2);
    M5.Lcd.setCursor(205, 64);
    M5.Lcd.print(pms_status_label(sensors.pms_status));
  }

  M5.Lcd.setTextSize(3);
  M5.Lcd.setTextColor(CYAN, kBackground);
  M5.Lcd.setCursor(10, 126);
  if (sensors.sht_ok) M5.Lcd.printf("%.1f", sensors.temperature);
  else M5.Lcd.print("--");
  M5.Lcd.setTextSize(2);
  M5.Lcd.setTextColor(kSubtle, kBackground);
  M5.Lcd.setCursor(98, 132); M5.Lcd.print("C");

  M5.Lcd.setTextSize(3);
  M5.Lcd.setTextColor(YELLOW, kBackground);
  M5.Lcd.setCursor(170, 126);
  if (sensors.sht_ok) M5.Lcd.printf("%.1f", sensors.humidity);
  else M5.Lcd.print("--");
  M5.Lcd.setTextSize(2);
  M5.Lcd.setTextColor(kSubtle, kBackground);
  M5.Lcd.setCursor(258, 132); M5.Lcd.print("%");

  M5.Lcd.setTextSize(3);
  M5.Lcd.setTextColor(GREEN, kBackground);
  M5.Lcd.setCursor(10, 174);
  if (sensors.pms_ok) M5.Lcd.printf("%.0f", sensors.pm1);
  else M5.Lcd.print("--");
  M5.Lcd.setTextColor(orange(), kBackground);
  M5.Lcd.setCursor(170, 174);
  if (sensors.pms_ok) M5.Lcd.printf("%.0f", sensors.pm10);
  else M5.Lcd.print("--");
}

void DeviceDisplay::draw_particles(
    const SensorSnapshot& sensors,
    const DisplayStatus& status) {
  draw_top_bar(status);
  draw_bottom_bar(status);
  M5.Lcd.setTextSize(2);
  M5.Lcd.setTextColor(kText, kBackground);
  M5.Lcd.setCursor(10, 34); M5.Lcd.print("PARTICLE COUNT / 0.1L");
  M5.Lcd.setTextColor(kSubtle, kBackground);
  const char* labels[] = {
      ">0.3um", ">0.5um", ">1.0um", ">2.5um", ">5.0um", ">10um"};
  const int values[] = {
      sensors.pc0_3, sensors.pc0_5, sensors.pc1_0,
      sensors.pc2_5, sensors.pc5_0, sensors.pc10};
  clear_box(8, 60, 292, 132);
  for (int index = 0; index < 6; ++index) {
    const int y = 64 + index * 22;
    M5.Lcd.setTextColor(kSubtle, kBackground);
    M5.Lcd.setCursor(10, y); M5.Lcd.print(labels[index]);
    M5.Lcd.setTextColor(sensors.pms_ok ? kText : red(), kBackground);
    M5.Lcd.setCursor(120, y);
    if (sensors.pms_ok) M5.Lcd.printf("%d", values[index]);
    else M5.Lcd.print("--");
  }
}

void DeviceDisplay::draw_system(
    const SensorSnapshot& sensors,
    const DisplayStatus& status) {
  draw_top_bar(status);
  draw_bottom_bar(status);
  clear_box(8, 32, 300, 164);
  M5.Lcd.setTextSize(2);
  M5.Lcd.setTextColor(kText, kBackground);
  M5.Lcd.setCursor(10, 34); M5.Lcd.print("SYSTEM");
  M5.Lcd.setTextColor(kSubtle, kBackground);
  const char* labels[] = {"WIFI", "API", "SESSION", "QUEUE", "SHT30", "PMSA003"};
  for (int index = 0; index < 6; ++index) {
    M5.Lcd.setCursor(10, 64 + index * 22);
    M5.Lcd.print(labels[index]);
  }
  M5.Lcd.setTextColor(kText, kBackground);
  M5.Lcd.setCursor(130, 64); M5.Lcd.print(status.wifi_connected ? "OK" : "LOST");
  M5.Lcd.setCursor(130, 86); M5.Lcd.printf("HTTP %d", status.last_http_status);
  M5.Lcd.setCursor(130, 108);
  if (status.active_session_id > 0U) {
    M5.Lcd.printf("%u", static_cast<unsigned>(status.active_session_id));
  }
  else M5.Lcd.print("WAIT");
  M5.Lcd.setTextSize(1);
  M5.Lcd.setCursor(130, 134);
  M5.Lcd.printf(
      "Q%u ok%u d%u r%u",
      static_cast<unsigned>(status.queue_size),
      static_cast<unsigned>(status.delivered_count),
      static_cast<unsigned>(status.dropped_count),
      static_cast<unsigned>(status.rejected_count));
  M5.Lcd.setTextSize(2);
  M5.Lcd.setCursor(130, 152); M5.Lcd.print(sensors.sht_ok ? "OK" : "ERR");
  M5.Lcd.setCursor(130, 174);
  M5.Lcd.print(pms_status_label(sensors.pms_status));
}

}  // namespace airmonitor
