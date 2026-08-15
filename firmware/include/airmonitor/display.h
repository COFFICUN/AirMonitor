#pragma once

#include <cstddef>
#include <cstdint>

#include "airmonitor/firmware_logic.h"

namespace airmonitor {

struct DisplayStatus {
  RunState run_state = RunState::wifi_unavailable;
  bool wifi_connected = false;
  bool sending = false;
  bool locally_paused = false;
  int last_http_status = 0;
  std::uint32_t active_session_id = 0;
  std::uint32_t delivered_count = 0;
  std::uint32_t last_success_ms = 0;
  std::size_t queue_size = 0;
  std::uint32_t dropped_count = 0;
  std::uint32_t rejected_count = 0;
};

struct ButtonActions {
  bool manual_capture = false;
  bool pause_toggled = false;
};

class DeviceDisplay {
 public:
  void begin();
  ButtonActions poll_buttons();
  void render(
      std::uint32_t now_ms,
      const SensorSnapshot& sensors,
      const DisplayStatus& status,
      bool force = false);
  void show_message(const char* message, std::uint32_t duration_ms = 1800U);

 private:
  void draw_static();
  void draw_main(const SensorSnapshot& sensors, const DisplayStatus& status);
  void draw_particles(
      const SensorSnapshot& sensors,
      const DisplayStatus& status);
  void draw_system(const SensorSnapshot& sensors, const DisplayStatus& status);
  void draw_top_bar(const DisplayStatus& status);
  void draw_bottom_bar(const DisplayStatus& status);

  int screen_ = 0;
  std::uint32_t last_render_ms_ = 0;
  std::uint32_t message_until_ms_ = 0;
  const char* message_ = nullptr;
  bool static_dirty_ = true;
};

}  // namespace airmonitor
