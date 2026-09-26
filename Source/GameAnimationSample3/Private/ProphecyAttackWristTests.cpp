#include "ProphecyAttackWrist.h"
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "ProphecyAttackWristLibrary.h"
#include "ProphecyAgent.h"
#include "Engine/World.h"
#if WITH_DEV_AUTOMATION_TESTS
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyAttackWristMath,"Prophecy.NN.AttackWrist.Math",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyAttackWristMath::RunTest(const FString&)
{
    FString Csv=TEXT("in_x,in_y,in_z,y_x,y_y,y_z,z_x,z_y,z_z,dx,dy,dz,out_x,out_y,out_z,out_yx,out_yy,out_yz,out_zx,out_zy,out_zz\n");
    FRandomStream Random(7195);
    for (int32 I=0;I<260;++I)
    {
        const FQuat4f Q(FVector3f(Random.VRand()),Random.FRandRange(-PI,PI));
        FVector3f Rows[3]={Q.RotateVector(FVector3f(1,0,0)),Q.RotateVector(FVector3f(0,1,0)),Q.RotateVector(FVector3f(0,0,1))};
        FVector3f Delta=I==0 ? FVector3f::ZeroVector : I==1 ? -Rows[0] : I==2 ? Rows[0] : FVector3f(Random.VRand())*.3f;
        FVector3f Original[3]={Rows[0],Rows[1],Rows[2]};
        const bool Changed=ProphecyAttackWrist::Constrain(Rows,FVector3f::ZeroVector,Delta);
        for (const FVector3f& V:Original) Csv+=FString::Printf(TEXT("%.9g,%.9g,%.9g,"),V.X,V.Y,V.Z);
        Csv+=FString::Printf(TEXT("%.9g,%.9g,%.9g,"),Delta.X,Delta.Y,Delta.Z);
        for (int32 J=0;J<3;++J) Csv+=FString::Printf(TEXT("%.9g,%.9g,%.9g%s"),Rows[J].X,Rows[J].Y,Rows[J].Z,J==2?TEXT("\n"):TEXT(","));
        if (Delta.Size()>1.e-8f)
            TestTrue(TEXT("Left hand stays inside training 55-degree cone"),FVector3f::DotProduct(Rows[0],Delta.GetSafeNormal())>=FMath::Cos(FMath::DegreesToRadians(55.f))-2.e-6f);
        if (!Changed) TestTrue(TEXT("In-band values untouched"),FMemory::Memcmp(Original,Rows,sizeof(Rows))==0);
        for (int32 J=0;J<3;++J)
        {
            TestTrue(TEXT("Unit rows"),FMath::IsNearlyEqual(Rows[J].SizeSquared(),1.f,2.e-6f));
            TestTrue(TEXT("Orthogonal rows"),FMath::Abs(FVector3f::DotProduct(Rows[J],Rows[(J+1)%3]))<2.e-6f);
        }
        FVector3f Again[3]={Rows[0],Rows[1],Rows[2]};
        ProphecyAttackWrist::Constrain(Again,FVector3f::ZeroVector,Delta);
        TestTrue(TEXT("Already constrained checkpoint receives no second significant correction"),Again[0].Equals(Rows[0],2.e-6f));
    }
    FFileHelper::SaveStringToFile(Csv,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/AttackWristMath.csv")));
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyAttackWristModes,"Prophecy.NN.AttackWrist.Modes",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyAttackWristModes::RunTest(const FString&)
{
    using Mode=EProphecyClampProfileMode;
    using namespace ProphecyAttackWrist;
    const auto Values=UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false)
        .CreatePhysicsScene(false).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(false)
        .EnableTraceCollision(false).CreateFXSystem(false).SetTransactional(false);
    UWorld* World=UWorld::CreateWorld(EWorldType::Game,false,NAME_None,nullptr,true,ERHIFeatureLevel::Num,&Values);
    if (!TestNotNull(TEXT("Fixture world"),World)) return false;
    auto* A=World->SpawnActor<AProphecyAgent>();auto* B=World->SpawnActor<AProphecyAgent>();
    if (!A || !B) { AddError(TEXT("Fixture actors"));World->DestroyWorld(false);return false; }
    auto Set=[&](bool On,Mode M,float Angle) { return UProphecyAttackWristLibrary::SetLeftHandConstraint(A,On,M,Angle); };
    TestEqual(TEXT("Default disabled"),Degrees(A,Mode::Locomotion),-1.f);
    TestFalse(TEXT("Default attack disabled"),Enabled(A));
    TestTrue(TEXT("Set all"),Set(true,Mode::All,30));
    TestEqual(TEXT("Attack retains training 55 with All"),Degrees(A,Mode::Attack),55.f);
    TestEqual(TEXT("Other agent unaffected"),Degrees(B,Mode::Locomotion),-1.f);
    TestTrue(TEXT("Independent parry setting"),Set(true,Mode::Parry,70));
    TestEqual(TEXT("Parry 70"),Degrees(A,Mode::Parry),70.f);
    TestEqual(TEXT("Locomotion still 30"),Degrees(A,Mode::Locomotion),30.f);
    TestEqual(TEXT("Dodge still 30"),Degrees(A,Mode::Dodge),30.f);
    TestTrue(TEXT("Attack ignores angle override"),Set(true,Mode::Attack,12));
    TestEqual(TEXT("Attack stays 55"),Degrees(A,Mode::Attack),55.f);
    TestFalse(TEXT("Reject invalid angle"),Set(true,Mode::Locomotion,180));
    TestEqual(TEXT("Rejected update preserves settings"),Degrees(A,Mode::Locomotion),30.f);
    for (float Limit:{0.f,30.f,55.f,70.f,150.f})
    {
        FTransform Hand(FRotator(0,0,0),FVector(0,20,0));
        const auto Position=Hand.GetLocation();
        ConstrainPose(Hand,FVector::ZeroVector,Limit);
        TestTrue(TEXT("UE pose honors variable angle"),FVector::DotProduct(Hand.GetRotation().GetAxisX(),Position.GetSafeNormal())>=FMath::Cos(FMath::DegreesToRadians(Limit))-1.e-6);
        TestTrue(TEXT("UE hand position unchanged"),Hand.GetLocation()==Position);
    }
    TestTrue(TEXT("Disable all"),Set(false,Mode::All,55));
    for (auto M:{Mode::Locomotion,Mode::Attack,Mode::Parry,Mode::Dodge}) TestEqual(TEXT("No retained enabled setting"),Degrees(A,M),-1.f);
    World->DestroyWorld(false);World->MarkAsGarbage();
    return !HasAnyErrors();
}
#endif
