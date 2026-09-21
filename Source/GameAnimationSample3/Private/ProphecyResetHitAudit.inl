#if WITH_EDITOR
#include "ProphecyHitEventTestSink.h"
#include "ProphecyNNDefenseLibrary.h"
#include "EngineUtils.h"
#include "UObject/StrongObjectPtr.h"
#include "HAL/IConsoleManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"
namespace ProphecyResetHitAudit
{
struct FEntry
{
    TWeakObjectPtr<AProphecyAgent> Agent;
    TWeakObjectPtr<USkeletalMeshComponent> Mesh;
    TStrongObjectPtr<UProphecyHitEventTestSink> Sink;
    int64 AgentContacts=0;
};
static TArray<TUniquePtr<FEntry>> Entries;
static FDelegateHandle Cleanup;
static TArray<TSharedPtr<FJsonValue>> Contacts;
static void Clear()
{
    for (auto& E:Entries)
    {
        if (E->Mesh.IsValid()) E->Mesh->OnComponentHit.RemoveDynamic(E->Sink.Get(),&UProphecyHitEventTestSink::ComponentHit);
        if (E->Agent.IsValid()) E->Agent->OnPhysicalHit.RemoveDynamic(E->Sink.Get(),&UProphecyHitEventTestSink::PhysicalHit);
    }
    Entries.Reset();Contacts.Reset();
    FWorldDelegates::OnWorldCleanup.Remove(Cleanup);Cleanup.Reset();
}
static void Run(const TArray<FString>& Args,UWorld* World)
{
    if (!World || !World->IsGameWorld() || Args.Num()!=1) return;
    if (Args[0]==TEXT("stop")) { Clear();return; }
    if (Args[0]==TEXT("start"))
    {
        Clear();
        for (TActorIterator<AProphecyAgent> It(World);It;++It)
        {
            auto* Mesh=It->GetPoseReferenceMesh();if (!Mesh) continue;
            auto& E=Entries.Add_GetRef(MakeUnique<FEntry>());
            E->Agent=*It;E->Mesh=Mesh;E->Sink.Reset(NewObject<UProphecyHitEventTestSink>());
            E->Sink->OnReceived=[Entry=E.Get()]()
            {
                auto* Other=Cast<AProphecyAgent>(Entry->Sink->LastHit.GetActor());
                if (!Other || !Entry->Agent.IsValid()) return;
                ++Entry->AgentContacts;
                if (Contacts.Num()>=20000) return;
                FName Attack;bool Half=false,Armed=false,Hit=false;int32 Frame=0;
                const bool Active=Other->GetNNAttackState(Attack,Half,Armed,Hit,Frame);
                const auto State=UProphecyNNDefenseLibrary::GetAgentState(Other);
                auto Row=MakeShared<FJsonObject>();
                Row->SetNumberField(TEXT("time"),Other->GetWorld()->GetTimeSeconds());
                Row->SetStringField(TEXT("self"),Entry->Agent->GetName());
                Row->SetStringField(TEXT("other"),Other->GetName());
                Row->SetBoolField(TEXT("mesh_match"),Entry->Sink->LastHit.GetComponent()==Other->GetPoseReferenceMesh());
                Row->SetBoolField(TEXT("not_self"),Other!=Entry->Agent.Get());
                Row->SetNumberField(TEXT("state"),int32(State));
                Row->SetBoolField(TEXT("active"),Active);Row->SetBoolField(TEXT("armed"),Armed);
                Row->SetBoolField(TEXT("hit"),Hit);Row->SetNumberField(TEXT("policy_frame"),Frame);
                Row->SetStringField(TEXT("attack"),Attack.ToString());
                Row->SetStringField(TEXT("my_bone"),Entry->Sink->LastHit.MyBoneName.ToString());
                Row->SetStringField(TEXT("other_bone"),Entry->Sink->LastHit.BoneName.ToString());
                Contacts.Add(MakeShared<FJsonValueObject>(Row));
            };
            Mesh->OnComponentHit.AddDynamic(E->Sink.Get(),&UProphecyHitEventTestSink::ComponentHit);
            It->OnPhysicalHit.AddDynamic(E->Sink.Get(),&UProphecyHitEventTestSink::PhysicalHit);
        }
        Cleanup=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld*,bool,bool){Clear();});
    }
    TArray<TSharedPtr<FJsonValue>> Rows;
    for (const auto& E:Entries) if (E->Agent.IsValid())
    {
        auto Row=MakeShared<FJsonObject>();
        Row->SetStringField(TEXT("agent"),E->Agent->GetName());
        Row->SetNumberField(TEXT("component_hits"),double(E->Sink->ComponentHits));
        Row->SetNumberField(TEXT("physical_hits"),double(E->Sink->PhysicalHits));
        Row->SetNumberField(TEXT("agent_contacts"),double(E->AgentContacts));
        Row->SetBoolField(TEXT("enabled"),E->Agent->bGeneratePhysicalHitEvents);
        Rows.Add(MakeShared<FJsonValueObject>(Row));
    }
    auto Root=MakeShared<FJsonObject>();Root->SetArrayField(TEXT("agents"),Rows);Root->SetArrayField(TEXT("contacts"),Contacts);
    FString Json;FJsonSerializer::Serialize(Root,TJsonWriterFactory<>::Create(&Json));
    FFileHelper::SaveStringToFile(Json,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/ResetHitAudit.json")));
}
static FAutoConsoleCommandWithWorldAndArgs Command(TEXT("Prophecy.Reset.HitAudit"),
    TEXT("On-demand PhysicalMesh hit audit: start/sample/stop. Editor only, no normal gameplay work."),
    FConsoleCommandWithWorldAndArgsDelegate::CreateStatic(&Run));
}
#endif
