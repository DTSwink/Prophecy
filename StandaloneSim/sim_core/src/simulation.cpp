#include "prophecy/sim/simulation.h"

#include <algorithm>
#include <cmath>
#include <utility>

namespace prophecy::sim {
namespace {

constexpr double kPi = 3.1415926535897932384626433832795;

class StableRng final {
public:
    explicit StableRng(std::uint64_t seed) noexcept { Reset(seed); }

    void Reset(std::uint64_t seed) noexcept {
        state_ = seed == 0 ? 0x9e3779b97f4a7c15ULL : seed;
    }

    std::uint64_t Next() noexcept {
        std::uint64_t value = state_;
        value ^= value >> 12U;
        value ^= value << 25U;
        value ^= value >> 27U;
        state_ = value;
        return value * 0x2545f4914f6cdd1dULL;
    }

    double Unit() noexcept {
        return static_cast<double>(Next() >> 11U) * (1.0 / 9007199254740992.0);
    }

    double Range(double minimum, double maximum) noexcept {
        return minimum + (maximum - minimum) * Unit();
    }

    std::uint32_t Range(std::uint32_t minimum, std::uint32_t maximum_inclusive) noexcept {
        const std::uint64_t span = static_cast<std::uint64_t>(maximum_inclusive - minimum) + 1U;
        return minimum + static_cast<std::uint32_t>(Next() % span);
    }

private:
    std::uint64_t state_ = 1;
};

SimulationConfig NormalizeConfig(SimulationConfig config) noexcept {
    config.agent_count = std::max(1U, config.agent_count);
    config.tick_rate_hz = std::max(1.0f, config.tick_rate_hz);
    if (config.world_min.x > config.world_max.x) std::swap(config.world_min.x, config.world_max.x);
    if (config.world_min.y > config.world_max.y) std::swap(config.world_min.y, config.world_max.y);
    return config;
}

double AngleTo(Vec2 from, Vec2 to) noexcept {
    return std::atan2(to.x - from.x, to.z - from.z);
}

float PosePhase(const LocomotionState& state, LocomotionMode mode) noexcept {
    // Full-body source cycles span 120 walk frames at 2 m/s and 75 run frames at 5 m/s.
    const double cycle_distance = mode == LocomotionMode::Walk ? 8.00007152557373 : 12.5;
    return static_cast<float>(std::fmod(state.distance_travelled, cycle_distance) / cycle_distance);
}

}  // namespace

struct Simulation::Impl final {
    struct AgentRuntime {
        EntityId id = kInvalidEntityId;
        Team team = Team::Azure;
        LocomotionState locomotion{};
        LocomotionIntent intent{};
        std::uint32_t intent_ticks_remaining = 0;
        bool sword_equipped = true;
        SwordState sword_state = SwordState::Sheathed;
        std::uint32_t sword_state_ticks_remaining = 0;
    };

    explicit Impl(SimulationConfig in_config, std::uint64_t in_seed) noexcept
        : config(NormalizeConfig(std::move(in_config))), rng(in_seed),
          equipment_rng(in_seed ^ 0xd1b54a32d192ed03ULL) {
        agents.reserve(config.agent_count);
        snapshot.agents.reserve(config.agent_count);
        Reset(in_seed);
    }

    void ChooseIntent(AgentRuntime& agent, bool initial) noexcept {
        const double margin = 6.0;
        const bool near_edge = agent.locomotion.position.x < static_cast<double>(config.world_min.x) + margin ||
            agent.locomotion.position.x > static_cast<double>(config.world_max.x) - margin ||
            agent.locomotion.position.z < static_cast<double>(config.world_min.y) + margin ||
            agent.locomotion.position.z > static_cast<double>(config.world_max.y) - margin;
        agent.intent.mode = initial
            ? (agent.id % 2U == 1U ? LocomotionMode::Walk : LocomotionMode::Run)
            : (rng.Unit() < 0.5 ? LocomotionMode::Walk : LocomotionMode::Run);
        agent.intent.speed_amplitude = rng.Range(0.58, 1.0);
        agent.intent.speed_direction_radians = rng.Range(-0.35, 0.35);
        if (near_edge) {
            const Vec2 center{
                0.5 * static_cast<double>(config.world_min.x + config.world_max.x),
                0.5 * static_cast<double>(config.world_min.y + config.world_max.y),
            };
            agent.intent.orientation_yaw_radians = AngleTo(agent.locomotion.position, center);
            agent.intent.speed_direction_radians = 0.0;
        } else if (initial) {
            agent.intent.orientation_yaw_radians = agent.team == Team::Azure ? 0.5 * kPi : -0.5 * kPi;
        } else {
            agent.intent.orientation_yaw_radians = agent.locomotion.yaw_radians + rng.Range(-1.15, 1.15);
        }
        agent.intent_ticks_remaining = rng.Range(55U, 125U);
    }

