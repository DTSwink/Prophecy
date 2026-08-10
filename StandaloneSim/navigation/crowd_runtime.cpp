#include "crowd_runtime.h"

#include "navigation_artifact.h"

#include <DetourAlloc.h>
#include <DetourCrowd.h>
#include <DetourNavMesh.h>
#include <DetourNavMeshQuery.h>
#include <DetourObstacleAvoidance.h>

#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstring>
#include <fstream>
#include <limits>
#include <memory>
#include <numeric>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

namespace prophecy::navigation {
namespace {

constexpr float kAgentRadiusMeters = 0.30f;
constexpr float kAgentHeightMeters = 1.72f;
constexpr float kAgentMaximumSpeedMetersPerSecond = 2.0f;
constexpr float kArrivalRadiusMeters = 0.38f;
constexpr float kMinimumTargetDistanceMeters = 6.0f;
constexpr float kAtticMinimumHeightMeters = 2.5f;
constexpr float kMaximumTargetHeightMeters = 4.5f;
constexpr float kVillageMinimumX = -35.5f;
constexpr float kVillageMaximumX = 31.8f;
constexpr float kVillageMinimumY = -55.2f;
constexpr float kVillageMaximumY = 21.8f;
constexpr std::size_t kAtticAssignmentPeriod = 5U;
constexpr std::size_t kTimingWindow = 256U;
constexpr float kNavigationUpdateSeconds = 1.0f / 15.0f;
constexpr float kJamDetectionSeconds = 1.5f;
constexpr float kJamMaximumProgressMetersPerSecond = 0.25f;
constexpr float kJamRecoveryProgressMetersPerSecond = 0.50f;
constexpr float kPreventiveStallRecoverySeconds = 1.0f;
constexpr float kJamCorridorRecoveryStepMeters = 0.10f;
constexpr float kBottleneckMaximumWallDistanceMeters = 0.35f;

struct NavMeshDeleter {
    void operator()(dtNavMesh* value) const noexcept { dtFreeNavMesh(value); }
};

struct NavQueryDeleter {
    void operator()(dtNavMeshQuery* value) const noexcept { dtFreeNavMeshQuery(value); }
};

struct CrowdDeleter {
    void operator()(dtCrowd* value) const noexcept { dtFreeCrowd(value); }
};

using NavMeshPtr = std::unique_ptr<dtNavMesh, NavMeshDeleter>;
using NavQueryPtr = std::unique_ptr<dtNavMeshQuery, NavQueryDeleter>;
using CrowdPtr = std::unique_ptr<dtCrowd, CrowdDeleter>;

std::array<float, 3> PolygonCenter(const dtMeshTile& tile, const dtPoly& polygon) {
    std::array<float, 3> center{};
    for (unsigned int vertex = 0U; vertex < polygon.vertCount; ++vertex) {
        const float* value = &tile.verts[polygon.verts[vertex] * 3U];
        center[0] += value[0];
        center[1] += value[1];
        center[2] += value[2];
    }
    const float inverse = 1.0f / static_cast<float>(polygon.vertCount);
    center[0] *= inverse;
    center[1] *= inverse;
    center[2] *= inverse;
    return center;
}

std::array<float, 3> DetourToSim(const float* point) {
    return {point[0], point[2], point[1]};
}

void ConfigureSoftObstacleAvoidance(dtCrowd& crowd) {
    dtObstacleAvoidanceParams avoidance{};
    std::memcpy(&avoidance, crowd.getObstacleAvoidanceParams(0), sizeof(avoidance));
    avoidance.velBias = 0.65f;
    avoidance.weightDesVel = 2.0f;
    avoidance.weightCurVel = 0.25f;
    avoidance.weightSide = 0.75f;
    avoidance.weightToi = 2.5f;
    avoidance.horizTime = 2.5f;
    avoidance.adaptiveDivs = 5;
    avoidance.adaptiveRings = 2;
    avoidance.adaptiveDepth = 1;
    crowd.setObstacleAvoidanceParams(0, &avoidance);
}

dtCrowdAgentParams MakeCrowdAgentParameters() {
    dtCrowdAgentParams params{};
    params.radius = kAgentRadiusMeters;
    params.height = kAgentHeightMeters;
    params.maxAcceleration = 8.0f;
    params.maxSpeed = kAgentMaximumSpeedMetersPerSecond;
    params.collisionQueryRange = params.radius * 8.0f;
    params.pathOptimizationRange = params.radius * 20.0f;
    params.separationWeight = 0.0f;
    params.updateFlags = DT_CROWD_ANTICIPATE_TURNS | DT_CROWD_OBSTACLE_AVOIDANCE;
    params.obstacleAvoidanceType = 0U;
    params.queryFilterType = 0U;
    return params;
}

void ApplyNonBlockingIntent(dtCrowd& crowd, dtNavMeshQuery& query,
    const int* crowd_indices, const std::size_t agent_count,
    const std::array<float, 3>* previous_positions, const float update_seconds) {
    if (update_seconds <= 0.0f) return;
    const dtQueryFilter* filter = crowd.getFilter(0);
    for (std::size_t slot = 0U; slot < agent_count; ++slot) {
        const int crowd_index = crowd_indices[slot];
        dtCrowdAgent* agent = crowd_index >= 0 ? crowd.getEditableAgent(crowd_index) : nullptr;
        if (agent == nullptr || !agent->active ||
            agent->state != DT_CROWDAGENT_STATE_WALKING ||
            agent->targetState != DT_CROWDAGENT_TARGET_VALID ||
            agent->corridor.getFirstPoly() == 0) continue;

        float desired_x = agent->dvel[0];
        float desired_z = agent->dvel[2];
        const float desired_length = std::sqrt(
            desired_x * desired_x + desired_z * desired_z);
        if (desired_length <= 1.0e-4f || agent->desiredSpeed <= 1.0e-4f) continue;
        desired_x /= desired_length;
        desired_z /= desired_length;

        float direction_x = agent->vel[0];
        float direction_z = agent->vel[2];
        const float selected_length = std::sqrt(
            direction_x * direction_x + direction_z * direction_z);
        if (selected_length > 1.0e-4f) {
            direction_x /= selected_length;
            direction_z /= selected_length;
        }
        if (selected_length <= 1.0e-4f ||
            direction_x * desired_x + direction_z * desired_z <= 0.0f) {
            direction_x = desired_x;
            direction_z = desired_z;
        }

        const float speed = std::min(agent->desiredSpeed, agent->params.maxSpeed);
        const std::array<float, 3>& previous = previous_positions[slot];
        if (!agent->corridor.movePosition(previous.data(), &query, filter)) continue;
        const float intended[3]{
            previous[0] + direction_x * speed * update_seconds,
            previous[1],
            previous[2] + direction_z * speed * update_seconds};
        if (!agent->corridor.movePosition(intended, &query, filter)) continue;
        const float* constrained = agent->corridor.getPos();
        agent->npos[0] = constrained[0];
        agent->npos[1] = constrained[1];
        agent->npos[2] = constrained[2];
        agent->vel[0] = direction_x * speed;
        agent->vel[1] = 0.0f;
        agent->vel[2] = direction_z * speed;
    }
}

}  // namespace

struct CrowdRuntime::Impl {
    struct Candidate {
        dtPolyRef polygon = 0;
        std::array<float, 3> position{};  // Detour X/Y-up/Z.
        bool attic = false;
    };

