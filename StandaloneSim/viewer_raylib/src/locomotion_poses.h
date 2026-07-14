#pragma once

#include "prophecy/sim/locomotion.h"

#include "raylib.h"

#include <cstddef>
#include <string>
#include <vector>

namespace prophecy::viewer {

struct LocomotionPoseClip {
    sim::LocomotionMode mode = sim::LocomotionMode::Walk;
    float fps = 30.0f;
    float cycle_distance_m = 0.0f;
    std::size_t frame_count = 0;
    std::vector<Vector3> positions{};

    const Vector3& Joint(std::size_t frame, std::size_t joint, std::size_t joint_count) const noexcept;
};

struct LocomotionPoses {
    std::vector<std::string> joint_names{};
    std::vector<int> parents{};
    LocomotionPoseClip walk{};
    LocomotionPoseClip run{};

    const LocomotionPoseClip& Clip(sim::LocomotionMode mode) const noexcept;
};

bool LoadLocomotionPoses(const std::string& path, LocomotionPoses& poses, std::string& error);
Vector3 SamplePoseJoint(const LocomotionPoses& poses, sim::LocomotionMode mode,
    float phase, std::size_t joint) noexcept;

}  // namespace prophecy::viewer
