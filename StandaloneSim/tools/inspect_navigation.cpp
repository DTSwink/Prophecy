#include "navigation_artifact.h"

#include <DetourAlloc.h>
#include <DetourNavMesh.h>
#include <DetourNavMeshQuery.h>

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <limits>
#include <memory>
#include <optional>
#include <string>
#include <unordered_map>
#include <vector>

namespace {

struct NavMeshDeleter {
    void operator()(dtNavMesh* mesh) const noexcept { dtFreeNavMesh(mesh); }
};

struct NavQueryDeleter {
    void operator()(dtNavMeshQuery* query) const noexcept { dtFreeNavMeshQuery(query); }
};

using NavMeshPtr = std::unique_ptr<dtNavMesh, NavMeshDeleter>;
using NavQueryPtr = std::unique_ptr<dtNavMeshQuery, NavQueryDeleter>;

struct Component {
    std::size_t id = std::numeric_limits<std::size_t>::max();
    std::size_t polygon_count = 0U;
    float minimum_x = std::numeric_limits<float>::max();
    float maximum_x = std::numeric_limits<float>::lowest();
    float minimum_height = std::numeric_limits<float>::max();
    float maximum_height = std::numeric_limits<float>::lowest();
    float minimum_z = std::numeric_limits<float>::max();
    float maximum_z = std::numeric_limits<float>::lowest();
};

}  // namespace

