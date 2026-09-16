#include "ProphecyDodgeRuntime.h"

namespace ProphecyDefense
{
void FDodgeState::Initialize(const float* Lower0,const float* Upper0,const float* Root0,
    const float* Lower1,const float* Upper1,const float* Root1,const float* Limits)
{
    FMemory::Memcpy(PreviousLower,Lower0,sizeof(PreviousLower));FMemory::Memcpy(PreviousUpper,Upper0,sizeof(PreviousUpper));
    FMemory::Memcpy(CurrentLower,Lower1,sizeof(CurrentLower));FMemory::Memcpy(CurrentUpper,Upper1,sizeof(CurrentUpper));
    FMemory::Memcpy(Remaining,Limits,sizeof(Remaining));
    PreviousRoot=FRootFrame::Read12(Root0);CurrentRoot=FRootFrame::Read12(Root1);
    InitialRootCommand(Root0,Root1,InitialWorldDelta,InitialYawDelta);
    RootShift=FVector3f::ZeroVector;YawOffset=0;CompletedSteps=0;bInitialized=true;
}
bool PrepareDodge(const FDodgeState& S,const float* Frozen,FContext Context,FDodgeWork& W,float* Input)
{
    W.StateStep=MAX_uint64;if (!S.bInitialized) return false;
    Context.RootPosition=S.CurrentRoot.P;Context.RootAxes=S.CurrentRoot.R;
    Context.InitialWorldDelta=DodgeCommand(S.InitialWorldDelta,S.YawOffset);Context.InitialYawDelta=S.InitialYawDelta;
    float Features[50];if (!Conditioning(Context,Features)) return false;
    float PreviousLower[41],PreviousUpper[90];
    RebaseLower(S.PreviousLower,PreviousLower,S.PreviousRoot.P,S.PreviousRoot.R,S.CurrentRoot.P,S.CurrentRoot.R);
    RebaseUpper(S.PreviousUpper,PreviousUpper,S.PreviousRoot.P,S.PreviousRoot.R,S.CurrentRoot.P,S.CurrentRoot.R);
    UpperInput(PreviousUpper,S.CurrentUpper,PreviousLower,S.CurrentLower,Frozen,Features,Input);
    FMemory::Memcpy(Input+257,PreviousLower+9,32*sizeof(float));
    FMemory::Memcpy(Input+289,S.CurrentLower+9,32*sizeof(float));
    FMemory::Memcpy(Input+321,Frozen+9,32*sizeof(float));FMemory::Memcpy(Input+353,S.Remaining,6*sizeof(float));
    Write(Input+359,InTransposedBasis(S.RootShift,S.CurrentRoot.R));W.StateStep=S.CompletedSteps;return true;
}
bool CompleteDodge(FDodgeState& S,const FDodgeWork& W,const float* Frozen,const float* Output,
    const FGeometry& Geometry,FPose& Pose,float* ModifiedLower,float* UnrebasedUpper)
{
    if (!S.bInitialized || W.StateStep!=S.CompletedSteps) return false;
    const float PelvisHeight=(Transform(Read(Frozen),S.CurrentRoot.R)+S.CurrentRoot.P).Y;
    const auto C=DodgeControls(Output+90,S.Remaining,PelvisHeight);
    float Modified[41];Geometry.SolveDodgeLower(Frozen,C,S.CurrentRoot.P,S.CurrentRoot.R,Modified);
    if (ModifiedLower) FMemory::Memcpy(ModifiedLower,Modified,sizeof(Modified));
    const FRows Identity={{{1,0,0},{0,1,0},{0,0,1}}};
    FPose CurrentBasePose,NextBasePose;float CurrentBase[90],NextBase[90],Upper[90];
    Geometry.LowerPose(S.CurrentLower,FVector3f::ZeroVector,Identity,CurrentBasePose,false);
    Geometry.EncodeUpper(CurrentBasePose,FVector3f::ZeroVector,Identity,CurrentBase);
    Geometry.LowerPose(Modified,FVector3f::ZeroVector,Identity,NextBasePose);
    Geometry.EncodeUpper(NextBasePose,FVector3f::ZeroVector,Identity,NextBase);
    CarryUpper(S.CurrentUpper,CurrentBase,NextBase,Upper);for (int32 I=0;I<90;++I) Upper[I]+=Output[I];CleanUpper(Upper);
    if (UnrebasedUpper) FMemory::Memcpy(UnrebasedUpper,Upper,sizeof(Upper));
    for (int32 I=0;I<25;++I)
    {
        NextBasePose.P[I]=Transform(NextBasePose.P[I],S.CurrentRoot.R)+S.CurrentRoot.P;
        for (auto& Row:NextBasePose.R[I].V) Row=Transform(Row,S.CurrentRoot.R);
    }
    // The final decoder derives its baseline from the supplied world pose,
    // retaining float32 root-basis effects from the reference.
    float WorldBase[90];Geometry.EncodeUpper(NextBasePose,S.CurrentRoot.P,S.CurrentRoot.R,WorldBase);
    Geometry.Finish(Modified,Upper,S.CurrentRoot.P,S.CurrentRoot.R,NextBasePose,WorldBase,Pose);
    const auto NextRoot=DodgeNextRoot(S.CurrentRoot,S.InitialWorldDelta,S.InitialYawDelta,C.RootHorizontal,C.RootYaw,S.YawOffset);
    FMemory::Memcpy(S.PreviousLower,S.CurrentLower,sizeof(S.PreviousLower));FMemory::Memcpy(S.PreviousUpper,S.CurrentUpper,sizeof(S.PreviousUpper));
    RebaseLower(Modified,S.CurrentLower,S.CurrentRoot.P,S.CurrentRoot.R,NextRoot.P,NextRoot.R);
    RebaseUpper(Upper,S.CurrentUpper,S.CurrentRoot.P,S.CurrentRoot.R,NextRoot.P,NextRoot.R);
    S.RootShift+=DodgeHorizontal(C.RootHorizontal,S.CurrentRoot.R);S.YawOffset+=C.RootYaw;
    FMemory::Memcpy(S.Remaining,C.Remaining,sizeof(S.Remaining));S.PreviousRoot=S.CurrentRoot;S.CurrentRoot=NextRoot;
    ++S.CompletedSteps;return true;
}
}
