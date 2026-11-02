#include "CoreMinimal.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "ProphecyFootIKLive.h"
#include "ProphecyFootIKLiveLibrary.h"
#include "ProphecyThrowMath.h"
#include "ProphecyAgent.h"
#include "Components/BoxComponent.h"
#include "Dom/JsonObject.h"
#include "Engine/World.h"
#include "Misc/AutomationTest.h"
#include "Serialization/JsonSerializer.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FFootIKLiveBoundaryTest,"Prophecy.FootIK.Live.CoordinatesAndTerrain",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FFootIKLiveBoundaryTest::RunTest(const FString&)
{
    using namespace ProphecyFootIKLive;
    const FName Names[]={TEXT("pelvis"),TEXT("spine_01"),TEXT("spine_02"),TEXT("spine_03"),TEXT("spine_04"),TEXT("spine_05"),TEXT("clavicle_l"),TEXT("upperarm_l"),TEXT("lowerarm_l"),TEXT("hand_l"),TEXT("clavicle_r"),TEXT("upperarm_r"),TEXT("lowerarm_r"),TEXT("hand_r"),TEXT("neck_01"),TEXT("neck_02"),TEXT("head"),TEXT("thigh_l"),TEXT("calf_l"),TEXT("foot_l"),TEXT("ball_l"),TEXT("thigh_r"),TEXT("calf_r"),TEXT("foot_r"),TEXT("ball_r")};
    FString Error,Source,History;
    const FTransform Course(FRotator(0,73,0),FVector(325,-813,92));
    TArray<FSourceSample> Samples;
    for(int32 Row=0;Row<4;++Row)
    {
        FSourceSample S;const FVector Root(.1*Row,.15*Row,.2*Row);
        S.RootWorld=Course.TransformPosition(ProphecyThrow::ToUnrealPoint(Root));
        S.HeadingWorld=Course.TransformVectorNoScale(FVector(FMath::Sin(Row*.1),FMath::Cos(Row*.1),0));
        for(int32 Body=0;Body<25;++Body)
        {
            const FTransform Solver(FRotator(Body*7-80,Row*13+Body*5,Body*3-20).Quaternion(),Root+FVector(Body*.01,.9+Body*.012,.02*Body));
            const FTransform World=ProphecyThrow::ToUnreal(Solver)*Course;
            const FTransform Back=ToSolverBody(World,Course);
            TestTrue(TEXT("Body-axis and world conversion preserves position"),Solver.GetLocation().Equals(Back.GetLocation(),1.e-10));
            TestTrue(TEXT("Body-axis and world conversion preserves rotation"),Solver.GetRotation().AngularDistance(Back.GetRotation())<1.e-7);
            S.BodiesWorld.Add(World);
        }
        Samples.Add(MoveTemp(S));
    }
    TestTrue(TEXT("Real pose window serializes"),BuildSource(Names,Samples,Course,TEXT("run"),Source,Error));
    TSharedPtr<FJsonObject> Parsed;FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Source),Parsed);
    if(!Parsed){AddError(Error);return false;}
    TestEqual(TEXT("All actual samples retained"),Parsed->GetArrayField(TEXT("poses")).Num(),4);
    TestEqual(TEXT("All root headings retained"),Parsed->GetArrayField(TEXT("rootYawDegrees")).Num(),4);
    for(int32 Row=0;Row<4;++Row)
    {
        TestEqual(TEXT("Navigation rise is removed exactly once from raw root"),Parsed->GetArrayField(TEXT("roots"))[Row]->AsArray()[1]->AsNumber(),0.);
        const auto P=Parsed->GetArrayField(TEXT("poses"))[Row]->AsObject();
        TestTrue(TEXT("Body elevation is relative to actual root"),FMath::Abs(P->GetArrayField(TEXT("points"))[0]->AsArray()[1]->AsNumber()-.9)<1.e-10);
    }
    TestTrue(TEXT("Initial history retains actual displayed poses"),BuildInitialHistory(0,4,Samples[0],Samples[1],Course,History,Error));
    FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(History),Parsed);
    TestTrue(TEXT("Actual history is not flattened"),FMath::Abs(Parsed->GetObjectField(TEXT("current"))->GetArrayField(TEXT("points"))[0]->AsArray()[1]->AsNumber()-.15)<1.e-10);
    TestFalse(TEXT("History gap is rejected"),BuildInitialHistory(0,8,Samples[0],Samples[1],Course,History,Error));

    const auto Values=UWorld::InitializationValues().AllowAudioPlayback(false).CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(false).EnableTraceCollision(true).CreateFXSystem(false).SetTransactional(false);
    UWorld* World=UWorld::CreateWorld(EWorldType::Game,false,NAME_None,nullptr,true,ERHIFeatureLevel::Num,&Values);
    if(!World){AddError(TEXT("Cannot create isolated terrain-query world"));return false;}
    auto* Agent=World->SpawnActor<AProphecyAgent>();auto* Floor=World->SpawnActor<AActor>();
    auto* Box=NewObject<UBoxComponent>(Floor);Floor->SetRootComponent(Box);Box->SetBoxExtent(FVector(150,300,10));Box->SetCollisionProfileName(TEXT("BlockAll"));Box->RegisterComponent();Floor->SetActorLocation(FVector(0,0,-10));
    TArray<FSourceSample> Roots;Roots.SetNum(2);Roots[0].RootWorld=FVector(0,0,0);Roots[1].RootWorld=FVector(0,100,0);
    FString Terrain;TestTrue(TEXT("Finite real collider captured"),CaptureTerrain(Agent,FTransform::Identity,Roots,Terrain,Error));
    if(FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Terrain),Parsed)&&Parsed)
    {
        TestEqual(TEXT("One actual floor face"),Parsed->GetArrayField(TEXT("tiles")).Num(),1);
        const auto Tile=Parsed->GetArrayField(TEXT("tiles"))[0]->AsObject();
        TestTrue(TEXT("Floor top height is exact"),FMath::Abs(Tile->GetArrayField(TEXT("point"))[1]->AsNumber())<1.e-12);
        TestEqual(TEXT("Finite tread boundary in metres"),Tile->GetArrayField(TEXT("bounds"))[3]->AsNumber(),3.);
        uint32 Before=0,After=0;TestTrue(TEXT("Collider geometry has a stable key"),TerrainGeometryHash(Terrain,Before,Error));
        auto Profile=MakeShared<FJsonObject>();Profile->SetNumberField(TEXT("z"),12);Profile->SetNumberField(TEXT("y"),4);
        Parsed->SetArrayField(TEXT("rootProfile"),{MakeShared<FJsonValueObject>(Profile)});Parsed->SetNumberField(TEXT("start"),-100);Parsed->SetNumberField(TEXT("end"),200);
        FString Modified;FJsonSerializer::Serialize(Parsed.ToSharedRef(),TJsonWriterFactory<>::Create(&Modified));
        TestTrue(TEXT("Moving root profile serializes"),TerrainGeometryHash(Modified,After,Error));
        TestEqual(TEXT("Moving root profile does not invalidate the collider cache"),Before,After);
        auto MovedPoint=Tile->GetArrayField(TEXT("point"));MovedPoint[1]=MakeShared<FJsonValueNumber>(.01);Tile->SetArrayField(TEXT("point"),MovedPoint);Modified.Reset();FJsonSerializer::Serialize(Parsed.ToSharedRef(),TJsonWriterFactory<>::Create(&Modified));
        TestTrue(TEXT("Changed collider key serializes"),TerrainGeometryHash(Modified,After,Error));
        TestTrue(TEXT("Moving a real surface invalidates geometry"),Before!=After);
    }
    else AddError(Error);
    Floor->SetActorRotation(FRotator(0,37,0));
    Roots.SetNum(3);Roots[0].RootWorld=FVector(0,0,0);Roots[1].RootWorld=FVector(100,0,50);Roots[2].RootWorld=FVector(0,0,100);
    TestTrue(TEXT("Yawed horizontal box and returning navigation route are accepted"),CaptureTerrain(Agent,FTransform::Identity,Roots,Terrain,Error));
    if(FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Terrain),Parsed)&&Parsed)
    {
        const auto Tile=Parsed->GetArrayField(TEXT("tiles"))[0]->AsObject();
        const auto Axis=Tile->GetArrayField(TEXT("u"));const FVector U(Axis[0]->AsNumber(),Axis[1]->AsNumber(),Axis[2]->AsNumber());
        TestTrue(TEXT("Tread stores its exact rotated local axis"),U.Equals(ProphecyThrow::FromUnrealPoint(Box->GetComponentQuat().GetAxisX()).GetSafeNormal(),1.e-10));
        const auto Rows=Parsed->GetArrayField(TEXT("rootRows"));TestEqual(TEXT("Returning roots retain traversal order"),Rows.Num(),3);
        TestEqual(TEXT("Same horizontal point keeps its later navigation height"),Rows[2]->AsObject()->GetArrayField(TEXT("position"))[1]->AsNumber(),1.);
        TestTrue(TEXT("Arbitrary collider ID explicitly enables tread placement"),Tile->GetBoolField(TEXT("shaped")));
    }
    // A separate pawn-blocking ramp may be sloped/non-box without becoming a
    // foot contact. Query-only treads remain visible to Foot IK.
    auto* RampActor=World->SpawnActor<AActor>();auto* Ramp=NewObject<UBoxComponent>(RampActor);RampActor->SetRootComponent(Ramp);Ramp->SetBoxExtent(FVector(100,100,8));Ramp->SetCollisionProfileName(TEXT("BlockAll"));Ramp->ComponentTags.Add(TEXT("FootIKRoot"));Ramp->RegisterComponent();RampActor->SetActorLocation(FVector(0,0,30));RampActor->SetActorRotation(FRotator(25,0,0));
    Box->ComponentTags.Add(TEXT("FootIKFeet"));Box->SetCollisionResponseToChannel(ECC_Pawn,ECR_Ignore);Box->SetCollisionResponseToChannel(ECC_GameTraceChannel8,ECR_Ignore);
    TestTrue(TEXT("Root-only navigation ramp is excluded from horizontal foot capture"),CaptureTerrain(Agent,FTransform::Identity,Roots,Terrain,Error));
    if(FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Terrain),Parsed)&&Parsed)TestEqual(TEXT("Pawn-ignoring foot tread remains queryable"),Parsed->GetArrayField(TEXT("tiles")).Num(),1);
    TestTrue(TEXT("Surface capture separates navigation and contact materials"),CaptureSurfaceTerrain(Agent,FTransform::Identity,Roots,Terrain,Error));
    if(FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Terrain),Parsed)&&Parsed)
    {
        const FString RampPrefix=FString::Printf(TEXT("%u:"),Ramp->GetUniqueID()),FootPrefix=FString::Printf(TEXT("%u:"),Box->GetUniqueID());
        TestTrue(TEXT("Tread contact faces exist"),Parsed->GetArrayField(TEXT("surfaces")).Num()>0);
        TestTrue(TEXT("Navigation ramp faces exist"),Parsed->GetArrayField(TEXT("rootSurfaces")).Num()>0);
        for(const auto& Value:Parsed->GetArrayField(TEXT("surfaces")))TestTrue(TEXT("Root-only ramp has no foot collision"),!Value->AsObject()->GetStringField(TEXT("id")).StartsWith(RampPrefix));
        for(const auto& Value:Parsed->GetArrayField(TEXT("rootSurfaces")))TestTrue(TEXT("Foot-only tread has no root collision"),!Value->AsObject()->GetStringField(TEXT("id")).StartsWith(FootPrefix));
        uint32 Before=0,After=0;TestTrue(TEXT("Split collision hash is valid"),TerrainGeometryHash(Terrain,Before,Error));
        auto Face=Parsed->GetArrayField(TEXT("rootSurfaces"))[0]->AsObject();auto P=Face->GetArrayField(TEXT("origin"));P[1]=MakeShared<FJsonValueNumber>(P[1]->AsNumber()+.01);Face->SetArrayField(TEXT("origin"),P);
        FString Modified;FJsonSerializer::Serialize(Parsed.ToSharedRef(),TJsonWriterFactory<>::Create(&Modified));TestTrue(TEXT("Changed navigation geometry hash is valid"),TerrainGeometryHash(Modified,After,Error));TestTrue(TEXT("Moving only the navigation ramp invalidates root geometry"),Before!=After);
    }
    RampActor->Destroy();Box->ComponentTags.Reset();Box->SetCollisionResponseToChannel(ECC_Pawn,ECR_Block);Box->SetCollisionResponseToChannel(ECC_GameTraceChannel8,ECR_Block);
    Floor->SetActorRotation(FRotator(35,0,0));
    TestFalse(TEXT("Inclined collider is not silently flattened"),CaptureTerrain(Agent,FTransform::Identity,Roots,Terrain,Error));
    TestTrue(TEXT("Actual finite incline faces are available to surface mode"),CaptureSurfaceTerrain(Agent,FTransform::Identity,Roots,Terrain,Error));
    if(FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Terrain),Parsed)&&Parsed)
    {
        const FString TopId=FString::Printf(TEXT("%u:0:2:1"),Box->GetUniqueID());bool Found=false;
        for(const auto& Value:Parsed->GetArrayField(TEXT("surfaces")))
        {
            const auto Face=Value->AsObject();if(Face->GetStringField(TEXT("id"))!=TopId)continue;Found=true;
            const auto Normal=Face->GetArrayField(TEXT("normal")),Origin=Face->GetArrayField(TEXT("origin")),Bounds=Face->GetArrayField(TEXT("bounds"));
            const FVector N(Normal[0]->AsNumber(),Normal[1]->AsNumber(),Normal[2]->AsNumber());
            const FVector P(Origin[0]->AsNumber(),Origin[1]->AsNumber(),Origin[2]->AsNumber());
            const FVector NormalWorld=Box->GetComponentQuat().GetAxisZ();
            TestTrue(TEXT("Incline keeps its actual normal"),N.Equals(ProphecyThrow::FromUnrealPoint(NormalWorld).GetSafeNormal(),1.e-10));
            TestTrue(TEXT("Incline face starts at actual transformed box top"),P.Equals(ProphecyThrow::FromUnrealPoint(Box->GetComponentLocation()+NormalWorld*10),1.e-10));
            TestEqual(TEXT("Incline half width is not its AABB"),Bounds[1]->AsNumber(),1.5);
            TestEqual(TEXT("Incline half length stays local to rotation"),Bounds[3]->AsNumber(),3.);
        }
        TestTrue(TEXT("Reachable inclined top face is retained"),Found);
        uint32 Key=0;TestTrue(TEXT("Incline finite geometry has a valid stable key"),TerrainGeometryHash(Terrain,Key,Error));
    }
    else AddError(Error);
    TestTrue(TEXT("Disable is safe before any worker exists"),UProphecyFootIKLiveLibrary::SetFootIKEnabled(Agent,false,Error));
    TestFalse(TEXT("No live state remains"),Enabled(Agent));
    World->DestroyWorld(false);
    return !HasAnyErrors();
}
#endif
