#pragma once

#include "prophecy/sim/locomotion.h"

#include <array>
#include <cstdint>
#include <memory>
#include <vector>

#ifndef PROPHECY_ENABLE_REWIND
#define PROPHECY_ENABLE_REWIND 1
#endif

namespace prophecy::sim {

using EntityId = std::uint32_t;
constexpr EntityId kInvalidEntityId = 0;
inline constexpr bool kRewindEnabled = PROPHECY_ENABLE_REWIND != 0;

struct Vec3 {
    float x = 0.0f;
    float y = 0.0f;
    float z = 0.0f;
};

struct SimulationConfig {
    std::uint32_t agent_count = 2;
    float tick_rate_hz = 30.0f;
    Vec3 world_min{-32.0f, -24.0f, 0.0f};
    Vec3 world_max{32.0f, 24.0f, 0.0f};
};

enum class Team : std::uint8_t {
    Azure,
    Crimson,
};

enum class SwordState : std::uint8_t {
    Sheathed,
    Drawn,
};

struct AgentSnapshot {
    EntityId id = kInvalidEntityId;
    Vec3 position{};
    float facing_radians = 0.0f;
    Team team = Team::Azure;
    LocomotionMode locomotion_mode = LocomotionMode::Walk;
    LocomotionResponse locomotion_response = LocomotionResponse::Normal;
    Vec3 root_velocity{};
    float root_speed_mps = 0.0f;
    float speed_stick_direction_radians = 0.0f;
    float speed_stick_amplitude = 0.0f;
    float orientation_stick_yaw_radians = 0.0f;
    float pose_phase = 0.0f;
    bool sword_equipped = false;
    SwordState sword_state = SwordState::Sheathed;
    FutureRootWindow future_roots{};
};

struct SimulationSnapshot {
    std::uint64_t tick = 0;
    double time_seconds = 0.0;
    std::uint64_t seed = 0;
    std::vector<AgentSnapshot> agents{};
};

struct ReplayLog {
    std::uint64_t seed = 0;
    std::uint64_t end_tick = 0;
    SimulationConfig initial_config{};
};

SimulationConfig MakeDefaultConfig();
const char* ToString(Team team) noexcept;
const char* ToString(SwordState state) noexcept;

class Simulation final {
public:
    explicit Simulation(SimulationConfig config = MakeDefaultConfig(), std::uint64_t seed = 1) noexcept;
    ~Simulation();

    Simulation(const Simulation&) = delete;
    Simulation& operator=(const Simulation&) = delete;
    Simulation(Simulation&&) noexcept;
    Simulation& operator=(Simulation&&) noexcept;

    void Tick() noexcept;
    void Reset(std::uint64_t seed) noexcept;

    void BeginReplay(const ReplayLog& replay) noexcept;
    bool SeekReplay(const ReplayLog& replay, std::uint64_t target_tick) noexcept;
    bool ResumeRecordingFromReplay() noexcept;
    const ReplayLog& RecordedReplay() const noexcept;
    bool IsReplaying() const noexcept;

    const SimulationSnapshot& Snapshot() const noexcept;
    const SimulationConfig& Config() const noexcept;
    std::uint64_t Seed() const noexcept;
    double TickSeconds() const noexcept;

private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

}  // namespace prophecy::sim
