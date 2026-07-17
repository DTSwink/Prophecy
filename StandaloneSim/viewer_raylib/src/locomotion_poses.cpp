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
    if (mode == "idle") clip.kind = LocomotionPoseKind::Idle;
    else if (mode == "walk") clip.kind = LocomotionPoseKind::Walk;
    else if (mode == "run") clip.kind = LocomotionPoseKind::Run;
    else {
        error = "Locomotion pose clip has an unknown mode.";
        return false;
    }
    clip.fps = value.value("fps", 30.0f);
    clip.cycle_distance_m = value.value("cycle_distance_m", 0.0f);
    clip.frame_count = value["positions"].size();
    const bool invalid_distance = clip.kind != LocomotionPoseKind::Idle &&
        clip.cycle_distance_m <= 0.0f;
    if (clip.frame_count < 2U || clip.fps <= 0.0f || invalid_distance) {
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

bool ParseActionClip(const Json& value, std::size_t joint_count, ActionPoseClip& clip,
    std::string& error) {
    if (!value.is_object() || !value.contains("positions") || !value["positions"].is_array()) {
        error = "Action pose clip is missing its positions.";
        return false;
    }
    const std::string category = value.value("category", "");
    if (category == "sword") clip.kind = sim::ActionKind::SwordAttack;
    else if (category == "melee") clip.kind = sim::ActionKind::MeleeAttack;
    else {
        error = "Action pose clip has an unknown category.";
        return false;
    }
    clip.name = value.value("name", "");
    clip.fps = value.value("fps", 30.0f);
    clip.frame_count = value["positions"].size();
    if (clip.name.empty() || clip.frame_count < 2U || clip.fps <= 0.0f) {
        error = "Action pose clip metadata is invalid.";
        return false;
    }
    clip.positions.reserve(clip.frame_count * joint_count);
    for (const Json& frame : value["positions"]) {
        if (!frame.is_array() || frame.size() != joint_count) {
            error = "Action pose frame has the wrong joint count.";
            return false;
        }
        for (const Json& joint : frame) {
            if (!joint.is_array() || joint.size() != 3U) {
                error = "Action pose contains an invalid joint.";
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

const Vector3& ActionPoseClip::Joint(std::size_t frame, std::size_t joint,
    std::size_t joint_count) const noexcept {
    return positions[frame * joint_count + joint];
}

const LocomotionPoseClip& LocomotionPoses::Clip(sim::LocomotionMode mode) const noexcept {
    return mode == sim::LocomotionMode::Run ? run : walk;
}

const ActionPoseClip* LocomotionPoses::ActionClip(sim::ActionKind kind, std::size_t index) const noexcept {
    const std::vector<ActionPoseClip>* clips = nullptr;
    if (kind == sim::ActionKind::SwordAttack) clips = &sword_attacks;
    else if (kind == sim::ActionKind::MeleeAttack) clips = &melee_attacks;
    return clips != nullptr && index < clips->size() ? &(*clips)[index] : nullptr;
}

bool LoadLocomotionPoses(const std::string& path, LocomotionPoses& poses, std::string& error) {
    std::ifstream input(path);
    if (!input) {
        error = "Could not open locomotion poses: " + path;
        return false;
    }
    const Json root = Json::parse(input, nullptr, false);
    if (root.is_discarded() || !root.is_object() ||
        root.value("schema", "") != "prophecy.full-body-source-poses.v2" ||
        !root.contains("joint_names") || !root.contains("parents") || !root.contains("clips") ||
        !root.contains("action_clips")) {
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

    bool found_idle = false;
    bool found_walk = false;
    bool found_run = false;
    for (const Json& value : root["clips"]) {
        LocomotionPoseClip clip{};
        if (!ParseClip(value, loaded.joint_names.size(), clip, error)) return false;
        switch (clip.kind) {
            case LocomotionPoseKind::Idle:
                loaded.idle = std::move(clip);
                found_idle = true;
                break;
            case LocomotionPoseKind::Walk:
                loaded.walk = std::move(clip);
                found_walk = true;
                break;
            case LocomotionPoseKind::Run:
                loaded.run = std::move(clip);
                found_run = true;
                break;
        }
    }
    if (!found_idle || !found_walk || !found_run) {
        error = "Locomotion poses must contain idle, walk, and run clips.";
        return false;
    }
    for (const Json& value : root["action_clips"]) {
        ActionPoseClip clip{};
        if (!ParseActionClip(value, loaded.joint_names.size(), clip, error)) return false;
        if (clip.kind == sim::ActionKind::SwordAttack) loaded.sword_attacks.push_back(std::move(clip));
        else loaded.melee_attacks.push_back(std::move(clip));
    }
    if (loaded.sword_attacks.size() != sim::kSwordAttackClipCount ||
        loaded.melee_attacks.size() != sim::kMeleeAttackClipCount) {
        error = "Action poses must contain seven sword clips and nine melee clips.";
        return false;
    }
    poses = std::move(loaded);
    error.clear();
    return true;
}

namespace {

Vector3 SampleClipJoint(const LocomotionPoses& poses, const LocomotionPoseClip& clip,
    float phase, std::size_t joint) noexcept {
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

}  // namespace

Vector3 SampleIdlePoseJoint(const LocomotionPoses& poses, float phase,
    std::size_t joint) noexcept {
    return SampleClipJoint(poses, poses.idle, phase, joint);
}

Vector3 SamplePoseJoint(const LocomotionPoses& poses, sim::LocomotionMode mode,
    float phase, std::size_t joint) noexcept {
    return SampleClipJoint(poses, poses.Clip(mode), phase, joint);
}

Vector3 SampleActionPoseJoint(const LocomotionPoses& poses, sim::ActionKind kind,
    std::size_t animation_index, float progress, std::size_t joint) noexcept {
    const ActionPoseClip* clip = poses.ActionClip(kind, animation_index);
    if (clip == nullptr || joint >= poses.joint_names.size() || clip->frame_count == 0U) return {};
    progress = std::clamp(progress, 0.0f, 1.0f);
    const float frame = progress * static_cast<float>(clip->frame_count - 1U);
    const std::size_t first = std::min(static_cast<std::size_t>(frame), clip->frame_count - 1U);
    const std::size_t second = std::min(first + 1U, clip->frame_count - 1U);
    const float alpha = frame - static_cast<float>(first);
    const Vector3& a = clip->Joint(first, joint, poses.joint_names.size());
    const Vector3& b = clip->Joint(second, joint, poses.joint_names.size());
    return {
        a.x + (b.x - a.x) * alpha,
        a.y + (b.y - a.y) * alpha,
        a.z + (b.z - a.z) * alpha,
    };
}

const char* ActionClipName(const LocomotionPoses& poses, sim::ActionKind kind,
    std::size_t animation_index) noexcept {
    const ActionPoseClip* clip = poses.ActionClip(kind, animation_index);
    return clip == nullptr ? "" : clip->name.c_str();
}

}  // namespace prophecy::viewer
