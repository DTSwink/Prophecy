#pragma once

#include <string>

namespace prophecy::viewer {

struct ControlSettings {
    float look_sensitivity = 0.007f;
    float pan_sensitivity = 0.10f;
    float flight_speed = 18.0f;
    float zoom_sensitivity = 2.5f;
};

constexpr float kMinLookSensitivity = 0.001f;
constexpr float kMaxLookSensitivity = 0.020f;
constexpr float kMinPanSensitivity = 0.01f;
constexpr float kMaxPanSensitivity = 0.30f;
constexpr float kMinFlightSpeed = 2.0f;
constexpr float kMaxFlightSpeed = 50.0f;
constexpr float kMinZoomSensitivity = 0.25f;
constexpr float kMaxZoomSensitivity = 6.0f;

ControlSettings DefaultControlSettings() noexcept;
bool LoadControlSettings(const std::string& path, ControlSettings& settings, std::string& error);
bool SaveControlSettings(const std::string& path, const ControlSettings& settings, std::string& error);

}  // namespace prophecy::viewer
