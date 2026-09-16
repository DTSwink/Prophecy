#include "ProphecyParryRuntime.h"
#include "ProphecyDefenseNetwork.h"
#include "ProphecyDefenseContacts.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyParryRecurrenceTest,"Prophecy.NN.Defense.ParryRecurrence",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyParryRecurrenceTest::RunTest(const FString&)
{
    using namespace ProphecyDefense;
    const FString Directory=FPaths::ProjectSavedDir()/TEXT("DefenseIntegration/Models");
    FString Text,Error;TSharedPtr<FJsonObject> Document;
    if (!FFileHelper::LoadFileToString(Text,*(Directory/TEXT("parry_recurrence_reference.json"))) || !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Document) || !Document)
    { AddError(TEXT("Run ExportDefenseGeometryReference.py first."));return false; }
    ProphecyDefense::FGeometry Geometry;FProphecyDefenseNetwork Network;FContactGeometry ContactGeometry;
    if (!Geometry.Load(Directory/TEXT("parry_skeleton.json"),false,Error) || !Network.Initialize(Directory/TEXT("prophecy_parry_upper.onnx"),258,90,Error)
        || !ContactGeometry.Load(Directory/TEXT("parry_colliders.json"),Error))
    { AddError(Error);return false; }
    auto ReadArray=[&](const TSharedPtr<FJsonValue>& V,float* Out,int32 Count)
    {
        if (!V || V->Type!=EJson::Array || V->AsArray().Num()!=Count) { AddError(TEXT("Invalid recurrent fixture tensor."));return false; }
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
    FParryState State;const auto Primers=Document->GetObjectField(TEXT("primers"));
    float Lower[2][41],Upper[2][90],Root[2][12],Baseline[90];
    for (int32 I=0;I<2;++I)
        if (!ReadArray(Primers->GetArrayField(TEXT("lower"))[I],Lower[I],41) || !ReadArray(Primers->GetArrayField(TEXT("upper"))[I],Upper[I],90)
            || !ReadArray(Primers->GetArrayField(TEXT("roots"))[I],Root[I],12)) return false;
    if (!ReadArray(Primers->TryGetField(TEXT("baseline1")),Baseline,90)) return false;
    State.Initialize(Lower[0],Upper[0],Root[0],Lower[1],Upper[1],Root[1],Baseline);
    // Export the complete native candidate in the handoff comparator's exact
    // tensor layout, including both real primer poses and swept contacts.
    TSharedPtr<FJsonObject> ContactFixture;
    if (!FFileHelper::LoadFileToString(Text,*(Directory/TEXT("parry_contact_reference.json")))
        || !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),ContactFixture) || !ContactFixture) return false;
    TArray<TSharedPtr<FJsonValue>> Inputs,Outputs,Positions,Rotations,Roots,Centers,Axes;
    auto Array=[](const float* P,int32 Count)->TSharedPtr<FJsonValue>
    {
        TArray<TSharedPtr<FJsonValue>> Values;Values.Reserve(Count);
        for (int32 I=0;I<Count;++I) Values.Add(MakeShared<FJsonValueNumber>(P[I]));
        return MakeShared<FJsonValueArray>(MoveTemp(Values));
    };
    FDefenseBox PreviousBoxes[20],PreviousAttack;FContactOrder ContactOrder;double PreviousTime=0;
    float AttackerHalf[3];if (!ReadArray(ContactFixture->TryGetField(TEXT("attacker_half")),AttackerHalf,3)) return false;
    auto StorePose=[&](const FPose& Pose,const float* R12)
    {
        TArray<TSharedPtr<FJsonValue>> P,R,C,A;
        for (int32 I=0;I<25;++I)
        {
            float V[3];Write(V,Pose.P[I]);P.Add(Array(V,3));TArray<TSharedPtr<FJsonValue>> Rows;
            for (int32 J=0;J<3;++J) { Write(V,Pose.R[I].V[J]);Rows.Add(Array(V,3)); }
            R.Add(MakeShared<FJsonValueArray>(MoveTemp(Rows)));
        }
        FDefenseBox Boxes[20];ContactGeometry.Build(Pose,Boxes);
        for (int32 I=0;I<ContactGeometry.Count;++I)
        {
            float V[3];Write(V,Boxes[I].Center);C.Add(Array(V,3));TArray<TSharedPtr<FJsonValue>> Rows;
            for (int32 J=0;J<3;++J) { Write(V,Boxes[I].Axes.V[J]);Rows.Add(Array(V,3)); }
            A.Add(MakeShared<FJsonValueArray>(MoveTemp(Rows)));
        }
        const auto F=ContactFixture->GetArrayField(TEXT("frames"))[Positions.Num()]->AsObject();float AC[3],AR[9];
        if (!ReadArray(F->TryGetField(TEXT("attacker_center")),AC,3) || !ReadArray(F->TryGetField(TEXT("attacker_axes")),AR,9)) return false;
        const FDefenseBox Attack{Read(AC),Rows(AR)};const double Time=F->GetNumberField(TEXT("time"));
        if (!Positions.IsEmpty()) for (int32 I=0;I<ContactGeometry.Count;++I)
        {
            const auto& Box=ContactGeometry.Boxes[I];const auto Pair=SweepBoxes(PreviousBoxes[I],Boxes[I],Box.Half,Box.CenterOffset,
                PreviousAttack,Attack,Read(AttackerHalf),FVector3f::ZeroVector);
            ContactOrder.Include(Pair,I,(ContactGeometry.BlockingMask(16,true)&(1u<<I))!=0,PreviousTime,Time);
        }
        FMemory::Memcpy(PreviousBoxes,Boxes,sizeof(Boxes));PreviousAttack=Attack;PreviousTime=Time;
        Positions.Add(MakeShared<FJsonValueArray>(MoveTemp(P)));Rotations.Add(MakeShared<FJsonValueArray>(MoveTemp(R)));
        Centers.Add(MakeShared<FJsonValueArray>(MoveTemp(C)));Axes.Add(MakeShared<FJsonValueArray>(MoveTemp(A)));Roots.Add(Array(R12,12));return true;
    };
    for (int32 I=0;I<2;++I)
    {
        FPose Primer,FrozenPrimer;float PrimerBaseline[90];
        Geometry.LowerPose(Lower[I],Read(Root[I]),Rows(Root[I]+3),FrozenPrimer);
        Geometry.EncodeUpper(FrozenPrimer,Read(Root[I]),Rows(Root[I]+3),PrimerBaseline);
        Geometry.Finish(Lower[I],Upper[I],Read(Root[I]),Rows(Root[I]+3),FrozenPrimer,PrimerBaseline,Primer);
        // Parry owns only upper joints. The supplied lower globals are copied
        // unchanged even for primer display, exactly as native rollout does.
        const auto F=ContactFixture->GetArrayField(TEXT("frames"))[I]->AsObject();float P[75],R[225];
        if (!ReadArray(F->TryGetField(TEXT("positions")),P,75) || !ReadArray(F->TryGetField(TEXT("rotations")),R,225)) return false;
        for (int32 Bone:{0,17,18,19,20,21,22,23,24}) { Primer.P[Bone]=Read(P+3*Bone);Primer.R[Bone]=Rows(R+9*Bone); }
        if (!StorePose(Primer,Root[I])) return false;
    }
    FContext Context;float Target[3];
    if (!ReadArray(Document->TryGetField(TEXT("target")),Target,3) || !ReadArray(Document->TryGetField(TEXT("attack_type")),Context.AttackControls,6)) return false;
    Context.TargetWorld=Read(Target);const float Drawn=float(Document->GetNumberField(TEXT("drawn")));
    for (const auto& V:Document->GetArrayField(TEXT("frames")))
    {
        const auto F=V->AsObject();const FString Stage=FString::Printf(TEXT("frame %d"),int32(F->GetNumberField(TEXT("frame"))));
        float NextLower[41],NextBase[90],NextRoot[12],FP[75],FR[225];
        if (!ReadArray(F->TryGetField(TEXT("lower")),NextLower,41) || !ReadArray(F->TryGetField(TEXT("baseline")),NextBase,90)
            || !ReadArray(F->TryGetField(TEXT("root")),NextRoot,12) || !ReadArray(F->TryGetField(TEXT("frozen_p")),FP,75)
            || !ReadArray(F->TryGetField(TEXT("frozen_r")),FR,225)) return false;
        FPose Frozen,Out;
        for (int32 I=0;I<25;++I) { Frozen.P[I]=Read(FP+I*3);Frozen.R[I]=Rows(FR+I*9); }
        for (int32 I=0;I<2;++I)
            if (!ReadArray(F->GetArrayField(TEXT("pelvis"))[I],Context.AttackerPelvis[I],9) || !ReadArray(F->GetArrayField(TEXT("collider"))[I],Context.AttackerCollider[I],9)) return false;
        Context.Event=float(F->GetNumberField(TEXT("event")));
        FParryWork Work;float Input[258],Delta[90];const auto Next=FRootFrame::Read12(NextRoot);
        if (!PrepareParry(State,NextLower,NextBase,Next,Context,Drawn,Work,Input)) return false;
        if (!Compare(Input,F->TryGetField(TEXT("expected_input")),258,Stage+TEXT(" input"))) return false;
        if (!Network.Run(MakeArrayView(Input),MakeArrayView(Delta))) { AddError(TEXT("Parry inference failed."));return false; }
        if (!Compare(Delta,F->TryGetField(TEXT("expected_delta")),90,Stage+TEXT(" delta"))) return false;
        if (!CompleteParry(State,Work,Delta,NextLower,NextBase,Next,Frozen,Geometry,Out)) return false;
        Inputs.Add(Array(Input,258));Outputs.Add(Array(Delta,90));if (!StorePose(Out,NextRoot)) return false;
        float P[75],R[225];
        for (int32 I=0;I<25;++I) { Write(P+I*3,Out.P[I]);for (int32 J=0;J<3;++J) Write(R+I*9+J*3,Out.R[I].V[J]); }
        if (!Compare(P,F->TryGetField(TEXT("expected_p")),75,Stage+TEXT(" positions"))
            || !Compare(R,F->TryGetField(TEXT("expected_r")),225,Stage+TEXT(" rotations"))
            || !Compare(State.CurrentUpper,F->TryGetField(TEXT("expected_upper")),90,Stage+TEXT(" recurrent upper"))) return false;
        for (int32 I:{0,17,18,19,20,21,22,23,24})
        {
            if (FMemory::Memcmp(P+I*3,FP+I*3,3*sizeof(float)) || FMemory::Memcmp(R+I*9,FR+I*9,9*sizeof(float)))
            { AddError(TEXT("Parry changed a frozen lower joint."));return false; }
        }
        if (CompleteParry(State,Work,Delta,NextLower,NextBase,Next,Frozen,Geometry,Out))
        { AddError(TEXT("Parry applied the same prepared step twice."));return false; }
    }
    auto Candidate=MakeShared<FJsonObject>();Candidate->SetArrayField(TEXT("network/inputs"),Inputs);Candidate->SetArrayField(TEXT("network/outputs"),Outputs);
    Candidate->SetArrayField(TEXT("trajectory/positions"),Positions);Candidate->SetArrayField(TEXT("trajectory/basis"),Rotations);Candidate->SetArrayField(TEXT("trajectory/roots"),Roots);
    Candidate->SetArrayField(TEXT("colliders/centers"),Centers);Candidate->SetArrayField(TEXT("colliders/axes"),Axes);
    Candidate->SetNumberField(TEXT("contact/protected"),ContactOrder.bProtected?1:0);
    Candidate->SetNumberField(TEXT("contact/first_block_time"),FMath::IsFinite(ContactOrder.BlockTime)?ContactOrder.BlockTime:-1);
    FString CandidateText;FJsonSerializer::Serialize(Candidate,TJsonWriterFactory<>::Create(&CandidateText));
    FFileHelper::SaveStringToFile(CandidateText,*(Directory/TEXT("ue_parry_candidate.json")));
    TestTrue(TEXT("Native inferred pose blocks the attack"),ContactOrder.bProtected);
    const double ExpectedContact=ContactFixture->GetNumberField(TEXT("expected_time"));
    TestTrue(TEXT("Native inferred contact matches saved time"),FMath::Abs(ContactOrder.BlockTime-ExpectedContact)<=1.e-5+1.e-5*ExpectedContact);
    AddInfo(FString::Printf(TEXT("%llu consecutive native parry steps, max element error %.9g; lower joints unchanged bit-for-bit; native block %.9f."),State.CompletedSteps,Maximum,ContactOrder.BlockTime));
    return State.CompletedSteps>0 && !HasAnyErrors();
}
#endif
