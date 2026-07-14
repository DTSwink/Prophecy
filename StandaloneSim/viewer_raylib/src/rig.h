#pragma once

#include "raylib.h"

#include <string>
#include <vector>

namespace prophecy::viewer {

struct Rig {
    std::vector<std::string> joint_names{};
    std::vector<int> parents{};
    std::vector<Vector3> reference_pose{};
};

bool LoadRig(const std::string& path, Rig& rig, std::string& error);

}  // namespace prophecy::viewer
