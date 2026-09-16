// The exact mover source compiled by Unreal, exercised without the editor.
#include "../../StandaloneSim/sim_core/src/locomotion.cpp"
#include <cassert>
#include <iostream>

int main() {
    using namespace prophecy::sim;
    LocomotionIntent idle{};
    idle.speed_amplitude = 0;
    RootBalanceSpring spring;
    spring.target = {.2, -.1};
    for (double hz : {30., 60., 120.}) {
        LocomotionState state;
        double previous = std::hypot(spring.target.x, spring.target.z);
        for (int i = 0; i < hz*5; ++i) {
            const auto future = PredictFutureRoots(state, idle, 1./hz, false, &spring);
            StepLocomotion(state, idle, 1./hz, nullptr, false, &spring);
            assert(state.position.x == future[0].position.x && state.position.z == future[0].position.z);
            assert(state.yaw_radians == 0);
            const double error = std::hypot(spring.target.x-state.position.x, spring.target.z-state.position.z);
            assert(error <= previous+1e-12);
            previous = error;
            assert(std::hypot(state.velocity.x, state.velocity.z) <= spring.maximum_speed+1e-12);
        }
        assert(previous < 1e-8);
    }
    // Gate input before velocity has had a chance to change. Both walk and run.
    for (auto mode : {LocomotionMode::Walk, LocomotionMode::Run}) {
        auto moving = idle;
        moving.mode = mode;
        moving.speed_amplitude = spring.input_threshold+.0001;
        LocomotionState original, balance;
        assert(!IsRootBalanceActive(balance, moving, spring));
        for (int i=0; i<60; ++i) {
            StepLocomotion(original, moving, 1./30);
            StepLocomotion(balance, moving, 1./30, nullptr, false, &spring);
            assert(original.position.x == balance.position.x && original.position.z == balance.position.z);
            assert(original.velocity.x == balance.velocity.x && original.velocity.z == balance.velocity.z);
        }
    }
    LocomotionState fast;
    fast.velocity = {spring.speed_threshold+.001, 0};
    assert(!IsRootBalanceActive(fast, idle, spring));
    auto ordinary = fast;
    StepLocomotion(fast, idle, 1./30, nullptr, false, &spring);
    StepLocomotion(ordinary, idle, 1./30);
    assert(fast.position.x == ordinary.position.x && fast.velocity.x == ordinary.velocity.x);
    assert(IsRootBalanceActive(LocomotionState{}, idle, spring));
    // High stiffness remains finite; zero damping is allowed. Cap prevents self-disengagement.
    spring.maximum_speed = 10;
    spring.frequency_hz = 1000;
    spring.damping_ratio = 0;
    spring.target = {100, 100};
    LocomotionState capped;
    for (int i=0; i<120; ++i) {
        assert(IsRootBalanceActive(capped, idle, spring));
        StepLocomotion(capped, idle, 1./30, nullptr, false, &spring);
        assert(std::isfinite(capped.position.x));
    }
    // Prediction's complete eight-step window must match real integration.
    spring = RootBalanceSpring{};
    spring.target = {.2, -.1};
    LocomotionState yaw;
    yaw.previous_yaw_radians = -.05;
    idle.turn_scale = 0;
    const auto future = PredictFutureRoots(yaw, idle, 1./30, true, &spring);
    for (int i=0; i<8; ++i) {
        StepLocomotion(yaw, idle, 1./30, nullptr, true, &spring);
        assert(yaw.position.x == future[i].position.x && yaw.position.z == future[i].position.z);
        assert(yaw.yaw_radians == future[i].yaw_radians);
    }
    assert(yaw.yaw_radians > .39);
    spring = RootBalanceSpring{};
    spring.tolerance = .05; // 5 cm disk: inside and boundary exert no correction.
    for (Vec2 position : {Vec2{}, Vec2{.02, .02}, Vec2{.05, 0}}) {
        LocomotionState inside;
        inside.position = position;
        for (int i=0; i<60; ++i) StepLocomotion(inside, idle, 1./30, nullptr, false, &spring);
        assert(inside.position.x == position.x && inside.position.z == position.z);
        assert(inside.velocity.x == 0 && inside.velocity.z == 0);
    }
    LocomotionState coasting;
    coasting.velocity = {.01, -.02};
    spring.maximum_speed = .001;
    StepLocomotion(coasting, idle, 1./30, nullptr, false, &spring);
    assert(coasting.velocity.x == .01 && coasting.velocity.z == -.02);
    assert(std::abs(coasting.position.x-.01/30)<1e-15);
    spring.maximum_speed = .3;
    LocomotionState outside, equivalent;
    outside.position = {.08, 0};
    equivalent.position = outside.position;
    auto point = spring;
    point.tolerance = 0;
    point.target = {.05, 0};
    StepLocomotion(outside, idle, 1./30, nullptr, false, &spring);
    StepLocomotion(equivalent, idle, 1./30, nullptr, false, &point);
    assert(std::abs(outside.velocity.x-equivalent.velocity.x)<1e-14);
    assert(std::abs(outside.position.x-equivalent.position.x)<1e-14);
    auto predicted = PredictFutureRoots(outside, idle, 1./30, false, &spring);
    for (int i=0; i<8; ++i) {
        StepLocomotion(outside, idle, 1./30, nullptr, false, &spring);
        assert(outside.position.x == predicted[i].position.x);
    }
    LocomotionState diagonal;
    diagonal.position = {.04,.04}; // Outside radius, although each coordinate is <5 cm.
    StepLocomotion(diagonal, idle, 1./30, nullptr, false, &spring);
    assert(diagonal.velocity.x < 0 && diagonal.velocity.z < 0);
    std::cout << "Root balance: convergence, caps, input/speed gates, prediction, yaw, tolerance passed\n";
}
