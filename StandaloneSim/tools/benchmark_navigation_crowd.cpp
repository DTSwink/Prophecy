#include "crowd_runtime.h"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <limits>
#include <numeric>
#include <string>
#include <vector>

namespace {

double Percentile(const std::vector<double>& sorted, const double fraction) {
    if (sorted.empty()) return 0.0;
    const std::size_t index = static_cast<std::size_t>(std::clamp(
        fraction * static_cast<double>(sorted.size() - 1U), 0.0,
        static_cast<double>(sorted.size() - 1U)));
    return sorted[index];
}

}  // namespace

int main(int argc, char** argv) {
    if (argc < 2 || argc > 4) {
        std::cerr << "Usage: prophecy_navigation_crowd_benchmark <mybasic.navbin> "
                     "[measured_ticks] [warmup_ticks]\n";
        return 2;
    }
    const std::size_t measured_ticks = argc >= 3
        ? static_cast<std::size_t>(std::strtoull(argv[2], nullptr, 10)) : 9000U;
    const std::size_t warmup_ticks = argc >= 4
        ? static_cast<std::size_t>(std::strtoull(argv[3], nullptr, 10)) : 600U;
    if (measured_ticks == 0U) return 2;

    prophecy::navigation::CrowdBehaviorProbeResult behavior{};
    std::string error;
    if (!prophecy::navigation::CrowdRuntime::RunBehaviorProbe(argv[1], behavior, error)) {
        std::cerr << error << '\n';
        return 1;
    }
    std::cout << std::fixed << std::setprecision(4)
              << "behavior distant_avoided=" << behavior.distant_agents_avoided
              << " distant_passed=" << behavior.distant_agents_passed
              << " distant_lateral_m=" << behavior.maximum_distant_lateral_offset_m
              << " face_to_face_passed=" << behavior.face_to_face_agents_passed
              << " face_to_face_kept_moving=" << behavior.face_to_face_agents_kept_moving
              << " face_to_face_min_separation_m="
              << behavior.minimum_face_to_face_separation_m
              << " face_to_face_min_forward_mps="
              << behavior.minimum_face_to_face_forward_speed_mps << '\n';

    prophecy::navigation::CrowdRuntime crowd{};
    if (!crowd.Load(argv[1], 0xC0FFEEULL, error)) {
        std::cerr << error << '\n';
        return 1;
    }
    constexpr float tick_seconds = 1.0f / 30.0f;
    for (std::size_t tick = 0U; tick < warmup_ticks; ++tick) crowd.Update(tick_seconds);

    std::vector<double> samples;
    samples.reserve(measured_ticks);
    std::vector<double> active_samples;
    active_samples.reserve((measured_ticks + 1U) / 2U);
    prophecy::navigation::CrowdTickMetrics final_metrics{};
    double minimum_separation = std::numeric_limits<double>::max();
    std::uint32_t maximum_jammed_agents = 0U;
    std::uint32_t maximum_corner_stalled_agents = 0U;
    for (std::size_t tick = 0U; tick < measured_ticks; ++tick) {
        final_metrics = crowd.Update(tick_seconds);
        samples.push_back(final_metrics.elapsed_milliseconds);
        if (final_metrics.navigation_updated) {
            active_samples.push_back(final_metrics.elapsed_milliseconds);
        }
        maximum_jammed_agents = std::max(
            maximum_jammed_agents, final_metrics.jammed_agents);
        maximum_corner_stalled_agents = std::max(
            maximum_corner_stalled_agents, final_metrics.corner_stalled_agents);
        if ((tick % 30U) == 0U) {
            for (std::size_t first = 0U; first < crowd.AgentCount(); ++first) {
                const auto a = crowd.Agent(first);
                if (!a.active) continue;
                for (std::size_t second = first + 1U; second < crowd.AgentCount(); ++second) {
                    const auto b = crowd.Agent(second);
                    if (!b.active || std::fabs(a.position[2] - b.position[2]) > 1.0f) continue;
                    const double dx = static_cast<double>(a.position[0] - b.position[0]);
                    const double dy = static_cast<double>(a.position[1] - b.position[1]);
                    minimum_separation = std::min(minimum_separation, std::sqrt(dx * dx + dy * dy));
                }
            }
        }
    }
    std::sort(samples.begin(), samples.end());
    std::sort(active_samples.begin(), active_samples.end());
    const double mean = std::accumulate(samples.begin(), samples.end(), 0.0) /
        static_cast<double>(samples.size());
    std::cout << std::fixed << std::setprecision(4)
              << "agents=" << final_metrics.active_agents
              << " village_targets=" << crowd.VillageTargetCount()
              << " attic_targets=" << crowd.AtticTargetCount()
              << " bottleneck_zones=" << crowd.BottleneckZoneCount()
              << " bottleneck_polygons=" << crowd.BottleneckPolygonCount() << '\n'
              << "navigation_ms mean=" << mean
              << " p50=" << Percentile(samples, 0.50)
              << " p95=" << Percentile(samples, 0.95)
              << " p99=" << Percentile(samples, 0.99)
              << " max=" << samples.back() << '\n'
              << "active_15hz_update_ms mean="
              << (active_samples.empty() ? 0.0 : std::accumulate(
                    active_samples.begin(), active_samples.end(), 0.0) /
                    static_cast<double>(active_samples.size()))
              << " p95=" << Percentile(active_samples, 0.95)
              << " max=" << (active_samples.empty() ? 0.0 : active_samples.back()) << '\n'
              << "completed_targets=" << final_metrics.completed_targets
              << " assigned_targets=" << final_metrics.assigned_targets
              << " assigned_attic_targets=" << final_metrics.assigned_attic_targets
              << " minimum_sampled_separation_m="
              << (std::isfinite(minimum_separation) ? minimum_separation : 0.0) << '\n'
              << "jam_events=" << final_metrics.jam_events
              << " recovered_jams=" << final_metrics.recovered_jams
              << " stall_recoveries=" << final_metrics.stall_recovery_events
              << " active_jams=" << final_metrics.jammed_agents
              << " max_simultaneous_jams=" << maximum_jammed_agents
              << " max_jam_seconds=" << final_metrics.maximum_jam_seconds
              << " max_corner_stalls=" << maximum_corner_stalled_agents << '\n';
    return behavior.distant_agents_avoided && behavior.distant_agents_passed &&
        behavior.face_to_face_agents_passed && behavior.face_to_face_agents_kept_moving &&
        final_metrics.active_agents == prophecy::navigation::kCrowdTestAgentCount &&
        final_metrics.completed_targets > 0U && final_metrics.assigned_attic_targets > 0U &&
        final_metrics.jam_events == 0U && maximum_corner_stalled_agents == 0U &&
        mean < 0.5 ? 0 : 1;
}
