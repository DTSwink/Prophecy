#include "ProphecyHandRecoveryLibrary.h"
#include "ProphecyHandRecovery.h"
#include "ProphecyHandChainMath.h"
#include "ProphecyAttackRecovery.h"
#include "ProphecyBlendClock.h"
#include "ProphecyAgent.h"
#include "Engine/World.h"

namespace ProphecyHandRecovery
{
using E=EProphecyRecoverySource;
using K=ProphecyBlendClock::EKind;
static K HandClock(int32 I) { return I==0?K::LeftHandTempering:K::RightHandTempering; }
static float Progress(double Elapsed,float Hold,float Duration)
{
    if (Elapsed+1.e-8<Hold) return 0;
    const float T=Duration>0?FMath::Clamp(float((Elapsed-Hold)/Duration),0.f,1.f):1.f;
    return T*T*(3-2*T);
}
struct FReturn { FFollow Initial;float Hold=0,Duration=0;double Elapsed=0;bool Active=false; };
struct FValues { FTempering Value;FReturn Return[2]; };
struct FPart
{
    E Source=E::Normal;float Hold=0,Duration=0;
    bool Enabled() const { return Source!=E::Normal && Duration>0; }
    double End() const { return Enabled()?double(Hold)+Duration:0.; }
};
struct FConfig { FTempering Tempering;FPart Recovery[2]; };
struct FRecovery { FPart Part[2];FFrame Sample;double Elapsed=0;bool First=true; };
struct FBaseline { FConfig Config;FTempering Value; };
static TMap<TWeakObjectPtr<const AProphecyAgent>,FConfig> Configs;
static TMap<TWeakObjectPtr<const AProphecyAgent>,FValues> Values;
static TMap<TWeakObjectPtr<const AProphecyAgent>,FRecovery> Active;
static TMap<TWeakObjectPtr<const AProphecyAgent>,FBaseline> Baselines;
static FDelegateHandle Cleanup;
static void EnsureCleanup()
{
    if (Cleanup.IsValid()) return;
    Cleanup=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* W,bool,bool)
    {
        auto Clean=[W](auto& Map) { for(auto It=Map.CreateIterator();It;++It)
            if (!It.Key().IsValid() || It.Key()->GetWorld()==W) It.RemoveCurrent(); };
        Clean(Configs);Clean(Values);Clean(Active);Clean(Baselines);
    });
}
static bool Valid(AProphecyAgent* A)
{ return IsInGameThread() && IsValid(A) && !A->IsActorBeingDestroyed() && A->GetWorld() && !A->GetWorld()->bIsTearingDown; }
static void ClearValues(const AProphecyAgent* A)
{
    if (Values.IsEmpty() || !Values.Remove(A)) return;
    for(int32 I=0;I<2;++I) ProphecyBlendClock::Stop(A,HandClock(I));
}
static void SetValues(const AProphecyAgent* A,const FTempering& T)
{ ClearValues(A);if (!T.Normal()) { EnsureCleanup();Values.Add(A,FValues{T}); } }
void CancelRecovery(const AProphecyAgent* A)
{
    if (Active.IsEmpty() || !Active.Remove(A)) return;
    ProphecyBlendClock::Stop(A,K::HandRecovery);
}
static void StartRecovery(const AProphecyAgent* A,const FConfig& C)
{
    CancelRecovery(A);
    if (!C.Recovery[0].Enabled() && !C.Recovery[1].Enabled()) return;
    EnsureCleanup();FRecovery R;R.Part[0]=C.Recovery[0];R.Part[1]=C.Recovery[1];Active.Add(A,R);
}
void Begin(const AProphecyAgent* A)
{
    const auto* C=Configs.IsEmpty()?nullptr:Configs.Find(A);
    if (!C) return;
    SetValues(A,C->Tempering);StartRecovery(A,*C);
}
void Remove(const AProphecyAgent* A)
{ CancelRecovery(A);ClearValues(A);Configs.Remove(A);Baselines.Remove(A); }
void CancelMotion(const AProphecyAgent* A) { CancelRecovery(A);ClearValues(A); }
void Step(const AProphecyAgent* A)
{
    auto* R=Active.IsEmpty()?nullptr:Active.Find(A);
    if (!R) return;
    const double End=FMath::Max(R->Part[0].End(),R->Part[1].End());
    if (R->First) { R->First=false;ProphecyBlendClock::Start(A,K::HandRecovery,End); }
    else R->Elapsed+=ProphecyBlendClock::Consume(A,K::HandRecovery);
    if (R->Elapsed+1.e-6>=End) { CancelRecovery(A);return; }
    auto& S=R->Sample;S.Need[0]=S.Need[1]=S.Ready[0]=S.Ready[1]=false;
    for(int32 I=0;I<2;++I)
    {
        const auto& P=R->Part[I];S.Alpha[I]=P.Enabled()?Progress(R->Elapsed,P.Hold,P.Duration):1.f;
        S.Source[I]=P.Source==E::Walk?1:0;
        if (S.Alpha[I]<1) S.Need[S.Source[I]]=true;
    }
}
FFrame* Frame(const AProphecyAgent* A)
{ auto* R=Active.IsEmpty()?nullptr:Active.Find(A);return R?&R->Sample:nullptr; }
bool HasRecovery() { return !Active.IsEmpty(); }
const FTempering* Tempering(const AProphecyAgent* A)
{
    auto* V=Values.IsEmpty()?nullptr:Values.Find(A);if (!V) return nullptr;
    for(int32 I=0;I<2;++I)
    {
        auto& R=V->Return[I];if (!R.Active) continue;
        R.Elapsed+=ProphecyBlendClock::Consume(A,HandClock(I));
        const float W=Progress(R.Elapsed,R.Hold,R.Duration);
        V->Value.Hand[I]={FMath::Lerp(R.Initial.XY,1.f,W),FMath::Lerp(R.Initial.Z,1.f,W),FMath::Lerp(R.Initial.Rotation,1.f,W)};
        if (W>=1) { R.Active=false;ProphecyBlendClock::Stop(A,HandClock(I)); }
    }
    if (V->Value.Normal()) { ClearValues(A);return nullptr; }
    return &V->Value;
}
FTransform TemperTarget(const FFollow& F,const FTransform& PreviousReference,const FTransform& Reference,
    const FTransform& PreviousHand,const FTransform& Target)
{
    if (F.Normal()) return Target;
    const FTransform P=PreviousHand.GetRelativeTransform(PreviousReference),N=Target.GetRelativeTransform(Reference);
    const FVector A=P.GetLocation(),B=N.GetLocation();
    return FTransform(FQuat::Slerp(P.GetRotation(),N.GetRotation(),F.Rotation).GetNormalized(),
        FVector(FMath::Lerp(A.X,B.X,double(F.XY)),FMath::Lerp(A.Y,B.Y,double(F.XY)),FMath::Lerp(A.Z,B.Z,double(F.Z))),N.GetScale3D())*Reference;
}
void CaptureReset(const AProphecyAgent* A)
{
    FBaseline B;if (const auto* C=Configs.Find(A)) B.Config=*C;
    if (const auto* T=Tempering(A)) B.Value=*T;
    EnsureCleanup();Baselines.Add(A,B);
}
void RestoreReset(const AProphecyAgent* A)
{
    CancelRecovery(A);ClearValues(A);
    if (const auto* B=Baselines.Find(A)) { Configs.Add(A,B->Config);SetValues(A,B->Value); }
}
void ForgetReset(const AProphecyAgent* A) { Baselines.Remove(A); }
}

