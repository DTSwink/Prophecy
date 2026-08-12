#pragma once

#include <cstddef>
#include <cstdint>

namespace prophecy::bridge {

constexpr std::uint32_t kMagic = 0x50425247U;  // PBRG
constexpr std::uint32_t kVersion = 3U;
constexpr std::size_t kMaximumVillagerCount = 100U;
constexpr std::size_t kMaximumAgentCount = kMaximumVillagerCount + 1U;

struct AgentState {
    float position[3]{};  // Sim/Unreal axes in metres: X, Y, Z-up.
    float velocity[3]{};
    float facing_radians = 0.0f;
    float speed_direction_radians = 0.0f;  // Root-relative mover stick.
    float speed_amplitude = 0.0f;
    float orientation_yaw_radians = 0.0f;  // World-relative mover stick.
    float speed_scale = 1.0f;
    float turn_scale = 1.0f;
    std::uint32_t locomotion_mode = 0U;  // 0 Walk, 1 Run, 2 Crawl.
    std::uint32_t physical_world_blocked = 0U;  // One-shot Unreal wall-contact correction.
    std::uint32_t active = 0U;
};

/**
 * Fixed-size, binary PIE bridge shared by Unreal and the standalone viewer.
 *
 * Each direction owns one sequence counter. Writers make the counter odd,
 * write their complete payload, then make it even. Readers only accept an
 * unchanged even sequence, so neither process ever consumes a torn frame.
 */
struct SharedState {
    std::uint32_t magic = kMagic;
    std::uint32_t version = kVersion;
    std::uint32_t byte_size = 0U;
    std::uint32_t villager_count = 0U;
    std::uint32_t total_agent_count = 0U;
    volatile std::int32_t unreal_sequence = 0;
    volatile std::int32_t sim_sequence = 0;
    volatile std::int32_t shutdown_requested = 0;
    volatile std::int32_t sim_ready = 0;
    AgentState initial_player{};
    AgentState unreal_agents[kMaximumAgentCount]{};
    // For villagers, position is one-time spawn/debug data. Continuous runtime
    // authority is the mover intent in the remaining fields, not this position.
    AgentState sim_agents[kMaximumAgentCount]{};
    char error_message[256]{};
};

static_assert(sizeof(std::int32_t) == 4U, "The PIE bridge requires 32-bit sequence counters.");
static_assert(offsetof(SharedState, unreal_sequence) % alignof(std::int32_t) == 0U);
static_assert(offsetof(SharedState, sim_sequence) % alignof(std::int32_t) == 0U);

}  // namespace prophecy::bridge