    struct AgentTarget {
        Candidate target{};
        bool assigned = false;
    };

    struct AgentProgress {
        std::array<float, 3> last_position{};
        float distance_travelled_m = 0.0f;
        float facing_radians = 0.0f;
        float stalled_seconds = 0.0f;
        float jam_duration_seconds = 0.0f;
        bool jammed = false;
        bool corridor_recovery = false;
    };

    struct BottleneckZone {
        std::vector<dtPolyRef> polygons{};
    };

    NavMeshPtr nav_mesh{};
    NavQueryPtr query{};
    CrowdPtr crowd{};
    std::vector<Candidate> village_targets{};
    std::vector<std::size_t> ground_target_indices{};
    std::vector<std::size_t> attic_target_indices{};
    std::vector<BottleneckZone> bottleneck_zones{};
    std::unordered_map<dtPolyRef, std::size_t> bottleneck_by_polygon{};
    std::array<int, kCrowdTestAgentCount> crowd_indices{};
    std::array<AgentTarget, kCrowdTestAgentCount> targets{};
    std::array<AgentProgress, kCrowdTestAgentCount> progress{};
    std::array<double, kTimingWindow> timing_window{};
    std::uint64_t random_state = 1U;
    std::uint64_t assignment_serial = 0U;
    std::uint64_t assigned_targets = 0U;
    std::uint64_t assigned_attic_targets = 0U;
    std::uint64_t completed_targets = 0U;
    std::uint64_t jam_events = 0U;
    std::uint64_t recovered_jams = 0U;
    std::uint64_t stall_recovery_events = 0U;
    float maximum_jam_seconds = 0.0f;
    std::size_t timing_cursor = 0U;
    std::size_t timing_count = 0U;
    float navigation_accumulator_seconds = 0.0f;

    std::uint64_t NextRandom() noexcept {
        random_state += 0x9e3779b97f4a7c15ULL;
        std::uint64_t value = random_state;
        value = (value ^ (value >> 30U)) * 0xbf58476d1ce4e5b9ULL;
        value = (value ^ (value >> 27U)) * 0x94d049bb133111ebULL;
        return value ^ (value >> 31U);
    }

    std::size_t RandomIndex(const std::size_t size) noexcept {
        return size > 0U ? static_cast<std::size_t>(NextRandom() % size) : 0U;
    }

    bool LoadMesh(const std::string& path, FileHeader& header, std::string& error) {
        std::ifstream input(path, std::ios::binary);
        input.read(reinterpret_cast<char*>(&header), sizeof(header));
        if (!input || header.magic != kMagic || header.version != kVersion) {
            error = "Unsupported crowd navigation artifact: " + path;
            return false;
        }
        nav_mesh.reset(dtAllocNavMesh());
        if (!nav_mesh || dtStatusFailed(nav_mesh->init(&header.nav_params))) {
            error = "Could not allocate the crowd navigation mesh.";
            return false;
        }
        for (std::uint32_t tile_index = 0U; tile_index < header.tile_count; ++tile_index) {
            TileHeader tile_header{};
            input.read(reinterpret_cast<char*>(&tile_header), sizeof(tile_header));
            if (!input || tile_header.data_size == 0U) {
                error = "Crowd navigation contains an invalid tile header.";
                return false;
            }
            auto* tile_data = static_cast<unsigned char*>(
                dtAlloc(tile_header.data_size, DT_ALLOC_PERM));
            if (tile_data == nullptr) {
                error = "Could not allocate a crowd navigation tile.";
                return false;
            }
            input.read(reinterpret_cast<char*>(tile_data), tile_header.data_size);
            if (!input || dtStatusFailed(nav_mesh->addTile(tile_data,
                    static_cast<int>(tile_header.data_size), DT_TILE_FREE_DATA,
                    tile_header.tile_reference, nullptr))) {
                dtFree(tile_data);
                error = "Could not load a crowd navigation tile.";
                return false;
            }
        }
        query.reset(dtAllocNavMeshQuery());
        if (!query || dtStatusFailed(query->init(nav_mesh.get(), 8192))) {
            error = "Could not initialize the crowd navigation query.";
            return false;
        }
        return true;
    }

