#include "CoreMinimal.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "ProphecyJoltWorldSubsystem.h"
#include "ProphecyJoltStaticBody.h"
#include "Chaos/ImplicitObjectType.h"
#include "ProphecyJoltOil.h"
#include "Engine/World.h"
#include "Engine/Engine.h"
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "HAL/FileManager.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyOilTest,"Prophecy.Jolt.Oil.ContactAndPerformance",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyOilTest::RunTest(const FString&)
{
    using namespace ProphecyJolt::Oil;
    FRegistry Grid;
    const auto Id=Grid.Add(7,FVector::ZeroVector,FVector::UpVector,100,1);
    TestEqual(TEXT("Wet center"),Grid.Coverage(7,FVector::ZeroVector,FVector::UpVector),1.f);
    TestEqual(TEXT("Dry outside"),Grid.Coverage(7,FVector(101,0,0),FVector::UpVector),0.f);
    TestEqual(TEXT("Different body"),Grid.Coverage(8,FVector::ZeroVector,FVector::UpVector),0.f);
    TestEqual(TEXT("Other floor"),Grid.Coverage(7,FVector(0,0,20),FVector::UpVector),0.f);
    TestEqual(TEXT("Underside"),Grid.Coverage(7,FVector::ZeroVector,-FVector::UpVector),0.f);
    TestTrue(TEXT("Feather matches visual"),FMath::IsNearlyEqual(Grid.Coverage(7,FVector(97.5,0,0),FVector::UpVector),.5f));
    Grid.Patches[Id].Strength=.25;
    TestEqual(TEXT("Fade"),Grid.Coverage(7,FVector::ZeroVector,FVector::UpVector),.25f);
    const auto Overlap=Grid.Add(7,FVector::ZeroVector,FVector::UpVector,100,.5);
    TestEqual(TEXT("Overlap strongest only"),Grid.Coverage(7,FVector::ZeroVector,FVector::UpVector),.5f);
    Grid.Remove(Overlap);Grid.Forget(7);TestTrue(TEXT("Destroyed surface leaves no buckets"),Grid.Patches.IsEmpty()&&Grid.Surfaces.IsEmpty());
    double Timings[3]={};volatile float Sink=0;
    for(int Pass=0;Pass<3;++Pass)
    {
        FRegistry G;const int N=Pass==0?0:Pass==1?64:4096;
        for(int I=0;I<N;++I)G.Add(4,FVector((I%64)*450,(I/64)*450,0),FVector::UpVector,100,1);
        const double Start=FPlatformTime::Seconds();
        for(int I=0;I<200000;++I)Sink=Sink+G.Coverage(4,FVector((I%64)*450,0,0),FVector::UpVector);
        Timings[Pass]=(FPlatformTime::Seconds()-Start)*1e6/200000;
    }
    auto Sim=[&](float Strength)
    {
        const auto Values=UWorld::InitializationValues().AllowAudioPlayback(false).CreatePhysicsScene(false).CreateNavigation(false).CreateAISystem(false).CreateFXSystem(false);
        UWorld* W=UWorld::CreateWorld(EWorldType::Game,false,NAME_None,nullptr,true,ERHIFeatureLevel::Num,&Values);
        GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(W);
        auto* S=W->GetSubsystem<UProphecyJoltWorldSubsystem>();FProphecyJoltWorldSettings Settings;
        TestTrue(TEXT("Initialize"),S->InitializeSimulation(Settings).IsSuccess());
        FProphecyJoltFixtureBodySettings Floor;Floor.bDynamic=false;Floor.PositionCm=FVector(0,0,-10);Floor.Friction=.8f;
        FProphecyJoltBodyHandle Ground;S->CreateBox(FVector(1000,1000,10),0,Floor,Ground);
        FProphecyJoltFixtureBodySettings Box;Box.PositionCm=FVector(-80,0,10);Box.Friction=.8f;
        FProphecyJoltBodyHandle Wet,Dry;S->CreateBox(FVector(10),0,Box,Wet);Box.PositionCm.Y=500;S->CreateBox(FVector(10),0,Box,Dry);
        for(int I=0;I<10;++I)S->Step(1.f/60,1);
        uint64 Patch;TestTrue(TEXT("Add native patch"),S->AddOilPatch(Ground,FVector::ZeroVector,FVector::UpVector,300,Strength,Patch).IsSuccess());
        S->SetBodyVelocity(Wet,FVector(180,0,0),FVector::ZeroVector,true);S->SetBodyVelocity(Dry,FVector(180,0,0),FVector::ZeroVector,true);
        for(int I=0;I<60;++I)TestTrue(TEXT("Healthy step"),S->Step(1.f/60,1).IsSuccess());
        FProphecyJoltBodyState WetState,DryState;S->ReadBody(Wet,WetState);S->ReadBody(Dry,DryState);
        TestTrue(TEXT("Dry neighboring contact grips"),FMath::Abs(DryState.CenterOfMassVelocityCmPerSecond.X)<1);
        FProphecyJoltBodyMaterial Mat;S->ReadBodyMaterial(Ground,Mat);TestEqual(TEXT("Material unchanged"),Mat.Friction,.8f);
        const float Speed=WetState.CenterOfMassVelocityCmPerSecond.X;
        S->SetOilStrength(Patch,0);for(int I=0;I<60;++I)S->Step(1.f/60,1);S->ReadBody(Wet,WetState);
        TestTrue(TEXT("Live return to dry friction"),FMath::Abs(WetState.CenterOfMassVelocityCmPerSecond.X)<1);
        S->RemoveOilPatch(Patch);TestEqual(TEXT("Removal"),S->GetOilPatchCount(),0);
        uint64 MovingPatch=0;const FVector LocalTop(0,0,10);
        S->AddOilPatch(Wet,WetState.PositionCm+WetState.Rotation.RotateVector(LocalTop),WetState.Rotation.RotateVector(FVector::UpVector),30,1,MovingPatch);
        const FTransform Moved(FRotator(30,25,15),FVector(500,500,400));S->SetBodyPose(Wet,Moved);
        float Coverage=0;S->ReadOilCoverage(Wet,Moved.TransformPosition(LocalTop),Moved.TransformVectorNoScale(FVector::UpVector),Coverage);
        TestEqual(TEXT("Oil follows moving rotated body"),Coverage,1.f);
        S->DestroyBody(Wet);TestEqual(TEXT("Destroyed moving receiver clears its oil"),S->GetOilPatchCount(),0);
        S->DestroyBody(Ground);uint64 Bad=0;TestFalse(TEXT("Stale surface rejected"),S->AddOilPatch(Ground,FVector::ZeroVector,FVector::UpVector,50,1,Bad).IsSuccess());
        FProphecyJoltStaticBodySnapshot EmptyTerrain;EmptyTerrain.CaptureId=FGuid::NewGuid();EmptyTerrain.CollisionEnabled=ECollisionEnabled::QueryAndPhysics;
        auto& TerrainShape=EmptyTerrain.MeshShapes.AddDefaulted_GetRef();TerrainShape.NativeShapeIndex=0;
        TerrainShape.NativeGeometryTypeChain.Add(uint32(Chaos::ImplicitObjectType::HeightField));
        TerrainShape.VerticesCm={FVector(0,0,0),FVector(100,0,0),FVector(0,100,0),FVector(100,100,0)};
        FProphecyJoltPreparedStaticBody Prepared;FString TerrainError;
        TestTrue(TEXT("Completely holed terrain prepares without stopping scene"),Prepared.Build(EmptyTerrain,TerrainError));
        W->DestroyWorld(false);GEngine->DestroyWorldContext(W);W->MarkAsGarbage();return Speed;
    };
    const float Dry=Sim(0),Half=Sim(.9f),Wet=Sim(1);
    TestTrue(TEXT("Zero friction retains speed"),Wet>175);
    TestTrue(TEXT("Fading physically interpolates"),Dry<Half&&Half<Wet);
    // Paired full Jolt updates: 100 awake contact bodies, same world and near-zero
    // motion, alternating dry/coated passes. Excludes setup and GT velocity writes.
    double PhysicsMs[2]={};
    {
        const auto Values=UWorld::InitializationValues().AllowAudioPlayback(false).CreatePhysicsScene(false).CreateNavigation(false).CreateAISystem(false).CreateFXSystem(false);
        UWorld* W=UWorld::CreateWorld(EWorldType::Game,false,NAME_None,nullptr,true,ERHIFeatureLevel::Num,&Values);
        GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(W);
        auto* S=W->GetSubsystem<UProphecyJoltWorldSubsystem>();FProphecyJoltWorldSettings Settings;
        TestTrue(TEXT("Benchmark world initialized"),S->InitializeSimulation(Settings).IsSuccess());
        FProphecyJoltFixtureBodySettings Floor;Floor.bDynamic=false;Floor.PositionCm=FVector(0,0,-10);Floor.Friction=.8f;
        FProphecyJoltBodyHandle Ground;S->CreateBox(FVector(1000,1000,10),0,Floor,Ground);
        TArray<FProphecyJoltBodyHandle> Boxes;
        for(int I=0;I<100;++I)
        {
            FProphecyJoltFixtureBodySettings Box;Box.PositionCm=FVector((I%10)*100-450,(I/10)*100-450,10);Box.Friction=.8f;
            S->CreateBox(FVector(10),0,Box,Boxes.AddDefaulted_GetRef());
        }
        for(int Pass=0;Pass<6;++Pass)
        {
            TArray<uint64> Patches;
            if(Pass%2)for(int I=0;I<100;++I)
            {uint64 PatchId;S->AddOilPatch(Ground,FVector((I%10)*100-450,(I/10)*100-450,0),FVector::UpVector,40,.5f,PatchId);Patches.Add(PatchId);}
            for(int Frame=0;Frame<350;++Frame)
            {
                for(const auto& B:Boxes)S->SetBodyVelocity(B,FVector(1,0,0),FVector::ZeroVector,true);
                if(!S->Step(1.f/60,1).IsSuccess()){AddError(TEXT("Benchmark step failed"));break;}
                if(Frame>=50){FProphecyJoltWorldDiagnostics D;S->GetDiagnostics(D);PhysicsMs[Pass%2]+=D.LastPhysicsUpdateWallSeconds*1000/900.;}
            }
            for(uint64 PatchId:Patches)S->RemoveOilPatch(PatchId);
        }
        W->DestroyWorld(false);GEngine->DestroyWorldContext(W);W->MarkAsGarbage();
    }
    const FString Report=FString::Printf(TEXT("{\"query_us_0_64_4096\":[%.6f,%.6f,%.6f],\"speed_dry_90percent_wet\":[%.6f,%.6f,%.6f],\"physics_ms_100_contacts_dry_oil\":[%.6f,%.6f],\"failures\":%d}"),Timings[0],Timings[1],Timings[2],Dry,Half,Wet,PhysicsMs[0],PhysicsMs[1],int(HasAnyErrors()));
    const FString Dir=FPaths::ProjectSavedDir()/TEXT("Diagnostics/Oil");IFileManager::Get().MakeDirectory(*Dir,true);FFileHelper::SaveStringToFile(Report,*(Dir/TEXT("native.json")));
    return !HasAnyErrors();
}
#endif
