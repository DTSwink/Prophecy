#include "scenario.h"

#include <nlohmann/json.hpp>

#include <algorithm>
#include <fstream>
#include <utility>

namespace prophecy::viewer {
namespace {

using Json = nlohmann::json;

sim::Vec3 ReadVec3(const Json& value, sim::Vec3 fallback = {}) {
    if (!value.is_array() || value.size() < 3U) return fallback;
    return {
        value[0].is_number() ? value[0].get<float>() : fallback.x,
        value[1].is_number() ? value[1].get<float>() : fallback.y,
        value[2].is_number() ? value[2].get<float>() : fallback.z,
    };
}

Color ReadColor(const Json& value, Color fallback) {
    if (!value.is_array() || value.size() < 3U) return fallback;
    const auto channel = [&value](std::size_t index, unsigned char fallback_value) {
        if (index >= value.size() || !value[index].is_number_integer()) return fallback_value;
        return static_cast<unsigned char>(std::clamp(value[index].get<int>(), 0, 255));
    };
    return {channel(0, fallback.r), channel(1, fallback.g), channel(2, fallback.b), channel(3, fallback.a)};
}

}  // namespace

Scenario MakeFallbackScenario() {
    Scenario scenario{};
    scenario.simulation = sim::MakeDefaultConfig();
    scenario.seed = 1337ULL;
    return scenario;
}

bool LoadScenario(const std::string& path, Scenario& scenario, std::string& error) {
    std::ifstream input(path);
    if (!input) {
        error = "Could not open scenario: " + path;
        return false;
    }
    const Json root = Json::parse(input, nullptr, false);
    if (root.is_discarded() || !root.is_object()) {
        error = "Scenario JSON is invalid: " + path;
        return false;
    }

    Scenario loaded = MakeFallbackScenario();
    loaded.name = root.value("name", loaded.name);
    loaded.seed = root.value("seed", loaded.seed);
    if (root.contains("simulation") && root["simulation"].is_object()) {
        const Json& simulation = root["simulation"];
        loaded.simulation.agent_count = simulation.value("agent_count", loaded.simulation.agent_count);
        loaded.simulation.tick_rate_hz = simulation.value("tick_rate_hz", loaded.simulation.tick_rate_hz);
        if (simulation.contains("world_min")) loaded.simulation.world_min = ReadVec3(simulation["world_min"], loaded.simulation.world_min);
        if (simulation.contains("world_max")) loaded.simulation.world_max = ReadVec3(simulation["world_max"], loaded.simulation.world_max);
    }
    if (root.contains("atmosphere") && root["atmosphere"].is_object()) {
        const Json& atmosphere = root["atmosphere"];
        if (atmosphere.contains("sky_color")) loaded.sky_color = ReadColor(atmosphere["sky_color"], loaded.sky_color);
        if (atmosphere.contains("ground_color")) loaded.ground_color = ReadColor(atmosphere["ground_color"], loaded.ground_color);
        if (atmosphere.contains("grid_color")) loaded.grid_color = ReadColor(atmosphere["grid_color"], loaded.grid_color);
    }
    if (root.contains("camera") && root["camera"].is_object()) {
        const Json& camera = root["camera"];
        if (camera.contains("focus")) loaded.camera_focus = ReadVec3(camera["focus"], loaded.camera_focus);
        loaded.camera_distance = camera.value("distance", loaded.camera_distance);
        loaded.camera_yaw = camera.value("yaw", loaded.camera_yaw);
        loaded.camera_pitch = camera.value("pitch", loaded.camera_pitch);
    }
    scenario = std::move(loaded);
    error.clear();
    return true;
}

}  // namespace prophecy::viewer
