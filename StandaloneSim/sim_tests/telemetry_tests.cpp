#include "telemetry.h"

#include <nlohmann/json.hpp>

#include <cstdio>
#include <cstdlib>

int main() {
    namespace sim = ::prophecy::sim;
    namespace viewer = ::prophecy::viewer;
    sim::Simulation simulation({}, 99);
    for (int tick = 0; tick < 17; ++tick) simulation.Tick();
    viewer::TelemetryViewState view{};
    view.paused = true;
    view.render_fps = 60;
    view.rewind_head_tick = 17;
    view.selected_agent_id = 1;
    const nlohmann::json root = nlohmann::json::parse(
        viewer::SerializeTelemetrySnapshot("test", simulation.Snapshot(), simulation.Config(), view));
    const bool valid = root.value("schema", "") == "prophecy.locomotion-sim.snapshot.v1" &&
        root["simulation"]["tick"] == 17U && root["simulation"]["agent_count"] == 2U &&
        root["viewer"]["paused"] == true && root["viewer"]["selected_agent_id"] == 1U &&
        root["agents"].size() == 2U &&
        root["agents"][0].contains("id") && root["agents"][0].contains("position") &&
        root["agents"][0].contains("facing_radians") && root["agents"][0].contains("team") &&
        root["agents"][0]["equipment"]["sword_equipped"] == true &&
        root["agents"][0]["equipment"].contains("sword_state") &&
        root["agents"][0]["locomotion"]["future_roots"].size() == sim::kFutureRootWindow &&
        root["agents"][0]["locomotion"].contains("speed_stick_amplitude") &&
        !root.contains("battle_tuning");
    if (!valid) {
        std::fprintf(stderr, "FAIL: simulation telemetry schema is incomplete\n");
        return EXIT_FAILURE;
    }
    std::printf("Locomotion telemetry serialization test passed.\n");
    return EXIT_SUCCESS;
}
