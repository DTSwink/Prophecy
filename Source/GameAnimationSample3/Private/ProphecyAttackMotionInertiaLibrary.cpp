#include "ProphecyAttackMotionInertiaLibrary.h"
#include "ProphecyNNModifierDebug.h"
#include "ProphecyAttackMotionInertia.h"
#include "ProphecyAgent.h"
#include "ProphecyBlendClock.h"
#include "ProphecyPelvisInertiaMath.h"
#include "Engine/World.h"

namespace ProphecyAttackMotionInertia
{
using K=ProphecyBlendClock::EKind;
constexpr int32 MaxJoints=16;
constexpr double Step=1./30.;
struct FConfig { float Response=.03f;int32 After=1;bool CoreOnly=false,AfterHit=false; };
struct FJoint
{
    int32 Bone=INDEX_NONE,Parent=INDEX_NONE;
    bool Filter=false;
    FQuat Rotation=FQuat::Identity;
    FVector Velocity=FVector::ZeroVector;
};
struct FState
{
    FConfig Config;
    FJoint Joints[MaxJoints];
    int32 Count=0;
    double W=0,E=0,Elapsed=0,ArmedAt=0;
    bool SawArmed=false,SawHit=false,FilteringNow=true;
    TArray<FTransform> SourceWorld;
};
static TMap<TWeakObjectPtr<const AProphecyAgent>,FConfig> Configs,Baselines;
static TMap<TWeakObjectPtr<const AProphecyAgent>,FState> States;
static FDelegateHandle Cleanup;
static void EnsureCleanup()
{
    if(Cleanup.IsValid())return;
    Cleanup=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* World,bool,bool)
    {
        auto Clean=[World](auto& Map){for(auto It=Map.CreateIterator();It;++It)
            if(!It.Key().IsValid() || It.Key()->GetWorld()==World)It.RemoveCurrent();};
        Clean(Configs);Clean(Baselines);Clean(States);
    });
}
bool Configured(const AProphecyAgent* A){return !Configs.IsEmpty() && Configs.Contains(A);}
bool FilteringArms(const AProphecyAgent* A)
{const auto* S=States.IsEmpty()?nullptr:States.Find(A);return S && S->FilteringNow && (!S->Config.CoreOnly || S->SawHit);}
void Cancel(const AProphecyAgent* A)
{if(!States.IsEmpty() && States.Remove(A))ProphecyBlendClock::Stop(A,K::AttackMotionInertia);}
void Remove(const AProphecyAgent* A){Cancel(A);Configs.Remove(A);Baselines.Remove(A);}
void CaptureReset(const AProphecyAgent* A){if(const auto* C=Configs.Find(A))Baselines.Add(A,*C);else Baselines.Remove(A);}
void RestoreReset(const AProphecyAgent* A){Cancel(A);Configs.Remove(A);if(const auto* C=Baselines.Find(A))Configs.Add(A,*C);}
void ForgetReset(const AProphecyAgent* A){Baselines.Remove(A);}
static bool Prepare(FState& S,const FConfig& C,TConstArrayView<FName> Names,TConstArrayView<int32> Parents,
    TConstArrayView<FTransform> Previous,TConstArrayView<FTransform> Current)
{
    if(Names.Num()!=Parents.Num() || Names.Num()!=Current.Num() || Current.Num()!=Previous.Num())return false;
    const int32 Spine=Names.IndexOfByKey(TEXT("spine_01"));if(Spine==INDEX_NONE)return false;
    S.Config=C;S.W=2./C.Response;S.E=FMath::Exp(-S.W*Step);
    S.SourceWorld.Reserve(Current.Num());
    for(int32 B=0;B<Names.Num();++B)
    {
        const int32 Parent=Parents[B];bool Upper=false;
        for(int32 P=B,Remaining=Names.Num();Parents.IsValidIndex(P) && Remaining-->0;P=Parents[P])
            if(P==Spine){Upper=true;break;}
        if(!Upper)continue;
        if(Parent<0 || Parent>=B || S.Count==MaxJoints)return false;
        auto& J=S.Joints[S.Count++];J.Bone=B;J.Parent=Parent;
        const FString Name=Names[B].ToString();
        J.Filter=!C.CoreOnly || Name.StartsWith(TEXT("spine_")) || Name.StartsWith(TEXT("neck_")) || Name==TEXT("head");
        J.Rotation=(Current[Parent].GetRotation().Inverse()*Current[B].GetRotation()).GetNormalized();
        if(J.Filter || C.AfterHit)
        {
            const FQuat Before=(Previous[Parent].GetRotation().Inverse()*Previous[B].GetRotation()).GetNormalized();
            J.Velocity=ProphecyPelvisInertia::RotationVector(J.Rotation*Before.Inverse())/Step;
        }
    }
    return S.Count>0;
}
void Begin(const AProphecyAgent* A,TConstArrayView<FName> Names,TConstArrayView<int32> Parents,
    TConstArrayView<FTransform> Previous,TConstArrayView<FTransform> Current)
{
    Cancel(A);const auto* C=Configs.IsEmpty()?nullptr:Configs.Find(A);if(!C)return;
    FState S;if(!Prepare(S,*C,Names,Parents,Previous,Current))return;
    States.Add(A,MoveTemp(S));ProphecyBlendClock::Start(A,K::AttackMotionInertia);
}
static bool InWindow(FState& S,bool Armed,double Dt,bool Hit=false)
{
    S.Elapsed+=Dt;
    if(Armed && !S.SawArmed){S.SawArmed=true;S.ArmedAt=S.Elapsed;}
    if(S.Config.AfterHit && Hit && !S.SawHit)
    {
        S.SawHit=true;
        for(int32 I=0;I<S.Count;++I)S.Joints[I].Filter=true;
    }
    return S.SawHit || S.Config.CoreOnly || !S.SawArmed || (S.Config.After>0 &&
        S.Elapsed-S.ArmedAt<=double(S.Config.After)/60.+1.e-8);
}
static void Track(FJoint& J,const FQuat& Rotation)
{
    J.Velocity=ProphecyPelvisInertia::RotationVector(Rotation*J.Rotation.Inverse())/Step;
    J.Rotation=Rotation;
}
static void Solve(FState& S,TArrayView<FTransform> Pose)
{
    // Fixed stack scratch; all source locals are read before any parent changes.
    FTransform Local[MaxJoints];
    for(int32 I=0;I<S.Count;++I)
    {const auto& J=S.Joints[I];Local[I]=Pose[J.Bone].GetRelativeTransform(Pose[J.Parent]);}
    for(int32 I=0;I<S.Count;++I)
    {
        auto& J=S.Joints[I];
        if(J.Filter)
        {
            const FQuat Goal=Local[I].GetRotation();
            const FVector X=ProphecyPelvisInertia::RotationVector(J.Rotation*Goal.Inverse()),V=J.Velocity+S.W*X;
            J.Rotation=(ProphecyPelvisInertia::RotationIncrement((X+V*Step)*S.E)*Goal).GetNormalized();
            J.Velocity=(J.Velocity-S.W*V*Step)*S.E;
            Local[I].SetRotation(J.Rotation);
        }
        else if(S.Config.AfterHit)Track(J,Local[I].GetRotation());
        // Translations and scale come from the source, including forearm leeway.
        Pose[J.Bone]=Local[I]*Pose[J.Parent];
    }
}
bool Apply(const AProphecyAgent* A,TArrayView<FTransform> Pose,bool Armed,bool Hit)
{
    auto* S=States.IsEmpty()?nullptr:States.Find(A);if(!S)return false;
    // Called exactly once per accepted 30 Hz prediction, never by pose reads.
    if(!Pose.IsValidIndex(S->Joints[S->Count-1].Bone)){Cancel(A);return false;}
    S->FilteringNow=InWindow(*S,Armed,ProphecyBlendClock::Consume(A,K::AttackMotionInertia),Hit);
    if(!S->FilteringNow)
    {
        // Previous source was consumed before Publish. This endpoint is now raw,
        // so the next step can safely use its ordinary previous-visible cache.
        if(!S->Config.AfterHit){Cancel(A);return false;}
        // Observe the current unfiltered local motion while waiting for Hit.
        // Never restart from the obsolete wind-up spring pose/velocity.
        for(int32 I=0;I<S->Count;++I)
        {
            auto& J=S->Joints[I];
            Track(J,(Pose[J.Parent].GetRotation().Inverse()*Pose[J.Bone].GetRotation()).GetNormalized());
        }
        return false;
    }
    Solve(*S,Pose);return true;
}

