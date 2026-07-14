#pragma once

#include "prophecy/sim/simulation.h"

#include <cstdint>
#include <memory>
#include <string>

namespace prophecy::viewer {

struct TelemetryViewState {
    bool paused = false;
    float time_scale = 1.0f;
    int render_fps = 0;
    bool replaying = false;
    bool rewind_enabled = ::prophecy::sim::kRewindEnabled;
    bool rewind_active = false;
    std::uint64_t rewind_head_tick = 0;
    ::prophecy::sim::EntityId selected_agent_id = ::prophecy::sim::kInvalidEntityId;
};

std::string SerializeTelemetrySnapshot(const std::string& scenario_name,
    const ::prophecy::sim::SimulationSnapshot& snapshot,
    const ::prophecy::sim::SimulationConfig& config,
    const TelemetryViewState& view);

class TelemetryServer final {
public:
    TelemetryServer();
    ~TelemetryServer();

    TelemetryServer(const TelemetryServer&) = delete;
    TelemetryServer& operator=(const TelemetryServer&) = delete;

    bool Start(std::uint16_t port, std::string& error);
    void Stop() noexcept;
    bool Running() const noexcept;
    bool SnapshotRequested() const noexcept;
    void FulfillSnapshot(std::string scenario_name,
        ::prophecy::sim::SimulationSnapshot snapshot,
        ::prophecy::sim::SimulationConfig config,
        TelemetryViewState view);

private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

}  // namespace prophecy::viewer
