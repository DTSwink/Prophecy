#include "ProphecyDodgeLower.h"
#include "ProphecyDefenseNetwork.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyDodgeFullTraceTest,"Prophecy.NN.Defense.DodgeFullTrace",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyDodgeFullTraceTest::RunTest(const FString&)
{
    using namespace ProphecyDefense;
    const FString Dir=FPaths::ProjectSavedDir()/TEXT("DefenseIntegration/Models");
    FString Text,Error;TSharedPtr<FJsonObject> Fixture;
    if (!FFileHelper::LoadFileToString(Text,*(Dir/TEXT("dodge_trace_inputs.json")))
        || !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Fixture) || !Fixture) return false;
    TMap<FString,TArray<float>> Input,Trace,Trajectory;
    for (const auto& Pair:Fixture->Values)
    {
        auto& A=Input.Add(Pair.Key);for (const auto& V:Pair.Value->AsArray()) A.Add(float(V->AsNumber()));
        if (Pair.Key.StartsWith(TEXT("episode/"))) Trace.Add(Pair.Key,A);
    }
    auto Get=[&](const TCHAR* Name)->const TArray<float>& { return Input.FindChecked(Name); };
    const auto& L=Get(TEXT("episode/lower_primers"));const auto& U=Get(TEXT("episode/upper_primers"));
    const auto& Roots=Get(TEXT("episode/root_primers"));const auto& Limits=Get(TEXT("limits"));
    const auto& Valid=Get(TEXT("episode/valid"));const int32 Frames=Valid.Num();
    if (L.Num()!=82 || U.Num()!=180 || Roots.Num()!=24 || Limits.Num()!=6 || Frames<3) return false;
    ProphecyDefense::FGeometry G;FDodgeLowerSettings Settings[2];FProphecyDefenseNetwork Lower[2],Upper;
    if (!G.Load(Dir/TEXT("dodge_skeleton.json"),true,Error)
        || !Upper.Initialize(Dir/TEXT("prophecy_dodge_upper.onnx"),362,112,Error)) { AddError(Error);return false; }
    for (int32 I=0;I<2;++I)
    {
        const FString Kind=I?TEXT("run"):TEXT("walk");
        if (!Settings[I].Load(Dir/TEXT("dodge_lower_settings.json"),Kind,Error)
            || !Lower[I].Initialize(Dir/(TEXT("prophecy_dodge_")+Kind+TEXT(".onnx")),152,43,Error)) { AddError(Error);return false; }
    }
    auto Put=[&](const FString& Key,const float* V,int32 N) { auto& A=Trace.FindOrAdd(Key);A.Reset(N);A.Append(V,N); };
    auto Append=[&](const TCHAR* Key,const float* V,int32 N) { Trajectory.FindOrAdd(Key).Append(V,N); };
    auto RootValues=[](const FRootFrame& Root,float* Out)
    { Write(Out,Root.P);for (int32 I=0;I<3;++I) Write(Out+3+I*3,Root.R.V[I]); };
    auto PoseValues=[](const FPose& Pose,float* P,float* R)
    { for (int32 I=0;I<25;++I) { Write(P+I*3,Pose.P[I]);for (int32 J=0;J<3;++J) Write(R+I*9+J*3,Pose.R[I].V[J]); } };
    auto SaveState=[&](const FString& Prefix,const FDodgeState& S)
    {
        Put(Prefix+TEXT("previous_lower"),S.PreviousLower,41);Put(Prefix+TEXT("previous_upper"),S.PreviousUpper,90);
        Put(Prefix+TEXT("current_lower"),S.CurrentLower,41);Put(Prefix+TEXT("current_upper"),S.CurrentUpper,90);
        float R[12];RootValues(S.PreviousRoot,R);Put(Prefix+TEXT("previous_root"),R,3);Put(Prefix+TEXT("previous_axes"),R+3,9);
        RootValues(S.CurrentRoot,R);Put(Prefix+TEXT("current_root"),R,3);Put(Prefix+TEXT("current_axes"),R+3,9);
        Put(Prefix+TEXT("initial_axes"),Roots.GetData()+3,9);Write(R,S.InitialWorldDelta);Put(Prefix+TEXT("initial_delta_world"),R,3);
        Put(Prefix+TEXT("initial_delta_yaw"),&S.InitialYawDelta,1);Put(Prefix+TEXT("remaining"),S.Remaining,6);
        Write(R,S.RootShift);Put(Prefix+TEXT("root_shift_world"),R,3);Put(Prefix+TEXT("root_yaw_offset"),&S.YawOffset,1);
    };
    FDodgeState S;S.Initialize(L.GetData(),U.GetData(),Roots.GetData(),L.GetData()+41,U.GetData()+90,Roots.GetData()+12,Limits.GetData());
    FPose HeldPose;
    auto AppendState=[&](const float* LowerState,const float* UpperState,const FRootFrame& Root)
    {
        float P[75],R[225],Root12[12],Shift[3];PoseValues(HeldPose,P,R);RootValues(Root,Root12);Write(Shift,S.RootShift);
        Append(TEXT("positions"),P,75);Append(TEXT("rotations"),R,225);Append(TEXT("roots"),Root12,12);
        Append(TEXT("lower"),LowerState,41);Append(TEXT("upper"),UpperState,90);Append(TEXT("movement_banks"),S.Remaining,6);
        Append(TEXT("root_shifts_world"),Shift,3);Append(TEXT("root_yaw_offsets"),&S.YawOffset,1);
    };
    for (int32 I=0;I<2;++I)
    {
        const auto Root=FRootFrame::Read12(Roots.GetData()+12*I);FPose Base;float BaseUpper[90];
        G.LowerPose(L.GetData()+41*I,Root.P,Root.R,Base);G.EncodeUpper(Base,Root.P,Root.R,BaseUpper);
        G.Finish(L.GetData()+41*I,U.GetData()+90*I,Root.P,Root.R,Base,BaseUpper,HeldPose);
        AppendState(L.GetData()+41*I,U.GetData()+90*I,Root);
    }
    for (int32 Frame=2;Frame<Frames;++Frame)
    {
        const FString Prefix=FString::Printf(TEXT("frame/%03d/"),Frame);const FDodgeState Before=S;
        SaveState(Prefix+TEXT("state_before/"),S);SaveState(Prefix+TEXT("frozen_cleaned/input/0/"),S);
        const float Category=1;Put(Prefix+TEXT("frozen_cleaned/input/1"),&Category,1);
        float Frozen[41],Pins[2];
        for (int32 I=0;I<2;++I)
        {
            const FString K=Prefix+(I?TEXT("run/"):TEXT("walk/"));float In[152],Raw[43],Future[24];
            DodgeLowerInput(S,Settings[I],In);
            if (!Lower[I].Run(MakeArrayView(In),MakeArrayView(Raw))) return false;
            Put(K+TEXT("input/0"),In,152);Put(K+TEXT("output"),Raw,43);Put(K+TEXT("root_window"),In+117,35);
            const auto Command=DodgeCommand(S.InitialWorldDelta,S.YawOffset);
            for (int32 J=0;J<8;++J) Write(Future+3*J,S.CurrentRoot.P+float(J+1)*Command);
            Put(K+TEXT("extrapolated_root_points"),Future,24);
            // Both neural calls are traced by the original graph; only the
            // recorded run category's cleaned proposal affects this episode.
            if (I) CleanDodgeLower(Raw,S.CurrentLower,G,Settings[I],Frozen,Pins);
        }
        Put(Prefix+TEXT("frozen_cleaned/output/0"),Frozen,41);Put(Prefix+TEXT("frozen_cleaned/output/1"),Pins,2);
        FContext C;C.TargetWorld=Read(Get(TEXT("episode/target_world")).GetData());
        FMemory::Memcpy(C.AttackControls,Get(TEXT("episode/attack_type")).GetData(),sizeof(C.AttackControls));
        for (int32 I=0;I<2;++I)
        {
            FMemory::Memcpy(C.AttackerPelvis[I],Get(TEXT("episode/pelvis")).GetData()+9*(Frame-1+I),9*sizeof(float));
            FMemory::Memcpy(C.AttackerCollider[I],Get(TEXT("episode/collider")).GetData()+9*(Frame-1+I),9*sizeof(float));
        }
        C.Event=Get(TEXT("episode/event"))[Frame];FDodgeWork W;float In[362],Out[112],Modified[41],UnrebasedUpper[90];FPose Pose;
        if (!PrepareDodge(S,Frozen,C,W,In) || !Upper.Run(MakeArrayView(In),MakeArrayView(Out))) return false;
        Put(Prefix+TEXT("upper/input/0"),In,362);Put(Prefix+TEXT("upper/output/0"),Out,112);
        const auto Controls=DodgeControls(Out+90,S.Remaining,(Transform(Read(Frozen),S.CurrentRoot.R)+S.CurrentRoot.P).Y);
        if (!CompleteDodge(S,W,Frozen,Out,G,Pose,Modified,UnrebasedUpper)) return false;
        SaveState(Prefix+TEXT("proposal/state/"),S);
        float P[75],R[225],LowerOutput[43],Row[443],Requests[6],V[3];PoseValues(Pose,P,R);
        Put(Prefix+TEXT("proposal/positions"),P,75);Put(Prefix+TEXT("proposal/rotations"),R,225);
        FMemory::Memcpy(LowerOutput,Modified,sizeof(Modified));FMemory::Memcpy(LowerOutput+41,Pins,sizeof(Pins));
        Put(Prefix+TEXT("proposal/lower_output"),LowerOutput,43);Put(Prefix+TEXT("proposal/upper_output"),Out,90);
        Put(Prefix+TEXT("proposal/pin_probabilities"),Pins,2);
        // Predictor loss row: proposed-current, previous, current, context.
        for (int32 I=0;I<41;++I) Row[I]=Modified[I]-Before.CurrentLower[I];
        for (int32 I=0;I<90;++I) Row[41+I]=UnrebasedUpper[I]-Before.CurrentUpper[I];
        FMemory::Memcpy(Row+131,In+180,9*sizeof(float));FMemory::Memcpy(Row+140,In+257,32*sizeof(float));
        FMemory::Memcpy(Row+172,In,90*sizeof(float));FMemory::Memcpy(Row+262,Before.CurrentLower,41*sizeof(float));
        FMemory::Memcpy(Row+303,Before.CurrentUpper,90*sizeof(float));FMemory::Memcpy(Row+393,In+207,50*sizeof(float));
        Put(Prefix+TEXT("proposal/predictor_row"),Row,443);
        for (int32 I=0;I<6;++I) Requests[I]=Limits[I]>0?Controls.RequestedDistance[I]/FMath::Max(Limits[I],1.e-8f):0;
        Requests[0]+=Controls.DropRequested/(Limits[0]>0?Limits[0]:.3f);
        Put(Prefix+TEXT("proposal/bank_requests"),Requests,6);
        const FString CP=Prefix+TEXT("controls/");
        V[0]=Controls.PelvisHorizontal.X;V[1]=Controls.PelvisHorizontal.Y;Put(CP+TEXT("pelvis_horizontal"),V,2);
        for (int32 I=0;I<2;++I) { Write(V,Controls.Foot[I]);Put(CP+(I?TEXT("right_foot"):TEXT("left_foot")),V,3); }
        Write(V,Controls.PelvisRotation);Put(CP+TEXT("pelvis_rotation"),V,3);
        V[0]=Controls.RootHorizontal.X;V[1]=Controls.RootHorizontal.Y;Put(CP+TEXT("root_horizontal"),V,2);
        Put(CP+TEXT("root_yaw"),&Controls.RootYaw,1);Put(CP+TEXT("drop"),&Controls.Drop,1);Put(CP+TEXT("remaining"),Controls.Remaining,6);
        V[0]=Controls.bEnabled?1.f:0.f;Put(CP+TEXT("enabled"),V,1);Put(CP+TEXT("requested_distance"),Controls.RequestedDistance,6);
        Put(CP+TEXT("drop_requested_distance"),&Controls.DropRequested,1);
        if (Valid[Frame]) HeldPose=Pose;else { S=Before;FMemory::Memzero(Requests,sizeof(Requests)); }
        AppendState(S.CurrentLower,S.CurrentUpper,S.CurrentRoot);
        Append(TEXT("predictor_rows"),Row,443);Append(TEXT("pin_probabilities"),Pins,2);Append(TEXT("pin_commands"),Pins,2);Append(TEXT("bank_requests"),Requests,6);
    }
    for (auto& Pair:Trajectory) Trace.Add(TEXT("trajectory/")+Pair.Key,MoveTemp(Pair.Value));
    auto Document=MakeShared<FJsonObject>();
    for (const auto& Pair:Trace)
    {
        TArray<TSharedPtr<FJsonValue>> A;A.Reserve(Pair.Value.Num());
        for (float V:Pair.Value) { if (!FMath::IsFinite(V)) { AddError(TEXT("Nonfinite native Dodge trace."));return false; } A.Add(MakeShared<FJsonValueNumber>(V)); }
        Document->SetArrayField(Pair.Key,MoveTemp(A));
    }
    FJsonSerializer::Serialize(Document,TJsonWriterFactory<>::Create(&Text));
    if (!FFileHelper::SaveStringToFile(Text,*(Dir/TEXT("ue_dodge_trace_flat.json")))) return false;
    TestEqual(TEXT("Padding does not advance the recurrent state"),S.CompletedSteps,uint64(6));
    AddInfo(FString::Printf(TEXT("Exported %d native trace tensors. Run the original Dodge comparator for full numerical verification."),Trace.Num()));
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyDodgeLiveRootTest,"Prophecy.NN.Defense.DodgeLiveRoot",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyDodgeLiveRootTest::RunTest(const FString&)
{
    using namespace ProphecyDefense;
    const FString Dir=FPaths::ProjectSavedDir()/TEXT("DefenseIntegration/Models");
    FString Text,Error;TSharedPtr<FJsonObject> Fixture;
    if (!FFileHelper::LoadFileToString(Text,*(Dir/TEXT("dodge_trace_inputs.json"))) ||
        !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Fixture)) return false;
    auto Get=[&](const TCHAR* Name) { TArray<float> A;for (auto& V:Fixture->GetArrayField(Name)) A.Add(float(V->AsNumber()));return A; };
    const auto L=Get(TEXT("episode/lower_primers")),U=Get(TEXT("episode/upper_primers")),R=Get(TEXT("episode/root_primers"));
    ProphecyDefense::FGeometry Geometry;if (!Geometry.Load(Dir/TEXT("dodge_skeleton.json"),true,Error)) { AddError(Error);return false; }
    const float Budgets[]={10,10,10,10,10,10};
    FDodgeState S;S.Initialize(L.GetData(),U.GetData(),R.GetData(),L.GetData()+41,U.GetData()+90,R.GetData()+12,Budgets);
    // Large retained yaw must not rotate a new world-space command into a helix.
    S.YawOffset=1.7f;S.InitialWorldDelta={9,0,9};
    auto Planned=S.CurrentRoot;Planned.P+=FVector3f(.2f,.01f,-.1f);
    const auto Turn=DodgeYaw(.13f);for (auto& Row:Planned.R.V) Row=Transform(Row,Turn);
    FDodgeWork W;FContext Context;float Input[362],Output[112]={};FPose Pose;
    TestTrue(TEXT("Live preparation"),PrepareDodge(S,S.CurrentLower,Context,W,Input,&Planned));
    const auto ExpectedCommand=InTransposedBasis(Planned.P-S.CurrentRoot.P,S.CurrentRoot.R);
    TestTrue(TEXT("Conditioning uses new command, not episode seed"),Read(Input+207+37).Equals(ExpectedCommand,1.e-6f));
    TestTrue(TEXT("Zero residual completion"),CompleteDodge(S,W,S.CurrentLower,Output,Geometry,Pose,nullptr,nullptr,&Planned));
    TestTrue(TEXT("Zero residual follows planned position exactly"),S.CurrentRoot.P.Equals(Planned.P,1.e-6f));
    for (int32 I=0;I<3;++I) TestTrue(TEXT("Zero residual follows planned orientation"),S.CurrentRoot.R.V[I].Equals(Planned.R.V[I],1.e-6f));
    const auto Old=S.CurrentRoot;Planned.P+=FVector3f(-.1f,0,.23f);
    Output[105]=.04f;Output[106]=-.02f;Output[107]=1;Output[110]=.2f;Output[111]=1;
    TestTrue(TEXT("Second live preparation"),PrepareDodge(S,S.CurrentLower,Context,W,Input,&Planned));
    TestTrue(TEXT("Residual completion"),CompleteDodge(S,W,S.CurrentLower,Output,Geometry,Pose,nullptr,nullptr,&Planned));
    TestTrue(TEXT("Dodge displacement added once in native root frame"),S.CurrentRoot.P.Equals(Planned.P+Transform(FVector3f(.04f,-.02f,0),Old.R),1.e-6f));
    const auto Rotation=DodgeYaw(.2f);
    for (int32 I=0;I<3;++I) TestTrue(TEXT("Dodge yaw added once"),S.CurrentRoot.R.V[I].Equals(Transform(Planned.R.V[I],Rotation),1.e-6f));
    TestTrue(TEXT("Only learned movement consumes root budget"),FMath::IsNearlyEqual(S.Remaining[4],10.f-FMath::Sqrt(.002f),1.e-5f));
    TestEqual(TEXT("Retarget/live movement did not reseed history"),S.CompletedSteps,uint64(2));
    return !HasAnyErrors();
}
#endif
