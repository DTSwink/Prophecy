from pathlib import Path
p=Path('Source/GameAnimationSample3/Private/ProphecyJoltBlueprintLibrary.cpp');s=p.read_text(encoding='utf-8');s=s[:s.index('\n#if !UE_BUILD_SHIPPING')];p.write_text(s,encoding='utf-8')
p=Path('Source/GameAnimationSample3/Private/ProphecyDefenseContactTests.cpp');s=p.read_text(encoding='utf-8');s='\n'.join(l for l in s.split('\n') if 'PenetrationCm' not in l);p.write_text(s,encoding='utf-8')
p=Path('Plugins/ProphecyJolt/Source/ProphecyJolt/Private/ProphecyJoltContactShape.cpp');s=p.read_text(encoding='utf-8');s+='''
#if !UE_BUILD_SHIPPING
#include "Components/SkeletalMeshComponent.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "PhysicsEngine/SkeletalBodySetup.h"
#include "EngineUtils.h"
#include "HAL/IConsoleManager.h"
// On demand only: measure PHAT overlap at the actually displayed PhysicalMesh poses.
static FAutoConsoleCommandWithWorldAndArgs MeasureHandHead(TEXT("Prophecy.Debug.MeasureHandHead"),
    TEXT("Measure displayed PHAT overlap: attacker actor name, defender actor name."),
    FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args,UWorld* World)
{
    if (!World || Args.Num()!=2) return;
    USkeletalMeshComponent* AM=nullptr;USkeletalMeshComponent* BM=nullptr;
    for (TActorIterator<AActor> It(World);It;++It)
    {
        if (It->GetName()!=Args[0] && It->GetName()!=Args[1]) continue;
        TInlineComponentArray<USkeletalMeshComponent*> Meshes(*It);
        for (auto* Mesh:Meshes) if (Mesh->GetFName()==TEXT("PhysicalMesh"))
        {
            if (It->GetName()==Args[0]) AM=Mesh;
            if (It->GetName()==Args[1]) BM=Mesh;
        }
    }
    if (!AM || !BM || !AM->GetPhysicsAsset() || !BM->GetPhysicsAsset()) return;
    auto Build=[](USkeletalMeshComponent* Mesh,FName Bone,FProphecyJoltContactShape& Shape)
    {
        auto* Asset=Mesh->GetPhysicsAsset();const int32 Index=Asset->FindBodyIndex(Bone);
        FString Error;
        return Asset->SkeletalBodySetups.IsValidIndex(Index) &&
            Shape.Build(*Asset->SkeletalBodySetups[Index],Mesh->GetSocketTransform(Bone).GetScale3D(),Error);
    };
    FProphecyJoltContactShape Head;
    if (!Build(BM,TEXT("head"),Head)) return;
    for (FName Bone:{FName(TEXT("hand_l")),FName(TEXT("hand_r")),FName(TEXT("lowerarm_l")),FName(TEXT("lowerarm_r"))})
    {
        FProphecyJoltContactShape Limb;if (!Build(AM,Bone,Limb)) continue;
        const float Visible=Limb.PenetrationCm(AM->GetSocketTransform(Bone),Head,BM->GetSocketTransform(TEXT("head")));
        UE_LOG(LogTemp,Display,TEXT("PHAT_OVERLAP,%.6f,%s,%s,%s,%.6f"),
            World->GetTimeSeconds(),*Args[0],*Args[1],*Bone.ToString(),Visible);
    }
}));
#endif

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyContactDepthTest,"Prophecy.Jolt.ContactShapes.PenetrationDepth",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyContactDepthTest::RunTest(const FString&)
{
    auto* Capsule=NewObject<UBodySetup>();FKSphylElem C;C.Radius=10;C.Length=20;Capsule->AggGeom.SphylElems.Add(C);
    auto* Sphere=NewObject<UBodySetup>();FKSphereElem S;S.Radius=1;Sphere->AggGeom.SphereElems.Add(S);
    FProphecyJoltContactShape A,B;FString Error;
    if (!A.Build(*Capsule,FVector::OneVector,Error) || !B.Build(*Sphere,FVector::OneVector,Error)) { AddError(Error);return false; }
    TestNearlyEqual(TEXT("Capsule/sphere overlap in cm"),A.PenetrationCm(FTransform::Identity,B,FTransform(FVector(10.5,0,0))),.5f,.001f);
    TestEqual(TEXT("Separated shapes"),A.PenetrationCm(FTransform::Identity,B,FTransform(FVector(12,0,0))),0.f);
    return true;
}
#endif
''';p.write_text(s,encoding='utf-8')
p=Path('Saved/Diagnostics/summarize_hook_penetration.py');s=p.read_text(encoding='utf-8').replace('PHAT_DEPTH,','PHAT_OVERLAP,').replace(",native=float(fields[4]),visible=float(fields[5])",",visible=float(fields[4])").replace("peak_native=max(r['native'] for r in bs),",'').replace("r['native']","r['visible']");p.write_text(s,encoding='utf-8')
p=Path('Saved/Diagnostics/test_contact_substeps.py');s=p.read_text(encoding='utf-8').replace('Prophecy.NN.Defense.PhysicalContactShapes','Prophecy.Jolt.ContactShapes.PenetrationDepth');p.write_text(s,encoding='utf-8')