int main(int argc, char** argv) {
    if (argc < 2) {
        std::cerr << "Usage: prophecy_navigation_inspector <mybasic.navbin> "
                     "[--all-components] "
                     "[--probe-box min-x max-x min-y max-y min-z max-z]\n";
        return 2;
    }
    bool show_all_components = false;
    std::optional<std::array<float, 6>> probe_box;
    for (int argument = 2; argument < argc; ++argument) {
        const std::string option = argv[argument];
        if (option == "--all-components") {
            show_all_components = true;
        } else if (option == "--probe-box" && argument + 6 < argc) {
            std::array<float, 6> values{};
            for (float& value : values) value = std::strtof(argv[++argument], nullptr);
            probe_box = values;
        } else {
            return 2;
        }
    }
    std::ifstream input(argv[1], std::ios::binary);
    prophecy::navigation::FileHeader header{};
    input.read(reinterpret_cast<char*>(&header), sizeof(header));
    if (!input || header.magic != prophecy::navigation::kMagic ||
        header.version != prophecy::navigation::kVersion) {
        std::cerr << "Unsupported navigation artifact.\n";
        return 1;
    }
    NavMeshPtr nav_mesh(dtAllocNavMesh());
    if (!nav_mesh || dtStatusFailed(nav_mesh->init(&header.nav_params))) return 1;
    for (std::uint32_t tile_index = 0U; tile_index < header.tile_count; ++tile_index) {
        prophecy::navigation::TileHeader tile_header{};
        input.read(reinterpret_cast<char*>(&tile_header), sizeof(tile_header));
        auto* data = static_cast<unsigned char*>(dtAlloc(tile_header.data_size, DT_ALLOC_PERM));
        input.read(reinterpret_cast<char*>(data), tile_header.data_size);
        if (!input || dtStatusFailed(nav_mesh->addTile(data,
                static_cast<int>(tile_header.data_size), DT_TILE_FREE_DATA,
                tile_header.tile_reference, nullptr))) {
            dtFree(data);
            return 1;
        }
    }
    std::vector<prophecy::navigation::Portal> portals(header.portal_count);
    input.read(reinterpret_cast<char*>(portals.data()),
        static_cast<std::streamsize>(portals.size() * sizeof(portals.front())));
    if (!input && !portals.empty()) return 1;
    std::cout << "agent radius=" << header.agent_radius
              << " height=" << header.agent_height
              << " climb=" << header.agent_maximum_climb
              << " slope=" << header.agent_maximum_slope_degrees
              << " cell=" << header.cell_size << "x" << header.cell_height << "\n";

    std::vector<dtPolyRef> references;
    std::unordered_map<dtPolyRef, std::size_t> indices;
    const dtNavMesh& mesh = *nav_mesh;

    if (probe_box.has_value()) {
        const auto& bounds = *probe_box;
        std::size_t overlapping_polygons = 0U;
        for (int tile_index = 0; tile_index < mesh.getMaxTiles(); ++tile_index) {
            const dtMeshTile* tile = mesh.getTile(tile_index);
            if (tile == nullptr || tile->header == nullptr) continue;
            for (int polygon_index = 0; polygon_index < tile->header->polyCount;
                 ++polygon_index) {
                const dtPoly& polygon = tile->polys[polygon_index];
                if (polygon.getType() != DT_POLYTYPE_GROUND ||
                    (polygon.flags & 1U) == 0U) continue;
                std::array<float, 3> minimum{
                    std::numeric_limits<float>::max(),
                    std::numeric_limits<float>::max(),
                    std::numeric_limits<float>::max()};
                std::array<float, 3> maximum{
                    std::numeric_limits<float>::lowest(),
                    std::numeric_limits<float>::lowest(),
                    std::numeric_limits<float>::lowest()};
                for (unsigned int vertex_index = 0U; vertex_index < polygon.vertCount;
                     ++vertex_index) {
                    const float* vertex = &tile->verts[polygon.verts[vertex_index] * 3U];
                    minimum[0] = std::min(minimum[0], vertex[0]);
                    maximum[0] = std::max(maximum[0], vertex[0]);
                    minimum[1] = std::min(minimum[1], vertex[2]);
                    maximum[1] = std::max(maximum[1], vertex[2]);
                    minimum[2] = std::min(minimum[2], vertex[1]);
                    maximum[2] = std::max(maximum[2], vertex[1]);
                }
                if (maximum[0] >= bounds[0] && minimum[0] <= bounds[1] &&
                    maximum[1] >= bounds[2] && minimum[1] <= bounds[3] &&
                    maximum[2] >= bounds[4] && minimum[2] <= bounds[5]) {
                    ++overlapping_polygons;
                }
            }
        }
        std::cout << "probe_box walkable_polygons=" << overlapping_polygons << "\n";
    }

    if (header.test_start_house[0] != '\0' && header.test_goal_house[0] != '\0') {
        NavQueryPtr query(dtAllocNavMeshQuery());
        if (!query || dtStatusFailed(query->init(nav_mesh.get(), 8192))) return 1;
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
                &goal_polygon, nearest_goal)) || goal_polygon == 0) return 1;
        std::array<dtPolyRef, 2048> corridor{};
        int corridor_count = 0;
        if (dtStatusFailed(query->findPath(start_polygon, goal_polygon,
                nearest_start, nearest_goal, &filter, corridor.data(), &corridor_count,
                static_cast<int>(corridor.size()))) || corridor_count == 0) return 1;
        std::array<float, 2048 * 3> straight{};
        std::array<unsigned char, 2048> straight_flags{};
        std::array<dtPolyRef, 2048> straight_polygons{};
        int straight_count = 0;
        if (dtStatusFailed(query->findStraightPath(nearest_start, nearest_goal,
                corridor.data(), corridor_count, straight.data(), straight_flags.data(),
                straight_polygons.data(), &straight_count, 2048))) return 1;
        std::cout << "test=" << header.test_start_house << " -> "
                  << header.test_goal_house << " corridor_polygons=" << corridor_count
                  << " straight_points=" << straight_count << "\n";
        for (int point = 0; point < straight_count; ++point) {
            const float* value = &straight[static_cast<std::size_t>(point) * 3U];
            std::cout << "  path=[" << value[0] << "," << value[2] << ","
                      << value[1] << "]\n";
        }
    } else {
        std::cout << "test=none\n";
    }
    for (int tile_index = 0; tile_index < mesh.getMaxTiles(); ++tile_index) {
        const dtMeshTile* tile = mesh.getTile(tile_index);
        if (tile == nullptr || tile->header == nullptr) continue;
        const dtPolyRef base = mesh.getPolyRefBase(tile);
        for (int polygon_index = 0; polygon_index < tile->header->polyCount; ++polygon_index) {
            if (tile->polys[polygon_index].getType() != DT_POLYTYPE_GROUND ||
                (tile->polys[polygon_index].flags & 1U) == 0U) continue;
            const dtPolyRef reference = base | static_cast<dtPolyRef>(polygon_index);
            indices.emplace(reference, references.size());
            references.push_back(reference);
        }
    }
    std::vector<std::size_t> parents(references.size());
    for (std::size_t index = 0U; index < parents.size(); ++index) parents[index] = index;
    const auto find = [&parents](std::size_t index) {
        while (parents[index] != index) {
            parents[index] = parents[parents[index]];
            index = parents[index];
        }
        return index;
    };
    const auto unite = [&parents, &find](std::size_t first, std::size_t second) {
        first = find(first);
        second = find(second);
        if (first != second) parents[second] = first;
    };
    for (int tile_index = 0; tile_index < mesh.getMaxTiles(); ++tile_index) {
        const dtMeshTile* tile = mesh.getTile(tile_index);
        if (tile == nullptr || tile->header == nullptr) continue;
        const dtPolyRef base = mesh.getPolyRefBase(tile);
        for (int polygon_index = 0; polygon_index < tile->header->polyCount; ++polygon_index) {
            const dtPoly& polygon = tile->polys[polygon_index];
            const auto current = indices.find(base | static_cast<dtPolyRef>(polygon_index));
            if (current == indices.end()) continue;
            for (unsigned int link = polygon.firstLink; link != DT_NULL_LINK;
                 link = tile->links[link].next) {
                const auto neighbor = indices.find(tile->links[link].ref);
                if (neighbor != indices.end()) unite(current->second, neighbor->second);
            }
        }
    }

    std::unordered_map<std::size_t, Component> components;
    for (int tile_index = 0; tile_index < mesh.getMaxTiles(); ++tile_index) {
        const dtMeshTile* tile = mesh.getTile(tile_index);
        if (tile == nullptr || tile->header == nullptr) continue;
        const dtPolyRef base = mesh.getPolyRefBase(tile);
        for (int polygon_index = 0; polygon_index < tile->header->polyCount; ++polygon_index) {
            const dtPoly& polygon = tile->polys[polygon_index];
            const auto found = indices.find(base | static_cast<dtPolyRef>(polygon_index));
            if (found == indices.end()) continue;
            float center_x = 0.0f;
            float center_z = 0.0f;
            for (unsigned int vertex = 0U; vertex < polygon.vertCount; ++vertex) {
                const float* value = &tile->verts[polygon.verts[vertex] * 3U];
                center_x += value[0];
                center_z += value[2];
            }
            center_x /= polygon.vertCount;
            center_z /= polygon.vertCount;
            if (center_x < -35.0f || center_x > 30.0f || center_z < -55.0f || center_z > 20.0f) {
                continue;
            }
            const std::size_t component_id = find(found->second);
            Component& component = components[component_id];
            component.id = component_id;
            ++component.polygon_count;
            for (unsigned int vertex = 0U; vertex < polygon.vertCount; ++vertex) {
                const float* value = &tile->verts[polygon.verts[vertex] * 3U];
                component.minimum_x = std::min(component.minimum_x, value[0]);
                component.maximum_x = std::max(component.maximum_x, value[0]);
                component.minimum_height = std::min(component.minimum_height, value[1]);
                component.maximum_height = std::max(component.maximum_height, value[1]);
                component.minimum_z = std::min(component.minimum_z, value[2]);
                component.maximum_z = std::max(component.maximum_z, value[2]);
            }
        }
    }
    std::vector<Component> sorted;
    for (const auto& entry : components) sorted.push_back(entry.second);
    std::sort(sorted.begin(), sorted.end(), [](const Component& first, const Component& second) {
        return first.maximum_height > second.maximum_height;
    });
    std::cout << "portals=" << portals.size() << " components_in_village=" << sorted.size() << "\n";
    for (const prophecy::navigation::Portal& portal : portals) {
        std::cout << "  portal " << portal.house << " first=["
                  << portal.first[0] << "," << portal.first[1] << "," << portal.first[2]
                  << "] second=[" << portal.second[0] << "," << portal.second[1]
                  << "," << portal.second[2] << "]\n";
    }
    for (const Component& component : sorted) {
        if (!show_all_components && component.maximum_height < 1.5f &&
            component.polygon_count < 10U) continue;
        std::cout << "  component=" << component.id
                  << " polys=" << component.polygon_count
                  << " height=[" << component.minimum_height << "," << component.maximum_height
                  << "] x=[" << component.minimum_x << "," << component.maximum_x
                  << "] y=[" << component.minimum_z << "," << component.maximum_z << "]\n";
    }
    return 0;
}
