#include "ProphecyRobotProfile.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "ProphecyJoltWorldSubsystem.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Engine/SkeletalMesh.h"
#include "Components/SkeletalMeshComponent.h"
#include "PhysicsEngine/PhysicsAsset.h"
namespace ProphecyRobot { bool EvaluatePolicy(bool Clanker,TArrayView<float> Observation,TArrayView<float> Action,FVector2f& Phase,FString& Error); }
namespace ProphecyRobotTests
{
constexpr auto Flags=EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter;
FVector V(const TArray<TSharedPtr<FJsonValue>>& A,int32 N){return FVector(A[N]->AsNumber(),A[N+1]->AsNumber(),A[N+2]->AsNumber());}
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyRobotObservations,"Prophecy.Robotics.ObservationContract",ProphecyRobotTests::Flags)
bool FProphecyRobotObservations::RunTest(const FString&)
{
    FString Error;const auto* P=ProphecyRobot::Profile(Error);if(!P){AddError(Error);return false;}
    TestEqual(TEXT("Bodies"),P->Bodies.Num(),15);TestEqual(TEXT("Joints"),P->Joints.Num(),14);
    int32 Spheres=0,Actions=0;for(const auto& J:P->Joints){Spheres+=J.Motor[0].bBall;Actions+=J.Motor[0].bBall?3:1;}
    TestEqual(TEXT("Ten spherical joints"),Spheres,10);TestEqual(TEXT("34 motor axes"),Actions,34);
    FString Text;TArray<TSharedPtr<FJsonValue>> Rows;
    if(!FFileHelper::LoadFileToString(Text,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/RobotLocomotion20261026/observation-vectors.json")))||
        !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Rows))
    {AddError(TEXT("Run Tools/Robotics/PrepareObservationCheck.py first."));return false;}
    double Worst=0;
    for(const auto& Row:Rows)
    {
        const auto O=Row->AsObject();TArray<ProphecyRobot::FBodyState> Bodies;
        for(const auto& Value:O->GetArrayField(TEXT("states")))
        {
            const auto& A=Value->AsArray();auto& B=Bodies.AddDefaulted_GetRef();
            B.World=FTransform(FQuat(A[3]->AsNumber(),A[4]->AsNumber(),A[5]->AsNumber(),A[6]->AsNumber()).GetNormalized(),ProphecyRobotTests::V(A,0));
            B.COMVelocity=ProphecyRobotTests::V(A,7);B.AngularVelocity=ProphecyRobotTests::V(A,10);
        }
        const auto& Phase=O->GetArrayField(TEXT("phase"));float Actual[154];
        ProphecyRobot::Observation(*P,Bodies,false,-1,FVector::ZeroVector,false,FVector2f(Phase[0]->AsNumber(),Phase[1]->AsNumber()),MakeArrayView(Actual));
        const auto& Expected=O->GetArrayField(TEXT("expected"));
        for(int32 I=0;I<154;++I)Worst=FMath::Max(Worst,FMath::Abs(Actual[I]-Expected[I]->AsNumber()));
        float Loco[154];ProphecyRobot::Observation(*P,Bodies,true,1,FVector(0,-1,0),false,FVector2f(1,0),MakeArrayView(Loco));
        TestEqual(TEXT("Clanker gait"),Loco[146],1.f);TestTrue(TEXT("UE -Y maps to training +X"),FMath::IsNearlyEqual(Loco[147],1.f,1.e-6f));
        for(int32 I=0;I<146;++I)Worst=FMath::Max(Worst,FMath::Abs(Loco[I]-Expected[I]->AsNumber()));
    }
    AddInfo(FString::Printf(TEXT("%d recorded states; maximum observation error %.9g"),Rows.Num(),Worst));
    TestTrue(TEXT("Native encoding matches frozen MimicKit"),Worst<1.e-4);return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyRobotNNE,"Prophecy.Robotics.NativeNNEParity",ProphecyRobotTests::Flags)
