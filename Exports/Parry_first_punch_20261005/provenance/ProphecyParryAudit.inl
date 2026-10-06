// Optional capture of the native Parry boundary for portable trainer cases.
#if !UE_BUILD_SHIPPING
namespace ProphecyParryAudit
{
static TAutoConsoleVariable<int32> Enabled(TEXT("Prophecy.Debug.ParryTrace"),0,TEXT("Development-only live Parry boundary trace."));
void Array(const TSharedPtr<FJsonObject>& Doc,const TCHAR* Key,const float* Data,int32 Count)
{
    TArray<TSharedPtr<FJsonValue>> Values;Values.Reserve(Count);
    for(int32 I=0;I<Count;++I) Values.Add(MakeShared<FJsonValueNumber>(Data[I]));
    Doc->SetArrayField(Key,Values);
}
void Vector(const TSharedPtr<FJsonObject>& Doc,const TCHAR* Key,const FVector3f& V)
{ const float A[]={V.X,V.Y,V.Z};Array(Doc,Key,A,3); }
void Root(const TSharedPtr<FJsonObject>& Doc,const TCHAR* Key,const ProphecyDefense::FRootFrame& R)
{ float A[12];DefenseRoot12(R,A);Array(Doc,Key,A,12); }
TSharedPtr<FJsonObject> State(const ProphecyDefense::FParryState& S)
{
    auto Doc=MakeShared<FJsonObject>();
    Array(Doc,TEXT("previous_lower"),S.PreviousLower,41);Array(Doc,TEXT("current_lower"),S.CurrentLower,41);
    Array(Doc,TEXT("previous_upper"),S.PreviousUpper,90);Array(Doc,TEXT("current_upper"),S.CurrentUpper,90);
    Array(Doc,TEXT("current_baseline"),S.CurrentBaseline,90);
    Root(Doc,TEXT("previous_root"),S.PreviousRoot);Root(Doc,TEXT("current_root"),S.CurrentRoot);
    Vector(Doc,TEXT("initial_delta_world"),S.InitialWorldDelta);Doc->SetNumberField(TEXT("initial_delta_yaw"),S.InitialYawDelta);
    Doc->SetNumberField(TEXT("steps"),double(S.CompletedSteps));return Doc;
}
void Save(const FProphecyLiveParry& P,int32 Frame,const TCHAR* Stage,const float* Input=nullptr,const float* Output=nullptr)
{
    auto Doc=MakeShared<FJsonObject>();Doc->SetObjectField(TEXT("state"),State(P.State));
    Doc->SetStringField(TEXT("owner"),GetNameSafe(P.Owner.Get()));Doc->SetStringField(TEXT("attacker"),GetNameSafe(P.Attacker.Get()));
    Doc->SetStringField(TEXT("family"),P.Family.ToString());Doc->SetNumberField(TEXT("frame"),Frame);
    Vector(Doc,TEXT("target"),P.Context.TargetWorld);Array(Doc,TEXT("attack_controls"),P.Context.AttackControls,5);
    if(Input)
    {
        Array(Doc,TEXT("input"),Input,258);Array(Doc,TEXT("pelvis"),P.Context.AttackerPelvis[0],18);
        Array(Doc,TEXT("collider"),P.Context.AttackerCollider[0],18);Array(Doc,TEXT("next_lower"),P.NextLower,41);
        Array(Doc,TEXT("next_baseline"),P.NextBaseline,90);Root(Doc,TEXT("next_root"),P.NextRoot);
        float Positions[75],Rotations[225];
        for(int32 I=0;I<25;++I)
        {
            ProphecyDefense::Write(Positions+I*3,P.Frozen.P[I]);
            for(int32 J=0;J<3;++J) ProphecyDefense::Write(Rotations+I*9+J*3,P.Frozen.R[I].V[J]);
        }
        Array(Doc,TEXT("frozen_positions"),Positions,75);Array(Doc,TEXT("frozen_rotations"),Rotations,225);
    }
    if(Output)Array(Doc,TEXT("output"),Output,90);
    const FString Dir=FPaths::ProjectSavedDir()/TEXT("Diagnostics/ParryExport/NativeTrace");IFileManager::Get().MakeDirectory(*Dir,true);
    const FString Path=Dir/FString::Printf(TEXT("%s_%03d_%s.json"),*GetNameSafe(P.Owner.Get()),Frame,Stage);
    FString Json;FJsonSerializer::Serialize(Doc,TJsonWriterFactory<>::Create(&Json));FFileHelper::SaveStringToFile(Json,*Path);
}
}
#endif
