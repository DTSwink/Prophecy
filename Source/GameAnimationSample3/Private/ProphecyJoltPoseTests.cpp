#include "ProphecyJoltPose.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"

namespace ProphecyJolt::PoseTests
{
constexpr EAutomationTestFlags Flags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;

FQuat AroundZ(double Degrees)
{
    return FQuat(FVector::UpVector, FMath::DegreesToRadians(Degrees));
}

bool NearPose(const FTransform& A, const FTransform& B)
{
    return A.GetTranslation().Equals(B.GetTranslation(), 1.0e-5)
        && A.GetScale3D().Equals(B.GetScale3D(), 1.0e-6)
        && A.GetRotation().AngularDistance(B.GetRotation()) < 1.0e-6;
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltPoseOffsetTest,
    "Prophecy.Jolt.Pose.RotatedBodyOffsetAndHelper", ProphecyJolt::PoseTests::Flags)

bool FProphecyJoltPoseOffsetTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::PoseTests;
    const TArray<int32> Parents = { INDEX_NONE, 0, 1, 0 };
    TArray<FTransform> Base;
    Base.Add(FTransform(AroundZ(10.0), FVector(5.0, 10.0, 15.0)));
    Base.Add(FTransform(AroundZ(-20.0), FVector(0.0, 0.0, 40.0)));
    const FQuat FingerRotation(FVector::ForwardVector, FMath::DegreesToRadians(20.0));
    Base.Add(FTransform(FingerRotation, FVector(0.0, 10.0, 5.0), FVector(0.9, 1.1, 1.0)));
    Base.Add(FTransform(AroundZ(12.0), FVector(8.0, 4.0, 2.0)));
    const TArray<FTransform> OriginalBase = Base;
    const FTransform ComponentWorld(AroundZ(30.0), FVector(100.0, -50.0, 5.0));
    FProphecyJoltPoseBodyMapping Mapping;
    Mapping.BoneIndex = 1;
    Mapping.BodyFromBoneRigid = FTransform(AroundZ(45.0), FVector(10.0, 0.0, 0.0));
    Mapping.VisualScale = FVector(1.2, 0.8, 1.1);
    const TArray<FProphecyJoltPoseBodyMapping> Mappings = { Mapping };
    // Analytic construction: bone world Rz90 at (200,100,80), with body offset Rz45 and local +X10.
    const TArray<FTransform> BodyWorld = { FTransform(AroundZ(135.0), FVector(200.0, 110.0, 80.0)) };
    FProphecyJoltComposedPose Pose;
    FString Error;
    if (!TestTrue(*FString::Printf(TEXT("Compose succeeds: %s"), *Error),
        ProphecyJolt::Pose::ComposeCompletedPose(Base, Parents, Mappings, BodyWorld, ComponentWorld, Pose, Error)))
    {
        AddError(Error);
        return false;
    }
    TestEqual(TEXT("Complete skeleton output"), Pose.WorldTransforms.Num(), 4);
    TestTrue(TEXT("Rotated body offset is removed in the correct order"),
        Pose.WorldTransforms[1].GetTranslation().Equals(FVector(200.0, 100.0, 80.0), 1.0e-5));
    TestTrue(TEXT("Physical bone world orientation is independent of the component carrier"),
        Pose.WorldTransforms[1].GetRotation().AngularDistance(AroundZ(90.0)) < 1.0e-6);
    TestTrue(TEXT("Visual scale is restored once"), Pose.WorldTransforms[1].GetScale3D().Equals(Mapping.VisualScale, 1.0e-6));
    TestTrue(TEXT("Helper/finger local pose is preserved"), NearPose(Pose.LocalTransforms[2], OriginalBase[2]));
    TestTrue(TEXT("Helper follows the physical parent including its nonuniform visual scale"),
        Pose.WorldTransforms[2].GetTranslation().Equals(FVector(192.0, 100.0, 85.5), 1.0e-5));
    TestTrue(TEXT("Finger rotation composes after its physical parent"),
        Pose.WorldTransforms[2].GetRotation().AngularDistance(AroundZ(90.0) * FingerRotation) < 1.0e-6);
    TestTrue(TEXT("Unmapped sibling keeps its authored local pose"), NearPose(Pose.LocalTransforms[3], OriginalBase[3]));
    for (int32 Index = 0; Index < Base.Num(); ++Index)
        TestTrue(*FString::Printf(TEXT("Input local bone %d remains unchanged"), Index), NearPose(Base[Index], OriginalBase[Index]));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltPoseFrameAgreementTest,
    "Prophecy.Jolt.Pose.CompletedFeedbackAndRenderFrame", ProphecyJolt::PoseTests::Flags)

bool FProphecyJoltPoseFrameAgreementTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::PoseTests;
    // Full current-mesh-sized frame, with multiple branches and mappings deliberately out of bone order.
    TArray<FTransform> Base;
    TArray<int32> Parents;
    for (int32 Index = 0; Index < 88; ++Index)
    {
        Parents.Add(Index == 0 ? INDEX_NONE : (Index - 1) / 2);
        Base.Add(FTransform(FRotator(0.3 * Index, -0.7 * Index, 0.2 * Index),
            FVector(0.1 * Index, 2.0, 3.0), FVector(1.0, 1.0 + 0.001 * Index, 1.0)));
    }
    const int32 PhysicalBones[] = { 87, 20, 1, 45 };
    TArray<FProphecyJoltPoseBodyMapping> Mappings;
    TArray<FTransform> BodyWorld;
    for (int32 Index = 0; Index < UE_ARRAY_COUNT(PhysicalBones); ++Index)
    {
        FProphecyJoltPoseBodyMapping& Mapping = Mappings.AddDefaulted_GetRef();
        Mapping.BoneIndex = PhysicalBones[Index];
        Mapping.BodyFromBoneRigid = FTransform(FRotator(3.0 * Index, 15.0, -7.0), FVector(1.0, -2.0, 4.0));
        Mapping.VisualScale = FVector(0.9 + 0.05 * Index, 1.1, 1.0);
        BodyWorld.Add(FTransform(FRotator(10.0 * Index, 30.0 + 9.0 * Index, -5.0),
            FVector(625.0 + Index * 20.0, -240.0 + Index * 5.0, 130.0 + Index * 15.0)));
    }
    const FTransform ComponentWorld(FRotator(2.0, 31.0, -4.0), FVector(600.0, -220.0, 81.0));
    FProphecyJoltComposedPose Completed;
    FString Error;
    if (!ProphecyJolt::Pose::ComposeCompletedPose(Base, Parents, Mappings, BodyWorld, ComponentWorld, Completed, Error))
    {
        AddError(Error);
        return false;
    }

    // Render consumes only the published local transforms. Reconstruct that hierarchy independently
    // and compare it to feedback's absolute completed frame, including a changed feedback carrier.
    const FTransform FeedbackCarrier(FRotator(-3.0, 53.0, 1.0), FVector(614.0, -205.0, 79.0));
    TArray<FTransform> RenderComponent;
    RenderComponent.SetNum(Parents.Num());
    for (int32 Index = 0; Index < Parents.Num(); ++Index)
    {
        RenderComponent[Index] = Parents[Index] == INDEX_NONE ? Completed.LocalTransforms[Index]
            : Completed.LocalTransforms[Index] * RenderComponent[Parents[Index]];
        const FTransform RenderWorld = RenderComponent[Index] * ComponentWorld;
        TestTrue(*FString::Printf(TEXT("Rendered world bone %d matches the completed physical frame"), Index),
            NearPose(RenderWorld, Completed.WorldTransforms[Index]));
        TestTrue(*FString::Printf(TEXT("Feedback bone %d is the same completed world pose in its current carrier"), Index),
            NearPose(RenderWorld.GetRelativeTransform(FeedbackCarrier),
                Completed.WorldTransforms[Index].GetRelativeTransform(FeedbackCarrier)));
    }

    const FProphecyJoltComposedPose FirstFrame = Completed;
    BodyWorld[0].AddToTranslation(FVector(100.0, 0.0, 0.0));
    FProphecyJoltComposedPose NextFrame;
    if (!ProphecyJolt::Pose::ComposeCompletedPose(Base, Parents, Mappings, BodyWorld, ComponentWorld, NextFrame, Error))
    {
        AddError(Error);
        return false;
    }
    TestTrue(TEXT("A later completed frame changes the driven bone"),
        !NextFrame.WorldTransforms[87].GetTranslation().Equals(FirstFrame.WorldTransforms[87].GetTranslation(), 1.0e-5));
    TestTrue(TEXT("Producing a later frame does not mutate the prior published frame"),
        NearPose(Completed.WorldTransforms[87], FirstFrame.WorldTransforms[87]));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltPoseValidationTest,
    "Prophecy.Jolt.Pose.RejectInvalidFramesAndMappings", ProphecyJolt::PoseTests::Flags)

