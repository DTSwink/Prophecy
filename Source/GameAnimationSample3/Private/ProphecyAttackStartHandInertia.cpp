#include "ProphecyAttackStartHandInertia.h"
#include "ProphecyAttackStartInertiaLibrary.h"
#include "ProphecyAgent.h"
#include "ProphecyForearmStretch.h"
#include "ProphecyNNPoseTypes.h"
#include "ProphecyBlendClock.h"
#include "ProphecyHandChainMath.h"
#include "ProphecyPelvisInertiaMath.h"
#include "Engine/World.h"

namespace ProphecyAttackStartHands
{
using K=ProphecyBlendClock::EKind;
struct FConfig
{
    float Hold=.1f,Blend=.3f,Reference=1,Response=.25f,Momentum=1,Alpha=1;
    bool Hand[2]={true,true};
};
struct FHand
{
    FVector Position,Velocity,AngularVelocity,LocalUpper,LocalPole;
    double ForearmLength=0;
    FQuat Rotation;
    FTransform Accepted[3]; // In the blended locomotion-root/spine reference.
};
struct FState
{
    FConfig Config;
    FHand Hand[2];
    int32 Indices[8]={-1,-1,-1,-1,-1,-1,-1,-1};
    double Elapsed=0;
    bool Applied=false;
};
static const FName Bones[]={TEXT("pelvis"),TEXT("spine_05"),TEXT("upperarm_l"),TEXT("lowerarm_l"),TEXT("hand_l"),
    TEXT("upperarm_r"),TEXT("lowerarm_r"),TEXT("hand_r")};
static TMap<TWeakObjectPtr<const AProphecyAgent>,FConfig> Configs,Baselines;
static TMap<TWeakObjectPtr<const AProphecyAgent>,FState> States;
static FDelegateHandle Cleanup;
static FTransform Reference(const FTransform& Root,const FTransform& Spine,float Alpha)
{
    return FTransform(FQuat::Slerp(Root.GetRotation(),Spine.GetRotation(),Alpha).GetNormalized(),
        FMath::Lerp(Root.GetLocation(),Spine.GetLocation(),Alpha));
}
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
void Cancel(const AProphecyAgent* A){if(!States.IsEmpty() && States.Remove(A))ProphecyBlendClock::Stop(A,K::AttackStartHands);}
void Remove(const AProphecyAgent* A){Cancel(A);Configs.Remove(A);Baselines.Remove(A);}
void CaptureReset(const AProphecyAgent* A){if(const auto* C=Configs.Find(A))Baselines.Add(A,*C);else Baselines.Remove(A);}
void RestoreReset(const AProphecyAgent* A){Cancel(A);Configs.Remove(A);if(const auto* C=Baselines.Find(A))Configs.Add(A,*C);}
void ForgetReset(const AProphecyAgent* A){Baselines.Remove(A);}
static void Seed(FState& State,const FTransform* Previous,const FTransform* Current,const FTransform* Future,double Dt,
    const FTransform& PreviousRoot,const FTransform& Root)
{
    const auto& C=State.Config;
    const FTransform P=Reference(PreviousRoot,Previous[1],C.Reference);
    const FTransform R=Reference(Root,Current[1],C.Reference);
    const FTransform F=Reference(Root,Future[1],C.Reference);
    for(int S=0;S<2;++S)if(C.Hand[S])
    {
        auto& M=State.Hand[S];const int B=2+S*3;
        for(int J=0;J<3;++J)M.Accepted[J]=Current[B+J].GetRelativeTransform(R);
        const FTransform Before=Previous[B+2].GetRelativeTransform(P),After=Future[B+2].GetRelativeTransform(F);
        M.ForearmLength=FVector::Distance(M.Accepted[1].GetLocation(),M.Accepted[2].GetLocation());
        M.Position=M.Accepted[2].GetLocation();M.Rotation=M.Accepted[2].GetRotation();
        M.Velocity=(After.GetLocation()-Before.GetLocation())*(C.Momentum/Dt);
        M.AngularVelocity=ProphecyPelvisInertia::RotationVector(After.GetRotation()*Before.GetRotation().Inverse())*(C.Momentum/Dt);
        M.LocalUpper=M.Accepted[0].InverseTransformVectorNoScale(M.Accepted[1].GetLocation()-M.Accepted[0].GetLocation());
        const FVector Axis=(M.Accepted[2].GetLocation()-M.Accepted[0].GetLocation()).GetSafeNormal();
        M.LocalPole=M.Accepted[0].InverseTransformVectorNoScale(ProphecyHandChain::Plane(
            M.Accepted[1].GetLocation()-M.Accepted[0].GetLocation(),Axis,M.Accepted[0].GetRotation().GetAxisZ()));
    }
}
void Begin(const AProphecyAgent* A,const FTransform& PreviousRoot,const FTransform& Root)
{
    Cancel(A);
    const auto* C=Configs.IsEmpty()?nullptr:Configs.Find(A);if(!C)return;
    // Entry-only sampling; no rolling pose history and no disabled bone reads.
    TArray<FName> Names;TArray<FTransform> Future,Visible;float Alpha=1;FProphecyNNPoseSnapshot Snapshot;
    if(!A->ReadNNFutureWorldPoseWithSnapshot(Names,Future,Visible,Alpha,Snapshot))return;
    int32 Id;float Interval;bool Interpolate;
    if(!A->GetNNPoseDataSource(Id,Interval,Interpolate) || Interval<=0)return;
    FTransform P[8],F[8];
    for(int I=0;I<8;++I)
    {
        const int N=Names.IndexOfByKey(Bones[I]),Old=Snapshot.BoneNames.IndexOfByKey(Bones[I]);
        if(!Visible.IsValidIndex(N)||!Future.IsValidIndex(N)||!Snapshot.PreviousComponentTransforms.IsValidIndex(Old))return;
        P[I]=Snapshot.PreviousComponentTransforms[Old]*Snapshot.PreviousComponentWorldTransform;
        F[I]=Future[N];
    }
    // The next attack interval begins at the preceding published endpoint.
    // Seeding from the halfway displayed pose would rewind a half-entry's
    // immediate publication and lag one half interval at full entry.
    FState State;State.Config=*C;Seed(State,P,F,F,Interval,PreviousRoot,Root);
    States.Add(A,MoveTemp(State));ProphecyBlendClock::Start(A,K::AttackStartHands,double(C->Hold)+C->Blend);
}
static double Weight(const FConfig& C,double Elapsed)
{
    const double T=Elapsed<C.Hold?0.:C.Blend>0?FMath::Clamp((Elapsed-C.Hold)/C.Blend,0.,1.):1.;
    return C.Alpha*(1.-T*T*(3.-2.*T));
}
static void Spring(FHand& M,const FTransform& Goal,double Response,double Dt)
{
    if(Dt<=0)return;
    const double W=2./Response,E=FMath::Exp(-W*Dt);
    const FVector X=M.Position-Goal.GetLocation(),C=M.Velocity+W*X;
    M.Position=Goal.GetLocation()+(X+C*Dt)*E;M.Velocity=(M.Velocity-W*C*Dt)*E;
    const FVector R=ProphecyPelvisInertia::RotationVector(M.Rotation*Goal.GetRotation().Inverse()),V=M.AngularVelocity+W*R;
    M.Rotation=(ProphecyPelvisInertia::RotationIncrement((R+V*Dt)*E)*Goal.GetRotation()).GetNormalized();
    M.AngularVelocity=(M.AngularVelocity-W*V*Dt)*E;
}
static void Solve(FState& State,TArrayView<FTransform> Pose,const FTransform& Carrier,double Dt,const FTransform& Root,bool VariableLength=false)
{
    const auto& C=State.Config;const double W=Weight(C,State.Elapsed),Follow=1.-W;
    const FTransform Frame=Reference(Root,Pose[State.Indices[1]]*Carrier,C.Reference);
    for(int S=0;S<2;++S)if(C.Hand[S])
    {
        auto& M=State.Hand[S];FTransform Goal[3];const int B=2+S*3;
        for(int J=0;J<3;++J)Goal[J]=(Pose[State.Indices[B+J]]*Carrier).GetRelativeTransform(Frame);
        Spring(M,Goal[2],C.Response,Dt);
        FTransform Target(FQuat::Slerp(Goal[2].GetRotation(),M.Rotation,W).GetNormalized(),FMath::Lerp(Goal[2].GetLocation(),M.Position,W));
        // The source hinge guides the elbow; the inertial wrist remains bounded
        // by the connected arm. No whole-skeleton solve or physical force.
        const FVector LocalUpper=M.LocalUpper;
        ProphecyHandChain::Resolve(M.Accepted[0],M.Accepted[1],M.Accepted[2],Goal[0],Goal[1],Goal[2],
            Target,LocalUpper,M.LocalPole,Follow,VariableLength?FVector::Distance(Goal[1].GetLocation(),Goal[2].GetLocation()):M.ForearmLength);
        if(!Goal[2].GetLocation().Equals(Target.GetLocation(),1.e-5))
        {
            const FVector Normal=(Target.GetLocation()-Goal[2].GetLocation()).GetSafeNormal();
            M.Position=Goal[2].GetLocation();
            const double Outward=FVector::DotProduct(M.Velocity,Normal);if(Outward>0)M.Velocity-=Normal*Outward;
        }
        for(int J=0;J<3;++J){M.Accepted[J]=Goal[J];Pose[State.Indices[B+J]]=(Goal[J]*Frame).GetRelativeTransform(Carrier);}
    }
}
uint8 Apply(const AProphecyAgent* A,TConstArrayView<FName> Names,TArrayView<FTransform> Pose,
    const FTransform& Carrier,double PoseStepSeconds,const FTransform& Root)
{
    auto* State=States.IsEmpty()?nullptr:States.Find(A);if(!State)return false;
    const double Dt=ProphecyBlendClock::Consume(A,K::AttackStartHands);State->Elapsed+=Dt;
    // Match the shared clock's rounded tick boundary despite float pin values
    // such as 0.1 + 0.3; otherwise its finished clock can leave a tiny live tail.
    if(State->Elapsed+1.e-6>=double(State->Config.Hold)+State->Config.Blend){Cancel(A);return false;}
    if(State->Indices[0]==INDEX_NONE)for(int I=0;I<8;++I)
    {
        State->Indices[I]=Names.IndexOfByKey(Bones[I]);
        if(!Pose.IsValidIndex(State->Indices[I])){Cancel(A);return false;}
    }
    // Half/full switches may republish the same sample: never solve/integrate twice.
    if(State->Applied && Dt<=0)
    {
        const FTransform Frame=Reference(Root,Pose[State->Indices[1]]*Carrier,State->Config.Reference);
        for(int S=0;S<2;++S)if(State->Config.Hand[S])for(int J=0;J<3;++J)
            Pose[State->Indices[2+S*3+J]]=(State->Hand[S].Accepted[J]*Frame).GetRelativeTransform(Carrier);
    }
    else Solve(*State,Pose,Carrier,Dt>0?PoseStepSeconds:0.,Root,ProphecyForearmStretch::OwnsPosition(A));
    State->Applied=true;return uint8((State->Config.Hand[0]?1:0)|(State->Config.Hand[1]?2:0));
}
}

