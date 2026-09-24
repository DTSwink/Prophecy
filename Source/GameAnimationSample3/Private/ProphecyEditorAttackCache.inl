// Editor-only, exclusively leased native model. No actor/history/pose is cached.
#if WITH_EDITOR
namespace ProphecyEditorAttackCache
{
static TAutoConsoleVariable<int32> Enabled(TEXT("Prophecy.Editor.AttackWarmup"),1,
    TEXT("Prepare attack models at PIE startup and retain one idle model between Play sessions. 0 restores lazy loading."));
static TUniquePtr<FSlashNative> Idle;
static FString IdleKey;
static TMap<TWeakObjectPtr<const AProphecyNNLocomotionManager>,FString> Leases;
static FDelegateHandle ExitHandle;
static void Clear()
{
    Idle.Reset();IdleKey.Reset();Leases.Reset();
}
static FAutoConsoleCommand ClearCommand(TEXT("Prophecy.Editor.ClearAttackCache"),
    TEXT("Release the idle attack cache; active models keep running but will not be retained."),FConsoleCommandDelegate::CreateStatic(&Clear));
static bool Uses(const AProphecyNNLocomotionManager* Owner)
{
    return Enabled.GetValueOnGameThread()!=0 && Owner && Owner->GetWorld()
        && Owner->GetWorld()->WorldType==EWorldType::PIE;
}
static FString Fingerprint(const FString& Directory)
{
    FString Text;TSharedPtr<FJsonObject> Native;
    if (!FFileHelper::LoadFileToString(Text,*(Directory/TEXT("prophecy_slash_native.json")))
        || !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Native) || !Native.IsValid()) return {};
    TArray<FString> Files{TEXT("prophecy_slash_runtime.json"),TEXT("prophecy_slash_native.json")};
    const TSharedPtr<FJsonObject>* Networks=nullptr;
    if (!Native->TryGetObjectField(TEXT("networks"),Networks)) return {};
    for (const auto& Pair:(*Networks)->Values)
    {
        FString File;
        if (!Pair.Value->AsObject().IsValid() || !Pair.Value->AsObject()->TryGetStringField(TEXT("file"),File)) return {};
        Files.AddUnique(File);
    }
    // Optional auxiliary data can be loaded into a model after acquisition.
    for (const TCHAR* File:{TEXT("prophecy_slash_half_gt.json")})
        if (FPaths::FileExists(Directory/File)) Files.Add(File);
    Files.Sort();
    FString Key=FPaths::ConvertRelativePathToFull(Directory);
    // HashFile requires a nonempty caller-supplied buffer; otherwise its read
    // loop cannot advance. Reuse one bounded buffer across all model files.
    TArray<uint8> Scratch;Scratch.SetNumUninitialized(64*1024);
    for (const FString& File:Files)
    {
        const FMD5Hash Hash=FMD5Hash::HashFile(*(Directory/File),&Scratch);
        if (!Hash.IsValid()) return {};
        Key+=TEXT("|")+File+TEXT(":")+LexToString(Hash);
    }
    return Key;
}
static TUniquePtr<FSlashNative> Acquire(const AProphecyNNLocomotionManager* Owner,const FString& Key)
{
    if (Key.IsEmpty()) return {};
    if (!ExitHandle.IsValid()) ExitHandle=FCoreDelegates::OnEnginePreExit.AddStatic(&Clear);
    // Different content never reuses a stale session, even if timestamps match.
    if (IdleKey!=Key) { Idle.Reset();IdleKey.Reset(); }
    Leases.Add(Owner,Key);
    return MoveTemp(Idle); // Never share writable inference buffers across worlds.
}
static void Release(const AProphecyNNLocomotionManager* Owner,TUniquePtr<FSlashNative>& Model,bool Ready)
{
    FString Key;
    if (!Leases.RemoveAndCopyValue(Owner,Key)) return;
    if (!Uses(Owner)) { Idle.Reset();IdleKey.Reset();return; }
    if (Ready && Model) { Idle=MoveTemp(Model);IdleKey=MoveTemp(Key); }
}
#if WITH_DEV_AUTOMATION_TESTS
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyAttackCacheFingerprintTest,"Prophecy.Editor.AttackCache.Fingerprint",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyAttackCacheFingerprintTest::RunTest(const FString&)
{
    const FString Directory=FPaths::ProjectSavedDir()/TEXT("Automation/AttackCache")/FGuid::NewGuid().ToString();
    IFileManager::Get().MakeDirectory(*Directory,true);
    const FString Native=Directory/TEXT("prophecy_slash_native.json");
    const FString Contract=Directory/TEXT("prophecy_slash_runtime.json");
    const FString Model=Directory/TEXT("network.onnx");
    FFileHelper::SaveStringToFile(TEXT("{\"networks\":{\"test\":{\"file\":\"network.onnx\"}}}"),*Native);
    FFileHelper::SaveStringToFile(TEXT("contract-a"),*Contract);
    FFileHelper::SaveStringToFile(TEXT("weights-a"),*Model);
    const FString A=Fingerprint(Directory);
    TestFalse(TEXT("Valid data has a cache key"),A.IsEmpty());
    TestEqual(TEXT("Unchanged content has the same key"),Fingerprint(Directory),A);
    const FDateTime Stamp=IFileManager::Get().GetTimeStamp(*Model);
    FFileHelper::SaveStringToFile(TEXT("weights-b"),*Model);
    IFileManager::Get().SetTimeStamp(*Model,Stamp);
    TestNotEqual(TEXT("Same-size weights with unchanged timestamp invalidate"),Fingerprint(Directory),A);
    FFileHelper::SaveStringToFile(TEXT("weights-a"),*Model);
    TestEqual(TEXT("Restored content matches"),Fingerprint(Directory),A);
    FFileHelper::SaveStringToFile(TEXT("contract-b"),*Contract);
    TestNotEqual(TEXT("Contract-only change invalidates"),Fingerprint(Directory),A);
    IFileManager::Get().Delete(*Model);
    TestTrue(TEXT("Missing model cannot reuse cached data"),Fingerprint(Directory).IsEmpty());
    IFileManager::Get().Delete(*Native);IFileManager::Get().Delete(*Contract);
    IFileManager::Get().DeleteDirectory(*Directory,false,false);
    return !HasAnyErrors();
}
#endif
}
#endif
