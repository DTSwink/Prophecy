#include "Misc/AutomationTest.h"
#include "ProphecyDefenseInputDebug.h"

#if WITH_DEV_AUTOMATION_TESTS
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyDefenseInputGhostTest,"Prophecy.NN.Defense.InputGhost",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyDefenseInputGhostTest::RunTest(const FString&)
{
    using namespace ProphecyDefenseFeatures;
    FContext C;
    const FRows Axes={{{0,0,1},{1,0,0},{0,1,0}}};
    for(int32 I=0;I<2;++I)
    {
        Write(C.AttackerPelvis[I],FVector3f(2+.2f*I,1,3+.3f*I));
        Write(C.AttackerCollider[I],FVector3f(2+.4f*I,1.5f,4+.5f*I));
        for(float* V:{C.AttackerPelvis[I],C.AttackerCollider[I]}){Write(V+3,Axes.V[0]);Write(V+6,Axes.V[1]);}
    }
    const FVector3f Half(.025f,.4f,.08f),Origin(100,7,-90);
    const FVector Offset(150,-30,20);
    auto World=[](const FVector3f& V){return FVector(V.X,V.Z,V.Y)*100.;};
    for(int32 Mode=0;Mode<3;++Mode)
    {
        auto Filtered=C;
        if(Mode==1)RemoveAttackerHorizontalVelocity(Filtered);
        if(Mode==2)RemoveAttackerRootHorizontalVelocity(Filtered,FVector3f(.1f,.9f,.2f));
        const auto Before=Filtered;
        for(int32 Frame=0;Frame<2;++Frame)
        {
            const auto S=ProphecyDefenseInputDebug::Build(Filtered.AttackerPelvis[Frame],Filtered.AttackerCollider[Frame],Half,Origin,Offset);
            TestTrue(TEXT("Dodge origin restored exactly once"),S.Pelvis.Equals(World(Read(Filtered.AttackerPelvis[Frame])+Origin)+Offset,1.e-8));
            TestTrue(TEXT("Collider is the filtered input center"),S.Collider.Equals(World(Read(Filtered.AttackerCollider[Frame])+Origin)+Offset,1.e-8));
            TestTrue(TEXT("First box edge preserves trained extent and basis"),(S.Corners[1]-S.Corners[0]).Equals(World(Axes.V[0]*Half.X)*2,1.e-5));
            TestTrue(TEXT("Second box edge preserves trained extent and basis"),(S.Corners[2]-S.Corners[0]).Equals(World(Axes.V[1]*Half.Y)*2,1.e-5));
            TestTrue(TEXT("Third box edge preserves training handedness"),(S.Corners[4]-S.Corners[0]).Equals(World(Axes.V[2]*Half.Z)*2,1.e-5));
            const auto Parry=ProphecyDefenseInputDebug::Build(Filtered.AttackerPelvis[Frame],Filtered.AttackerCollider[Frame],Half,FVector3f::ZeroVector,Offset);
            TestTrue(TEXT("Parry has no Dodge origin"),Parry.Pelvis.Equals(World(Read(Filtered.AttackerPelvis[Frame]))+Offset,1.e-8));
        }
        TestTrue(TEXT("Drawing cannot alter NN conditioning"),FMemory::Memcmp(&Before,&Filtered,sizeof(Filtered))==0);
        const auto A=ProphecyDefenseInputDebug::Build(Filtered.AttackerPelvis[0],Filtered.AttackerCollider[0],Half,Origin,Offset);
        const auto B=ProphecyDefenseInputDebug::Build(Filtered.AttackerPelvis[1],Filtered.AttackerCollider[1],Half,Origin,Offset);
        if(Mode==1)TestTrue(TEXT("Pelvis velocity removal appears as stationary pelvis"),A.Pelvis.Equals(B.Pelvis,1.e-5));
        TestTrue(TEXT("Collider relative motion survives pelvis/root filtering"),
            ((B.Collider-A.Collider)-(B.Pelvis-A.Pelvis)).Equals(World((Read(C.AttackerCollider[1])-Read(C.AttackerCollider[0]))-(Read(C.AttackerPelvis[1])-Read(C.AttackerPelvis[0]))),.003));
    }
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyDefenseFullGhostTest,"Prophecy.NN.Defense.FullGhostPose",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyDefenseFullGhostTest::RunTest(const FString&)
{
    using namespace ProphecyDefenseFeatures;
    const FVector Offset(150,-20,45);
    const FVector3f Origin(32,2,-14);
    for(int32 Bone=0;Bone<25;++Bone)
    {
        const FTransform Expected(FRotator(Bone*3-35,Bone*11-120,Bone*2-20),FVector(120+Bone*7,340-Bone*5,30+Bone*6));
        const FVector Position=Expected.GetLocation()/100.;
        const FVector3f World(Position.X,Position.Z,Position.Y);
        auto Axis=[&](const FVector& Local)
        {
            const FVector V=Expected.TransformVectorNoScale(Local);return FVector3f(V.X,V.Z,V.Y);
        };
        const FRows Axes={{Axis(FVector::ForwardVector),Axis(-FVector::RightVector),Axis(FVector::UpVector)}};
        const auto Parry=ProphecyDefenseInputDebug::WorldBone(World,Axes,FVector3f::ZeroVector,Offset);
        const auto Dodge=ProphecyDefenseInputDebug::WorldBone(World-Origin,Axes,Origin,Offset);
        TestTrue(TEXT("All upper/lower joints retain accepted world position"),Parry.GetLocation().Equals(Expected.GetLocation()+Offset,.001));
        TestTrue(TEXT("Dodge restores local origin once on all joints"),Dodge.GetLocation().Equals(Expected.GetLocation()+Offset,.001));
        TestTrue(TEXT("Bone rotations match UE axes, not reflected training axes"),Parry.GetRotation().AngularDistance(Expected.GetRotation())<1.e-6);
        TestTrue(TEXT("Dodge origin cannot rotate joints"),Dodge.GetRotation().Equals(Parry.GetRotation(),1.e-7));
        // Input markers and the defender must receive exactly the same world shift.
        float Pelvis[9]={};Write(Pelvis,World-Origin);Write(Pelvis+3,Axes.V[0]);Write(Pelvis+6,Axes.V[1]);
        const auto Input=ProphecyDefenseInputDebug::Build(Pelvis,Pelvis,FVector3f(.1f),Origin,Offset);
        TestTrue(TEXT("Defender and input coordinates agree"),Input.Pelvis.Equals(Dodge.GetLocation(),1.e-8));
    }
    return !HasAnyErrors();
}
#endif
