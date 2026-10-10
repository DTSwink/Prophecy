#include "ProphecyGetUpLibrary.h"
#include "ProphecyGetUp.h"
#include "ProphecyCoreTempering.h"
#include "ProphecyAgent.h"
#include "ProphecyNNLocomotionManager.h"
#include "ProphecyBlendClock.h"
#include "ProphecyPhysicalContext.h"
#include "ProphecyPhysicalProfileLibrary.h"
#include "Animation/AnimSequence.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#if WITH_EDITOR
#include "HAL/IConsoleManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#endif

namespace ProphecyGetUp
{
static TMap<TWeakObjectPtr<const AProphecyAgent>,FProfile> Profiles;
static TMap<TWeakObjectPtr<const AProphecyAgent>,FActive> Active;
static TSet<TWeakObjectPtr<const AProphecyAgent>> BeforeLowerHandoff;
static void ArmWindow(const AProphecyAgent* A,bool Enabled)
{
    // Event-only reflected bridge avoids a new Live Coding cross-DLL import.
    struct FParams { AActor* Agent;bool Active; } Params{const_cast<AProphecyAgent*>(A),Enabled};
    auto* Library=FindObjectChecked<UClass>(nullptr,TEXT("/Script/ProphecyJolt.ProphecyJoltBodyDriveLibrary"))->GetDefaultObject();
    Library->ProcessEvent(Library->FindFunctionChecked(TEXT("NotifyArmsAntiJiggleGetUpWindow")),&Params);
}
static void ReleaseLowerWindow(const AProphecyAgent* A)
{
    if (!BeforeLowerHandoff.Remove(A)) return;
    ArmWindow(A,false);
    UProphecyPhysicalProfileLibrary::SetMagnetizationMode(const_cast<AProphecyAgent*>(A),1);
}
static void UpdateLowerWindow(const AProphecyAgent* A,const FActive& S)
{
    if (S.Elapsed+1.e-8>=S.Profile.Entry+S.ClipDuration*S.Profile.LowerStart) ReleaseLowerWindow(A);
}
static FDelegateHandle Cleanup;
static void Refresh()
{
    if(Profiles.IsEmpty() && Active.IsEmpty())
    { FWorldDelegates::OnWorldCleanup.Remove(Cleanup);Cleanup.Reset(); }
    else if(!Cleanup.IsValid()) Cleanup=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* W,bool,bool)
    {
        auto Clean=[W](auto& Map){for(auto It=Map.CreateIterator();It;++It)
            if(!It.Key().IsValid() || It.Key()->GetWorld()==W)It.RemoveCurrent();};
        for(auto It=BeforeLowerHandoff.CreateIterator();It;++It)
            if(!It->IsValid() || It->Get()->GetWorld()==W)It.RemoveCurrent();
        Clean(Profiles);Clean(Active);Refresh();
    });
}
static bool Valid(AProphecyAgent* A)
{ return IsInGameThread() && IsValid(A) && !A->IsActorBeingDestroyed() && A->GetWorld() && !A->GetWorld()->bIsTearingDown; }
static bool Unit(float V) { return FMath::IsFinite(V) && V>=0 && V<=1; }
static bool Time(float V) { return FMath::IsFinite(V) && V>=0; }
static bool ValidCurve(EProphecyGetUpInterpolation V) { return uint8(V)<=uint8(EProphecyGetUpInterpolation::SmootherStep); }
static FProfile& Edit(const AProphecyAgent* A) { auto& P=Profiles.FindOrAdd(A);Refresh();return P; }
FProfile Configured(const AProphecyAgent* A) { const auto* P=Profiles.Find(A);return P?*P:FProfile{}; }
FActive* Find(const AProphecyAgent* A) { return Active.IsEmpty()?nullptr:Active.Find(A); }
bool IsActive(const AProphecyAgent* A) { return Find(A)!=nullptr; }
bool FreezeInference(const AProphecyAgent* A)
{
    const auto* S=Find(A);
    return S && S->Elapsed+1.e-8<S->Profile.Entry+S->ClipDuration*FMath::Min(S->Profile.LowerStart,S->Profile.UpperStart);
}
bool OwnsLower(const AProphecyAgent* A)
{ const auto* S=Find(A);return S && (S->FeetAlpha<1 || S->PelvisAlpha<1); }
float Curve(float X,EProphecyGetUpInterpolation Type)
{
    X=FMath::Clamp(X,0.f,1.f);
    if(Type==EProphecyGetUpInterpolation::Linear)return X;
    return Type==EProphecyGetUpInterpolation::SmootherStep ? X*X*X*(X*(X*6-15)+10) : X*X*(3-2*X);
}
float Progress(double Elapsed,const FTiming& T,EProphecyGetUpInterpolation Type)
{ return Elapsed+1.e-8<T.Hold?0.f:T.Duration<=0?1.f:Curve(float((Elapsed-T.Hold)/T.Duration),Type); }
void SampleTiming(FActive& S)
{
    const auto& P=S.Profile;
    S.Playback=float(FMath::Clamp(S.Elapsed-P.Entry,0.,S.ClipDuration)*S.Rate);
    const double L=S.Elapsed-P.Entry-S.ClipDuration*P.LowerStart,U=S.Elapsed-P.Entry-S.ClipDuration*P.UpperStart;
    S.FeetAlpha=Progress(L,P.Feet,P.HandoffCurve);S.PelvisAlpha=Progress(L,P.Pelvis,P.HandoffCurve);
    S.CoreAlpha=Progress(U,P.CoreTime,P.HandoffCurve);
    S.Lower=P.Lower;
    auto Mix=[](float V,float Alpha){return FMath::Lerp(V,1.f,Alpha);};
    S.Lower.FeetTranslation=Mix(P.Lower.FeetTranslation,S.FeetAlpha);
    S.Lower.FeetTranslationZ=Mix(P.Lower.FeetTranslationZ,S.FeetAlpha);
    S.Lower.FeetRotation=Mix(P.Lower.FeetRotation,S.FeetAlpha);
    S.Lower.PelvisTranslation=Mix(P.Lower.PelvisTranslation,S.PelvisAlpha);
    S.Lower.PelvisTranslationZ=Mix(P.Lower.PelvisTranslationZ,S.PelvisAlpha);
    S.Lower.PelvisRotation=Mix(P.Lower.PelvisRotation,S.PelvisAlpha);
    // Tempering belongs to locomotion handoff, never the initial floor pose.
    if(L<0)S.Lower={};
    for(int32 I=0;I<2;++I)
    {
        S.HandAlpha[I]=Progress(U,P.Hand[I],P.HandoffCurve);
        const auto& H=P.Hands.Hand[I];const float T=S.HandAlpha[I];
        S.Hands.Hand[I]=U<0?ProphecyHandRecovery::FFollow{}:ProphecyHandRecovery::FFollow{Mix(H.XY,T),Mix(H.Z,T),Mix(H.Rotation,T)};
    }
    S.Core=U<0?1.f:Mix(P.Core,S.CoreAlpha);
    S.Finished=S.FeetAlpha>=1 && S.PelvisAlpha>=1 && S.CoreAlpha>=1 && S.HandAlpha[0]>=1 && S.HandAlpha[1]>=1;
}
void Install(const AProphecyAgent* A,FActive&& S)
{
    Cancel(A);SampleTiming(S);
    const auto& P=S.Profile;
    const double LowerEnd=P.Entry+S.ClipDuration*P.LowerStart+FMath::Max(P.Feet.Hold+P.Feet.Duration,P.Pelvis.Hold+P.Pelvis.Duration);
    const double UpperEnd=P.Entry+S.ClipDuration*P.UpperStart+FMath::Max3(P.Hand[0].Hold+P.Hand[0].Duration,P.Hand[1].Hold+P.Hand[1].Duration,P.CoreTime.Hold+P.CoreTime.Duration);
    ProphecyBlendClock::Start(A,ProphecyBlendClock::EKind::GetUp,FMath::Max(1./60.,FMath::Max(LowerEnd,UpperEnd)));
    Active.Add(A,MoveTemp(S));Refresh();
    ProphecyPhysicalContext::RestoreSnapshotPhysicalMaterial(const_cast<AProphecyAgent*>(A),TEXT("1"));
    UProphecyPhysicalProfileLibrary::SetMagnetizationMode(const_cast<AProphecyAgent*>(A),0);
    BeforeLowerHandoff.Add(A);ArmWindow(A,true);
    UpdateLowerWindow(A,Active.FindChecked(A));
}
void Advance(const AProphecyAgent* A)
{
    auto* S=Find(A);if(!S)return;
    if(S->Finished && S->Published){Cancel(A);return;}
    S->Elapsed+=ProphecyBlendClock::Consume(A,ProphecyBlendClock::EKind::GetUp);SampleTiming(*S);UpdateLowerWindow(A,*S);
}
void Cancel(const AProphecyAgent* A)
{ if(Active.Remove(A)){ReleaseLowerWindow(A);ProphecyBlendClock::Stop(A,ProphecyBlendClock::EKind::GetUp);Refresh();} }
void Remove(const AProphecyAgent* A) { Cancel(A);Profiles.Remove(A);Refresh(); }
const ProphecyLowerTempering::FSettings* Lower(const AProphecyAgent* A)
{ auto* S=Find(A);return S && !S->Lower.IsIdentity()?&S->Lower:nullptr; }
const ProphecyHandRecovery::FTempering* Hands(const AProphecyAgent* A)
{ auto* S=Find(A);return S && !S->Hands.Normal()?&S->Hands:nullptr; }
float Core(const AProphecyAgent* A) { auto* S=Find(A);return S?S->Core:1.f; }
#if WITH_EDITOR
static FAutoConsoleCommandWithWorld InspectCommand(TEXT("Prophecy.GetUp.Inspect"),TEXT("Write active get-up timing; no simulation changes."),
    FConsoleCommandWithWorldDelegate::CreateLambda([](UWorld* W)
    {
        FString Rows;
        for(TActorIterator<AProphecyAgent> It(W);It;++It)
        {
            const auto* S=Find(*It);
            Rows+=FString::Printf(TEXT("%s active=%d"),*It->GetName(),S?1:0);
            if(S)Rows+=FString::Printf(TEXT(" clip=%s time=%.6f playback=%.6f feet=%.6f pelvis=%.6f left=%.6f right=%.6f core=%.6f frozen=%d finished=%d"),
                *GetNameSafe(S->Animation.Get()),S->Elapsed,S->Playback,S->FeetAlpha,S->PelvisAlpha,S->HandAlpha[0],S->HandAlpha[1],S->CoreAlpha,FreezeInference(*It),S->Finished);
            Rows+=FString::Printf(TEXT(" lower_window=%d mode=%.3f"),BeforeLowerHandoff.Contains(*It),ProphecyPhysicalContext::MagnetizationMode(*It));
            Rows+=TEXT("\n");
        }
        FFileHelper::SaveStringToFile(Rows,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/GetUp-Inspect.txt")));
    }));
#endif
}

