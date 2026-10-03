from pathlib import Path
p=Path('Source/GameAnimationSample3/Private/ProphecyLowerTempering.inl')
text=p.read_text(encoding='utf-8')
Path('Saved/Diagnostics/LowerTempering-before-history25.inl').write_text(text,encoding='utf-8')
old=Path('Saved/Diagnostics/SupportSourceExperiments/ProphecyLowerTempering-experiments.inl').read_text(encoding='utf-8')
old=old[old.index('void ResolveTemperedLeg('):old.index('#if WITH_DEV_AUTOMATION_TESTS')]
old=old.replace('void ResolveTemperedLeg(','void ResolveTemperedLegSeptember20(')
old=old.replace('int32 ExperimentMode=0','int32 ExperimentMode=7')
Path('Source/GameAnimationSample3/Private/ProphecyKneeHistoricalAudit.inl').write_text('''// Editor-only September20 mode7 reference, retained for same-input causal comparison.
#if WITH_EDITOR
static TAutoConsoleVariable<int32> CVarKneeHistoricalAudit(TEXT("Prophecy.Tempering.HistoricalAudit"),0,TEXT("Opt-in bounded knee solver input/oracle capture."));
'''+old+'\n#endif\n',encoding='utf-8')
text=text.replace('void ResolveTemperedLeg(', '#include "ProphecyKneeHistoricalAudit.inl"\n\nvoid ResolveTemperedLegCurrent(',1)
index=text.index('#if WITH_DEV_AUTOMATION_TESTS')
wrapper='''void ResolveTemperedLeg(const ProphecyLowerTempering::FSettings& S,const float* Previous,
    const FPelvisLegGeometry& G,float* Target,int32 Offset,
    FVector3f FootForwardLocal=FVector3f(1,0,0),FVector3f FootUpLocal=FVector3f(0,0,1),
    float MinimumReach=0.f,bool bClampOuterReach=true,const float* NNSource=nullptr)
{
#if WITH_EDITOR
    const bool Audit=CVarKneeHistoricalAudit.GetValueOnGameThread()>0;
    float Input[41];if(Audit)FMemory::Memcpy(Input,Target,sizeof(Input));
    if(CVarTemperingKneePlane.GetValueOnGameThread()==20)
        ResolveTemperedLegSeptember20(S,Previous,G,Target,Offset,FootForwardLocal,FootUpLocal,MinimumReach,bClampOuterReach,NNSource);
    else
#endif
        ResolveTemperedLegCurrent(S,Previous,G,Target,Offset,FootForwardLocal,FootUpLocal,MinimumReach,bClampOuterReach,NNSource);
#if WITH_EDITOR
    if(Audit)
    {
        CVarKneeHistoricalAudit->Set(CVarKneeHistoricalAudit.GetValueOnGameThread()-1,ECVF_SetByConsole);
        float Historical[41];FMemory::Memcpy(Historical,Input,sizeof(Historical));
        ResolveTemperedLegSeptember20(S,Previous,G,Historical,Offset,FootForwardLocal,FootUpLocal,MinimumReach,bClampOuterReach,NNSource);
        auto Row=MakeShared<FJsonObject>();
        auto Add=[&](const TCHAR* Key,const float* V,int32 Count){TArray<TSharedPtr<FJsonValue>> A;for(int32 I=0;I<Count;++I)A.Add(MakeShared<FJsonValueNumber>(V[I]));Row->SetArrayField(Key,A);};
        auto Vec=[&](const TCHAR* Key,const FVector3f& V){const float X[]={V.X,V.Y,V.Z};Add(Key,X,3);};
        Add(TEXT("previous"),Previous,41);Add(TEXT("input"),Input,41);Add(TEXT("current"),Target,41);Add(TEXT("historical"),Historical,41);if(NNSource)Add(TEXT("nn"),NNSource,41);
        const float Settings[]={S.FeetTranslation,S.FeetRotation,S.PelvisTranslation,S.PelvisRotation,S.FeetTranslationZ,S.PelvisTranslationZ};Add(TEXT("settings"),Settings,6);
        Vec(TEXT("hip"),G.HipOffset);Vec(TEXT("knee"),G.KneeOffset);Vec(TEXT("pole"),G.PoleAxis);Vec(TEXT("forward"),FootForwardLocal);Vec(TEXT("up"),FootUpLocal);
        Row->SetNumberField(TEXT("offset"),Offset);Row->SetNumberField(TEXT("calf"),G.CalfLength);Row->SetNumberField(TEXT("floor"),G.MinimumAnkleZ);Row->SetNumberField(TEXT("minimum"),MinimumReach);Row->SetBoolField(TEXT("outer"),bClampOuterReach);
        FString Line;FJsonSerializer::Serialize(Row,TJsonWriterFactory<TCHAR,TCondensedJsonPrintPolicy<TCHAR>>::Create(&Line));
        FFileHelper::SaveStringToFile(Line+TEXT("\\n"),*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/KneeHistoricalSolve.jsonl")),FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM,&IFileManager::Get(),FILEWRITE_Append);
    }
#endif
}

'''
text=text[:index]+wrapper+text[index:]
p.write_text(text,encoding='utf-8')
