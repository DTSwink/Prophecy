#pragma once
#include "prophecy/sim/locomotion.h"
#include <algorithm>
#include <cmath>

// Above-one window controls accelerate the mover's response, not its speed cap.
// No retained state: the existing window and actual mover share this forecast.
namespace ProphecyRootResponse
{
inline double Advance(double Previous, double Candidate, double Target, double Factor)
{
    if (Factor <= 1.) return Candidate;
    const double Error = Target - Previous, Step = Candidate - Previous;
    // Don't amplify a motor still moving away from its goal, or manufacture a
    // reversal after the native controller has already reached/passed it.
    if (Step * Error <= 0. || std::abs(Step) >= std::abs(Error)) return Candidate;
    return Previous + std::copysign(std::min(std::abs(Error), std::abs(Step) * Factor), Error);
}
inline double Angle(double Previous, double Candidate, double Target, double Factor)
{
    using prophecy::sim::SignedAngleDelta;
    return Previous + Advance(0., SignedAngleDelta(Previous, Candidate),
        SignedAngleDelta(Previous, Target), Factor);
}
inline prophecy::sim::FutureRootWindow Predict(const prophecy::sim::LocomotionState& State,
    const prophecy::sim::LocomotionIntent& Intent, double Dt, bool Momentum,
    const prophecy::sim::RootBalanceSpring* Balance,
    double Acceleration, double Direction, double Orientation, double Deceleration)
{
    using namespace prophecy::sim;
    if (Deceleration < 0.) Deceleration = Acceleration;
    if (Acceleration <= 1. && Direction <= 1. && Orientation <= 1. && Deceleration <= 1.)
        return PredictFutureRoots(State, Intent, Dt, Momentum, Balance);
    FutureRootWindow Future{};
    auto Projected = State;
    auto Input = Intent;
    const double WorldDirection = State.yaw_radians + Intent.speed_direction_radians;
    for (auto& Root : Future)
    {
        const auto Before = Projected;
        LocomotionTarget Goal;
        StepLocomotion(Projected, Input, Dt, &Goal, Momentum, Balance);
        // The balance spring and explicit angular impulses retain their own
        // response/stopping contract; these controls affect ordinary steering.
        if (Dt > 0. && !(Balance && IsRootBalanceActive(Before, Input, *Balance)) &&
            (Acceleration > 1. || Deceleration > 1. || Direction > 1.))
        {
            const double OldSpeed = std::hypot(Before.velocity.x, Before.velocity.z);
            const double Speed = std::hypot(Projected.velocity.x, Projected.velocity.z);
            const double GoalSpeed = std::hypot(Goal.velocity.x, Goal.velocity.z);
            const double Factor = GoalSpeed < OldSpeed ? Deceleration : Acceleration;
            const double NewSpeed = Advance(OldSpeed, Speed, GoalSpeed, Factor);
            double Heading = std::atan2(Projected.velocity.x, Projected.velocity.z);
            if (Direction > 1. && OldSpeed > 1.e-8 && Speed > 1.e-8 && GoalSpeed > 1.e-8)
                Heading = Angle(std::atan2(Before.velocity.x, Before.velocity.z), Heading,
                    std::atan2(Goal.velocity.x, Goal.velocity.z), Direction);
            if (NewSpeed != Speed || Direction > 1.)
            {
                Projected.velocity = {NewSpeed * std::sin(Heading), NewSpeed * std::cos(Heading)};
                Projected.position = {Before.position.x + Projected.velocity.x * Dt,
                    Before.position.z + Projected.velocity.z * Dt};
                Projected.distance_travelled = Before.distance_travelled + NewSpeed * Dt;
            }
        }
        if (Dt > 0. && !Momentum && Orientation > 1.)
            Projected.yaw_radians = Angle(Before.yaw_radians, Projected.yaw_radians,
                Goal.orientation_yaw_radians, Orientation);
        Root = {Projected.position, Projected.yaw_radians};
        Input.speed_direction_radians = SignedAngleDelta(Projected.yaw_radians, WorldDirection);
    }
    return Future;
}
}
