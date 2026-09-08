#pragma once

#include <array>
#include <cstdint>

namespace prophecy::sim {

inline constexpr std::size_t kFutureRootWindow = 8;

struct Vec2 {
    double x = 0.0;
    double z = 0.0;
};

enum class LocomotionMode : std::uint8_t {
    Walk,
    Run,
    Crawl,
};

enum class LocomotionResponse : std::uint8_t {
    Normal,
    Stop,
    YawOnly,
    Side90,
    Side135,
    Side135Slow,
    Pivot,
    PivotSlow,
    Turn45,
    Turn90,
    Turn135,
    Turn180,
};

struct LocomotionIntent {
    LocomotionMode mode = LocomotionMode::Walk;
    double speed_direction_radians = 0.0;
    double speed_amplitude = 1.0;
    double orientation_yaw_radians = 0.0;
    double speed_scale = 1.0;
    double turn_scale = 1.0;
};

struct LocomotionState {
    Vec2 position{};
    Vec2 velocity{};
    double previous_yaw_radians = 0.0;
    double yaw_radians = 0.0;
    double distance_travelled = 0.0;
    LocomotionResponse response = LocomotionResponse::Normal;
};

struct RootTransform {
    Vec2 position{};
    double yaw_radians = 0.0;
};

// Readback of the goal used by one actual mover step, before acceleration/braking.
struct LocomotionTarget {
    Vec2 velocity{};
    double orientation_yaw_radians = 0.0;
};

using FutureRootWindow = std::array<RootTransform, kFutureRootWindow>;

double SignedAngleDelta(double start, double end, double preferred = 0.0) noexcept;
Vec2 DirectionFromAngle(double angle) noexcept;
double DirectionalSpeedCap(LocomotionMode mode, double root_relative_direction_radians) noexcept;
void StepLocomotion(LocomotionState& state, const LocomotionIntent& intent, double dt) noexcept;
void StepLocomotion(LocomotionState& state, const LocomotionIntent& intent, double dt,
    LocomotionTarget* out_target, bool allow_yaw_momentum = false) noexcept;
FutureRootWindow PredictFutureRoots(const LocomotionState& state,
    const LocomotionIntent& intent, double dt, bool allow_yaw_momentum = false) noexcept;
const char* ToString(LocomotionMode mode) noexcept;
const char* ToString(LocomotionResponse response) noexcept;

}  // namespace prophecy::sim
