#pragma once

#include <DetourNavMesh.h>

#include <cstdint>

namespace prophecy::navigation {

constexpr std::uint32_t kMagic =
    static_cast<std::uint32_t>('P') << 24U |
    static_cast<std::uint32_t>('N') << 16U |
    static_cast<std::uint32_t>('A') << 8U |
    static_cast<std::uint32_t>('V');
constexpr std::uint32_t kVersion = 2U;

struct FileHeader {
    std::uint32_t magic = kMagic;
    std::uint32_t version = kVersion;
    std::uint32_t tile_count = 0U;
    std::uint32_t portal_count = 0U;
    dtNavMeshParams nav_params{};
    float agent_radius = 0.30f;
    float agent_height = 1.72f;
    float agent_maximum_climb = 0.45f;
    float agent_maximum_slope_degrees = 44.765083f;
    float cell_size = 0.10f;
    float cell_height = 0.05f;
    float test_start[3]{};  // Sim X/Y/Z coordinates.
    float test_goal[3]{};
    char test_start_house[32]{};
    char test_goal_house[32]{};
};

struct TileHeader {
    dtTileRef tile_reference = 0;
    std::uint32_t data_size = 0U;
};

struct Portal {
    dtPolyRef first_polygon = 0;
    dtPolyRef second_polygon = 0;
    float first[3]{};   // Sim X/Y/Z coordinates.
    float second[3]{};
    char house[32]{};
};

}  // namespace prophecy::navigation
