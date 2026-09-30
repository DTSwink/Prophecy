#include "ProphecyUpperBodyInertiaLibrary.h"
#include "ProphecyUpperBodyInertia.h"
#include "ProphecyPelvisInertiaMath.h"
#include "ProphecyBlendClock.h"
#include "ProphecyAgent.h"
#include "ProphecyHandChainMath.h"
#include "ProphecyNNPoseTypes.h"
#include "ProphecyAttackWrist.h"
#include "ProphecyClampProfileLibrary.h"
#include "ProphecyClampEase.h"
#include "Engine/World.h"
#if WITH_EDITOR
#include "HAL/IConsoleManager.h"
#endif
namespace ProphecyUpperBodyInertia
{
#if WITH_EDITOR
static TAutoConsoleVariable<int32> ArmSolveAudit(TEXT("Prophecy.UpperInertia.Audit"),0,TEXT("Trace active player arm goal, guide and solved elbow; opt-in only."));
static TAutoConsoleVariable<float> DebugResponse(TEXT("Prophecy.UpperInertia.DebugResponse"),0,TEXT("Owned diagnostic only: override exit response, zero preserves Blueprint."));
static TAutoConsoleVariable<int32> DebugNoTwist(TEXT("Prophecy.UpperInertia.DebugNoTwist"),0,TEXT("Owned diagnostic only: remove outgoing arm axial momentum."));
#endif
using K=ProphecyBlendClock::EKind;
struct FConfig { float Response=.25f,Hold=0,Blend=.5f,Momentum=1; };
struct FMotion { FQuat Rotation=FQuat::Identity;FVector Velocity=FVector::ZeroVector; };
struct FReturn { FConfig Config;TArray<FMotion> Joints;double Elapsed=0; };
static TMap<TWeakObjectPtr<const AProphecyAgent>,FConfig> Configs,Baselines;
static TMap<TWeakObjectPtr<const AProphecyAgent>,FReturn> Returns;
// Separate sidecar: don't resize allocations retained by Live Coding.
static TMap<TWeakObjectPtr<const AProphecyAgent>,TArray<FTransform>> Handoffs;
static TSet<TWeakObjectPtr<const AProphecyAgent>> HandoffReady;
struct FArmMotion
{
    int32 Bones[3];
    FMotion Upper,Forearm,Hand;
    FVector Position,Velocity,LocalUpper,LocalLower,LocalPole;
    FTransform Previous[3],Current[3];
};
struct FArms { FArmMotion Side[2];bool Ready=false; };
static TMap<TWeakObjectPtr<const AProphecyAgent>,FArms> Arms;
using ESpace=EProphecyUpperHandInertiaSpace;
struct FArmReference { ESpace Space=ESpace::RootLocal;int32 Spine=INDEX_NONE; };
static TMap<TWeakObjectPtr<const AProphecyAgent>,ESpace> Spaces,SpaceBaselines;
static TMap<TWeakObjectPtr<const AProphecyAgent>,FArmReference> ArmReferences;
// Separate from retained config/return allocations for Live Coding compatibility.
static TMap<TWeakObjectPtr<const AProphecyAgent>,float> Influences,InfluenceBaselines;
static float Influence(const AProphecyAgent* A) { const float* V=Influences.Find(A);return V?*V:1.f; }
static FDelegateHandle Cleanup;
static void EnsureCleanup()
{
    if(Cleanup.IsValid()) return;
    Cleanup=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* W,bool,bool)
    {
        auto Clean=[W](auto& M) { for(auto It=M.CreateIterator();It;++It)
            if(!It.Key().IsValid() || It.Key()->GetWorld()==W) It.RemoveCurrent(); };
        Clean(Configs);Clean(Baselines);Clean(Returns);Clean(Handoffs);Clean(Arms);
        Clean(Spaces);Clean(SpaceBaselines);Clean(ArmReferences);
        Clean(Influences);Clean(InfluenceBaselines);
        for(auto It=HandoffReady.CreateIterator();It;++It) if(!It->IsValid() || It->Get()->GetWorld()==W) It.RemoveCurrent();
    });
}
static void Spring(FMotion& M,const FQuat& Target,double Response,double Dt)
{
    using namespace ProphecyPelvisInertia;
    if(Dt<=0) return;
    const double W=2./Response,E=FMath::Exp(-W*Dt);
    const FVector X=RotationVector(M.Rotation*Target.Inverse()),C=M.Velocity+W*X;
    M.Rotation=(RotationIncrement((X+C*Dt)*E)*Target).GetNormalized();
    M.Velocity=(M.Velocity-W*C*Dt)*E;
}
bool Active(const AProphecyAgent* A) { return !Returns.IsEmpty() && Returns.Contains(A); }
bool Configured(const AProphecyAgent* A) { return !Configs.IsEmpty() && Configs.Contains(A); }
bool ArmsActive(const AProphecyAgent* A) { return !Arms.IsEmpty() && Arms.Contains(A); }
void Cancel(const AProphecyAgent* A) { ArmReferences.Remove(A);Arms.Remove(A);Handoffs.Remove(A);HandoffReady.Remove(A);if(Returns.Remove(A)) ProphecyBlendClock::Stop(A,K::UpperBodyInertia); }
void Remove(const AProphecyAgent* A) { Cancel(A);Configs.Remove(A);Baselines.Remove(A);Spaces.Remove(A);SpaceBaselines.Remove(A);Influences.Remove(A);InfluenceBaselines.Remove(A); }
void CaptureReset(const AProphecyAgent* A) { EnsureCleanup();if(const auto* C=Configs.Find(A)) Baselines.Add(A,*C);else Baselines.Remove(A);SpaceBaselines.Add(A,Spaces.FindRef(A));InfluenceBaselines.Add(A,Influence(A)); }
void RestoreReset(const AProphecyAgent* A) { Cancel(A);Configs.Remove(A);if(const auto* C=Baselines.Find(A)) Configs.Add(A,*C);Spaces.Add(A,SpaceBaselines.FindRef(A));const float* V=InfluenceBaselines.Find(A);Influences.Add(A,V?*V:1.f); }
void ForgetReset(const AProphecyAgent* A) { Baselines.Remove(A);SpaceBaselines.Remove(A);InfluenceBaselines.Remove(A); }
void Begin(const AProphecyAgent* A,TConstArrayView<FTransform> Previous,TConstArrayView<FTransform> World,
    TConstArrayView<FName> Names,TConstArrayView<FName> Core,double Dt,const FTransform& PreviousRoot,const FTransform& Root)
{
    Cancel(A);const auto* C=Configs.IsEmpty()?nullptr:Configs.Find(A);if(!C || Dt<=0 || World.Num()!=Names.Num() || Previous.Num()!=World.Num()) return;
    FReturn R;R.Config=*C;
#if WITH_EDITOR
    if(DebugResponse.GetValueOnGameThread()>0)R.Config.Response=DebugResponse.GetValueOnGameThread();
#endif
    for(FName N:Core)
    {
        const int32 I=Names.IndexOfByKey(N);if(I==INDEX_NONE) return;
        const FQuat Q=World[I].GetRotation();
        R.Joints.Add({Q,ProphecyPelvisInertia::RotationVector(Q*Previous[I].GetRotation().Inverse())*(C->Momentum/Dt)});
    }
    Returns.Add(A,MoveTemp(R));Handoffs.Add(A).Append(World.GetData(),World.Num());
    FArms NewArms;bool ValidArms=true;
    const FArmReference Ref{Spaces.FindRef(A),Names.IndexOfByKey(TEXT("spine_05"))};
    if(Ref.Space==ESpace::SpineLocal && Ref.Spine==INDEX_NONE){Cancel(A);return;}
    const FTransform& Frame=Ref.Space==ESpace::SpineLocal?World[Ref.Spine]:Root;
    const FTransform& PreviousFrame=Ref.Space==ESpace::SpineLocal?Previous[Ref.Spine]:PreviousRoot;
    const FName ArmNames[2][3]={{TEXT("upperarm_l"),TEXT("lowerarm_l"),TEXT("hand_l")},
        {TEXT("upperarm_r"),TEXT("lowerarm_r"),TEXT("hand_r")}};
    for(int32 S=0;S<2;++S)
    {
        auto& M=NewArms.Side[S];
        for(int32 B=0;B<3;++B)
        {
            const int32 I=Names.IndexOfByKey(ArmNames[S][B]);M.Bones[B]=I;
            if(I==INDEX_NONE){ValidArms=false;break;}
            M.Previous[B]=M.Current[B]=World[I];
            FMotion& Q=B==0?M.Upper:B==1?M.Forearm:M.Hand;
            const FQuat CurrentLocal=(Frame.GetRotation().Inverse()*World[I].GetRotation()).GetNormalized();
            const FQuat PreviousLocal=(PreviousFrame.GetRotation().Inverse()*Previous[I].GetRotation()).GetNormalized();
            Q={CurrentLocal,ProphecyPelvisInertia::RotationVector(CurrentLocal*PreviousLocal.Inverse())*(C->Momentum/Dt)};
        }
        if(!ValidArms)break;
        M.Position=M.Current[2].GetLocation();
        M.Velocity=(M.Position-Previous[M.Bones[2]].GetLocation())*(C->Momentum/Dt);
        M.LocalUpper=M.Current[0].GetRotation().UnrotateVector(M.Current[1].GetLocation()-M.Current[0].GetLocation());
        M.LocalLower=M.Current[1].GetRotation().UnrotateVector(M.Position-M.Current[1].GetLocation());
#if WITH_EDITOR
        if(DebugNoTwist.GetValueOnGameThread())
        {
            auto Strip=[&](FMotion& Motion,const FVector& LocalAxis)
            {
                const FVector Axis=Motion.Rotation.RotateVector(LocalAxis.GetSafeNormal());
                Motion.Velocity-=Axis*FVector::DotProduct(Motion.Velocity,Axis);
            };
            Strip(M.Upper,M.LocalUpper);Strip(M.Forearm,M.LocalLower);Strip(M.Hand,FVector::ForwardVector);
        }
#endif
        const FVector Axis=(M.Position-M.Current[0].GetLocation()).GetSafeNormal();
        M.LocalPole=M.Current[0].GetRotation().UnrotateVector(ProphecyHandChain::Plane(
            M.Current[1].GetLocation()-M.Current[0].GetLocation(),Axis,M.Current[0].GetRotation().GetAxisZ()));
        M.Position=Frame.InverseTransformPosition(M.Position);
        M.Velocity=(M.Position-PreviousFrame.InverseTransformPosition(Previous[M.Bones[2]].GetLocation()))*(C->Momentum/Dt);
    }
    if(ValidArms){Arms.Add(A,MoveTemp(NewArms));ArmReferences.Add(A,Ref);}
    ProphecyBlendClock::Start(A,K::UpperBodyInertia,double(C->Hold)+C->Blend);
}
static double BlendAlpha(const FReturn& R)
{
    const double T=R.Elapsed<R.Config.Hold?0.:R.Config.Blend>0?
        FMath::Clamp((R.Elapsed-R.Config.Hold)/R.Config.Blend,0.,1.):1.;
    return T*T*(3.-2.*T);
}
static void SpringPosition(FVector& Position,FVector& Velocity,const FVector& Goal,double Response,double Dt)
{
    if(Dt<=0)return;
    const double W=2./Response,E=FMath::Exp(-W*Dt);
    const FVector X=Position-Goal,C=Velocity+W*X;
    Position=Goal+(X+C*Dt)*E;Velocity=(Velocity-W*C*Dt)*E;
}
void ApplyArms(const AProphecyAgent* A,const FTransform& Carrier,TArrayView<FTransform> Pose,
    double Dt,const FVector2D& RestLengths,const FTransform& Root)
{
    auto* State=Arms.IsEmpty()?nullptr:Arms.Find(A);const auto* R=State?Returns.Find(A):nullptr;
    if(!R)return;
    const double Alpha=1.-Influence(A)*(1.-BlendAlpha(*R));
    const auto* Ref=ArmReferences.Find(A);if(!Ref)return;
    const FTransform Frame=Ref->Space==ESpace::SpineLocal?Pose[Ref->Spine]*Carrier:Root;
    for(int32 S=0;S<2;++S)
    {
        auto& M=State->Side[S];
        FTransform Goal[3];for(int32 B=0;B<3;++B){Goal[B]=Pose[M.Bones[B]]*Carrier;M.Previous[B]=M.Current[B];}
        const FVector RawLower=Goal[2].GetLocation()-Goal[1].GetLocation();
        const double RawLength=RawLower.Length();
        const double Rest=S==0?RestLengths.X:RestLengths.Y;
        const double GoalLength=Rest;
        Goal[2].SetLocation(Goal[1].GetLocation()+RawLower.GetSafeNormal(1.e-12,
            Goal[1].GetRotation().RotateVector(M.LocalLower.GetSafeNormal()))*Rest);
        FTransform LocalGoal[3];for(int32 B=0;B<3;++B)LocalGoal[B]=Goal[B].GetRelativeTransform(Frame);
        SpringPosition(M.Position,M.Velocity,LocalGoal[2].GetLocation(),R->Config.Response,Dt);
        Spring(M.Upper,LocalGoal[0].GetRotation(),R->Config.Response,Dt);
        Spring(M.Forearm,LocalGoal[1].GetRotation(),R->Config.Response,Dt);
        Spring(M.Hand,LocalGoal[2].GetRotation(),R->Config.Response,Dt);
        const double Length=Rest;
        FTransform Shoulder=Goal[0],Elbow=Goal[1],Wrist=Goal[2];
        Shoulder.SetRotation((Frame.GetRotation()*FQuat::Slerp(M.Upper.Rotation,LocalGoal[0].GetRotation(),Alpha)).GetNormalized());
        Elbow.SetRotation((Frame.GetRotation()*FQuat::Slerp(M.Forearm.Rotation,LocalGoal[1].GetRotation(),Alpha)).GetNormalized());
        Elbow.SetLocation(Shoulder.GetLocation()+Shoulder.GetRotation().RotateVector(M.LocalUpper));
        Wrist.SetLocation(Elbow.GetLocation()+Elbow.GetRotation().RotateVector(M.LocalLower.GetSafeNormal()*Length));
        const FTransform Target=FTransform(FQuat::Slerp(M.Hand.Rotation,LocalGoal[2].GetRotation(),Alpha).GetNormalized(),
            FMath::Lerp(M.Position,LocalGoal[2].GetLocation(),Alpha))*Frame;
        // The predicted angular chain supplies a continuous elbow pole. The
        // reference-local wrist spring owns translation; IK projects only unreachable goals.
        const FTransform GuideShoulder=Shoulder,GuideElbow=Elbow,GuideWrist=Wrist;
        ProphecyHandChain::Resolve(GuideShoulder,GuideElbow,GuideWrist,Shoulder,Elbow,Wrist,
            Target,M.LocalUpper,M.LocalPole,1.,Rest);
#if WITH_EDITOR
        if(S==0 && A->IsPlayerControlled() && ArmSolveAudit.GetValueOnGameThread())
        {
            const FVector Out=(Goal[0].GetLocation()-(Pose[State->Side[1].Bones[0]]*Carrier).GetLocation()).GetSafeNormal();
            auto Lateral=[&](const FTransform& T){return FVector::DotProduct(T.GetLocation()-Goal[0].GetLocation(),Out);};
            UE_LOG(LogTemp,Display,TEXT("ArmSolve time=%.9f elapsed=%.4f alpha=%.4f rawLength=%.4f goalLength=%.4f length=%.4f goalElbow=%.4f guideElbow=%.4f solvedElbow=%.4f goalHand=%.4f targetHand=%.4f guideHand=%.4f"),
                A->GetWorld()->GetTimeSeconds(),R->Elapsed,Alpha,RawLength,GoalLength,Length,
                Lateral(Goal[1]),Lateral(GuideElbow),Lateral(Elbow),Lateral(Goal[2]),Lateral(Target),Lateral(GuideWrist));
        }
#endif
        if(S==0)
        {
            // Publication used to clamp first and then overwrite it with these arms.
            // Blend toward the actual constrained wrist during inertia, so expiry
            // cannot suddenly reinstate a stricter locomotion wrist angle.
            const float Requested=ProphecyAttackWrist::Degrees(A,EProphecyClampProfileMode::Locomotion);
            const float Limit=Requested<0?-1:ProphecyClampEase::Current(A,ProphecyClampEase::EChannel::Wrist,Requested);
            if(Limit>=0)
            {
                FTransform Constrained=Wrist;
                if(ProphecyAttackWrist::ConstrainPose(Constrained,Elbow.GetLocation(),Limit))
                    Wrist.SetRotation(FQuat::Slerp(Wrist.GetRotation(),Constrained.GetRotation(),Alpha).GetNormalized());
            }
        }
        M.Current[0]=Shoulder;M.Current[1]=Elbow;M.Current[2]=Wrist;
        // No hidden ballistic target can accumulate outside the reachable arm.
        if(!Wrist.GetLocation().Equals(Target.GetLocation(),1.e-5))
        {
            const FVector Normal=Frame.InverseTransformVectorNoScale(Target.GetLocation()-Wrist.GetLocation()).GetSafeNormal();
            M.Position+=Frame.InverseTransformVector(Wrist.GetLocation()-Target.GetLocation());
            const double Outward=FVector::DotProduct(M.Velocity,Normal);
            if(Outward>0)M.Velocity-=Normal*Outward;
        }
        for(int32 B=0;B<3;++B)Pose[M.Bones[B]]=M.Current[B].GetRelativeTransform(Carrier);
    }
    State->Ready=true;
}
bool PublishArms(const AProphecyAgent* A,const FTransform& PreviousCarrier,const FTransform& Carrier,
    TArrayView<FTransform> PreviousPose,TArrayView<FTransform> Pose)
{
    const auto* S=Arms.IsEmpty()?nullptr:Arms.Find(A);if(!S || !S->Ready)return false;
    for(const auto& M:S->Side)for(int32 B=0;B<3;++B)
    {
        PreviousPose[M.Bones[B]]=M.Previous[B].GetRelativeTransform(PreviousCarrier);
        Pose[M.Bones[B]]=M.Current[B].GetRelativeTransform(Carrier);
    }
    return true;
}
void PreserveHandoff(const AProphecyAgent* A,TConstArrayView<int32> Parents,TConstArrayView<FName> Names,
    TConstArrayView<FName> Core,const FTransform& Carrier,TArrayView<FTransform> PreviousPose)
{
    const auto* World=Handoffs.IsEmpty()?nullptr:Handoffs.Find(A);if(!World || !HandoffReady.Contains(A))return;
    const float Weight=Influence(A);
    // The reduced upper state contains rotations, not the outgoing attack's FK
    // offsets. Re-decoding that previous endpoint would move the head before
    // interpolation even starts. Retain the actual outgoing upper-body endpoint.
    if(World->Num()==PreviousPose.Num()) for(int32 B=0;B<PreviousPose.Num();++B)
        for(int32 P=B;P!=INDEX_NONE;P=Parents[P]) if(Core.Contains(Names[P]))
        {
            const FTransform Held=(*World)[B].GetRelativeTransform(Carrier);
            if(Weight>=1.f)PreviousPose[B]=Held;
            else PreviousPose[B].BlendWith(Held,Weight);
            break;
        }
}
void Apply(const AProphecyAgent* A,TConstArrayView<int32> Parents,TConstArrayView<FName> Names,
    TConstArrayView<FName> Core,const FTransform& Carrier,TArrayView<FTransform> Pose,double PoseStepSeconds)
{
    auto* R=Returns.IsEmpty()?nullptr:Returns.Find(A);if(!R) return;
    const double Dt=ProphecyBlendClock::Consume(A,K::UpperBodyInertia);R->Elapsed+=Dt;
    if(R->Elapsed+1.e-8>=double(R->Config.Hold)+R->Config.Blend) {Cancel(A);return;}
    if(HandoffReady.Remove(A)) Handoffs.Remove(A);
    else if(Handoffs.Contains(A)) HandoffReady.Add(A);
    const double T=R->Elapsed<R->Config.Hold?0.:R->Config.Blend>0?FMath::Clamp((R->Elapsed-R->Config.Hold)/R->Config.Blend,0.,1.):1.;
    const double Alpha=1.-Influence(A)*(1.-T*T*(3.-2.*T));
    TArray<FTransform,TInlineAllocator<32>> Before;Before.Append(Pose.GetData(),Pose.Num());
    // Traverse parent order. FK attachments are preserved, while each joint's
    // world rotation carries its outgoing angular velocity through the handoff.
    for(int32 B=0;B<Pose.Num();++B)
    {
        const int32 I=Core.IndexOfByKey(Names[B]);if(I==INDEX_NONE || !R->Joints.IsValidIndex(I)) continue;
        const int32 P=Parents[B];if(P==INDEX_NONE) continue;
        auto& M=R->Joints[I];const FQuat Goal=(Before[B]*Carrier).GetRotation();
        // A future NN pose spans its complete sample interval, even when its
        // first evaluation is only one game tick after Attack Ended. The
        // ownership clock is still counted in authored 60 Hz ticks separately.
        Spring(M,Goal,R->Config.Response,PoseStepSeconds>=0?PoseStepSeconds:Dt);
        const FQuat Q=FQuat::Slerp(M.Rotation,Goal,Alpha).GetNormalized();
        const FVector Offset=Before[B].GetRelativeTransform(Before[P]).GetLocation();
        Pose[B].SetLocation(Pose[P].TransformPosition(Offset));
        Pose[B].SetRotation((Carrier.GetRotation().Inverse()*Q).GetNormalized());
    }
}
}
bool UProphecyUpperBodyInertiaLibrary::SetAttackUpperBodyInertia(AProphecyAgent* A,bool Enabled,float Response,float Hold,float Blend,float Momentum,EProphecyUpperHandInertiaSpace Space,float Alpha)
{
    using namespace ProphecyUpperBodyInertia;
    if(!IsInGameThread() || !IsValid(A) || A->IsActorBeingDestroyed() || !A->GetWorld() || A->GetWorld()->bIsTearingDown) return false;
    for(float V:{Response,Hold,Blend,Momentum}) if(!FMath::IsFinite(V) || V<0) return false;
    if(!FMath::IsFinite(Alpha))return false;
    Alpha=FMath::Clamp(Alpha,0.f,1.f);
    if(Space!=ESpace::RootLocal && Space!=ESpace::SpineLocal)return false;
    if(Enabled && Response>0 && Alpha>0 && Hold+Blend>0)
    {
        if(const auto* C=Configs.Find(A)) if(C->Response==Response && C->Hold==Hold && C->Blend==Blend && C->Momentum==Momentum && Spaces.FindRef(A)==Space)
        { Influences.Add(A,Alpha);return true; } // Alpha-only edits preserve clocks and spring velocities.
        EnsureCleanup();Cancel(A);Spaces.Add(A,Space);Influences.Add(A,Alpha);Configs.Add(A,FConfig{Response,Hold,Blend,Momentum});
    }
    else {Cancel(A);Configs.Remove(A);Spaces.Remove(A);Influences.Remove(A);}
    return true;
}
#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyArmInertiaSpaceTest,"Prophecy.NN.UpperBodyInertia.ReferenceFrames",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyArmInertiaSpaceTest::RunTest(const FString&)
{
    using namespace ProphecyUpperBodyInertia;
    UWorld* W=UWorld::CreateWorld(EWorldType::Editor,false);auto* A=W?W->SpawnActor<AProphecyAgent>():nullptr;if(!A)return false;
    const TArray<FName> Names={TEXT("spine_05"),TEXT("clavicle_l"),TEXT("upperarm_l"),TEXT("lowerarm_l"),TEXT("hand_l"),
        TEXT("clavicle_r"),TEXT("upperarm_r"),TEXT("lowerarm_r"),TEXT("hand_r")};
    const TArray<FName> Core={TEXT("clavicle_l"),TEXT("clavicle_r")};
    TArray<FTransform> Local;Local.Init(FTransform::Identity,9);
    for(int32 S=0;S<2;++S)
    {
        const int32 B=1+S*4;const double Y=S?20.:-20.;
        Local[B]=Local[B+1]=FTransform(FVector(0,Y,0));
        Local[B+2]=FTransform(FVector(30,Y,0));Local[B+3]=FTransform(FVector(30,Y,-30));
    }
    const FTransform PrevFrame(FRotator(-10,-30,5),FVector(-100,40,80));
    const FTransform Frame(FRotator(15,20,-5),FVector(200,60,120));
    const FTransform NextFrame(FRotator(25,75,10),FVector(450,-80,140));
    for(ESpace Space:{ESpace::RootLocal,ESpace::SpineLocal})
    {
        UProphecyUpperBodyInertiaLibrary::SetAttackUpperBodyInertia(A,true,80000,1,.5,1,Space);CaptureReset(A);
        UProphecyUpperBodyInertiaLibrary::SetAttackUpperBodyInertia(A,true,80000,1,.5,1,
            Space==ESpace::RootLocal?ESpace::SpineLocal:ESpace::RootLocal);
        RestoreReset(A);TestTrue(TEXT("Reset restores selected reference space"),Spaces.FindRef(A)==Space);
        TArray<FTransform> Previous=Local,World=Local,Pose=Local;
        for(int32 I=0;I<9;++I)
        {
            if(I==4 || I==8)Previous[I].AddToTranslation(FVector(-2,0,-3));
            Previous[I]=Previous[I]*PrevFrame;World[I]=World[I]*Frame;Pose[I]=Pose[I]*NextFrame;
        }
        Begin(A,Previous,World,Names,Core,1./30,
            Space==ESpace::RootLocal?PrevFrame:FTransform::Identity,
            Space==ESpace::RootLocal?Frame:FTransform::Identity);
        TestTrue(TEXT("Reference motion is removed from captured hand velocity"),Arms.FindChecked(A).Side[1].Velocity.Equals(FVector(60,0,90),1.e-5));
        TestTrue(TEXT("Reference turning is removed from captured arm angular velocity"),Arms.FindChecked(A).Side[1].Upper.Velocity.IsNearlyZero(1.e-5));
        ApplyArms(A,FTransform::Identity,Pose,1./30,FVector2D(30,30),
            Space==ESpace::RootLocal?NextFrame:FTransform::Identity);
        for(int32 I:{4,8})TestTrue(TEXT("Hand momentum follows moving/turning selected reference"),
            NextFrame.InverseTransformPosition(Pose[I].GetLocation()).Equals(Local[I].GetLocation()+FVector(2,0,3),1.e-4));
        Cancel(A);TestFalse(TEXT("Reference state retires with arm state"),ArmReferences.Contains(A));
    }
    Remove(A);W->DestroyWorld(false);return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyArmInertiaTest,"Prophecy.NN.UpperBodyInertia.HandVelocityAndReach",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyArmInertiaTest::RunTest(const FString&)
{
    using namespace ProphecyUpperBodyInertia;
    UWorld* W=UWorld::CreateWorld(EWorldType::Editor,false);auto* A=W?W->SpawnActor<AProphecyAgent>():nullptr;if(!A)return false;
    const TArray<FName> Names={TEXT("pelvis"),TEXT("clavicle_l"),TEXT("upperarm_l"),TEXT("lowerarm_l"),TEXT("hand_l"),
        TEXT("clavicle_r"),TEXT("upperarm_r"),TEXT("lowerarm_r"),TEXT("hand_r")};
    const TArray<FName> Core={TEXT("clavicle_l"),TEXT("clavicle_r")};
    const TArray<int32> Parents={INDEX_NONE,0,1,2,3,0,5,6,7};
    TArray<FTransform> Last;Last.Init(FTransform::Identity,9);
    for(int32 S=0;S<2;++S)
    {
        const int32 B=1+S*4;const double Y=S?20.:-20.;
        Last[B]=Last[B+1]=FTransform(FVector(0,Y,100));
        Last[B+2]=FTransform(FVector(30,Y,100));Last[B+3]=FTransform(FVector(30,Y,70));
    }
    TArray<FTransform> Prior=Last;
    for(int32 I:{4,8})Prior[I].AddToTranslation(FVector(-2,0,-3));
    UProphecyUpperBodyInertiaLibrary::SetAttackUpperBodyInertia(A,true,80000,1,.5,1);
    Begin(A,Prior,Last,Names,Core,1./30);
    TestTrue(TEXT("Real arms captured"),ArmsActive(A));
    FWorldDelegates::OnWorldPreActorTick.Broadcast(W,LEVELTICK_All,1.f/60);
    TArray<FTransform> Pose=Last;
    for(int32 I:{4,8})Pose[I].SetLocation(FVector(15,Pose[I].GetLocation().Y,85));
    Apply(A,Parents,Names,Core,FTransform::Identity,Pose,1./30);
    ApplyArms(A,FTransform::Identity,Pose,1./30,FVector2D(30,30));
    for(int32 I:{4,8})
    {
        TestTrue(TEXT("Outgoing world hand velocity survives changed NN goal"),
            Pose[I].GetLocation().Equals(Last[I].GetLocation()+FVector(2,0,3),1.e-4));
        TestTrue(TEXT("Inertia keeps the anatomical forearm length"),
            FMath::IsNearlyEqual((Pose[I].GetLocation()-Pose[I-1].GetLocation()).Length(),30.,1.e-5));
        TestTrue(TEXT("Upper arm stays attached with original length"),
            FMath::IsNearlyEqual((Pose[I-1].GetLocation()-Pose[I-2].GetLocation()).Length(),30.,1.e-5));
    }
    const FTransform Carrier(FRotator(0,80,0),FVector(500,-200,0));
    TArray<FTransform> P=Last,C=Last;
    TestTrue(TEXT("Publication has cached authored endpoints"),PublishArms(A,Carrier,Carrier,P,C));
    for(int32 I:{4,8})
    {
        TestTrue(TEXT("Previous world endpoint survives carrier changes"),(P[I]*Carrier).Equals(Last[I],1.e-5));
        TestTrue(TEXT("Current world endpoint survives carrier changes"),(C[I]*Carrier).Equals(Pose[I],1.e-5));
    }
    // Force unreachable ballistic demand; solve must stay finite and attached.
    Arms.FindChecked(A).Side[1].Velocity=FVector(1.e5,0,0);
    ApplyArms(A,FTransform::Identity,Pose,1./30,FVector2D(30,30));
    TestTrue(TEXT("Reach constraint prevents arm stretching"),(Pose[8].GetLocation()-Pose[6].GetLocation()).Length()<=60.00001);
    TestFalse(TEXT("Reach solve remains finite"),Pose[8].ContainsNaN());
    UProphecyUpperBodyInertiaLibrary::SetAttackUpperBodyInertia(A,true,80000,1,.5,1,ESpace::RootLocal,0);
    TestFalse(TEXT("Zero alpha cancels core ownership immediately"),Active(A));
    TestFalse(TEXT("Zero alpha cancels arm ownership immediately"),ArmsActive(A));
    TestFalse(TEXT("Zero alpha disables future returns"),Configured(A));
    Begin(A,Prior,Last,Names,Core,1./30);
    TestFalse(TEXT("Zero alpha does not start a return"),Active(A));
    TArray<FTransform> Unchanged=Pose;
    Apply(A,Parents,Names,Core,FTransform::Identity,Pose,1./30);
    ApplyArms(A,FTransform::Identity,Pose,1./30,FVector2D(30,30));
    for(int32 I=0;I<Pose.Num();++I)TestTrue(TEXT("Zero alpha leaves the normal pose untouched"),Pose[I].Equals(Unchanged[I]));
    UProphecyUpperBodyInertiaLibrary::SetAttackUpperBodyInertia(A,true,80000,1,.5,.5);
    Begin(A,Prior,Last,Names,Core,1./30);
    TestTrue(TEXT("Positive momentum re-enables inertia and scales outgoing velocity"),Arms.FindChecked(A).Side[1].Velocity.Equals(FVector(30,0,45),1.e-5));
    for(float Weight:{.25f,.5f,1.f})
    {
        UProphecyUpperBodyInertiaLibrary::SetAttackUpperBodyInertia(A,true,80000,1,.5,1,ESpace::RootLocal,Weight);
        Begin(A,Prior,Last,Names,Core,1./30);Pose=Last;
        // A different reachable pose with the same forearm length. Translating
        // only the wrist upward would ask this Alpha test to shorten the bone.
        for(int32 I:{4,8})Pose[I].SetLocation(Pose[I-1].GetLocation()+
            FQuat(FVector::RightVector,.2).RotateVector(Last[I].GetLocation()-Last[I-1].GetLocation()));
        const TArray<FTransform> FixedGoal=Pose;
        ApplyArms(A,FTransform::Identity,Pose,1./30,FVector2D(30,30));
        for(int32 I:{4,8})TestTrue(TEXT("Alpha continuously scales wrist displacement"),Pose[I].GetLocation().Equals(
            FMath::Lerp(FixedGoal[I].GetLocation(),Last[I].GetLocation()+FVector(2,0,3),double(Weight)),1.e-4));
    }
    const FVector SavedVelocity=Arms.FindChecked(A).Side[1].Velocity;
    Returns.FindChecked(A).Elapsed=.25;
    UProphecyUpperBodyInertiaLibrary::SetAttackUpperBodyInertia(A,true,80000,1,.5,1,ESpace::RootLocal,.3);
    TestTrue(TEXT("Alpha-only edits preserve active motion and timing"),Active(A) && ArmsActive(A));
    TestEqual(TEXT("Alpha does not restart hold"),Returns.FindChecked(A).Elapsed,.25);
    TestTrue(TEXT("Alpha does not reset spring velocity"),Arms.FindChecked(A).Side[1].Velocity==SavedVelocity);
    CaptureReset(A);
    UProphecyUpperBodyInertiaLibrary::SetAttackUpperBodyInertia(A,true,80000,1,.5,1,ESpace::RootLocal,.8);
    RestoreReset(A);TestEqual(TEXT("Reset restores alpha"),Influence(A),.3f);
    UProphecyUpperBodyInertiaLibrary::SetAttackUpperBodyInertia(A,true,80000,1,.5,0);
    Begin(A,Prior,Last,Names,Core,1./30);
    TestTrue(TEXT("Zero momentum still permits spring ownership"),Active(A) && ArmsActive(A));
    TestTrue(TEXT("Zero momentum only clears initial velocity"),Arms.FindChecked(A).Side[1].Velocity.IsZero());
    // Arbitrary decoded lengths and every influence must retain the one rest length.
    for(const float Weight:{.25f,.5f,1.f})
    {
        UProphecyUpperBodyInertiaLibrary::SetAttackUpperBodyInertia(A,true,.025,0,.5,1,ESpace::RootLocal,Weight);
        Begin(A,Last,Last,Names,Core,1./30);
        for(int32 Step=0;Step<15;++Step)
        {
            Returns.FindChecked(A).Elapsed=double(Step+1)/30.;Pose=Last;
            for(int32 I:{4,8})Pose[I].SetLocation(Last[I-1].GetLocation()+FVector(0,0,Step%2?-16.:-60.));
            ApplyArms(A,FTransform::Identity,Pose,1./30,FVector2D(30,30));
            for(int32 I:{4,8})
            {
                TestTrue(TEXT("Fixed wrist goal does not kick a stationary elbow sideways"),Pose[I-1].GetLocation().Equals(Last[I-1].GetLocation(),1.e-5));
                TestTrue(TEXT("Forearm never stretches or compresses during inertia/blend"),FMath::IsNearlyEqual((Pose[I].GetLocation()-Pose[I-1].GetLocation()).Length(),30.,1.e-5));
            }
        }
    }
    Cancel(A);TestFalse(TEXT("Cancel removes arm sidecar"),ArmsActive(A));
    TestFalse(TEXT("Disabled publication performs no pose work"),PublishArms(A,Carrier,Carrier,P,C));
    Remove(A);W->DestroyWorld(false);return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyCoreInertiaTest,"Prophecy.NN.UpperBodyInertia.SpringAndRetirement",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyCoreInertiaTest::RunTest(const FString&)
{
    using namespace ProphecyUpperBodyInertia;
    FMotion M;M.Velocity=FVector(0,0,2);const double Dt=1.e-5;
    Spring(M,FQuat::Identity,.25,Dt);
    TestTrue(TEXT("Initial outgoing velocity retained in the continuous limit"),FMath::Abs(ProphecyPelvisInertia::RotationVector(M.Rotation).Z/Dt-2)<.001);
    for(int32 I=0;I<600;++I) Spring(M,FQuat::Identity,.25,1./60);
    TestTrue(TEXT("Stationary target settles without residual drift"),M.Velocity.IsNearlyZero(1.e-6) && M.Rotation.AngularDistance(FQuat::Identity)<1.e-6);
    UWorld* W=UWorld::CreateWorld(EWorldType::Editor,false);auto* A=W?W->SpawnActor<AProphecyAgent>():nullptr;if(!A)return false;
    const TArray<FName> Names={TEXT("pelvis"),TEXT("head")},Core={TEXT("head")};const TArray<int32> Parents={INDEX_NONE,0};
    const TArray<FTransform> Previous={FTransform::Identity,FTransform(FRotator(0,0,0),FVector(0,0,70))};
    const TArray<FTransform> Next={FTransform::Identity,FTransform(FRotator(0,4,0),FVector(0,0,70))};
    for(float FPS:{30.f,60.f,120.f})
    {
        UProphecyUpperBodyInertiaLibrary::SetAttackUpperBodyInertia(A,true,.25,.5,.5,1);
        CaptureReset(A);Begin(A,Previous,Next,Names,Core,1./30);TestTrue(TEXT("Configured attack return starts"),Active(A));
        for(int32 I=0;I<60;++I)
        {
            FWorldDelegates::OnWorldPreActorTick.Broadcast(W,LEVELTICK_All,1/FPS);
            TArray<FTransform> Pose=Next;Apply(A,Parents,Names,Core,FTransform::Identity,Pose);
            TestTrue(TEXT("FK offset retained"),Pose[1].GetLocation()==Next[1].GetLocation());
        }
        TestFalse(TEXT("Retires at 60 ticks regardless of FPS"),Active(A));
        RestoreReset(A);Begin(A,Previous,Next,Names,Core,1./30);Cancel(A);TestFalse(TEXT("Special/reset cancels motion"),Active(A));
        UProphecyUpperBodyInertiaLibrary::SetAttackUpperBodyInertia(A,true,.25,0,0,1);Begin(A,Previous,Next,Names,Core,1./30);
        TestFalse(TEXT("Zero durations retain no active work"),Active(A));
        UProphecyUpperBodyInertiaLibrary::SetAttackUpperBodyInertia(A,true,.25,.25,0,1);
        Begin(A,Previous,Next,Names,Core,1./30);
        for(int32 Tick=1;Tick<=15;++Tick)
        {
            FWorldDelegates::OnWorldPreActorTick.Broadcast(W,LEVELTICK_All,1/FPS);
            TArray<FTransform> HeldPose=Next;Apply(A,Parents,Names,Core,FTransform::Identity,HeldPose);
            TestTrue(TEXT("Hold-only inertia retains ownership until tick15 then retires"),Active(A)==(Tick<15));
        }
    }
    UProphecyUpperBodyInertiaLibrary::SetAttackUpperBodyInertia(A,true,.25,0,.5,1);
    Begin(A,Previous,Next,Names,Core,1./30);
    FWorldDelegates::OnWorldPreActorTick.Broadcast(W,LEVELTICK_All,1.f/60);
    TArray<FTransform> Pose=Next;
    Apply(A,Parents,Names,Core,FTransform::Identity,Pose,1./30);
    TestTrue(TEXT("First future pose integrates a full NN interval, not just the first ownership tick"),
        FMath::RadiansToDegrees(Next[1].GetRotation().AngularDistance(Pose[1].GetRotation()))>2.5);
    const FTransform Carrier(FRotator(0,70,0),FVector(100,-80,0));
    for(int32 Repeat=0;Repeat<2;++Repeat)
    {
        TArray<FTransform> Out=Next;Out[1].AddToTranslation(FVector(2,0,0));
        const FTransform Pelvis=Out[0];
        PreserveHandoff(A,Parents,Names,Core,Carrier,Out);
        TestTrue(TEXT("Outgoing upper endpoint retains its actual world pose across root snaps"),(Out[1]*Carrier).Equals(Next[1],1.e-6));
        TestTrue(TEXT("Handoff does not change pelvis or legs"),Out[0].Equals(Pelvis));
    }
    FWorldDelegates::OnWorldPreActorTick.Broadcast(W,LEVELTICK_All,1.f/60);
    Apply(A,Parents,Names,Core,FTransform::Identity,Pose,1./30);
    TestTrue(TEXT("Outgoing endpoint cache retires after its one interpolation interval"),Handoffs.IsEmpty() && HandoffReady.IsEmpty());
    FQuat Full=FQuat::Identity;
    for(float Weight:{1.f,.5f,.25f})
    {
        UProphecyUpperBodyInertiaLibrary::SetAttackUpperBodyInertia(A,true,80000,1,.5,1,ESpace::RootLocal,Weight);
        Begin(A,Previous,Next,Names,Core,1./30);Pose=Next;
        Apply(A,Parents,Names,Core,FTransform::Identity,Pose,1./30);
        if(Weight==1)Full=Pose[1].GetRotation();
        else TestTrue(TEXT("Alpha scales core angular influence continuously"),Pose[1].GetRotation().AngularDistance(
            FQuat::Slerp(Next[1].GetRotation(),Full,double(Weight)))<1.e-6);
    }
    Remove(A);W->DestroyWorld(false);return !HasAnyErrors();
}
#endif
