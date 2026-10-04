#include "ProphecyRootResponse.h"
#include <cstdio>
#include <cstdlib>
#include <limits>
using namespace prophecy::sim;
constexpr double Dt=1./30., Pi=3.14159265358979323846;
void Check(bool OK,const char* Message) { if(!OK){std::fprintf(stderr,"FAIL: %s\n",Message);std::exit(1);} }
bool Equal(const FutureRootWindow& A,const FutureRootWindow& B)
{
    for(int I=0;I<8;++I)if(A[I].position.x!=B[I].position.x || A[I].position.z!=B[I].position.z || A[I].yaw_radians!=B[I].yaw_radians)return false;
    return true;
}
double Speed(const LocomotionState& S,const RootTransform& R)
{return std::hypot(R.position.x-S.position.x,R.position.z-S.position.z)/Dt;}
FutureRootWindow Predict(const LocomotionState& S,const LocomotionIntent& I,double A=1,double D=1,double O=1,double B=-1)
{return ProphecyRootResponse::Predict(S,I,Dt,false,nullptr,A,D,O,B);}
int main()
{
    LocomotionState S;LocomotionIntent I;I.mode=LocomotionMode::Run;
    auto Ordinary=Predict(S,I),Fast=Predict(S,I,2);
    Check(Equal(Ordinary,PredictFutureRoots(S,I,Dt)),"all ones exactly match native forecast");
    Check(Speed(S,Fast[0])>Speed(S,Ordinary[0]),"acceleration above one increases first-step response");
    Check(std::abs(Speed(S,Fast[0])-2*Speed(S,Ordinary[0]))<1.e-12,"two doubles forward acceleration progress");
    Check(Speed(S,Predict(S,I,1.e30)[0])<=DirectionalSpeedCap(I.mode,0)+1.e-12,"large gain cannot exceed requested speed");
    S.velocity={0,5};I.speed_amplitude=0;
    Ordinary=Predict(S,I);Fast=Predict(S,I,1,1,1,2);
    Check(Speed(S,Fast[0])<Speed(S,Ordinary[0]),"braking independently becomes faster");
    Check(Speed(S,Predict(S,I,1,1,1,1.e30)[0])==0.,"large braking stops without reverse motion");
    Check(Equal(Predict(S,I,2),Predict(S,I,2,1,1,2)),"deceleration inherits above-one acceleration");
    Check(Equal(Ordinary,Predict(S,I,2,1,1,1)),"explicit one braking keeps ordinary stop response");
    S={};I={};I.mode=LocomotionMode::Run;S.velocity={0,4};I.speed_direction_radians=Pi/2;
    Ordinary=Predict(S,I);Fast=Predict(S,I,1,2);
    Check(std::atan2(Fast[0].position.x,Fast[0].position.z)>std::atan2(Ordinary[0].position.x,Ordinary[0].position.z),"direction sharpens steering");
    Check(std::abs(Speed(S,Fast[0])-Speed(S,Ordinary[0]))<1.e-12,"direction-only preserves first-step speed");
    S={};I={};I.speed_amplitude=0;I.orientation_yaw_radians=Pi/2;
    Ordinary=Predict(S,I);Fast=Predict(S,I,1,1,2);
    Check(Fast[0].yaw_radians>Ordinary[0].yaw_radians,"orientation sharpens facing response");
    Check(Predict(S,I,1,1,1.e30)[0].yaw_radians==I.orientation_yaw_radians,"orientation saturates at target");
    S.yaw_radians=S.previous_yaw_radians=179*Pi/180;I.orientation_yaw_radians=-179*Pi/180;
    Check(std::abs(SignedAngleDelta(Predict(S,I,1,1,100)[0].yaw_radians,I.orientation_yaw_radians))<1.e-12,"wraparound takes short arc");
    S={};I={};I.speed_amplitude=0;
    Check(AddRootYawImpulse(S,I,3,Dt),"seed angular impulse");
    Check(Equal(PredictFutureRoots(S,I,Dt,true),ProphecyRootResponse::Predict(S,I,Dt,true,nullptr,1,1,10,-1)),"orientation gain preserves explicit angular momentum contract");
    RootBalanceSpring Balance;Balance.target={.1,.1};S={};
    Check(Equal(PredictFutureRoots(S,I,Dt,false,&Balance),ProphecyRootResponse::Predict(S,I,Dt,false,&Balance,10,10,1,10)),"distance/direction gains leave balance spring alone");
    S={};I={};I.mode=LocomotionMode::Run;
    for(int Tick=0;Tick<2000;++Tick)
    {
        I.speed_amplitude=(Tick/47)%2?1.:0.;I.speed_direction_radians=std::sin(Tick*.03)*Pi;
        I.orientation_yaw_radians=std::cos(Tick*.017)*Pi;
        const auto Native=PredictFutureRoots(S,I,Dt);
        Check(Equal(Native,Predict(S,I)),"all-one exact identity across reversals/turns/stops");
        Check(Equal(Native,Predict(S,I,.2,.4,0,.8)),"sub-one controls leave native forecast untouched");
        const auto Window=Predict(S,I,2,3,4,5);
        for(const auto& R:Window)Check(std::isfinite(R.position.x)&&std::isfinite(R.position.z)&&std::isfinite(R.yaw_radians),"finite mixed-gain forecast");
        auto Next=S;Next.velocity={(Window[0].position.x-S.position.x)/Dt,(Window[0].position.z-S.position.z)/Dt};
        Next.position=Window[0].position;Next.previous_yaw_radians=S.yaw_radians;Next.yaw_radians=Window[0].yaw_radians;
        auto NextIntent=I;NextIntent.speed_direction_radians=SignedAngleDelta(Next.yaw_radians,S.yaw_radians+I.speed_direction_radians);
        const auto Continued=Predict(Next,NextIntent,2,3,4,5);
        Check(std::hypot(Continued[0].position.x-Window[1].position.x,Continued[0].position.z-Window[1].position.z)<1.e-10 &&
            std::abs(SignedAngleDelta(Continued[0].yaw_radians,Window[1].yaw_radians))<1.e-10,"forecast matches actual first-step advancement");
        S=Next;
    }
    std::puts("PASS: identity, acceleration, braking, direction, orientation, bounds, wrap, impulse, balance, 2000-step forecast parity");
}
