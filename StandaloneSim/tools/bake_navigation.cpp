#include <DetourAlloc.h>
#include <DetourNavMesh.h>
#include <DetourNavMeshBuilder.h>
#include <DetourNavMeshQuery.h>
#include <Recast.h>
#include <ChunkyTriMesh.h>
#include <nlohmann/json.hpp>

#include "navigation_artifact.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <memory>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

namespace {

using Json = nlohmann::json;

constexpr unsigned short kWalkFlag = 1U;

// Measured from the actual `my guy` actor in /Game/mybasic.
constexpr float kAgentRadiusMeters = 0.30f;
constexpr float kAgentHeightMeters = 1.72f;
constexpr float kAgentMaximumClimbMeters = 0.30f;
constexpr float kAgentMaximumSlopeDegrees = 44.765083f;

// These values represent the measured capsule without conservative rounding:
// 0.30 m radius = 3 cells, 1.72 m height = 35 cells (1.75 m), and
// 0.30 m maximum climb = 6 cells. The 10 cm horizontal raster is required
// to retain the real narrow attic stair continuation in the village houses.
constexpr float kCellSizeMeters = 0.10f;
constexpr float kCellHeightMeters = 0.05f;
constexpr int kTileSizeCells = 96;

struct SimBounds {
    std::array<float, 3> minimum{
        std::numeric_limits<float>::max(),
        std::numeric_limits<float>::max(),
        std::numeric_limits<float>::max()};
    std::array<float, 3> maximum{
        std::numeric_limits<float>::lowest(),
        std::numeric_limits<float>::lowest(),
        std::numeric_limits<float>::lowest()};
};

struct HouseInfo {
    std::string label{};
    SimBounds bounds{};
    double upper_floor_height_sum = 0.0;
    double upper_floor_area = 0.0;
};

enum class NavigationGeometryGroup : unsigned char {
    Default,
    DenseVillageHouse,
    Tent
};

struct Geometry {
    std::vector<float> vertices{};  // Recast coordinates: X, vertical Z, ground Y.
    std::vector<NavigationGeometryGroup> vertex_groups{};
    std::vector<int> triangles{};
    std::vector<HouseInfo> houses{};
    std::array<float, 3> bounds_min{};
    std::array<float, 3> bounds_max{};
    std::string map{};
};

struct NavMeshDeleter {
    void operator()(dtNavMesh* mesh) const noexcept { dtFreeNavMesh(mesh); }
};

struct NavQueryDeleter {
    void operator()(dtNavMeshQuery* query) const noexcept { dtFreeNavMeshQuery(query); }
};

struct HeightfieldDeleter {
    void operator()(rcHeightfield* value) const noexcept { rcFreeHeightField(value); }
};

struct CompactHeightfieldDeleter {
    void operator()(rcCompactHeightfield* value) const noexcept {
        rcFreeCompactHeightfield(value);
    }
};

struct ContourSetDeleter {
    void operator()(rcContourSet* value) const noexcept { rcFreeContourSet(value); }
};

struct PolyMeshDeleter {
    void operator()(rcPolyMesh* value) const noexcept { rcFreePolyMesh(value); }
};

struct DetailMeshDeleter {
    void operator()(rcPolyMeshDetail* value) const noexcept { rcFreePolyMeshDetail(value); }
};

using NavMeshPtr = std::unique_ptr<dtNavMesh, NavMeshDeleter>;
using NavQueryPtr = std::unique_ptr<dtNavMeshQuery, NavQueryDeleter>;
using HeightfieldPtr = std::unique_ptr<rcHeightfield, HeightfieldDeleter>;
using CompactHeightfieldPtr = std::unique_ptr<rcCompactHeightfield, CompactHeightfieldDeleter>;
using ContourSetPtr = std::unique_ptr<rcContourSet, ContourSetDeleter>;
using PolyMeshPtr = std::unique_ptr<rcPolyMesh, PolyMeshDeleter>;
using DetailMeshPtr = std::unique_ptr<rcPolyMeshDetail, DetailMeshDeleter>;

bool IsHouseLabel(const std::string& label) {
    return label.rfind("SM_house_", 0U) == 0U ||
        label.rfind("BP_LogCabin", 0U) == 0U || label == "tent" || label == "Tent";
}

bool IsDenseVillageHouse(const std::string& label) {
    return label.rfind("SM_house_", 0U) == 0U;
}

std::array<float, 3> ReadSimVertex(const Json& value) {
    if (!value.is_array() || value.size() != 3U ||
        !value[0].is_number() || !value[1].is_number() || !value[2].is_number()) {
        throw std::runtime_error("Collision snapshot contains an invalid vertex.");
    }
    return {value[0].get<float>(), value[1].get<float>(), value[2].get<float>()};
}

void Include(SimBounds& bounds, const std::array<float, 3>& vertex) {
    for (std::size_t axis = 0; axis < 3U; ++axis) {
        bounds.minimum[axis] = std::min(bounds.minimum[axis], vertex[axis]);
        bounds.maximum[axis] = std::max(bounds.maximum[axis], vertex[axis]);
    }
}

float UpwardTriangleArea(const std::array<float, 3>& a,
    const std::array<float, 3>& b, const std::array<float, 3>& c) {
    const std::array<double, 3> ab{
        static_cast<double>(b[0] - a[0]),
        static_cast<double>(b[1] - a[1]),
        static_cast<double>(b[2] - a[2])};
    const std::array<double, 3> ac{
        static_cast<double>(c[0] - a[0]),
        static_cast<double>(c[1] - a[1]),
        static_cast<double>(c[2] - a[2])};
    const std::array<double, 3> cross{
        ab[1] * ac[2] - ab[2] * ac[1],
        ab[2] * ac[0] - ab[0] * ac[2],
        ab[0] * ac[1] - ab[1] * ac[0]};
    const double twice_area = std::sqrt(
        cross[0] * cross[0] + cross[1] * cross[1] + cross[2] * cross[2]);
    if (twice_area <= 1.0e-12 || cross[2] / twice_area < 0.985) return 0.0f;
    return static_cast<float>(0.5 * twice_area);
}

HouseInfo& FindOrAddHouse(std::vector<HouseInfo>& houses, const std::string& label) {
    auto found = std::find_if(houses.begin(), houses.end(), [&label](const HouseInfo& house) {
        return house.label == label;
    });
    if (found != houses.end()) return *found;
    houses.push_back({});
    houses.back().label = label;
    return houses.back();
}

Geometry ReadGeometry(Json& root, const std::unordered_set<std::string>& excluded_labels = {}) {
    Geometry geometry{};
    geometry.map = root.value("map", std::string{});
    const Json& objects = root.at("objects");

    std::size_t vertex_count = 0U;
    std::size_t triangle_count = 0U;
    for (const Json& object : objects) {
        const std::string label = object.is_object()
            ? object.value("label", std::string{}) : std::string{};
        if (!object.is_object() ||
            object.value("collision_source", std::string{}) == "unreal_water_plane" ||
            excluded_labels.find(label) != excluded_labels.end()) continue;
        vertex_count += object.at("vertices").size();
        triangle_count += object.at("indices").size();
    }
    if (vertex_count > static_cast<std::size_t>(std::numeric_limits<int>::max())) {
        throw std::runtime_error("Navigation input has too many vertices for Recast.");
    }
    geometry.vertices.reserve(vertex_count * 3U);
    geometry.vertex_groups.reserve(vertex_count);
    geometry.triangles.reserve(triangle_count * 3U);

    for (const Json& object : objects) {
        if (!object.is_object()) continue;
        const std::string source = object.value("collision_source", std::string{});
        if (source == "unreal_water_plane") continue;
        const std::string label = object.value("label", std::string{});
        if (excluded_labels.find(label) != excluded_labels.end()) continue;
        const Json& vertices_json = object.at("vertices");
        const Json& indices_json = object.at("indices");
        const std::size_t base_vertex = geometry.vertices.size() / 3U;
        std::vector<std::array<float, 3>> object_vertices;
        object_vertices.reserve(vertices_json.size());
        HouseInfo* house = nullptr;
        if (IsHouseLabel(label)) house = &FindOrAddHouse(geometry.houses, label);
        const NavigationGeometryGroup navigation_group = IsDenseVillageHouse(label)
            ? NavigationGeometryGroup::DenseVillageHouse
            : ((label == "tent" || label == "Tent")
                ? NavigationGeometryGroup::Tent
                : NavigationGeometryGroup::Default);

        for (const Json& value : vertices_json) {
            const std::array<float, 3> sim = ReadSimVertex(value);
            object_vertices.push_back(sim);
            if (house != nullptr) Include(house->bounds, sim);
            // Recast and Detour use Y-up. The cached sim convention is Z-up.
            geometry.vertices.push_back(sim[0]);
            geometry.vertices.push_back(sim[2]);
            geometry.vertices.push_back(sim[1]);
            geometry.vertex_groups.push_back(navigation_group);
        }

        for (const Json& triangle : indices_json) {
            if (!triangle.is_array() || triangle.size() != 3U) {
                throw std::runtime_error("Collision snapshot contains an invalid triangle.");
            }
            const std::size_t first = triangle[0].get<std::size_t>();
            const std::size_t second = triangle[1].get<std::size_t>();
            const std::size_t third = triangle[2].get<std::size_t>();
            if (first >= object_vertices.size() || second >= object_vertices.size() ||
                third >= object_vertices.size()) {
                throw std::runtime_error("Collision snapshot contains an out-of-range triangle.");
            }
            // Sim XYZ -> Recast X/Z/Y swaps two axes and changes handedness.
            // Reverse the winding so upward collision remains upward to Recast.
            geometry.triangles.push_back(static_cast<int>(base_vertex + first));
            geometry.triangles.push_back(static_cast<int>(base_vertex + third));
            geometry.triangles.push_back(static_cast<int>(base_vertex + second));

            if (house != nullptr) {
                const float area = UpwardTriangleArea(object_vertices[first],
                    object_vertices[second], object_vertices[third]);
                const float height = (object_vertices[first][2] + object_vertices[second][2] +
                    object_vertices[third][2]) / 3.0f;
                if (area > 0.0f && height >= 2.5f && height <= 4.25f) {
                    house->upper_floor_height_sum += static_cast<double>(height) * area;
                    house->upper_floor_area += area;
                }
            }
        }
    }

    if (geometry.triangles.empty()) throw std::runtime_error("Navigation input is empty.");
    rcCalcBounds(geometry.vertices.data(), static_cast<int>(geometry.vertices.size() / 3U),
        geometry.bounds_min.data(), geometry.bounds_max.data());
    return geometry;
}

void AppendGeometry(Geometry& destination, Geometry&& source) {
    const std::size_t base_vertex = destination.vertices.size() / 3U;
    destination.vertices.insert(destination.vertices.end(),
        source.vertices.begin(), source.vertices.end());
    destination.vertex_groups.insert(destination.vertex_groups.end(),
        source.vertex_groups.begin(), source.vertex_groups.end());
    destination.triangles.reserve(destination.triangles.size() + source.triangles.size());
    for (const int index : source.triangles) {
        destination.triangles.push_back(static_cast<int>(base_vertex) + index);
    }
    destination.houses.insert(destination.houses.end(),
        std::make_move_iterator(source.houses.begin()),
        std::make_move_iterator(source.houses.end()));
    if (destination.map.empty()) destination.map = std::move(source.map);
    rcCalcBounds(destination.vertices.data(),
        static_cast<int>(destination.vertices.size() / 3U),
        destination.bounds_min.data(), destination.bounds_max.data());
}

unsigned int NextPowerOfTwo(unsigned int value) {
    --value;
    value |= value >> 1U;
    value |= value >> 2U;
    value |= value >> 4U;
    value |= value >> 8U;
    value |= value >> 16U;
    return ++value;
}

unsigned int IntegerLog2(unsigned int value) {
    unsigned int result = 0U;
    while (value > 1U) {
        value >>= 1U;
        ++result;
    }
    return result;
}

bool IsExplicitlyNonWalkableSurface(const Geometry& geometry, const int* triangle) {
    const NavigationGeometryGroup group = geometry.vertex_groups[
        static_cast<std::size_t>(triangle[0])];
    if (group == NavigationGeometryGroup::Default ||
        geometry.vertex_groups[static_cast<std::size_t>(triangle[1])] != group ||
        geometry.vertex_groups[static_cast<std::size_t>(triangle[2])] != group) return false;

    const float* first = &geometry.vertices[static_cast<std::size_t>(triangle[0]) * 3U];
    const float* second = &geometry.vertices[static_cast<std::size_t>(triangle[1]) * 3U];
    const float* third = &geometry.vertices[static_cast<std::size_t>(triangle[2]) * 3U];
    const float minimum_height = std::min({first[1], second[1], third[1]});
    const float maximum_height = std::max({first[1], second[1], third[1]});
    if (group == NavigationGeometryGroup::Tent) {
        return maximum_height > kAgentMaximumClimbMeters;
    }

    constexpr float kBenchSurfaceMinimumHeightMeters = 0.32f;
    constexpr float kBenchSurfaceMaximumHeightMeters = 0.43f;
    constexpr float kBenchTriangleMinimumAreaSquareMeters = 0.30f;
    if (minimum_height < kBenchSurfaceMinimumHeightMeters ||
        maximum_height > kBenchSurfaceMaximumHeightMeters) return false;
    const float first_edge_x = second[0] - first[0];
    const float first_edge_y = second[1] - first[1];
    const float first_edge_z = second[2] - first[2];
    const float second_edge_x = third[0] - first[0];
    const float second_edge_y = third[1] - first[1];
    const float second_edge_z = third[2] - first[2];
    const float cross_x = first_edge_y * second_edge_z - first_edge_z * second_edge_y;
    const float cross_y = first_edge_z * second_edge_x - first_edge_x * second_edge_z;
    const float cross_z = first_edge_x * second_edge_y - first_edge_y * second_edge_x;
    const float area = 0.5f * std::sqrt(
        cross_x * cross_x + cross_y * cross_y + cross_z * cross_z);
    return area >= kBenchTriangleMinimumAreaSquareMeters;
}

bool BuildTile(rcContext& context, const Geometry& geometry,
    const rcChunkyTriMesh& chunky_mesh, std::vector<int>& chunk_ids,
    int tile_x, int tile_y, const float* tile_minimum, const float* tile_maximum,
    unsigned char*& nav_data, int& nav_data_size) {
    nav_data = nullptr;
    nav_data_size = 0;

    rcConfig config{};
    config.cs = kCellSizeMeters;
    config.ch = kCellHeightMeters;
    config.walkableSlopeAngle = kAgentMaximumSlopeDegrees;
    config.walkableHeight = static_cast<int>(std::ceil(kAgentHeightMeters / config.ch));
    config.walkableClimb = static_cast<int>(std::floor(kAgentMaximumClimbMeters / config.ch));
    config.walkableRadius = static_cast<int>(std::ceil(kAgentRadiusMeters / config.cs));
    config.maxEdgeLen = static_cast<int>(12.0f / config.cs);
    config.maxSimplificationError = 1.3f;
    config.minRegionArea = 36;
    config.mergeRegionArea = 400;
    config.maxVertsPerPoly = DT_VERTS_PER_POLYGON;
    config.tileSize = kTileSizeCells;
    config.borderSize = config.walkableRadius + 3;
    config.width = config.tileSize + config.borderSize * 2;
    config.height = config.tileSize + config.borderSize * 2;
    config.detailSampleDist = config.cs * 6.0f;
    config.detailSampleMaxError = config.ch;
    rcVcopy(config.bmin, tile_minimum);
    rcVcopy(config.bmax, tile_maximum);
    config.bmin[0] -= static_cast<float>(config.borderSize) * config.cs;
    config.bmin[2] -= static_cast<float>(config.borderSize) * config.cs;
    config.bmax[0] += static_cast<float>(config.borderSize) * config.cs;
    config.bmax[2] += static_cast<float>(config.borderSize) * config.cs;

    HeightfieldPtr heightfield(rcAllocHeightfield());
    if (!heightfield || !rcCreateHeightfield(&context, *heightfield,
            config.width, config.height, config.bmin, config.bmax, config.cs, config.ch)) {
        throw std::runtime_error("Could not create a Recast heightfield.");
    }

    float query_minimum[2]{config.bmin[0], config.bmin[2]};
    float query_maximum[2]{config.bmax[0], config.bmax[2]};
    const int overlapping_chunks = rcGetChunksOverlappingRect(&chunky_mesh,
        query_minimum, query_maximum, chunk_ids.data(), static_cast<int>(chunk_ids.size()));
    if (overlapping_chunks == 0) return true;

    std::vector<unsigned char> triangle_areas(
        static_cast<std::size_t>(chunky_mesh.maxTrisPerChunk));
    for (int chunk_index = 0; chunk_index < overlapping_chunks; ++chunk_index) {
        const rcChunkyTriMeshNode& node = chunky_mesh.nodes[chunk_ids[chunk_index]];
        const int* triangles = &chunky_mesh.tris[node.i * 3];
        std::fill_n(triangle_areas.data(), static_cast<std::size_t>(node.n),
            static_cast<unsigned char>(0));
        rcMarkWalkableTriangles(&context, config.walkableSlopeAngle,
            geometry.vertices.data(), static_cast<int>(geometry.vertices.size() / 3U),
            triangles, node.n, triangle_areas.data());
        for (int triangle_index = 0; triangle_index < node.n; ++triangle_index) {
            const int* triangle = &triangles[triangle_index * 3];
            if (IsExplicitlyNonWalkableSurface(geometry, triangle)) {
                triangle_areas[static_cast<std::size_t>(triangle_index)] = 0U;
            }
        }
        if (!rcRasterizeTriangles(&context, geometry.vertices.data(),
                static_cast<int>(geometry.vertices.size() / 3U), triangles,
                triangle_areas.data(), node.n, *heightfield, config.walkableClimb)) {
            throw std::runtime_error("Could not rasterize navigation triangles.");
        }
    }

    rcFilterLowHangingWalkableObstacles(&context, config.walkableClimb, *heightfield);
    rcFilterLedgeSpans(&context, config.walkableHeight, config.walkableClimb, *heightfield);
    rcFilterWalkableLowHeightSpans(&context, config.walkableHeight, *heightfield);

    CompactHeightfieldPtr compact(rcAllocCompactHeightfield());
    if (!compact || !rcBuildCompactHeightfield(&context, config.walkableHeight,
            config.walkableClimb, *heightfield, *compact)) {
        throw std::runtime_error("Could not build a compact navigation heightfield.");
    }
    heightfield.reset();
    if (!rcErodeWalkableArea(&context, config.walkableRadius, *compact)) {
        throw std::runtime_error("Could not apply agent-radius navigation clearance.");
    }
    if (!rcBuildDistanceField(&context, *compact) ||
        !rcBuildRegions(&context, *compact, config.borderSize,
            config.minRegionArea, config.mergeRegionArea)) {
        throw std::runtime_error("Could not partition navigation regions.");
    }

    ContourSetPtr contours(rcAllocContourSet());
    if (!contours || !rcBuildContours(&context, *compact,
            config.maxSimplificationError, config.maxEdgeLen, *contours)) {
        throw std::runtime_error("Could not build navigation contours.");
    }
    if (contours->nconts == 0) return true;

    PolyMeshPtr poly_mesh(rcAllocPolyMesh());
    if (!poly_mesh || !rcBuildPolyMesh(&context, *contours,
            config.maxVertsPerPoly, *poly_mesh)) {
        throw std::runtime_error("Could not build navigation polygons.");
    }
    DetailMeshPtr detail_mesh(rcAllocPolyMeshDetail());
    if (!detail_mesh || !rcBuildPolyMeshDetail(&context, *poly_mesh, *compact,
            config.detailSampleDist, config.detailSampleMaxError, *detail_mesh)) {
        throw std::runtime_error("Could not build navigation height detail.");
    }

    for (int polygon = 0; polygon < poly_mesh->npolys; ++polygon) {
        if (poly_mesh->areas[polygon] == RC_WALKABLE_AREA) poly_mesh->areas[polygon] = 0U;
        poly_mesh->flags[polygon] = kWalkFlag;
    }

    dtNavMeshCreateParams params{};
    params.verts = poly_mesh->verts;
    params.vertCount = poly_mesh->nverts;
    params.polys = poly_mesh->polys;
    params.polyAreas = poly_mesh->areas;
    params.polyFlags = poly_mesh->flags;
    params.polyCount = poly_mesh->npolys;
    params.nvp = poly_mesh->nvp;
    params.detailMeshes = detail_mesh->meshes;
    params.detailVerts = detail_mesh->verts;
    params.detailVertsCount = detail_mesh->nverts;
    params.detailTris = detail_mesh->tris;
    params.detailTriCount = detail_mesh->ntris;
    params.walkableHeight = kAgentHeightMeters;
    params.walkableRadius = kAgentRadiusMeters;
    params.walkableClimb = kAgentMaximumClimbMeters;
    params.tileX = tile_x;
    params.tileY = tile_y;
    params.tileLayer = 0;
    rcVcopy(params.bmin, poly_mesh->bmin);
    rcVcopy(params.bmax, poly_mesh->bmax);
    params.cs = config.cs;
    params.ch = config.ch;
    params.buildBvTree = true;
    if (!dtCreateNavMeshData(&params, &nav_data, &nav_data_size)) {
        throw std::runtime_error("Could not create a Detour navigation tile.");
    }
    return true;
}

NavMeshPtr BuildNavigation(const Geometry& geometry, std::size_t& built_tile_count) {
    rcChunkyTriMesh chunky_mesh{};
    if (!rcCreateChunkyTriMesh(geometry.vertices.data(), geometry.triangles.data(),
            static_cast<int>(geometry.triangles.size() / 3U), 256, &chunky_mesh)) {
        throw std::runtime_error("Could not build the navigation triangle spatial index.");
    }
    int grid_width = 0;
    int grid_height = 0;
    rcCalcGridSize(geometry.bounds_min.data(), geometry.bounds_max.data(),
        kCellSizeMeters, &grid_width, &grid_height);
    const int tile_width = (grid_width + kTileSizeCells - 1) / kTileSizeCells;
    const int tile_height = (grid_height + kTileSizeCells - 1) / kTileSizeCells;
    const unsigned int requested_tiles = static_cast<unsigned int>(tile_width * tile_height);
    const unsigned int tile_bits = std::min(IntegerLog2(NextPowerOfTwo(requested_tiles)), 14U);
    const unsigned int polygon_bits = 22U - tile_bits;

    dtNavMeshParams params{};
    rcVcopy(params.orig, geometry.bounds_min.data());
    params.tileWidth = static_cast<float>(kTileSizeCells) * kCellSizeMeters;
    params.tileHeight = static_cast<float>(kTileSizeCells) * kCellSizeMeters;
    params.maxTiles = static_cast<int>(1U << tile_bits);
    params.maxPolys = static_cast<int>(1U << polygon_bits);

    NavMeshPtr nav_mesh(dtAllocNavMesh());
    if (!nav_mesh || dtStatusFailed(nav_mesh->init(&params))) {
        throw std::runtime_error("Could not initialize the Detour navigation mesh.");
    }

    rcContext context(true);
    std::vector<int> chunk_ids(static_cast<std::size_t>(chunky_mesh.nnodes));
    built_tile_count = 0U;
    const float tile_world_size = static_cast<float>(kTileSizeCells) * kCellSizeMeters;
    for (int tile_y = 0; tile_y < tile_height; ++tile_y) {
        if ((tile_y % 4) == 0) {
            std::cout << "Building navigation tile row " << (tile_y + 1) << "/"
                      << tile_height << "\n";
        }
        for (int tile_x = 0; tile_x < tile_width; ++tile_x) {
            std::array<float, 3> tile_minimum{
                geometry.bounds_min[0] + static_cast<float>(tile_x) * tile_world_size,
                geometry.bounds_min[1],
                geometry.bounds_min[2] + static_cast<float>(tile_y) * tile_world_size};
            std::array<float, 3> tile_maximum{
                geometry.bounds_min[0] + static_cast<float>(tile_x + 1) * tile_world_size,
                geometry.bounds_max[1],
                geometry.bounds_min[2] + static_cast<float>(tile_y + 1) * tile_world_size};
            unsigned char* nav_data = nullptr;
            int nav_data_size = 0;
            BuildTile(context, geometry, chunky_mesh, chunk_ids, tile_x, tile_y,
                tile_minimum.data(), tile_maximum.data(), nav_data, nav_data_size);
            if (nav_data == nullptr || nav_data_size == 0) continue;
            const dtStatus status = nav_mesh->addTile(nav_data, nav_data_size,
                DT_TILE_FREE_DATA, 0, nullptr);
            if (dtStatusFailed(status)) {
                dtFree(nav_data);
                throw std::runtime_error("Could not add a generated navigation tile.");
            }
            ++built_tile_count;
        }
    }
    return nav_mesh;
}

std::array<float, 3> DetourToSim(const float* point) {
    return {point[0], point[2], point[1]};
}

std::array<float, 3> PolygonCenter(const dtMeshTile& tile, const dtPoly& polygon) {
    std::array<float, 3> center{};
    for (unsigned int vertex = 0; vertex < polygon.vertCount; ++vertex) {
        const float* value = &tile.verts[polygon.verts[vertex] * 3U];
        center[0] += value[0];
        center[1] += value[1];
        center[2] += value[2];
    }
    const float inverse_count = 1.0f / static_cast<float>(polygon.vertCount);
    center[0] *= inverse_count;
    center[1] *= inverse_count;
    center[2] *= inverse_count;
    return center;
}

struct HouseNavPoint {
    const HouseInfo* house = nullptr;
    dtPolyRef polygon = 0;
    std::array<float, 3> detour_position{};
};

struct EntrancePortal {
    const HouseInfo* house = nullptr;
    dtPolyRef first_polygon = 0;
    dtPolyRef second_polygon = 0;
    std::array<float, 3> first{};   // Detour X/Y-up/Z.
    std::array<float, 3> second{};
};

struct NavigationTopology {
    std::vector<dtPolyRef> polygons{};
    std::unordered_map<dtPolyRef, std::size_t> indices{};
    std::vector<std::size_t> parents{};

