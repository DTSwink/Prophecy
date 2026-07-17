#pragma once

#include "prophecy/sim/simulation.h"

#include "raylib.h"

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace prophecy::viewer {

enum class LocomotionPoseKind : std::uint8_t {
    Idle,
    Walk,
    Run,
};

struct LocomotionPoseClip {
    LocomotionPoseKind kind = LocomotionPoseKind::Walk;
    float fps = 30.0f;
    float cycle_distance_m = 0.0f;
    std::size_t frame_count = 0;
    std::vector<Vector3> positions{};

    const Vector3& Joint(std::size_t frame, std::size_t joint, std::size_t joint_count) const noexcept;
};

struct ActionPoseClip {
    std::string name{};
    sim::ActionKind kind = sim::ActionKind::None;
    float fps = 30.0f;
    std::size_t frame_count = 0;
    std::vector<Vector3> positions{};

    const Vector3& Joint(std::size_t frame, std::size_t joint, std::size_t joint_count) const noexcept;
};

struct LocomotionPoses {
    std::vector<std::string> joint_names{};
    std::vector<int> parents{};
    LocomotionPoseClip idle{};
    LocomotionPoseClip walk{};
    LocomotionPoseClip run{};
    std::vector<ActionPoseClip> sword_attacks{};
    std::vector<ActionPoseClip> melee_attacks{};

    const LocomotionPoseClip& Clip(sim::LocomotionMode mode) const noexcept;
    const ActionPoseClip* ActionClip(sim::ActionKind kind, std::size_t index) const noexcept;
};

bool LoadLocomotionPoses(const std::string& path, LocomotionPoses& poses, std::string& error);
Vector3 SampleIdlePoseJoint(const LocomotionPoses& poses, float phase,
    std::size_t joint) noexcept;
Vector3 SamplePoseJoint(const LocomotionPoses& poses, sim::LocomotionMode mode,
    float phase, std::size_t joint) noexcept;
Vector3 SampleActionPoseJoint(const LocomotionPoses& poses, sim::ActionKind kind,
    std::size_t animation_index, float progress, std::size_t joint) noexcept;
const char* ActionClipName(const LocomotionPoses& poses, sim::ActionKind kind,
    std::size_t animation_index) noexcept;

}  // namespace prophecy::viewer