    void BuildBottleneckZones(const std::unordered_set<dtPolyRef>& reachable) {
        dtQueryFilter filter{};
        filter.setIncludeFlags(1U);
        std::unordered_set<dtPolyRef> narrow;
        narrow.reserve(reachable.size());
        for (const dtPolyRef reference : reachable) {
            const dtMeshTile* tile = nullptr;
            const dtPoly* polygon = nullptr;
            if (dtStatusFailed(nav_mesh->getTileAndPolyByRef(reference, &tile, &polygon)) ||
                tile == nullptr || polygon == nullptr ||
                polygon->getType() != DT_POLYTYPE_GROUND || (polygon->flags & 1U) == 0U) continue;
            const std::array<float, 3> center = PolygonCenter(*tile, *polygon);
            float point[3]{};
            bool over_polygon = false;
            if (dtStatusFailed(query->closestPointOnPoly(reference, center.data(),
                    point, &over_polygon)) ||
                point[0] < kVillageMinimumX || point[0] > kVillageMaximumX ||
                point[2] < kVillageMinimumY || point[2] > kVillageMaximumY ||
                point[1] > kMaximumTargetHeightMeters) continue;
            float wall_distance = 0.0f;
            float wall_position[3]{};
            float wall_normal[3]{};
            if (dtStatusSucceed(query->findDistanceToWall(reference, point, 2.0f, &filter,
                    &wall_distance, wall_position, wall_normal)) &&
                wall_distance < kBottleneckMaximumWallDistanceMeters) {
                narrow.insert(reference);
            }
        }

        std::unordered_set<dtPolyRef> remaining = narrow;
        std::vector<dtPolyRef> pending;
        while (!remaining.empty()) {
            BottleneckZone zone{};
            pending.clear();
            const dtPolyRef first = *remaining.begin();
            remaining.erase(first);
            pending.push_back(first);
            for (std::size_t cursor = 0U; cursor < pending.size(); ++cursor) {
                const dtPolyRef reference = pending[cursor];
                zone.polygons.push_back(reference);
                const dtMeshTile* tile = nullptr;
                const dtPoly* polygon = nullptr;
                if (dtStatusFailed(nav_mesh->getTileAndPolyByRef(reference, &tile, &polygon)) ||
                    tile == nullptr || polygon == nullptr) continue;
                for (unsigned int link_index = polygon->firstLink; link_index != DT_NULL_LINK;
                     link_index = tile->links[link_index].next) {
                    const dtPolyRef neighbor = tile->links[link_index].ref;
                    if (neighbor != 0 && remaining.erase(neighbor) > 0U) {
                        pending.push_back(neighbor);
                    }
                }
            }
            const std::size_t zone_index = bottleneck_zones.size();
            for (const dtPolyRef reference : zone.polygons) {
                bottleneck_by_polygon.emplace(reference, zone_index);
            }
            bottleneck_zones.push_back(std::move(zone));
        }
    }

    void ApplyJamCorridorRecovery() noexcept {
        const dtQueryFilter* filter = crowd->getFilter(0);
        for (std::size_t slot = 0U; slot < kCrowdTestAgentCount; ++slot) {
            AgentProgress& state = progress[slot];
            const float blocked_seconds = state.jammed
                ? state.jam_duration_seconds : state.stalled_seconds;
            if (blocked_seconds < kPreventiveStallRecoverySeconds) continue;
            const int crowd_index = crowd_indices[slot];
            dtCrowdAgent* agent = crowd_index >= 0
                ? crowd->getEditableAgent(crowd_index) : nullptr;
            if (agent == nullptr || !agent->active || agent->ncorners <= 0 ||
                agent->corridor.getFirstPoly() == 0) continue;
            int corner_index = 0;
            float direction_x = 0.0f;
            float direction_z = 0.0f;
            float distance = 0.0f;
            for (; corner_index < agent->ncorners; ++corner_index) {
                direction_x = agent->cornerVerts[corner_index * 3] - agent->npos[0];
                direction_z = agent->cornerVerts[corner_index * 3 + 2] - agent->npos[2];
                distance = std::sqrt(direction_x * direction_x + direction_z * direction_z);
                if (distance > 0.05f) break;
            }
            if (corner_index >= agent->ncorners || distance <= 0.05f) continue;
            direction_x /= distance;
            direction_z /= distance;
            const float step = std::min(kJamCorridorRecoveryStepMeters, distance);
            const float desired[3]{agent->npos[0] + direction_x * step,
                agent->npos[1], agent->npos[2] + direction_z * step};
            float constrained[3]{};
            dtPolyRef visited[16]{};
            int visited_count = 0;
            if (dtStatusFailed(query->moveAlongSurface(agent->corridor.getFirstPoly(),
                    agent->npos, desired, filter, constrained, visited, &visited_count, 16)) ||
                !agent->corridor.movePosition(constrained, query.get(), filter)) continue;
            const float* corridor_position = agent->corridor.getPos();
            agent->npos[0] = corridor_position[0];
            agent->npos[1] = corridor_position[1];
            agent->npos[2] = corridor_position[2];
            agent->vel[0] = direction_x * kAgentMaximumSpeedMetersPerSecond;
            agent->vel[1] = 0.0f;
            agent->vel[2] = direction_z * kAgentMaximumSpeedMetersPerSecond;
            if (!state.corridor_recovery) {
                state.corridor_recovery = true;
                ++stall_recovery_events;
            }
        }
    }