bool UProphecyAttackStartInertiaLibrary::SetAttackStartHandInertia(AProphecyAgent* A,bool Enabled,
    float Hold,float Blend,float ReferenceAlpha,float Response,float Momentum,float Alpha,bool Left,bool Right)
{
    using namespace ProphecyAttackStartHands;
    if(!IsInGameThread()||!IsValid(A)||A->IsActorBeingDestroyed()||!A->GetWorld()||A->GetWorld()->bIsTearingDown)return false;
    for(float V:{Hold,Blend,Response,Momentum})if(!FMath::IsFinite(V)||V<0)return false;
    if(!FMath::IsFinite(ReferenceAlpha)||!FMath::IsFinite(Alpha))return false;
    Alpha=FMath::Clamp(Alpha,0.f,1.f);ReferenceAlpha=FMath::Clamp(ReferenceAlpha,0.f,1.f);
    if(!Enabled||Alpha==0||Response==0||(Hold==0&&Blend==0)||(!Left&&!Right)){Cancel(A);Configs.Remove(A);return true;}
    EnsureCleanup();Configs.Add(A,FConfig{Hold,Blend,ReferenceAlpha,Response,Momentum,Alpha,{Left,Right}});
    return true; // Configure next entry; per-tick setters do not restart active motion.
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEntryHandsReferenceTest,"Prophecy.NN.AttackEntry.HandReference",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FEntryHandsReferenceTest::RunTest(const FString&)
{
    using namespace ProphecyAttackStartHands;
    FTransform Base[8];Base[0]=FTransform(FRotator(5,15,0),FVector(0,0,70));
    Base[1]=FTransform(FRotator(-10,40,8),FVector(0,0,115));
    for(int S=0;S<2;++S)
    {
        const int B=2+S*3;const double Y=S?20:-20;
        Base[B]=FTransform(FVector(0,Y,110));Base[B+1]=FTransform(FVector(25,Y,100));Base[B+2]=FTransform(FVector(35,Y,80));
    }
    const FTransform Root(FRotator(0,25,0),FVector(10,-20,3));
    const FTransform Shift(FRotator(0,80,0),FVector(200,80,-20));
    for(float A:{0.f,.5f,1.f})
    {
        FState S;S.Config.Reference=A;FTransform P[8],F[8];
        for(int I=0;I<8;++I){P[I]=Base[I];F[I]=Base[I]*Shift;}
        Seed(S,P,F,F,1./30,Root,Root*Shift);
        for(int Side=0;Side<2;++Side)
        {
            const auto& H=S.Hand[Side];
            TestTrue(TEXT("Root/spine reference removes common body linear velocity"),H.Velocity.IsNearlyZero(1.e-7));
            TestTrue(TEXT("Root/spine reference removes common body angular velocity"),H.AngularVelocity.IsNearlyZero(1.e-7));
        }
        const FTransform Frame=Reference(Root,Base[1],A);
        TestTrue(TEXT("Reference origin blends root and spine"),Frame.GetLocation().Equals(FMath::Lerp(Root.GetLocation(),Base[1].GetLocation(),A),1.e-8));
        if(A==0)TestTrue(TEXT("Zero is the locomotion root, independent of pelvis"),Frame.Equals(Root,1.e-8));
        if(A==1)TestTrue(TEXT("One is spine"),Frame.Equals(Base[1],1.e-8));
        if(A==.5f)TestTrue(TEXT("Midpoint rotates halfway from root heading to spine"),
            FMath::IsNearlyEqual(Root.GetRotation().AngularDistance(Frame.GetRotation()),
                Root.GetRotation().AngularDistance(Base[1].GetRotation())*.5,1.e-8));
        P[7].AddToTranslation(Frame.TransformVectorNoScale(FVector(-1,0,0)));
        Seed(S,P,Base,Base,1./30,Root,Root);
        TestTrue(TEXT("Hand velocity measured in blended frame"),S.Hand[1].Velocity.Equals(FVector(30,0,0),1.e-6));
        S.Config.Momentum=0;Seed(S,P,Base,Base,1./30,Root,Root);
        TestTrue(TEXT("Zero momentum kills entry velocity only"),S.Hand[1].Velocity.IsZero());
        const FVector Before=S.Hand[1].Position;FTransform Goal=S.Hand[1].Accepted[2];Goal.AddToTranslation(FVector(10,0,0));
        Spring(S.Hand[1],Goal,.25,1./30);
        TestTrue(TEXT("Zero momentum still produces positional lag"),S.Hand[1].Position.X>Before.X && S.Hand[1].Position.X<Goal.GetLocation().X);
    }
    // Root motion carries both endpoints; spine-only motion carries only alpha one.
    // Exercise the actual arm solver with a separate nonidentity component carrier.
    const FTransform BodyMotion(FRotator(0,2,0),FVector(2,-1,1));
    const FTransform Carrier(FRotator(15,70,-10),FVector(400,-200,30));
    for(bool MoveRoot:{false,true})for(float A:{0.f,1.f})
    {
        FState S;S.Config.Reference=A;Seed(S,Base,Base,Base,1./30,Root,Root);
        FTransform Pose[8];
        for(int I=0;I<8;++I){S.Indices[I]=I;Pose[I]=(Base[I]*BodyMotion).GetRelativeTransform(Carrier);}
        Solve(S,MakeArrayView(Pose),Carrier,0.,MoveRoot?Root*BodyMotion:Root);
        for(int Side=0;Side<2;++Side)
        {
            const int Hand=4+3*Side;
            const FTransform Expected=(MoveRoot || A==1)?Base[Hand]*BodyMotion:Base[Hand];
            TestTrue(TEXT("Root carries hand while independent spine motion only carries spine-local hand"),
                (Pose[Hand]*Carrier).Equals(Expected,1.e-6));
            TestTrue(TEXT("Root/spine solve retains connected forearm length"),
                FMath::IsNearlyEqual(FVector::Distance(Pose[Hand].GetLocation(),Pose[Hand-1].GetLocation()),
                    S.Hand[Side].ForearmLength,1.e-6));
        }
    }
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEntryHandsLifecycleTest,"Prophecy.NN.AttackEntry.HandLifecycle",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FEntryHandsLifecycleTest::RunTest(const FString&)
{
    using namespace ProphecyAttackStartHands;using L=UProphecyAttackStartInertiaLibrary;
    UWorld* W=UWorld::CreateWorld(EWorldType::Editor,false);auto* A=W?W->SpawnActor<AProphecyAgent>():nullptr;if(!A)return false;
    FTransform P[8];P[0]=FTransform(FVector(0,0,70));P[1]=FTransform(FVector(0,0,110));
    for(int S=0;S<2;++S){const int B=2+3*S;P[B]=FTransform(FVector(0,S?20:-20,100));P[B+1]=FTransform(P[B].GetLocation()+FVector(25,0,0));P[B+2]=FTransform(P[B+1].GetLocation()+FVector(0,0,-25));}
    TestFalse(TEXT("Disabled apply has no state"),Apply(A,Bones,P,FTransform::Identity,1./30,FTransform::Identity)!=0);Begin(A,FTransform::Identity,FTransform::Identity);TestFalse(TEXT("Disabled entry samples nothing"),Active(A));
    TestTrue(TEXT("Configure node"),L::SetAttackStartHandInertia(A,true,.1,.2,.5,.25,1,1,false,true));
    CaptureReset(A);FState State;State.Config=Configs.FindChecked(A);Seed(State,P,P,P,1./30,FTransform::Identity,FTransform::Identity);States.Add(A,State);
    const FTransform EntryWrist=P[7];auto Left=P[4];P[7].AddToTranslation(FVector(5,0,5));
    TestEqual(TEXT("NN-only apply reports exactly the selected hand"),Apply(A,Bones,P,FTransform::Identity,1./30,FTransform::Identity),uint8(2));
    TestTrue(TEXT("Unselected hand unchanged"),P[4].Equals(Left,0));
    TestTrue(TEXT("Held position restored on entry"),P[7].GetLocation().Equals(EntryWrist.GetLocation(),1.e-6));
    TestTrue(TEXT("Elbow remains connected"),FMath::IsNearlyEqual((P[6].GetLocation()-P[5].GetLocation()).Length(),25.,1.e-6));
    TestTrue(TEXT("Forearm remains connected"),FMath::IsNearlyEqual((P[7].GetLocation()-P[6].GetLocation()).Length(),25.,1.e-6));
    const FTransform Once=P[7];Apply(A,Bones,P,FTransform::Identity,1./30,FTransform::Identity);
    TestTrue(TEXT("Same-clock publication idempotent"),P[7].Equals(Once,1.e-6));
    L::SetAttackStartHandInertia(A,true,.1,.2,.5,.25,1,1,false,true);
    TestTrue(TEXT("Repeated setter preserves active state"),States.FindChecked(A).Applied);
    TestEqual(TEXT("Full hold weight"),Weight(State.Config,.05),1.);
    TestTrue(TEXT("Smooth blend midpoint"),FMath::IsNearlyEqual(Weight(State.Config,.2),.5,1.e-6));
    States.FindChecked(A).Elapsed=.3;TestFalse(TEXT("Completion retires before further pose work"),Apply(A,Bones,P,FTransform::Identity,1./30,FTransform::Identity)!=0);TestFalse(TEXT("Completed state gone"),Active(A));
    State.Config.Hold=.1f;State.Config.Blend=.3f;State.Elapsed=24./60.;States.Add(A,State);
    TestFalse(TEXT("Default float durations retire exactly on tick 24"),Apply(A,Bones,P,FTransform::Identity,1./30,FTransform::Identity)!=0);
    L::SetAttackStartHandInertia(A,true,.1,.2,.5,.25,1,0);TestFalse(TEXT("Zero alpha removes configuration"),Configs.Contains(A));
    RestoreReset(A);TestTrue(TEXT("Reset restores configuration only"),Configs.Contains(A)&&!Active(A));
    Remove(A);W->DestroyWorld(false);return !HasAnyErrors();
}
#endif

#include "ProphecyAttackStartFKCore.inl"