    std::size_t Find(std::size_t index) {
        while (parents[index] != index) {
            parents[index] = parents[parents[index]];
            index = parents[index];
        }
        return index;
    }

    void Unite(std::size_t first, std::size_t second) {
        first = Find(first);
        second = Find(second);
        if (first != second) parents[second] = first;
    }

    std::size_t Component(const dtPolyRef polygon) {
        const auto found = indices.find(polygon);
        return found == indices.end() ? std::numeric_limits<std::size_t>::max()
                                      : Find(found->second);
    }
};

NavigationTopology BuildTopology(const dtNavMesh& nav_mesh) {
    NavigationTopology topology{};
    for (int tile_index = 0; tile_index < nav_mesh.getMaxTiles(); ++tile_index) {
        const dtMeshTile* tile = nav_mesh.getTile(tile_index);
        if (tile == nullptr || tile->header == nullptr) continue;
        const dtPolyRef base = nav_mesh.getPolyRefBase(tile);
        for (int polygon_index = 0; polygon_index < tile->header->polyCount; ++polygon_index) {
            const dtPoly& polygon = tile->polys[polygon_index];
            if (polygon.getType() != DT_POLYTYPE_GROUND ||
                (polygon.flags & kWalkFlag) == 0U) continue;
            const dtPolyRef reference = base | static_cast<dtPolyRef>(polygon_index);
            topology.indices.emplace(reference, topology.polygons.size());
            topology.polygons.push_back(reference);
        }
    }
    topology.parents.resize(topology.polygons.size());
    for (std::size_t index = 0U; index < topology.parents.size(); ++index) {
        topology.parents[index] = index;
    }
    for (int tile_index = 0; tile_index < nav_mesh.getMaxTiles(); ++tile_index) {
        const dtMeshTile* tile = nav_mesh.getTile(tile_index);
        if (tile == nullptr || tile->header == nullptr) continue;
        const dtPolyRef base = nav_mesh.getPolyRefBase(tile);
        for (int polygon_index = 0; polygon_index < tile->header->polyCount; ++polygon_index) {
            const dtPoly& polygon = tile->polys[polygon_index];
            const dtPolyRef reference = base | static_cast<dtPolyRef>(polygon_index);
            const auto current = topology.indices.find(reference);
            if (current == topology.indices.end()) continue;
            for (unsigned int link_index = polygon.firstLink; link_index != DT_NULL_LINK;
                 link_index = tile->links[link_index].next) {
                const auto neighbor = topology.indices.find(tile->links[link_index].ref);
                if (neighbor != topology.indices.end()) {
                    topology.Unite(current->second, neighbor->second);
                }
            }
        }
    }
    return topology;
}

struct BoundaryEdge {
    dtPolyRef polygon = 0;
    std::size_t component = 0U;
    std::array<float, 3> first{};
    std::array<float, 3> second{};
};

struct ClosestSegmentsResult {
    float first_fraction = 0.0f;
    float second_fraction = 0.0f;
    float distance_squared = 0.0f;
};

ClosestSegmentsResult ClosestSegmentsGroundPlane(const BoundaryEdge& first,
    const BoundaryEdge& second) {
    const float ux = first.second[0] - first.first[0];
    const float uz = first.second[2] - first.first[2];
    const float vx = second.second[0] - second.first[0];
    const float vz = second.second[2] - second.first[2];
    const float wx = first.first[0] - second.first[0];
    const float wz = first.first[2] - second.first[2];
    const float a = ux * ux + uz * uz;
    const float b = ux * vx + uz * vz;
    const float c = vx * vx + vz * vz;
    const float d = ux * wx + uz * wz;
    const float e = vx * wx + vz * wz;
    const float denominator = a * c - b * b;
    float s = denominator > 1.0e-8f ? std::clamp((b * e - c * d) / denominator, 0.0f, 1.0f)
                                     : 0.0f;
    float t = c > 1.0e-8f ? std::clamp((b * s + e) / c, 0.0f, 1.0f) : 0.0f;
    if (a > 1.0e-8f) s = std::clamp((b * t - d) / a, 0.0f, 1.0f);
    if (c > 1.0e-8f) t = std::clamp((b * s + e) / c, 0.0f, 1.0f);
    const float dx = first.first[0] + ux * s - (second.first[0] + vx * t);
    const float dz = first.first[2] + uz * s - (second.first[2] + vz * t);
    return {s, t, dx * dx + dz * dz};
}

std::array<float, 3> InterpolateEdge(const BoundaryEdge& edge, const float fraction) {
    return {
        edge.first[0] + (edge.second[0] - edge.first[0]) * fraction,
        edge.first[1] + (edge.second[1] - edge.first[1]) * fraction,
        edge.first[2] + (edge.second[2] - edge.first[2]) * fraction};
}

float SegmentTriangleFraction(const std::array<float, 3>& start,
    const std::array<float, 3>& end, const float* first, const float* second,
    const float* third) {
    const std::array<float, 3> direction{
        end[0] - start[0], end[1] - start[1], end[2] - start[2]};
    const std::array<float, 3> edge_one{
        second[0] - first[0], second[1] - first[1], second[2] - first[2]};
    const std::array<float, 3> edge_two{
        third[0] - first[0], third[1] - first[1], third[2] - first[2]};
    const std::array<float, 3> p{
        direction[1] * edge_two[2] - direction[2] * edge_two[1],
        direction[2] * edge_two[0] - direction[0] * edge_two[2],
        direction[0] * edge_two[1] - direction[1] * edge_two[0]};
    const float determinant = edge_one[0] * p[0] + edge_one[1] * p[1] + edge_one[2] * p[2];
    if (std::fabs(determinant) < 1.0e-7f) return std::numeric_limits<float>::max();
    const float inverse = 1.0f / determinant;
    const std::array<float, 3> from_first{
        start[0] - first[0], start[1] - first[1], start[2] - first[2]};
    const float u = (from_first[0] * p[0] + from_first[1] * p[1] + from_first[2] * p[2]) * inverse;
    if (u < 0.0f || u > 1.0f) return std::numeric_limits<float>::max();
    const std::array<float, 3> q{
        from_first[1] * edge_one[2] - from_first[2] * edge_one[1],
        from_first[2] * edge_one[0] - from_first[0] * edge_one[2],
        from_first[0] * edge_one[1] - from_first[1] * edge_one[0]};
    const float v = (direction[0] * q[0] + direction[1] * q[1] + direction[2] * q[2]) * inverse;
    if (v < 0.0f || u + v > 1.0f) return std::numeric_limits<float>::max();
    const float fraction = (edge_two[0] * q[0] + edge_two[1] * q[1] + edge_two[2] * q[2]) * inverse;
    return fraction >= 0.0f && fraction <= 1.0f
        ? fraction : std::numeric_limits<float>::max();
}

bool SegmentHitsTriangle(const std::array<float, 3>& start,
    const std::array<float, 3>& end, const float* first, const float* second,
    const float* third) {
    const float fraction = SegmentTriangleFraction(start, end, first, second, third);
    return fraction > 0.02f && fraction < 0.98f;
}

bool SegmentIsClear(const Geometry& geometry, const rcChunkyTriMesh& chunky_mesh,
    const std::array<float, 3>& start, const std::array<float, 3>& end,
    std::vector<int>& chunk_ids) {
    float ground_start[2]{start[0], start[2]};
    float ground_end[2]{end[0], end[2]};
    const int chunk_count = rcGetChunksOverlappingSegment(&chunky_mesh,
        ground_start, ground_end, chunk_ids.data(), static_cast<int>(chunk_ids.size()));
    for (int chunk = 0; chunk < chunk_count; ++chunk) {
        const rcChunkyTriMeshNode& node = chunky_mesh.nodes[chunk_ids[chunk]];
        for (int triangle = 0; triangle < node.n; ++triangle) {
            const int* indices = &chunky_mesh.tris[(node.i + triangle) * 3];
            if (SegmentHitsTriangle(start, end,
                    &geometry.vertices[static_cast<std::size_t>(indices[0]) * 3U],
                    &geometry.vertices[static_cast<std::size_t>(indices[1]) * 3U],
                    &geometry.vertices[static_cast<std::size_t>(indices[2]) * 3U])) {
                return false;
            }
        }
    }
    return true;
}

float GeometryClearanceAbove(const Geometry& geometry, const rcChunkyTriMesh& chunky_mesh,
    const std::array<float, 3>& position, std::vector<int>& chunk_ids) {
    constexpr float kRayStartLiftMeters = 0.02f;
    constexpr float kPointQueryHalfExtentMeters = 0.02f;
    const std::array<float, 3> start{
        position[0], position[1] + kRayStartLiftMeters, position[2]};
    const std::array<float, 3> end{
        position[0], geometry.bounds_max[1] + 2.0f, position[2]};
    float query_minimum[2]{
        position[0] - kPointQueryHalfExtentMeters,
        position[2] - kPointQueryHalfExtentMeters};
    float query_maximum[2]{
        position[0] + kPointQueryHalfExtentMeters,
        position[2] + kPointQueryHalfExtentMeters};
    const int chunk_count = rcGetChunksOverlappingRect(&chunky_mesh,
        query_minimum, query_maximum, chunk_ids.data(), static_cast<int>(chunk_ids.size()));
    float minimum_clearance = std::numeric_limits<float>::max();
    const float ray_length = end[1] - start[1];
    for (int chunk = 0; chunk < chunk_count; ++chunk) {
        const rcChunkyTriMeshNode& node = chunky_mesh.nodes[chunk_ids[chunk]];
        for (int triangle = 0; triangle < node.n; ++triangle) {
            const int* indices = &chunky_mesh.tris[(node.i + triangle) * 3];
            const float fraction = SegmentTriangleFraction(start, end,
                &geometry.vertices[static_cast<std::size_t>(indices[0]) * 3U],
                &geometry.vertices[static_cast<std::size_t>(indices[1]) * 3U],
                &geometry.vertices[static_cast<std::size_t>(indices[2]) * 3U]);
            if (fraction == std::numeric_limits<float>::max()) continue;
            minimum_clearance = std::min(minimum_clearance,
                kRayStartLiftMeters + fraction * ray_length);
        }
    }
    return minimum_clearance;
}

std::size_t ExcludeHouseRoofs(const Geometry& geometry, dtNavMesh& nav_mesh) {
    rcChunkyTriMesh chunky_mesh{};
    if (!rcCreateChunkyTriMesh(geometry.vertices.data(), geometry.triangles.data(),
            static_cast<int>(geometry.triangles.size() / 3U), 256, &chunky_mesh)) {
        throw std::runtime_error("Could not build the roof-exclusion spatial index.");
    }
    std::vector<int> chunk_ids(static_cast<std::size_t>(chunky_mesh.nnodes));
    constexpr float kMinimumElevatedSurfaceMeters = 1.50f;
    constexpr float kMaximumRoofShellThicknessMeters = 0.50f;
    std::size_t excluded_polygons = 0U;
    for (const HouseInfo& house : geometry.houses) {
        const bool tent = house.label == "tent" || house.label == "Tent";
        const float minimum_excluded_height = tent
            ? house.bounds.minimum[2] + kAgentMaximumClimbMeters
            : house.bounds.minimum[2] + kMinimumElevatedSurfaceMeters;
        const float roof_minimum_height = IsDenseVillageHouse(house.label) &&
            house.upper_floor_area > 1.0
            ? static_cast<float>(house.upper_floor_height_sum / house.upper_floor_area) + 0.75f
            : (tent
                ? minimum_excluded_height
                : house.bounds.minimum[2] + 3.0f);
        std::size_t house_excluded_polygons = 0U;
        for (int tile_index = 0; tile_index < nav_mesh.getMaxTiles(); ++tile_index) {
            const dtMeshTile* tile = static_cast<const dtNavMesh&>(nav_mesh).getTile(tile_index);
            if (tile == nullptr || tile->header == nullptr) continue;
            const dtPolyRef base = nav_mesh.getPolyRefBase(tile);
            for (int polygon_index = 0; polygon_index < tile->header->polyCount;
                 ++polygon_index) {
                const dtPoly& polygon = tile->polys[polygon_index];
                if (polygon.getType() != DT_POLYTYPE_GROUND ||
                    (polygon.flags & kWalkFlag) == 0U) continue;
                const std::array<float, 3> center = PolygonCenter(*tile, polygon);
                const std::array<float, 3> sim = DetourToSim(center.data());
                bool horizontal_overlap = sim[0] >= house.bounds.minimum[0] &&
                    sim[0] <= house.bounds.maximum[0] &&
                    sim[1] >= house.bounds.minimum[1] &&
                    sim[1] <= house.bounds.maximum[1];
                float polygon_maximum_height = sim[2];
                if (tent) {
                    float minimum_x = std::numeric_limits<float>::max();
                    float maximum_x = std::numeric_limits<float>::lowest();
                    float minimum_y = std::numeric_limits<float>::max();
                    float maximum_y = std::numeric_limits<float>::lowest();
                    for (unsigned int vertex_index = 0U;
                         vertex_index < polygon.vertCount; ++vertex_index) {
                        const float* vertex = &tile->verts[polygon.verts[vertex_index] * 3U];
                        minimum_x = std::min(minimum_x, vertex[0]);
                        maximum_x = std::max(maximum_x, vertex[0]);
                        minimum_y = std::min(minimum_y, vertex[2]);
                        maximum_y = std::max(maximum_y, vertex[2]);
                        polygon_maximum_height = std::max(
                            polygon_maximum_height, vertex[1]);
                    }
                    horizontal_overlap = maximum_x >= house.bounds.minimum[0] &&
                        minimum_x <= house.bounds.maximum[0] &&
                        maximum_y >= house.bounds.minimum[1] &&
                        minimum_y <= house.bounds.maximum[1];
                }
                if (!horizontal_overlap || polygon_maximum_height < minimum_excluded_height) continue;
                const auto roof_exposed = [&](const std::array<float, 3>& sample) {
                    if (sample[1] >= roof_minimum_height) return true;
                    const float overhead_clearance = GeometryClearanceAbove(
                        geometry, chunky_mesh, sample, chunk_ids);
                    return overhead_clearance == std::numeric_limits<float>::max() ||
                        overhead_clearance < kMaximumRoofShellThicknessMeters;
                };
                bool exposed = roof_exposed(center);
                for (unsigned int vertex_index = 0U;
                     !exposed && vertex_index < polygon.vertCount; ++vertex_index) {
                    const float* vertex = &tile->verts[polygon.verts[vertex_index] * 3U];
                    exposed = roof_exposed({vertex[0], vertex[1], vertex[2]});
                }
                const dtPolyDetail& detail = tile->detailMeshes[polygon_index];
                for (unsigned int triangle_index = 0U;
                     !exposed && triangle_index < detail.triCount; ++triangle_index) {
                    const unsigned char* triangle =
                        &tile->detailTris[(detail.triBase + triangle_index) * 4U];
                    for (unsigned int corner = 0U; !exposed && corner < 3U; ++corner) {
                        const unsigned int detail_index = triangle[corner];
                        const float* vertex = detail_index < polygon.vertCount
                            ? &tile->verts[polygon.verts[detail_index] * 3U]
                            : &tile->detailVerts[(detail.vertBase + detail_index -
                                polygon.vertCount) * 3U];
                        exposed = roof_exposed({vertex[0], vertex[1], vertex[2]});
                    }
                }
                if (!exposed) continue;
                const dtPolyRef reference = base | static_cast<dtPolyRef>(polygon_index);
                if (dtStatusFailed(nav_mesh.setPolyFlags(reference,
                        static_cast<unsigned short>(polygon.flags & ~kWalkFlag)))) {
                    throw std::runtime_error("Could not exclude a house roof polygon.");
                }
                ++house_excluded_polygons;
            }
        }
        excluded_polygons += house_excluded_polygons;
        std::cout << "  exterior exclusion " << house.label
                  << " starts_z=" << roof_minimum_height
                  << " removed_polygons=" << house_excluded_polygons << "\n";
    }
    return excluded_polygons;
}

bool CapsuleWidthPassageIsClear(const Geometry& geometry,
    const rcChunkyTriMesh& chunky_mesh, const std::array<float, 3>& first,
    const std::array<float, 3>& second, std::vector<int>& chunk_ids) {
    const float dx = second[0] - first[0];
    const float dz = second[2] - first[2];
    const float length = std::sqrt(dx * dx + dz * dz);
    if (length < 1.0e-5f) return false;
    const float perpendicular_x = -dz / length;
    const float perpendicular_z = dx / length;
    const float ray_height = std::min(first[1], second[1]) + 0.75f;
    constexpr std::array<float, 3> offsets{-kAgentRadiusMeters, 0.0f, kAgentRadiusMeters};
    for (const float offset : offsets) {
        const std::array<float, 3> ray_start{
            first[0] + perpendicular_x * offset, ray_height,
            first[2] + perpendicular_z * offset};
        const std::array<float, 3> ray_end{
            second[0] + perpendicular_x * offset, ray_height,
            second[2] + perpendicular_z * offset};
        if (!SegmentIsClear(geometry, chunky_mesh, ray_start, ray_end, chunk_ids)) return false;
    }
    return true;
}

std::vector<EntrancePortal> FindRaisedEntrancePortals(const Geometry& geometry,
    const dtNavMesh& nav_mesh, NavigationTopology& topology) {
    std::unordered_map<std::size_t, std::size_t> component_sizes;
    for (const dtPolyRef polygon : topology.polygons) ++component_sizes[topology.Component(polygon)];
    const auto exterior = std::max_element(component_sizes.begin(), component_sizes.end(),
        [](const auto& first, const auto& second) { return first.second < second.second; });
    if (exterior == component_sizes.end()) return {};
    const std::size_t exterior_component = exterior->first;

    std::vector<BoundaryEdge> all_edges;
    for (int tile_index = 0; tile_index < nav_mesh.getMaxTiles(); ++tile_index) {
        const dtMeshTile* tile = nav_mesh.getTile(tile_index);
        if (tile == nullptr || tile->header == nullptr) continue;
        const dtPolyRef base = nav_mesh.getPolyRefBase(tile);
        for (int polygon_index = 0; polygon_index < tile->header->polyCount; ++polygon_index) {
            const dtPoly& polygon = tile->polys[polygon_index];
            if (polygon.getType() != DT_POLYTYPE_GROUND ||
                (polygon.flags & kWalkFlag) == 0U) continue;
            const dtPolyRef reference = base | static_cast<dtPolyRef>(polygon_index);
            const std::size_t component = topology.Component(reference);
            for (unsigned int edge = 0U; edge < polygon.vertCount; ++edge) {
                if (polygon.neis[edge] != 0U) continue;
                const float* first = &tile->verts[polygon.verts[edge] * 3U];
                const float* second = &tile->verts[polygon.verts[(edge + 1U) % polygon.vertCount] * 3U];
                all_edges.push_back({reference, component,
                    {first[0], first[1], first[2]},
                    {second[0], second[1], second[2]}});
            }
        }
    }

    rcChunkyTriMesh chunky_mesh{};
    if (!rcCreateChunkyTriMesh(geometry.vertices.data(), geometry.triangles.data(),
            static_cast<int>(geometry.triangles.size() / 3U), 256, &chunky_mesh)) {
        throw std::runtime_error("Could not build the entrance-clearance spatial index.");
    }
    std::vector<int> chunk_ids(static_cast<std::size_t>(chunky_mesh.nnodes));
    std::vector<EntrancePortal> portals;
    for (const HouseInfo& house : geometry.houses) {
        if (!IsDenseVillageHouse(house.label)) continue;
        std::vector<const BoundaryEdge*> nearby_edges;
        const float minimum_x = house.bounds.minimum[0] - 2.5f;
        const float maximum_x = house.bounds.maximum[0] + 2.5f;
        const float minimum_z = house.bounds.minimum[1] - 2.5f;
        const float maximum_z = house.bounds.maximum[1] + 2.5f;
        const float maximum_height = house.bounds.minimum[2] + 1.75f;
        for (const BoundaryEdge& edge : all_edges) {
            if (std::min(edge.first[0], edge.second[0]) > maximum_x ||
                std::max(edge.first[0], edge.second[0]) < minimum_x ||
                std::min(edge.first[2], edge.second[2]) > maximum_z ||
                std::max(edge.first[2], edge.second[2]) < minimum_z ||
                std::min(edge.first[1], edge.second[1]) > maximum_height) continue;
            nearby_edges.push_back(&edge);
        }

        struct Candidate {
            EntrancePortal portal{};
            float distance_squared = 0.0f;
            std::array<float, 2> midpoint{};
        };
        std::vector<Candidate> candidates;
        for (std::size_t first_index = 0U; first_index < nearby_edges.size(); ++first_index) {
            for (std::size_t second_index = first_index + 1U;
                 second_index < nearby_edges.size(); ++second_index) {
                const BoundaryEdge& first = *nearby_edges[first_index];
                const BoundaryEdge& second = *nearby_edges[second_index];
                const bool first_is_exterior = first.component == exterior_component;
                const bool second_is_exterior = second.component == exterior_component;
                if (first_is_exterior == second_is_exterior) continue;
                const ClosestSegmentsResult closest =
                    ClosestSegmentsGroundPlane(first, second);
                if (closest.distance_squared < 0.01f || closest.distance_squared > 4.0f) continue;
                const std::array<float, 3> first_point =
                    InterpolateEdge(first, closest.first_fraction);
                const std::array<float, 3> second_point =
                    InterpolateEdge(second, closest.second_fraction);
                if (std::fabs(first_point[1] - second_point[1]) > 1.0f ||
                    !CapsuleWidthPassageIsClear(geometry, chunky_mesh,
                        first_point, second_point, chunk_ids)) continue;
                candidates.push_back({{&house, first.polygon, second.polygon,
                        first_point, second_point}, closest.distance_squared,
                    {0.5f * (first_point[0] + second_point[0]),
                     0.5f * (first_point[2] + second_point[2])}});
            }
        }
        std::sort(candidates.begin(), candidates.end(),
            [](const Candidate& first, const Candidate& second) {
                return first.distance_squared < second.distance_squared;
            });
        std::vector<std::array<float, 2>> accepted_midpoints;
        for (const Candidate& candidate : candidates) {
            const bool duplicate = std::any_of(accepted_midpoints.begin(),
                accepted_midpoints.end(), [&candidate](const auto& midpoint) {
                    const float dx = midpoint[0] - candidate.midpoint[0];
                    const float dz = midpoint[1] - candidate.midpoint[1];
                    return dx * dx + dz * dz < 1.0f;
                });
            if (duplicate) continue;
            portals.push_back(candidate.portal);
            accepted_midpoints.push_back(candidate.midpoint);
            if (accepted_midpoints.size() >= 8U) break;
        }
        std::cout << "  raised entrances " << house.label << " = "
                  << accepted_midpoints.size() << "\n";
    }
    return portals;
}

std::vector<HouseNavPoint> FindDenseVillageUpperFloors(const Geometry& geometry,
    const dtNavMesh& nav_mesh) {
    std::vector<HouseNavPoint> result;
    for (const HouseInfo& house : geometry.houses) {
        if (!IsDenseVillageHouse(house.label) || house.upper_floor_area <= 1.0) continue;
        const float expected_height = static_cast<float>(
            house.upper_floor_height_sum / house.upper_floor_area);
        const float center_x = 0.5f * (house.bounds.minimum[0] + house.bounds.maximum[0]);
        const float center_y = 0.5f * (house.bounds.minimum[1] + house.bounds.maximum[1]);
        std::size_t house_point_count = 0U;
        std::array<float, 3> representative_position{};
        float representative_distance_squared = std::numeric_limits<float>::max();

        for (int tile_index = 0; tile_index < nav_mesh.getMaxTiles(); ++tile_index) {
            const dtMeshTile* tile = nav_mesh.getTile(tile_index);
            if (tile == nullptr || tile->header == nullptr) continue;
            for (int polygon_index = 0; polygon_index < tile->header->polyCount; ++polygon_index) {
                const dtPoly& polygon = tile->polys[polygon_index];
                if (polygon.getType() != DT_POLYTYPE_GROUND ||
                    (polygon.flags & kWalkFlag) == 0U) continue;
                const std::array<float, 3> center = PolygonCenter(*tile, polygon);
                const std::array<float, 3> sim = DetourToSim(center.data());
                if (sim[0] < house.bounds.minimum[0] || sim[0] > house.bounds.maximum[0] ||
                    sim[1] < house.bounds.minimum[1] || sim[1] > house.bounds.maximum[1] ||
                    std::fabs(sim[2] - expected_height) > 0.55f) continue;
                const float delta_x = sim[0] - center_x;
                const float delta_y = sim[1] - center_y;
                const float distance_squared = delta_x * delta_x + delta_y * delta_y;
                result.push_back(HouseNavPoint{
                    &house,
                    nav_mesh.getPolyRefBase(tile) | static_cast<dtPolyRef>(polygon_index),
                    center});
                ++house_point_count;
                if (distance_squared < representative_distance_squared) {
                    representative_distance_squared = distance_squared;
                    representative_position = center;
                }
            }
        }
        if (house_point_count > 0U) {
            const auto sim = DetourToSim(representative_position.data());
            std::cout << "  upper floor " << house.label << " expected_z="
                      << expected_height << " nav=[" << sim[0] << ", " << sim[1]
                      << ", " << sim[2] << "] candidates=" << house_point_count << "\n";
        } else {
            std::cout << "  no upper-floor navigation polygon for " << house.label
                      << " expected_z=" << expected_height << "\n";
        }
    }
    return result;
}

void DescribeUpperFloorComponents(const std::vector<HouseNavPoint>& points,
    NavigationTopology topology) {
    struct Summary {
        const HouseInfo* house = nullptr;
        std::size_t component = 0U;
        std::size_t polygon_count = 0U;
        std::array<float, 3> minimum{
            std::numeric_limits<float>::max(), std::numeric_limits<float>::max(),
            std::numeric_limits<float>::max()};
        std::array<float, 3> maximum{
            std::numeric_limits<float>::lowest(), std::numeric_limits<float>::lowest(),
            std::numeric_limits<float>::lowest()};
    };
    std::vector<Summary> summaries;
    for (const HouseNavPoint& point : points) {
        const std::size_t component = topology.Component(point.polygon);
        auto found = std::find_if(summaries.begin(), summaries.end(),
            [&point, component](const Summary& summary) {
                return summary.house == point.house && summary.component == component;
            });
        if (found == summaries.end()) {
            summaries.push_back({});
            found = std::prev(summaries.end());
            found->house = point.house;
            found->component = component;
        }
        ++found->polygon_count;
        const auto sim = DetourToSim(point.detour_position.data());
        for (std::size_t axis = 0U; axis < 3U; ++axis) {
            found->minimum[axis] = std::min(found->minimum[axis], sim[axis]);
            found->maximum[axis] = std::max(found->maximum[axis], sim[axis]);
        }
    }
    for (const Summary& summary : summaries) {
        std::cout << "  upper component " << summary.house->label
                  << " id=" << summary.component
                  << " candidates=" << summary.polygon_count
                  << " x=[" << summary.minimum[0] << "," << summary.maximum[0]
                  << "] y=[" << summary.minimum[1] << "," << summary.maximum[1]
                  << "] z=[" << summary.minimum[2] << "," << summary.maximum[2]
                  << "]\n";
    }
}

bool FindConnectedTestPair(
    std::pair<HouseNavPoint, HouseNavPoint>& result,
    const std::vector<HouseNavPoint>& points, dtNavMeshQuery& query,
    NavigationTopology topology, const std::vector<EntrancePortal>& portals) {
    dtQueryFilter filter{};
    filter.setIncludeFlags(kWalkFlag);
    std::array<dtPolyRef, 2048> path{};
    for (std::size_t first = 0; first < points.size(); ++first) {
        for (std::size_t second = first + 1U; second < points.size(); ++second) {
            if (points[first].house == points[second].house) continue;
            int path_count = 0;
            const dtStatus status = query.findPath(points[first].polygon, points[second].polygon,
                points[first].detour_position.data(), points[second].detour_position.data(),
                &filter, path.data(), &path_count, static_cast<int>(path.size()));
            if (dtStatusSucceed(status) && path_count > 1 &&
                path[static_cast<std::size_t>(path_count - 1)] == points[second].polygon) {
                std::cout << "Connected upper-floor test path: "
                          << points[first].house->label << " -> "
                          << points[second].house->label << " (" << path_count
                          << " polygons)\n";
                result = {points[first], points[second]};
                return true;
            }
        }
    }
    for (const EntrancePortal& portal : portals) {
        const auto first = topology.indices.find(portal.first_polygon);
        const auto second = topology.indices.find(portal.second_polygon);
        if (first != topology.indices.end() && second != topology.indices.end()) {
            topology.Unite(first->second, second->second);
        }
    }
    for (std::size_t first = 0; first < points.size(); ++first) {
        for (std::size_t second = first + 1U; second < points.size(); ++second) {
            if (points[first].house == points[second].house) continue;
            const std::size_t first_component = topology.Component(points[first].polygon);
            const std::size_t second_component = topology.Component(points[second].polygon);
            if (first_component == std::numeric_limits<std::size_t>::max() ||
                first_component != second_component) continue;
            std::cout << "Connected upper-floor test through raised entrances: "
                      << points[first].house->label << " -> "
                      << points[second].house->label << "\n";
            result = {points[first], points[second]};
            return true;
        }
    }
    return false;
}

void DiagnoseUpperFloorConnections(const std::vector<HouseNavPoint>& points,
    dtNavMeshQuery& query) {
    dtQueryFilter filter{};
    filter.setIncludeFlags(kWalkFlag);
    const float search_extents[3]{12.0f, 0.45f, 12.0f};
    std::array<dtPolyRef, 2048> path{};
    std::unordered_set<const HouseInfo*> diagnosed_houses;
    for (const HouseNavPoint& point : points) {
        if (!diagnosed_houses.insert(point.house).second) continue;
        // The house floors and door openings sit above the surrounding
        // landscape/foundation band. Probe at the actual entrance height.
        const float ground_search[3]{point.detour_position[0], 0.75f,
            point.detour_position[2]};
        dtPolyRef ground_polygon = 0;
        float ground_position[3]{};
        const dtStatus nearest_status = query.findNearestPoly(ground_search, search_extents,
            &filter, &ground_polygon, ground_position);
        int path_count = 0;
        dtStatus path_status = DT_FAILURE;
        if (dtStatusSucceed(nearest_status) && ground_polygon != 0) {
            path_status = query.findPath(point.polygon, ground_polygon,
                point.detour_position.data(), ground_position, &filter,
                path.data(), &path_count, static_cast<int>(path.size()));
        }
        const bool reached = path_count > 0 &&
            path[static_cast<std::size_t>(path_count - 1)] == ground_polygon;
        const auto sim_ground = DetourToSim(ground_position);
        std::cout << "  upper-to-ground " << point.house->label << " ground=["
                  << sim_ground[0] << ", " << sim_ground[1] << ", " << sim_ground[2]
                  << "] polygons=" << path_count << " reached=" << reached
                  << " status=0x" << std::hex << path_status << std::dec << "\n";

        const float center_x = 0.5f *
            (point.house->bounds.minimum[0] + point.house->bounds.maximum[0]);
        const float center_y = 0.5f *
            (point.house->bounds.minimum[1] + point.house->bounds.maximum[1]);
        const std::array<std::array<float, 2>, 4> outside_points{{
            {point.house->bounds.minimum[0] - 1.5f, center_y},
            {point.house->bounds.maximum[0] + 1.5f, center_y},
            {center_x, point.house->bounds.minimum[1] - 1.5f},
            {center_x, point.house->bounds.maximum[1] + 1.5f}}};
        bool has_exit = false;
        for (const auto& outside : outside_points) {
            const float outside_search[3]{outside[0], 0.75f, outside[1]};
            const float outside_extents[3]{0.75f, 0.85f, 0.75f};
            dtPolyRef outside_polygon = 0;
            float outside_position[3]{};
            if (dtStatusFailed(query.findNearestPoly(outside_search, outside_extents,
                    &filter, &outside_polygon, outside_position)) || outside_polygon == 0) continue;
            path_count = 0;
            path_status = query.findPath(point.polygon, outside_polygon,
                point.detour_position.data(), outside_position, &filter,
                path.data(), &path_count, static_cast<int>(path.size()));
            const bool outside_reached = path_count > 0 &&
                path[static_cast<std::size_t>(path_count - 1)] == outside_polygon;
            if (outside_reached) {
                const auto sim_outside = DetourToSim(outside_position);
                std::cout << "    reachable exterior=[" << sim_outside[0] << ", "
                          << sim_outside[1] << ", " << sim_outside[2] << "] polygons="
                          << path_count << "\n";
                has_exit = true;
                break;
            }
        }
        if (!has_exit) std::cout << "    no reachable exterior polygon\n";
    }
}

void CopyLabel(char (&destination)[32], const std::string& source) {
    const std::size_t length = std::min(source.size(), sizeof(destination) - 1U);
    std::memcpy(destination, source.data(), length);
    destination[length] = '\0';
}

void SaveNavigation(const std::filesystem::path& path, const dtNavMesh& nav_mesh,
    const std::vector<EntrancePortal>& portals,
    const HouseNavPoint* test_start, const HouseNavPoint* test_goal) {
    prophecy::navigation::FileHeader header{};
    std::memcpy(&header.nav_params, nav_mesh.getParams(), sizeof(dtNavMeshParams));
    header.agent_radius = kAgentRadiusMeters;
    header.agent_height = kAgentHeightMeters;
    header.agent_maximum_climb = kAgentMaximumClimbMeters;
    header.agent_maximum_slope_degrees = kAgentMaximumSlopeDegrees;
    header.cell_size = kCellSizeMeters;
    header.cell_height = kCellHeightMeters;
    for (int tile_index = 0; tile_index < nav_mesh.getMaxTiles(); ++tile_index) {
        const dtMeshTile* tile = nav_mesh.getTile(tile_index);
        if (tile != nullptr && tile->header != nullptr && tile->dataSize > 0) ++header.tile_count;
    }
    header.portal_count = static_cast<std::uint32_t>(portals.size());
    if (test_start != nullptr && test_goal != nullptr) {
        const std::array<float, 3> start = DetourToSim(test_start->detour_position.data());
        const std::array<float, 3> goal = DetourToSim(test_goal->detour_position.data());
        std::copy(start.begin(), start.end(), header.test_start);
        std::copy(goal.begin(), goal.end(), header.test_goal);
        CopyLabel(header.test_start_house, test_start->house->label);
        CopyLabel(header.test_goal_house, test_goal->house->label);
    }

    std::filesystem::create_directories(path.parent_path());
    std::ofstream output(path, std::ios::binary | std::ios::trunc);
    if (!output) throw std::runtime_error("Could not create the navigation artifact.");
    output.write(reinterpret_cast<const char*>(&header), sizeof(header));
    for (int tile_index = 0; tile_index < nav_mesh.getMaxTiles(); ++tile_index) {
        const dtMeshTile* tile = nav_mesh.getTile(tile_index);
        if (tile == nullptr || tile->header == nullptr || tile->dataSize <= 0) continue;
        prophecy::navigation::TileHeader tile_header{};
        tile_header.tile_reference = nav_mesh.getTileRef(tile);
        tile_header.data_size = static_cast<std::uint32_t>(tile->dataSize);
        output.write(reinterpret_cast<const char*>(&tile_header), sizeof(tile_header));
        output.write(reinterpret_cast<const char*>(tile->data), tile->dataSize);
    }
    for (const EntrancePortal& portal : portals) {
        prophecy::navigation::Portal saved{};
        saved.first_polygon = portal.first_polygon;
        saved.second_polygon = portal.second_polygon;
        const auto first = DetourToSim(portal.first.data());
        const auto second = DetourToSim(portal.second.data());
        std::copy(first.begin(), first.end(), saved.first);
        std::copy(second.begin(), second.end(), saved.second);
        CopyLabel(saved.house, portal.house->label);
        output.write(reinterpret_cast<const char*>(&saved), sizeof(saved));
    }
    if (!output) throw std::runtime_error("Could not finish writing the navigation artifact.");
}

}  // namespace