    bool BuildTargetPools(const FileHeader& header, std::string& error) {
        const float start[3]{header.test_start[0], header.test_start[2], header.test_start[1]};
        const float extents[3]{1.0f, 1.5f, 1.0f};
        dtQueryFilter filter{};
        filter.setIncludeFlags(1U);
        dtPolyRef start_polygon = 0;
        float nearest_start[3]{};
        if (header.test_start_house[0] == '\0' ||
            dtStatusFailed(query->findNearestPoly(start, extents, &filter,
                &start_polygon, nearest_start)) || start_polygon == 0) {
            error = "The crowd test requires the validated attic route component.";
            return false;
        }

        std::unordered_set<dtPolyRef> visited;
        std::vector<dtPolyRef> pending;
        visited.reserve(4096U);
        pending.reserve(4096U);
        visited.insert(start_polygon);
        pending.push_back(start_polygon);
        for (std::size_t cursor = 0U; cursor < pending.size(); ++cursor) {
            const dtPolyRef reference = pending[cursor];
            const dtMeshTile* tile = nullptr;
            const dtPoly* polygon = nullptr;
            if (dtStatusFailed(nav_mesh->getTileAndPolyByRef(reference, &tile, &polygon)) ||
                tile == nullptr || polygon == nullptr) continue;
            for (unsigned int link_index = polygon->firstLink; link_index != DT_NULL_LINK;
                 link_index = tile->links[link_index].next) {
                const dtPolyRef neighbor = tile->links[link_index].ref;
                if (neighbor == 0 || !visited.insert(neighbor).second) continue;
                pending.push_back(neighbor);
            }
        }

        village_targets.reserve(visited.size());
        for (const dtPolyRef reference : visited) {
            const dtMeshTile* tile = nullptr;
            const dtPoly* polygon = nullptr;
            if (dtStatusFailed(nav_mesh->getTileAndPolyByRef(reference, &tile, &polygon)) ||
                tile == nullptr || polygon == nullptr ||
                polygon->getType() != DT_POLYTYPE_GROUND || (polygon->flags & 1U) == 0U) continue;
            const std::array<float, 3> center = PolygonCenter(*tile, *polygon);
            float point[3]{};
            bool over_polygon = false;
            if (dtStatusFailed(query->closestPointOnPoly(reference, center.data(),
                    point, &over_polygon))) continue;
            if (point[0] < kVillageMinimumX || point[0] > kVillageMaximumX ||
                point[2] < kVillageMinimumY || point[2] > kVillageMaximumY ||
                point[1] > kMaximumTargetHeightMeters) continue;
            const bool attic = point[1] >= kAtticMinimumHeightMeters;
            village_targets.push_back({reference, {point[0], point[1], point[2]}, attic});
        }
        std::sort(village_targets.begin(), village_targets.end(),
            [](const Candidate& first, const Candidate& second) {
                if (first.polygon != second.polygon) return first.polygon < second.polygon;
                return first.position < second.position;
            });
        for (std::size_t index = 0U; index < village_targets.size(); ++index) {
            if (village_targets[index].attic) attic_target_indices.push_back(index);
            else ground_target_indices.push_back(index);
        }
        if (ground_target_indices.size() < kCrowdTestAgentCount || attic_target_indices.empty()) {
            error = "The reachable village component has insufficient crowd or attic targets.";
            return false;
        }
        BuildBottleneckZones(visited);
        return true;
    }

    bool SelectTarget(const std::size_t agent_slot, const float* current_position,
        const bool count_assignment) noexcept {
        const bool request_attic = !attic_target_indices.empty() &&
            (assignment_serial++ % kAtticAssignmentPeriod) == 0U;
        const std::vector<std::size_t>& pool = request_attic
            ? attic_target_indices : ground_target_indices;
        Candidate selected{};
        for (int attempt = 0; attempt < 32; ++attempt) {
            selected = village_targets[pool[RandomIndex(pool.size())]];
            const float dx = selected.position[0] - current_position[0];
            const float dy = selected.position[1] - current_position[1];
            const float dz = selected.position[2] - current_position[2];
            if (dx * dx + dy * dy + dz * dz >=
                kMinimumTargetDistanceMeters * kMinimumTargetDistanceMeters) break;
        }
        const int crowd_index = crowd_indices[agent_slot];
        if (crowd_index < 0 || !crowd->requestMoveTarget(
                crowd_index, selected.polygon, selected.position.data())) return false;
        targets[agent_slot].target = selected;
        targets[agent_slot].assigned = true;
        if (count_assignment) {
            ++assigned_targets;
            if (selected.attic) ++assigned_attic_targets;
        }
        return true;
    }