bool FProphecyJoltPoseValidationTest::RunTest(const FString& Parameters)
{
    const TArray<FTransform> Base = { FTransform::Identity, FTransform(FVector(0.0, 0.0, 10.0)) };
    TArray<int32> Parents = { INDEX_NONE, 0 };
    FProphecyJoltPoseBodyMapping Mapping;
    Mapping.BoneIndex = 1;
    TArray<FProphecyJoltPoseBodyMapping> Mappings = { Mapping };
    TArray<FTransform> BodyWorld = { FTransform::Identity };
    FProphecyJoltComposedPose Output;
    FString Error;
    auto Compose = [&](const FTransform& Component)
    {
        return ProphecyJolt::Pose::ComposeCompletedPose(Base, Parents, Mappings, BodyWorld, Component, Output, Error);
    };
    TestTrue(TEXT("Baseline input succeeds"), Compose(FTransform::Identity));
    Parents[1] = 1;
    TestFalse(TEXT("Self-parent/cyclic hierarchy is rejected"), Compose(FTransform::Identity));
    TestTrue(TEXT("Failure clears every output array and gives a reason"),
        Output.LocalTransforms.IsEmpty() && Output.ComponentTransforms.IsEmpty() && Output.WorldTransforms.IsEmpty() && !Error.IsEmpty());
    Parents[1] = 0;
    Mappings.Add(Mapping);
    BodyWorld.Add(FTransform::Identity);
    TestFalse(TEXT("Two bodies cannot independently own the same bone"), Compose(FTransform::Identity));
    Mappings.Pop();
    BodyWorld.Pop();
    TestFalse(TEXT("Zero component scale is rejected"),
        Compose(FTransform(FQuat::Identity, FVector::ZeroVector, FVector(0.0, 1.0, 1.0))));
    Mappings[0].VisualScale.X = -1.0;
    TestFalse(TEXT("Negative visual scale is rejected"), Compose(FTransform::Identity));
    Mappings[0].VisualScale = FVector::OneVector;
    Mappings[0].BodyFromBoneRigid.SetScale3D(FVector(1.0, 2.0, 1.0));
    TestFalse(TEXT("Collision scale cannot leak into the rigid bone/body offset"), Compose(FTransform::Identity));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltScaledCarrierPoseTest,
    "Prophecy.Jolt.Pose.ScaledSkeletalCarrier", ProphecyJolt::PoseTests::Flags)
bool FProphecyJoltScaledCarrierPoseTest::RunTest(const FString&)
{
    const TArray<FTransform> Base={FTransform::Identity,FTransform(FVector(0,0,-20)),FTransform(FVector(0,0,-20))};
    const TArray<int32> Parents={INDEX_NONE,0,1};
    for (const FVector Scale:{FVector(.492965,.492965,1),FVector(.79),FVector(2,1,.7)})
    {
        const FTransform Carrier(FRotator(20,30,10),FVector(5,-40,600),Scale);
        TArray<FProphecyJoltPoseBodyMapping> Maps;
        TArray<FTransform> Bodies;
        for (int32 I=0;I<3;++I)
        {
            FProphecyJoltPoseBodyMapping Map; Map.BoneIndex=I; Map.VisualScale=Scale; Maps.Add(Map);
            Bodies.Emplace(FRotator(10+I*15,30-I*10,5+I*20),FVector(5+I*12,-40+I*7,600-I*20));
        }
        ProphecyJolt::Pose::FPreparedLayout Layout; FString Error;
        FProphecyJoltComposedPose Pose;
        if (!Layout.Build(3,Parents,Maps,Error) || !Layout.Compose(Base,Bodies,Carrier,Pose,Error))
        { AddError(Error); return false; }
        TArray<FTransform> CS;
        for (int32 I=0;I<3;++I)
        {
            CS.Add(I==0?Pose.LocalTransforms[I]:Pose.LocalTransforms[I]*CS[I-1]);
            const FTransform World=CS[I]*Carrier;
            TestTrue(TEXT("Scaled skeletal evaluation preserves native bone position"),World.GetLocation().Equals(Bodies[I].GetLocation(),1.e-5));
            TestTrue(TEXT("Scaled skeletal evaluation preserves native bone rotation"),World.GetRotation().Equals(Bodies[I].GetRotation(),1.e-5));
            TestTrue(TEXT("Carrier scale applied once"),World.GetScale3D().Equals(Scale,1.e-6));
        }
    }
    return !HasAnyErrors();
}
#endif
