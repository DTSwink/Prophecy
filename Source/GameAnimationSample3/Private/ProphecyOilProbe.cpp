#include "CoreMinimal.h"
#if !UE_BUILD_SHIPPING
#include "ProphecyOil.h"
#include "ProphecyOilCoverage.h"
#include "ProphecyJoltWorldSubsystem.h"
#include "ProphecyJoltSceneCollisionComponent.h"
#include "ProphecyJoltBodyComponent.h"
#include "ProphecyJoltSkeletalPropComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "EngineUtils.h"
#include "Engine/World.h"
#include "HAL/IConsoleManager.h"
#include "HAL/FileManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"
#include "UObject/UObjectIterator.h"

static FAutoConsoleCommandWithWorldAndArgs OilProbe(TEXT("Prophecy.Oil.Probe"),TEXT("Explicit isolated Oil map audit; no persistent sampler."),
    FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args,UWorld* World)
    {
        if(!World || !World->IsGameWorld() || !World->GetName().Contains(TEXT("M_OilTest")))return;
        auto* N=World->GetSubsystem<UProphecyJoltWorldSubsystem>();auto* Scene=UProphecyJoltSceneCollisionComponent::FindForWorld(World);
        FProphecyJoltWorldDiagnostics D;N->GetDiagnostics(D);
        auto Root=MakeShared<FJsonObject>();Root->SetNumberField(TEXT("steps"),D.CompletedSteps);Root->SetBoolField(TEXT("faulted"),D.bFaulted);
        Root->SetNumberField(TEXT("patches"),N->GetOilPatchCount());Root->SetNumberField(TEXT("bodies"),D.BodyCount);
        const auto VisualCoverage=ProphecyOilCoverage::Stats(World);
        Root->SetNumberField(TEXT("coverage_groups"),VisualCoverage.Groups);Root->SetNumberField(TEXT("coverage_stamps"),VisualCoverage.Stamps);
        Root->SetNumberField(TEXT("coverage_rebuilds"),VisualCoverage.Rebuilds);Root->SetNumberField(TEXT("coverage_raster_ms"),VisualCoverage.RasterMs);
        Root->SetNumberField(TEXT("physics_ms"),D.LastPhysicsUpdateWallSeconds*1000);Root->SetStringField(TEXT("failure"),D.Failure);
        int Terrain=0;for(TObjectIterator<UPrimitiveComponent> It;It;++It)if(It->GetWorld()==World && It->GetClass()->GetName().Contains(TEXT("LandscapeHeightfield")))
        {FProphecyJoltBodyHandle H;if(Scene && Scene->GetBodyHandle(**It,INDEX_NONE,H))++Terrain;}
        Root->SetNumberField(TEXT("landscape_bodies"),Terrain);
        int Matches=0,Holes=0,Mismatches=0;
        for(int Y=0;Y<8;++Y)for(int X=0;X<8;++X)
        {
            FVector P(550+X*140,-550+Y*140,500);FHitResult UE;
            const bool U=World->LineTraceSingleByChannel(UE,P,P-FVector(0,0,1200),ECC_Visibility);
            FProphecyJoltRayHit J;bool Hit=false;N->RayCast(P,P-FVector(0,0,1200),J,Hit);
            if(!U&&!Hit){++Holes;continue;}
            if(U&&Hit&&J.PositionCm.Equals(UE.ImpactPoint,.1)&&FVector::DotProduct(J.Normal,UE.ImpactNormal)>.99)++Matches;
            else ++Mismatches;
        }
        Root->SetNumberField(TEXT("terrain_matches"),Matches);Root->SetNumberField(TEXT("terrain_holes"),Holes);Root->SetNumberField(TEXT("terrain_mismatches"),Mismatches);
        TArray<TSharedPtr<FJsonValue>> Bodies;
        for(TObjectIterator<UProphecyJoltBodyComponent> It;It;++It)if(It->GetWorld()==World && It->IsJoltBody())
        {
            FProphecyJoltBodyState B;FProphecyJoltBodyHandle H;It->GetBodyHandle(H);if(!It->GetBodyState(B))continue;
            if(Args.Contains(TEXT("Push")) && (It->GetOwner()->ActorHasTag(TEXT("Slider_Wet")) || It->GetOwner()->ActorHasTag(TEXT("Slider_Dry"))))N->SetBodyVelocity(H,FVector(250,0,0),FVector::ZeroVector,true);
            if(Args.Contains(TEXT("SlideDemo")) && (It->GetOwner()->ActorHasTag(TEXT("Slider_Wet")) || It->GetOwner()->ActorHasTag(TEXT("Slider_Dry"))))
                N->SetBodyVelocity(H,FVector(-150,0,0),FVector::ZeroVector,true);
            if(It->GetOwner()->ActorHasTag(TEXT("Oil_MovingCrate")))
            {
                if(Args.Contains(TEXT("Move")))N->SetBodyPose(H,FTransform(FRotator(20,35,10),B.PositionCm+FVector(-120,0,100)));
                float Coverage=0;N->ReadOilCoverage(H,B.PositionCm+B.Rotation.RotateVector(FVector(0,0,55.5)),B.Rotation.RotateVector(FVector::UpVector),Coverage);
                Root->SetNumberField(TEXT("moving_surface_coverage"),Coverage);
            }
            auto Row=MakeShared<FJsonObject>();Row->SetStringField(TEXT("name"),It->GetOwner()->GetName());Row->SetNumberField(TEXT("x"),B.PositionCm.X);Row->SetNumberField(TEXT("y"),B.PositionCm.Y);Row->SetNumberField(TEXT("z"),B.PositionCm.Z);Row->SetNumberField(TEXT("vx"),B.CenterOfMassVelocityCmPerSecond.X);
            if(It->GetOwner()->ActorHasTag(TEXT("Slider_Wet")))Row->SetStringField(TEXT("slider"),TEXT("wet"));
            if(It->GetOwner()->ActorHasTag(TEXT("Slider_Dry")))Row->SetStringField(TEXT("slider"),TEXT("dry"));
            Bodies.Add(MakeShared<FJsonValueObject>(Row));
        }
        Root->SetArrayField(TEXT("objects"),Bodies);
        TArray<TSharedPtr<FJsonValue>> Limbs;
        for(TObjectIterator<UProphecyJoltSkeletalPropComponent> It;It;++It)if(It->GetWorld()==World)
        for(const FName Bone:{FName(TEXT("hand_l")),FName(TEXT("hand_r")),FName(TEXT("foot_l")),FName(TEXT("foot_r"))})
        {
            FProphecyJoltBodyHandle H;FProphecyJoltBodyState B;if(!It->GetBodyHandle(Bone,H)||!N->ReadBody(H,B).IsSuccess())continue;
            if(Args.Contains(TEXT("Push")))N->SetBodyVelocity(H,FVector(250,0,0),FVector::ZeroVector,true);
            auto Row=MakeShared<FJsonObject>();Row->SetStringField(TEXT("bone"),Bone.ToString());Row->SetNumberField(TEXT("x"),B.PositionCm.X);Row->SetNumberField(TEXT("z"),B.PositionCm.Z);Row->SetNumberField(TEXT("vx"),B.CenterOfMassVelocityCmPerSecond.X);Limbs.Add(MakeShared<FJsonValueObject>(Row));
        }
        Root->SetArrayField(TEXT("limbs"),Limbs);
        TArray<TSharedPtr<FJsonValue>> PatchVisuals;
        for(TActorIterator<AProphecyOilSpill> It(World);It;++It)
        {
            auto Row=MakeShared<FJsonObject>();Row->SetNumberField(TEXT("amount"),It->GetOilAmount());
            Row->SetNumberField(TEXT("decal_count"),It->GetComponents().Num());PatchVisuals.Add(MakeShared<FJsonValueObject>(Row));
        }
        Root->SetArrayField(TEXT("spills"),PatchVisuals);
        FString JSON;FJsonSerializer::Serialize(Root,TJsonWriterFactory<>::Create(&JSON));const FString Dir=FPaths::ProjectSavedDir()/TEXT("Diagnostics/Oil");IFileManager::Get().MakeDirectory(*Dir,true);
        FFileHelper::SaveStringToFile(JSON,*(Dir/TEXT("probe.json")));
    }));
#endif
