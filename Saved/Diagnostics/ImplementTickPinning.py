from pathlib import Path
root=Path('Source/GameAnimationSample3')
p=root/'Private/ProphecyWalkTickPinning.h'
p.write_text('''#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
namespace ProphecyWalkPinning
{
// Experimental presentation cache; no changes to the NN clock or retained agent layouts.
struct FTickPinFrame
{
    FVector3f Delta[2]={FVector3f::ZeroVector,FVector3f::ZeroVector};
    FVector2f Applied=FVector2f::ZeroVector,Cap=FVector2f(1,1),Minimum=FVector2f::ZeroVector;
    FVector2f WalkWeight=FVector2f::ZeroVector,OtherPin=FVector2f::ZeroVector;
    bool Valid=false;
    float Effective(int32 Side,float Smoothed) const
    { return FMath::Min(Cap[Side],FMath::Max(Smoothed,Minimum[Side])); }
    FVector3f Shift(int32 Side,float Smoothed) const
    { return Valid ? Delta[Side]*((Effective(Side,Smoothed)-Applied[Side])*WalkWeight[Side]) : FVector3f::ZeroVector; }
};
struct FTickPinning
{
    FTickPinFrame Previous,Current;
    int32 PoseId=INDEX_NONE;
    int32 Bones[8]={};
    FTransform BasePrevious[8],BaseCurrent[8];
    FVector2f Last=FVector2f(-1,-1);
    bool HasBase=false,Dirty=false;
};
FTickPinning* FindTickPinning(const AProphecyAgent* Agent);
bool AnyTickPinning();
void ResetTickPinning(const AProphecyAgent* Agent);
}
''')
p=root/'Public/ProphecyWalkPinningLibrary.h';s=p.read_text();needle='    /** Walk only (including its recovery blend)'
s=s.replace(needle,'''    /** Temporary A/B switch. Uses the latest NN pin request and existing Pin In/Out
     * frames to update Walk foot targets every unpaused game tick. NN inference stays
     * at its configured rate. Off by default; disable restores the ordinary path.
     * Requires Set Walk Pinning Smoothing; no state/tick work when disabled. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Foot Pinning",meta=(DefaultToSelf="Agent",DisplayName="Set Walk Pinning Every Tick"))
    static bool SetWalkPinningEveryTick(AProphecyAgent* Agent,bool Enabled=true);

'''+needle);p.write_text(s)
p=root/'Public/ProphecyNNPoseTypes.h';s=p.read_text();pos=s.index('public:',s.index('class GAMEANIMATIONSAMPLE3_API FProphecyNNPoseStore'))+len('public:');s=s[:pos]+'''
    // Replace only the eight cached leg transforms; preserve source time and upper pose.
    static void UpdateTickPinningLegs(int32 AgentId,TConstArrayView<int32> Indices,
        TConstArrayView<FTransform> Previous,TConstArrayView<FTransform> Current);
'''+s[pos:];p.write_text(s)
p=root/'Private/ProphecyNNPoseTypes.cpp';s=p.read_text();s+='''
void FProphecyNNPoseStore::UpdateTickPinningLegs(int32 Id,TConstArrayView<int32> Indices,
    TConstArrayView<FTransform> Previous,TConstArrayView<FTransform> Current)
{
    FWriteScopeLock Lock(GProphecyNNPoseLock);
    auto* P=GProphecyNNPoses.Find(Id);
    if(!P || Indices.Num()!=8 || Previous.Num()!=8 || Current.Num()!=8)return;
    for(int32 J=0;J<8;++J)
    {
        const int32 I=Indices[J];
        if(!P->ComponentTransforms.IsValidIndex(I) || !P->PreviousComponentTransforms.IsValidIndex(I))return;
    }
    for(int32 J=0;J<8;++J)
    {
        const int32 I=Indices[J];P->PreviousComponentTransforms[I]=Previous[J];P->ComponentTransforms[I]=Current[J];
        const int32 Parent=J%4 ? Indices[J-1] : P->BoneNames.IndexOfByKey(FName(TEXT("pelvis")));
        if(P->LocalTransforms.IsValidIndex(I) && P->ComponentTransforms.IsValidIndex(Parent))
            P->LocalTransforms[I]=Current[J].GetRelativeTransform(P->ComponentTransforms[Parent]);
    }
    P->Revision=AllocatePoseRevision();
}
''';p.write_text(s)
p=root/'Private/ProphecyWalkPinningLibrary.cpp';s=p.read_text().replace('#include "ProphecyWalkPinning.h"','#include "ProphecyWalkPinning.h"\n#include "ProphecyWalkTickPinning.h"\n#include "ProphecyNNPoseTypes.h"');s=s.replace('static TMap<TWeakObjectPtr<const AProphecyAgent>,FSettings> Settings;', '''static TMap<TWeakObjectPtr<const AProphecyAgent>,FTickPinning> TickPins;
FTickPinning* FindTickPinning(const AProphecyAgent* A) {return TickPins.IsEmpty()?nullptr:TickPins.Find(A);}
bool AnyTickPinning() {return !TickPins.IsEmpty();}
void ResetTickPinning(const AProphecyAgent* A)
{
    if(auto* T=FindTickPinning(A))
    {
        if(T->HasBase) FProphecyNNPoseStore::UpdateTickPinningLegs(T->PoseId,MakeArrayView(T->Bones),MakeArrayView(T->BasePrevious),MakeArrayView(T->BaseCurrent));
        *T=FTickPinning{};
    }
}
static TMap<TWeakObjectPtr<const AProphecyAgent>,FSettings> Settings;''');s=s.replace('void ResetSmoothing(const AProphecyAgent* Agent)\n{','void ResetSmoothing(const AProphecyAgent* Agent)\n{\n    ResetTickPinning(Agent);');s=s.replace('if (Settings.IsEmpty() && ReachGuards.IsEmpty()', 'if (TickPins.IsEmpty() && Settings.IsEmpty() && ReachGuards.IsEmpty()');s=s.replace('for (auto It=Smoothing.CreateIterator();It;++It)\n                if', 'for (auto It=TickPins.CreateIterator();It;++It)\n                if (!It.Key().IsValid() || It.Key()->GetWorld()==World) It.RemoveCurrent();\n            for (auto It=Smoothing.CreateIterator();It;++It)\n                if');marker='bool UProphecyWalkPinningLibrary::SetWalkPinningBackwardTransfer';s=s.replace(marker,'''bool UProphecyWalkPinningLibrary::SetWalkPinningEveryTick(AProphecyAgent* Agent,bool Enabled)
{
    using namespace ProphecyWalkPinning;
    if(!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed())return false;
    if(Enabled) TickPins.FindOrAdd(Agent);
    else {ResetTickPinning(Agent);TickPins.Remove(Agent);}
    RefreshCleanup();return true;
}
'''+marker);p.write_text(s)
p=root/'Public/ProphecyNNLocomotionManager.h';s=p.read_text().replace('void PublishAgentPose(int32 AgentIndex, double SourceTimeSeconds);','void PublishAgentPose(int32 AgentIndex, double SourceTimeSeconds);\n    void UpdateWalkTickPinning();');p.write_text(s)