    bool InitializeCrowd(std::string& error) {
        crowd.reset(dtAllocCrowd());
        if (!crowd || !crowd->init(static_cast<int>(kCrowdTestAgentCount),
                kAgentRadiusMeters, nav_mesh.get())) {
            error = "Could not initialize the 100-agent Detour crowd.";
            return false;
        }
        crowd->getEditableFilter(0)->setIncludeFlags(1U);
        ConfigureSoftObstacleAvoidance(*crowd);
        const dtCrowdAgentParams params = MakeCrowdAgentParameters();

        crowd_indices.fill(-1);
        std::array<std::array<float, 3>, kCrowdTestAgentCount> starts{};
        for (std::size_t slot = 0U; slot < kCrowdTestAgentCount; ++slot) {
            Candidate candidate{};
            bool accepted = false;
            for (int attempt = 0; attempt < 128 && !accepted; ++attempt) {
                candidate = village_targets[ground_target_indices[
                    RandomIndex(ground_target_indices.size())]];
                accepted = true;
                for (std::size_t prior = 0U; prior < slot; ++prior) {
                    const float dx = candidate.position[0] - starts[prior][0];
                    const float dz = candidate.position[2] - starts[prior][2];
                    if (dx * dx + dz * dz < 0.85f * 0.85f) {
                        accepted = false;
                        break;
                    }
                }
            }
            starts[slot] = candidate.position;
            const int crowd_index = crowd->addAgent(candidate.position.data(), &params);
            if (crowd_index < 0) {
                error = "Could not place all 100 crowd agents on the village navmesh.";
                return false;
            }
            crowd_indices[slot] = crowd_index;
            progress[slot].last_position = candidate.position;
        }
        for (std::size_t slot = 0U; slot < kCrowdTestAgentCount; ++slot) {
            const dtCrowdAgent* agent = crowd->getAgent(crowd_indices[slot]);
            if (agent == nullptr || !SelectTarget(slot, agent->npos, true)) {
                error = "Could not assign the initial crowd destinations.";
                return false;
            }
        }
        return true;
    }

