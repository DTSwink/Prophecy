#if WITH_DEV_AUTOMATION_TESTS
// Runs in a separate transient world; never edits the user's scene or profiles.
static bool VerifyFKReturnGaze()
{
    using namespace ProphecyFKReturn;
    int32 Failures=0,Checks=0;
    auto Check=[&](bool B,const TCHAR* Message){++Checks;if(!B){++Failures;UE_LOG(LogTemp,Error,TEXT("FKGaze: %s"),Message);}};
    auto* W=UWorld::CreateWorld(EWorldType::Editor,false);
    auto* A=W?W->SpawnActor<AProphecyAgent>():nullptr;
    if(!A)return false;
    ON_SCOPE_EXIT{Remove(A);W->DestroyWorld(false);};
    TArray<FName> Names{FName(TEXT("pelvis"))};TArray<int32> Parents{INDEX_NONE};TArray<FTransform> Pose{FTransform::Identity};
    FTransform Idle[BoneCount];GazeIdle(FVector2f::ZeroVector,Idle);
    for(int32 J=0;J<BoneCount;++J){const auto& D=Data::Bones[J];const int32 P=Names.IndexOfByKey(FName(D.Parent));Names.Add(FName(D.Name));Parents.Add(P);Pose.Add(Idle[J]*Pose[P]);}
    auto JsonPose=[](TConstArrayView<FTransform> P){TArray<TSharedPtr<FJsonValue>> Rows;for(const auto& T:P){const auto Q=T.GetRotation();const auto V=T.GetLocation();TArray<TSharedPtr<FJsonValue>> R;for(double X:{Q.X,Q.Y,Q.Z,Q.W,V.X,V.Y,V.Z})R.Add(MakeShared<FJsonValueNumber>(X));Rows.Add(MakeShared<FJsonValueArray>(R));}return Rows;};
    TArray<TSharedPtr<FJsonValue>> Cases;
    for(float Y:{-1.f,-.45f,0.f,.6f,1.f})for(float P:{-1.f,0.f,.7f})
    {
        FTransform Target[BoneCount];GazeIdle(FVector2f(Y,P),Target);auto World=Pose;
        for(int32 J=0;J<BoneCount;++J){World[J+1]=Target[J]*World[Parents[J+1]];Check(!Target[J].ContainsNaN(),TEXT("Finite gaze target"));Check(FMath::Abs(Target[J].GetLocation().Size()-Idle[J].GetLocation().Size())<1.e-5,TEXT("Bone length retained"));}
        const auto C=MakeShared<FJsonObject>();C->SetNumberField(TEXT("yaw"),Y);C->SetNumberField(TEXT("pitch"),P);C->SetArrayField(TEXT("pose"),JsonPose(World));Cases.Add(MakeShared<FJsonValueObject>(C));
    }
    FProfile Profile;Profile.Duration=1;Profile.Inertia=0;Profile.AngleTimeSeconds=0;
    for(bool World:{false,true})
    {
        Profile.WorldInertia=World;FCurve Old,Zero;
        Check(PrepareForAttack(Old,Profile,1,Names,Parents,Pose,Pose,1.f/30,{},TEXT("pike")),TEXT("Original prepare"));
        Check(PrepareForAttack(Zero,Profile,1,Names,Parents,Pose,Pose,1.f/30,{},TEXT("pike"),Idle),TEXT("Zero gaze prepare"));
        for(float T:{0.f,.2f,.8f,1.f}){auto O=Pose,Z=Pose;Old.Apply(T,O,{},FQuat::Identity);Zero.Apply(T,Z,{},FQuat::Identity);for(int32 J=0;J<O.Num();++J)Check(O[J].Equals(Z[J],0),TEXT("Zero gaze is exact original curve"));}
    }
    Configs.FindOrAdd(A).Profiles.Add(NAME_None,Profile);SetTestReturnTiming(A,true,1,1,0);
    A->UpperNNGazeYawNormalized=.7f;A->UpperNNGazePitchNormalized=.3f;
    Begin(A,TEXT("pike"),Names,Parents,Pose,Pose,0,1.f/30);
    Check(!ActiveGaze.Contains(A),TEXT("Off by default"));Cancel(A);
    Check(UProphecyFKReturnLibrary::SetAttackFKReturnGaze(A,true),TEXT("Enable node"));
    Begin(A,TEXT("pike"),Names,Parents,Pose,Pose,0,1.f/30);
    Check(ActiveGaze.Contains(A),TEXT("Enabled at attack end"));
    const auto Limit=TickPhases.FindChecked(A).Limit;const auto Duration=Active.FindChecked(A).Curve.InverseDuration;
    TArray<FTransform> Previous=Pose,Current=Pose;
    for(int32 Tick=1;Tick<=60;++Tick)
    {
        if(Tick==20){A->UpperNNGazeYawNormalized=-.4f;A->UpperNNGazePitchNormalized=-.6f;}
        FWorldDelegates::OnWorldPreActorTick.Broadcast(W,LEVELTICK_All,Tick%2?1.f/20:1.f/120);
        Previous=Pose;Current=Pose;Check(Apply(A,Tick,Previous,Current,{}),TEXT("Return remains active through final interval"));
        Check(TickPhases.FindChecked(A).Ticks==uint64(Tick),TEXT("FPS independent game tick"));
        Check(TickPhases.FindChecked(A).Limit==Limit && Active.FindChecked(A).Curve.InverseDuration==Duration,TEXT("Gaze never retimes return"));
        if(Tick<60){Check(ActiveGaze.FindChecked(A)==ReadGaze(A),TEXT("Uses current gaze"));FTransform Target[BoneCount];GazeIdle(ReadGaze(A),Target);for(int32 J=0;J<BoneCount;++J){const auto& B=Active.FindChecked(A).Curve.Bones[J];Check(FQuat(B.Start*B.Return.At(1)).GetNormalized().AngularDistance(Target[J].GetRotation().GetNormalized())<1.e-5,TEXT("Live destination updated"));}}
        if(Tick==10)Check(Current.Last().GetRotation().AngularDistance(Pose.Last().GetRotation())>.01,TEXT("Gaze works during full NN hold"));
        const auto Accepted=Current;Previous=Pose;Current=Pose;Apply(A,Tick,Previous,Current,{});for(int32 J=0;J<Current.Num();++J)Check(Current[J].Equals(Accepted[J],0),TEXT("Repeat publication not applied twice"));
    }
    Check(!ActiveGaze.Contains(A),TEXT("Completed return drops gaze work"));
    Apply(A,61,Previous,Current,{});Check(!Active.Contains(A),TEXT("Final interval retires"));
    CaptureReset(A);UProphecyFKReturnLibrary::SetAttackFKReturnGaze(A,false);RestoreReset(A);Check(GazeEnabled.Contains(A),TEXT("Reset restores gaze setting"));
    ParryConfigs.FindOrAdd(A);BeginParry(A,Names,Parents,Pose,Pose,0,1.f/30);Check(!ActiveGaze.Contains(A),TEXT("Parry unaffected"));Cancel(A);
    FCurve Arc;for(auto& B:Arc.Bones){B.Start=FQuat4f::Identity;B.Offset=FVector3f(1,0,0);B.Return.Set(FQuat4f(FVector3f(0,0,1),FMath::DegreesToRadians(179.f)));}
    FVector3f Last=Arc.Bones[0].Return.Axis*Arc.Bones[0].Return.HalfAngle;
    for(float Degrees:{180.f,181.f,190.f,359.f,360.f,361.f}){FTransform Target[BoneCount];for(auto& T:Target)T=FTransform(FQuat(FVector::UpVector,FMath::DegreesToRadians(double(Degrees))),FVector(1,0,0));RetargetGaze(Arc,Target);const auto& B=Arc.Bones[0];const FVector3f Next=B.Return.Axis*B.Return.HalfAngle;Check((Next-Last).Size()<1.5f,TEXT("Continuous arc through 180 and 360"));Last=Next;}
    const auto Report=MakeShared<FJsonObject>();Report->SetNumberField(TEXT("failures"),Failures);Report->SetNumberField(TEXT("checks"),Checks);Report->SetArrayField(TEXT("source"),JsonPose(Pose));Report->SetArrayField(TEXT("cases"),Cases);
    TArray<TSharedPtr<FJsonValue>> N,P;for(auto V:Names)N.Add(MakeShared<FJsonValueString>(V.ToString()));for(auto V:Parents)P.Add(MakeShared<FJsonValueNumber>(V));Report->SetArrayField(TEXT("names"),N);Report->SetArrayField(TEXT("parents"),P);
    FString Output;FJsonSerializer::Serialize(Report,TJsonWriterFactory<>::Create(&Output));FFileHelper::SaveStringToFile(Output,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/AttackFKGaze20261011/native.json")));
    UE_LOG(LogTemp,Display,TEXT("FKGaze failures=%d checks=%d"),Failures,Checks);return Failures==0;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyFKReturnGazeTest,"Prophecy.NN.FKReturn.LiveGaze",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyFKReturnGazeTest::RunTest(const FString&){return TestTrue(TEXT("Live attack gaze"),VerifyFKReturnGaze());}
#if WITH_EDITOR
static FAutoConsoleCommand VerifyFKReturnGazeCommand(TEXT("Prophecy.FKReturn.VerifyGaze"),TEXT("Verify live gaze in an isolated transient world."),FConsoleCommandDelegate::CreateLambda([](){VerifyFKReturnGaze();}));
#endif
#endif
