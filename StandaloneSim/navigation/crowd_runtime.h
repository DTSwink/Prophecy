#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <memory>
#include <string>

namespace prophecy::navigation {

constexpr std::size_t kCrowdTestAgentCount = 100U;
constexpr std::size_t kCrowdMaximumAgentCount = 101U;

struct CrowdAgentSample {
    std::array<float, 3> position{};  // Sim X/Y/Z, with Z vertical.
    std::array<float, 3> velocity{};
    float distance_travelled_m = 0.0f;
    float facing_radians = 0.0f;
    bool locomotion_active = false;
    bool active = false;
};

struct CrowdTickMetrics {
    double elapsed_milliseconds = 0.0;
    double rolling_average_milliseconds = 0.0;
    bool navigation_updated = false;
    std::uint32_t active_agents = 0U;
    std::uint64_t completed_targets = 0U;
    std::uint64_t assigned_targets = 0U;
    std::uint64_t assigned_attic_targets = 0U;
    std::uint64_t jam_events = 0U;
    std::uint64_t recovered_jams = 0U;
    std::uint64_t stall_recovery_events = 0U;
    float maximum_jam_seconds = 0.0f;
    std::uint32_t jammed_agents = 0U;
    std::uint32_t corner_stalled_agents = 0U;
};

struct CrowdBehaviorProbeResult {
    bool distant_agents_avoided = false;
    bool distant_agents_passed = false;
    bool face_to_face_agents_passed = false;
    bool face_to_face_agents_kept_moving = false;
    float maximum_distant_lateral_offset_m = 0.0f;
    float minimum_face_to_face_separation_m = 0.0f;
    float minimum_face_to_face_forward_speed_mps = 0.0f;
};

class CrowdRuntime {
public:
    CrowdRuntime();
    ~CrowdRuntime();
    CrowdRuntime(CrowdRuntime&&) noexcept;
    CrowdRuntime& operator=(CrowdRuntime&&) noexcept;
    CrowdRuntime(const CrowdRuntime&) = delete;
    CrowdRuntime& operator=(const CrowdRuntime&) = delete;

    static bool RunBehaviorProbe(const std::string& navigation_path,
        CrowdBehaviorProbeResult& result, std::string& error);
    bool Load(const std::string& navigation_path, std::uint64_t seed, std::string& error,
        std::size_t agent_count = kCrowdTestAgentCount);
    CrowdTickMetrics Update(float tick_seconds) noexcept;
    bool SetAgentTransform(std::size_t index, const std::array<float, 3>& position,
        float facing_radians, bool keep_navigation_target) noexcept;
    [[nodiscard]] CrowdAgentSample Agent(std::size_t index) const noexcept;
    [[nodiscard]] std::size_t AgentCount() const noexcept;
    [[nodiscard]] std::size_t VillageTargetCount() const noexcept;
    [[nodiscard]] std::size_t AtticTargetCount() const noexcept;
    [[nodiscard]] std::size_t BottleneckZoneCount() const noexcept;
    [[nodiscard]] std::size_t BottleneckPolygonCount() const noexcept;
    [[nodiscard]] bool IsLoaded() const noexcept;

private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

}  // namespace prophecy::navigation
