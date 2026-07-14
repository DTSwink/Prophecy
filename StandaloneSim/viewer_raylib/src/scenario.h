#pragma once

#include "prophecy/sim/simulation.h"

#include "raylib.h"

#include <string>

namespace prophecy::viewer {

namespace sim = ::prophecy::sim;

struct Scenario {
    std::string name = "Prophecy Blockout";
    sim::SimulationConfig simulation{};
    Color sky_color{176, 194, 204, 255};
    Color ground_color{83, 99, 78, 255};
    Color grid_color{116, 128, 108, 100};
    sim::Vec3 camera_focus{};
    float camera_distance = 57.0f;
    float camera_yaw = 0.72f;
    float camera_pitch = 0.72f;
    std::uint64_t seed = 1337ULL;
};

Scenario MakeFallbackScenario();
bool LoadScenario(const std::string& path, Scenario& scenario, std::string& error);

}  // namespace prophecy::viewer
