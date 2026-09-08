// Standalone readback regression using the identical mover source compiled by Unreal.
#include "../../StandaloneSim/sim_core/src/locomotion.cpp"
#include <cassert>
#include <iostream>

int main()
{
    using namespace prophecy::sim;
    LocomotionState plain{}, observed{};
    LocomotionIntent intent{};
    LocomotionTarget target{};
    constexpr double dt = 1.0 / 30.0;
    for (int frame = 0; frame < 3000; ++frame)
    {
        intent.mode = frame % 120 < 60 ? LocomotionMode::Walk : LocomotionMode::Run;
        intent.speed_amplitude = double(frame % 11) / 10.0;
        intent.speed_scale = double(frame % 5) / 4.0;
        intent.turn_scale = double(frame % 7) / 6.0;
        intent.speed_direction_radians = double(frame % 37 - 18) * 0.1;
        intent.orientation_yaw_radians = double(frame % 67 - 33) * 0.1;
        const double old_yaw = observed.yaw_radians;
        StepLocomotion(plain, intent, dt);
        StepLocomotion(observed, intent, dt, &target);
        assert(plain.position.x == observed.position.x && plain.position.z == observed.position.z);
        assert(plain.velocity.x == observed.velocity.x && plain.velocity.z == observed.velocity.z);
        assert(plain.yaw_radians == observed.yaw_radians && plain.previous_yaw_radians == observed.previous_yaw_radians);
        assert(plain.distance_travelled == observed.distance_travelled && plain.response == observed.response);
        assert(target.orientation_yaw_radians == intent.orientation_yaw_radians);
        const double speed = std::hypot(target.velocity.x, target.velocity.z);
        const double base = intent.speed_amplitude * intent.speed_scale *
            DirectionalSpeedCap(intent.mode, intent.speed_direction_radians);
        assert(speed + 1e-12 >= base);
        assert(std::abs(target.velocity.x - std::sin(old_yaw + intent.speed_direction_radians) * speed) < 1e-10);
        assert(std::abs(target.velocity.z - std::cos(old_yaw + intent.speed_direction_radians) * speed) < 1e-10);
    }
    observed = {};
    observed.velocity.z = 1.5;
    intent = {};
    intent.mode = LocomotionMode::Run;
    intent.speed_amplitude = 0.3;
    intent.orientation_yaw_radians = 3.14159265358979323846 / 2.0;
    StepLocomotion(observed, intent, dt, &target);
    assert(observed.response == LocomotionResponse::YawOnly);
    assert(std::abs(std::hypot(target.velocity.x, target.velocity.z) - 3.0) < 1e-12);
    assert(observed.yaw_radians != target.orientation_yaw_radians);
    assert(std::hypot(observed.velocity.x, observed.velocity.z) < 3.0);
    intent.speed_amplitude = 0.0;
    StepLocomotion(observed, intent, dt, &target);
    assert(target.velocity.x == 0.0 && target.velocity.z == 0.0);
    std::cout << "PASS: 3000 identical observed/unobserved mover steps; actual run boost; target/current distinction; stop target\n";
}
