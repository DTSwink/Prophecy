#include "locomotion_poses.h"

#include <nlohmann/json.hpp>

#include <algorithm>
#include <cmath>
#include <fstream>
#include <utility>

namespace prophecy::viewer {
namespace {

using Json = nlohmann::json;

bool ParseClip(const Json& value, std::size_t joint_count, LocomotionPoseClip& clip,
    std::string& error) {
    if (!value.is_object() || !value.contains("positions") || !value["positions"].is_array()) {
        error = "Locomotion pose clip is missing its positions.";
        return false;
    }
    const std::string mode = value.value("mode", "");
    if (mode == "walk") clip.mode = sim::LocomotionMode::Walk;
    else if (mode == "run") clip.mode = sim::LocomotionMode::Run;
    else {
        error = "Locomotion pose clip has an unknown mode.";
        return false;
    }
    clip.fps = value.value("fps", 30.0f);
    clip.cycle_distance_m = value.value("cycle_distance_m", 0.0f);
    clip.frame_count = value["positions"].size();
    if (clip.frame_count < 2U || clip.fps <= 0.0f || clip.cycle_distance_m <= 0.0f) {
        error = "Locomotion pose clip metadata is invalid.";
        return false;
    }
    clip.positions.reserve(clip.frame_count * joint_count);
    for (const Json& frame : value["positions"]) {
        if (!frame.is_array() || frame.size() != joint_count) {
            error = "Locomotion pose frame has the wrong joint count.";
            return false;
        }
        for (const Json& joint : frame) {
            if (!joint.is_array() || joint.size() != 3U) {
                error = "Locomotion pose contains an invalid joint.";
                return false;
            }
            clip.positions.push_back({joint[0].get<float>(), joint[1].get<float>(), joint[2].get<float>()});
        }
    }
    return true;
}

}  // namespace

const Vector3& LocomotionPoseClip::Joint(std::size_t frame, std::size_t joint,
    std::size_t joint_count) const noexcept {
    return positions[frame * joint_count + joint];
}

const LocomotionPoseClip& LocomotionPoses::Clip(sim::LocomotionMode mode) const noexcept {
    return mode == sim::LocomotionMode::Run ? run : walk;
}

bool LoadLocomotionPoses(const std::string& path, LocomotionPoses& poses, std::string& error) {
    std::ifstream input(path);
    if (!input) {
        error = "Could not open locomotion poses: " + path;
        return false;
    }
    const Json root = Json::parse(input, nullptr, false);
    if (root.is_discarded() || !root.is_object() ||
        root.value("schema", "") != "prophecy.full-body-source-locomotion-poses.v1" ||
        !root.contains("joint_names") || !root.contains("parents") || !root.contains("clips")) {
        error = "Locomotion pose JSON is invalid: " + path;
        return false;
    }

    LocomotionPoses loaded{};
    loaded.joint_names = root["joint_names"].get<std::vector<std::string>>();
    loaded.parents = root["parents"].get<std::vector<int>>();
    if (loaded.joint_names.empty() || loaded.parents.size() != loaded.joint_names.size()) {
        error = "Locomotion pose rig arrays do not match.";
        return false;
    }
    for (std::size_t index = 0; index < loaded.parents.size(); ++index) {
        if (loaded.parents[index] >= static_cast<int>(index)) {
            error = "Locomotion pose parent order is invalid.";
            return false;
        }
    }

    bool found_walk = false;
    bool found_run = false;
    for (const Json& value : root["clips"]) {
        LocomotionPoseClip clip{};
        if (!ParseClip(value, loaded.joint_names.size(), clip, error)) return false;
        if (clip.mode == sim::LocomotionMode::Walk) {
            loaded.walk = std::move(clip);
            found_walk = true;
        } else {
            loaded.run = std::move(clip);
            found_run = true;
        }
    }
    if (!found_walk || !found_run) {
        error = "Locomotion poses must contain both walk and run clips.";
        return false;
    }
    poses = std::move(loaded);
    error.clear();
    return true;
}

Vector3 SamplePoseJoint(const LocomotionPoses& poses, sim::LocomotionMode mode,
    float phase, std::size_t joint) noexcept {
    const LocomotionPoseClip& clip = poses.Clip(mode);
    if (joint >= poses.joint_names.size() || clip.frame_count == 0U) return {};
    phase -= std::floor(phase);
    const float frame = phase * static_cast<float>(clip.frame_count - 1U);
    const std::size_t first = std::min(static_cast<std::size_t>(frame), clip.frame_count - 1U);
    const std::size_t second = std::min(first + 1U, clip.frame_count - 1U);
    const float alpha = frame - static_cast<float>(first);
    const Vector3& a = clip.Joint(first, joint, poses.joint_names.size());
    const Vector3& b = clip.Joint(second, joint, poses.joint_names.size());
    return {
        a.x + (b.x - a.x) * alpha,
        a.y + (b.y - a.y) * alpha,
        a.z + (b.z - a.z) * alpha,
    };
}

}  // namespace prophecy::viewer
