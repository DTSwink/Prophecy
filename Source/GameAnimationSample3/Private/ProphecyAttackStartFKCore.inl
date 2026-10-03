#include "ProphecyAttackStartFKCore.h"
#include "ProphecyAttackStartInertiaLibrary.h"
#include "ProphecyAgent.h"
#include "ProphecyNNPoseTypes.h"
#include "ProphecyBlendClock.h"
#include "ProphecyPelvisInertiaMath.h"
#include "Engine/World.h"

namespace ProphecyAttackStartFKCore
{
using K=ProphecyBlendClock::EKind;
struct FConfig { float Hold=.1f, Blend=.3f, Response=.25f, Momentum=1.f, Alpha=1.f; };
struct FJoint
{
    int32 Bone=INDEX_NONE, Parent=INDEX_NONE;
    bool Core=false;
    FQuat Rotation=FQuat::Identity, Accepted=FQuat::Identity;
    FVector Velocity=FVector::ZeroVector;
    FTransform Local;
};
struct FState
{
    FConfig Config;
    TArray<FJoint,TInlineAllocator<24>> Joints;
    double Elapsed=0;
    bool Applied=false;
};
static TMap<TWeakObjectPtr<const AProphecyAgent>,FConfig> Configs,Baselines;
static TMap<TWeakObjectPtr<const AProphecyAgent>,FState> States;
static FDelegateHandle Cleanup;
static void EnsureCleanup()
{
    if(Cleanup.IsValid())return;
    Cleanup=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* W,bool,bool)
    {
        auto Clean=[W](auto& Map){for(auto It=Map.CreateIterator();It;++It)
            if(!It.Key().IsValid() || It.Key()->GetWorld()==W)It.RemoveCurrent();};
        Clean(Configs);Clean(Baselines);Clean(States);
    });
}
bool Active(const AProphecyAgent* A){return !States.IsEmpty() && States.Contains(A);}
bool AwaitingFirstPose(const AProphecyAgent* A)
{
    const auto* State=States.IsEmpty()?nullptr:States.Find(A);
    return State && !State->Applied;
}
bool Configured(const AProphecyAgent* A){return !Configs.IsEmpty() && Configs.Contains(A);}
void Cancel(const AProphecyAgent* A){if(!States.IsEmpty() && States.Remove(A))ProphecyBlendClock::Stop(A,K::AttackStartFKCore);}
void Remove(const AProphecyAgent* A){Cancel(A);Configs.Remove(A);Baselines.Remove(A);}
void CaptureReset(const AProphecyAgent* A){if(const auto* C=Configs.Find(A))Baselines.Add(A,*C);else Baselines.Remove(A);}
void RestoreReset(const AProphecyAgent* A){Cancel(A);Configs.Remove(A);if(const auto* C=Baselines.Find(A))Configs.Add(A,*C);}
void ForgetReset(const AProphecyAgent* A){Baselines.Remove(A);}
static void Seed(FJoint& J,const FQuat& Before,const FQuat& After,double Interval,float Momentum)
{
    J.Rotation=J.Accepted=After;
    J.Velocity=ProphecyPelvisInertia::RotationVector(After*Before.Inverse())*(Momentum/Interval);
}
void Begin(const AProphecyAgent* A,TConstArrayView<FName> Names,TConstArrayView<int32> Parents,
    TConstArrayView<FName> CoreNames)
{
    Cancel(A);
    const auto* C=Configs.IsEmpty()?nullptr:Configs.Find(A);if(!C)return;
    TArray<FName> SampleNames;TArray<FTransform> Future,Visible;float Alpha=1;FProphecyNNPoseSnapshot Snapshot;
    if(Names.Num()!=Parents.Num() || !A->ReadNNFutureWorldPoseWithSnapshot(SampleNames,Future,Visible,Alpha,Snapshot))return;
    int32 Id;float Interval;bool Interpolate;
    if(!A->GetNNPoseDataSource(Id,Interval,Interpolate) || Interval<=0)return;
    FState State;State.Config=*C;
    // The model hierarchy is parent-first. Cache only the core and its descendants.
    // No pelvis/leg correction, and no independent arm/hand springs.
    for(int32 B=0;B<Names.Num();++B)
    {
        const int32 P=Parents[B];
        if(P==INDEX_NONE)continue;
        if(P<0 || P>=B)return;
        const bool Core=CoreNames.Contains(Names[B]);
        if(!Core && !State.Joints.ContainsByPredicate([P](const FJoint& J){return J.Bone==P;}))continue;
        FJoint J;J.Bone=B;J.Parent=P;J.Core=Core;
        if(Core)
        {
            const int32 F=SampleNames.IndexOfByKey(Names[B]),FP=SampleNames.IndexOfByKey(Names[P]);
            const int32 O=Snapshot.BoneNames.IndexOfByKey(Names[B]),OP=Snapshot.BoneNames.IndexOfByKey(Names[P]);
            if(!Future.IsValidIndex(F)||!Future.IsValidIndex(FP)||!Snapshot.PreviousComponentTransforms.IsValidIndex(O)
                ||!Snapshot.PreviousComponentTransforms.IsValidIndex(OP))return;
            // Seed the outgoing published endpoint, as with attack-start hands.
            // Relative rotations remove carrier/pelvis motion from angular momentum.
            Seed(J,(Snapshot.PreviousComponentTransforms[OP].GetRotation().Inverse()*
                    Snapshot.PreviousComponentTransforms[O].GetRotation()).GetNormalized(),
                (Future[FP].GetRotation().Inverse()*Future[F].GetRotation()).GetNormalized(),Interval,C->Momentum);
        }
        State.Joints.Add(J);
    }
    if(State.Joints.IsEmpty())return;
    States.Add(A,MoveTemp(State));ProphecyBlendClock::Start(A,K::AttackStartFKCore,double(C->Hold)+C->Blend);
}
static double Weight(const FConfig& C,double Elapsed)
{
    const double T=Elapsed<C.Hold?0.:C.Blend>0?FMath::Clamp((Elapsed-C.Hold)/C.Blend,0.,1.):1.;
    return C.Alpha*(1.-T*T*(3.-2.*T));
}
static void RestoreEntryCore(FState& State,TArrayView<FTransform> Pose)
{
    // Physical entry retains the displayed pelvis to avoid a positional rewind.
    // The core spring starts at the outgoing policy endpoint, however: retain
    // that endpoint's local rotations instead of repeating the displayed core
    // for one game tick. Descendant locals and the pelvis/legs remain intact.
    for(auto& J:State.Joints)J.Local=Pose[J.Bone].GetRelativeTransform(Pose[J.Parent]);
    for(auto& J:State.Joints)
    {
        if(J.Core)J.Local.SetRotation(FQuat::Slerp(J.Local.GetRotation(),J.Rotation,State.Config.Alpha).GetNormalized());
        Pose[J.Bone]=J.Local*Pose[J.Parent];
    }
}
void PrepareEntryPose(const AProphecyAgent* A,TArrayView<FTransform> Pose)
{
    auto* State=States.IsEmpty()?nullptr:States.Find(A);
    if(!State || State->Applied || !Pose.IsValidIndex(State->Joints.Last().Bone))return;
    // Presentation history only: do not integrate the spring or consume its clock.
    RestoreEntryCore(*State,Pose);
}
static void Spring(FJoint& J,const FQuat& Goal,double Response,double Dt)
{
    if(Dt<=0)return;
    const double W=2./Response,E=FMath::Exp(-W*Dt);
    const FVector X=ProphecyPelvisInertia::RotationVector(J.Rotation*Goal.Inverse()),V=J.Velocity+W*X;
    J.Rotation=(ProphecyPelvisInertia::RotationIncrement((X+V*Dt)*E)*Goal).GetNormalized();
    J.Velocity=(J.Velocity-W*V*Dt)*E;
}
static void Solve(FState& State,TArrayView<FTransform> Pose,double Dt,bool Reuse)
{
    // Read all NN locals before modifying parents; reuse existing scratch storage.
    for(auto& J:State.Joints)J.Local=Pose[J.Bone].GetRelativeTransform(Pose[J.Parent]);
    const double W=Weight(State.Config,State.Elapsed);
    for(auto& J:State.Joints)
    {
        if(J.Core)
        {
            if(!Reuse)
            {
                const FQuat Goal=J.Local.GetRotation();
                Spring(J,Goal,State.Config.Response,Dt);
                J.Accepted=FQuat::Slerp(Goal,J.Rotation,W).GetNormalized();
            }
            J.Local.SetRotation(J.Accepted);
        }
        Pose[J.Bone]=J.Local*Pose[J.Parent];
    }
}
bool Apply(const AProphecyAgent* A,TArrayView<FTransform> Pose,double PoseStepSeconds)
{
    auto* State=States.IsEmpty()?nullptr:States.Find(A);if(!State)return false;
    const double Dt=ProphecyBlendClock::Consume(A,K::AttackStartFKCore);State->Elapsed+=Dt;
    if(State->Elapsed+1.e-6>=double(State->Config.Hold)+State->Config.Blend){Cancel(A);return false;}
    if(!Pose.IsValidIndex(State->Joints.Last().Bone)){Cancel(A);return false;}
    // Policy endpoints span their fixed NN interval; duplicate publications never integrate twice.
    Solve(*State,Pose,Dt>0?PoseStepSeconds:0.,State->Applied && Dt<=0);
    State->Applied=true;return true;
}
}