    void ChooseSwordStateDuration(AgentRuntime& agent) noexcept {
        agent.sword_state_ticks_remaining = equipment_rng.Range(75U, 180U);
    }

    void BuildAgents() noexcept {
        agents.clear();
        for (std::uint32_t index = 0; index < config.agent_count; ++index) {
            AgentRuntime agent{};
            agent.id = index + 1U;
            agent.team = index % 2U == 0U ? Team::Azure : Team::Crimson;
            const double lane = static_cast<double>(index / 2U) * 2.5;
            agent.locomotion.position = agent.team == Team::Azure
                ? Vec2{-7.0 - lane, -2.0 + lane}
                : Vec2{7.0 + lane, 2.0 - lane};
            agent.locomotion.yaw_radians = agent.team == Team::Azure ? 0.5 * kPi : -0.5 * kPi;
            agent.locomotion.previous_yaw_radians = agent.locomotion.yaw_radians;
            ChooseIntent(agent, true);
            agent.sword_equipped = true;
            agent.sword_state = equipment_rng.Unit() < 0.5 ? SwordState::Sheathed : SwordState::Drawn;
            ChooseSwordStateDuration(agent);
            agents.push_back(agent);
        }
    }

    void PublishSnapshot() noexcept {
        snapshot.tick = tick;
        snapshot.time_seconds = static_cast<double>(tick) / static_cast<double>(config.tick_rate_hz);
        snapshot.seed = seed;
        snapshot.agents.resize(agents.size());
        const double dt = 1.0 / static_cast<double>(config.tick_rate_hz);
        for (std::size_t index = 0; index < agents.size(); ++index) {
            const AgentRuntime& source = agents[index];
            AgentSnapshot& target = snapshot.agents[index];
            target.id = source.id;
            target.team = source.team;
            target.position = {static_cast<float>(source.locomotion.position.x),
                static_cast<float>(source.locomotion.position.z), 0.0f};
            target.facing_radians = static_cast<float>(source.locomotion.yaw_radians);
            target.locomotion_mode = source.intent.mode;
            target.locomotion_response = source.locomotion.response;
            target.root_velocity = {static_cast<float>(source.locomotion.velocity.x),
                static_cast<float>(source.locomotion.velocity.z), 0.0f};
            target.root_speed_mps = static_cast<float>(std::hypot(
                source.locomotion.velocity.x, source.locomotion.velocity.z));
            target.speed_stick_direction_radians = static_cast<float>(source.intent.speed_direction_radians);
            target.speed_stick_amplitude = static_cast<float>(source.intent.speed_amplitude);
            target.orientation_stick_yaw_radians = static_cast<float>(source.intent.orientation_yaw_radians);
            target.pose_phase = PosePhase(source.locomotion, source.intent.mode);
            target.sword_equipped = source.sword_equipped;
            target.sword_state = source.sword_state;
            target.future_roots = PredictFutureRoots(source.locomotion, source.intent, dt);
        }
    }

    void Reset(std::uint64_t new_seed) noexcept {
        seed = new_seed;
        tick = 0;
        rng.Reset(seed);
        equipment_rng.Reset(seed ^ 0xd1b54a32d192ed03ULL);
#if PROPHECY_ENABLE_REWIND
        replaying = false;
        replay_source = {};
        replay.seed = seed;
        replay.end_tick = 0;
        replay.initial_config = config;
#endif
        BuildAgents();
        PublishSnapshot();
    }

