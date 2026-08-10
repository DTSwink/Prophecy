#pragma once

#include "raylib.h"

#include <cstddef>
#include <string>
#include <vector>

namespace prophecy::viewer {

// Viewer-only GPU representation of the cached Detour navigation artifact.
// It is not consulted by sim_core and costs nothing per frame while hidden.
class NavigationDebugSurface {
public:
    NavigationDebugSurface() = default;
    NavigationDebugSurface(const NavigationDebugSurface&) = delete;
    NavigationDebugSurface& operator=(const NavigationDebugSurface&) = delete;

    bool Load(const std::string& path, std::string& error);
    bool Reload(const std::string& path, std::string& error);
    void Draw() const noexcept;
    void Shutdown() noexcept;

    [[nodiscard]] bool IsLoaded() const noexcept { return loaded_; }
    [[nodiscard]] std::size_t TriangleCount() const noexcept { return triangle_count_; }
    [[nodiscard]] std::size_t PortalCount() const noexcept { return portals_.size() / 2U; }
    [[nodiscard]] std::size_t ComponentCount() const noexcept { return component_count_; }
    [[nodiscard]] bool HasTestRoute() const noexcept { return test_route_.size() >= 2U; }
    [[nodiscard]] float TestRouteLength() const noexcept { return test_route_length_; }
    [[nodiscard]] const std::string& TestStartHouse() const noexcept { return test_start_house_; }
    [[nodiscard]] const std::string& TestGoalHouse() const noexcept { return test_goal_house_; }
    bool SampleTestRoute(double time_seconds, Vector3& position, Vector3& velocity) const noexcept;

private:
    std::vector<Mesh> meshes_{};
    Material fill_material_{};
    Material wire_material_{};
    std::vector<Vector3> portals_{};
    std::vector<Vector3> test_route_{};
    std::vector<float> test_route_distances_{};
    std::string test_start_house_{};
    std::string test_goal_house_{};
    float test_route_length_ = 0.0f;
    std::size_t triangle_count_ = 0U;
    std::size_t component_count_ = 0U;
    bool loaded_ = false;
};

}  // namespace prophecy::viewer