bool UProphecyHandRecoveryLibrary::SetLocomotionHandTempering(AProphecyAgent* A,bool Enabled,
    float LX,float LZ,float LR,float RX,float RZ,float RR)
{
    using namespace ProphecyHandRecovery;
    if (!Valid(A)) return false;
    for(float V:{LX,LZ,LR,RX,RZ,RR}) if(!FMath::IsFinite(V)||V<0||V>1) return false;
    FTempering T;if(Enabled) { T.Hand[0]={LX,LZ,LR};T.Hand[1]={RX,RZ,RR}; }
    EnsureCleanup();Configs.FindOrAdd(A).Tempering=T;SetValues(A,T);return true;
}
bool UProphecyHandRecoveryLibrary::BlendLocomotionHandTemperingToNormal(AProphecyAgent* A,float LH,float LD,float RH,float RD)
{
    using namespace ProphecyHandRecovery;
    if (!Valid(A)) return false;
    for(float V:{LH,LD,RH,RD}) if(!FMath::IsFinite(V)||V<0) return false;
    if (!Tempering(A)) return true;
    auto& V=Values.FindChecked(A);const float H[2]={LH,RH},D[2]={LD,RD};
    for(int32 I=0;I<2;++I)
    {
        ProphecyBlendClock::Stop(A,HandClock(I));V.Return[I]={};
        if(V.Value.Hand[I].Normal()) continue;
        if(H[I]==0 && D[I]==0) { V.Value.Hand[I]={};continue; }
        V.Return[I]={V.Value.Hand[I],H[I],D[I],0,true};
        ProphecyBlendClock::Start(A,HandClock(I),double(H[I])+D[I]);
    }
    if(V.Value.Normal()) ClearValues(A);
    return true;
}
bool UProphecyHandRecoveryLibrary::SetAttackToLocomotionHandBlend(AProphecyAgent* A,
    EProphecyRecoverySource LS,float LH,float LD,EProphecyRecoverySource RS,float RH,float RD)
{
    using namespace ProphecyHandRecovery;
    if(!Valid(A)||uint8(LS)>uint8(E::Run)||uint8(RS)>uint8(E::Run)) return false;
    for(float V:{LH,LD,RH,RD}) if(!FMath::IsFinite(V)||V<0) return false;
    EnsureCleanup();auto& C=Configs.FindOrAdd(A);C.Recovery[0]={LS,LH,LD};C.Recovery[1]={RS,RH,RD};
    if(ProphecyAttackRecovery::IsEndEvent(A)) StartRecovery(A,C);
    else if(auto* R=Active.Find(A))
    {
        if(R->First) { R->Part[0]=C.Recovery[0];R->Part[1]=C.Recovery[1]; }
        for(int32 I=0;I<2;++I) if(!C.Recovery[I].Enabled()) { R->Part[I]=C.Recovery[I];R->Sample.Alpha[I]=1; }
        if(!R->Part[0].Enabled()&&!R->Part[1].Enabled()) CancelRecovery(A);
    }
    return true;
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "ProphecyHandInertia.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyHandRecoveryTest,"Prophecy.NN.HandRecovery.ControlsAndLifecycle",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyHandRecoveryTest::RunTest(const FString&)
{
    using namespace ProphecyHandRecovery;using L=UProphecyHandRecoveryLibrary;
    UWorld* W=UWorld::CreateWorld(EWorldType::Editor,false);
    auto* A=W?W->SpawnActor<AProphecyAgent>():nullptr;if(!A) return false;
    for(float FPS:{30.f,60.f,120.f})
    {
        L::SetLocomotionHandTempering(A,true,0,.25f,.5f,.2f,.4f,.6f);
        CaptureReset(A);
        L::BlendLocomotionHandTemperingToNormal(A,.5f,1,0,.5f);
        for(int32 T=1;T<=90;++T)
        {
            FWorldDelegates::OnWorldPreActorTick.Broadcast(W,LEVELTICK_All,1.f/FPS);
            const auto* S=Tempering(A);
            if(T==30) TestTrue(TEXT("Left holds while right independently reaches normal"),S && S->Hand[0].XY==0 && S->Hand[1].Normal());
            if(T==60) TestTrue(TEXT("Left XY/Z/rotation halfway after hold"),S && FMath::IsNearlyEqual(S->Hand[0].XY,.5f) &&
                FMath::IsNearlyEqual(S->Hand[0].Z,.625f) && FMath::IsNearlyEqual(S->Hand[0].Rotation,.75f));
        }
        TestNull(TEXT("Completed tempering retires values"),Tempering(A));
        RestoreReset(A);
        TestTrue(TEXT("Reset restores captured hand values without restarting return"),Tempering(A) && Tempering(A)->Hand[0].XY==0);
        L::SetAttackToLocomotionHandBlend(A,E::Walk,.5f,1,E::Run,0,.5f);
        Begin(A);Step(A);
        TestTrue(TEXT("Independent hand sources requested"),Frame(A) && Frame(A)->Need[0] && Frame(A)->Need[1]);
        for(int32 T=1;T<=90;++T)
        {
            FWorldDelegates::OnWorldPreActorTick.Broadcast(W,LEVELTICK_All,1.f/FPS);Step(A);
            const auto* F=Frame(A);
            if(T==30) TestTrue(TEXT("Only held left source remains after right completion"),F && F->Need[1] && !F->Need[0] && F->Alpha[0]==0 && F->Alpha[1]==1);
            if(T==60) TestTrue(TEXT("Walk source halfway back to normal"),F && FMath::IsNearlyEqual(F->Alpha[0],.5f));
        }
        TestNull(TEXT("Finished recovery removes source scratch and clock"),Frame(A));
        Begin(A);Step(A);ProphecyAttackRecovery::Cancel(A);
        TestNotNull(TEXT("Leg completion or disabling cannot cancel a longer hand recovery"),Frame(A));
        CancelRecovery(A);TestNull(TEXT("New special cancels recovery"),Frame(A));
        L::SetAttackToLocomotionHandBlend(A,E::Walk,3,0,E::Run,3,0);Begin(A);Step(A);
        TestNull(TEXT("Zero blend duration creates no recovery despite hold"),Frame(A));
    }
    const FTransform PrevRoot(FRotator(0,20,0),FVector(10,20,0)),Root(FRotator(0,110,0),FVector(100,200,0));
    const FTransform Local(FRotator(20,30,40),FVector(25,-15,50));
    const FTransform Target=FTransform(FRotator(-20,70,10),FVector(50,30,100))*Root;
    const auto Frozen=TemperTarget({0,0,0},PrevRoot,Root,Local*PrevRoot,Target);
    TestTrue(TEXT("Zero follows root while retaining complete local hand pose"),Frozen.Equals(Local*Root,1.e-6));
    const auto Split=TemperTarget({0,1,1},PrevRoot,Root,Local*PrevRoot,Target).GetRelativeTransform(Root);
    TestTrue(TEXT("XY frozen independently from Z and rotation"),Split.GetLocation().Equals(FVector(25,-15,100),1.e-6) &&
        Split.GetRotation().Equals(Target.GetRelativeTransform(Root).GetRotation(),1.e-6));
    FTransform Shoulder(FQuat::Identity,FVector::ZeroVector),Elbow(FQuat::Identity,FVector(40,0,0)),Hand(FQuat::Identity,FVector(65,20,0));
    ProphecyHandInertia::ResolveTarget(Shoulder,Elbow,Hand,Target,FVector::UpVector,35);
    TestTrue(TEXT("Tempered/recovered arm stays connected at fixed lengths"),FMath::IsNearlyEqual((Elbow.GetLocation()-Shoulder.GetLocation()).Length(),40.,1.e-6) &&
        FMath::IsNearlyEqual((Hand.GetLocation()-Elbow.GetLocation()).Length(),35.,1.e-6));
    TestTrue(TEXT("Reach correction preserves requested hand rotation"),Hand.GetRotation().Equals(Target.GetRotation(),1.e-6));
    TestFalse(TEXT("Invalid values reject without changing state"),L::SetLocomotionHandTempering(A,true,-1));
    Remove(A);TestNull(TEXT("Teardown has no tempering or recovery"),Tempering(A));TestNull(TEXT("Teardown has no source frame"),Frame(A));
    W->DestroyWorld(false);return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyHandChainContinuityTest,"Prophecy.NN.HandRecovery.ChainContinuity",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyHandChainContinuityTest::RunTest(const FString&)
{
    using namespace ProphecyHandChain;
    const FVector Offset(30,0,0),Pole(0,1,0);
    const FTransform S(FRotator(15,20,10),FVector(10,20,40));
    const FTransform E(FRotator(10,-20,35),S.TransformPosition(Offset));
    const FTransform W(FRotator(20,50,-30),E.GetLocation()+S.TransformVector(FVector(10,25,5)));
    for(double Follow:{0.,.1,.5,.9,1.})
    {
        FTransform Shoulder=S,Elbow=E,Wrist=W;
        Resolve(S,E,W,Shoulder,Elbow,Wrist,W,Offset,Pole,Follow);
        TestTrue(TEXT("An unchanged coherent arm stays unchanged, including shoulder twist"),Shoulder.Equals(S,1.e-6) &&
            Elbow.GetLocation().Equals(E.GetLocation(),1.e-6) && Wrist.Equals(W,1.e-6));
    }
    FTransform Target=W;Target.AddToTranslation(FVector(5,-8,7));
    FTransform FirstElbow,FirstShoulder;
    for(int32 I=0;I<8;++I)
    {
        FTransform Shoulder=S,Elbow=E,Wrist=W;
        Target.SetRotation((FQuat(FVector::ForwardVector,I*.4)*W.GetRotation()).GetNormalized());
        Resolve(S,E,W,Shoulder,Elbow,Wrist,Target,Offset,Pole,0.);
        if(I==0) {FirstElbow=Elbow;FirstShoulder=Shoulder;}
        TestTrue(TEXT("Wrist roll cannot orbit the elbow or twist the upper arm"),Elbow.GetLocation().Equals(FirstElbow.GetLocation(),1.e-6) && Shoulder.Equals(FirstShoulder,1.e-6));
        TestTrue(TEXT("Connected chain and requested wrist orientation"),Elbow.GetLocation().Equals(Shoulder.TransformPosition(Offset),1.e-6) &&
            FMath::IsNearlyEqual((Wrist.GetLocation()-Elbow.GetLocation()).Length(),(W.GetLocation()-E.GetLocation()).Length(),1.e-6) &&
            Wrist.GetRotation().Equals(Target.GetRotation(),1.e-6));
    }
    // Stretched but deliberately unclamped source converges to EXACT normal,
    // instead of forcing rest length until the last active sample.
    const FTransform NS(FRotator(35,-15,20),FVector(12,19,41));
    const FTransform NE(FQuat::Identity,NS.TransformPosition(Offset));
    const FTransform NW(FRotator(5,10,15),NE.GetLocation()+NS.TransformVector(FVector(15,28,6)));
    FTransform PrevS=S,PrevE=E,PrevW=W;
    double MaxStep=0;
    for(int32 I=0;I<=60;++I)
    {
        const double T=I/60.,Follow=T*T*(3-2*T);
        FTransform Shoulder=NS,Elbow=NE,Wrist=NW;
        FTransform Goal=NW;Goal.SetLocation(FMath::Lerp(PrevW.GetLocation(),NW.GetLocation(),Follow));
        Resolve(PrevS,PrevE,PrevW,Shoulder,Elbow,Wrist,Goal,Offset,Pole,Follow);
        MaxStep=FMath::Max(MaxStep,Shoulder.GetRotation().AngularDistance(PrevS.GetRotation()));
        TestFalse(TEXT("Fade produces finite connected transforms"),Shoulder.ContainsNaN() || Elbow.ContainsNaN() || Wrist.ContainsNaN());
        TestTrue(TEXT("Elbow remains on the upper arm throughout fade"),Elbow.GetLocation().Equals(Shoulder.TransformPosition(Offset),1.e-6));
        PrevS=Shoulder;PrevE=Elbow;PrevW=Wrist;
    }
    TestTrue(TEXT("No endpoint or shoulder jump when normal decoder resumes"),PrevS.Equals(NS,1.e-6) && PrevE.GetLocation().Equals(NE.GetLocation(),1.e-6) && PrevW.Equals(NW,1.e-6));
    TestTrue(TEXT("Coherent return stays below ten degrees per policy sample"),MaxStep<FMath::DegreesToRadians(10.));
    for(double Follow:{0.,.2,.9,1.})
    {
        const FQuat R=FollowTwist(S.GetRotation(),NS.GetRotation(),Offset,Follow);
        TestTrue(TEXT("Forearm twist following never changes its aim"),R.RotateVector(Offset).Equals(NS.GetRotation().RotateVector(Offset),1.e-6));
    }
    // The same calculation in another root/world frame must commute.
    const FTransform Root(FRotator(30,110,5),FVector(500,-700,80));
    FTransform A=NS,B=NE,C=NW,RA=NS*Root,RB=NE*Root,RC=NW*Root;
    Resolve(S,E,W,A,B,C,NW,Offset,Pole,.3);
    Resolve(S*Root,E*Root,W*Root,RA,RB,RC,NW*Root,Offset,Pole,.3);
    TestTrue(TEXT("Root-local chain solve is equivariant"),RA.Equals(A*Root,1.e-6) && RB.Equals(B*Root,1.e-6) && RC.Equals(C*Root,1.e-6));
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyHandBendBlendTest,"Prophecy.NN.HandRecovery.BendBlend",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyHandBendBlendTest::RunTest(const FString&)
{
    using namespace ProphecyHandChain;
    // Captured slashR exit: mixing the raw shoulder/endpoints gave a strongly
    // nonlinear swivel and kept the elbow on the opposite side of idle.
    const FVector Offset(-26.651449,0,0),LocalPole(0,99.67503,-8.055328);
    const FTransform PS(FQuat(.889630664,-.347223185,.295306014,-.028065994).GetNormalized(),FVector(0,13.375396,2.054786));
    const FTransform PE(PS.TransformPosition(Offset));
    const FTransform PW(FVector(-31.041967,43.987524,-18.115667));
    const FTransform NS(FQuat(.853407639,-.312747866,.273992396,.314344304).GetNormalized(),FVector(0,13.288782,1.952071));
    const FTransform NE(NS.TransformPosition(Offset));
    const FTransform NW(FVector(-21.813846,36.301616,-33.290068));
    const FTransform Target(FVector(-30.746899,43.775991,-18.572348));
    const FVector Axis=(Target.GetLocation()-NS.GetLocation()).GetSafeNormal();
    auto Bend=[&](const FTransform& S,const FTransform& E,const FTransform& W)
    { const FVector A=(W.GetLocation()-S.GetLocation()).GetSafeNormal();
      return TransportPole(A,Axis,Plane(E.GetLocation()-S.GetLocation(),A,S.TransformVectorNoScale(LocalPole))); };
    const FVector P=Bend(PS,PE,PW),N=Bend(NS,NE,NW);
    const double Total=FMath::Acos(FMath::Clamp(FVector::DotProduct(P,N),-1.,1.));
    double OldAngle=-1;
    for(int32 I=0;I<=40;++I)
    {
        const double T=I/40.;FTransform S=NS,E=NE,W=NW;
        Resolve(PS,PE,PW,S,E,W,Target,Offset,LocalPole,T);
        const FVector Actual=Bend(S,E,W);
        const double Angle=FMath::Acos(FMath::Clamp(FVector::DotProduct(P,Actual),-1.,1.));
        TestTrue(TEXT("Bend progresses without reversal or an intermediate singularity"),Angle+1.e-6>=OldAngle && FMath::Abs(Angle-Total*T)<1.e-5);
        TestTrue(TEXT("Reconstruction preserves wrist and both link lengths"),W.GetLocation().Equals(Target.GetLocation(),1.e-6) &&
            E.GetLocation().Equals(S.TransformPosition(Offset),1.e-6) && FMath::IsNearlyEqual((W.GetLocation()-E.GetLocation()).Length(),
                FMath::Lerp((PW.GetLocation()-PE.GetLocation()).Length(),(NW.GetLocation()-NE.GetLocation()).Length(),T),1.e-6));
        OldAngle=Angle;
    }
    FTransform Results[2];int32 Index=0;
    for(double Sign:{-1.,1.})
    {
        FTransform S=NS,E=NE,W=NW;
        W.SetLocation(NS.TransformPosition(Offset*1.8)+NS.TransformVectorNoScale(FVector(0,Sign*1.e-8,0)));
        Resolve(PS,PE,PW,S,E,W,Target,Offset,LocalPole,.5);
        Results[Index++]=E;
        TestFalse(TEXT("Straight source remains finite"),S.ContainsNaN() || E.ContainsNaN() || W.ContainsNaN());
    }
    TestTrue(TEXT("Sub-nanometre straight-arm noise cannot flip the elbow"),Results[0].GetLocation().Equals(Results[1].GetLocation(),1.e-5));
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyHandSpineReferenceTest,"Prophecy.NN.HandRecovery.SpineReference",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyHandSpineReferenceTest::RunTest(const FString&)
{
    using namespace ProphecyHandRecovery;
    // Torso moves and tilts while the actor root stays stationary.
    const FTransform Before(FRotator(15,20,-10),FVector(0,0,130));
    const FTransform After(FRotator(-30,85,40),FVector(8,-12,143));
    const FTransform Local(FRotator(20,10,15),FVector(25,-18,-35));
    const FTransform DesiredLocal(FRotator(-5,65,40),FVector(45,12,-10));
    const FTransform Desired=DesiredLocal*After;
    const FTransform Frozen=TemperTarget({0,0,0},Before,After,Local*Before,Desired);
    TestTrue(TEXT("Zero carries the hand with translated, pitched, yawed and rolled spine"),Frozen.Equals(Local*After,1.e-6));
    TestFalse(TEXT("Stationary actor root does not leave the frozen hand in world space"),Frozen.Equals(Local*Before,1.e-6));
    const auto Split=TemperTarget({0,1,.5},Before,After,Local*Before,Desired).GetRelativeTransform(After);
    TestTrue(TEXT("XY and Z are independently controlled in spine axes"),Split.GetLocation().Equals(FVector(25,-18,-10),1.e-6));
    TestTrue(TEXT("Rotation blends in spine frame"),Split.GetRotation().Equals(FQuat::Slerp(Local.GetRotation(),DesiredLocal.GetRotation(),.5).GetNormalized(),1.e-6));
    TestTrue(TEXT("All-one exactly bypasses the frame conversion"),TemperTarget({},Before,After,Local*Before,Desired).Equals(Desired,0));
    // Carry elbow/forearm frames with that same torso rotation. A fixed local
    // pose must not counter-rotate its forearm against the moving spine.
    const FQuat OldForearm=(FQuat(FVector::UpVector,.3)*Before.GetRotation()).GetNormalized();
    const FQuat Carried=(After.GetRotation()*Before.GetRotation().Inverse()*OldForearm).GetNormalized();
    TestTrue(TEXT("Frozen forearm keeps torso-relative twist"),ProphecyHandChain::FollowTwist(Carried,Carried,FVector::ForwardVector,0).Equals(Carried,1.e-6));
    for(int32 I=0;I<=60;++I)
    {
        const float T=I/60.f,W=T*T*(3-2*T);
        const auto Result=TemperTarget({W,W,W},Before,After,Local*Before,Desired).GetRelativeTransform(After);
        TestTrue(TEXT("Existing return-to-normal values act in spine frame throughout fade"),Result.GetLocation().Equals(FMath::Lerp(Local.GetLocation(),DesiredLocal.GetLocation(),double(W)),1.e-6));
    }
    return !HasAnyErrors();
}
#endif