bool UProphecyAttackStartInertiaLibrary::SetAttackStartFKCoreInertia(AProphecyAgent* A,bool Enabled,
    float Hold,float Blend,float Response,float Momentum,float Alpha)
{
    using namespace ProphecyAttackStartFKCore;
    if(!IsInGameThread()||!IsValid(A)||A->IsActorBeingDestroyed()||!A->GetWorld()||A->GetWorld()->bIsTearingDown)return false;
    for(float V:{Hold,Blend,Response,Momentum})if(!FMath::IsFinite(V)||V<0)return false;
    if(!FMath::IsFinite(Alpha))return false;
    Alpha=FMath::Clamp(Alpha,0.f,1.f);
    if(!Enabled||Alpha==0||Response==0||(Hold==0&&Blend==0)){Cancel(A);Configs.Remove(A);return true;}
    EnsureCleanup();Configs.Add(A,FConfig{Hold,Blend,Response,Momentum,Alpha});
    return true; // Settings latch on the next attack; repeated setters never restart an active spring.
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEntryFKCoreSpaceTest,"Prophecy.NN.AttackEntry.FKCoreSpace",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FEntryFKCoreSpaceTest::RunTest(const FString&)
{
    using namespace ProphecyAttackStartFKCore;
    FState S;S.Config.Hold=1;
    FTransform Pose[5],Original[5];
    Pose[0]=FTransform(FRotator(12,70,3),FVector(30,40,80));
    for(int B=1;B<5;++B)
    {
        FJoint J;J.Bone=B;J.Parent=B-1;J.Core=B<3;
        Seed(J,FQuat::Identity,FQuat::Identity,1./30,1);
        Pose[B]=FTransform(FRotator(10*B,7*B,3*B),FVector(3,2,10))*Pose[B-1];
        S.Joints.Add(J);
    }
    for(int B=0;B<5;++B)Original[B]=Pose[B];
    Solve(S,Pose,0,false);
    TestTrue(TEXT("Pelvis is untouched"),Pose[0].Equals(Original[0],0));
    for(int B=1;B<5;++B)
    {
        const auto Local=Pose[B].GetRelativeTransform(Pose[B-1]);
        const auto Before=Original[B].GetRelativeTransform(Original[B-1]);
        TestTrue(TEXT("All attachment translations preserved"),Local.GetLocation().Equals(Before.GetLocation(),1.e-7));
        TestTrue(TEXT("Only core local rotations receive inertia"),Local.GetRotation().Equals(B<3?FQuat::Identity:Before.GetRotation(),1.e-7));
    }
    const FTransform Shift(FRotator(-20,110,40),FVector(200,0,100));
    FTransform Shifted[5];for(int B=0;B<5;++B)Shifted[B]=Original[B]*Shift;
    FState ShiftState=S;Solve(ShiftState,Shifted,0,false);
    for(int B=0;B<5;++B)TestTrue(TEXT("Carrier motion does not change local inertia"),Shifted[B].Equals(Pose[B]*Shift,1.e-6));
    FJoint J;const FQuat R(FVector::UpVector,.1);
    Seed(J,FQuat::Identity,R,1./30,1);Spring(J,R,.25,1./30);
    TestTrue(TEXT("Outgoing angular momentum continues beyond entry pose"),
        ProphecyPelvisInertia::RotationVector(J.Rotation).Z>.1);
    Seed(J,FQuat::Identity,R,1./30,0);Spring(J,R,.25,1./30);
    TestTrue(TEXT("Momentum zero removes outgoing drift"),J.Rotation.Equals(R,1.e-7));
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEntryFKCoreBoundaryTest,"Prophecy.NN.AttackEntry.FKCoreBoundary",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FEntryFKCoreBoundaryTest::RunTest(const FString&)
{
    using namespace ProphecyAttackStartFKCore;
    const FTransform Pelvis(FRotator(10,60,-8),FVector(30,50,80));
    const FTransform LocalArm(FRotator(7,-15,20),FVector(0,20,5));
    const FQuat Endpoint(FVector::UpVector,.2);
    for(float Alpha:{0.f,.5f,1.f})
    {
        FState S;S.Config.Alpha=Alpha;
        FJoint Core;Core.Bone=1;Core.Parent=0;Core.Core=true;
        Seed(Core,FQuat::Identity,Endpoint,1./30,1);S.Joints.Add(Core);
        FJoint Arm;Arm.Bone=2;Arm.Parent=1;S.Joints.Add(Arm);
        FTransform Pose[3]={Pelvis,FTransform(FQuat(FVector::UpVector,.1),FVector(0,0,20))*Pelvis,FTransform::Identity};
        Pose[2]=LocalArm*Pose[1];
        RestoreEntryCore(S,Pose);
        const auto Local=Pose[1].GetRelativeTransform(Pose[0]);
        TestTrue(TEXT("Core advances to outgoing endpoint according to alpha"),
            Local.GetRotation().Equals(FQuat(FVector::UpVector,.1+.1*Alpha),1.e-8));
        TestTrue(TEXT("Physical-entry pelvis history remains untouched"),Pose[0].Equals(Pelvis,0));
        TestTrue(TEXT("Core attachment offset retained"),Local.GetLocation().Equals(FVector(0,0,20),1.e-8));
        TestTrue(TEXT("Carried arm keeps its local transform"),Pose[2].GetRelativeTransform(Pose[1]).Equals(LocalArm,1.e-8));
        TestTrue(TEXT("History preparation does not spend spring time or momentum"),
            S.Elapsed==0 && !S.Applied && S.Joints[0].Rotation.Equals(Endpoint,1.e-8) &&
            S.Joints[0].Velocity.Equals(Core.Velocity,0));
    }
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEntryFKCoreAttachmentTest,"Prophecy.NN.AttackEntry.FKCoreAttachment",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FEntryFKCoreAttachmentTest::RunTest(const FString&)
{
    using namespace ProphecyAttackStartFKCore;
    const FTransform Pelvis(FRotator(10,45,7),FVector(40,20,80));
    const FTransform Authored(FRotator(5,8,3),FVector(0,0,20));
    const FTransform Arm(FRotator(4,-7,20),FVector(2,15,3));
    for(float Alpha:{0.f,.5f,1.f})for(double Elapsed:{0.,.25,.4})
    {
        FState S;S.Config.Alpha=Alpha;S.Elapsed=Elapsed;
        FJoint J;J.Bone=1;J.Parent=0;J.Core=true;
        Seed(J,FQuat::Identity,FQuat(FVector::UpVector,.3),1./30,1);S.Joints.Add(J);
        FJoint Child;Child.Bone=2;Child.Parent=1;S.Joints.Add(Child);
        FTransform Pose[3]={Pelvis,Authored*Pelvis,Arm*(Authored*Pelvis)};
        Solve(S,Pose,0,false);
        TestTrue(TEXT("NN attachment offsets are untouched at every alpha and window phase"),
            Pose[1].GetRelativeTransform(Pose[0]).GetLocation().Equals(Authored.GetLocation(),1.e-8));
        TestTrue(TEXT("Descendant local transform remains intact"),Pose[2].GetRelativeTransform(Pose[1]).Equals(Arm,1.e-8));
        TestTrue(TEXT("Pelvis remains intact"),Pose[0].Equals(Pelvis,0));
    }
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEntryFKCoreNNSeedTest,"Prophecy.NN.AttackEntry.FKCoreNNSeed",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FEntryFKCoreNNSeedTest::RunTest(const FString&)
{
    using namespace ProphecyAttackStartFKCore;
    const FTransform Parent0(FRotator(10,30,7),FVector(5,10,80));
    const FTransform Parent1(FRotator(-7,55,12),FVector(8,20,85));
    const FTransform Local0(FQuat(FVector::UpVector,.1),FVector(0,0,20));
    const FTransform Local1(FQuat(FVector::UpVector,.2),FVector(0,0,20));
    const FQuat Before=(Local0*Parent0).GetRelativeTransform(Parent0).GetRotation();
    const FQuat After=(Local1*Parent1).GetRelativeTransform(Parent1).GetRotation();
    FJoint J;Seed(J,Before,After,1./30.,1);
    TestTrue(TEXT("NN core momentum excludes moving parent's angular motion"),J.Velocity.Equals(FVector(0,0,3),1.e-7));
    TestTrue(TEXT("Entry uses the exact published NN endpoint"),J.Rotation.Equals(After,1.e-7));
    Seed(J,Before,After,1./30.,0);
    TestTrue(TEXT("Momentum zero retains NN local pose"),J.Rotation.Equals(After,1.e-7)&&J.Velocity.IsNearlyZero());
    Seed(J,Before,(Local0*Parent1).GetRelativeTransform(Parent1).GetRotation(),1./30.,1);
    TestTrue(TEXT("Common parent motion produces no relative core inertia"),J.Velocity.IsNearlyZero(1.e-7));
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEntryFKCoreClockTest,"Prophecy.NN.AttackEntry.FKCoreClock",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FEntryFKCoreClockTest::RunTest(const FString&)
{
    using namespace ProphecyAttackStartFKCore;using L=UProphecyAttackStartInertiaLibrary;
    UWorld* W=UWorld::CreateWorld(EWorldType::Editor,false);auto* A=W?W->SpawnActor<AProphecyAgent>():nullptr;if(!A)return false;
    FTransform Pose[2];
    TestFalse(TEXT("Disabled apply has no state"),Apply(A,Pose,1./30));
    Begin(A,TConstArrayView<FName>(),TConstArrayView<int32>(),TConstArrayView<FName>());
    TestFalse(TEXT("Disabled entry needs no pose data"),Active(A));
    TestTrue(TEXT("Default node disables"),L::SetAttackStartFKCoreInertia(A));
    TestFalse(TEXT("Default node retains no configuration"),Configs.Contains(A));
    L::SetAttackStartFKCoreInertia(A,true,.1,.3,.25,1,.5);CaptureReset(A);
    FQuat Reference=FQuat::Identity;
    for(float FPS:{5.f,30.f,60.f,120.f})
    {
        FState S;S.Config=Configs.FindChecked(A);FJoint J;J.Bone=1;J.Parent=0;J.Core=true;
        Seed(J,FQuat::Identity,FQuat(FVector::UpVector,.1),1./30,1);S.Joints.Add(J);
        States.Add(A,S);ProphecyBlendClock::Start(A,K::AttackStartFKCore,.4);
        for(int Tick=1;Tick<=24;++Tick)
        {
            FWorldDelegates::OnWorldPreActorTick.Broadcast(W,LEVELTICK_All,Tick==7?2.f:1.f/FPS);
            if(Tick%2)continue;
            Pose[0]=FTransform::Identity;Pose[1]=FTransform(FQuat(FVector::UpVector,.5));
            const bool Applied=Apply(A,Pose,1./30);
            TestEqual(TEXT("Retires on tick 24 regardless of FPS or hitch"),Applied,Tick<24);
            if(Tick==12)
            {
                if(FPS==5)Reference=Pose[1].GetRotation();
                else TestTrue(TEXT("Identical motion at the same tick"),Pose[1].GetRotation().Equals(Reference,1.e-10));
                const auto Before=Pose[1];Apply(A,Pose,1./30);
                TestTrue(TEXT("Duplicate publication does not integrate"),Before.Equals(Pose[1],1.e-10));
                L::SetAttackStartFKCoreInertia(A,true,.1,.3,.25,1,.5);
                TestTrue(TEXT("Repeated configuration does not restart"),States.FindChecked(A).Elapsed>.19);
            }
        }
        TestFalse(TEXT("Completed state retired"),Active(A));
    }
    TestTrue(TEXT("Hold keeps alpha"),FMath::IsNearlyEqual(Weight(Configs.FindChecked(A),.05),.5,1.e-7));
    TestTrue(TEXT("Blend midpoint halves alpha"),FMath::IsNearlyEqual(Weight(Configs.FindChecked(A),.25),.25,1.e-7));
    L::SetAttackStartFKCoreInertia(A,true,.1,.3,0);TestFalse(TEXT("Response zero bypasses"),Configs.Contains(A));
    RestoreReset(A);TestTrue(TEXT("Reset restores configuration only"),Configs.Contains(A)&&!Active(A));
    L::SetAttackStartFKCoreInertia(A,true,.1,.3,.25,1,0);TestFalse(TEXT("Alpha zero bypasses"),Configs.Contains(A));
    Remove(A);W->DestroyWorld(false);return !HasAnyErrors();
}
#endif
