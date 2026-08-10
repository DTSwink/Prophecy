#pragma once

#include "raylib.h"

#include <cstddef>
#include <string>
#include <vector>

namespace prophecy::viewer {

// Debug-only rendering of collision exported from Unreal. This data deliberately
// stays outside sim_core: it has no gameplay authority and is uploaded only when
// the persistent snapshot changes.
class EnvironmentCollision {
public:
    EnvironmentCollision() = default;
    EnvironmentCollision(const EnvironmentCollision&) = delete;
    EnvironmentCollision& operator=(const EnvironmentCollision&) = delete;

    bool Load(const std::string& path, std::string& error);
    bool Reload(const std::string& path, std::string& error);
    void Draw() const noexcept;
    void Shutdown() noexcept;

    [[nodiscard]] bool IsLoaded() const noexcept { return loaded_; }
    [[nodiscard]] std::size_t ObjectCount() const noexcept { return object_count_; }
    [[nodiscard]] std::size_t TriangleCount() const noexcept { return triangle_count_; }
    [[nodiscard]] std::size_t WarningCount() const noexcept { return warning_count_; }
    [[nodiscard]] const std::string& MapName() const noexcept { return map_name_; }

private:
    std::vector<Mesh> meshes_{};
    Material material_{};
    std::size_t object_count_ = 0;
    std::size_t triangle_count_ = 0;
    std::size_t warning_count_ = 0;
    std::string map_name_{};
    bool loaded_ = false;
};

}  // namespace prophecy::viewer
