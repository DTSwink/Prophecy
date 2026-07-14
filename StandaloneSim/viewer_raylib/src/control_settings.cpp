#include "control_settings.h"

#include <nlohmann/json.hpp>

#include <algorithm>
#include <filesystem>
#include <fstream>

namespace prophecy::viewer {
namespace {

using Json = nlohmann::json;

void ClampSettings(ControlSettings& settings) {
    settings.look_sensitivity = std::clamp(settings.look_sensitivity, kMinLookSensitivity, kMaxLookSensitivity);
    settings.pan_sensitivity = std::clamp(settings.pan_sensitivity, kMinPanSensitivity, kMaxPanSensitivity);
    settings.flight_speed = std::clamp(settings.flight_speed, kMinFlightSpeed, kMaxFlightSpeed);
    settings.zoom_sensitivity = std::clamp(settings.zoom_sensitivity, kMinZoomSensitivity, kMaxZoomSensitivity);
}

}  // namespace

ControlSettings DefaultControlSettings() noexcept {
    return {};
}

bool LoadControlSettings(const std::string& path, ControlSettings& settings, std::string& error) {
    settings = DefaultControlSettings();
    if (!std::filesystem::exists(path)) {
        error.clear();
        return true;
    }

    std::ifstream input(path);
    if (!input) {
        error = "Could not open camera settings: " + path;
        return false;
    }
    const Json root = Json::parse(input, nullptr, false);
    if (root.is_discarded() || !root.is_object()) {
        error = "Camera settings JSON is invalid: " + path;
        return false;
    }

    const Json& camera = root.contains("camera") && root["camera"].is_object() ? root["camera"] : root;
    settings.look_sensitivity = camera.value("look_sensitivity", settings.look_sensitivity);
    settings.pan_sensitivity = camera.value("pan_sensitivity", settings.pan_sensitivity);
    settings.flight_speed = camera.value("flight_speed", settings.flight_speed);
    settings.zoom_sensitivity = camera.value("zoom_sensitivity", settings.zoom_sensitivity);
    ClampSettings(settings);
    error.clear();
    return true;
}

bool SaveControlSettings(const std::string& path, const ControlSettings& settings, std::string& error) {
    std::error_code directory_error;
    const std::filesystem::path output_path(path);
    std::filesystem::create_directories(output_path.parent_path(), directory_error);
    if (directory_error) {
        error = "Could not create the camera-settings directory.";
        return false;
    }

    ControlSettings clamped = settings;
    ClampSettings(clamped);
    std::ofstream output(output_path, std::ios::trunc);
    if (!output) {
        error = "Could not write camera settings: " + path;
        return false;
    }
    output << Json{{"camera", {
        {"look_sensitivity", clamped.look_sensitivity},
        {"pan_sensitivity", clamped.pan_sensitivity},
        {"flight_speed", clamped.flight_speed},
        {"zoom_sensitivity", clamped.zoom_sensitivity},
    }}}.dump(2) << '\n';
    if (!output) {
        error = "Writing camera settings failed: " + path;
        return false;
    }
    error.clear();
    return true;
}

}  // namespace prophecy::viewer