bool FProphecyRobotNNE::RunTest(const FString&)
{
    for(bool Clanker:{false,true})
    {
        FString Text,Error;TSharedPtr<FJsonObject> Root;
        const FString File=FPaths::ProjectSavedDir()/TEXT("Diagnostics/RobotLocomotion20261026")/(Clanker?TEXT("clanker-vectors.json"):TEXT("getup-vectors.json"));
        if(!FFileHelper::LoadFileToString(Text,*File)||!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Root))
        {AddError(TEXT("Missing prepared NNE parity vectors."));return false;}
        const auto& Inputs=Root->GetArrayField(TEXT("observations"));const auto& Outputs=Root->GetArrayField(TEXT("joint_velocity_rad_s"));
        const auto& Phases=Root->GetArrayField(TEXT("next_phase"));double Worst=0;
        for(int32 R=0;R<Inputs.Num();++R)
        {
            float Input[154],Action[34];FVector2f Phase;
            for(int32 I=0;I<154;++I)Input[I]=Inputs[R]->AsArray()[I]->AsNumber();
            if(!ProphecyRobot::EvaluatePolicy(Clanker,MakeArrayView(Input),MakeArrayView(Action),Phase,Error)){AddError(Error);return false;}
            for(int32 I=0;I<34;++I)Worst=FMath::Max(Worst,FMath::Abs(Action[I]-Outputs[R]->AsArray()[I]->AsNumber()));
            for(int32 I=0;I<2;++I)Worst=FMath::Max(Worst,FMath::Abs(Phase[I]-Phases[R]->AsArray()[I]->AsNumber()));
        }
        AddInfo(FString::Printf(TEXT("%s NNE: %d samples, max error %.9g"),Clanker?TEXT("Clanker"):TEXT("Get Up"),Inputs.Num(),Worst));
        TestTrue(TEXT("Unreal CPU inference matches frozen reference"),Worst<5.e-5);
    }
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyRobotPhysics,"Prophecy.Robotics.PhysicalPolicy",ProphecyRobotTests::Flags)
bool FProphecyRobotPhysics::RunTest(const FString&)
{
    FString Error,Text;const auto* P=ProphecyRobot::Profile(Error);if(!P){AddError(Error);return false;}
    TArray<TSharedPtr<FJsonValue>> Rows;
    if(!FFileHelper::LoadFileToString(Text,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/RobotLocomotion20261026/observation-vectors.json")))||
        !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Rows)){AddError(TEXT("Missing frozen states."));return false;}
    const auto Values=UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false)
        .CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(true).CreateFXSystem(false).SetTransactional(false);
    UWorld* World=UWorld::CreateWorld(EWorldType::Game,false,NAME_None,nullptr,true,ERHIFeatureLevel::Num,&Values);
    if(!World)return false;
    GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
    struct FCleanup{UWorld* W;~FCleanup(){W->DestroyWorld(false);GEngine->DestroyWorldContext(W);W->MarkAsGarbage();}}Cleanup{World};
    auto* Owner=World->GetSubsystem<UProphecyJoltWorldSubsystem>();FProphecyJoltWorldSettings Settings;
    Settings.GravityCmPerSecondSquared=FVector(0,0,-981);
    if(!Owner->InitializeSimulation(Settings).IsSuccess())return false;
    FProphecyJoltFixtureBodySettings Floor;Floor.bDynamic=false;Floor.PositionCm=FVector(0,0,-5);Floor.Friction=1;
    FProphecyJoltBodyHandle Ground;if(!Owner->CreateBox(FVector(10000,10000,5),0,Floor,Ground).IsSuccess())return false;
    auto* Actor=World->SpawnActor<AActor>();auto* Mesh=NewObject<USkeletalMeshComponent>(Actor);
    Actor->AddInstanceComponent(Mesh);Actor->SetRootComponent(Mesh);
    Mesh->SetSkeletalMesh(LoadObject<USkeletalMesh>(nullptr,TEXT("/Game/_mygame/SKM_UEFN_Mannequin.SKM_UEFN_Mannequin")));
    Mesh->SetPhysicsAsset(LoadObject<UPhysicsAsset>(nullptr,TEXT("/Game/Characters/UEFN_Mannequin/Rigs/PA_UEFN_Mannequin.PA_UEFN_Mannequin")));
    Mesh->SetCollisionProfileName(TEXT("PhysicsActor"));Mesh->SetCollisionResponseToAllChannels(ECR_Block);
    Mesh->RegisterComponent();Mesh->SetAllBodiesSimulatePhysics(true);
    for(int32 Case=0;Case<2;++Case)
    {
        FProphecyJoltRigSnapshot Snapshot;if(!ProphecyJolt::Rig::CaptureLiveRig(*Mesh,Snapshot,Error)){AddError(Error);return false;}
        TArray<ProphecyRobot::FBodyState> Bodies;
        for(const auto& Value:Rows[Case]->AsObject()->GetArrayField(TEXT("states")))
        {
            const auto& A=Value->AsArray();auto& B=Bodies.AddDefaulted_GetRef();
            B.World=FTransform(FQuat(A[3]->AsNumber(),A[4]->AsNumber(),A[5]->AsNumber(),A[6]->AsNumber()).GetNormalized(),ProphecyRobotTests::V(A,0));
            B.COMVelocity=ProphecyRobotTests::V(A,7);B.AngularVelocity=ProphecyRobotTests::V(A,10);
        }
        if(!ProphecyRobot::MakeSnapshot(*P,*Mesh,Bodies,Snapshot,Error)){AddError(Error);return false;}
        FProphecyJoltPreparedRig Prepared;if(!Prepared.Build(Snapshot,Error)){AddError(Error);return false;}
        FProphecyJoltRigHandle Rig;TArray<FProphecyJoltBodyHandle> Handles;TArray<FString> Notes;
        auto Status=Owner->CreateRig(Snapshot,Prepared,Rig,Handles,Notes);if(!Status.IsSuccess()){AddError(Status.Message);return false;}
        TArray<FProphecyJoltRobotMotor> Motors;for(const auto& J:P->Joints)Motors.Add(J.Motor[0]);
        TArray<FProphecyJoltRobotDrag> Drag;for(const auto& B:P->Bodies)Drag.Add(B.Drag);
        Status=Owner->ConfigureRobotRig(Rig,Motors,Drag);if(!Status.IsSuccess()){AddError(Status.Message);return false;}
        const auto& SeedPhase=Rows[Case]->AsObject()->GetArrayField(TEXT("phase"));FVector2f Phase(SeedPhase[0]->AsNumber(),SeedPhase[1]->AsNumber());
        double FinalGetUp=0,MinimumClanker=DBL_MAX,MinimumMoving=DBL_MAX,MinimumWalk=DBL_MAX,MinimumRun=DBL_MAX;
        int32 FirstFall=INDEX_NONE;
        FVector WalkStart,WalkEnd,RunEnd;
        for(int32 Tick=0;Tick<720;++Tick)
        {
            const bool Clanker=Tick>=300;
            for(int32 I=0;I<15;++I)
            {
                FProphecyJoltBodyState B;Status=Owner->ReadBody(Handles[I],B);
                if(!Status.IsSuccess()){AddError(Status.Message);return false;}
                Bodies[I]={FTransform(B.Rotation,B.PositionCm),B.CenterOfMassVelocityCmPerSecond,B.AngularVelocityRadiansPerSecond};
            }
            if(Tick==299)FinalGetUp=Bodies[0].World.GetLocation().Z;
            if(Clanker&&Tick<420)MinimumClanker=FMath::Min(MinimumClanker,Bodies[0].World.GetLocation().Z);
            if(Tick>=420)MinimumMoving=FMath::Min(MinimumMoving,Bodies[0].World.GetLocation().Z);
            if(Tick>=420&&Tick<570)MinimumWalk=FMath::Min(MinimumWalk,Bodies[0].World.GetLocation().Z);
            if(Tick>=570)MinimumRun=FMath::Min(MinimumRun,Bodies[0].World.GetLocation().Z);
            if(Tick>=420&&FirstFall==INDEX_NONE&&Bodies[0].World.GetLocation().Z<60)FirstFall=Tick;
            if(Tick==420)WalkStart=Bodies[0].World.GetLocation();
            if(Tick==570)WalkEnd=Bodies[0].World.GetLocation();
            if(Tick==719)RunEnd=Bodies[0].World.GetLocation();
            const float Gait=Tick<420?-1:Tick<570?0:1;
            const FVector Direction=Case==0?FVector(0,-1,0):FVector(1,0,0);
            float Obs[154],Action[34];ProphecyRobot::Observation(*P,Bodies,Clanker,Gait,Direction,false,Phase,MakeArrayView(Obs));
            if(!ProphecyRobot::EvaluatePolicy(Clanker,MakeArrayView(Obs),MakeArrayView(Action),Phase,Error)){AddError(Error);return false;}
            for(int32 I=0;I<14;++I){const auto& J=P->Joints[I];Motors[I]=J.Motor[Clanker?1:0];
                Motors[I].Velocity=J.Motor[0].bBall?FVector(Action[J.Action],Action[J.Action+1],Action[J.Action+2]):FVector(0,0,Action[J.Action]);}
            Status=Owner->PublishRobotMotors(Rig,Motors,1);if(!Status.IsSuccess()){AddError(Status.Message);return false;}
            Status=Owner->Step(1.f/30,8);if(!Status.IsSuccess()){AddError(Status.Message);return false;}
        }
        AddInfo(FString::Printf(TEXT("Case %d: Get Up pelvis %.3f cm; Clanker minimum pelvis %.3f cm"),Case,FinalGetUp,MinimumClanker));
        TestTrue(TEXT("Get Up stands from the recorded fall"),FinalGetUp>75);
        TestTrue(TEXT("Clanker remains upright after robot-to-robot switch"),MinimumClanker>60);
        AddInfo(FString::Printf(TEXT("Case %d moving: minimum pelvis %.3f cm; walk %.3f cm; run %.3f cm"),Case,MinimumMoving,
            FVector::Dist2D(WalkStart,WalkEnd),FVector::Dist2D(WalkEnd,RunEnd)));
        TestTrue(TEXT("Clanker walks and runs without falling"),MinimumMoving>60);
        AddInfo(FString::Printf(TEXT("Walk minimum %.3f; run minimum %.3f; first fall tick %d"),MinimumWalk,MinimumRun,FirstFall));
        TestTrue(TEXT("Walk command produces travel"),FVector::Dist2D(WalkStart,WalkEnd)>100);
        TestTrue(TEXT("Run command produces travel"),FVector::Dist2D(WalkEnd,RunEnd)>100);
        Owner->DestroyRig(Rig);
    }
    return !HasAnyErrors();
}
#include "ProphecyRobotContactTests.inl"
#endif
