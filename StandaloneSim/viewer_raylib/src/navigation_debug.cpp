#include "navigation_debug.h"

#include "navigation_artifact.h"

#include "raymath.h"
#include "rlgl.h"

#include <DetourAlloc.h>
#include <DetourNavMesh.h>
#include <DetourNavMeshQuery.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <limits>
#include <memory>
#include <unordered_map>
#include <utility>
#include <vector>

namespace prophecy::viewer {
namespace {

constexpr std::size_t kMaximumIndexedVerticesPerMesh = 65'535U;
constexpr float kSurfaceLiftMeters = 0.035f;
constexpr Color kWalkableFill{30, 225, 132, 118};
constexpr Color kWalkableWire{205, 255, 225, 215};
constexpr Color kPortalColor{255, 178, 52, 255};
constexpr Color kTestRouteColor{54, 219, 255, 255};
constexpr Color kTestStartColor{72, 156, 255, 255};
constexpr Color kTestGoalColor{255, 80, 187, 255};
constexpr float kTestAgentSpeedMetersPerSecond = 1.4f;
constexpr float kTestGoalHoldSeconds = 2.5f;
constexpr std::array<Color, 8> kIslandColors{{
    {235, 82, 104, 118}, {83, 173, 255, 118}, {255, 193, 67, 118},
    {195, 111, 255, 118}, {47, 211, 211, 118}, {255, 126, 61, 118},
    {177, 221, 76, 118}, {242, 104, 201, 118}}};

struct NavMeshDeleter {
    void operator()(dtNavMesh* mesh) const noexcept { dtFreeNavMesh(mesh); }
};

struct NavQueryDeleter {
    void operator()(dtNavMeshQuery* query) const noexcept { dtFreeNavMeshQuery(query); }
};

using NavMeshPtr = std::unique_ptr<dtNavMesh, NavMeshDeleter>;
using NavQueryPtr = std::unique_ptr<dtNavMeshQuery, NavQueryDeleter>;

template <std::size_t Size>
std::string ReadLabel(const char (&label)[Size]) {
    const char* end = std::find(label, label + Size, '\0');
    return std::string(label, end);
}

const float* DetailVertex(const dtMeshTile& tile, const dtPoly& polygon,
    const dtPolyDetail& detail, const unsigned char index) {
    if (index < polygon.vertCount) return &tile.verts[polygon.verts[index] * 3U];
    return &tile.detailVerts[(detail.vertBase + index - polygon.vertCount) * 3U];
}

}  // namespace

bool NavigationDebugSurface::Load(const std::string& path, std::string& error) {
    Shutdown();
    std::ifstream input(path, std::ios::binary);
    if (!input) {
        error = "Could not open navigation artifact: " + path;
        return false;
    }

    navigation::FileHeader header{};
    input.read(reinterpret_cast<char*>(&header), sizeof(header));
    if (!input || header.magic != navigation::kMagic ||
        header.version != navigation::kVersion) {
        error = "Unsupported navigation artifact: " + path;
        return false;
    }

    NavMeshPtr nav_mesh(dtAllocNavMesh());
    if (!nav_mesh || dtStatusFailed(nav_mesh->init(&header.nav_params))) {
        error = "Could not allocate navigation debug mesh.";
        return false;
    }
    for (std::uint32_t tile_index = 0U; tile_index < header.tile_count; ++tile_index) {
        navigation::TileHeader tile_header{};
        input.read(reinterpret_cast<char*>(&tile_header), sizeof(tile_header));
        if (!input || tile_header.data_size == 0U) {
            error = "Navigation artifact contains an invalid tile header.";
            return false;
        }
        auto* tile_data = static_cast<unsigned char*>(dtAlloc(tile_header.data_size, DT_ALLOC_PERM));
        if (tile_data == nullptr) {
            error = "Could not allocate a navigation tile.";
            return false;
        }
        input.read(reinterpret_cast<char*>(tile_data), tile_header.data_size);
        if (!input || dtStatusFailed(nav_mesh->addTile(tile_data,
                static_cast<int>(tile_header.data_size), DT_TILE_FREE_DATA,
                tile_header.tile_reference, nullptr))) {
            dtFree(tile_data);
            error = "Could not load a navigation tile.";
            return false;
        }
    }
    std::vector<navigation::Portal> portal_records;
    portal_records.reserve(header.portal_count);
    portals_.reserve(static_cast<std::size_t>(header.portal_count) * 2U);
    for (std::uint32_t portal_index = 0U; portal_index < header.portal_count; ++portal_index) {
        navigation::Portal portal{};
        input.read(reinterpret_cast<char*>(&portal), sizeof(portal));
        if (!input || portal.first_polygon == 0 || portal.second_polygon == 0) {
            error = "Navigation artifact contains an invalid entrance portal.";
            return false;
        }
        portal_records.push_back(portal);
        portals_.push_back({portal.first[0], portal.first[2] + kSurfaceLiftMeters,
            portal.first[1]});
        portals_.push_back({portal.second[0], portal.second[2] + kSurfaceLiftMeters,
            portal.second[1]});
    }

    test_start_house_ = ReadLabel(header.test_start_house);
    test_goal_house_ = ReadLabel(header.test_goal_house);
    if (!test_start_house_.empty() && !test_goal_house_.empty()) {
        NavQueryPtr query(dtAllocNavMeshQuery());
        if (!query || dtStatusFailed(query->init(nav_mesh.get(), 8192))) {
            error = "Could not initialize the attic navigation test query.";
            return false;
        }
        const float start[3]{header.test_start[0], header.test_start[2], header.test_start[1]};
        const float goal[3]{header.test_goal[0], header.test_goal[2], header.test_goal[1]};
        const float extents[3]{0.75f, 1.0f, 0.75f};
        dtQueryFilter filter{};
        filter.setIncludeFlags(1U);
        dtPolyRef start_polygon = 0;
        dtPolyRef goal_polygon = 0;
        float nearest_start[3]{};
        float nearest_goal[3]{};
        if (dtStatusFailed(query->findNearestPoly(start, extents, &filter,
                &start_polygon, nearest_start)) || start_polygon == 0 ||
            dtStatusFailed(query->findNearestPoly(goal, extents, &filter,
                &goal_polygon, nearest_goal)) || goal_polygon == 0) {
            error = "Could not locate the saved attic navigation test endpoints.";
            return false;
        }
        std::array<dtPolyRef, 2048> corridor{};
        int corridor_count = 0;
        if (dtStatusFailed(query->findPath(start_polygon, goal_polygon,
                nearest_start, nearest_goal, &filter, corridor.data(), &corridor_count,
                static_cast<int>(corridor.size()))) || corridor_count == 0 ||
            corridor[static_cast<std::size_t>(corridor_count - 1)] != goal_polygon) {
            error = "The saved attic navigation test route is no longer connected.";
            return false;
        }
        std::array<float, 2048 * 3> straight_points{};
        std::array<unsigned char, 2048> straight_flags{};
        std::array<dtPolyRef, 2048> straight_polygons{};
        int straight_count = 0;
        if (dtStatusFailed(query->findStraightPath(nearest_start, nearest_goal,
                corridor.data(), corridor_count, straight_points.data(), straight_flags.data(),
                straight_polygons.data(), &straight_count, 2048)) || straight_count < 2) {
            error = "Could not construct the saved attic navigation test route.";
            return false;
        }
        test_route_.reserve(static_cast<std::size_t>(straight_count));
        test_route_distances_.reserve(static_cast<std::size_t>(straight_count));
        for (int point_index = 0; point_index < straight_count; ++point_index) {
            const float* point = &straight_points[static_cast<std::size_t>(point_index) * 3U];
            const Vector3 world{point[0], point[1], point[2]};
            if (!test_route_.empty()) {
                test_route_length_ += Vector3Distance(test_route_.back(), world);
            }
            test_route_.push_back(world);
            test_route_distances_.push_back(test_route_length_);
        }
    }

    const dtNavMesh& read_only_nav_mesh = *nav_mesh;
    std::vector<dtPolyRef> polygon_references;
    std::unordered_map<dtPolyRef, std::size_t> polygon_indices;
    for (int tile_index = 0; tile_index < read_only_nav_mesh.getMaxTiles(); ++tile_index) {
        const dtMeshTile* tile = read_only_nav_mesh.getTile(tile_index);
        if (tile == nullptr || tile->header == nullptr) continue;
        const dtPolyRef base = read_only_nav_mesh.getPolyRefBase(tile);
        for (int polygon_index = 0; polygon_index < tile->header->polyCount; ++polygon_index) {
            if (tile->polys[polygon_index].getType() != DT_POLYTYPE_GROUND ||
                (tile->polys[polygon_index].flags & 1U) == 0U) continue;
            const dtPolyRef reference = base | static_cast<dtPolyRef>(polygon_index);
            polygon_indices.emplace(reference, polygon_references.size());
            polygon_references.push_back(reference);
        }
    }
    std::vector<std::size_t> component_parents(polygon_references.size());
    for (std::size_t index = 0U; index < component_parents.size(); ++index) {
        component_parents[index] = index;
    }
    const auto find_component = [&component_parents](std::size_t index) {
        while (component_parents[index] != index) {
            component_parents[index] = component_parents[component_parents[index]];
            index = component_parents[index];
        }
        return index;
    };
    const auto unite_components = [&component_parents, &find_component](
        std::size_t first, std::size_t second) {
        first = find_component(first);
        second = find_component(second);
        if (first != second) component_parents[second] = first;
    };
    for (int tile_index = 0; tile_index < read_only_nav_mesh.getMaxTiles(); ++tile_index) {
        const dtMeshTile* tile = read_only_nav_mesh.getTile(tile_index);
        if (tile == nullptr || tile->header == nullptr) continue;
        const dtPolyRef base = read_only_nav_mesh.getPolyRefBase(tile);
        for (int polygon_index = 0; polygon_index < tile->header->polyCount; ++polygon_index) {
            const dtPoly& polygon = tile->polys[polygon_index];
            const auto current = polygon_indices.find(
                base | static_cast<dtPolyRef>(polygon_index));
            if (current == polygon_indices.end()) continue;
            for (unsigned int link_index = polygon.firstLink; link_index != DT_NULL_LINK;
                 link_index = tile->links[link_index].next) {
                const auto neighbor = polygon_indices.find(tile->links[link_index].ref);
                if (neighbor != polygon_indices.end()) {
                    unite_components(current->second, neighbor->second);
                }
            }
        }
    }
    for (const navigation::Portal& portal : portal_records) {
        const auto first = polygon_indices.find(portal.first_polygon);
        const auto second = polygon_indices.find(portal.second_polygon);
        if (first != polygon_indices.end() && second != polygon_indices.end()) {
            unite_components(first->second, second->second);
        }
    }
    std::unordered_map<std::size_t, std::size_t> component_sizes;
    for (std::size_t index = 0U; index < polygon_references.size(); ++index) {
        ++component_sizes[find_component(index)];
    }
    component_count_ = component_sizes.size();
    const auto exterior = std::max_element(component_sizes.begin(), component_sizes.end(),
        [](const auto& first, const auto& second) { return first.second < second.second; });
    const std::size_t exterior_component = exterior == component_sizes.end()
        ? std::numeric_limits<std::size_t>::max() : exterior->first;

    std::vector<float> positions;
    std::vector<unsigned char> colors;
    std::vector<unsigned short> indices;
    positions.reserve(kMaximumIndexedVerticesPerMesh * 3U);
    colors.reserve(kMaximumIndexedVerticesPerMesh * 4U);

    const auto flush = [&]() -> bool {
        if (indices.empty()) return true;
        Mesh mesh{};
        mesh.vertexCount = static_cast<int>(positions.size() / 3U);
        mesh.triangleCount = static_cast<int>(indices.size() / 3U);
        mesh.vertices = static_cast<float*>(MemAlloc(
            static_cast<unsigned int>(positions.size() * sizeof(float))));
        mesh.colors = static_cast<unsigned char*>(MemAlloc(
            static_cast<unsigned int>(colors.size())));
        mesh.indices = static_cast<unsigned short*>(MemAlloc(
            static_cast<unsigned int>(indices.size() * sizeof(unsigned short))));
        if (mesh.vertices == nullptr || mesh.colors == nullptr || mesh.indices == nullptr) {
            if (mesh.vertices != nullptr) MemFree(mesh.vertices);
            if (mesh.colors != nullptr) MemFree(mesh.colors);
            if (mesh.indices != nullptr) MemFree(mesh.indices);
            return false;
        }
        std::copy(positions.begin(), positions.end(), mesh.vertices);
        std::copy(colors.begin(), colors.end(), mesh.colors);
        std::copy(indices.begin(), indices.end(), mesh.indices);
        UploadMesh(&mesh, false);
        meshes_.push_back(mesh);
        positions.clear();
        colors.clear();
        indices.clear();
        return true;
    };

    for (int tile_index = 0; tile_index < read_only_nav_mesh.getMaxTiles(); ++tile_index) {
        const dtMeshTile* tile = read_only_nav_mesh.getTile(tile_index);
        if (tile == nullptr || tile->header == nullptr) continue;
        for (int polygon_index = 0; polygon_index < tile->header->polyCount; ++polygon_index) {
            const dtPoly& polygon = tile->polys[polygon_index];
            if (polygon.getType() != DT_POLYTYPE_GROUND ||
                (polygon.flags & 1U) == 0U) continue;
            const dtPolyRef reference = read_only_nav_mesh.getPolyRefBase(tile) |
                static_cast<dtPolyRef>(polygon_index);
            const auto indexed = polygon_indices.find(reference);
            const std::size_t component = indexed == polygon_indices.end()
                ? std::numeric_limits<std::size_t>::max()
                : find_component(indexed->second);
            const Color surface_color = component == exterior_component
                ? kWalkableFill
                : kIslandColors[component % kIslandColors.size()];
            const dtPolyDetail& detail = tile->detailMeshes[polygon_index];
            for (unsigned int triangle_index = 0; triangle_index < detail.triCount;
                 ++triangle_index) {
                if (positions.size() / 3U + 3U > kMaximumIndexedVerticesPerMesh && !flush()) {
                    error = "Could not allocate a navigation debug surface chunk.";
                    Shutdown();
                    return false;
                }
                const unsigned char* triangle =
                    &tile->detailTris[(detail.triBase + triangle_index) * 4U];
                // Detour is already X/Y-up/Z, exactly raylib's world convention.
                // Reverse winding because the detail triangles face the opposite
                // way under raylib's front-face convention.
                constexpr int order[3]{0, 2, 1};
                for (const int corner : order) {
                    const float* vertex = DetailVertex(*tile, polygon, detail, triangle[corner]);
                    const unsigned short local_index =
                        static_cast<unsigned short>(positions.size() / 3U);
                    positions.push_back(vertex[0]);
                    positions.push_back(vertex[1] + kSurfaceLiftMeters);
                    positions.push_back(vertex[2]);
                    colors.push_back(surface_color.r);
                    colors.push_back(surface_color.g);
                    colors.push_back(surface_color.b);
                    colors.push_back(surface_color.a);
                    indices.push_back(local_index);
                }
                ++triangle_count_;
            }
        }
    }
    if (!flush()) {
        error = "Could not allocate a navigation debug surface chunk.";
        Shutdown();
        return false;
    }
    fill_material_ = LoadMaterialDefault();
    fill_material_.maps[MATERIAL_MAP_DIFFUSE].color = WHITE;
    wire_material_ = LoadMaterialDefault();
    wire_material_.maps[MATERIAL_MAP_DIFFUSE].color = kWalkableWire;
    loaded_ = true;
    return true;
}

bool NavigationDebugSurface::Reload(const std::string& path, std::string& error) {
    NavigationDebugSurface replacement{};
    if (!replacement.Load(path, error)) return false;
    meshes_.swap(replacement.meshes_);
    std::swap(fill_material_, replacement.fill_material_);
    std::swap(wire_material_, replacement.wire_material_);
    portals_.swap(replacement.portals_);
    test_route_.swap(replacement.test_route_);
    test_route_distances_.swap(replacement.test_route_distances_);
    test_start_house_.swap(replacement.test_start_house_);
    test_goal_house_.swap(replacement.test_goal_house_);
    std::swap(test_route_length_, replacement.test_route_length_);
    std::swap(triangle_count_, replacement.triangle_count_);
    std::swap(component_count_, replacement.component_count_);
    std::swap(loaded_, replacement.loaded_);
    replacement.Shutdown();
    return true;
}

void NavigationDebugSurface::Draw() const noexcept {
    if (!loaded_) return;
    rlDisableBackfaceCulling();
    BeginBlendMode(BLEND_ALPHA);
    for (const Mesh& mesh : meshes_) DrawMesh(mesh, fill_material_, MatrixIdentity());
    EndBlendMode();
    rlEnableWireMode();
    for (const Mesh& mesh : meshes_) DrawMesh(mesh, wire_material_, MatrixIdentity());
    rlDisableWireMode();
    for (std::size_t index = 0U; index + 1U < portals_.size(); index += 2U) {
        DrawCylinderEx(portals_[index], portals_[index + 1U], 0.055f, 0.055f, 8,
            kPortalColor);
        DrawSphere(portals_[index], 0.10f, kPortalColor);
        DrawSphere(portals_[index + 1U], 0.10f, kPortalColor);
    }
    // Keep the test proof readable through roofs and walls; the cached surface
    // itself remains depth-tested.
    rlDisableDepthTest();
    for (std::size_t index = 1U; index < test_route_.size(); ++index) {
        Vector3 first = test_route_[index - 1U];
        Vector3 second = test_route_[index];
        first.y += kSurfaceLiftMeters * 2.0f;
        second.y += kSurfaceLiftMeters * 2.0f;
        DrawCylinderEx(first, second, 0.055f, 0.055f, 8, kTestRouteColor);
    }
    if (test_route_.size() >= 2U) {
        Vector3 start = test_route_.front();
        Vector3 goal = test_route_.back();
        start.y += 0.18f;
        goal.y += 0.22f;
        DrawSphere(start, 0.18f, kTestStartColor);
        DrawSphere(goal, 0.22f, kTestGoalColor);
        DrawCylinderEx(goal, Vector3Add(goal, {0.0f, 1.4f, 0.0f}),
            0.035f, 0.035f, 8, kTestGoalColor);
    }
    rlEnableDepthTest();
    rlEnableBackfaceCulling();
}

bool NavigationDebugSurface::SampleTestRoute(const double time_seconds,
    Vector3& position, Vector3& velocity) const noexcept {
    position = {};
    velocity = {};
    if (test_route_.size() < 2U || test_route_length_ <= 0.0f ||
        test_route_distances_.size() != test_route_.size()) return false;
    const double travel_seconds = static_cast<double>(test_route_length_) /
        static_cast<double>(kTestAgentSpeedMetersPerSecond);
    const double cycle_seconds = travel_seconds + static_cast<double>(kTestGoalHoldSeconds);
    const double cycle_time = std::fmod(std::max(0.0, time_seconds), cycle_seconds);
    if (cycle_time >= travel_seconds) {
        position = test_route_.back();
        return true;
    }
    const float distance = static_cast<float>(cycle_time) * kTestAgentSpeedMetersPerSecond;
    const auto upper = std::upper_bound(test_route_distances_.begin(),
        test_route_distances_.end(), distance);
    const std::size_t second_index = std::clamp<std::size_t>(
        static_cast<std::size_t>(std::distance(test_route_distances_.begin(), upper)),
        1U, test_route_.size() - 1U);
    const std::size_t first_index = second_index - 1U;
    const float segment_start = test_route_distances_[first_index];
    const float segment_end = test_route_distances_[second_index];
    const float fraction = segment_end > segment_start
        ? std::clamp((distance - segment_start) / (segment_end - segment_start), 0.0f, 1.0f)
        : 0.0f;
    position = Vector3Lerp(test_route_[first_index], test_route_[second_index], fraction);
    const Vector3 direction = Vector3Normalize(
        Vector3Subtract(test_route_[second_index], test_route_[first_index]));
    velocity = Vector3Scale(direction, kTestAgentSpeedMetersPerSecond);
    return true;
}

void NavigationDebugSurface::Shutdown() noexcept {
    for (Mesh& mesh : meshes_) UnloadMesh(mesh);
    if (fill_material_.maps != nullptr) UnloadMaterial(fill_material_);
    if (wire_material_.maps != nullptr) UnloadMaterial(wire_material_);
    meshes_.clear();
    portals_.clear();
    test_route_.clear();
    test_route_distances_.clear();
    test_start_house_.clear();
    test_goal_house_.clear();
    test_route_length_ = 0.0f;
    fill_material_ = {};
    wire_material_ = {};
    triangle_count_ = 0U;
    component_count_ = 0U;
    loaded_ = false;
}

}  // namespace prophecy::viewer
