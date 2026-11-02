#pragma once
#include "ProphecyFootIKLive.h"

// The lab's short local velocity carry, sampled at the game's publication rate.
// It follows the newly reseeded NN; there is no cached gait destination.
namespace ProphecyFootIKGame
{
struct FTerrainReturn
{
    static constexpr int32 Parent[25]={-1,0,1,2,3,4,5,6,7,8,5,10,11,12,5,14,15,0,17,18,19,0,21,22,23};
    TArray<FTransform> Start;
    TArray<FVector> Linear,Angular,Offset,AngularOffset;
    int32 BeginTick=-1,FreshTick=-1;
    double SourceTime=0;
    bool HasOutgoingVelocity=false;
    static FVector Log(FQuat Q)
    {
        if(Q.W<0)Q=Q*-1.;const double N=FVector(Q.X,Q.Y,Q.Z).Size();
        return FVector(Q.X,Q.Y,Q.Z)*(N<1.e-10?2.:2.*FMath::Atan2(N,Q.W)/N);
    }
    static FQuat Exp(const FVector& V)
    {
        const double N=V.Size();if(N<1.e-10)return FQuat(V.X*.5,V.Y*.5,V.Z*.5,1).GetNormalized();
        const FVector A=V*(FMath::Sin(N*.5)/N);return FQuat(A.X,A.Y,A.Z,FMath::Cos(N*.5));
    }
    static FTransform Carrier(const ProphecyFootIKLive::FSourceSample& S)
    {return FTransform(FRotator(0,S.HeadingWorld.Rotation().Yaw,0),S.RootWorld);}
    static TArray<FTransform> Local(const ProphecyFootIKLive::FSourceSample& S)
    {
        TArray<FTransform> Out;Out.Reserve(25);const auto Root=Carrier(S);
        for(int32 I=0;I<25;++I)Out.Add(S.BodiesWorld[I].GetRelativeTransform(Parent[I]<0?Root:S.BodiesWorld[Parent[I]]));return Out;
    }
    void Begin(int32 Tick,double RawSourceTime,const ProphecyFootIKLive::FSourceSample& Previous,const ProphecyFootIKLive::FSourceSample& Current)
    {
        BeginTick=Tick;FreshTick=-1;SourceTime=RawSourceTime;HasOutgoingVelocity=false;Start=Local(Current);const auto Old=Local(Previous);
        Linear.SetNum(25);Angular.SetNum(25);
        for(int32 I=0;I<25;++I){Linear[I]=(Start[I].GetLocation()-Old[I].GetLocation())*60.;Angular[I]=Log(Start[I].GetRotation()*Old[I].GetRotation().Inverse())*60.;}
    }
    bool Apply(int32 Tick,double RawSourceTime,ProphecyFootIKLive::FSourceSample& Sample,const ProphecyFootIKLive::FSourceSample& Endpoint)
    {
        if(BeginTick<0)return false;const double T=(Tick-BeginTick)/120.,Duration=.10;
        if(T>=Duration){BeginTick=-1;Start.Reset();Linear.Reset();Angular.Reset();Offset.Reset();AngularOffset.Reset();return false;}
        auto Pose=Local(Sample);
        // The normal manager may publish on the intervening game tick. Until
        // that happens, advance the actual incoming local velocity rather than
        // exposing its old, uncorrected display buffer for one frame.
        const bool Fresh=RawSourceTime>SourceTime+1.e-8;
        if(Fresh&&!HasOutgoingVelocity)
        {
            // A new publication starts at Alpha0: its displayed predecessor is
            // the corrected seed, not a new motion sample. The future endpoint
            // supplies the actual outgoing30Hz velocity even on that tick.
            const auto Future=Local(Endpoint);
            Offset.SetNum(25);AngularOffset.SetNum(25);FreshTick=Tick;
            for(int32 I=0;I<25;++I)
            {
                // Bridge the publication latency in local pose space. Advancing
                // the NN clock here would create a phase snap when carry ends.
                FVector Predicted=Start[I].GetLocation()+Linear[I]*T;
                if(I>0&&Predicted.SizeSquared()>1.e-16)Predicted=Predicted.GetSafeNormal()*Pose[I].GetLocation().Size();
                Offset[I]=Predicted-Pose[I].GetLocation();
                AngularOffset[I]=Log(Exp(Angular[I]*T)*Start[I].GetRotation()*Pose[I].GetRotation().Inverse());
                Linear[I]-=(Future[I].GetLocation()-Start[I].GetLocation())*30.;Angular[I]-=Log(Future[I].GetRotation()*Start[I].GetRotation().Inverse())*30.;
            }
            HasOutgoingVelocity=true;
        }
        const double Elapsed=HasOutgoingVelocity?(Tick-FreshTick)/120.:0;
        const double U=HasOutgoingVelocity?Elapsed/(Duration-(FreshTick-BeginTick)/120.):0;
        const double Carry=HasOutgoingVelocity?Elapsed*FMath::Square(1.-U):T;
        const double PositionCarry=HasOutgoingVelocity?(1+2*U)*FMath::Square(1-U):0;
        if(!HasOutgoingVelocity)Pose=Start;
        const auto Root=Carrier(Sample);
        for(int32 I=0;I<25;++I)
        {
            const double BoneLength=Pose[I].GetLocation().Size();FVector P=Pose[I].GetLocation()+Linear[I]*Carry;
            if(HasOutgoingVelocity)P+=Offset[I]*PositionCarry;
            if(I>0&&P.SizeSquared()>1.e-16)P=P.GetSafeNormal()*BoneLength;
            Pose[I].SetLocation(P);Pose[I].SetRotation((Exp(Angular[I]*Carry+(HasOutgoingVelocity?AngularOffset[I]*PositionCarry:FVector::ZeroVector))*Pose[I].GetRotation()).GetNormalized());
            Sample.BodiesWorld[I]=Pose[I]*(Parent[I]<0?Root:Sample.BodiesWorld[Parent[I]]);
        }
        return true;
    }
};
}
