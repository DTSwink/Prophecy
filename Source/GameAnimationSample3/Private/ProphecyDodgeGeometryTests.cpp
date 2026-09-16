#include "ProphecyDodgeBanks.h"
#include "ProphecyDodgeRuntime.h"
#include "ProphecyDefenseNetwork.h"
#include "ProphecyDodgeLower.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyDodgeGeometryTest,"Prophecy.NN.Defense.DodgeLegAndBankReference",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyDodgeGeometryTest::RunTest(const FString&)
{
    using namespace ProphecyDefense;
    const FString Directory=FPaths::ProjectSavedDir()/TEXT("DefenseIntegration/Models");
    FString Text,Error;TArray<TSharedPtr<FJsonValue>> Cases;
    ProphecyDefense::FGeometry Geometry;
    if (!Geometry.Load(Directory/TEXT("dodge_skeleton.json"),true,Error)) { AddError(Error);return false; }
    if (!FFileHelper::LoadFileToString(Text,*(Directory/TEXT("dodge_geometry_reference.json"))) || !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Cases))
    { AddError(TEXT("ExportDefenseGeometryReference.py must prepare the local fixtures."));return false; }
    auto ReadArray=[&](const TSharedPtr<FJsonValue>& V,float* Out,int32 Count)
    {
        if (!V || V->Type!=EJson::Array || V->AsArray().Num()!=Count) { AddError(TEXT("Invalid dodge reference tensor."));return false; }
        for (int32 I=0;I<Count;++I) Out[I]=float(V->AsArray()[I]->AsNumber());return true;
    };
    double Maximum=0;
    auto Compare=[&](const float* Values,const TSharedPtr<FJsonValue>& Expected,int32 Count,const FString& Stage)
    {
        TArray<float> E;E.SetNumUninitialized(Count);if (!ReadArray(Expected,E.GetData(),Count)) return false;
        for (int32 I=0;I<Count;++I)
        {
            const float D=FMath::Abs(Values[I]-E[I]);Maximum=FMath::Max(Maximum,double(D));
            if (!FMath::IsFinite(Values[I]) || D>1.e-5f+1.e-5f*FMath::Abs(E[I]))
            { AddError(FString::Printf(TEXT("%s channel %d: %.9g expected %.9g"),*Stage,I,Values[I],E[I]));return false; }
        }
        return true;
    };
    for (const auto& V:Cases)
    {
        const auto F=V->AsObject(),S=F->GetObjectField(TEXT("state"));const FString Key=F->GetStringField(TEXT("key"));
        float Raw[22],Remaining[6],Baseline[41],Root[12],InitialDelta[3],Yaw[1],Offset[1];
        if (!ReadArray(F->TryGetField(TEXT("raw")),Raw,22) || !ReadArray(F->TryGetField(TEXT("baseline")),Baseline,41)
            || !ReadArray(S->TryGetField(TEXT("remaining")),Remaining,6) || !ReadArray(S->TryGetField(TEXT("current_root")),Root,3)
            || !ReadArray(S->TryGetField(TEXT("current_axes")),Root+3,9) || !ReadArray(S->TryGetField(TEXT("initial_delta_world")),InitialDelta,3)
            || !ReadArray(S->TryGetField(TEXT("initial_delta_yaw")),Yaw,1) || !ReadArray(S->TryGetField(TEXT("root_yaw_offset")),Offset,1)) return false;
        const auto Frame=FRootFrame::Read12(Root);const float Height=(Transform(Read(Baseline),Frame.R)+Frame.P).Y;
        const auto Controls=DodgeControls(Raw,Remaining,Height);const auto Expected=F->GetObjectField(TEXT("expected_controls"));
        float PH[]={Controls.PelvisHorizontal.X,Controls.PelvisHorizontal.Y},RH[]={Controls.RootHorizontal.X,Controls.RootHorizontal.Y};
        float LF[3],RF[3],PR[3],Enabled[]={Controls.bEnabled?1.f:0.f};Write(LF,Controls.Foot[0]);Write(RF,Controls.Foot[1]);Write(PR,Controls.PelvisRotation);
        auto Field=[&](const TCHAR* Name,const float* Data,int32 Count) { return Compare(Data,Expected->TryGetField(Name),Count,Key+TEXT(" ")+Name); };
        if (!Field(TEXT("pelvis_horizontal"),PH,2) || !Field(TEXT("left_foot"),LF,3) || !Field(TEXT("right_foot"),RF,3)
            || !Field(TEXT("pelvis_rotation"),PR,3) || !Field(TEXT("root_horizontal"),RH,2) || !Field(TEXT("root_yaw"),&Controls.RootYaw,1)
            || !Field(TEXT("drop"),&Controls.Drop,1) || !Field(TEXT("remaining"),Controls.Remaining,6) || !Field(TEXT("enabled"),Enabled,1)
            || !Field(TEXT("requested_distance"),Controls.RequestedDistance,6) || !Field(TEXT("drop_requested_distance"),&Controls.DropRequested,1)) return false;
        float Modified[41];Geometry.SolveDodgeLower(Baseline,Controls,Frame.P,Frame.R,Modified);
        if (!Compare(Modified,F->TryGetField(TEXT("expected_lower")),41,Key+TEXT(" solved lower"))) return false;
        const auto Next=DodgeNextRoot(Frame,Read(InitialDelta),Yaw[0],Controls.RootHorizontal,Controls.RootYaw,Offset[0]);
        float NextValues[12];Write(NextValues,Next.P);for (int32 I=0;I<3;++I) Write(NextValues+3+I*3,Next.R.V[I]);
        if (!Compare(NextValues,F->TryGetField(TEXT("expected_root")),12,Key+TEXT(" next root"))) return false;
        // The final full decoder must retain this same signed leg frame.
        FPose Pose;Geometry.LowerPose(Modified,Frame.P,Frame.R,Pose);
        float ExpectedP[75],ExpectedR[225];
        if (!ReadArray(F->TryGetField(TEXT("expected_positions")),ExpectedP,75) || !ReadArray(F->TryGetField(TEXT("expected_rotations")),ExpectedR,225)) return false;
        for (int32 I:{0,17,18,19,20,21,22,23,24}) for (int32 Channel=0;Channel<12;++Channel)
        {
            const float A=Channel<3?Pose.P[I][Channel]:Pose.R[I].V[(Channel-3)/3][(Channel-3)%3];
            const float E=Channel<3?ExpectedP[I*3+Channel]:ExpectedR[I*9+Channel-3];
            if (!FMath::IsFinite(A) || FMath::Abs(A-E)>1.e-5f+1.e-5f*FMath::Abs(E))
            { AddError(FString::Printf(TEXT("%s lower FK bone %d channel %d %.9g expected %.9g"),*Key,I,Channel,A,E));return false; }
        }
    }
    AddInfo(FString::Printf(TEXT("%d dodge bank/leg/root reference cases; max element error %.9g"),Cases.Num(),Maximum));
    return !Cases.IsEmpty() && !HasAnyErrors();
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyDodgeUpperTransitionTest,"Prophecy.NN.Defense.DodgeUpperTransitionReference",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyDodgeUpperTransitionTest::RunTest(const FString&)
{
    using namespace ProphecyDefense;
    const FString Directory=FPaths::ProjectSavedDir()/TEXT("DefenseIntegration/Models");
    FString Text,Error;TArray<TSharedPtr<FJsonValue>> Cases;
    ProphecyDefense::FGeometry Geometry;FProphecyDefenseNetwork Network;
    if (!Geometry.Load(Directory/TEXT("dodge_skeleton.json"),true,Error) || !Network.Initialize(Directory/TEXT("prophecy_dodge_upper.onnx"),362,112,Error))
    { AddError(Error);return false; }
    if (!FFileHelper::LoadFileToString(Text,*(Directory/TEXT("dodge_geometry_reference.json"))) || !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Cases)) return false;
    auto ReadArray=[&](const TSharedPtr<FJsonValue>& V,float* Out,int32 Count)
    {
        if (!V || V->Type!=EJson::Array || V->AsArray().Num()!=Count) { AddError(TEXT("Invalid dodge transition fixture tensor."));return false; }
        for (int32 I=0;I<Count;++I) Out[I]=float(V->AsArray()[I]->AsNumber());return true;
    };
    double Maximum=0;
    auto Compare=[&](const float* Values,const TSharedPtr<FJsonValue>& Expected,int32 Count,const FString& Stage)
    {
        TArray<float> E;E.SetNumUninitialized(Count);if (!ReadArray(Expected,E.GetData(),Count)) return false;
        for (int32 I=0;I<Count;++I)
        {
            const float D=FMath::Abs(Values[I]-E[I]);Maximum=FMath::Max(Maximum,double(D));
            if (!FMath::IsFinite(Values[I]) || D>1.e-5f+1.e-5f*FMath::Abs(E[I]))
            { AddError(FString::Printf(TEXT("%s channel %d: %.9g expected %.9g"),*Stage,I,Values[I],E[I]));return false; }
        }
        return true;
    };
    for (const auto& V:Cases)
    {
        const auto F=V->AsObject(),Before=F->GetObjectField(TEXT("state")),After=F->GetObjectField(TEXT("expected_state"));
        const FString Key=F->GetStringField(TEXT("key"));FDodgeState State;
        float PR[12],CR[12],Delta[3],Shift[3],Frozen[41];
        if (!ReadArray(Before->TryGetField(TEXT("previous_lower")),State.PreviousLower,41)
            || !ReadArray(Before->TryGetField(TEXT("previous_upper")),State.PreviousUpper,90)
            || !ReadArray(Before->TryGetField(TEXT("current_lower")),State.CurrentLower,41)
            || !ReadArray(Before->TryGetField(TEXT("current_upper")),State.CurrentUpper,90)
            || !ReadArray(Before->TryGetField(TEXT("previous_root")),PR,3) || !ReadArray(Before->TryGetField(TEXT("previous_axes")),PR+3,9)
            || !ReadArray(Before->TryGetField(TEXT("current_root")),CR,3) || !ReadArray(Before->TryGetField(TEXT("current_axes")),CR+3,9)
            || !ReadArray(Before->TryGetField(TEXT("initial_delta_world")),Delta,3) || !ReadArray(Before->TryGetField(TEXT("initial_delta_yaw")),&State.InitialYawDelta,1)
            || !ReadArray(Before->TryGetField(TEXT("root_shift_world")),Shift,3) || !ReadArray(Before->TryGetField(TEXT("root_yaw_offset")),&State.YawOffset,1)
            || !ReadArray(Before->TryGetField(TEXT("remaining")),State.Remaining,6) || !ReadArray(F->TryGetField(TEXT("baseline")),Frozen,41)) return false;
        State.PreviousRoot=FRootFrame::Read12(PR);State.CurrentRoot=FRootFrame::Read12(CR);
        State.InitialWorldDelta=Read(Delta);State.RootShift=Read(Shift);State.bInitialized=true;
        FContext Context;const auto C=F->GetObjectField(TEXT("context"));float Target[3];
        if (!ReadArray(C->TryGetField(TEXT("target")),Target,3) || !ReadArray(C->TryGetField(TEXT("attack_type")),Context.AttackControls,6)) return false;
        for (int32 I=0;I<2;++I)
            if (!ReadArray(C->GetArrayField(TEXT("pelvis"))[I],Context.AttackerPelvis[I],9) || !ReadArray(C->GetArrayField(TEXT("collider"))[I],Context.AttackerCollider[I],9)) return false;
        Context.TargetWorld=Read(Target);Context.Event=float(C->GetNumberField(TEXT("event")));
        FDodgeWork Work;float Input[362],Output[112],Modified[41];FPose Pose;
        if (!PrepareDodge(State,Frozen,Context,Work,Input) || !Compare(Input,F->TryGetField(TEXT("expected_input")),362,Key+TEXT(" input"))) return false;
        if (!Network.Run(MakeArrayView(Input),MakeArrayView(Output)) || !Compare(Output,F->TryGetField(TEXT("expected_output")),112,Key+TEXT(" output"))) return false;
        if (!CompleteDodge(State,Work,Frozen,Output,Geometry,Pose,Modified)) return false;
        if (!Compare(Modified,F->TryGetField(TEXT("expected_lower")),41,Key+TEXT(" modified"))
            || !Compare(State.CurrentLower,After->TryGetField(TEXT("current_lower")),41,Key+TEXT(" recurrent lower"))
            || !Compare(State.CurrentUpper,After->TryGetField(TEXT("current_upper")),90,Key+TEXT(" recurrent upper"))
            || !Compare(State.Remaining,After->TryGetField(TEXT("remaining")),6,Key+TEXT(" remaining"))) return false;
        float P[75],R[225];for (int32 I=0;I<25;++I) { Write(P+3*I,Pose.P[I]);for (int32 J=0;J<3;++J) Write(R+9*I+3*J,Pose.R[I].V[J]); }
        if (!Compare(P,F->TryGetField(TEXT("expected_positions")),75,Key+TEXT(" positions"))
            || !Compare(R,F->TryGetField(TEXT("expected_rotations")),225,Key+TEXT(" rotations"))) return false;
        if (CompleteDodge(State,Work,Frozen,Output,Geometry,Pose)) { AddError(TEXT("Dodge completed the same step twice."));return false; }
    }
    AddInfo(FString::Printf(TEXT("%d full dodge upper transitions from saved lower proposals; max element error %.9g. Lower inference is a separate pending check."),Cases.Num(),Maximum));
    return !Cases.IsEmpty() && !HasAnyErrors();
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyDodgeRolloutTest,"Prophecy.NN.Defense.DodgeCausalRollout",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyDodgeRolloutTest::RunTest(const FString&)
{
    using namespace ProphecyDefense;
    const FString Directory=FPaths::ProjectSavedDir()/TEXT("DefenseIntegration/Models");
    FString Text,Error;TArray<TSharedPtr<FJsonValue>> Cases;
    ProphecyDefense::FGeometry Geometry;FProphecyDefenseNetwork LowerNetwork,UpperNetwork;FDodgeLowerSettings Settings;
    if (!Geometry.Load(Directory/TEXT("dodge_skeleton.json"),true,Error)
        || !Settings.Load(Directory/TEXT("dodge_lower_settings.json"),TEXT("run"),Error)
        || !LowerNetwork.Initialize(Directory/TEXT("prophecy_dodge_run.onnx"),152,43,Error)
        || !UpperNetwork.Initialize(Directory/TEXT("prophecy_dodge_upper.onnx"),362,112,Error)) { AddError(Error);return false; }
    if (!FFileHelper::LoadFileToString(Text,*(Directory/TEXT("dodge_geometry_reference.json"))) || !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Cases) || Cases.IsEmpty()) return false;
    auto ReadArray=[&](const TSharedPtr<FJsonValue>& V,float* Out,int32 Count)
    {
        if (!V || V->Type!=EJson::Array || V->AsArray().Num()!=Count) { AddError(TEXT("Invalid causal dodge fixture tensor."));return false; }
        for (int32 I=0;I<Count;++I) Out[I]=float(V->AsArray()[I]->AsNumber());return true;
    };
    double Maximum=0;
    TArray<TSharedPtr<FJsonValue>> Diagnostics;
    auto Compare=[&](const float* Values,const TSharedPtr<FJsonValue>& Expected,int32 Count,const FString& Stage)
    {
        TArray<float> E;E.SetNumUninitialized(Count);if (!ReadArray(Expected,E.GetData(),Count)) return false;
        TArray<TSharedPtr<FJsonValue>> ActualValues,ExpectedValues;double StageMaximum=0;int32 FirstMismatch=INDEX_NONE;
        for (int32 I=0;I<Count;++I)
        {
            const float D=FMath::Abs(Values[I]-E[I]);Maximum=FMath::Max(Maximum,double(D));
            ActualValues.Add(MakeShared<FJsonValueNumber>(Values[I]));ExpectedValues.Add(MakeShared<FJsonValueNumber>(E[I]));StageMaximum=FMath::Max(StageMaximum,double(D));
            if (!FMath::IsFinite(Values[I]) || D>1.e-5f+1.e-5f*FMath::Abs(E[I]))
            { if (FirstMismatch==INDEX_NONE) FirstMismatch=I; }
        }
        auto Row=MakeShared<FJsonObject>();Row->SetStringField(TEXT("stage"),Stage);Row->SetNumberField(TEXT("max_abs"),StageMaximum);
        Row->SetArrayField(TEXT("actual"),MoveTemp(ActualValues));Row->SetArrayField(TEXT("expected"),MoveTemp(ExpectedValues));
        Row->SetNumberField(TEXT("first_mismatch"),FirstMismatch);Diagnostics.Add(MakeShared<FJsonValueObject>(Row));
        if (FirstMismatch!=INDEX_NONE)
            AddError(FString::Printf(TEXT("%s channel %d: %.9g expected %.9g"),*Stage,FirstMismatch,Values[FirstMismatch],E[FirstMismatch]));
        // Record the complete drift after a finite mismatch; the test still
        // fails below and never relaxes the reference comparison threshold.
        return true;
    };
    FDodgeState State;const auto Before=Cases[0]->AsObject()->GetObjectField(TEXT("state"));
    float PR[12],CR[12],Delta[3],Shift[3];
    if (!ReadArray(Before->TryGetField(TEXT("previous_lower")),State.PreviousLower,41)
        || !ReadArray(Before->TryGetField(TEXT("previous_upper")),State.PreviousUpper,90)
        || !ReadArray(Before->TryGetField(TEXT("current_lower")),State.CurrentLower,41)
        || !ReadArray(Before->TryGetField(TEXT("current_upper")),State.CurrentUpper,90)
        || !ReadArray(Before->TryGetField(TEXT("previous_root")),PR,3) || !ReadArray(Before->TryGetField(TEXT("previous_axes")),PR+3,9)
        || !ReadArray(Before->TryGetField(TEXT("current_root")),CR,3) || !ReadArray(Before->TryGetField(TEXT("current_axes")),CR+3,9)
        || !ReadArray(Before->TryGetField(TEXT("initial_delta_world")),Delta,3) || !ReadArray(Before->TryGetField(TEXT("initial_delta_yaw")),&State.InitialYawDelta,1)
        || !ReadArray(Before->TryGetField(TEXT("root_shift_world")),Shift,3) || !ReadArray(Before->TryGetField(TEXT("root_yaw_offset")),&State.YawOffset,1)
        || !ReadArray(Before->TryGetField(TEXT("remaining")),State.Remaining,6)) return false;
    State.PreviousRoot=FRootFrame::Read12(PR);State.CurrentRoot=FRootFrame::Read12(CR);
    State.InitialWorldDelta=Read(Delta);State.RootShift=Read(Shift);State.bInitialized=true;
    for (const auto& V:Cases)
    {
        const auto F=V->AsObject();if (!F->GetBoolField(TEXT("valid"))) break;
        const auto ExpectedLower=F->GetObjectField(TEXT("lower_models"))->GetObjectField(TEXT("run"));
        const FString Key=F->GetStringField(TEXT("key"));
        float LowerInput[152],Raw[43],Frozen[41],Pins[2];DodgeLowerInput(State,Settings,LowerInput);
        if (!Compare(LowerInput,ExpectedLower->TryGetField(TEXT("input")),152,Key+TEXT(" lower input"))) return false;
        if (!LowerNetwork.Run(MakeArrayView(LowerInput),MakeArrayView(Raw)) || !Compare(Raw,ExpectedLower->TryGetField(TEXT("raw")),43,Key+TEXT(" lower network"))) return false;
        CleanDodgeLower(Raw,State.CurrentLower,Geometry,Settings,Frozen,Pins);
        if (!Compare(Frozen,F->TryGetField(TEXT("baseline")),41,Key+TEXT(" frozen cleanup")) || !Compare(Pins,F->TryGetField(TEXT("expected_pins")),2,Key+TEXT(" pins"))) return false;
        FContext Context;const auto C=F->GetObjectField(TEXT("context"));float Target[3];
        if (!ReadArray(C->TryGetField(TEXT("target")),Target,3) || !ReadArray(C->TryGetField(TEXT("attack_type")),Context.AttackControls,6)) return false;
        for (int32 I=0;I<2;++I)
            if (!ReadArray(C->GetArrayField(TEXT("pelvis"))[I],Context.AttackerPelvis[I],9) || !ReadArray(C->GetArrayField(TEXT("collider"))[I],Context.AttackerCollider[I],9)) return false;
        Context.TargetWorld=Read(Target);Context.Event=float(C->GetNumberField(TEXT("event")));
        FDodgeWork Work;float Input[362],Output[112],Modified[41];FPose Pose;
        if (!PrepareDodge(State,Frozen,Context,Work,Input) || !Compare(Input,F->TryGetField(TEXT("expected_input")),362,Key+TEXT(" upper input"))) return false;
        if (!UpperNetwork.Run(MakeArrayView(Input),MakeArrayView(Output)) || !Compare(Output,F->TryGetField(TEXT("expected_output")),112,Key+TEXT(" upper network"))) return false;
        if (!CompleteDodge(State,Work,Frozen,Output,Geometry,Pose,Modified)) return false;
        const auto After=F->GetObjectField(TEXT("expected_state"));
        if (!Compare(Modified,F->TryGetField(TEXT("expected_lower")),41,Key+TEXT(" modified lower"))
            || !Compare(State.CurrentLower,After->TryGetField(TEXT("current_lower")),41,Key+TEXT(" recurrent lower"))
            || !Compare(State.CurrentUpper,After->TryGetField(TEXT("current_upper")),90,Key+TEXT(" recurrent upper"))
            || !Compare(State.Remaining,After->TryGetField(TEXT("remaining")),6,Key+TEXT(" remaining"))) return false;
        float P[75],R[225],Root[12];
        for (int32 I=0;I<25;++I) { Write(P+3*I,Pose.P[I]);for (int32 J=0;J<3;++J) Write(R+9*I+3*J,Pose.R[I].V[J]); }
        Write(Root,State.CurrentRoot.P);for (int32 J=0;J<3;++J) Write(Root+3+3*J,State.CurrentRoot.R.V[J]);
        if (!Compare(P,F->TryGetField(TEXT("expected_positions")),75,Key+TEXT(" positions"))
            || !Compare(R,F->TryGetField(TEXT("expected_rotations")),225,Key+TEXT(" rotations"))
            || !Compare(Root,F->TryGetField(TEXT("expected_root")),12,Key+TEXT(" root"))) return false;
    }
    FString DiagnosticText;FJsonSerializer::Serialize(Diagnostics,TJsonWriterFactory<>::Create(&DiagnosticText));
    FFileHelper::SaveStringToFile(DiagnosticText,*(Directory/TEXT("unreal_dodge_causal_diagnostics.json")));
    AddInfo(FString::Printf(TEXT("%llu consecutive complete native dodge steps, both networks from own recurrence; max element error %.9g."),State.CompletedSteps,Maximum));
    return State.CompletedSteps==6 && !HasAnyErrors();
}
#endif