int main(int argc, char** argv) {
    try {
        if (argc != 3 && argc != 4) {
            std::cerr << "Usage: prophecy_navigation_baker <unreal_collision.json> "
                         "<mybasic.navbin> [replacement_collision.json]\n";
            return 2;
        }
        std::ifstream input(argv[1]);
        if (!input) throw std::runtime_error("Could not open collision snapshot.");
        Json root;
        input >> root;
        if (!root.is_object() || root.value("schema", std::string{}) !=
                "prophecy.unreal-collision.v1") {
            throw std::runtime_error("Unsupported collision snapshot schema.");
        }

        std::unordered_set<std::string> replacement_labels;
        Geometry replacement_geometry{};
        if (argc == 4) {
            std::ifstream replacement_input(argv[3]);
            if (!replacement_input) {
                throw std::runtime_error("Could not open replacement collision snapshot.");
            }
            Json replacement_root;
            replacement_input >> replacement_root;
            if (!replacement_root.is_object() || replacement_root.value("schema", std::string{}) !=
                    "prophecy.unreal-collision.v1") {
                throw std::runtime_error("Unsupported replacement collision snapshot schema.");
            }
            for (const Json& object : replacement_root.at("objects")) {
                if (object.is_object()) {
                    replacement_labels.insert(object.value("label", std::string{}));
                }
            }
            replacement_geometry = ReadGeometry(replacement_root);
            replacement_root = Json{};
            std::cout << "Replacing cached navigation geometry for "
                      << replacement_labels.size() << " actor(s)\n";
        }

        Geometry geometry = ReadGeometry(root, replacement_labels);
        root = Json{};
        if (!replacement_geometry.triangles.empty()) {
            AppendGeometry(geometry, std::move(replacement_geometry));
        }
        std::cout << "Navigation input: " << geometry.vertices.size() / 3U << " vertices, "
                  << geometry.triangles.size() / 3U << " triangles, "
                  << geometry.houses.size() << " houses\n";
        std::size_t tile_count = 0U;
        NavMeshPtr nav_mesh = BuildNavigation(geometry, tile_count);
        std::cout << "Built " << tile_count << " non-empty navigation tiles\n";
        const std::size_t excluded_roof_polygons = ExcludeHouseRoofs(geometry, *nav_mesh);
        std::cout << "Excluded " << excluded_roof_polygons
                  << " house-roof/tent-exterior navigation polygons\n";

        NavQueryPtr query(dtAllocNavMeshQuery());
        if (!query || dtStatusFailed(query->init(nav_mesh.get(), 8192))) {
            throw std::runtime_error("Could not initialize the navigation validation query.");
        }
        NavigationTopology topology = BuildTopology(*nav_mesh);
        const std::vector<EntrancePortal> entrance_portals =
            FindRaisedEntrancePortals(geometry, *nav_mesh, topology);
        std::cout << "Detected " << entrance_portals.size()
                  << " capsule-clear raised entrance portal(s)\n";
        const std::vector<HouseNavPoint> upper_floors =
            FindDenseVillageUpperFloors(geometry, *nav_mesh);
        std::cout << "Dense-village houses with upper-floor navigation: "
                  << upper_floors.size() << "\n";
        DescribeUpperFloorComponents(upper_floors, topology);
        DiagnoseUpperFloorConnections(upper_floors, *query);
        std::pair<HouseNavPoint, HouseNavPoint> test_pair{};
        const bool has_test_pair = FindConnectedTestPair(test_pair, upper_floors,
            *query, topology, entrance_portals);
        SaveNavigation(argv[2], *nav_mesh, entrance_portals,
            has_test_pair ? &test_pair.first : nullptr,
            has_test_pair ? &test_pair.second : nullptr);

        std::cout << "Saved " << argv[2] << "\n";
        if (has_test_pair) {
            const auto start = DetourToSim(test_pair.first.detour_position.data());
            const auto goal = DetourToSim(test_pair.second.detour_position.data());
            std::cout << "  start " << test_pair.first.house->label << " = ["
                      << start[0] << ", " << start[1] << ", " << start[2] << "]\n"
                      << "  goal  " << test_pair.second.house->label << " = ["
                      << goal[0] << ", " << goal[1] << ", " << goal[2] << "]\n";
        } else {
            std::cout << "  no connected upper-floor test pair yet; debug surface is available\n";
        }
        return 0;
    } catch (const std::exception& exception) {
        std::cerr << exception.what() << '\n';
        return 1;
    }
}