    void Tick() noexcept {
        const double dt = 1.0 / static_cast<double>(config.tick_rate_hz);
        for (AgentRuntime& agent : agents) {
            if (agent.intent_ticks_remaining == 0U) ChooseIntent(agent, false);
            else --agent.intent_ticks_remaining;
            if (agent.sword_equipped) {
                if (agent.sword_state_ticks_remaining == 0U) {
                    agent.sword_state = agent.sword_state == SwordState::Sheathed
                        ? SwordState::Drawn : SwordState::Sheathed;
                    ChooseSwordStateDuration(agent);
                } else {
                    --agent.sword_state_ticks_remaining;
                }
            }
            StepLocomotion(agent.locomotion, agent.intent, dt);
        }
        ++tick;
#if PROPHECY_ENABLE_REWIND
        if (!replaying) replay.end_tick = tick;
#endif
        PublishSnapshot();
    }

    SimulationConfig config{};
    SimulationSnapshot snapshot{};
    std::vector<AgentRuntime> agents{};
    StableRng rng;
    StableRng equipment_rng;
    std::uint64_t seed = 0;
    std::uint64_t tick = 0;
#if PROPHECY_ENABLE_REWIND
    ReplayLog replay{};
    ReplayLog replay_source{};
    bool replaying = false;
#endif
};

SimulationConfig MakeDefaultConfig() { return {}; }
const char* ToString(Team team) noexcept { return team == Team::Azure ? "Azure" : "Crimson"; }
const char* ToString(SwordState state) noexcept {
    return state == SwordState::Drawn ? "drawn" : "sheathed";
}

Simulation::Simulation(SimulationConfig config, std::uint64_t seed) noexcept
    : impl_(std::make_unique<Impl>(std::move(config), seed)) {}
Simulation::~Simulation() = default;
Simulation::Simulation(Simulation&&) noexcept = default;
Simulation& Simulation::operator=(Simulation&&) noexcept = default;

void Simulation::Tick() noexcept { impl_->Tick(); }
void Simulation::Reset(std::uint64_t seed) noexcept { impl_->Reset(seed); }

void Simulation::BeginReplay(const ReplayLog& replay) noexcept {
#if PROPHECY_ENABLE_REWIND
    const ReplayLog source = replay;
    impl_->config = NormalizeConfig(source.initial_config);
    impl_->Reset(source.seed);
    impl_->replay_source = source;
    impl_->replaying = true;
#else
    (void)replay;
#endif
}

bool Simulation::SeekReplay(const ReplayLog& replay, std::uint64_t target_tick) noexcept {
#if PROPHECY_ENABLE_REWIND
    if (target_tick > replay.end_tick) return false;
    BeginReplay(replay);
    while (impl_->tick < target_tick) impl_->Tick();
    return impl_->tick == target_tick;
#else
    (void)replay;
    (void)target_tick;
    return false;
#endif
}

bool Simulation::ResumeRecordingFromReplay() noexcept {
#if PROPHECY_ENABLE_REWIND
    if (!impl_->replaying || impl_->tick != impl_->replay_source.end_tick) return false;
    impl_->replay = impl_->replay_source;
    impl_->replay.end_tick = impl_->tick;
    impl_->replay_source = {};
    impl_->replaying = false;
    return true;
#else
    return false;
#endif
}

const ReplayLog& Simulation::RecordedReplay() const noexcept {
#if PROPHECY_ENABLE_REWIND
    return impl_->replay;
#else
    static const ReplayLog empty{};
    return empty;
#endif
}

bool Simulation::IsReplaying() const noexcept {
#if PROPHECY_ENABLE_REWIND
    return impl_->replaying;
#else
    return false;
#endif
}

const SimulationSnapshot& Simulation::Snapshot() const noexcept { return impl_->snapshot; }
const SimulationConfig& Simulation::Config() const noexcept { return impl_->config; }
std::uint64_t Simulation::Seed() const noexcept { return impl_->seed; }
double Simulation::TickSeconds() const noexcept { return 1.0 / static_cast<double>(impl_->config.tick_rate_hz); }

}  // namespace prophecy::sim
