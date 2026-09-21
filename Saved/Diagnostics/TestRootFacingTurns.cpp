#include "../../StandaloneSim/sim_core/src/locomotion.cpp"
#include <iostream>
#include <cassert>
int main()
{
    using namespace prophecy::sim;
    constexpr double dt=1./30.;
    for (int mode=0;mode<3;++mode)
    {
        LocomotionState state{};LocomotionIntent intent{};
        intent.speed_amplitude=1;intent.mode=LocomotionMode::Run;
        AddRootYawImpulse(state,intent,22.406,dt);
        double peak=0,reverse=0;
        for (int i=0;i<300;++i)
        {
            const double requested=mode==1 ? 0.0001*std::sin(i*.3) : 0.;
            // Current UE path versus slightly changing keyboard/camera heading versus solution.
            if (mode==2 || std::abs(SignedAngleDelta(intent.orientation_yaw_radians,requested))>1.e-6)
                intent.orientation_yaw_radians=state.yaw_radians+SignedAngleDelta(state.yaw_radians,requested);
            const double old=state.yaw_radians;
            intent.speed_direction_radians=SignedAngleDelta(state.yaw_radians,0);
            StepLocomotion(state,intent,dt,nullptr,true);
            peak=std::max(peak,state.yaw_radians);
            reverse+=std::max(0.,old-state.yaw_radians);
        }
        std::cout<<"mode="<<mode<<" peak_deg="<<peak*180/3.141592653589793
            <<" reverse_deg="<<reverse*180/3.141592653589793
            <<" settled_deg="<<state.yaw_radians*180/3.141592653589793<<std::endl;
        if (!mode) assert(reverse>2*3.141592653589793);
        else assert(reverse<3.141592653589793);
    }
}
