#include "control_settings.h"

#include <filesystem>
#include <fstream>
#include <cstdio>
#include <cstdlib>

namespace {

namespace viewer = ::prophecy::viewer;

bool Equal(const viewer::ControlSettings& left, const viewer::ControlSettings& right) {
    return left.look_sensitivity == right.look_sensitivity &&
        left.pan_sensitivity == right.pan_sensitivity &&
        left.flight_speed == right.flight_speed &&
        left.zoom_sensitivity == right.zoom_sensitivity;
}

}  // namespace

int main() {
    const std::filesystem::path directory = std::filesystem::temp_directory_path() / "prophecy_neutral_settings_test";
    const std::filesystem::path path = directory / "camera.json";
    std::error_code ignored;
    std::filesystem::remove_all(directory, ignored);

    viewer::ControlSettings expected{};
    expected.look_sensitivity = 0.011f;
    expected.pan_sensitivity = 0.21f;
    expected.flight_speed = 31.0f;
    expected.zoom_sensitivity = 4.5f;
    std::string error;
    if (!viewer::SaveControlSettings(path.string(), expected, error)) {
        std::fprintf(stderr, "FAIL: %s\n", error.c_str());
        return EXIT_FAILURE;
    }
    viewer::ControlSettings loaded{};
    if (!viewer::LoadControlSettings(path.string(), loaded, error) || !Equal(expected, loaded)) {
        std::fprintf(stderr, "FAIL: camera settings did not round-trip\n");
        return EXIT_FAILURE;
    }

    std::ofstream(path) << R"({"camera":{"look_sensitivity":100,"pan_sensitivity":-1,"flight_speed":500,"zoom_sensitivity":0}})";
    if (!viewer::LoadControlSettings(path.string(), loaded, error) ||
        loaded.look_sensitivity != viewer::kMaxLookSensitivity ||
        loaded.pan_sensitivity != viewer::kMinPanSensitivity ||
        loaded.flight_speed != viewer::kMaxFlightSpeed ||
        loaded.zoom_sensitivity != viewer::kMinZoomSensitivity) {
        std::fprintf(stderr, "FAIL: camera settings were not clamped\n");
        return EXIT_FAILURE;
    }
    std::filesystem::remove_all(directory, ignored);
    std::printf("Camera settings tests passed.\n");
    return EXIT_SUCCESS;
}
