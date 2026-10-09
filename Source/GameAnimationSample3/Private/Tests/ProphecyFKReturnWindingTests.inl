#if WITH_DEV_AUTOMATION_TESTS
// Pure math diagnostic: can run without changing PIE, assets, or the editor's
// global automation state (which conflicts with an already-running CEF browser).
static bool VerifyFKSlashWinding()
{
    using namespace ProphecyFKReturn;
    const FString Directory=FPaths::ProjectSavedDir()/TEXT("Diagnostics/SlashUnwind20261008/");
    FString Json;TSharedPtr<FJsonObject> Root;
    if(!FFileHelper::LoadFileToString(Json,*(Directory+TEXT("verification-input.json"))) ||
        !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Json),Root))return false;
    int32 Failures=0,Unchanged=0,Changed=0,Samples=0;
    TArray<TSharedPtr<FJsonValue>> Cases;
    auto Check=[&](bool OK,const TCHAR* Message)
    {if(!OK){++Failures;UE_LOG(LogTemp,Error,TEXT("FKSlashWinding: %s"),Message);}};
    auto ReadPose=[](const TArray<TSharedPtr<FJsonValue>>& Rows)
    {
        TArray<FTransform> Pose;
        for(const auto& V:Rows){const auto& A=V->AsArray();Pose.Emplace(
            FQuat(A[0]->AsNumber(),A[1]->AsNumber(),A[2]->AsNumber(),A[3]->AsNumber()),
            FVector(A[4]->AsNumber(),A[5]->AsNumber(),A[6]->AsNumber()));}
        return Pose;
    };
    for(const auto& Value:Root->GetArrayField(TEXT("cases")))
    {
        const auto C=Value->AsObject();TArray<FName> Names;TArray<int32> Parents;
        for(const auto& V:C->GetArrayField(TEXT("names")))Names.Add(FName(V->AsString()));
        for(const auto& V:C->GetArrayField(TEXT("parents")))Parents.Add(int32(V->AsNumber()));
        const auto Previous=ReadPose(C->GetArrayField(TEXT("previous"))),Current=ReadPose(C->GetArrayField(TEXT("current")));
        const FName Attack(C->GetStringField(TEXT("attack")));const bool Expected=C->GetBoolField(TEXT("change"));
        const auto& F=C->GetArrayField(TEXT("frame"));const FQuat Frame(F[0]->AsNumber(),F[1]->AsNumber(),F[2]->AsNumber(),F[3]->AsNumber());
        const int32 BeforeFailures=Failures;
        for(bool World:{false,true})for(float Inertia:{0.f,1.f})for(float Easing:{0.f,1.f})
        {
            FProfile P;P.Duration=.28f;P.Inertia=Inertia;P.Easing=Easing;P.WorldInertia=World;
            P.AngleTimeSeconds=.29f;P.InertiaHold=.05f;P.InertiaDecay=.8f;
            for(float& Weight:P.Weights)Weight=1;
            FCurve Old,New;Old.SeedFrame=New.SeedFrame=Frame;
            Check(Prepare(Old,P,1,Names,Parents,Previous,Current,1.f/30),TEXT("Legacy prepare"));
            Check(PrepareForAttack(New,P,1,Names,Parents,Previous,Current,1.f/30,{},Attack),TEXT("New prepare"));
            const auto& A=Old.Bones[10].Return;const auto& B=New.Bones[10].Return;
            const bool Switched=A.HalfAngle!=B.HalfAngle;
            Check(Switched==Expected,TEXT("Independent inward/direction oracle"));
            Check(Old.InverseDuration==New.InverseDuration,TEXT("Duration unchanged"));
            if(Switched)
            {
                Check(B.Axis.Equals(-A.Axis,0) && B.HalfAngle==PI-A.HalfAngle,TEXT("Only complementary arc selected"));
                Check(FQuat(A.At(1)).GetNormalized().AngularDistance(FQuat(B.At(1)).GetNormalized())<1.e-5,TEXT("Same orientation endpoint"));
            }
            Old.SetAlphaHold(1);New.SetAlphaHold(1);
            for(float X:{0.f,.001f,.05f,.1f,.25f,.5f,.75f,.99f,1.f})
            {
                const auto W=Old.Weights(X/Old.InverseDuration);
                FQuat4f OQ[BoneCount],NQ[BoneCount];FVector3f OP[BoneCount],NP[BoneCount];
                // Moving pelvis and carrier must preserve equivalence too.
                const FQuat4f Pelvis=FQuat4f(FVector3f(0,0,1),X*.4f)*Old.StartPelvis;
                const FQuat4f Delta(FVector3f(0,0,1),-X*.2f);
                Old.SampleLocals(W,Pelvis,Delta,OQ,OP);New.SampleLocals(W,Pelvis,Delta,NQ,NP);
                for(int32 J=0;J<BoneCount;++J)
                {
                    Check(!NQ[J].ContainsNaN() && !NP[J].ContainsNaN(),TEXT("Finite output"));
                    Check(FMemory::Memcmp(&OP[J],&NP[J],sizeof(FVector3f))==0,TEXT("All bone offsets bit-identical"));
                    if(!Switched || J<10 || J>12)
                        Check(FMemory::Memcmp(&OQ[J],&NQ[J],sizeof(FQuat4f))==0,TEXT("Unaffected rotations bit-identical"));
                    if(X==0 || X==1)Check(FQuat(OQ[J]).GetNormalized().AngularDistance(FQuat(NQ[J]).GetNormalized())<1.e-5,TEXT("Continuous entry and same idle endpoint"));
                }
                ++Samples;
            }
            for(float Hold:{0.f,.11f,1.f})for(float Trim:{0.f,.34f})
            {
                Old.SetAlphaHold(Hold);New.SetAlphaHold(Hold);Old.TakeoverTimeScale=New.TakeoverTimeScale=1.f/(1.f-Trim);
                for(float X:{.05f,.4f,.8f,1.f})
                {
                    auto O=Current,N=Current;
                    Old.Apply(X/Old.InverseDuration,O,{},Frame);New.Apply(X/New.InverseDuration,N,{},Frame);
                    if(!Switched)for(int32 J=0;J<O.Num();++J)
                        Check(FMemory::Memcmp(&O[J],&N[J],sizeof(FTransform))==0,TEXT("Full mixed pose bit-identical"));
                    if(X>=1.f-Trim)for(int32 J=0;J<N.Num();++J)
                        Check(N[J].Equals(Current[J],0),TEXT("Unchanged NN takeover endpoint"));
                }
            }
            // The corrected cached return derivative must still cancel out of
            // the existing inertia seed, including inherited parent rates.
            if(Switched && Inertia>0)
            {
                auto InitialVelocity=[&](const FCurve& Curve)
                {
                    const auto& Bone=Curve.Bones[10];
                    const FVector3f Pull=Bone.Return.Axis*(2*Bone.Return.HalfAngle*(1-Easing)*Curve.InverseDuration);
                    if(World)return FVector3f(Current[Bone.Index].GetRotation().RotateVector(FVector(Pull)))+
                        Bone.WorldCorrection.Axis*(2*Bone.WorldCorrection.HalfAngle);
                    return Pull+Bone.Velocity.Axis*(2*Bone.Velocity.HalfAngle);
                };
                Check(InitialVelocity(Old).Equals(InitialVelocity(New),.0001f),TEXT("Outgoing inertia velocity preserved"));
            }
        }
        Expected?++Changed:++Unchanged;
        const auto Result=MakeShared<FJsonObject>();Result->SetStringField(TEXT("id"),C->GetStringField(TEXT("id")));
        Result->SetBoolField(TEXT("changed"),Expected);Result->SetNumberField(TEXT("failures"),Failures-BeforeFailures);
        Cases.Add(MakeShared<FJsonValueObject>(Result));
    }
    const auto Report=MakeShared<FJsonObject>();Report->SetNumberField(TEXT("failures"),Failures);
    Report->SetNumberField(TEXT("unchanged"),Unchanged);Report->SetNumberField(TEXT("changed"),Changed);
    Report->SetNumberField(TEXT("samples"),Samples);Report->SetArrayField(TEXT("cases"),Cases);
    FString Output;FJsonSerializer::Serialize(Report,TJsonWriterFactory<>::Create(&Output));
    FFileHelper::SaveStringToFile(Output,*(Directory+TEXT("verification.json")));
    UE_LOG(LogTemp,Display,TEXT("FKSlashWinding failures=%d unchanged=%d changed=%d samples=%d"),Failures,Unchanged,Changed,Samples);
    return Failures==0;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyFKSlashWindingTest,"Prophecy.NN.FKReturn.SlashWinding",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyFKSlashWindingTest::RunTest(const FString&)
{return TestTrue(TEXT("Slash winding verification"),VerifyFKSlashWinding());}
#if WITH_EDITOR
static FAutoConsoleCommand VerifyFKSlashWindingCommand(TEXT("Prophecy.FKReturn.VerifyWinding"),
    TEXT("Run pure FK winding fixture checks without entering global automation mode."),
    FConsoleCommandDelegate::CreateLambda([](){VerifyFKSlashWinding();}));
#endif
#endif
