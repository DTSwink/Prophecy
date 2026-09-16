#include "ProphecyParryRuntime.h"

namespace ProphecyDefense
{
void FParryState::Initialize(const float* Lower0,const float* Upper0,const float* Root0,
    const float* Lower1,const float* Upper1,const float* Root1,const float* Baseline1)
{
    FMemory::Memcpy(PreviousLower,Lower0,sizeof(PreviousLower));FMemory::Memcpy(PreviousUpper,Upper0,sizeof(PreviousUpper));
    FMemory::Memcpy(CurrentLower,Lower1,sizeof(CurrentLower));FMemory::Memcpy(CurrentUpper,Upper1,sizeof(CurrentUpper));
    FMemory::Memcpy(CurrentBaseline,Baseline1,sizeof(CurrentBaseline));
    PreviousRoot=FRootFrame::Read12(Root0);CurrentRoot=FRootFrame::Read12(Root1);
    InitialRootCommand(Root0,Root1,InitialWorldDelta,InitialYawDelta);CompletedSteps=0;bInitialized=true;
}
bool PrepareParry(const FParryState& S,const float* NextLower,const float* NextBaseline,
    const FRootFrame& NextRoot,FContext Context,float Drawn,FParryWork& W,float* Input)
{
    W.StateStep=MAX_uint64;
    if (!S.bInitialized) return false;
    Context.RootPosition=S.CurrentRoot.P;Context.RootAxes=S.CurrentRoot.R;
    Context.InitialWorldDelta=S.InitialWorldDelta;Context.InitialYawDelta=S.InitialYawDelta;
    float Conditioning50[50];
    if (!Conditioning(Context,Conditioning50)) return false;
    float PreviousLower[41],PreviousUpper[90];
    RebaseLower(S.PreviousLower,PreviousLower,S.PreviousRoot.P,S.PreviousRoot.R,S.CurrentRoot.P,S.CurrentRoot.R);
    RebaseUpper(S.PreviousUpper,PreviousUpper,S.PreviousRoot.P,S.PreviousRoot.R,S.CurrentRoot.P,S.CurrentRoot.R);
    RebaseLower(NextLower,W.HeldLower,NextRoot.P,NextRoot.R,S.CurrentRoot.P,S.CurrentRoot.R);
    RebaseUpper(NextBaseline,W.HeldBaseline,NextRoot.P,NextRoot.R,S.CurrentRoot.P,S.CurrentRoot.R);
    UpperInput(PreviousUpper,S.CurrentUpper,PreviousLower,S.CurrentLower,W.HeldLower,Conditioning50,Input);
    Input[257]=Drawn;W.StateStep=S.CompletedSteps;return true;
}
bool CompleteParry(FParryState& S,const FParryWork& W,const float* Delta,const float* NextLower,
    const float* NextBaseline,const FRootFrame& NextRoot,const FPose& Frozen,const FGeometry& Geometry,FPose& Out)
{
    if (!S.bInitialized || W.StateStep!=S.CompletedSteps) return false;
    float Upper[90];CarryUpper(S.CurrentUpper,S.CurrentBaseline,W.HeldBaseline,Upper);
    for (int32 I=0;I<90;++I) Upper[I]+=Delta[I];CleanUpper(Upper);
    Geometry.Finish(W.HeldLower,Upper,S.CurrentRoot.P,S.CurrentRoot.R,Frozen,W.HeldBaseline,Out);
    FMemory::Memcpy(S.PreviousLower,S.CurrentLower,sizeof(S.PreviousLower));
    FMemory::Memcpy(S.PreviousUpper,S.CurrentUpper,sizeof(S.PreviousUpper));
    // Recurrent state is the learned representation, never re-encoded from
    // the retargeted/physical presentation pose.
    RebaseUpper(Upper,S.CurrentUpper,S.CurrentRoot.P,S.CurrentRoot.R,NextRoot.P,NextRoot.R);
    FMemory::Memcpy(S.CurrentLower,NextLower,sizeof(S.CurrentLower));
    FMemory::Memcpy(S.CurrentBaseline,NextBaseline,sizeof(S.CurrentBaseline));
    S.PreviousRoot=S.CurrentRoot;S.CurrentRoot=NextRoot;++S.CompletedSteps;return true;
}
}
