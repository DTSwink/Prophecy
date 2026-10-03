#include "ProphecyAttackFootLocomotionLibrary.h"
#include "ProphecyAttackFootLocomotion.h"
#include "ProphecyAttackStartInertia.h"
#include "ProphecyNNPresentation.h"
#include "ProphecyAgent.h"
#include "ProphecyBlendClock.h"
#include "ProphecyAttackFootLocomotionMath.h"
#include "DrawDebugHelpers.h"
#include "Engine/World.h"

namespace ProphecyAttackFootLocomotion
{
static TMap<TWeakObjectPtr<const AProphecyAgent>,FConfig> Configs,Baselines;
static TMap<TWeakObjectPtr<const AProphecyAgent>,FRun> Runs;
static TSet<TWeakObjectPtr<const AProphecyAgent>> GhostSettings,GhostBaselines;
static TMap<TWeakObjectPtr<const AProphecyAgent>,FGhostRun> GhostRuns;
FGhostRun* FindGhost(const AProphecyAgent* A)
{
    const auto* R=Runs.IsEmpty()?nullptr:Runs.Find(A);
    return R && !R->Suspended && !GhostRuns.IsEmpty()?GhostRuns.Find(A):nullptr;
}
void CancelGhost(const AProphecyAgent* A,float* State)
{
    if(const auto* G=GhostRuns.Find(A))
    {
        FMemory::Memcpy(State+9,G->PreviousLegs,sizeof(G->PreviousLegs));
        FMemory::Memcpy(State+50,G->CurrentLegs,sizeof(G->CurrentLegs));
        GhostRuns.Remove(A);
    }
}
void BeginGhost(const AProphecyAgent* A,const float* State,TConstArrayView<FTransform> Pose,const FTransform& Carrier)
{
    const auto* R=FindActive(A);if(!R || !GhostSettings.Contains(A))return;
    auto& G=GhostRuns.FindOrAdd(A);G=FGhostRun{};G.PoseId=R->PoseId;
    FMemory::Memcpy(G.Legs,R->Legs,sizeof(G.Legs));
    FMemory::Memcpy(G.PreviousLegs,State+9,sizeof(G.PreviousLegs));
    FMemory::Memcpy(G.CurrentLegs,State+50,sizeof(G.CurrentLegs));
    G.PreviousWorld[0]=G.CurrentWorld[0]=Pose[0]*Carrier;
    for(int32 S=0;S<2;++S)for(int32 B=0;B<4;++B)
        G.PreviousWorld[1+S*4+B]=G.CurrentWorld[1+S*4+B]=Pose[G.Legs[S][B]]*Carrier;
}
static TMap<TWeakObjectPtr<const AProphecyAgent>,float> FreezeSettings,FreezeBaselines;
static TMap<TWeakObjectPtr<const AProphecyAgent>,FFreezeWindow> FreezeWindows;
struct FHandoffConfig { float Rotation=1,Duration[2]={0,0}; };
struct FHandoff { FHandoffConfig Config;double Elapsed[2]={0,0};uint8 Started=0; };
static TMap<TWeakObjectPtr<const AProphecyAgent>,FHandoffConfig> HandoffSettings,HandoffBaselines;
static TMap<TWeakObjectPtr<const AProphecyAgent>,FHandoff> Handoffs;
// Separate from retained handoff layouts for safe Live Coding.
static TMap<TWeakObjectPtr<const AProphecyAgent>,float> PoleSettings,PoleBaselines;
struct FPoleBlend { double Duration=0,Elapsed[2]={0,0};uint8 Feet=0,Running=0; };
static TMap<TWeakObjectPtr<const AProphecyAgent>,FPoleBlend> PoleBlends;
static ProphecyBlendClock::EKind PoleClock(int32 Side)
{return Side?ProphecyBlendClock::EKind::RightAttackFootPole:ProphecyBlendClock::EKind::LeftAttackFootPole;}
static void ClearPoles(const AProphecyAgent* A)
{
    if(PoleBlends.IsEmpty() || !PoleBlends.Remove(A))return;
    for(int32 S=0;S<2;++S)ProphecyBlendClock::Stop(A,PoleClock(S));
}
void AdvancePoles(const AProphecyAgent* A,uint8 Remaining,float (&Alpha)[2])
{
    Alpha[0]=Alpha[1]=-1;
    auto* P=PoleBlends.IsEmpty()?nullptr:PoleBlends.Find(A);if(!P)return;
    for(int32 S=0;S<2;++S)if(P->Feet&(1<<S))
    {
        const uint8 Bit=1<<S;
        if(P->Running&Bit)
        {
            P->Elapsed[S]+=ProphecyBlendClock::Consume(A,PoleClock(S));
            if(P->Elapsed[S]+1.e-6>=P->Duration)
            {P->Elapsed[S]=P->Duration;P->Running&=~Bit;ProphecyBlendClock::Stop(A,PoleClock(S));}
        }
        const double T=FMath::Clamp(P->Elapsed[S]/P->Duration,0.,1.);
        Alpha[S]=float(T*T*(3.-2.*T));
        if(!(Remaining&Bit)){P->Feet&=~Bit;P->Running&=~Bit;ProphecyBlendClock::Stop(A,PoleClock(S));}
    }
    if(!P->Feet)ClearPoles(A);
}
static ProphecyBlendClock::EKind HandoffClock(int32 Side)
{return Side?ProphecyBlendClock::EKind::RightAttackFootHandoff:ProphecyBlendClock::EKind::LeftAttackFootHandoff;}
static void ClearHandoff(const AProphecyAgent* A)
{
    if(Handoffs.IsEmpty() || !Handoffs.Remove(A))return;
    for(int32 S=0;S<2;++S)ProphecyBlendClock::Stop(A,HandoffClock(S));
}
static FDelegateHandle Cleanup;
static void EnsureCleanup()
{
    if(Cleanup.IsValid())return;
    Cleanup=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* W,bool,bool)
    {
        for(auto* M:{&Configs,&Baselines})for(auto It=M->CreateIterator();It;++It)
            if(!It.Key().IsValid()||It.Key()->GetWorld()==W)It.RemoveCurrent();
        for(auto It=Runs.CreateIterator();It;++It)
            if(!It.Key().IsValid()||It.Key()->GetWorld()==W)It.RemoveCurrent();
        for(auto* M:{&GhostSettings,&GhostBaselines})for(auto It=M->CreateIterator();It;++It)
            if(!It->IsValid()||It->Get()->GetWorld()==W)It.RemoveCurrent();
        for(auto It=GhostRuns.CreateIterator();It;++It)
            if(!It.Key().IsValid()||It.Key()->GetWorld()==W)It.RemoveCurrent();
        for(auto* M:{&FreezeSettings,&FreezeBaselines})for(auto It=M->CreateIterator();It;++It)
            if(!It.Key().IsValid()||It.Key()->GetWorld()==W)It.RemoveCurrent();
        for(auto It=FreezeWindows.CreateIterator();It;++It)
            if(!It.Key().IsValid()||It.Key()->GetWorld()==W)It.RemoveCurrent();
        for(auto* M:{&HandoffSettings,&HandoffBaselines})for(auto It=M->CreateIterator();It;++It)
            if(!It.Key().IsValid()||It.Key()->GetWorld()==W)It.RemoveCurrent();
        for(auto It=Handoffs.CreateIterator();It;++It)
            if(!It.Key().IsValid()||It.Key()->GetWorld()==W)It.RemoveCurrent();
        for(auto* M:{&PoleSettings,&PoleBaselines})for(auto It=M->CreateIterator();It;++It)
            if(!It.Key().IsValid()||It.Key()->GetWorld()==W)It.RemoveCurrent();
        for(auto It=PoleBlends.CreateIterator();It;++It)
            if(!It.Key().IsValid()||It.Key()->GetWorld()==W)It.RemoveCurrent();
    });
}
FRun* FindActive(const AProphecyAgent* A)
{auto* R=Runs.IsEmpty()?nullptr:Runs.Find(A);return R && R->Loco && !R->Suspended?R:nullptr;}
uint8 Mask(const AProphecyAgent* A){const auto* R=FindActive(A);return R?R->Loco:0;}
float FreezeBlend(const AProphecyAgent* A)
{const auto* V=FreezeSettings.IsEmpty()?nullptr:FreezeSettings.Find(A);return V && Mask(A)?*V:0.f;}
void CaptureFreezeWindow(const AProphecyAgent* A,const float* Encoded)
{auto& W=FreezeWindows.FindOrAdd(A);for(int32 I=0;I<8;++I){W.XY[2*I]=Encoded[4*I];W.XY[2*I+1]=Encoded[4*I+1];}}
void ClearFreezeWindow(const AProphecyAgent* A){if(!FreezeWindows.IsEmpty())FreezeWindows.Remove(A);}
const FFreezeWindow* FindFreezeWindow(const AProphecyAgent* A)
{return FreezeWindows.IsEmpty() || !Mask(A)?nullptr:FreezeWindows.Find(A);}
static bool Outside(const FConfig& C,const FVector& Foot,const FVector& Pelvis,const FVector& Axis,float Floor)
{return FVector::DotProduct(Foot-Pelvis,Axis)<-C.Distance || Foot.Z-Floor>C.Height;}
uint8 Step(FRun& R,const FVector& Pelvis,const FVector& Target,float Floor,const FVector& Left,const FVector& Right)
{
    const FVector Axis=(Target-Pelvis).GetSafeNormal2D();const uint8 Before=R.Loco;
    if((R.Loco&1) && !Outside(R.Config,Left,Pelvis,Axis,Floor))R.Loco&=~1;
    if((R.Loco&2) && !Outside(R.Config,Right,Pelvis,Axis,Floor))R.Loco&=~2;
    return Before^R.Loco;
}
uint8 Advance(const AProphecyAgent* A,FRun& R,const FVector& Pelvis,const FVector& Target,float Floor,
    const FVector& Left,const FVector& Right,float (&Position)[2],float& AlphaRotation)
{
    Position[0]=Position[1]=1;AlphaRotation=1;
    auto* H=Handoffs.IsEmpty()?nullptr:Handoffs.Find(A);
    if(!H)return Step(R,Pelvis,Target,Floor,Left,Right);
    AlphaRotation=H->Config.Rotation;
    const FVector Axis=(Target-Pelvis).GetSafeNormal2D();const FVector Feet[]={Left,Right};
    uint8 Released=0;
    for(int32 S=0;S<2;++S)
    {
        const uint8 Bit=1<<S;if(!(R.Loco&Bit))continue;
        if(!(H->Started&Bit))
        {
            if(Outside(R.Config,Feet[S],Pelvis,Axis,Floor))continue;
            if(H->Config.Duration[S]<=0){R.Loco&=~Bit;Released|=Bit;continue;}
            H->Started|=Bit;ProphecyBlendClock::Start(A,HandoffClock(S),H->Config.Duration[S]);
        }
        else H->Elapsed[S]+=ProphecyBlendClock::Consume(A,HandoffClock(S));
        const double T=FMath::Clamp(H->Elapsed[S]/H->Config.Duration[S],0.,1.);
        Position[S]=float(1.-T*T*(3.-2.*T));
        if(H->Elapsed[S]+1.e-6>=H->Config.Duration[S])
        {
            Position[S]=0;R.Loco&=~Bit;Released|=Bit;
            ProphecyBlendClock::Stop(A,HandoffClock(S));
        }
    }
    if(!R.Loco)ClearHandoff(A);
    return Released;
}
uint8 ReleaseAll(const AProphecyAgent* A)
{
    uint8 Released=0;if(auto* R=Runs.Find(A)){Released=R->Loco;R->Loco=0;}
    ClearHandoff(A);ClearFreezeWindow(A);ClearPoles(A);return Released;
}
float WalkWeight(const FRun& R,float Current)
{return R.Config.Mode==EProphecyAttackFootLocomotionMode::Walk?1.f:R.Config.Mode==EProphecyAttackFootLocomotionMode::Run?0.f:Current;}
void Begin(const AProphecyAgent* A,int32 Id,TConstArrayView<FName> Names,TConstArrayView<FTransform> Pose,const FTransform& Carrier,const FVector& Target)
{
    if(Runs.Contains(A))return; // Half/full toggles never reacquire an attack-owned foot.
    const auto* C=Configs.IsEmpty()?nullptr:Configs.Find(A);if(!C || Pose.IsEmpty())return;
    FRun R;R.Config=*C;R.PoseId=Id;R.Loco=3;
    for(int32 Side=0;Side<2;++Side)
    {
        const FName N[]={Side?TEXT("thigh_r"):TEXT("thigh_l"),Side?TEXT("calf_r"):TEXT("calf_l"),Side?TEXT("foot_r"):TEXT("foot_l"),Side?TEXT("ball_r"):TEXT("ball_l")};
        for(int32 B=0;B<4;++B){R.Legs[Side][B]=Names.IndexOfByKey(N[B]);if(!Pose.IsValidIndex(R.Legs[Side][B]))return;}
    }
    Step(R,(Pose[0]*Carrier).GetLocation(),Target,A->GetRootLowPoint().Z,
        (Pose[R.Legs[0][2]]*Carrier).GetLocation(),(Pose[R.Legs[1][2]]*Carrier).GetLocation());
    Runs.Add(A,R);
    // Feet accepted at entry never create a handoff clock or a blend.
    if(R.Loco)if(const auto* H=HandoffSettings.IsEmpty()?nullptr:HandoffSettings.Find(A))
    {FHandoff State;State.Config=*H;Handoffs.Add(A,State);}
    if(R.Loco)if(const auto* Duration=PoleSettings.IsEmpty()?nullptr:PoleSettings.Find(A))
    {
        FPoleBlend State;State.Duration=*Duration;State.Feet=State.Running=R.Loco;PoleBlends.Add(A,State);
        for(int32 S=0;S<2;++S)if(R.Loco&(1<<S))ProphecyBlendClock::Start(A,PoleClock(S),*Duration);
    }
}
void Suspend(const AProphecyAgent* A,bool Half)
{
    auto* R=Runs.Find(A);if(!R || R->Suspended==Half)return;
    if(auto* H=Handoffs.IsEmpty()?nullptr:Handoffs.Find(A))for(int32 S=0;S<2;++S)
        if((H->Started&R->Loco)&(1<<S))
        {
            if(Half){H->Elapsed[S]+=ProphecyBlendClock::Consume(A,HandoffClock(S));ProphecyBlendClock::Stop(A,HandoffClock(S));}
            else if(H->Elapsed[S]<H->Config.Duration[S])ProphecyBlendClock::Start(A,HandoffClock(S),H->Config.Duration[S]-H->Elapsed[S]);
        }
    if(auto* P=PoleBlends.IsEmpty()?nullptr:PoleBlends.Find(A))for(int32 S=0;S<2;++S)if(P->Running&(1<<S))
    {
        if(Half){P->Elapsed[S]+=ProphecyBlendClock::Consume(A,PoleClock(S));ProphecyBlendClock::Stop(A,PoleClock(S));}
        else if(P->Elapsed[S]<P->Duration)ProphecyBlendClock::Start(A,PoleClock(S),P->Duration-P->Elapsed[S]);
    }
    R->Suspended=Half;
}
void End(const AProphecyAgent* A){if(!Runs.IsEmpty())Runs.Remove(A);GhostRuns.Remove(A);ClearFreezeWindow(A);ClearHandoff(A);ClearPoles(A);}
void Remove(const AProphecyAgent* A){End(A);Configs.Remove(A);Baselines.Remove(A);FreezeSettings.Remove(A);FreezeBaselines.Remove(A);HandoffSettings.Remove(A);HandoffBaselines.Remove(A);PoleSettings.Remove(A);PoleBaselines.Remove(A);GhostSettings.Remove(A);GhostBaselines.Remove(A);}
void CaptureReset(const AProphecyAgent* A){if(const auto* C=Configs.Find(A))Baselines.Add(A,*C);else Baselines.Remove(A);
if(GhostSettings.Contains(A))GhostBaselines.Add(A);else GhostBaselines.Remove(A);
if(const auto* V=FreezeSettings.Find(A))FreezeBaselines.Add(A,*V);else FreezeBaselines.Remove(A);
if(const auto* V=HandoffSettings.Find(A))HandoffBaselines.Add(A,*V);else HandoffBaselines.Remove(A);
if(const auto* V=PoleSettings.Find(A))PoleBaselines.Add(A,*V);else PoleBaselines.Remove(A);}
void RestoreReset(const AProphecyAgent* A){End(A);Configs.Remove(A);if(const auto* C=Baselines.Find(A))Configs.Add(A,*C);
GhostSettings.Remove(A);if(GhostBaselines.Contains(A))GhostSettings.Add(A);
FreezeSettings.Remove(A);if(const auto* V=FreezeBaselines.Find(A))FreezeSettings.Add(A,*V);
HandoffSettings.Remove(A);if(const auto* V=HandoffBaselines.Find(A))HandoffSettings.Add(A,*V);
PoleSettings.Remove(A);if(const auto* V=PoleBaselines.Find(A))PoleSettings.Add(A,*V);}
void ForgetReset(const AProphecyAgent* A){Baselines.Remove(A);FreezeBaselines.Remove(A);HandoffBaselines.Remove(A);PoleBaselines.Remove(A);GhostBaselines.Remove(A);}
}
bool UProphecyAttackFootLocomotionLibrary::SetGhostLocoDrag(AProphecyAgent* A,bool Enabled)
{
    using namespace ProphecyAttackFootLocomotion;
    if(!IsInGameThread()||!IsValid(A)||A->IsActorBeingDestroyed())return false;
    EnsureCleanup();if(Enabled)GhostSettings.Add(A);else GhostSettings.Remove(A);
    return true; // Latched; never splice a different history into an ongoing attack.
}
bool UProphecyAttackFootLocomotionLibrary::ReadGhostLocoDrag(AProphecyAgent* A,TArray<FName>& Names,TArray<FTransform>& WorldPose)
{
    Names.Reset();WorldPose.Reset();
    if(!IsInGameThread()||!IsValid(A))return false;
    const auto* G=ProphecyAttackFootLocomotion::FindGhost(A);if(!G || !G->HasPose)return false;
    TArray<FName> AllNames;TArray<FTransform> Future,Presented;float Alpha=0;
    if(!A->ReadNNFutureWorldPose(AllNames,Future,Presented,Alpha))return false;
    const int32 Pelvis=AllNames.IndexOfByKey(TEXT("pelvis"));if(!Presented.IsValidIndex(Pelvis))return false;
    FTransform GhostPelvis;
    GhostPelvis.Blend(G->PreviousWorld[0],G->CurrentWorld[0],Alpha);
    Names.Add(TEXT("pelvis"));WorldPose.Add(Presented[Pelvis]);
    for(int32 S=0;S<2;++S)for(int32 B=0;B<4;++B)
    {
        const FName N[]={S?TEXT("thigh_r"):TEXT("thigh_l"),S?TEXT("calf_r"):TEXT("calf_l"),S?TEXT("foot_r"):TEXT("foot_l"),S?TEXT("ball_r"):TEXT("ball_l")};
        FTransform T;T.Blend(G->PreviousWorld[1+S*4+B],G->CurrentWorld[1+S*4+B],Alpha);
        Names.Add(N[B]);WorldPose.Add(T.GetRelativeTransform(GhostPelvis)*Presented[Pelvis]);
    }
    return true;
}
bool UProphecyAttackFootLocomotionLibrary::DrawGhostLocoDrag(AProphecyAgent* A,bool Enabled,FVector Offset,float Duration)
{
    if(!Enabled||Offset.ContainsNaN()||!FMath::IsFinite(Duration)||Duration<0)return false;
    TArray<FName> Names;TArray<FTransform> Pose;
    if(!ReadGhostLocoDrag(A,Names,Pose))return false;
    for(int32 S=0;S<2;++S)for(int32 B=0;B<4;++B)
    {
        const int32 I=1+S*4+B,P=B?I-1:0;
        DrawDebugLine(A->GetWorld(),Pose[P].GetLocation()+Offset,Pose[I].GetLocation()+Offset,FColor::Cyan,false,Duration,0,2.f);
        DrawDebugSphere(A->GetWorld(),Pose[I].GetLocation()+Offset,2.5f,8,FColor::Cyan,false,Duration,0,1.f);
    }
    return true;
}
bool UProphecyAttackFootLocomotionLibrary::SetAttackFootLocomotion(AProphecyAgent* A,bool Enabled,EProphecyAttackFootLocomotionMode Mode,float DistanceLimitCm,float HeightLimitCm,float Freeze,float AlphaRotation,float LeftDuration,float RightDuration,float PoleDuration)
{
    using namespace ProphecyAttackFootLocomotion;
    if(!IsInGameThread()||!IsValid(A)||A->IsActorBeingDestroyed()||!FMath::IsFinite(DistanceLimitCm)||!FMath::IsFinite(HeightLimitCm)
        ||!FMath::IsFinite(Freeze)||DistanceLimitCm<0||HeightLimitCm<0||uint8(Mode)>uint8(EProphecyAttackFootLocomotionMode::CurrentBlend)
        ||!FMath::IsFinite(AlphaRotation)||!FMath::IsFinite(LeftDuration)||!FMath::IsFinite(RightDuration)||LeftDuration<0||RightDuration<0
        ||!FMath::IsFinite(PoleDuration)||PoleDuration<0)return false;
    if(!Enabled)
    {
        if(auto* R=FindActive(A))ProphecyAttackStartInertia::BeginFeet(A,R->PoseId,R->Loco);
        ReleaseAll(A); // Keep completed ownership across half/full toggles.
        Configs.Remove(A);FreezeSettings.Remove(A);HandoffSettings.Remove(A);PoleSettings.Remove(A);return true;
    }
    EnsureCleanup();Configs.Add(A,{Mode,DistanceLimitCm,HeightLimitCm});
    if(Freeze>0)FreezeSettings.Add(A,FMath::Clamp(Freeze,0.f,1.f));else FreezeSettings.Remove(A);
    AlphaRotation=FMath::Clamp(AlphaRotation,0.f,1.f);
    if(AlphaRotation!=1 || LeftDuration>0 || RightDuration>0)HandoffSettings.Add(A,{AlphaRotation,{LeftDuration,RightDuration}});
    else HandoffSettings.Remove(A);
    if(PoleDuration>0)PoleSettings.Add(A,PoleDuration);else PoleSettings.Remove(A);
    return true;
}
void UProphecyAttackFootLocomotionLibrary::GetAttackFootLocomotion(AProphecyAgent* A,bool& Left,bool& Right)
{const uint8 M=ProphecyAttackFootLocomotion::Mask(A);Left=(M&1)!=0;Right=(M&2)!=0;}
void UProphecyAttackFootLocomotionLibrary::DrawAttackFootLocomotion(AProphecyAgent* A,float Duration)
{
    using namespace ProphecyAttackFootLocomotion;
    if(!IsValid(A)||!A->GetWorld()||!FMath::IsFinite(Duration)||Duration<0)return;
    const auto* R=Runs.Find(A);if(!R||R->Suspended)return;
    FTransform P,F[2];FVector Target,Effective,Ghost;
    if(!A->GetNNAttackTarget(Target,Effective,Ghost)||!ProphecyNNPresentation::ReadPelvisWorld(R->PoseId,P))return;
    const FVector Axis=(Target-P.GetLocation()).GetSafeNormal2D(),Side=FVector::CrossProduct(FVector::UpVector,Axis);
    const float Floor=A->GetRootLowPoint().Z;FVector Center=P.GetLocation();Center.Z=Floor;
    const FVector Along=Axis*R->Config.Distance,Across=Side*40,Up(0,0,R->Config.Height);
    const FVector Rear=Center-Along,Front=Center+Axis*FMath::Max(40.f,R->Config.Distance);
    DrawDebugLine(A->GetWorld(),Rear-Across,Rear+Across,FColor::Yellow,false,Duration,0,1.5);
    DrawDebugLine(A->GetWorld(),Rear-Across+Up,Rear+Across+Up,FColor::White,false,Duration,0,1);
    DrawDebugLine(A->GetWorld(),Front-Across+Up,Front+Across+Up,FColor::White,false,Duration,0,1);
    for(float S:{-1.f,1.f})
    {
        DrawDebugLine(A->GetWorld(),Rear+Across*S,Rear+Across*S+Up,FColor::Yellow,false,Duration,0,1);
        DrawDebugLine(A->GetWorld(),Rear+Across*S+Up,Front+Across*S+Up,FColor::White,false,Duration,0,1);
    }
    DrawDebugLine(A->GetWorld(),Rear,Center,FColor::Yellow,false,Duration,0,1);
    DrawDebugDirectionalArrow(A->GetWorld(),Center,Front,10,FColor::Green,false,Duration,0,1.5);
    DrawDebugString(A->GetWorld(),Front,TEXT("Forward: no distance limit"),nullptr,FColor::Green,Duration,true);
    for(int32 S=0;S<2;++S)if(ProphecyNNPresentation::ReadBoneWorld(R->PoseId,S?TEXT("foot_r"):TEXT("foot_l"),F[S]))
    {
        const bool Loco=(R->Loco&(1<<S))!=0;
        const auto* H=Handoffs.IsEmpty()?nullptr:Handoffs.Find(A);
        const bool Blending=Loco && H && (H->Started&(1<<S));
        const FColor Color=Blending?FColor::Orange:Loco?FColor::Cyan:FColor::Red;
        DrawDebugSphere(A->GetWorld(),F[S].GetLocation(),4,8,Color,false,Duration,0,1);
        DrawDebugString(A->GetWorld(),F[S].GetLocation()+FVector(0,0,8),FString::Printf(TEXT("%s: %s"),S?TEXT("R"):TEXT("L"),Blending?TEXT("LOCO -> ATTACK"):Loco?TEXT("LOCO"):TEXT("ATTACK")),nullptr,Color,Duration,true);
    }
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "HAL/IConsoleManager.h"
#include "GameFramework/PlayerController.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyGhostLocoLifecycle,"Prophecy.NN.GhostLocoDrag.Lifecycle",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyGhostLocoLifecycle::RunTest(const FString&)
{
    using namespace ProphecyAttackFootLocomotion;
    using L=UProphecyAttackFootLocomotionLibrary;
    UWorld* W=UWorld::CreateWorld(EWorldType::Editor,false);auto* A=W?W->SpawnActor<AProphecyAgent>():nullptr;
    if(!A)return false;
    FRun R;R.Loco=3;for(int32 S=0;S<2;++S)for(int32 B=0;B<4;++B)R.Legs[S][B]=1+4*S+B;
    Runs.Add(A,R);FTransform Pose[9];float State[82];for(int32 I=0;I<82;++I)State[I]=float(I);
    BeginGhost(A,State,MakeArrayView(Pose),FTransform::Identity);
    TestNull(TEXT("Disabled mode allocates no ghost"),FindGhost(A));
    L::SetGhostLocoDrag(A,true);CaptureReset(A);
    BeginGhost(A,State,MakeArrayView(Pose),FTransform::Identity);
    auto* G=FindGhost(A);if(!TestNotNull(TEXT("Enabled entry creates separate history"),G))return false;
    TestTrue(TEXT("Both actual leg histories seed exactly"),FMemory::Memcmp(G->PreviousLegs,State+9,32*sizeof(float))==0 && FMemory::Memcmp(G->CurrentLegs,State+50,32*sizeof(float))==0);
    G->CurrentLegs[0]=1234;TestEqual(TEXT("Real feedback cannot overwrite ghost state"),State[50],50.f);
    L::SetGhostLocoDrag(A,false);TestNotNull(TEXT("Option change latches next attack"),FindGhost(A));
    Suspend(A,true);TestNull(TEXT("Half mode performs no extra lower work"),FindGhost(A));
    Suspend(A,false);TestNotNull(TEXT("Full mode resumes its branch"),FindGhost(A));
    ReleaseAll(A);TestNotNull(TEXT("Real branch survives final foot handoff"),FindGhost(A));
    CancelGhost(A,State);TestNull(TEXT("Kick switch cancels ghost"),FindGhost(A));
    TestEqual(TEXT("Cancellation seeds real leg history"),State[50],1234.f);
    TestEqual(TEXT("Cancellation preserves pelvis history"),State[41],41.f);
    RestoreReset(A);TestTrue(TEXT("Reset restores enabled configuration"),GhostSettings.Contains(A));
    TestNull(TEXT("Reset retires prediction state"),FindGhost(A));
    Remove(A);TestFalse(TEXT("Removal clears config"),GhostSettings.Contains(A));
    TestFalse(TEXT("Removal clears baseline"),GhostBaselines.Contains(A));W->DestroyWorld(false);
    return !HasAnyErrors();
}
// Development capture bridge for new enums whose Python wrappers are unavailable
// until an editor restart after Live Coding. Only acts on the supplied PIE world.
static FAutoConsoleCommandWithWorldAndArgs GTestFootAuthoring(
    TEXT("Prophecy.Test.AttackFootLocomotion"),TEXT("PIE player: enabled mode distance height"),
    FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args,UWorld* W)
    {
        if(!W || W->WorldType!=EWorldType::PIE || Args.Num()!=4)return;
        auto* PC=W->GetFirstPlayerController();auto* A=PC?Cast<AProphecyAgent>(PC->GetPawn()):nullptr;
        UProphecyAttackFootLocomotionLibrary::SetAttackFootLocomotion(A,FCString::Atoi(*Args[0])!=0,
            EProphecyAttackFootLocomotionMode(FCString::Atoi(*Args[1])),FCString::Atof(*Args[2]),FCString::Atof(*Args[3]));
    }));
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyAttackFootAuthoringTest,"Prophecy.NN.AttackEntry.FootLocomotion",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyAttackFootAuthoringTest::RunTest(const FString&)
{
    using namespace ProphecyAttackFootLocomotion;
    FRun R;R.Config={EProphecyAttackFootLocomotionMode::CurrentBlend,40,15};R.Loco=3;
    const FVector Pelvis(0,0,90),Target(100,0,90);
    TestEqual(TEXT("Distance OR height keeps locomotion"),Step(R,Pelvis,Target,0,FVector(-41,0,10),FVector(0,0,16)),uint8(0));
    TestEqual(TEXT("Boundary inclusive; lateral offset is not 1D distance"),Step(R,Pelvis,Target,0,FVector(-40,300,15),FVector(0,0,16)),uint8(1));
    TestEqual(TEXT("Left cannot reacquire after moving far away"),Step(R,Pelvis,Target,0,FVector(-400,0,90),FVector(10,0,10)),uint8(2));
    TestEqual(TEXT("Both attack feet stop requesting locomotion"),R.Loco,uint8(0));
    for(int32 I=0;I<100;++I)Step(R,Pelvis,FVector(-I*100,200,50),0,FVector(1000,0,300),FVector(-1000,0,300));
    TestEqual(TEXT("Retargets cannot undo completed latches"),R.Loco,uint8(0));
    R.Loco=3;
    TestEqual(TEXT("Height still applies far forward"),Step(R,Pelvis,Target,0,FVector(1000,0,16),FVector(-41,0,10)),uint8(0));
    TestEqual(TEXT("Forward distance is unrestricted at accepted height"),Step(R,Pelvis,Target,0,FVector(1000,0,15),FVector(-41,0,10)),uint8(1));
    TestEqual(TEXT("Backward follows retargeted axis"),Step(R,Pelvis,-Target,0,FVector(-1000,0,10),FVector(41,0,10)),uint8(0));
    TestEqual(TEXT("Rear boundary is inclusive on reversed axis"),Step(R,Pelvis,-Target,0,FVector(-1000,0,10),FVector(40,0,10)),uint8(2));
    TestEqual(TEXT("Current blend retains fractional mix"),WalkWeight(R,.35f),.35f);
    R.Config.Mode=EProphecyAttackFootLocomotionMode::Walk;TestEqual(TEXT("Walk chooses only Walk"),WalkWeight(R,.35f),1.f);
    R.Config.Mode=EProphecyAttackFootLocomotionMode::Run;TestEqual(TEXT("Run chooses only Run"),WalkWeight(R,.35f),0.f);
    UWorld* W=UWorld::CreateWorld(EWorldType::Editor,false);AProphecyAgent* A=W?W->SpawnActor<AProphecyAgent>():nullptr;if(!A)return false;
    using L=UProphecyAttackFootLocomotionLibrary;
    TestTrue(TEXT("Opt in accepts finite limits"),L::SetAttackFootLocomotion(A,true,EProphecyAttackFootLocomotionMode::Walk,40,15));
    TestNull(TEXT("Configured idle agents do no authoring work"),FindActive(A));
    R.Loco=2;R.Suspended=false;Runs.Add(A,R);
    Suspend(A,true);TestEqual(TEXT("Half mode has no extra foot policy request"),Mask(A),uint8(0));
    Suspend(A,false);TestEqual(TEXT("Full rejoin preserves one-way progress"),Mask(A),uint8(2));
    CaptureReset(A);RestoreReset(A);TestNull(TEXT("Reset removes transient ownership"),FindActive(A));
    TestTrue(TEXT("Reset retains config"),Configs.Contains(A));
    L::SetAttackFootLocomotion(A,false,EProphecyAttackFootLocomotionMode::Walk,40,15);
    TestFalse(TEXT("Disable retains no config"),Configs.Contains(A));
    TestEqual(TEXT("Disable has no active authoring"),Mask(A),uint8(0));
    Remove(A);W->DestroyWorld(false);return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyFootHandoffTest,"Prophecy.NN.AttackEntry.FootLocomotionHandoff",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyFootHandoffTest::RunTest(const FString&)
{
    using namespace ProphecyAttackFootLocomotion;
    using L=UProphecyAttackFootLocomotionLibrary;
    UWorld* W=UWorld::CreateWorld(EWorldType::Editor,false);auto* A=W?W->SpawnActor<AProphecyAgent>():nullptr;
    if(!A)return false;
    const FVector Pelvis(0,0,90),Target(100,0,90),Inside(0,0,10),Outside(-50,0,20);
    const FName Names[]={TEXT("pelvis"),TEXT("thigh_l"),TEXT("calf_l"),TEXT("foot_l"),TEXT("ball_l"),TEXT("thigh_r"),TEXT("calf_r"),TEXT("foot_r"),TEXT("ball_r")};
    FTransform Pose[9];for(auto& T:Pose)T=FTransform(FVector(0,0,A->GetRootLowPoint().Z+10));
    L::SetAttackFootLocomotion(A,true,EProphecyAttackFootLocomotionMode::Run,40,15,0,.25f,.1f,.2f);
    Begin(A,INDEX_NONE,MakeArrayView(Names),MakeArrayView(Pose),FTransform::Identity,Target);
    TestEqual(TEXT("Feet starting at attack bypass duration"),Mask(A),uint8(0));
    TestFalse(TEXT("Direct attack creates no handoff state"),Handoffs.Contains(A));End(A);
    for(float FPS:{30.f,60.f,120.f})
    {
        FRun R;R.Config={EProphecyAttackFootLocomotionMode::Run,40,15};R.Loco=3;Runs.Add(A,R);
        FHandoff H;H.Config=HandoffSettings.FindChecked(A);Handoffs.Add(A,H);
        auto Tick=[&](int32 Count){for(int32 I=0;I<Count;++I)FWorldDelegates::OnWorldPreActorTick.Broadcast(W,LEVELTICK_All,1.f/FPS);};
        float Pos[2],Rot;auto Sample=[&](const FVector& Left,const FVector& Right)
        {return Advance(A,Runs.FindChecked(A),Pelvis,Target,0,Left,Right,Pos,Rot);};
        TestEqual(TEXT("Threshold starts left blend without releasing"),Sample(Inside,Outside),uint8(0));
        TestEqual(TEXT("Rotation alpha latches"),Rot,.25f);TestEqual(TEXT("Blend starts fully loco"),Pos[0],1.f);
        Tick(3);Sample(Outside,Inside);
        TestTrue(TEXT("Left half finished; right starts independently"),FMath::IsNearlyEqual(Pos[0],.5f) && Pos[1]==1);
        Sample(Outside,Outside);TestTrue(TEXT("Duplicate sample does not advance clock"),FMath::IsNearlyEqual(Pos[0],.5f));
        Suspend(A,true);Tick(60);TestEqual(TEXT("Half mode suspends extra inference"),Mask(A),uint8(0));
        Suspend(A,false);Sample(Outside,Outside);TestTrue(TEXT("Half mode pauses both fades"),FMath::IsNearlyEqual(Pos[0],.5f) && Pos[1]==1);
        FWorldDelegates::OnWorldPreActorTick.Broadcast(W,LEVELTICK_PauseTick,1.f/FPS);
        Sample(Outside,Outside);TestTrue(TEXT("Paused tick does not advance fade"),FMath::IsNearlyEqual(Pos[0],.5f));
        Tick(3);TestEqual(TEXT("Only left completes at six ticks"),Sample(Outside,Outside),uint8(1));
        TestTrue(TEXT("Right retains its own clock"),Pos[0]==0 && FMath::IsNearlyEqual(Pos[1],.84375f));
        TestEqual(TEXT("Pending right keeps lower inference"),Mask(A),uint8(2));
        Tick(9);TestEqual(TEXT("Right completes twelve ticks after its own start"),Sample(Outside,Outside),uint8(2));
        TestEqual(TEXT("Last completion removes lower request"),Mask(A),uint8(0));
        TestFalse(TEXT("Completed handoff has no runtime state"),Handoffs.Contains(A));
        for(int32 S=0;S<2;++S)TestEqual(TEXT("Completed clocks removed"),ProphecyBlendClock::Consume(A,HandoffClock(S)),0.);
        End(A);
    }
    FRun R;R.Config={EProphecyAttackFootLocomotionMode::Run,40,15};R.Loco=3;Runs.Add(A,R);
    FHandoff H;H.Config=HandoffSettings.FindChecked(A);Handoffs.Add(A,H);float Pos[2],Rot;
    Advance(A,Runs.FindChecked(A),Pelvis,Target,0,Inside,Outside,Pos,Rot);
    TestEqual(TEXT("Explicit release cancels pending and blending feet"),ReleaseAll(A),uint8(3));
    TestFalse(TEXT("Release clears handoff state"),Handoffs.Contains(A));
    CaptureReset(A);RestoreReset(A);TestTrue(TEXT("Reset preserves new config"),HandoffSettings.Contains(A));
    L::SetAttackFootLocomotion(A,true,EProphecyAttackFootLocomotionMode::Run,40,15);
    TestFalse(TEXT("Default values keep no extra config"),HandoffSettings.Contains(A));
    R.Loco=3;TestEqual(TEXT("Zero duration retains immediate handoff"),Advance(A,R,Pelvis,Target,0,Inside,Outside,Pos,Rot),uint8(1));
    TestTrue(TEXT("Zero duration keeps final feedback sample"),Pos[0]==1 && Rot==1);
    TestFalse(TEXT("Invalid duration rejected"),L::SetAttackFootLocomotion(A,true,EProphecyAttackFootLocomotionMode::Run,40,15,0,1,-1,0));

    FTransform Attack[4]={FTransform(FVector(0,0,80)),FTransform(FVector(20,0,45)),FTransform(FVector(0,0,10)),FTransform(FVector(12,0,10))};
    FTransform Loco[4];for(int32 B=0;B<4;++B)Loco[B]=Attack[B];
    Loco[2].SetLocation(FVector(15,0,15));Loco[2].SetRotation(FRotator(10,60,5).Quaternion());
    Loco[3]=FTransform(FVector(12,0,0))*Loco[2];
    for(float Weight:{0.f,.25f,.5f,.75f,1.f})for(float Alpha:{0.f,.5f,1.f})
    {
        FTransform Result[4];for(int32 B=0;B<4;++B)Result[B]=Attack[B];
        AuthorLeg(Result,Loco,Weight,Alpha);
        const FQuat Expected=FQuat::Slerp(Attack[2].GetRotation(),Loco[2].GetRotation(),Weight*Alpha).GetNormalized();
        TestTrue(TEXT("Foot rotation matches requested source contribution"),Result[2].GetRotation().Equals(Expected,1.e-6));
        TestTrue(TEXT("Hip remains attached"),Result[0].GetLocation().Equals(Attack[0].GetLocation(),1.e-6));
        TestTrue(TEXT("Ankle blends between reachable endpoints"),Result[2].GetLocation().Equals(FMath::Lerp(Attack[2].GetLocation(),Loco[2].GetLocation(),double(Weight)),1.e-5));
        for(int32 B=0;B<2;++B)
        {
            const double Length=FMath::Lerp((Attack[B+1].GetLocation()-Attack[B].GetLocation()).Length(),(Loco[B+1].GetLocation()-Loco[B].GetLocation()).Length(),double(Weight));
            TestTrue(TEXT("Segment length stays connected through fade"),FMath::IsNearlyEqual((Result[B+1].GetLocation()-Result[B].GetLocation()).Length(),Length,1.e-5));
        }
        for(const auto& T:Result)TestFalse(TEXT("Finite blended leg"),T.ContainsNaN());
    }
    Remove(A);W->DestroyWorld(false);return !HasAnyErrors();
}
#include "ProphecyAttackFootPoleTests.inl"
#endif
