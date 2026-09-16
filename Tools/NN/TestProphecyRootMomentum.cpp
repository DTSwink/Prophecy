// Identical mover implementation used in Unreal. No engine/rendering dependency.
#include "../../StandaloneSim/sim_core/src/locomotion.cpp"
#include <cassert>
#include <iostream>

int main() {
    using namespace prophecy::sim;
    constexpr double dt = 1.0 / 30.0;
    for (double impulse : {-1.e9, -12.0, -4.0, 4.0, 12.0, 1.e9}) {
        LocomotionState s{};
        LocomotionIntent goal{};
        goal.speed_amplitude = 0;
        assert(AddRootYawImpulse(s, goal, impulse, dt));
        const double stop = goal.orientation_yaw_radians;
        assert(stop * impulse > 0 && s.yaw_radians == 0);
        assert(std::abs(s.yaw_radians-s.previous_yaw_radians) < 3.141592653589793);
        const auto window=PredictFutureRoots(s,goal,dt,true);
        for(int i=0;i<8;++i) {
            StepLocomotion(s,goal,dt,nullptr,true);
            assert(std::abs(s.yaw_radians-window[i].yaw_radians)<1e-12);
        }
        double reverse=0;
        for(int i=0;i<20000;++i) {
            const double before=s.yaw_radians;
            StepLocomotion(s,goal,dt,nullptr,true);
            reverse += std::max(0., (before-s.yaw_radians)*std::copysign(1.,impulse));
        }
        std::cout << "impulse=" << impulse << " target=" << stop << " final=" << s.yaw_radians << " reverse=" << reverse << std::endl;
        assert(std::abs(s.yaw_radians-stop)<1e-8);
        assert(reverse<0.02);
    }
    LocomotionIntent intent{};
    intent.speed_amplitude = 0;
    for (double strength : {0.25, 0.5, 1.0}) {
        LocomotionState s{};
        LocomotionIntent goal{};
        goal.speed_amplitude=0;goal.turn_scale=strength;
        assert(AddRootYawImpulse(s,goal,4,dt));
        for(int i=0;i<8;++i) StepLocomotion(s,goal,dt,nullptr,true);
        assert(AddRootYawImpulse(s,goal,2,dt));
        const double target=goal.orientation_yaw_radians;
        for(int i=0;i<2000;++i) {
            const double before=s.yaw_radians;
            StepLocomotion(s,goal,dt,nullptr,true);
            assert(s.yaw_radians>=before-1e-9);
        }
        assert(std::abs(s.yaw_radians-target)<1e-8);
    }
    for (double impulse : {-4.0, 4.0}) {
        LocomotionState state{};
        state.velocity = {3, -2};
        state.previous_yaw_radians = -impulse * dt;
        const auto future = PredictFutureRoots(state, intent, dt, true);
        for (int i=0; i<8; ++i) {
            StepLocomotion(state, intent, dt, nullptr, true);
            assert(std::abs(state.yaw_radians-future[i].yaw_radians)<1e-12);
            assert(std::abs(state.position.x-future[i].position.x)<1e-12);
            assert(std::abs(state.position.z-future[i].position.z)<1e-12);
            if (i==0) assert(state.yaw_radians * impulse > 0);
        }
        for (int i=0; i<300; ++i) StepLocomotion(state, intent, dt, nullptr, true);
        assert(std::abs(state.yaw_radians)<1e-8);
        assert(std::hypot(state.velocity.x, state.velocity.z)<1e-8);
    }
    // A zero steering knob must not cancel external angular velocity.
    LocomotionState coast{};
    coast.previous_yaw_radians = -2 * dt;
    intent.turn_scale = 0;
    for (int i=0; i<30; ++i) StepLocomotion(coast, intent, dt, nullptr, true);
    assert(std::abs(coast.yaw_radians-2)<1e-10);
    // No-impulse entry points must remain exactly equivalent, including prediction.
    LocomotionState legacy{}, explicit_false{};
    for (int i=0; i<3000; ++i) {
        intent.mode = i%2 ? LocomotionMode::Walk : LocomotionMode::Run;
        intent.speed_amplitude = (i%11)*0.1;
        intent.turn_scale = (i%5)*0.25;
        intent.orientation_yaw_radians = (i%63)*0.1;
        StepLocomotion(legacy, intent, dt);
        StepLocomotion(explicit_false, intent, dt, nullptr, false);
        assert(legacy.position.x==explicit_false.position.x && legacy.position.z==explicit_false.position.z);
        assert(legacy.yaw_radians==explicit_false.yaw_radians);
        assert(legacy.velocity.x==explicit_false.velocity.x && legacy.velocity.z==explicit_false.velocity.z);
    }
    std::cout << "PASS: signed angular impulse, prediction equality, braking, zero-turn coasting, 3000 no-impulse steps\n";
}