bool UProphecyGetUpLibrary::GetUp(AProphecyAgent* A,float Rate)
{
    if(!ProphecyGetUp::Valid(A) || !FMath::IsFinite(Rate) || Rate<=0)return false;
    for(TActorIterator<AProphecyNNLocomotionManager> It(A->GetWorld());It;++It)
        if(It->ResolveAgent(A->GetAgentHandle())==A)return It->StartAgentGetUp(A->GetAgentHandle(),Rate);
    return false;
}
bool UProphecyGetUpLibrary::GetUpProfile(AProphecyAgent* A,float Entry,EProphecyGetUpInterpolation EntryCurve,
    EProphecyGetUpInterpolation HandoffCurve,float Magnetization,UAnimSequence* Front,UAnimSequence* Back,FName Snapshot,float Offset)
{
    using namespace ProphecyGetUp;
    if(!Valid(A) || !Time(Entry) || !Time(Magnetization) || !ValidCurve(EntryCurve) || !ValidCurve(HandoffCurve) || !FMath::IsFinite(Offset))return false;
    auto& P=Edit(A);P.Entry=Entry;P.EntryCurve=EntryCurve;P.HandoffCurve=HandoffCurve;
    P.Magnetization=Magnetization;P.Front=Front;P.Back=Back;P.Snapshot=Snapshot;P.GroundOffset=Offset;return true;
}
bool UProphecyGetUpLibrary::SetGetUpLowerbodyTempering(AProphecyAgent* A,bool Enabled,float Alpha,float FX,float FZ,float FR,float PX,float PZ,float PR)
{
    using namespace ProphecyGetUp;
    if(!Valid(A))return false;for(float V:{Alpha,FX,FZ,FR,PX,PZ,PR})if(!Unit(V))return false;
    auto& P=Edit(A);P.LowerStart=Alpha;P.Lower=Enabled?ProphecyLowerTempering::FSettings(FX,FR,PX,PR,FZ,PZ):ProphecyLowerTempering::FSettings{};return true;
}
bool UProphecyGetUpLibrary::BlendGetUpLowerbodyTempering(AProphecyAgent* A,float FD,float FH,float PD,float PH)
{
    using namespace ProphecyGetUp;
    if(!Valid(A))return false;for(float V:{FD,FH,PD,PH})if(!Time(V))return false;
    auto& P=Edit(A);P.Feet={FH,FD};P.Pelvis={PH,PD};return true;
}
bool UProphecyGetUpLibrary::SetGetUpUpperbodyTempering(AProphecyAgent* A,bool Enabled,float Alpha,float LX,float LZ,float LR,float RX,float RZ,float RR,float Core)
{
    using namespace ProphecyGetUp;
    if(!Valid(A))return false;for(float V:{Alpha,LX,LZ,LR,RX,RZ,RR,Core})if(!Unit(V))return false;
    auto& P=Edit(A);P.UpperStart=Alpha;P.Hands.Hand[0]=Enabled?ProphecyHandRecovery::FFollow{LX,LZ,LR}:ProphecyHandRecovery::FFollow{};
    P.Hands.Hand[1]=Enabled?ProphecyHandRecovery::FFollow{RX,RZ,RR}:ProphecyHandRecovery::FFollow{};P.Core=Enabled?Core:1;return true;
}
bool UProphecyGetUpLibrary::BlendGetUpUpperbodyTempering(AProphecyAgent* A,float LH,float LD,float RH,float RD,float CH,float CD)
{
    using namespace ProphecyGetUp;
    if(!Valid(A))return false;for(float V:{LH,LD,RH,RD,CH,CD})if(!Time(V))return false;
    auto& P=Edit(A);P.Hand[0]={LH,LD};P.Hand[1]={RH,RD};P.CoreTime={CH,CD};return true;
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "ProphecyLowerTemperingLibrary.h"
#include "ProphecyHandRecoveryLibrary.h"
#include "ProphecyCoreTemperingLibrary.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyGetUpTimingTest,"Prophecy.GetUp.TimingAndIsolation",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyGetUpTimingTest::RunTest(const FString&)
{
    using namespace ProphecyGetUp;using L=UProphecyGetUpLibrary;
    UWorld* W=UWorld::CreateWorld(EWorldType::Editor,false);auto* A=W?W->SpawnActor<AProphecyAgent>():nullptr;if(!A)return false;
    UProphecyLowerTemperingLibrary::SetLocomotionLowerBodyTempering(A,true,.17f);
    UProphecyHandRecoveryLibrary::SetLocomotionHandTempering(A,true,.23f);
    UProphecyCoreTemperingLibrary::SetLocomotionFKCoreTempering(A,true,.31f);
    L::SetGetUpLowerbodyTempering(A,true,.5f,0,0,0,0,0,0);
    L::SetGetUpUpperbodyTempering(A,true,1,0,0,0,0,0,0,0);
    L::BlendGetUpLowerbodyTempering(A,.5f,.25f,1,0);
    L::BlendGetUpUpperbodyTempering(A,0,.5f,.25f,.5f,0,1);
    TestFalse(TEXT("Configuration never starts active work"),IsActive(A));
    TestEqual(TEXT("Regular lower settings preserved"),ProphecyLowerTempering::Find(A)->FeetTranslation,.17f);
    TestEqual(TEXT("Regular hands preserved"),ProphecyHandRecovery::Tempering(A)->Hand[0].XY,.23f);
    TestEqual(TEXT("Regular core preserved"),ProphecyCoreTempering::Rotation(A),.31f);
    for(float FPS:{5.f,30.f,60.f,120.f})
    {
        FActive S;S.Profile=Configured(A);S.Profile.Entry=0;S.ClipDuration=2;S.Rate=2;Install(A,MoveTemp(S));
        TestEqual(TEXT("Entry snaps local mode"),ProphecyPhysicalContext::MagnetizationMode(A),0.f);
        TestTrue(TEXT("Entry owns arm window"),BeforeLowerHandoff.Contains(A));
        for(int32 Tick=1;Tick<=180;++Tick)
        {
            FWorldDelegates::OnWorldPreActorTick.Broadcast(W,LEVELTICK_All,1.f/FPS);Advance(A);
            auto* V=Find(A);if(!V){AddError(TEXT("State retired before its endpoint publication"));break;}
            const double T=V->Elapsed;Advance(A);TestEqual(TEXT("Duplicate samples spend no tick"),V->Elapsed,T);
            if(Tick==30){TestTrue(TEXT("No inference before either handoff"),FreezeInference(A));TestEqual(TEXT("Rate affects playback"),V->Playback,1.f);}
            if(Tick==59)TestEqual(TEXT("Local mode before marker"),ProphecyPhysicalContext::MagnetizationMode(A),0.f);
            if(Tick==60){TestFalse(TEXT("NN resumes at lower marker"),FreezeInference(A));TestEqual(TEXT("Lower begins at 50 percent"),V->PelvisAlpha,0.f);
                TestEqual(TEXT("World mode at marker, before hold/blend completion"),ProphecyPhysicalContext::MagnetizationMode(A),1.f);
                TestFalse(TEXT("Arms released at lower marker"),BeforeLowerHandoff.Contains(A));}
            if(Tick==75){TestEqual(TEXT("Feet hold ends at original deadline"),V->FeetAlpha,0.f);TestEqual(TEXT("Upper still clip-owned"),V->CoreAlpha,0.f);}
            if(Tick==90){TestTrue(TEXT("Pelvis halfway independently"),FMath::IsNearlyEqual(V->PelvisAlpha,.5f));TestTrue(TEXT("Feet halfway after hold"),FMath::IsNearlyEqual(V->FeetAlpha,.5f));}
            if(Tick==120){TestEqual(TEXT("Lower finished while upper starts"),V->FeetAlpha,1.f);TestEqual(TEXT("Upper marker at clip end"),V->CoreAlpha,0.f);}
            if(Tick==180){TestTrue(TEXT("Final endpoint finite and complete"),V->Finished);V->Published=true;}
        }
        Advance(A);TestFalse(TEXT("Completed recovery releases all pose storage"),IsActive(A));
    }
    FActive Snap;Snap.Profile.Entry=0;Snap.Profile.LowerStart=Snap.Profile.UpperStart=0;
    Snap.Profile.Feet=Snap.Profile.Pelvis=Snap.Profile.Hand[0]=Snap.Profile.Hand[1]=Snap.Profile.CoreTime={0,0};
    Snap.ClipDuration=3;SampleTiming(Snap);TestTrue(TEXT("Zero-time handoff is an exact endpoint"),Snap.Finished);
    Install(A,MoveTemp(Snap));TestFalse(TEXT("Immediate marker leaves no arm window"),BeforeLowerHandoff.Contains(A));
    TestEqual(TEXT("Immediate marker ends in world mode"),ProphecyPhysicalContext::MagnetizationMode(A),1.f);
    FActive Cancelled;Cancelled.ClipDuration=3;Install(A,MoveTemp(Cancelled));Cancel(A);
    TestFalse(TEXT("Cancellation releases arms"),BeforeLowerHandoff.Contains(A));
    TestEqual(TEXT("Cancellation cannot leak local mode"),ProphecyPhysicalContext::MagnetizationMode(A),1.f);
    TestFalse(TEXT("Reject invalid alpha"),L::SetGetUpLowerbodyTempering(A,true,-1));
    TestFalse(TEXT("Reject invalid duration"),L::BlendGetUpUpperbodyTempering(A,0,-1));
    TestEqual(TEXT("Rejected settings preserve config"),Configured(A).LowerStart,.5f);
    Remove(A);ProphecyLowerTempering::ForgetProfiles(A);ProphecyHandRecovery::Remove(A);ProphecyCoreTempering::Remove(A);
    W->DestroyWorld(false);return !HasAnyErrors();
}
#endif
