// Explicit editor-only experiment. Never runs from gameplay or changes a saved asset.
#if WITH_EDITOR
#include "CoreMinimal.h"
#include "Components/SphereComponent.h"
#include "Dom/JsonObject.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "HAL/IConsoleManager.h"
#include "HAL/PlatformFileManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "NiagaraDataInterface.h"
#include "NiagaraEmitter.h"
#include "NiagaraEmitterHandle.h"
#include "NiagaraScript.h"
#include "NiagaraSystem.h"
#include "ProphecyJoltWorldSubsystem.h"
#include "Serialization/JsonSerializer.h"
#include "NiagaraComponent.h"
#include "NiagaraEmitterInstance.h"
#include "NiagaraSystemInstanceController.h"
#include "NiagaraDataInterfaceCollisionQuery.h"
#include "NiagaraDataInterfaceExport.h"
#include "NiagaraDataInterfaceUtilities.h"
#include "Components/BoxComponent.h"
#include "PhysicalMaterials/PhysicalMaterial.h"

namespace ProphecyBloodQueryExperiment
{
using J=TSharedPtr<FJsonObject>;
using V=TSharedPtr<FJsonValue>;
static V Json(const J& O){return MakeShared<FJsonValueObject>(O);}
static void Inspect(TArray<V>& Out)
{
    for(const TCHAR* Name:{TEXT("NS_bloodsplat"),TEXT("NS_bloodarc"),TEXT("NS_bloodwound")})
    {
        const FString Path=FString(TEXT("/Game/_mygame/blood2/"))+Name;
        auto* System=LoadObject<UNiagaraSystem>(nullptr,*Path);
        J Row=MakeShared<FJsonObject>();Row->SetStringField(TEXT("asset"),Path);Row->SetBoolField(TEXT("loaded"),System!=nullptr);
        TArray<V> Emitters;
        if(System)for(const FNiagaraEmitterHandle& H:System->GetEmitterHandles())
        {
            J E=MakeShared<FJsonObject>();E->SetStringField(TEXT("name"),H.GetName().ToString());E->SetBoolField(TEXT("enabled"),H.GetIsEnabled());
            if(const auto* D=H.GetEmitterData())
            {
                E->SetStringField(TEXT("target"),D->SimTarget==ENiagaraSimTarget::CPUSim?TEXT("CPU"):TEXT("GPU"));
                TArray<UNiagaraScript*> Scripts;D->GetScripts(Scripts,false,false);TArray<V> ScriptRows;
                for(auto* S:Scripts)if(S)
                {
                    J R=MakeShared<FJsonObject>();R->SetStringField(TEXT("script"),S->GetPathName());TArray<V> Calls,Interfaces;
                    const FString DumpFolder=FPaths::ProjectSavedDir()/TEXT("Diagnostics/BloodNative20261001/HLSL");
                    IFileManager::Get().MakeDirectory(*DumpFolder,true);
                    if(!S->GetVMExecutableData().LastHlslTranslation.IsEmpty())FFileHelper::SaveStringToFile(S->GetVMExecutableData().LastHlslTranslation,*(DumpFolder/(FString(Name)+TEXT("_")+H.GetName().ToString()+TEXT("_")+S->GetName()+TEXT(".hlsl"))));
                    for(const auto& F:S->GetVMExecutableData().CalledVMExternalFunctions)
                        Calls.Add(MakeShared<FJsonValueString>(F.OwnerName.ToString()+TEXT(".")+F.Name.ToString()));
                    for(const auto& DI:S->GetCachedDefaultDataInterfaces())
                    {
                        J I=MakeShared<FJsonObject>();I->SetStringField(TEXT("name"),DI.Name.ToString());
                        I->SetStringField(TEXT("class"),DI.DataInterface?DI.DataInterface->GetClass()->GetPathName():TEXT("None"));
                        I->SetStringField(TEXT("parameter"),DI.RegisteredParameterMapRead.ToString());Interfaces.Add(Json(I));
                    }
                    R->SetArrayField(TEXT("external_calls"),Calls);R->SetArrayField(TEXT("data_interfaces"),Interfaces);ScriptRows.Add(Json(R));
                }
                E->SetArrayField(TEXT("scripts"),ScriptRows);
            }
            Emitters.Add(Json(E));
        }
        Row->SetArrayField(TEXT("emitters"),Emitters);Out.Add(Json(Row));
    }
}
struct FScope
{
    UWorld* World=nullptr;
    FScope(bool FX=false)
    {
        auto Settings=UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false).CreatePhysicsScene(true)
            .CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(false).EnableTraceCollision(true).CreateFXSystem(FX).SetTransactional(false);
        World=UWorld::CreateWorld(EWorldType::Game,false,NAME_None,nullptr,true,ERHIFeatureLevel::Num,&Settings);
        if(World&&GEngine)GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
    }
    ~FScope(){if(World){World->DestroyWorld(false);if(GEngine)GEngine->DestroyWorldContext(World);World->MarkAsGarbage();}}
};
static bool Measure(J Report,FString& Error)
{
    FScope Scope;UWorld* W=Scope.World;if(!W){Error=TEXT("No isolated world");return false;}
    auto* Native=W->GetSubsystem<UProphecyJoltWorldSubsystem>();if(!Native){Error=TEXT("No native subsystem");return false;}
    FProphecyJoltWorldSettings Settings;Settings.MaxBodies=4096;Settings.MaxBodyPairs=4096;Settings.MaxContactConstraints=4096;Settings.WorkerThreads=1;Settings.GravityCmPerSecondSquared=FVector::ZeroVector;
    auto Init=Native->InitializeSimulation(Settings);if(!Init.IsSuccess()){Error=Init.Message;return false;}
    auto* Actor=W->SpawnActor<AActor>();TArray<USphereComponent*> Proxies;TArray<FVector> Centers;TArray<V> Trials;
    FCollisionQueryParams Params(SCENE_QUERY_STAT(ProphecyBloodQueryExperiment),false);
    // Match stock Niagara CPU trace policy; this is its UE query backend, not a live emitter.
    Params.bReturnPhysicalMaterial=true;Params.bFindInitialOverlaps=false;Params.bIgnoreTouches=true;
    for(int32 Count:{22,220,2200})
    {
        while(Proxies.Num()<Count)
        {
            const int32 I=Proxies.Num();const FVector Center((I%50)*100.,(I/50)*100.,100.);
            auto* P=NewObject<USphereComponent>(Actor);Actor->AddInstanceComponent(P);P->InitSphereRadius(20);
            P->SetCollisionEnabled(ECollisionEnabled::QueryOnly);P->SetCollisionResponseToAllChannels(ECR_Block);
            P->SetWorldLocation(Center);P->RegisterComponent();Proxies.Add(P);Centers.Add(Center);
            FProphecyJoltFixtureBodySettings Body;Body.PositionCm=Center;Body.AssociatedObject=P;FProphecyJoltBodyHandle Handle;
            const auto Status=Native->CreateSphere(20,Body,Handle);if(!Status.IsSuccess()){Error=Status.Message;return false;}
        }
        // Newly inserted Jolt bodies have not yet gone through broadphase maintenance.
        // Measure a running world, rather than the one-off admission tree.
        for(int32 Warm=0;Warm<8;++Warm)
        {
            const auto Step=Native->Step(1.f/60,1);if(!Step.IsSuccess()){Error=Step.Message;return false;}
            W->Tick(LEVELTICK_All,1.f/60);
        }
        constexpr int32 Rays=4096;
        auto Run=[&](bool Jolt,int32& Hits,double& Checksum)
        {
            Hits=0;Checksum=0;const double Start=FPlatformTime::Seconds();
            for(int32 I=0;I<Rays;++I)
            {
                const FVector Center=Centers[(I*37)%Count],A=Center-FVector(40,0,0),B=Center+FVector(40,0,0);
                if(Jolt){FProphecyJoltRayHit H;bool Hit=false;if(Native->RayCast(A,B,H,Hit).IsSuccess()&&Hit){++Hits;Checksum+=H.PositionCm.X;}}
                else {FHitResult H;if(W->LineTraceSingleByChannel(H,A,B,ECC_Visibility,Params)){++Hits;Checksum+=H.ImpactPoint.X;}}
            }
            return (FPlatformTime::Seconds()-Start)*1000;
        };
        int32 Hits;double Sum;Run(false,Hits,Sum);Run(true,Hits,Sum);TArray<V> UEms,Joltms;
        for(int32 Round=0;Round<8;++Round)
        {
            double Totals[2];
            for(int32 Order=0;Order<2;++Order){const bool Jolt=((Round+Order)%2)!=0;Totals[Jolt?1:0]=Run(Jolt,Hits,Sum);if(Hits!=Rays){Error=FString::Printf(TEXT("%s hit count %d/%d at %d bodies"),Jolt?TEXT("Jolt"):TEXT("UE"),Hits,Rays,Count);return false;}}
            UEms.Add(MakeShared<FJsonValueNumber>(Totals[0]));Joltms.Add(MakeShared<FJsonValueNumber>(Totals[1]));
        }
        J T=MakeShared<FJsonObject>();T->SetNumberField(TEXT("bodies"),Count);T->SetNumberField(TEXT("rays_per_sample"),Rays);
        T->SetNumberField(TEXT("warmup_steps"),8);
        T->SetArrayField(TEXT("ue_ms"),UEms);T->SetArrayField(TEXT("jolt_ms"),Joltms);Trials.Add(Json(T));
    }
    Report->SetArrayField(TEXT("query_timings"),Trials);
    Proxies[0]->SetCollisionResponseToChannel(ECC_Visibility,ECR_Ignore);
    FHitResult UEHit;FProphecyJoltRayHit NativeHit;bool NativeFound=false;
    const FVector Start(-40,0,100),End(140,0,100);
    const bool UEFound=W->LineTraceSingleByChannel(UEHit,Start,End,ECC_Visibility,Params);
    auto Status=Native->RayCast(Start,End,NativeHit,NativeFound);
    Report->SetBoolField(TEXT("ue_channel_filter_skips_ignored_body"),UEFound&&UEHit.GetComponent()==Proxies[1]);
    Report->SetBoolField(TEXT("native_fixture_ray_ignores_ue_channel_policy"),Status.IsSuccess()&&NativeFound&&NativeHit.PositionCm.Equals(FVector(-20,0,100),.001));
    for(auto* P:Proxies)P->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    const bool UEWithoutProxy=W->LineTraceSingleByChannel(UEHit,Start,End,ECC_Visibility,Params);
    Status=Native->RayCast(Start,End,NativeHit,NativeFound);
    UObject* Associated=nullptr;
    const bool Identity=NativeFound&&Native->ResolveAssociatedObject(NativeHit.Handle,Associated).IsSuccess()&&Associated==Proxies[0];
    Report->SetBoolField(TEXT("ue_query_without_proxies_hits"),UEWithoutProxy);
    Report->SetBoolField(TEXT("native_query_without_proxies_keeps_hit_and_identity"),Status.IsSuccess()&&NativeFound&&Identity);
    if(UEWithoutProxy||!Identity){Error=TEXT("No-proxy isolation failed");return false;}
    return true;
}
static void Run()
{
    if(!GEngine)return;
    for(const auto& Context:GEngine->GetWorldContexts())if(Context.WorldType==EWorldType::PIE){UE_LOG(LogTemp,Warning,TEXT("Blood experiment preserves active PIE; run after Play ends."));return;}
    J Report=MakeShared<FJsonObject>();Report->SetStringField(TEXT("scope"),TEXT("Read-only compiled blood emitter inventory and isolated equal-sphere UE/Jolt ray microbenchmark. No live Niagara simulation, full frame/pose-sync/rendering cost, paint performance, or production migration claim."));
    TArray<V> Assets;Inspect(Assets);Report->SetArrayField(TEXT("niagara_assets"),Assets);
    FString Error;const bool OK=Measure(Report,Error);Report->SetBoolField(TEXT("success"),OK);Report->SetStringField(TEXT("error"),Error);
    FString Text;FJsonSerializer::Serialize(Report.ToSharedRef(),TJsonWriterFactory<>::Create(&Text));
    const FString Folder=FPaths::ProjectSavedDir()/TEXT("Diagnostics/BloodNative20261001");IFileManager::Get().MakeDirectory(*Folder,true);
    FFileHelper::SaveStringToFile(Text,*(Folder/TEXT("experiment.json")));
    UE_LOG(LogTemp,Display,TEXT("Blood native-query experiment complete success=%d error=%s"),OK,*Error);
}
static FAutoConsoleCommand Command(TEXT("Prophecy.Blood.NativeQueryExperiment"),TEXT("Opt-in isolated blood query experiment; no asset or production settings changes."),FConsoleCommandDelegate::CreateStatic(&Run));
}
#include "ProphecyJoltBloodEmitterExperiment.inl"
#endif