    CrowdTickMetrics Update(const float tick_seconds) noexcept {
        const auto started = std::chrono::steady_clock::now();
        navigation_accumulator_seconds += std::max(tick_seconds, 0.0f);
        const bool navigation_updated = navigation_accumulator_seconds + 1.0e-6f >=
            kNavigationUpdateSeconds;
        if (navigation_updated) {
            for (std::size_t slot = 0U; slot < kCrowdTestAgentCount; ++slot) {
                const int crowd_index = crowd_indices[slot];
                const dtCrowdAgent* agent = crowd_index >= 0 ? crowd->getAgent(crowd_index) : nullptr;
                if (agent == nullptr || !agent->active || !targets[slot].assigned) continue;
                const Candidate& target = targets[slot].target;
                const float dx = target.position[0] - agent->npos[0];
                const float dy = target.position[1] - agent->npos[1];
                const float dz = target.position[2] - agent->npos[2];
                const bool arrived = dx * dx + dy * dy + dz * dz <=
                    kArrivalRadiusMeters * kArrivalRadiusMeters;
                const bool failed = agent->targetState == DT_CROWDAGENT_TARGET_FAILED;
                if (arrived || failed) {
                    if (arrived) ++completed_targets;
                    (void)SelectTarget(slot, agent->npos, true);
                }
            }
            std::array<std::array<float, 3>, kCrowdTestAgentCount> previous_positions{};
            for (std::size_t slot = 0U; slot < kCrowdTestAgentCount; ++slot) {
                const int crowd_index = crowd_indices[slot];
                const dtCrowdAgent* agent = crowd_index >= 0
                    ? crowd->getAgent(crowd_index) : nullptr;
                if (agent != nullptr && agent->active) {
                    previous_positions[slot] = {
                        agent->npos[0], agent->npos[1], agent->npos[2]};
                }
            }
            crowd->update(navigation_accumulator_seconds, nullptr);
            ApplyNonBlockingIntent(*crowd, *query, crowd_indices.data(),
                kCrowdTestAgentCount, previous_positions.data(), navigation_accumulator_seconds);
            ApplyJamCorridorRecovery();
            const float update_seconds = navigation_accumulator_seconds;
            for (std::size_t slot = 0U; slot < kCrowdTestAgentCount; ++slot) {
                const int crowd_index = crowd_indices[slot];
                const dtCrowdAgent* agent = crowd_index >= 0 ? crowd->getAgent(crowd_index) : nullptr;
                if (agent == nullptr || !agent->active) continue;
                AgentProgress& state = progress[slot];
                const float dx = agent->npos[0] - state.last_position[0];
                const float dy = agent->npos[1] - state.last_position[1];
                const float dz = agent->npos[2] - state.last_position[2];
                const float displacement = std::sqrt(dx * dx + dy * dy + dz * dz);
                state.distance_travelled_m += displacement;
                state.last_position = {agent->npos[0], agent->npos[1], agent->npos[2]};
                const float progress_speed = update_seconds > 0.0f
                    ? displacement / update_seconds : 0.0f;
                const float horizontal_velocity_squared = agent->vel[0] * agent->vel[0] +
                    agent->vel[2] * agent->vel[2];
                if (horizontal_velocity_squared > 0.05f * 0.05f) {
                    state.facing_radians = std::atan2(agent->vel[0], agent->vel[2]);
                }
                const float target_dx = agent->targetPos[0] - agent->npos[0];
                const float target_dy = agent->targetPos[1] - agent->npos[1];
                const float target_dz = agent->targetPos[2] - agent->npos[2];
                const bool at_target = target_dx * target_dx + target_dy * target_dy +
                    target_dz * target_dz <= kArrivalRadiusMeters * kArrivalRadiusMeters;
                const bool expects_motion = agent->targetState == DT_CROWDAGENT_TARGET_VALID &&
                    target_dx * target_dx + target_dy * target_dy + target_dz * target_dz >
                        kArrivalRadiusMeters * kArrivalRadiusMeters &&
                    agent->desiredSpeed > 0.5f;
                if (state.jammed) {
                    if (at_target ||
                        agent->targetState == DT_CROWDAGENT_TARGET_FAILED ||
                        progress_speed >= kJamRecoveryProgressMetersPerSecond) {
                        ++recovered_jams;
                        state.jammed = false;
                        state.stalled_seconds = 0.0f;
                        state.jam_duration_seconds = 0.0f;
                        state.corridor_recovery = false;
                    } else {
                        state.jam_duration_seconds += update_seconds;
                        maximum_jam_seconds = std::max(
                            maximum_jam_seconds, state.jam_duration_seconds);
                    }
                } else if (expects_motion &&
                    progress_speed < kJamMaximumProgressMetersPerSecond) {
                    state.stalled_seconds += update_seconds;
                    if (state.stalled_seconds >= kJamDetectionSeconds) {
                        state.jammed = true;
                        state.jam_duration_seconds = state.stalled_seconds;
                        state.corridor_recovery = false;
                        ++jam_events;
                    }
                } else {
                    state.stalled_seconds = 0.0f;
                    if (progress_speed >= kJamRecoveryProgressMetersPerSecond) {
                        state.corridor_recovery = false;
                    }
                }
                maximum_jam_seconds = std::max(
                    maximum_jam_seconds, state.jam_duration_seconds);
            }
            navigation_accumulator_seconds = 0.0f;
        }
        const auto finished = std::chrono::steady_clock::now();
        const double elapsed = std::chrono::duration<double, std::milli>(
            finished - started).count();
        timing_window[timing_cursor] = elapsed;
        timing_cursor = (timing_cursor + 1U) % timing_window.size();
        timing_count = std::min(timing_count + 1U, timing_window.size());
        const double rolling_sum = std::accumulate(
            timing_window.begin(), timing_window.begin() +
                static_cast<std::ptrdiff_t>(timing_count), 0.0);
        std::uint32_t active = 0U;
        std::uint32_t jammed = 0U;
        std::uint32_t corner_stalled = 0U;
        for (std::size_t slot = 0U; slot < kCrowdTestAgentCount; ++slot) {
            const int crowd_index = crowd_indices[slot];
            const dtCrowdAgent* agent = crowd_index >= 0 ? crowd->getAgent(crowd_index) : nullptr;
            if (agent != nullptr && agent->active) ++active;
            if (progress[slot].jammed) {
                ++jammed;
                if (agent != nullptr && agent->ncorners >= 2) {
                    const float first_x = agent->cornerVerts[0] - agent->npos[0];
                    const float first_z = agent->cornerVerts[2] - agent->npos[2];
                    const float second_x = agent->cornerVerts[3] - agent->cornerVerts[0];
                    const float second_z = agent->cornerVerts[5] - agent->cornerVerts[2];
                    const float first_length = std::sqrt(
                        first_x * first_x + first_z * first_z);
                    const float second_length = std::sqrt(
                        second_x * second_x + second_z * second_z);
                    if (first_length > 1.0e-4f && second_length > 1.0e-4f &&
                        first_length < 1.4f &&
                        (first_x * second_x + first_z * second_z) /
                            (first_length * second_length) < 0.50f) ++corner_stalled;
                }
            }
        }
        return {elapsed, rolling_sum / static_cast<double>(timing_count), navigation_updated, active,
            completed_targets, assigned_targets, assigned_attic_targets, jam_events,
            recovered_jams, stall_recovery_events, maximum_jam_seconds, jammed,
            corner_stalled};
    }
};

CrowdRuntime::CrowdRuntime() : impl_(std::make_unique<Impl>()) {}
CrowdRuntime::~CrowdRuntime() = default;
CrowdRuntime::CrowdRuntime(CrowdRuntime&&) noexcept = default;
CrowdRuntime& CrowdRuntime::operator=(CrowdRuntime&&) noexcept = default;

bool CrowdRuntime::RunBehaviorProbe(const std::string& navigation_path,
    CrowdBehaviorProbeResult& result, std::string& error) {
    result = {};
    Impl probe{};
    FileHeader header{};
    if (!probe.LoadMesh(navigation_path, header, error) ||
        !probe.BuildTargetPools(header, error)) return false;

    const dtQueryFilter* filter = probe.crowd != nullptr
        ? probe.crowd->getFilter(0) : nullptr;
    dtQueryFilter navigation_filter{};
    navigation_filter.setIncludeFlags(1U);
    const dtQueryFilter* query_filter = filter != nullptr ? filter : &navigation_filter;
    Impl::Candidate first{};
    Impl::Candidate second{};
    bool pair_found = false;
    for (const std::size_t first_index : probe.ground_target_indices) {
        const Impl::Candidate& candidate_a = probe.village_targets[first_index];
        if (candidate_a.position[1] > 0.20f) continue;
        float first_wall_distance = 0.0f;
        float wall_position[3]{};
        float wall_normal[3]{};
        if (dtStatusFailed(probe.query->findDistanceToWall(candidate_a.polygon,
                candidate_a.position.data(), 3.0f, query_filter, &first_wall_distance,
                wall_position, wall_normal)) || first_wall_distance < 1.0f) continue;
        for (const std::size_t second_index : probe.ground_target_indices) {
            const Impl::Candidate& candidate_b = probe.village_targets[second_index];
            if (candidate_b.polygon == candidate_a.polygon ||
                std::fabs(candidate_b.position[1] - candidate_a.position[1]) > 0.10f) continue;
            const float dx = candidate_b.position[0] - candidate_a.position[0];
            const float dz = candidate_b.position[2] - candidate_a.position[2];
            const float distance_squared = dx * dx + dz * dz;
            if (distance_squared < 6.0f * 6.0f || distance_squared > 10.0f * 10.0f) continue;
            float second_wall_distance = 0.0f;
            if (dtStatusFailed(probe.query->findDistanceToWall(candidate_b.polygon,
                    candidate_b.position.data(), 3.0f, query_filter, &second_wall_distance,
                    wall_position, wall_normal)) || second_wall_distance < 1.0f) continue;
            float hit_fraction = 0.0f;
            float hit_normal[3]{};
            std::array<dtPolyRef, 64> ray_path{};
            int ray_path_count = 0;
            if (dtStatusFailed(probe.query->raycast(candidate_a.polygon,
                    candidate_a.position.data(), candidate_b.position.data(), query_filter,
                    &hit_fraction, hit_normal, ray_path.data(), &ray_path_count,
                    static_cast<int>(ray_path.size()))) || hit_fraction < 1.0f) continue;
            first = candidate_a;
            second = candidate_b;
            pair_found = true;
            break;
        }
        if (pair_found) break;
    }
    if (!pair_found) {
        error = "Could not find an open ground line for the crowd behavior probe.";
        return false;
    }

    const float axis_x_unscaled = second.position[0] - first.position[0];
    const float axis_z_unscaled = second.position[2] - first.position[2];
    const float axis_length = std::sqrt(
        axis_x_unscaled * axis_x_unscaled + axis_z_unscaled * axis_z_unscaled);
    const float axis_x = axis_x_unscaled / axis_length;
    const float axis_z = axis_z_unscaled / axis_length;
    const float perpendicular_x = -axis_z;
    const float perpendicular_z = axis_x;

    const auto run_pair = [&](const bool face_to_face, bool& passed,
                              float& maximum_lateral_offset,
                              float& minimum_separation,
                              float& minimum_forward_speed) {
        CrowdPtr pair(dtAllocCrowd());
        if (!pair || !pair->init(2, kAgentRadiusMeters, probe.nav_mesh.get())) return false;
        pair->getEditableFilter(0)->setIncludeFlags(1U);
        ConfigureSoftObstacleAvoidance(*pair);
        const dtCrowdAgentParams params = MakeCrowdAgentParameters();

        std::array<float, 3> start_a = first.position;
        std::array<float, 3> start_b = second.position;
        dtPolyRef start_polygon_a = first.polygon;
        dtPolyRef start_polygon_b = second.polygon;
        if (face_to_face) {
            const std::array<float, 3> midpoint{
                0.5f * (first.position[0] + second.position[0]),
                0.5f * (first.position[1] + second.position[1]),
                0.5f * (first.position[2] + second.position[2])};
            constexpr float initial_separation = 0.20f;
            const float requested_a[3]{
                midpoint[0] - axis_x * initial_separation * 0.5f,
                midpoint[1], midpoint[2] - axis_z * initial_separation * 0.5f};
            const float requested_b[3]{
                midpoint[0] + axis_x * initial_separation * 0.5f,
                midpoint[1], midpoint[2] + axis_z * initial_separation * 0.5f};
            const float extents[3]{0.50f, 0.50f, 0.50f};
            if (dtStatusFailed(probe.query->findNearestPoly(requested_a, extents,
                    query_filter, &start_polygon_a, start_a.data())) || start_polygon_a == 0 ||
                dtStatusFailed(probe.query->findNearestPoly(requested_b, extents,
                    query_filter, &start_polygon_b, start_b.data())) || start_polygon_b == 0) {
                return false;
            }
        }

        const std::array<int, 2> indices{
            pair->addAgent(start_a.data(), &params),
            pair->addAgent(start_b.data(), &params)};
        if (indices[0] < 0 || indices[1] < 0 ||
            !pair->requestMoveTarget(indices[0], second.polygon, second.position.data()) ||
            !pair->requestMoveTarget(indices[1], first.polygon, first.position.data())) return false;

        minimum_separation = std::numeric_limits<float>::max();
        minimum_forward_speed = std::numeric_limits<float>::max();
        constexpr float update_seconds = kNavigationUpdateSeconds;
        bool observed_valid_motion = false;
        for (int update = 0; update < 240; ++update) {
            std::array<std::array<float, 3>, 2> previous{};
            for (std::size_t index = 0U; index < indices.size(); ++index) {
                const dtCrowdAgent* agent = pair->getAgent(indices[index]);
                previous[index] = {agent->npos[0], agent->npos[1], agent->npos[2]};
            }
            pair->update(update_seconds, nullptr);
            ApplyNonBlockingIntent(*pair, *probe.query, indices.data(), indices.size(),
                previous.data(), update_seconds);
            const dtCrowdAgent* agent_a = pair->getAgent(indices[0]);
            const dtCrowdAgent* agent_b = pair->getAgent(indices[1]);
            if (agent_a == nullptr || agent_b == nullptr) return false;
            const float dx = agent_a->npos[0] - agent_b->npos[0];
            const float dz = agent_a->npos[2] - agent_b->npos[2];
            minimum_separation = std::min(minimum_separation,
                std::sqrt(dx * dx + dz * dz));
            const float lateral_a = std::fabs(
                (agent_a->npos[0] - start_a[0]) * perpendicular_x +
                (agent_a->npos[2] - start_a[2]) * perpendicular_z);
            const float lateral_b = std::fabs(
                (agent_b->npos[0] - start_b[0]) * perpendicular_x +
                (agent_b->npos[2] - start_b[2]) * perpendicular_z);
            maximum_lateral_offset = std::max(
                maximum_lateral_offset, std::max(lateral_a, lateral_b));
            if (agent_a->targetState == DT_CROWDAGENT_TARGET_VALID &&
                agent_b->targetState == DT_CROWDAGENT_TARGET_VALID) {
                observed_valid_motion = true;
                const float forward_a = agent_a->vel[0] * axis_x + agent_a->vel[2] * axis_z;
                const float forward_b = -(agent_b->vel[0] * axis_x + agent_b->vel[2] * axis_z);
                minimum_forward_speed = std::min(
                    minimum_forward_speed, std::min(forward_a, forward_b));
            }
            if (dx * axis_x + dz * axis_z > 0.0f) {
                passed = true;
                break;
            }
        }
        return observed_valid_motion;
    };

    float distant_minimum_separation = 0.0f;
    float distant_minimum_forward_speed = 0.0f;
    if (!run_pair(false, result.distant_agents_passed,
            result.maximum_distant_lateral_offset_m, distant_minimum_separation,
            distant_minimum_forward_speed)) {
        error = "The distant crowd behavior probe could not run.";
        return false;
    }
    result.distant_agents_avoided =
        result.maximum_distant_lateral_offset_m >= 0.05f;

    float face_to_face_lateral_offset = 0.0f;
    if (!run_pair(true, result.face_to_face_agents_passed,
            face_to_face_lateral_offset, result.minimum_face_to_face_separation_m,
            result.minimum_face_to_face_forward_speed_mps)) {
        error = "The face-to-face crowd behavior probe could not run.";
        return false;
    }
    result.face_to_face_agents_kept_moving =
        result.minimum_face_to_face_forward_speed_mps > 0.0f;
    error.clear();
    return true;
}

bool CrowdRuntime::Load(const std::string& navigation_path, const std::uint64_t seed,
    std::string& error) {
    impl_ = std::make_unique<Impl>();
    impl_->random_state = seed != 0U ? seed : 1U;
    FileHeader header{};
    if (!impl_->LoadMesh(navigation_path, header, error) ||
        !impl_->BuildTargetPools(header, error) || !impl_->InitializeCrowd(error)) return false;
    error.clear();
    return true;
}

CrowdTickMetrics CrowdRuntime::Update(const float tick_seconds) noexcept {
    return IsLoaded() ? impl_->Update(tick_seconds) : CrowdTickMetrics{};
}

CrowdAgentSample CrowdRuntime::Agent(const std::size_t index) const noexcept {
    if (!IsLoaded() || index >= kCrowdTestAgentCount) return {};
    const int crowd_index = impl_->crowd_indices[index];
    const dtCrowdAgent* agent = crowd_index >= 0 ? impl_->crowd->getAgent(crowd_index) : nullptr;
    if (agent == nullptr || !agent->active) return {};
    std::array<float, 3> displayed_position{
        agent->npos[0] + agent->vel[0] * impl_->navigation_accumulator_seconds,
        agent->npos[1] + agent->vel[1] * impl_->navigation_accumulator_seconds,
        agent->npos[2] + agent->vel[2] * impl_->navigation_accumulator_seconds};
    const float horizontal_speed = std::sqrt(
        agent->vel[0] * agent->vel[0] + agent->vel[2] * agent->vel[2]);
    const float displayed_distance = impl_->progress[index].distance_travelled_m +
        horizontal_speed * impl_->navigation_accumulator_seconds;
    const bool locomotion_active = agent->targetState == DT_CROWDAGENT_TARGET_VALID;
    return {DetourToSim(displayed_position.data()), DetourToSim(agent->vel),
        displayed_distance, impl_->progress[index].facing_radians,
        locomotion_active, true};
}

std::size_t CrowdRuntime::AgentCount() const noexcept {
    return IsLoaded() ? kCrowdTestAgentCount : 0U;
}

std::size_t CrowdRuntime::VillageTargetCount() const noexcept {
    return impl_ ? impl_->village_targets.size() : 0U;
}

std::size_t CrowdRuntime::AtticTargetCount() const noexcept {
    return impl_ ? impl_->attic_target_indices.size() : 0U;
}

std::size_t CrowdRuntime::BottleneckZoneCount() const noexcept {
    return impl_ ? impl_->bottleneck_zones.size() : 0U;
}

std::size_t CrowdRuntime::BottleneckPolygonCount() const noexcept {
    return impl_ ? impl_->bottleneck_by_polygon.size() : 0U;
}

bool CrowdRuntime::IsLoaded() const noexcept {
    return impl_ != nullptr && impl_->crowd != nullptr;
}

}  // namespace prophecy::navigation
