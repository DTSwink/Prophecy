// Explicit bounded editor capture. No delegates, sampling, allocation or clocks
// remain active after the requested capture or its world ends.
namespace ProphecyAttackPerf
{
enum class EStage { LowerInput,LowerRun,LowerOutput,UpperInput,UpperRun,UpperOutput,Layers,Attack,Debug,Count };
#if WITH_EDITOR
static const TCHAR* Names[]={TEXT("lower_input"),TEXT("lower_run"),TEXT("lower_output"),TEXT("upper_input"),
    TEXT("upper_run"),TEXT("upper_output"),TEXT("layers"),TEXT("attack"),TEXT("debug_mesh")};
struct FRow
{
    double Start=0,WorldMs=0,GapMs=0,Time=0;
    double Stages[int(EStage::Count)]={};
    uint32 Calls[int(EStage::Count)]={};
    TMap<FString,FVector2D> Networks; // Actual RunSync milliseconds and calls by input width/batch/backend.
    ProphecyJolt::CharacterProfiling::FFrame Physical;
    int32 Full=0,Half=0,Locomotion=0,PlayerFrame=-1;
    FString PlayerAttack;
};
struct FCapture
{
    TWeakObjectPtr<UWorld> World;
    FString Tag;
    int32 Limit=0;
    double LastStart=0;
    bool InFrame=false;
    FRow Current;
    TArray<FRow> Rows;
    FDelegateHandle Pre,Post,Cleanup;
};
static TUniquePtr<FCapture> Capture;
static void Finish()
{
    if (!Capture) return;
    auto Done=MoveTemp(Capture);
    FWorldDelegates::OnWorldPreActorTick.Remove(Done->Pre);
    FWorldDelegates::OnWorldPostActorTick.Remove(Done->Post);
    FWorldDelegates::OnWorldCleanup.Remove(Done->Cleanup);
    ProphecyJolt::CharacterProfiling::Disable();
    auto Root=MakeShared<FJsonObject>();TArray<TSharedPtr<FJsonValue>> Rows;
    for (const auto& R:Done->Rows)
    {
        auto J=MakeShared<FJsonObject>();
        J->SetNumberField(TEXT("time"),R.Time);J->SetNumberField(TEXT("world_ms"),R.WorldMs);J->SetNumberField(TEXT("gap_ms"),R.GapMs);
        J->SetNumberField(TEXT("full"),R.Full);J->SetNumberField(TEXT("half"),R.Half);J->SetNumberField(TEXT("locomotion"),R.Locomotion);
        J->SetStringField(TEXT("player_attack"),R.PlayerAttack);J->SetNumberField(TEXT("player_frame"),R.PlayerFrame);
        auto Stages=MakeShared<FJsonObject>();auto Calls=MakeShared<FJsonObject>();auto Networks=MakeShared<FJsonObject>();
        for(int32 I=0;I<int(EStage::Count);++I) { Stages->SetNumberField(Names[I],R.Stages[I]*1000);Calls->SetNumberField(Names[I],R.Calls[I]); }
        for(int32 I=0;I<ProphecyJolt::CharacterProfiling::PhaseCount;++I)
        { Stages->SetNumberField(ProphecyJolt::CharacterProfiling::PhaseNames[I],R.Physical.Seconds[I]*1000);Calls->SetNumberField(ProphecyJolt::CharacterProfiling::PhaseNames[I],R.Physical.Calls[I]); }
        for(const auto& N:R.Networks)
        { auto V=MakeShared<FJsonObject>();V->SetNumberField(TEXT("ms"),N.Value.X);V->SetNumberField(TEXT("calls"),N.Value.Y);Networks->SetObjectField(N.Key,V); }
        J->SetObjectField(TEXT("ms"),Stages);J->SetObjectField(TEXT("calls"),Calls);J->SetObjectField(TEXT("networks"),Networks);
        Rows.Add(MakeShared<FJsonValueObject>(J));
    }
    Root->SetArrayField(TEXT("rows"),Rows);
    Root->SetObjectField(TEXT("processor"),ProphecyJolt::CharacterProfiling::ProcessorEnvironmentJson());
    FString Json;FJsonSerializer::Serialize(Root,TJsonWriterFactory<>::Create(&Json));
    const FString Directory=FPaths::ProjectSavedDir()/TEXT("Diagnostics/AttackPerformance");
    IFileManager::Get().MakeDirectory(*Directory,true);
    const bool Saved=FFileHelper::SaveStringToFile(Json,*(Directory/(Done->Tag+TEXT(".json"))));
    UE_LOG(LogTemp,Display,TEXT("AttackPerformance completed tag=%s frames=%d saved=%d"),*Done->Tag,Done->Rows.Num(),Saved);
}
static void Pre(UWorld* World,ELevelTick Type,float)
{
    if (!Capture || Capture->World.Get()!=World || World->IsPaused() || Type!=LEVELTICK_All) return;
    auto& C=*Capture;C.Current={};auto& R=C.Current;
    for(TActorIterator<AProphecyAgent> It(World);It;++It)
    {
        FName Attack;bool Half=false,Armed=false,Hit=false;int32 Frame=0;
        if(It->GetNNAttackState(Attack,Half,Armed,Hit,Frame))
        { if(Half)++R.Half;else ++R.Full;if(It->IsPlayerControlled()){R.PlayerAttack=Attack.ToString();R.PlayerFrame=Frame;} }
        else ++R.Locomotion;
    }
    R.Time=World->GetTimeSeconds();
    ProphecyJolt::CharacterProfiling::BeginFrame();
    R.Start=FPlatformTime::Seconds();R.GapMs=C.LastStart>0?(R.Start-C.LastStart)*1000:0;C.LastStart=R.Start;C.InFrame=true;
}
static void Post(UWorld* World,ELevelTick,float)
{
    if(!Capture || Capture->World.Get()!=World || !Capture->InFrame)return;
    auto& C=*Capture;C.Current.WorldMs=(FPlatformTime::Seconds()-C.Current.Start)*1000;
    C.Current.Physical=ProphecyJolt::CharacterProfiling::EndFrame();C.InFrame=false;
    C.Rows.Add(MoveTemp(C.Current));if(C.Rows.Num()>=C.Limit)Finish();
}
static FAutoConsoleCommandWithWorldAndArgs Command(TEXT("Prophecy.AttackPerf.Capture"),
    TEXT("Bounded PIE timing capture: <safe_tag> <frames>, or stop. No gameplay settings changed."),
    FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args,UWorld* World)
    {
        if(Args.Num()==1 && Args[0]==TEXT("stop")){Finish();return;}
        if(Capture || !World || !World->IsGameWorld() || Args.Num()!=2)return;
        for(TCHAR C:Args[0])if(!FChar::IsAlnum(C) && C!=TEXT('_') && C!=TEXT('-'))return;
        const int32 Frames=FCString::Atoi(*Args[1]);if(Frames<1 || Frames>4000 || Args[0].IsEmpty())return;
        Capture=MakeUnique<FCapture>();auto& C=*Capture;C.World=World;C.Tag=Args[0];C.Limit=Frames;C.Rows.Reserve(Frames);
        C.Pre=FWorldDelegates::OnWorldPreActorTick.AddStatic(&Pre);C.Post=FWorldDelegates::OnWorldPostActorTick.AddStatic(&Post);
        C.Cleanup=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* W,bool,bool){if(Capture && Capture->World.Get()==W)Finish();});
    }));
class FScope
{
    EStage Stage;double Start=0;
public:
    explicit FScope(EStage S):Stage(S){if(Capture && Capture->InFrame)Start=FPlatformTime::Seconds();}
    ~FScope(){if(Start && Capture && Capture->InFrame){Capture->Current.Stages[int(Stage)]+=FPlatformTime::Seconds()-Start;++Capture->Current.Calls[int(Stage)];}}
};
class FNetworkScope
{
    int32 Width,Batch;bool GPU;double Start=0;
public:
    FNetworkScope(int32 W,int32 B,bool G):Width(W),Batch(B),GPU(G){if(Capture && Capture->InFrame)Start=FPlatformTime::Seconds();}
    ~FNetworkScope(){if(Start && Capture && Capture->InFrame){const double Ms=(FPlatformTime::Seconds()-Start)*1000;auto& N=Capture->Current.Networks.FindOrAdd(FString::Printf(TEXT("%d_b%d_%s"),Width,Batch,GPU?TEXT("gpu"):TEXT("cpu")));N.X+=Ms;N.Y+=1;}}
};
#else
struct FScope { explicit FScope(EStage){} };
struct FNetworkScope { FNetworkScope(int32,int32,bool){} };
#endif
}
