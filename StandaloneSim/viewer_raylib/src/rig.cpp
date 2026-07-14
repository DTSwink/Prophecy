#include "rig.h"

#include <nlohmann/json.hpp>

#include <fstream>
#include <utility>

namespace prophecy::viewer {

bool LoadRig(const std::string& path, Rig& rig, std::string& error) {
    std::ifstream input(path);
    if (!input) {
        error = "Could not open rig: " + path;
        return false;
    }
    const nlohmann::json root = nlohmann::json::parse(input, nullptr, false);
    if (root.is_discarded() || !root.is_object() || !root.contains("joint_names") ||
        !root.contains("parents") || !root.contains("reference_pose")) {
        error = "Rig JSON is invalid: " + path;
        return false;
    }

    Rig loaded{};
    loaded.joint_names = root["joint_names"].get<std::vector<std::string>>();
    loaded.parents = root["parents"].get<std::vector<int>>();
    for (const auto& joint : root["reference_pose"]) {
        if (!joint.is_array() || joint.size() != 3U) {
            error = "Rig reference pose contains an invalid joint.";
            return false;
        }
        loaded.reference_pose.push_back({joint[0].get<float>(), joint[1].get<float>(), joint[2].get<float>()});
    }
    if (loaded.joint_names.empty() || loaded.parents.size() != loaded.joint_names.size() ||
        loaded.reference_pose.size() != loaded.joint_names.size()) {
        error = "Rig arrays do not have matching lengths.";
        return false;
    }
    for (std::size_t index = 0; index < loaded.parents.size(); ++index) {
        if (loaded.parents[index] >= static_cast<int>(index)) {
            error = "Rig parent order is invalid.";
            return false;
        }
    }
    rig = std::move(loaded);
    error.clear();
    return true;
}

}  // namespace prophecy::viewer
