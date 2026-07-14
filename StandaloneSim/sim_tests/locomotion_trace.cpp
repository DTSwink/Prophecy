#include "prophecy/sim/locomotion.h"

#include <cmath>
#include <cstdio>

namespace {

namespace sim = ::prophecy::sim;

sim::LocomotionIntent IntentForFrame(int frame) {
    sim::LocomotionIntent intent{};
    if (frame < 60) {
        intent = {sim::LocomotionMode::Walk, 0.0, 0.8, 0.0};
    } else if (frame < 120) {
        intent = {sim::LocomotionMode::Walk, 0.7, 1.0, 1.1};
    } else if (frame < 180) {
        intent = {sim::LocomotionMode::Run, 0.0, 1.0, 0.0};
    } else if (frame < 240) {
        intent = {sim::LocomotionMode::Run, 0.5 * 3.14159265358979323846, 1.0, 1.2};
    } else if (frame < 300) {
        intent = {sim::LocomotionMode::Run, -2.4, 0.65, -1.0};
    } else {
        intent = {sim::LocomotionMode::Walk, -0.5, 0.3, 0.2};
    }
    return intent;
}

}  // namespace

int main() {
    constexpr double dt = 1.0 / 30.0;
    sim::LocomotionState state{};
    std::puts("frame,mode,direction,amplitude,target_yaw,pos_x,pos_z,vel_x,vel_z,previous_yaw,yaw,response");
    for (int frame = 0; frame < 360; ++frame) {
        const sim::LocomotionIntent intent = IntentForFrame(frame);
        sim::StepLocomotion(state, intent, dt);
        std::printf("%d,%s,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%s\n",
            frame, intent.mode == sim::LocomotionMode::Walk ? "walk" : "run",
            intent.speed_direction_radians, intent.speed_amplitude, intent.orientation_yaw_radians,
            state.position.x, state.position.z, state.velocity.x, state.velocity.z,
            state.previous_yaw_radians, state.yaw_radians, sim::ToString(state.response));
    }
    return 0;
}
