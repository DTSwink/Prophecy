#include "ProphecyDodgeBanks.h"

namespace ProphecyDefense
{
FDodgeControls DodgeControls(const float* Raw,const float* Remaining,float Height)
{
    FDodgeControls Out;
    constexpr int32 Starts[]={0,3,7,11,15,20},Widths[]={2,3,3,3,2,1},Gates[]={2,6,10,14,17,21};
    float Moves[6][3]={};
    for (int32 I=0;I<6;++I)
    {
        const float Gate=FMath::Clamp(Raw[Gates[I]],0.f,1.f),Capacity=FMath::Max(0.f,Remaining[I]);
        float DistanceSquared=0;
        for (int32 J=0;J<Widths[I];++J) { Moves[I][J]=Raw[Starts[I]+J]*Gate;DistanceSquared+=FMath::Square(Moves[I][J]); }
        const float Distance=FMath::Sqrt(DistanceSquared),Scale=FMath::Min(1.f,Capacity/FMath::Max(Distance,1.e-8f));
        for (int32 J=0;J<Widths[I];++J) Moves[I][J]*=Scale;
        Out.RequestedDistance[I]=Distance;Out.Remaining[I]=FMath::Max(0.f,Remaining[I]-FMath::Min(Distance,Capacity));
        if (I<4 && Raw[Gates[I]]>0 && Remaining[I]>0) Out.bEnabled=true;
    }
    Out.PelvisHorizontal={Moves[0][0],Moves[0][1]};Out.Foot[0]=Read(Moves[1]);Out.Foot[1]=Read(Moves[2]);
    Out.PelvisRotation=Read(Moves[3]);Out.RootHorizontal={Moves[4][0],Moves[4][1]};Out.RootYaw=Moves[5][0];
    const float Available=FMath::Max(0.f,Height-.30f);
    Out.DropRequested=FMath::Max(0.f,Raw[18])*FMath::Clamp(Raw[19],0.f,1.f);Out.Drop=FMath::Min(Out.DropRequested,Available);
    Out.bEnabled|=Raw[19]>0 && Available>0;
    return Out;
}
FVector3f DodgeHorizontal(const FVector2f& Offset,const FRows& RootAxes)
{ return Transform({Offset.X,Offset.Y,0},RootAxes); }
FRows DodgeYaw(float Angle)
{
    const float C=FMath::Cos(Angle),S=FMath::Sin(Angle);
    return {{{C,0,-S},{0,1,0},{S,0,C}}};
}
FVector3f DodgeCommand(const FVector3f& InitialDelta,float YawOffset)
{ return Transform(InitialDelta,DodgeYaw(YawOffset)); }
FRootFrame DodgeNextRoot(const FRootFrame& Current,const FVector3f& InitialDelta,float InitialYaw,
    const FVector2f& Horizontal,float YawShift,float YawOffset)
{
    const auto Rotation=DodgeYaw(InitialYaw+YawShift);
    return {Current.P+DodgeCommand(InitialDelta,YawOffset+YawShift)+DodgeHorizontal(Horizontal,Current.R),
        {{Transform(Current.R.V[0],Rotation),Transform(Current.R.V[1],Rotation),Transform(Current.R.V[2],Rotation)}}};
}
}
