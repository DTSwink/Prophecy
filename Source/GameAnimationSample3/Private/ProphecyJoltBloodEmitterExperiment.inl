// Explicit editor experiment only. Never hooks a production component or saved script.
namespace ProphecyBloodEmitterExperiment
{
using namespace ProphecyBloodQueryExperiment;
struct FRequest { FVector A,B; ECollisionChannel Channel; bool Complex; };
struct FResult { bool Hit=false,Inside=false; FVector Position=FVector::ZeroVector,Normal=FVector::ZeroVector; float Friction=0,Restitution=0; int32 Surface=0; };
struct FSite
{
    FCriticalSection Mutex;
    FString Name; FVMExternalFunction Function; const FVMExternalFunction* Original=nullptr;
    FNiagaraScriptExecutionContext* Context=nullptr; int32 Index=0;
    TArray<FRequest> Pending; TArray<FResult> Results;
    int64 Invocations=0,Skipped=0,Submitted=0,Hits=0,Exports=0,Complex=0;
    TMap<int32,int64> Channels;
    bool Disable=false;
    FBox TraceBounds=FBox(ForceInit);
    TArray<FBasicParticleData> ExportSamples;
};
static void CollisionVM(FSite& S,FVectorVMExternalFunctionContext& C)
{
    FScopeLock Lock(&S.Mutex);
    VectorVM::FUserPtrHandler<CQDIPerInstanceData> D(C);
    FNDIInputParam<int32> ID(C); FNDIInputParam<FNiagaraPosition> A(C),B(C);
    FNDIInputParam<ECollisionChannel> Channel(C); FNDIInputParam<FNiagaraBool> Skip(C),Complex(C);
    FNDIOutputParam<int32> NewID(C); FNDIOutputParam<FNiagaraBool> Valid(C),Inside(C);
    FNDIOutputParam<FNiagaraPosition> Pos(C); FNDIOutputParam<FVector3f> Normal(C);
    FNDIOutputParam<float> Friction(C),Restitution(C); FNDIOutputParam<int32> Surface(C);
    const auto LWC=D->SystemInstance->GetLWCConverter();
    for(int32 I=0;I<C.GetNumInstances();++I)
    {
        const int32 Old=ID.GetAndAdvance(); const FVector Start=LWC.ConvertSimulationPositionToWorld(A.GetAndAdvance()),End=LWC.ConvertSimulationPositionToWorld(B.GetAndAdvance());
        const auto Ch=Channel.GetAndAdvance(); const bool InputSkip=Skip.GetAndAdvance(),Cx=Complex.GetAndAdvance();const bool SkipIt=InputSkip||S.Disable;
        ++S.Invocations; S.Skipped+=SkipIt; S.Complex+=Cx; ++S.Channels.FindOrAdd(int32(Ch));
        int32 Next=0;
        if(!SkipIt&&(End-Start).SizeSquared()>SMALL_NUMBER){Next=S.Pending.Add({Start,End,Ch,Cx})+1;++S.Submitted;S.TraceBounds+=Start;S.TraceBounds+=End;}
        NewID.SetAndAdvance(Next);
        const FResult R=Old>0&&S.Results.IsValidIndex(Old-1)?S.Results[Old-1]:FResult();
        S.Hits+=R.Hit;
        Valid.SetAndAdvance(R.Hit);Inside.SetAndAdvance(R.Inside);
        Pos.SetAndAdvance(R.Hit?LWC.ConvertWorldToSimulationPosition(R.Position):FNiagaraPosition(FVector3f::ZeroVector));
        Normal.SetAndAdvance(FVector3f(R.Normal));Friction.SetAndAdvance(R.Friction);Restitution.SetAndAdvance(R.Restitution);Surface.SetAndAdvance(R.Surface);
    }
}
static void ExportVM(FSite& S,FVectorVMExternalFunctionContext& C)
{
    FScopeLock Lock(&S.Mutex);
    // Observe the real compiled export condition/data at the callback boundary.
    // Painting/callback object costs are deliberately outside this producer experiment.
    VectorVM::FUserPtrHandler<uint8> D(C);
    FNDIInputParam<FNiagaraBool> Store(C); FNDIInputParam<FVector3f> Pos(C);
    FNDIInputParam<float> Size(C); FNDIInputParam<FVector3f> Velocity(C); FNDIOutputParam<FNiagaraBool> Out(C);
    for(int32 I=0;I<C.GetNumInstances();++I)
    {
        const bool Save=Store.GetAndAdvance();FBasicParticleData Sample;Sample.Position=FVector(Pos.GetAndAdvance());Sample.Size=Size.GetAndAdvance();Sample.Velocity=FVector(Velocity.GetAndAdvance());
        ++S.Invocations;S.Exports+=Save;if(Save)S.ExportSamples.Add(Sample);Out.SetAndAdvance(Save);
    }
}
static FResult UEQuery(UWorld* W,const FRequest& Q)
{
    FCollisionQueryParams P(SCENE_QUERY_STAT(ProphecyBloodEmitterExperiment),Q.Complex);
    P.bReturnPhysicalMaterial=true;P.bIgnoreTouches=true;P.bFindInitialOverlaps=false;
    FHitResult H;FResult R;R.Hit=W->LineTraceSingleByChannel(H,Q.A,Q.B,Q.Channel,P);
    if(R.Hit){R.Position=H.ImpactPoint;R.Normal=H.ImpactNormal;R.Inside=H.bStartPenetrating;if(H.PhysMaterial.IsValid()){R.Friction=H.PhysMaterial->Friction;R.Restitution=H.PhysMaterial->Restitution;R.Surface=H.PhysMaterial->SurfaceType;}}
    return R;
}
static bool Trial(UWorld* W,UProphecyJoltWorldSubsystem* Native,UNiagaraSystem* System,int32 Mode,J Row,FString& Error,TArray<FBasicParticleData>& Baseline)
{
    auto* Actor=W->SpawnActor<AActor>();auto* C=NewObject<UNiagaraComponent>(Actor);Actor->AddInstanceComponent(C);
    C->SetAutoActivate(false);C->SetAutoDestroy(false);C->SetForceSolo(true);C->SetAsset(System);
    C->SetWorldLocation(FVector(0,0,150));C->RegisterComponent();C->Activate(true);C->SetComponentTickEnabled(false);
    C->AdvanceSimulation(1,1.f/60);
    W->Tick(LEVELTICK_All,1.f/60);
    auto Controller=C->GetSystemInstanceController();auto* Instance=Controller?Controller->GetSoloSystemInstance():nullptr;
    if(!Instance){Error=TEXT("No isolated Niagara instance");Actor->Destroy();return false;}
    Instance->WaitForConcurrentTickAndFinalize();
    TArray<TUniquePtr<FSite>> Sites;
    for(auto& E:Instance->GetEmitters())if(E->GetEmitterHandle().GetIsEnabled()&&!E->IsDisabled()&&E->GetSimTarget()==ENiagaraSimTarget::CPUSim)
    {
        auto& Context=E->GetUpdateExecutionContext();
        if(!Context.Script)continue;
        const auto& Calls=Context.Script->GetVMExecutableData().CalledVMExternalFunctions;
        for(int32 I=0;I<Calls.Num();++I)
        {
            const bool Collision=Calls[I].Name==TEXT("PerformCollisionQueryAsyncCPU"),Export=Calls[I].Name==TEXT("ExportParticleData");
            if((Collision&&Mode!=0)||Export)
            {
                if(!Context.FunctionTable.IsValidIndex(I)){Error=TEXT("VM function table mismatch");break;}
                auto S=MakeUnique<FSite>();S->Name=E->GetEmitterHandle().GetName().ToString()+TEXT(".")+Calls[I].OwnerName.ToString();
                S->Disable=(Mode==6&&S->Name.Contains(TEXT("CollisionQueryAndResponse.Query")))||(Mode==7&&S->Name.Contains(TEXT("CollisionQueryAndResponse001.Query")));
                S->Context=&Context;S->Index=I;S->Original=Context.FunctionTable[I];FSite* Raw=S.Get();
                if(Collision)S->Function=FVMExternalFunction::CreateLambda([Raw](FVectorVMExternalFunctionContext& VM){CollisionVM(*Raw,VM);});
                else S->Function=FVMExternalFunction::CreateLambda([Raw](FVectorVMExternalFunctionContext& VM){ExportVM(*Raw,VM);});
                Context.FunctionTable[I]=&S->Function;Sites.Add(MoveTemp(S));
            }
        }
    }
    double TickMs=0,QueryMs=0,MaxHitError=0,MaxNormalError=0;int64 ParticleTicks=0;int32 MaxParticles=0,MaxQueue=0,Mismatches=0,NativeHits=0;
    TArray<V> Frames;
    const FDelegateHandle TickHandle=FWorldDelegates::OnWorldPreActorTick.AddLambda([W,C,Instance](UWorld* TickedWorld,ELevelTick,float Delta)
    {if(TickedWorld==W){C->AdvanceSimulation(1,Delta);Instance->WaitForConcurrentTickAndFinalize();}});
    for(int32 Frame=0;Frame<240&&Error.IsEmpty();++Frame)
    {
        const double T0=FPlatformTime::Seconds();
        // Preserve the stock one-frame query lifecycle: collect after completed previous
        // dispatch, simulate/submit, then finish this frame's traces. A world tick followed
        // by a manual Niagara tick queries unfinished tasks and is not a valid baseline.
        W->Tick(LEVELTICK_All,1.f/60);
        TickMs+=(FPlatformTime::Seconds()-T0)*1000;
        int32 Particles=0,Requests=0;for(auto& E:Instance->GetEmitters())if(E->GetSimTarget()==ENiagaraSimTarget::CPUSim)Particles+=E->GetNumParticles();
        ParticleTicks+=Particles;MaxParticles=FMath::Max(MaxParticles,Particles);
        const double T1=FPlatformTime::Seconds();
        for(auto& S:Sites)
        {
            Requests+=S->Pending.Num();S->Results.Reset(S->Pending.Num());
            for(const FRequest& Q:S->Pending)
            {
                FResult R;
                if(Mode==1)R=UEQuery(W,Q);
                if(Mode>=2&&Mode!=3)
                {
                    FProphecyJoltRayHit H;bool Hit=false;const auto Status=Native->RayCast(Q.A,Q.B,H,Hit);
                    if(!Status.IsSuccess()){Error=Status.Message;break;}
                    R.Hit=Hit;if(Hit){R.Position=H.PositionCm;R.Normal=H.Normal;R.Inside=H.Fraction==0;R.Friction=.7f;R.Restitution=.3f;++NativeHits;}
                    // A quality-preserving hybrid: cheap native misses, existing UE
                    // precision/material semantics only for confirmed native contacts.
                    // Requires matching admitted geometry; not a general scene fallback.
                    if(Mode==8&&Hit)R=UEQuery(W,Q);
                    if(Mode==4){const FResult Ref=UEQuery(W,Q);Mismatches+=(Ref.Hit!=R.Hit)||(Ref.Hit&&(!Ref.Position.Equals(R.Position,.1)||!Ref.Normal.Equals(R.Normal,.01)));if(Ref.Hit&&R.Hit){MaxHitError=FMath::Max(MaxHitError,FVector::Distance(Ref.Position,R.Position));MaxNormalError=FMath::Max(MaxNormalError,FVector::Distance(Ref.Normal,R.Normal));}}
                }
                S->Results.Add(R);
            }
            S->Pending.Reset();
        }
        QueryMs+=(FPlatformTime::Seconds()-T1)*1000;MaxQueue=FMath::Max(MaxQueue,Requests);
        if(Frame%30==0){J F=MakeShared<FJsonObject>();F->SetNumberField(TEXT("frame"),Frame);F->SetNumberField(TEXT("particles"),Particles);F->SetNumberField(TEXT("requests"),Requests);Frames.Add(Json(F));}
    }
    FWorldDelegates::OnWorldPreActorTick.Remove(TickHandle);
    const double DrainStart=FPlatformTime::Seconds();W->Tick(LEVELTICK_All,1.f/60);TickMs+=(FPlatformTime::Seconds()-DrainStart)*1000;
    // Restore all pointers before destroying instances or their delegates.
    TArray<V> SiteRows;
    TArray<FBasicParticleData> Samples;
    for(auto& S:Sites)
    {
        if(S->Context->FunctionTable.IsValidIndex(S->Index)&&S->Context->FunctionTable[S->Index]==&S->Function)S->Context->FunctionTable[S->Index]=S->Original;
        J R=MakeShared<FJsonObject>();R->SetStringField(TEXT("name"),S->Name);R->SetNumberField(TEXT("invocations"),S->Invocations);R->SetNumberField(TEXT("skipped"),S->Skipped);R->SetNumberField(TEXT("submitted"),S->Submitted);R->SetNumberField(TEXT("returned_hits"),S->Hits);R->SetNumberField(TEXT("exports"),S->Exports);R->SetNumberField(TEXT("complex"),S->Complex);
        R->SetStringField(TEXT("bounds_min"),S->TraceBounds.Min.ToString());R->SetStringField(TEXT("bounds_max"),S->TraceBounds.Max.ToString());
        J Channels=MakeShared<FJsonObject>();for(auto P:S->Channels)Channels->SetNumberField(FString::FromInt(P.Key),P.Value);R->SetObjectField(TEXT("channels"),Channels);SiteRows.Add(Json(R));
        Samples.Append(S->ExportSamples);
    }
    if(Mode==0&&Baseline.IsEmpty())Baseline=Samples;
    double MaxPositionError=0,MaxVelocityError=0,MaxSizeError=0;
    TArray<V> Differences;
    if(Samples.Num()==Baseline.Num())for(int32 I=0;I<Samples.Num();++I){const double Distance=FVector::Distance(Samples[I].Position,Baseline[I].Position);MaxPositionError=FMath::Max(MaxPositionError,Distance);MaxVelocityError=FMath::Max(MaxVelocityError,FVector::Distance(Samples[I].Velocity,Baseline[I].Velocity));MaxSizeError=FMath::Max(MaxSizeError,double(FMath::Abs(Samples[I].Size-Baseline[I].Size)));if(Distance>.1&&Differences.Num()<8){J D=MakeShared<FJsonObject>();D->SetNumberField(TEXT("index"),I);D->SetNumberField(TEXT("error_cm"),Distance);D->SetStringField(TEXT("stock"),Baseline[I].Position.ToString());D->SetStringField(TEXT("candidate"),Samples[I].Position.ToString());Differences.Add(Json(D));}}
    Row->SetBoolField(TEXT("export_count_matches_stock"),Samples.Num()==Baseline.Num());Row->SetNumberField(TEXT("max_export_position_error_cm"),MaxPositionError);Row->SetNumberField(TEXT("max_export_velocity_error"),MaxVelocityError);Row->SetNumberField(TEXT("max_export_size_error"),MaxSizeError);
    Row->SetNumberField(TEXT("max_hit_position_error_cm"),MaxHitError);Row->SetNumberField(TEXT("max_hit_normal_error"),MaxNormalError);Row->SetArrayField(TEXT("export_differences"),Differences);
    Row->SetNumberField(TEXT("mode"),Mode);Row->SetNumberField(TEXT("tick_ms"),TickMs);Row->SetNumberField(TEXT("query_ms"),QueryMs);Row->SetNumberField(TEXT("particle_ticks"),ParticleTicks);Row->SetNumberField(TEXT("max_particles"),MaxParticles);Row->SetNumberField(TEXT("max_queue"),MaxQueue);Row->SetNumberField(TEXT("native_hits"),NativeHits);Row->SetNumberField(TEXT("mismatches"),Mismatches);Row->SetArrayField(TEXT("sites"),SiteRows);Row->SetArrayField(TEXT("frames"),Frames);
    C->DeactivateImmediate();C->DestroyComponent();Actor->Destroy();return Error.IsEmpty();
}
static void Run()
{
    if(!GEngine)return;for(const auto& C:GEngine->GetWorldContexts())if(C.WorldType==EWorldType::PIE){UE_LOG(LogTemp,Warning,TEXT("Blood emitter experiment refuses active PIE"));return;}
    FScope Scope(true);auto* W=Scope.World;J Report=MakeShared<FJsonObject>();FString Error;
    TArray<V> Inventory;Inspect(Inventory);
    auto* Native=W?W->GetSubsystem<UProphecyJoltWorldSubsystem>():nullptr;
    if(!Native){UE_LOG(LogTemp,Error,TEXT("No isolated world/native subsystem"));return;}
    FProphecyJoltWorldSettings Settings;Settings.GravityCmPerSecondSquared=FVector::ZeroVector;
    auto Status=Native->InitializeSimulation(Settings);if(!Status.IsSuccess()){UE_LOG(LogTemp,Error,TEXT("%s"),*Status.Message);return;}
    auto* A=W->SpawnActor<AActor>();
    auto* Floor=NewObject<UBoxComponent>(A);A->AddInstanceComponent(Floor);Floor->SetBoxExtent(FVector(10000,10000,10));Floor->SetWorldLocation(FVector(0,0,-10));Floor->SetCollisionEnabled(ECollisionEnabled::QueryOnly);Floor->SetCollisionResponseToAllChannels(ECR_Block);Floor->RegisterComponent();
    auto* Mat=NewObject<UPhysicalMaterial>(Floor);Mat->Friction=.7f;Mat->Restitution=.3f;Floor->SetPhysMaterialOverride(Mat);
    FProphecyJoltFixtureBodySettings B;B.bDynamic=false;B.Friction=.7f;B.Restitution=.3f;B.PositionCm=FVector(0,0,-10);B.AssociatedObject=Floor;FProphecyJoltBodyHandle H;
    Status=Native->CreateBox(FVector(10000,10000,10),0,B,H);if(!Status.IsSuccess())Error=Status.Message;
    for(int32 I=0;I<8;++I){Native->Step(1.f/60,1);W->Tick(LEVELTICK_All,1.f/60);}
    TArray<V> Trials;
    TArray<UBoxComponent*> Shapes;Shapes.Add(Floor);
    for(const TCHAR* Name:{TEXT("NS_bloodsplat"),TEXT("NS_bloodarc"),TEXT("NS_bloodwound")})
    {
        // Wounds need a nearby receiver; the other effects exercise the floor alone.
        if(FString(Name)==TEXT("NS_bloodwound"))for(int32 Axis=0;Axis<3;++Axis)for(int32 Sign:{-1,1})
        {
            FVector Center(0,0,150),Extent(200,200,200);Center[Axis]+=Sign*30.;Extent[Axis]=2.;
            auto* Box=NewObject<UBoxComponent>(A);A->AddInstanceComponent(Box);Box->SetBoxExtent(Extent);Box->SetWorldLocation(Center);Box->SetCollisionEnabled(ECollisionEnabled::QueryOnly);Box->SetCollisionResponseToAllChannels(ECR_Block);Box->RegisterComponent();Box->SetPhysMaterialOverride(Mat);Shapes.Add(Box);
            FProphecyJoltFixtureBodySettings Body;Body.bDynamic=false;Body.Friction=.7f;Body.Restitution=.3f;Body.PositionCm=Center;Body.AssociatedObject=Box;FProphecyJoltBodyHandle Handle;Status=Native->CreateBox(Extent,0,Body,Handle);if(!Status.IsSuccess())Error=Status.Message;
        }
        // Keep fixture bodies stationary; broadphase admission is warmed before sampling.
        for(int32 I=0;I<8;++I){Native->Step(1.f/60,1);W->Tick(LEVELTICK_All,1.f/60);}
        auto* Source=LoadObject<UNiagaraSystem>(nullptr,*(FString(TEXT("/Game/_mygame/blood2/"))+Name));if(!Source){Error=TEXT("Missing blood system");break;}
        auto* System=DuplicateObject<UNiagaraSystem>(Source,GetTransientPackage());System->AddToRoot();
        for(auto& E:System->GetEmitterHandles())if(auto* D=E.GetEmitterData()){D->bDeterminism=true;D->RandomSeed=12345;if(D->SimTarget==ENiagaraSimTarget::GPUComputeSim)E.SetIsEnabled(false,*System,false);}
        System->RequestCompile(true);System->WaitForCompilationComplete(false,false);
        for(auto& E:System->GetEmitterHandles())if(auto* D=E.GetEmitterData())
        {
            TArray<UNiagaraScript*> Scripts;D->GetScripts(Scripts,false,false);
            for(auto* S:Scripts)if(S&&!S->GetVMExecutableData().LastHlslTranslation.IsEmpty())FFileHelper::SaveStringToFile(S->GetVMExecutableData().LastHlslTranslation,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/BloodNative20261001/HLSL")/(FString(Name)+TEXT("_test_")+E.GetName().ToString()+TEXT("_")+S->GetName()+TEXT(".hlsl"))));
        }
        TArray<FBasicParticleData> Baseline;
        for(int32 Round=0;Round<3&&Error.IsEmpty();++Round)for(int32 K=0;K<9&&Error.IsEmpty();++K)
        {
            const int32 Mode=(K+Round)%9;for(auto* Shape:Shapes)Shape->SetCollisionEnabled(Mode==5?ECollisionEnabled::NoCollision:ECollisionEnabled::QueryOnly);
            J Row=MakeShared<FJsonObject>();Row->SetStringField(TEXT("asset"),Name);Row->SetNumberField(TEXT("round"),Round);
            Trial(W,Native,System,Mode,Row,Error,Baseline);Trials.Add(Json(Row));
        }
        System->RemoveFromRoot();if(!Error.IsEmpty())break;
    }
    Report->SetArrayField(TEXT("trials"),Trials);Report->SetStringField(TEXT("error"),Error);Report->SetBoolField(TEXT("success"),Error.IsEmpty());
    FString Text;FJsonSerializer::Serialize(Report.ToSharedRef(),TJsonWriterFactory<>::Create(&Text));FFileHelper::SaveStringToFile(Text,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/BloodNative20261001/emitters.json")));
    UE_LOG(LogTemp,Display,TEXT("Blood live emitter experiment finished: %s"),Error.IsEmpty()?TEXT("OK"):*Error);
}
static FAutoConsoleCommand Command(TEXT("Prophecy.Blood.EmitterExperiment"),TEXT("Opt-in isolated actual CPU emitter experiment. No production asset edits."),FConsoleCommandDelegate::CreateStatic(&Run));
}
