#include "prophecy/sim/simulation.h"

#include <array>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>

namespace {

namespace sim = ::prophecy::sim;
int failures = 0;

void Check(bool condition, const char* message) {
    if (condition) return;
    std::fprintf(stderr, "FAIL: %s\n", message);
    ++failures;
}

bool EqualAgent(const sim::AgentSnapshot& a, const sim::AgentSnapshot& b) {
    if (a.id != b.id || a.team != b.team || a.position.x != b.position.x ||
        a.position.y != b.position.y || a.position.z != b.position.z ||
        a.facing_radians != b.facing_radians || a.locomotion_mode != b.locomotion_mode ||
        a.locomotion_response != b.locomotion_response || a.root_velocity.x != b.root_velocity.x ||
        a.root_velocity.y != b.root_velocity.y || a.root_velocity.z != b.root_velocity.z ||
        a.root_speed_mps != b.root_speed_mps ||
        a.speed_stick_direction_radians != b.speed_stick_direction_radians ||
        a.speed_stick_amplitude != b.speed_stick_amplitude ||
        a.orientation_stick_yaw_radians != b.orientation_stick_yaw_radians ||
        a.pose_phase != b.pose_phase || a.sword_equipped != b.sword_equipped ||
        a.sword_state != b.sword_state) return false;
    for (std::size_t index = 0; index < a.future_roots.size(); ++index) {
        if (a.future_roots[index].position.x != b.future_roots[index].position.x ||
            a.future_roots[index].position.z != b.future_roots[index].position.z ||
            a.future_roots[index].yaw_radians != b.future_roots[index].yaw_radians) return false;
    }
    return true;
}

bool EqualAgents(const sim::SimulationSnapshot& left, const sim::SimulationSnapshot& right) {
    if (left.agents.size() != right.agents.size()) return false;
    for (std::size_t index = 0; index < left.agents.size(); ++index) {
        if (!EqualAgent(left.agents[index], right.agents[index])) return false;
    }
    return true;
}

void TestTwoAgentLocomotionScenario() {
    sim::Simulation first({}, 1337);
    sim::Simulation second({}, 1337);
    sim::Simulation different({}, 1338);
    Check(first.Snapshot().agents.size() == 2U, "the default scenario must contain exactly two agents");
    Check(first.Snapshot().agents[0].team == sim::Team::Azure &&
        first.Snapshot().agents[1].team == sim::Team::Crimson, "the two agents must be on opposite teams");
    Check(first.Snapshot().agents[0].locomotion_mode == sim::LocomotionMode::Walk &&
        first.Snapshot().agents[1].locomotion_mode == sim::LocomotionMode::Run,
        "the initial command must exercise both locomotion policies");
    Check(first.Snapshot().agents[0].sword_equipped && first.Snapshot().agents[1].sword_equipped,
        "both default agents must own equipped swords");
    Check(EqualAgents(first.Snapshot(), second.Snapshot()), "the same seed must reproduce all initial stick inputs");
    Check(!EqualAgents(first.Snapshot(), different.Snapshot()), "a new seed must change the locomotion intent stream");
}

void TestDeterministicSwordStateExercise() {
    sim::Simulation simulation({}, 1337);
    const std::array<sim::SwordState, 2> initial{
        simulation.Snapshot().agents[0].sword_state,
        simulation.Snapshot().agents[1].sword_state,
    };
    std::array<bool, 2> changed{};
    for (int tick = 0; tick < 220; ++tick) {
        simulation.Tick();
        for (std::size_t index = 0; index < changed.size(); ++index) {
            changed[index] = changed[index] || simulation.Snapshot().agents[index].sword_state != initial[index];
        }
    }
    Check(changed[0] && changed[1], "each equipped agent must independently change sword state");
}

void TestMoverDrivenMotionAndFutureRoots() {
    sim::Simulation simulation({}, 42);
    const sim::SimulationSnapshot initial = simulation.Snapshot();
    for (int tick = 0; tick < 120; ++tick) simulation.Tick();
    const sim::SimulationSnapshot& moved = simulation.Snapshot();
    Check(moved.tick == 120U, "fixed-step ticks must advance monotonically");
    Check(std::fabs(moved.time_seconds - 4.0) < 1.0e-9,
        "simulation time must derive exactly from the 30 Hz tick");
    Check(!EqualAgents(initial, moved), "stick commands must produce mover-authored root motion");
    for (const sim::AgentSnapshot& agent : moved.agents) {
        Check(agent.root_speed_mps > 0.0f, "each locomotion agent must publish nonzero root speed");
        Check(agent.future_roots.size() == sim::kFutureRootWindow,
            "each locomotion agent must publish exactly eight future roots");
        Check(agent.future_roots.front().position.x != static_cast<double>(agent.position.x) ||
            agent.future_roots.front().position.z != static_cast<double>(agent.position.y),
            "the first future root must advance from the current root");
    }
}

void TestLocomotionPrimitives() {
    Check(sim::DirectionFromAngle(0.0).x == 0.0 && sim::DirectionFromAngle(0.0).z == 1.0,
        "zero stick angle must use the dataset's positive-Z convention");
    Check(std::fabs(sim::DirectionalSpeedCap(sim::LocomotionMode::Walk, 0.0) - 2.0000178813934326) < 1.0e-12,
        "walk forward cap must match the source dataset");
    Check(std::fabs(sim::DirectionalSpeedCap(sim::LocomotionMode::Run, 0.0) - 5.0) < 1.0e-12,
        "run forward cap must match the source dataset");
    sim::LocomotionState state{};
    sim::LocomotionIntent intent{sim::LocomotionMode::Run, 0.0, 1.0, 0.0};
    sim::StepLocomotion(state, intent, 1.0 / 30.0);
    Check(state.position.z > 0.0 && state.velocity.z > 0.0,
        "forward run stick must infer forward root motion");
}

void TestReplayAndReset() {
    sim::Simulation simulation({}, 2026);
    for (int tick = 0; tick < 137; ++tick) simulation.Tick();
    const sim::SimulationSnapshot expected = simulation.Snapshot();
    for (int tick = 137; tick < 400; ++tick) simulation.Tick();
    const sim::ReplayLog tape = simulation.RecordedReplay();
#if PROPHECY_ENABLE_REWIND
    Check(tape.seed == 2026U && tape.end_tick == 400U, "rewind tape must retain seed and live head tick");
    Check(simulation.SeekReplay(tape, 137U), "an in-range locomotion tick must be seekable");
    Check(simulation.Snapshot().tick == 137U && EqualAgents(simulation.Snapshot(), expected),
        "replay must reproduce the exact root and future-window state at a requested tick");
    Check(!simulation.SeekReplay(tape, 401U), "replay seek must reject ticks beyond the recorded head");
    Check(simulation.SeekReplay(tape, tape.end_tick), "the live head must be replayable");
    Check(simulation.ResumeRecordingFromReplay(), "recording must resume at the replay head");
#else
    Check(tape.end_tick == 0U && !simulation.IsReplaying(),
        "shipping builds must carry no rewind history or replay state");
#endif
    simulation.Reset(2026);
    Check(simulation.Snapshot().tick == 0U, "reset must return to tick zero");
    Check(simulation.RecordedReplay().end_tick == 0U, "reset must clear the rewind head");
}

void TestConfigNormalization() {
    sim::SimulationConfig config{};
    config.agent_count = 0;
    config.tick_rate_hz = 0.0f;
    config.world_min = {5.0f, 7.0f, 0.0f};
    config.world_max = {-5.0f, -7.0f, 0.0f};
    sim::Simulation simulation(config, 1);
    Check(simulation.Config().agent_count == 1U, "agent count must never normalize below one");
    Check(simulation.Config().tick_rate_hz == 1.0f, "tick rate must never normalize below one hertz");
    Check(simulation.Config().world_min.x == -5.0f && simulation.Config().world_max.y == 7.0f,
        "inverted world bounds must normalize");
}

void TestTickPerformance() {
    sim::Simulation simulation({}, 7);
    constexpr int ticks = 250'000;
    const auto start = std::chrono::steady_clock::now();
    for (int tick = 0; tick < ticks; ++tick) simulation.Tick();
    const double elapsed = std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();
    Check(elapsed < 3.0, "two-agent locomotion ticking and future roots must remain lightweight");
}

}  // namespace

int main() {
    TestTwoAgentLocomotionScenario();
    TestMoverDrivenMotionAndFutureRoots();
    TestDeterministicSwordStateExercise();
    TestLocomotionPrimitives();
    TestReplayAndReset();
    TestConfigNormalization();
    TestTickPerformance();
    if (failures == 0) std::printf("All locomotion simulation tests passed.\n");
    return failures == 0 ? EXIT_SUCCESS : EXIT_FAILURE;
}
