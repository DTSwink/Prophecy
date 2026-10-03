#if WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSlashFastGeometryTest,"Prophecy.NN.Attack.NativeGeometryParityAndCost",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FSlashFastGeometryTest::RunTest(const FString&)
{
    const int32 Saved=SlashFastGeometry::Enabled.GetValueOnGameThread();
    ON_SCOPE_EXIT {SlashFastGeometry::Enabled->Set(Saved,ECVF_SetByCode);};
    TArray<TSharedPtr<FJsonValue>> Reports;
    for(const TCHAR* Suffix:{TEXT(""),TEXT("Attack160664"),TEXT("Attack184064")})
    {
        const FString Dir=FPaths::ProjectContentDir()/TEXT("locomotion/NN")/Suffix;
        FString Text;TSharedPtr<FJsonObject> Contract;
        if(!FFileHelper::LoadFileToString(Text,*(Dir/TEXT("prophecy_slash_runtime.json"))) ||
            !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Contract))return false;
        FSlashNative Reference,Fast;
        SlashFastGeometry::Enabled->Set(0,ECVF_SetByCode);
        if(!TestTrue(TEXT("Original model loads"),Reference.Initialize(Dir,Contract)))return false;
        SlashFastGeometry::Enabled->Set(1,ECVF_SetByCode);
        if(!TestTrue(TEXT("Neural-only model loads"),Fast.Initialize(Dir,Contract)))return false;
        // Every installed checkpoint sees the same diverse recorded real transition inputs.
        TArray<TSharedPtr<FJsonValue>> Rows;
        if(!FFileHelper::LoadFileToString(Text,*(FPaths::ProjectSavedDir()/TEXT("Slash184064/native_geometry_reference.json"))) ||
            !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Rows))return false;
        double MaxPosition=0,MaxRotation=0,MaxState=0;TArray<double> SlowMs,FastMs;
        TArray<float> Input,A,B;
        for(int32 Batch:{1,4,100})
        {
            if(!Reference.SetBatch(Batch) || !Fast.SetBatch(Batch))return false;
            const int32 Count=Batch==1?Rows.Num():Batch==4?8:3;
            for(int32 Frame=0;Frame<Count;++Frame)
            {
                Input.SetNumUninitialized(Batch*272);
                for(int32 Lane=0;Lane<Batch;++Lane)
                {
                    const auto& Values=Rows[(Frame+Lane)%Rows.Num()]->AsObject()->GetArrayField(TEXT("state"));
                    for(int32 I=0;I<272;++I)Input[Lane*272+I]=Values[I]->AsNumber();
                }
                const double T0=FPlatformTime::Seconds();const bool OkA=Reference.Run(Input,A);
                const double T1=FPlatformTime::Seconds();const bool OkB=Fast.Run(Input,B);
                const double T2=FPlatformTime::Seconds();
                if(!OkA || !OkB){AddError(FString::Printf(TEXT("Run failed %s batch=%d frame=%d original=%d native=%d"),Suffix,Batch,Frame,OkA,OkB));return false;}
                if(Batch==1 && Frame>=10){SlowMs.Add((T1-T0)*1000);FastMs.Add((T2-T1)*1000);}
                for(int32 Lane=0;Lane<Batch;++Lane)for(int32 I=0;I<437;++I)
                {
                    const float X=A[Lane*437+I],Y=B[Lane*437+I];
                    if(!FMath::IsFinite(Y)){AddError(TEXT("Nonfinite native output"));return false;}
                    const double Error=FMath::Abs(double(X)-Y);
                    if(I>=131 && I<206)MaxPosition=FMath::Max(MaxPosition,Error);
                    else if(I>=206 && I<431)MaxRotation=FMath::Max(MaxRotation,Error);
                    else MaxState=FMath::Max(MaxState,Error);
                    if((I==431 || I==432) && X!=Y){AddError(TEXT("Attack phase latch changed"));return false;}
                }
            }
        }
        SlowMs.Sort();FastMs.Sort();
        auto J=MakeShared<FJsonObject>();J->SetStringField(TEXT("checkpoint"),Suffix);
        J->SetNumberField(TEXT("position_m"),MaxPosition);J->SetNumberField(TEXT("rotation_matrix"),MaxRotation);J->SetNumberField(TEXT("state"),MaxState);
        J->SetNumberField(TEXT("original_ms"),SlowMs[SlowMs.Num()/2]);J->SetNumberField(TEXT("native_ms"),FastMs[FastMs.Num()/2]);
        J->SetNumberField(TEXT("speedup"),SlowMs[SlowMs.Num()/2]/FastMs[FastMs.Num()/2]);Reports.Add(MakeShared<FJsonValueObject>(J));
        AddInfo(FString::Printf(TEXT("%s pos=%.9g m matrix=%.9g state=%.9g; original=%.6f native=%.6f ms"),Suffix,MaxPosition,MaxRotation,MaxState,SlowMs[SlowMs.Num()/2],FastMs[FastMs.Num()/2]));
        TestTrue(TEXT("Existing whole-step position parity budget"),MaxPosition<.0001);
        TestTrue(TEXT("Existing rotation/state parity budget"),MaxRotation<.001 && MaxState<.001);
    }
    auto Root=MakeShared<FJsonObject>();Root->SetArrayField(TEXT("checkpoints"),Reports);FString Text;
    FJsonSerializer::Serialize(Root,TJsonWriterFactory<>::Create(&Text));
    FFileHelper::SaveStringToFile(Text,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/AttackPerformance20261002/native-parity.json")));
    return !HasAnyErrors();
}
#endif
