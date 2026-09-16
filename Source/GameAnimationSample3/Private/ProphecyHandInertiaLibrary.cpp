#include "ProphecyHandInertiaLibrary.h"
#include "ProphecyHandInertia.h"
#include "ProphecyPelvisInertiaMath.h"
#include "ProphecyAgent.h"

namespace ProphecyHandInertia
{
struct FFollow { FVector Linear=FVector::OneVector,Angular=FVector::OneVector; };
struct FHand
{
    bool Enabled=false,Seeded=false;
    FFollow Checkpoints[3];
    double Time=0,Dt=0;
    ProphecyPelvisInertia::FMotion Motion,Start;
};
struct FState { FHand Hands[2]; };
static TMap<TWeakObjectPtr<const AProphecyAgent>,FState> States;
static int32 Index(FName Bone) { return Bone==TEXT("hand_l") ? 0 : Bone==TEXT("hand_r") ? 1 : INDEX_NONE; }
static FFollow Resolve(const FHand& H,float W,bool Attack)
{
    if (Attack) return H.Checkpoints[2];
    W=FMath::Clamp(W,0.f,1.f);
    if (W==1) return H.Checkpoints[0];
    if (W==0) return H.Checkpoints[1];
    return {FMath::Lerp(H.Checkpoints[1].Linear,H.Checkpoints[0].Linear,double(W)),
        FMath::Lerp(H.Checkpoints[1].Angular,H.Checkpoints[0].Angular,double(W))};
}
static bool Active(const FHand& H,const FFollow& F)
{ return H.Enabled && (F.Linear!=FVector::OneVector || F.Angular!=FVector::OneVector); }
void Remove(const AProphecyAgent* Agent) { States.Remove(Agent); }
void ResetMotion(const AProphecyAgent* Agent)
{
    if (auto* S = States.Find(Agent)) for (auto& H : S->Hands)
    { H.Seeded = false; H.Time = H.Dt = 0.; H.Motion = {}; H.Start = {}; }
}
bool IsActive(const AProphecyAgent* Agent,float W,bool Attack)
{
    auto* S=States.IsEmpty() ? nullptr : States.Find(Agent);
    if (!S) return false;
    bool Result=false;
    for (auto& H:S->Hands)
    {
        if (!H.Enabled) continue;
        if (Active(H,Resolve(H,W,Attack))) Result=true;
        else H.Seeded=false;
    }
    return Result;
}
static FVector Perpendicular(const FVector& A)
{ return FVector::CrossProduct(A,FMath::Abs(A.Z)<.8 ? FVector::UpVector : FVector::ForwardVector).GetSafeNormal(); }
static FVector Plane(const FVector& P,const FVector& A)
{ return (P-A*FVector::DotProduct(P,A)).GetSafeNormal(1.e-12,Perpendicular(A)); }
static FTransform StepRootAxes(ProphecyPelvisInertia::FMotion& M,const FTransform& Target,
    const FQuat& Axes,const FFollow& Follow,double Dt)
{
    const FVector Desired=(Target.GetLocation()-M.World.GetLocation())/Dt;
    M.LinearVelocity+=Axes.RotateVector(Axes.UnrotateVector(Desired-M.LinearVelocity)*Follow.Linear);
    const FVector Position=Follow.Linear==FVector::OneVector ? Target.GetLocation() : M.World.GetLocation()+M.LinearVelocity*Dt;
    const FVector DesiredAngular=ProphecyPelvisInertia::RotationVector(Target.GetRotation()*M.World.GetRotation().Inverse())/Dt;
    M.AngularVelocity+=Axes.RotateVector(Axes.UnrotateVector(DesiredAngular-M.AngularVelocity)*Follow.Angular);
    const FQuat Rotation=Follow.Angular==FVector::OneVector ? Target.GetRotation()
        : (ProphecyPelvisInertia::RotationIncrement(M.AngularVelocity*Dt)*M.World.GetRotation()).GetNormalized();
    M.World=FTransform(Rotation,Position,Target.GetScale3D());
    return M.World;
}

static void Solve(FTransform& Shoulder,FTransform& Elbow,FTransform& Wrist,
    const FTransform& Target,const FVector& FallbackPole,double L2)
{
    const FVector Hip=Shoulder.GetLocation(),OldUpper=Elbow.GetLocation()-Hip;
    const double L1=OldUpper.Length();
    const FVector OldAxis=(Wrist.GetLocation()-Hip).GetSafeNormal(1.e-12,OldUpper.GetSafeNormal());
    const FVector Bend=Plane(OldUpper,OldAxis);
    const FVector RawBend=OldUpper-OldAxis*FVector::DotProduct(OldUpper,OldAxis);
    const FVector OldPole=RawBend.SquaredLength()>1.e-10 ? Bend : Plane(FallbackPole,OldAxis);
    const FQuat Carry=Target.GetRotation()*Wrist.GetRotation().Inverse();
    const FVector A=Carry.RotateVector(OldAxis),P=Carry.RotateVector(OldPole);
    const FVector Delta=Target.GetLocation()-Hip;
    const double Min=FMath::Abs(L1-L2)+.002,Max=L1+L2-.002;
    const FVector Axis=Delta.GetSafeNormal(1.e-12,A);
    const double Distance=FMath::Clamp(Delta.Length(),Min,Max);
    const FVector End=Hip+Axis*Distance;
    const double C=FMath::Clamp(FVector::DotProduct(A,Axis),-1.,1.);
    const FVector Pole=Plane(C < -1.+1.e-6 ? -P : P-(A+Axis)*(FVector::DotProduct(P,Axis)/FMath::Max(1.e-6,1.+C)),Axis);
    const double Along=(L1*L1-L2*L2+Distance*Distance)/(2.*Distance);
    const FVector Upper=Axis*Along+Pole*FMath::Sqrt(FMath::Max(0.,L1*L1-Along*Along));
    const FVector OldNormal=FVector::CrossProduct(OldAxis,OldPole).GetSafeNormal();
    const FVector NewNormal=FVector::CrossProduct(Axis,Pole).GetSafeNormal();
    const FQuat Swing=FQuat::FindBetweenNormals(OldUpper.GetSafeNormal(),Upper.GetSafeNormal());
    const FQuat Twist=FQuat::FindBetweenNormals(Swing.RotateVector(OldNormal),NewNormal);
    Shoulder.SetRotation((Twist*Swing*Shoulder.GetRotation()).GetNormalized());
    const FVector OldLower=Wrist.GetLocation()-Elbow.GetLocation();
    Elbow.SetLocation(Hip+Upper);
    Elbow.SetRotation((FQuat::FindBetweenNormals(OldLower.GetSafeNormal(),(End-Elbow.GetLocation()).GetSafeNormal())*Elbow.GetRotation()).GetNormalized());
    Wrist=Target; Wrist.SetLocation(End);
}

bool Apply(const AProphecyAgent* Agent,int32 Hand,float W,bool Attack,double Time,double Dt,
    const FTransform& PreviousRoot,const FTransform& Root,const FTransform& PreviousHand,
    FTransform& Shoulder,FTransform& Elbow,FTransform& Wrist,const FVector& Pole,double L2)
{
    auto* S=States.Find(Agent);
    if (!S || Hand<0 || Hand>1 || Dt<=0 || L2<=.004) return false;
    auto& H=S->Hands[Hand]; const auto F=Resolve(H,W,Attack);
    if (!Active(H,F)) { H.Seeded=false; return false; }
    const FTransform Target=Wrist;
    if (!H.Seeded || Time<H.Time)
    { H.Motion.Seed(PreviousHand,Target,Dt); H.Start=H.Motion; H.Dt=Dt; H.Time=Time; H.Seeded=true; }
    else if (Time>H.Time+1.e-8) { H.Start=H.Motion; H.Dt=Time-H.Time; H.Time=Time; }
    H.Motion=H.Start;
    const FTransform Filtered=StepRootAxes(H.Motion,Target,Root.GetRotation(),F,H.Dt);
    Solve(Shoulder,Elbow,Wrist,Filtered,Pole,L2);
    // Store the accepted IK endpoint, not an unreachable hidden target.
    H.Motion.World=Wrist;
    return true;
}
}
bool UProphecyHandInertiaLibrary::SetHandInertiaEnabled(AProphecyAgent* Agent,FName Bone,bool Enabled)
{
    const int32 I=ProphecyHandInertia::Index(Bone);
    if (!IsInGameThread() || !IsValid(Agent) || I==INDEX_NONE) return false;
    auto& H=ProphecyHandInertia::States.FindOrAdd(Agent).Hands[I];
    if (H.Enabled!=Enabled) H.Seeded=false;
    H.Enabled=Enabled; return true;
}
bool UProphecyHandInertiaLibrary::SetHandInertiaCheckpoint(AProphecyAgent* Agent,FName Bone,EProphecyHandInertiaCheckpoint Checkpoint,FVector Linear,FVector Angular)
{
    const int32 I=ProphecyHandInertia::Index(Bone),C=int32(Checkpoint);
    if (!IsInGameThread() || !IsValid(Agent) || I==INDEX_NONE || C<0 || C>2) return false;
    for (double V:{Linear.X,Linear.Y,Linear.Z,Angular.X,Angular.Y,Angular.Z}) if (!FMath::IsFinite(V) || V<0 || V>1) return false;
    auto& H=ProphecyHandInertia::States.FindOrAdd(Agent).Hands[I];
    H.Checkpoints[C]={Linear,Angular}; return true;
}
bool UProphecyHandInertiaLibrary::GetHandInertiaCheckpoint(AProphecyAgent* Agent,FName Bone,EProphecyHandInertiaCheckpoint Checkpoint,bool& Enabled,FVector& Linear,FVector& Angular)
{
    Enabled=false;Linear=Angular=FVector::OneVector;
    const int32 I=ProphecyHandInertia::Index(Bone),C=int32(Checkpoint);
    if (!IsValid(Agent) || I==INDEX_NONE || C<0 || C>2) return false;
    if (const auto* S=ProphecyHandInertia::States.Find(Agent))
    { Enabled=S->Hands[I].Enabled;Linear=S->Hands[I].Checkpoints[C].Linear;Angular=S->Hands[I].Checkpoints[C].Angular; }
    return true;
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyHandInertiaTest,"Prophecy.NN.HandInertia.ControlsAndIK",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyHandInertiaTest::RunTest(const FString&)
{
    using namespace ProphecyHandInertia;
    FHand H;
    TestFalse(TEXT("Disabled bypass"),Active(H,Resolve(H,.5f,false)));
    H.Enabled=true;
    TestFalse(TEXT("All-one bypass"),Active(H,Resolve(H,.5f,false)));
    H.Checkpoints[0]={FVector(0,.2,.4),FVector(.1,.3,.5)};
    H.Checkpoints[1]={FVector(1,.8,.6),FVector(.9,.7,.5)};
    H.Checkpoints[2]={FVector(.3,.4,.5),FVector(.6,.7,.8)};
    TestTrue(TEXT("Actual walk/run weights blend all axes"),Resolve(H,.5f,false).Linear.Equals(FVector(.5,.5,.5),1.e-8)
        && Resolve(H,.5f,false).Angular.Equals(FVector(.5,.5,.5),1.e-8));
    TestTrue(TEXT("Attack independent of walk blend"),Resolve(H,0,true).Linear==H.Checkpoints[2].Linear);
    for (int32 I=0;I<8;++I)
    {
        FTransform Shoulder(FQuat::Identity,FVector::ZeroVector),Elbow(FQuat::Identity,FVector(40,0,0));
        FTransform Wrist(FQuat::Identity,FVector(65,20,0));
        const FTransform Target(FRotator(I*15,I*30,-I*10),FVector(100*FMath::Cos(double(I)),50*FMath::Sin(double(I)),I*8));
        Solve(Shoulder,Elbow,Wrist,Target,FVector(0,1,0),35);
        TestTrue(TEXT("Upper arm remains attached and fixed-length"),Elbow.GetLocation().Equals(Shoulder.TransformPosition(FVector(40,0,0)),1.e-6));
        TestTrue(TEXT("Forearm fixed-length reaches hand"),FMath::IsNearlyEqual((Wrist.GetLocation()-Elbow.GetLocation()).Length(),35.,1.e-6));
        TestTrue(TEXT("Hand rotation retained after reach projection"),Wrist.GetRotation().Equals(Target.GetRotation(),1.e-8));
    }
    ProphecyPelvisInertia::FMotion M;
    const FTransform A(FQuat::Identity,FVector(10,0,0)),B(FQuat::Identity,FVector(11,0,0));
    M.Seed(A,B,1./30.);
    const FTransform Root(FRotator(0,90,0),FVector(100,200,0));
    const FTransform Coast=StepRootAxes(M,FTransform::Identity,Root.GetRotation(),{FVector::ZeroVector,FVector::ZeroVector},1./30.);
    TestTrue(TEXT("Zero follow retains world momentum despite rotating root axes"),Coast.GetLocation().Equals(FVector(11,0,0),1.e-8));
    M.Seed(FTransform::Identity,FTransform::Identity,1./30.);
    const FTransform Split=StepRootAxes(M,FTransform(FQuat::Identity,FVector(10,20,30)),Root.GetRotation(),
        {FVector(1,0,0),FVector::OneVector},1./30.);
    TestTrue(TEXT("Root X follow tracks world Y after a 90 degree turn"),Split.GetLocation().Equals(FVector(0,20,0),1.e-8));
    return true;
}
#endif