TConstArrayView<FTransform> PreviousSource(const AProphecyAgent* A)
{
    const auto* S=States.IsEmpty()?nullptr:States.Find(A);
    return S?TConstArrayView<FTransform>(S->SourceWorld):TConstArrayView<FTransform>();
}
void TranslateSource(const AProphecyAgent* A,const FVector& Delta)
{
    if(auto* S=States.IsEmpty()?nullptr:States.Find(A))
        for(auto& Bone:S->SourceWorld)Bone.AddToTranslation(Delta);
}
void Publish(const AProphecyAgent* A,TArrayView<FTransform> Pose,const FTransform& Carrier,bool Armed,bool Hit)
{
    auto* S=States.IsEmpty()?nullptr:States.Find(A);if(!S)return;
    S->SourceWorld.SetNumUninitialized(Pose.Num());
    for(int32 B=0;B<Pose.Num();++B)S->SourceWorld[B]=Pose[B]*Carrier;
    Apply(A,Pose,Armed,Hit);
}
}

bool UProphecyAttackMotionInertiaLibrary::SetAttackMotionInertia(AProphecyAgent* Agent,bool Enabled,
    float Inertia,int32 FramesAfterArmed,bool CoreOnlyThroughoutAttack,bool AfterHit)
{
    using namespace ProphecyAttackMotionInertia;
    if(!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed() || !Agent->GetWorld()
        || Agent->GetWorld()->bIsTearingDown || !FMath::IsFinite(Inertia) || Inertia<0 || FramesAfterArmed<0)return false;
    if(!Enabled || Inertia==0){Cancel(Agent);Configs.Remove(Agent);return true;}
    EnsureCleanup();Configs.Add(Agent,FConfig{Inertia,FramesAfterArmed,CoreOnlyThroughoutAttack,AfterHit});return true;
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FAttackMotionWindowTest,"Prophecy.Attack.MotionInertia.Window",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FAttackMotionWindowTest::RunTest(const FString&)
{
    using namespace ProphecyAttackMotionInertia;
    FState S;TestTrue(TEXT("Pre-armed active"),InWindow(S,false,1./60.));
    TestTrue(TEXT("Default includes armed prediction"),InWindow(S,true,1./60.));
    TestTrue(TEXT("Duplicate timing does not expire"),InWindow(S,true,0));
    TestTrue(TEXT("One following tick included"),InWindow(S,true,1./60.));
    TestFalse(TEXT("Next tick retires"),InWindow(S,true,1./60.));
    S=FState{};S.Config.After=0;TestFalse(TEXT("Zero excludes armed prediction"),InWindow(S,true,Step));
    S=FState{};S.Config.CoreOnly=true;TestTrue(TEXT("Core option spans armed"),InWindow(S,true,Step));
    TestTrue(TEXT("Core option lasts through attack"),InWindow(S,true,100));return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FAttackMotionGeometryTest,"Prophecy.Attack.MotionInertia.Geometry",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FAttackMotionGeometryTest::RunTest(const FString&)
{
    using namespace ProphecyAttackMotionInertia;
    const FName Names[]={TEXT("pelvis"),TEXT("spine_01"),TEXT("clavicle_r"),TEXT("upperarm_r"),TEXT("lowerarm_r"),TEXT("hand_r"),TEXT("thigh_r")};
    const int32 Parents[]={-1,0,1,2,3,4,0};
    FTransform Previous[7],Current[7],Goal[7],Original[7];
    for(int32 B=0;B<7;++B)
    {
        const FTransform Local(FRotator(0,10,0),FVector(0,0,20));
        Previous[B]=Parents[B]<0?FTransform::Identity:Local*Previous[Parents[B]];
        Current[B]=Previous[B];Goal[B]=Parents[B]<0?FTransform::Identity:
            FTransform(FRotator(12,25,0),FVector(0,0,B==5?23:20))*Goal[Parents[B]];
        Original[B]=Goal[B];
    }
    FState S;FConfig C;C.CoreOnly=true;
    TestTrue(TEXT("Prepare core hierarchy"),Prepare(S,C,Names,Parents,Previous,Current));Solve(S,Goal);
    TestTrue(TEXT("Pelvis identical"),Goal[0].Equals(Original[0],0));
    TestTrue(TEXT("Leg identical"),Goal[6].Equals(Original[6],0));
    for(int32 B=2;B<=5;++B)TestTrue(TEXT("Clavicle and arm locals untouched"),
        Goal[B].GetRelativeTransform(Goal[Parents[B]]).Equals(Original[B].GetRelativeTransform(Original[Parents[B]]),1.e-8));
    TestFalse(TEXT("Core filtered"),Goal[1].GetRotation().Equals(Original[1].GetRotation(),1.e-6));
    C.CoreOnly=false;S=FState{};Prepare(S,C,Names,Parents,Previous,Current);
    for(int32 B=0;B<7;++B)Goal[B]=Original[B];Solve(S,Goal);
    for(int32 B=1;B<=5;++B)TestTrue(TEXT("Every upper translation preserved"),
        Goal[B].GetRelativeTransform(Goal[Parents[B]]).GetTranslation().Equals(Original[B].GetRelativeTransform(Original[Parents[B]]).GetTranslation(),1.e-8));
    return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FAttackMotionLifecycleTest,"Prophecy.Attack.MotionInertia.Lifecycle",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FAttackMotionLifecycleTest::RunTest(const FString&)
{
    using namespace ProphecyAttackMotionInertia;
    UWorld* World=UWorld::CreateWorld(EWorldType::Editor,false);
    auto* A=World?World->SpawnActor<AProphecyAgent>():nullptr;if(!A)return false;
    const FName Names[]={TEXT("pelvis"),TEXT("spine_01")};const int32 Parents[]={-1,0};
    FTransform Pose[]={FTransform::Identity,FTransform(FVector(0,0,10))};
    TestFalse(TEXT("Default disabled"),Configured(A));
    TestFalse(TEXT("Disabled pose untouched"),Apply(A,Pose,false));
    TestTrue(TEXT("Enable accepted"),UProphecyAttackMotionInertiaLibrary::SetAttackMotionInertia(A,true));
    CaptureReset(A);Begin(A,Names,Parents,Pose,Pose);
    TestTrue(TEXT("Full upper window starts"),FilteringArms(A));
    UProphecyAttackMotionInertiaLibrary::SetAttackMotionInertia(A,false);
    TestFalse(TEXT("Disable cancels immediately"),FilteringArms(A));
    TestFalse(TEXT("Disabled apply remains bypass"),Apply(A,Pose,false));
    RestoreReset(A);TestTrue(TEXT("Reset restores configured value"),Configured(A));
    TestFalse(TEXT("Reset does not retain attack state"),FilteringArms(A));
    UProphecyAttackMotionInertiaLibrary::SetAttackMotionInertia(A,true,.04f,1,true);
    Begin(A,Names,Parents,Pose,Pose);TestFalse(TEXT("Core mode excludes arms"),FilteringArms(A));
    TestTrue(TEXT("Core runs after Armed"),Apply(A,Pose,true));
    Cancel(A);TestFalse(TEXT("Attack cancellation clears state"),Apply(A,Pose,true));
    TestFalse(TEXT("Invalid response rejected"),UProphecyAttackMotionInertiaLibrary::SetAttackMotionInertia(A,true,-1));
    TestFalse(TEXT("Invalid frames rejected"),UProphecyAttackMotionInertiaLibrary::SetAttackMotionInertia(A,true,.04f,-1));
    Remove(A);TestFalse(TEXT("Removal clears configuration"),Configured(A));
    RestoreReset(A);TestFalse(TEXT("Removal clears saved configuration"),Configured(A));
    World->DestroyWorld(false);return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FAttackMotionCostTest,"Prophecy.Attack.MotionInertia.Cost",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FAttackMotionCostTest::RunTest(const FString&)
{
    using namespace ProphecyAttackMotionInertia;
    FName Names[17];int32 Parents[17];FTransform Pose[17],Original[17],Alternate[17];
    Names[0]=TEXT("pelvis");Parents[0]=-1;Pose[0]=FTransform::Identity;
    for(int32 B=1;B<17;++B)
    {
        Names[B]=FName(*FString::Printf(TEXT("spine_%02d"),B));Parents[B]=B-1;
        Pose[B]=FTransform(FRotator(1,2,3),FVector(0,0,10))*Pose[B-1];
    }
    for(int32 B=0;B<17;++B)Original[B]=Pose[B];
    Alternate[0]=Pose[0];
    for(int32 B=1;B<17;++B)Alternate[B]=FTransform(FRotator(-2,-4,5),FVector(0,0,10))*Alternate[B-1];
    FState S;TestTrue(TEXT("Maximum supported upper hierarchy"),Prepare(S,FConfig{},Names,Parents,Pose,Pose));
    constexpr int32 Runs=10000;const double Start=FPlatformTime::Seconds();
    for(int32 I=0;I<Runs;++I)
    {
        for(int32 B=0;B<17;++B)Pose[B]=(I&1)?Original[B]:Alternate[B];
        Solve(S,Pose);
    }
    AddInfo(FString::Printf(TEXT("Moving 16-joint solve, including input copy: %.3f microseconds/agent/policy step"),
        (FPlatformTime::Seconds()-Start)*1.e6/Runs));
    TestTrue(TEXT("Finite output after long run"),!Pose[16].ContainsNaN());return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FAttackMotionAfterHitTest,"Prophecy.Attack.MotionInertia.AfterHit",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FAttackMotionAfterHitTest::RunTest(const FString&)
{
    using namespace ProphecyAttackMotionInertia;
    UWorld* World=UWorld::CreateWorld(EWorldType::Editor,false);
    auto* A=World?World->SpawnActor<AProphecyAgent>():nullptr;if(!A)return false;
    const FName Names[]={TEXT("pelvis"),TEXT("spine_01"),TEXT("clavicle_r"),TEXT("upperarm_r"),TEXT("lowerarm_r"),TEXT("hand_r")};
    const int32 Parents[]={-1,0,1,2,3,4};FTransform Pose[6],Before[6],Original[6];
    auto Make=[&](double Angle)
    {Pose[0]=FTransform::Identity;for(int32 B=1;B<6;++B)Pose[B]=FTransform(FRotator(0,Angle,0),FVector(0,0,20))*Pose[Parents[B]];};
    Make(0);for(int32 B=0;B<6;++B)Before[B]=Pose[B];
    UProphecyAttackMotionInertiaLibrary::SetAttackMotionInertia(A,true,.03f,0,false,true);
    Begin(A,Names,Parents,Before,Pose);
    for(double Angle:{10.,20.})
    {
        Make(Angle);for(int32 B=0;B<6;++B)Original[B]=Pose[B];
        TestFalse(TEXT("Armed gap is unfiltered"),Apply(A,Pose,true,false));
        TestFalse(TEXT("Gap keeps normal forearm publication"),FilteringArms(A));
        for(int32 B=0;B<6;++B)TestTrue(TEXT("Gap does not modify any pose"),Pose[B].Equals(Original[B],0));
    }
    const auto* Waiting=States.Find(A);TestNotNull(TEXT("Opt-in retains pending Hit state"),Waiting);
    if(Waiting)
    {
        TestTrue(TEXT("Restart observes latest pose, not wind-up"),Waiting->Joints[4].Rotation.Equals(FRotator(0,20,0).Quaternion(),1.e-8));
        TestTrue(TEXT("Restart observes current angular velocity"),FMath::IsNearlyEqual(Waiting->Joints[4].Velocity.Size(),FMath::DegreesToRadians(10.)/Step,1.e-6));
    }
    Make(30);TestTrue(TEXT("Hit prediction immediately resumes full upper"),Apply(A,Pose,true,true));
    TestTrue(TEXT("Forearm ownership follows resumed filter"),FilteringArms(A));
    TestTrue(TEXT("Hit remains latched if caller gate drops"),Apply(A,Pose,true,false));
    Cancel(A);TestFalse(TEXT("End cannot revive filter from Hit"),Apply(A,Pose,true,true));
    TestFalse(TEXT("End releases forearm convention ownership"),FilteringArms(A));
    UProphecyAttackMotionInertiaLibrary::SetAttackMotionInertia(A,true,.03f,1,true,true);
    Begin(A,Names,Parents,Before,Before);Make(10);
    TestTrue(TEXT("Core mode before Hit"),Apply(A,Pose,true,false));
    TestFalse(TEXT("Core mode leaves arms before Hit"),FilteringArms(A));
    Make(20);TestTrue(TEXT("Core mode expands at Hit"),Apply(A,Pose,true,true));
    TestTrue(TEXT("Core plus After Hit now includes arms"),FilteringArms(A));
    UProphecyAttackMotionInertiaLibrary::SetAttackMotionInertia(A,false);
    TestFalse(TEXT("Disable during tail is immediate"),Apply(A,Pose,true,true));
    Remove(A);World->DestroyWorld(false);return true;
}

#include "ProphecyFKReturn.h"
#include "ProphecyFKReturnData.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FAttackMotionSourceTest,"Prophecy.Attack.MotionInertia.SourceIsolation",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FAttackMotionSourceTest::RunTest(const FString&)
{
    using namespace ProphecyAttackMotionInertia;
    UWorld* World=UWorld::CreateWorld(EWorldType::Editor,false);
    auto* A=World?World->SpawnActor<AProphecyAgent>():nullptr;if(!A)return false;
    const FName Names[]={TEXT("pelvis"),TEXT("spine_01"),TEXT("hand_r")};const int32 Parents[]={-1,0,1};
    FTransform Pose[3]={FTransform::Identity,FTransform(FVector(0,0,10)),FTransform(FVector(0,0,20))};
    UProphecyAttackMotionInertiaLibrary::SetAttackMotionInertia(A,true,.03f,0);
    Begin(A,Names,Parents,Pose,Pose);
    Pose[1].SetRotation(FRotator(0,60,0).Quaternion());
    Pose[2]=FTransform(FVector(0,0,10))*Pose[1];
    const FTransform Source[]={Pose[0],Pose[1],Pose[2]};
    const FTransform Carrier(FRotator(0,35,0),FVector(100,200,0));
    Publish(A,Pose,Carrier,false,false);
    const auto History=PreviousSource(A);
    TestEqual(TEXT("Source history retains full pose"),History.Num(),3);
    for(int32 B=0;B<3;++B)TestTrue(TEXT("Entry feedback receives unsmoothed world source"),History[B].Equals(Source[B]*Carrier,1.e-8));
    TestFalse(TEXT("Displayed spine is smoothed"),Pose[1].Equals(Source[1],1.e-6));
    TestTrue(TEXT("Pelvis stays untouched"),Pose[0].Equals(Source[0],0));
    TranslateSource(A,FVector(20,0,0));
    TestTrue(TEXT("Explicit root relocation also moves source history"),PreviousSource(A)[1].GetLocation().Equals((Source[1]*Carrier).GetLocation()+FVector(20,0,0),1.e-8));
    for(int32 B=0;B<3;++B)Pose[B]=Source[B];
    Publish(A,Pose,Carrier,true,false);
    TestFalse(TEXT("Zero extra frames releases at Armed"),FilteringArms(A));
    for(int32 B=0;B<3;++B)TestTrue(TEXT("Released output is source"),Pose[B].Equals(Source[B],0));
    TestTrue(TEXT("Raw release endpoint needs no remaining source cache"),PreviousSource(A).IsEmpty());
    Cancel(A);TestTrue(TEXT("Attack end releases source history"),PreviousSource(A).IsEmpty());
    Remove(A);World->DestroyWorld(false);return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FAttackMotionReturnHandoffTest,"Prophecy.Attack.MotionInertia.ReturnHandoff",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FAttackMotionReturnHandoffTest::RunTest(const FString&)
{
    using namespace ProphecyAttackMotionInertia;
    UWorld* World=UWorld::CreateWorld(EWorldType::Editor,false);
    auto* A=World?World->SpawnActor<AProphecyAgent>():nullptr;if(!A)return false;
    TArray<FName> Names;TArray<int32> Parents;TArray<FTransform> Previous,Current,FinalPrevious,FinalCurrent,Local;
    Names.Add(TEXT("pelvis"));Parents.Add(-1);
    for(const auto& B:ProphecyFKReturn::Data::Bones){Parents.Add(Names.IndexOfByKey(FName(B.Parent)));Names.Add(FName(B.Name));}
    Previous.SetNum(17);Current.SetNum(17);Local.SetNum(17);
    auto Make=[&](double Angle)
    {
        Current[0]=FTransform::Identity;
        for(int32 B=1;B<17;++B)Current[B]=FTransform(FRotator(Angle,Angle*2,0),FVector(20,0,0))*Current[Parents[B]];
    };
    Make(0);Previous=Current;
    UProphecyAttackMotionInertiaLibrary::SetAttackMotionInertia(A,true,.08f,0,false,true);
    Begin(A,Names,Parents,Previous,Current);
    Make(5);Apply(A,Current,true,false);
    Make(10);TestTrue(TEXT("Post-hit sample accepted"),Apply(A,Current,true,true));FinalPrevious=Current;
    Make(20);TestTrue(TEXT("Final attack sample accepted"),Apply(A,Current,true,true));FinalCurrent=Current;
    // Match StopAgentNNAttack's ownership order: cancel filter, seed FK from accepted buffers.
    Cancel(A);
    ProphecyFKReturn::Begin(A,TEXT("slashL"),Names,Parents,FinalPrevious,FinalCurrent,1.,float(Step));
    TestTrue(TEXT("Return owns upper body after stop"),ProphecyFKReturn::IsActive(A));
    Make(-40);Previous=Current;
    TestTrue(TEXT("Return publishes accepted boundary"),ProphecyFKReturn::Apply(A,1.,Previous,Current,Local));
    for(int32 B=1;B<17;++B)
    {
        TestTrue(TEXT("Return keeps last filtered pose without a snap"),Current[B].Equals(FinalCurrent[B],1.e-7));
        TestTrue(TEXT("Return keeps preceding filtered pose for momentum"),Previous[B].Equals(FinalPrevious[B],1.e-7));
    }
    ProphecyFKReturn::FCurve Curve;ProphecyFKReturn::FProfile Profile;
    TestTrue(TEXT("Return curve prepares from accepted samples"),ProphecyFKReturn::Prepare(Curve,Profile,1,Names,Parents,FinalPrevious,FinalCurrent,float(Step)));
    // The new seed includes world motion and subtracts the idle/parent return
    // velocity. Check the resulting initial world motion, not the retired local delta.
    Curve.SetAlphaHold(1.f);auto Near=FinalCurrent;constexpr float Epsilon=1.e-5f;
    Curve.Apply(Epsilon,Near);
    for(const auto& B:Curve.Bones)if(B.Group<ProphecyFKReturn::GroupCount && Profile.Weights[B.Group]*Profile.Inertia>0)
    {
        ProphecyFKReturn::FArc Rate;
        Rate.Set(FQuat4f(FinalCurrent[B.Index].GetRotation()*FinalPrevious[B.Index].GetRotation().Inverse()),1.f/float(Step));
        const FQuat4f Actual(Near[B.Index].GetRotation()*FinalCurrent[B.Index].GetRotation().Inverse());
        TestTrue(TEXT("Return continues filtered world angular motion"),Actual.Equals(Rate.At(Epsilon),2.e-5f));
    }
    const auto Accepted=Current;
    TestFalse(TEXT("Hit cannot apply attack inertia inside return"),Apply(A,Current,true,true));
    for(int32 B=0;B<17;++B)TestTrue(TEXT("No double filtering after stop"),Current[B].Equals(Accepted[B],0));
    ProphecyFKReturn::Remove(A);Remove(A);World->DestroyWorld(false);return true;
}

#endif


void ProphecyNNModifierDebug::AttackMotion(FReport& R)
{
    using namespace ProphecyAttackMotionInertia;
    const auto* S=States.Find(R.Agent);if(!R.Attack || !S || !S->FilteringNow)return;
    R.Add(TEXT("AttackMotion"),TEXT("POSE+PHYSICS"),TEXT("Attack motion inertia (NN feedback isolated)"),
        FString::Printf(TEXT("%s | response %.4g | Armed+%d ticks | %s"),
        S->Config.CoreOnly&&!S->SawHit?TEXT("core, no clavicles/arms"):TEXT("whole upper"),S->Config.Response,S->Config.After,
        S->SawHit?TEXT("after Hit"):S->SawArmed?TEXT("armed"):TEXT("pre-armed")));
}
