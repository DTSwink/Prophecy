#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyFKReturnParityTest,"Prophecy.NN.FKReturn.LabParityAndCost",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyFKReturnParityTest::RunTest(const FString&)
{
    using namespace ProphecyFKReturn;
    FString Json;TSharedPtr<FJsonObject> Root;
    if(!FFileHelper::LoadFileToString(Json,*(FPaths::ProjectSavedDir()/TEXT("FKReturn/lab-reference.json"))) ||
        !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Json),Root))
    {AddError(TEXT("Generate the independent lab fixture with Tools/NN/ExportFKReturnLab.cjs"));return false;}
    TArray<FName> Names;TArray<int32> Parents;
    for(const auto& V:Root->GetArrayField(TEXT("names")))Names.Add(FName(V->AsString()));
    for(const auto& V:Root->GetArrayField(TEXT("parents")))Parents.Add(int32(V->AsNumber()));
    auto Pose=[](const TArray<TSharedPtr<FJsonValue>>& Rows)
    {
        TArray<FTransform> Out;Out.Reserve(Rows.Num());
        for(const auto& V:Rows){const auto& A=V->AsArray();
            Out.Emplace(FQuat(A[0]->AsNumber(),A[1]->AsNumber(),A[2]->AsNumber(),A[3]->AsNumber()),
                FVector(A[4]->AsNumber(),A[5]->AsNumber(),A[6]->AsNumber()));}
        return Out;
    };
    double MaxPosition=0,MaxAngle=0,MaxLength=0,MaxMixPosition=0,MaxMixAngle=0;
    int32 Cases=0,Samples=0;FCurve BenchmarkCurve;TArray<FTransform> BenchmarkPose;
    for(const auto& Row:Root->GetArrayField(TEXT("cases")))
    {
        const auto C=Row->AsObject(),O=C->GetObjectField(TEXT("options"));FProfile P;
        P.Duration=O->GetNumberField(TEXT("duration"));P.Easing=O->GetNumberField(TEXT("easing"));P.Inertia=O->GetNumberField(TEXT("inertia"));
        for(int32 G=0;G<GroupCount;++G)P.Weights[G]=O->GetArrayField(TEXT("weights"))[G]->AsNumber();
        const auto Previous=Pose(C->GetArrayField(TEXT("previous"))),Current=Pose(C->GetArrayField(TEXT("current")));
        FCurve Curve;if(!Prepare(Curve,P,1,Names,Parents,Previous,Current,1.f/C->GetNumberField(TEXT("fps"))))
        {AddError(TEXT("Bad fixture hierarchy"));return false;}
        const auto& References=C->GetArrayField(TEXT("samples"));
        const auto NN=Pose(References.Last()->AsObject()->GetArrayField(TEXT("pose")));
        for(const auto& Sample:References)
        {
            const float X=Sample->AsObject()->GetNumberField(TEXT("x")),Elapsed=X*P.Duration;
            const auto Expected=Pose(Sample->AsObject()->GetArrayField(TEXT("pose")));
            auto Actual=Current;const auto W=Curve.Weights(Elapsed);
            for(const auto& B:Curve.Bones)
            {
                FQuat4f Q;FVector3f V;FCurve::Local(B,W,Q,V);
                Actual[B.Index]=FTransform(FQuat(Q),FVector(V))*Actual[B.Parent];
                MaxPosition=FMath::Max(MaxPosition,FVector::Distance(Actual[B.Index].GetLocation(),Expected[B.Index].GetLocation()));
                MaxAngle=FMath::Max(MaxAngle,Actual[B.Index].GetRotation().GetNormalized().AngularDistance(Expected[B.Index].GetRotation()));
                MaxLength=FMath::Max(MaxLength,FMath::Abs(FVector::Distance(Actual[B.Index].GetLocation(),Actual[B.Parent].GetLocation())-
                    FVector::Distance(Current[B.Index].GetLocation(),Current[B.Parent].GetLocation())));
            }
            for(float Coefficient:{.5f,1.f,2.f,5.f})
            {
                Curve.Coefficient=Coefficient;auto Mixed=NN;Curve.Apply(Elapsed,Mixed);
                if(X>=1){for(int32 I=0;I<NN.Num();++I)TestTrue(TEXT("Completion returns exact NN"),Mixed[I].Equals(NN[I],0));continue;}
                auto Oracle=NN;const double Weight=FMath::Pow(double(X),double(Coefficient));
                for(const auto& B:Curve.Bones)
                {
                    const auto LabLocal=Expected[B.Index].GetRelativeTransform(Expected[B.Parent]);
                    const auto NNLocal=NN[B.Index].GetRelativeTransform(NN[B.Parent]);
                    // Double-precision independent SLERP rotation oracle.
                    const auto Rotation=FQuat::Slerp(LabLocal.GetRotation(),NNLocal.GetRotation(),Weight).GetNormalized();
                    const auto Position=BlendOffset(FVector3f(LabLocal.GetLocation()),FVector3f(NNLocal.GetLocation()),float(Weight));
                    Oracle[B.Index]=FTransform(Rotation,FVector(Position))*Oracle[B.Parent];
                    MaxMixPosition=FMath::Max(MaxMixPosition,FVector::Distance(Mixed[B.Index].GetLocation(),Oracle[B.Index].GetLocation()));
                    MaxMixAngle=FMath::Max(MaxMixAngle,Mixed[B.Index].GetRotation().GetNormalized().AngularDistance(Oracle[B.Index].GetRotation()));
                }
                for(int32 I=0;I<Names.Num();++I)
                    if(!Names[I].ToString().StartsWith(TEXT("spine")) && (Names[I]==TEXT("pelvis") || I>=18 || I==0))
                        TestTrue(TEXT("Lower/root completely untouched"),Mixed[I].Equals(NN[I],0));
            }
            ++Samples;
        }
        // Hands must not acquire their own inertia, irrespective of ancestors' weights.
        FProfile No=P;No.Inertia=0;FCurve NoCurve;Prepare(NoCurve,No,1,Names,Parents,Previous,Current,1.f/C->GetNumberField(TEXT("fps")));
        const auto A=Curve.Weights(P.Duration*.25f),B=NoCurve.Weights(P.Duration*.25f);
        for(int32 J=0;J<BoneCount;++J)if(Curve.Bones[J].Group==GroupCount)
        {
            FQuat4f QA,QB;FVector3f PA,PB;FCurve::Local(Curve.Bones[J],A,QA,PA);FCurve::Local(NoCurve.Bones[J],B,QB,PB);
            TestTrue(TEXT("Hands have no local rotational or positional inertia"),QA.Equals(QB,0) && PA.Equals(PB,0));
        }
        BenchmarkCurve=Curve;BenchmarkCurve.Coefficient=1;BenchmarkPose=NN;++Cases;
    }
    TestEqual(TEXT("All lab variants"),Cases,320);
    TestTrue(TEXT("Native lab positions within 0.003 cm"),MaxPosition<.003);
    TestTrue(TEXT("Native lab rotations within 0.02 degrees"),MaxAngle<FMath::DegreesToRadians(.02));
    TestTrue(TEXT("FK lengths within 0.0001 cm"),MaxLength<.0001);
    TestTrue(TEXT("Mixed positions within 0.003 cm"),MaxMixPosition<.003);
    TestTrue(TEXT("Mixed rotations within 0.02 degrees"),MaxMixAngle<FMath::DegreesToRadians(.02));
    constexpr int32 Iterations=50000;double Checksum=0;TArray<FTransform> Work=BenchmarkPose;
    const double Start=FPlatformTime::Seconds();
    for(int32 I=0;I<Iterations;++I)
    {
        FMemory::Memcpy(Work.GetData(),BenchmarkPose.GetData(),Work.Num()*sizeof(FTransform));
        BenchmarkCurve.Apply((.05f+.9f*float(I%101)/100.f)/BenchmarkCurve.InverseDuration,Work);
        Checksum+=Work[10].GetTranslation().X;
    }
    const double Us=(FPlatformTime::Seconds()-Start)*1.e6/Iterations;
    const FString Report=FString::Printf(TEXT("cases=%d samples=%d lab_cm=%.9g lab_degrees=%.9g length_cm=%.9g mix_cm=%.9g mix_degrees=%.9g microseconds_per_pose=%.6f checksum=%.6f"),
        Cases,Samples,MaxPosition,FMath::RadiansToDegrees(MaxAngle),MaxLength,MaxMixPosition,FMath::RadiansToDegrees(MaxMixAngle),Us,Checksum);
    AddInfo(Report);FFileHelper::SaveStringToFile(Report,*(FPaths::ProjectSavedDir()/TEXT("FKReturn/native-parity.txt")));
    return !HasAnyErrors();
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyFKReturnLifecycleTest,"Prophecy.NN.FKReturn.LifecycleAndCurve",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyFKReturnLifecycleTest::RunTest(const FString&)
{
    using namespace ProphecyFKReturn;
    FCurve C;C.InverseDuration=1;C.Coefficient=1;TestEqual(TEXT("Linear NN half weight"),C.Weights(.5f).NN,.5f);
    C.Coefficient=2;TestEqual(TEXT("Squared NN quarter weight"),C.Weights(.5f).NN,.25f);
    TestEqual(TEXT("Exact start"),C.Weights(0).NN,0.f);TestEqual(TEXT("Exact end"),C.Weights(1).NN,1.f);
    const auto NoHold=C.Weights(.75f);
    C.SetAlphaHold(.5f);
    TestEqual(TEXT("Hold excludes NN at midpoint"),C.Weights(.5f).NN,0.f);
    TestEqual(TEXT("Coefficient shapes remaining half"),C.Weights(.75f).NN,.25f);
    TestEqual(TEXT("Hold does not retime FK return"),C.Weights(.75f).Blend,NoHold.Blend);
    C.Coefficient=1;TestEqual(TEXT("Linear halfway through remaining window"),C.Weights(.75f).NN,.5f);
    C.SetAlphaHold(1);TestEqual(TEXT("Full hold before deadline"),C.Weights(.999f).NN,0.f);
    TestEqual(TEXT("Full hold exact deadline"),C.Weights(1).NN,1.f);
    auto* W=UWorld::CreateWorld(EWorldType::Editor,false);auto* A=W?W->SpawnActor<AProphecyAgent>():nullptr;
    if(!A)return false;
    TestTrue(TEXT("Default control"),UProphecyFKReturnLibrary::SetAttackFKReturn(A,true,2));
    TestFalse(TEXT("Reject zero coefficient"),UProphecyFKReturnLibrary::SetAttackFKReturn(A,true,0));
    TestFalse(TEXT("Reject negative hold"),UProphecyFKReturnLibrary::SetAttackFKReturn(A,true,1,-.1f));
    TestFalse(TEXT("Reject excessive hold"),UProphecyFKReturnLibrary::SetAttackFKReturn(A,true,1,1.1f));
    TArray<FName> Names;TArray<int32> Parents;TArray<FTransform> P;
    Names.Add(TEXT("pelvis"));Parents.Add(INDEX_NONE);P.Add(FTransform::Identity);
    for(const auto& D:Data::Bones)
    {
        const int32 Parent=Names.IndexOfByKey(FName(D.Parent));check(Parent!=INDEX_NONE);
        Parents.Add(Parent);Names.Add(FName(D.Name));
        P.Add(FTransform(FQuat(D.Q[0],D.Q[1],D.Q[2],D.Q[3]).GetNormalized(),FVector(D.P[0],D.P[1],D.P[2]))*P[Parent]);
    }
    Begin(A,TEXT("slashLU"),Names,Parents,P,P,10,1.f/30);
    TestTrue(TEXT("Begin is active"),Active.Contains(A));
    auto Prev=P,Now=P,Local=P;Apply(A,10.1,Prev,Now,Local);const auto First=Now;
    Prev=P;Now=P;Apply(A,10.1,Prev,Now,Local);
    for(int32 I=0;I<Now.Num();++I)TestTrue(TEXT("Republishing is deterministic"),Now[I].Equals(First[I],0));
    Cancel(A);TestFalse(TEXT("Replacement special cancels"),Active.Contains(A));
    Begin(A,TEXT("slashLU"),Names,Parents,P,P,10,1.f/30);
    UProphecyFKReturnLibrary::SetAttackFKReturn(A,false,1);TestFalse(TEXT("Disable cancels"),Active.Contains(A));
    Begin(A,TEXT("slashLU"),Names,Parents,P,P,10,1.f/30);TestFalse(TEXT("Disabled begins no work"),Active.Contains(A));
    UProphecyFKReturnLibrary::SetAttackFKReturn(A,true,1);Begin(A,TEXT("slashLU"),Names,Parents,P,P,10,1.f/30);
    for(int32 Tick=0;Tick<16;++Tick)FWorldDelegates::OnWorldPreActorTick.Broadcast(W,LEVELTICK_All,1.f/5);
    TestTrue(TEXT("Keep final interpolation interval"),Apply(A,12,Prev,Now,Local));
    TestFalse(TEXT("Completion retires recurring work"),Apply(A,13,Prev,Now,Local));
    TestFalse(TEXT("No retained active entry"),Active.Contains(A));
    UProphecyFKReturnLibrary::SetAttackFKReturn(A,true,2,.5f);CaptureReset(A);
    UProphecyFKReturnLibrary::SetAttackFKReturnProfile(A,NAME_None,.7f,.1f,.9f,FProphecyFKInertiaWeights());
    UProphecyFKReturnLibrary::SetAttackFKReturn(A,false,3);RestoreReset(A);
    TestTrue(TEXT("Reset restores settings and copied profiles"),Configs.FindChecked(A).Enabled &&
        Configs.FindChecked(A).Coefficient==2 && Configs.FindChecked(A).AlphaHold==.5f && Configs.FindChecked(A).Profiles.IsEmpty());
    Remove(A);TestFalse(TEXT("Remove clears settings"),Configs.Contains(A));W->DestroyWorld(false);
    return !HasAnyErrors();
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyFKReturnTickTest,"Prophecy.NN.FKReturn.GoldenTickTiming",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyFKReturnTickTest::RunTest(const FString&)
{
    using namespace ProphecyFKReturn;
    auto* W=UWorld::CreateWorld(EWorldType::Editor,false);auto* A=W?W->SpawnActor<AProphecyAgent>():nullptr;
    if(!A)return false;
    TArray<FName> Names;TArray<int32> Parents;TArray<FTransform> P;
    Names.Add(TEXT("pelvis"));Parents.Add(INDEX_NONE);P.Add(FTransform::Identity);
    for(const auto& D:Data::Bones)
    {
        const int32 Parent=Names.IndexOfByKey(FName(D.Parent));Parents.Add(Parent);Names.Add(FName(D.Name));
        P.Add(FTransform(FQuat(D.Q[0],D.Q[1],D.Q[2],D.Q[3]).GetNormalized(),FVector(D.P[0],D.P[1],D.P[2]))*P[Parent]);
    }
    UProphecyFKReturnLibrary::SetAttackFKReturn(A,true,2);
    auto AttackPose=P;
    AttackPose.Last().SetRotation(FQuat(FVector::UpVector,1.1)*AttackPose.Last().GetRotation());
    auto Prev=P,Now=P,Local=P;
    TArray<FTransform> Reference;
    double ReferenceWeight[16]{};
    for(float FPS:{5.f,30.f,60.f,120.f})
    {
        A->CustomTimeDilation=.1f; // Deliberately irrelevant to authored duration.
        Begin(A,TEXT("slashLU"),Names,Parents,P,AttackPose,10,1.f/30);
        // A giant source-time jump alone is not permission to advance.
        Apply(A,10000,Prev,Now,Local);
        TestEqual(TEXT("Wall-clock jump advances zero ticks"),TickPhases.FindChecked(A).Elapsed,0.);
        TestTrue(TEXT("Wall-clock jump still displays attack end"),Now.Last().Equals(AttackPose.Last(),.0001));
        for(int32 Tick=1;Tick<=16;++Tick)
        {
            // Include a 20-second hitch: still exactly one unpaused game tick.
            FWorldDelegates::OnWorldPreActorTick.Broadcast(W,LEVELTICK_All,Tick==7?20.f:1.f/FPS);
            Prev=P;Now=P;Apply(A,10000+Tick,Prev,Now,Local);
            const double Elapsed=TickPhases.FindChecked(A).Elapsed;
            TestTrue(TEXT("One authored second is always sixty ticks"),FMath::IsNearlyEqual(Elapsed,Tick/60.,1.e-12));
            const auto& Curve=Active.FindChecked(A).Curve;const double Weight=Curve.Weights(float(Elapsed)).NN;
            if(FPS==5)ReferenceWeight[Tick-1]=Weight;
            else TestEqual(TEXT("Same NN takeover at 5/30/60/120 FPS"),Weight,ReferenceWeight[Tick-1]);
            for(int32 J=0;J<Now.Num();++J)
                if(FPS==5)Reference.Add(Now[J]);
                else TestTrue(TEXT("Actual returning poses match by tick at every FPS"),Now[J].Equals(Reference[(Tick-1)*Now.Num()+J],0));
            const auto OriginalPrevious=Prev,OriginalCurrent=Now;
            Prev=P;Now=P;Apply(A,10000+Tick,Prev,Now,Local);
            for(int32 J=0;J<P.Num();++J)
                TestTrue(TEXT("Duplicate publication preserves both endpoints"),Prev[J].Equals(OriginalPrevious[J],0) && Now[J].Equals(OriginalCurrent[J],0));
            if(Tick<16)
            {
                // Extra policy evaluations in one game tick cannot spend more time.
                Prev=P;Now=P;Apply(A,10000+Tick+.25,Prev,Now,Local);
                TestEqual(TEXT("Catch-up evaluations cannot advance timer"),TickPhases.FindChecked(A).Elapsed,Elapsed);
            }
            FWorldDelegates::OnWorldPreActorTick.Broadcast(W,LEVELTICK_PauseTick,1.f/FPS);
            FWorldDelegates::OnWorldPreActorTick.Broadcast(W,LEVELTICK_All,0.f);
        }
        TestEqual(TEXT("0.26 seconds completes on tick sixteen, even at 5 FPS"),ReferenceWeight[15],1.);
        TestTrue(TEXT("Still incomplete on tick fifteen"),ReferenceWeight[14]<1.);
        TestFalse(TEXT("Next publication retires both completed endpoints"),Apply(A,20000,Prev,Now,Local));
        TestFalse(TEXT("Clock sidecar retired"),TickPhases.Contains(A));
        TestEqual(TEXT("No unread clock after retirement"),ProphecyBlendClock::Consume(A,ProphecyBlendClock::EKind::FKReturn),0.);
    }
    // Sampling may be less frequent than world ticks. Consume each tick once.
    Begin(A,TEXT("slashLU"),Names,Parents,P,P,0,1.f/30);
    for(int32 I=0;I<4;++I)FWorldDelegates::OnWorldPreActorTick.Broadcast(W,LEVELTICK_All,1.f/120);
    Apply(A,1,Prev,Now,Local);TestEqual(TEXT("Four real ticks between policy publications"),TickPhases.FindChecked(A).Elapsed,4./60.);
    Cancel(A);TestFalse(TEXT("Cancel clears tick phase"),TickPhases.Contains(A));
    TestEqual(TEXT("Cancel clears clock"),ProphecyBlendClock::Consume(A,ProphecyBlendClock::EKind::FKReturn),0.);
    for(float Duration:{.1f,.3f,.7f,1.f})
    {
        UProphecyFKReturnLibrary::SetAttackFKReturnProfile(A,NAME_None,Duration,.51f,.12f,FProphecyFKInertiaWeights());
        Begin(A,TEXT("slashLU"),Names,Parents,P,AttackPose,0,1.f/30);
        const int32 Count=FMath::RoundToInt(Duration*60);
        for(int32 I=0;I<Count;++I)FWorldDelegates::OnWorldPreActorTick.Broadcast(W,LEVELTICK_All,.2f);
        Prev=P;Now=P;Apply(A,1,Prev,Now,Local);
        TestTrue(TEXT("Float duration pins complete on their integer deadline"),TickPhases.FindChecked(A).Complete);
        for(int32 J=0;J<P.Num();++J)TestTrue(TEXT("Deadline publishes exact original NN"),Now[J].Equals(P[J],0));
        TestFalse(TEXT("Rounded duration never leaves permanent active work"),Apply(A,2,Prev,Now,Local));
    }
    Remove(A);W->DestroyWorld(false);return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyFKReturnAcceptedHistoryTest,"Prophecy.NN.FKReturn.AcceptedHistory",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyFKReturnAcceptedHistoryTest::RunTest(const FString&)
{
    using namespace ProphecyFKReturn;
    auto* W=UWorld::CreateWorld(EWorldType::Editor,false);auto* A=W?W->SpawnActor<AProphecyAgent>():nullptr;
    if(!A)return false;
    TArray<FName> Names;TArray<int32> Parents;TArray<FTransform> Idle;
    Names.Add(TEXT("pelvis"));Parents.Add(INDEX_NONE);Idle.Add(FTransform::Identity);
    for(const auto& D:Data::Bones)
    {
        const int32 Parent=Names.IndexOfByKey(FName(D.Parent));Parents.Add(Parent);Names.Add(FName(D.Name));
        Idle.Add(FTransform(FQuat(D.Q[0],D.Q[1],D.Q[2],D.Q[3]).GetNormalized(),FVector(D.P[0],D.P[1],D.P[2]))*Idle[Parent]);
    }
    auto Attack=Idle;Attack.Last().SetRotation(FQuat(FVector::UpVector,1.1)*Attack.Last().GetRotation());
    for(float Coefficient:{1.f,10.f})for(float Hold:{0.f,.5f,1.f})
    {
        UProphecyFKReturnLibrary::SetAttackFKReturn(A,true,Coefficient,Hold);
        UProphecyFKReturnLibrary::SetAttackFKReturnProfile(A,NAME_None,1,.51f,.12f,FProphecyFKInertiaWeights());
        Begin(A,TEXT("slashLU"),Names,Parents,Attack,Attack,0,1.f/30);
        TestEqual(TEXT("Hold latched on handoff"),Active.FindChecked(A).Curve.AlphaHold,Hold);
        TestFalse(TEXT("Zero initial alpha skips upper inference"),NeedsInference(A));
        auto Last=Attack,Previous=Attack,Now=Attack,Local=Idle;
        for(int32 Tick=1;Tick<=60;++Tick)
        {
            FWorldDelegates::OnWorldPreActorTick.Broadcast(W,LEVELTICK_All,.2f);
            const bool NeedNN=Tick==60 || Tick/60.f>Hold;
            TestEqual(TEXT("Only positive alpha requests upper inference"),NeedsInference(A),NeedNN);
            TestEqual(TEXT("Repeated scheduling spends no extra ticks"),NeedsInference(A),NeedNN);
            // A changing network candidate, predicted from the last accepted pose.
            Previous=Last;Now=Last;
            Now.Last().SetRotation((FQuat(FVector::UpVector,-.04)*Now.Last().GetRotation()).GetNormalized());
            const auto Candidate=Now;bool NewSample=false;
            TestTrue(TEXT("Active through final sample"),Apply(A,Tick,Previous,Now,Local,&NewSample));
            TestTrue(TEXT("Exactly one new feedback sample"),NewSample);
            TestEqual(TEXT("Scheduling and publication consume each tick once"),TickPhases.FindChecked(A).Elapsed,Tick/60.);
            for(int32 J=0;J<Now.Num();++J)TestTrue(TEXT("Previous endpoint is actual accepted history"),Previous[J].Equals(Last[J],1.e-6));
            const auto Accepted=Now,AcceptedPrevious=Previous;
            // Republishing ALREADY BLENDED buffers must not blend them again.
            Apply(A,Tick,Previous,Now,Local,&NewSample);
            TestFalse(TEXT("Duplicate does not write recurrent state"),NewSample);
            for(int32 J=0;J<Now.Num();++J)
                TestTrue(TEXT("Both endpoints survive repeated publication"),Now[J].Equals(Accepted[J],1.e-6) && Previous[J].Equals(AcceptedPrevious[J],1.e-6));
            if(Tick<=FMath::FloorToInt(Hold*60) && Tick<60)
                TestEqual(TEXT("Hold blocks NN for requested fraction"),Active.FindChecked(A).Curve.Weights(Tick/60.f).NN,0.f);
            if(Tick==60)for(int32 J=0;J<Now.Num();++J)TestTrue(TEXT("Completion is exact candidate NN"),Now[J].Equals(Candidate[J],0));
            Last=Now;
        }
        TestFalse(TEXT("Retire after final interval"),Apply(A,61,Previous,Now,Local));
    }
    Remove(A);W->DestroyWorld(false);return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyFKReturnExitIntervalTest,"Prophecy.NN.FKReturn.ExitInterval",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyFKReturnExitIntervalTest::RunTest(const FString&)
{
    using namespace ProphecyFKReturn;
    auto* W=UWorld::CreateWorld(EWorldType::Editor,false);auto* A=W?W->SpawnActor<AProphecyAgent>():nullptr;
    if(!A)return false;
    TArray<FName> Names;TArray<int32> Parents;TArray<FTransform> Idle;
    Names.Add(TEXT("pelvis"));Parents.Add(INDEX_NONE);Idle.Add(FTransform::Identity);
    for(const auto& D:Data::Bones)
    {
        const int32 Parent=Names.IndexOfByKey(FName(D.Parent));Parents.Add(Parent);Names.Add(FName(D.Name));
        Idle.Add(FTransform(FQuat(D.Q[0],D.Q[1],D.Q[2],D.Q[3]).GetNormalized(),FVector(D.P[0],D.P[1],D.P[2]))*Idle[Parent]);
    }
    auto Earlier=Idle;
    const int32 Arm=Names.IndexOfByKey(TEXT("upperarm_r"));
    Earlier[Arm].SetRotation((Earlier[Arm].GetRotation()*FQuat(FVector::UpVector,-.1)).GetNormalized());
    UProphecyFKReturnLibrary::SetAttackFKReturn(A,true,1,1); // Isolate authored inertia.
    double MaxPositionError=0,MaxRotationError=0;
    for(float FPS:{5.f,60.f,120.f})for(uint32 Age:{0u,1u,2u})
    {
        Begin(A,TEXT("slashR"),Names,Parents,Earlier,Idle,10,1.f/30,Age);
        auto Previous=Earlier,Current=Idle,Local=Idle;
        // Re-reading the outgoing publication must retain its moving endpoints.
        Apply(A,10,Previous,Current,Local);
        for(int32 J=0;J<Idle.Num();++J)
            TestTrue(TEXT("Exit preserves outgoing interval"),Previous[J].Equals(Earlier[J],1.e-5) && Current[J].Equals(Idle[J],1.e-5));
        for(uint32 Tick=Age;Tick<2;++Tick)
            FWorldDelegates::OnWorldPreActorTick.Broadcast(W,LEVELTICK_All,1.f/FPS);
        TestFalse(TEXT("Full hold skips first upper inference"),NeedsInference(A));
        const auto Curve=Active.FindChecked(A).Curve;
        auto Expected=Idle;Curve.Apply(2.f/60,Expected);
        Apply(A,10000,Previous,Current,Local); // Source timestamp is not duration.
        TestEqual(TEXT("First endpoint continues two authored ticks later"),TickPhases.FindChecked(A).Elapsed,2./60.);
        for(int32 J=0;J<Idle.Num();++J)
        {
            const double PositionError=FVector::Distance(Current[J].GetTranslation(),Expected[J].GetTranslation());
            const double RotationError=Current[J].GetRotation().GetNormalized().AngularDistance(Expected[J].GetRotation().GetNormalized());
            MaxPositionError=FMath::Max(MaxPositionError,PositionError);MaxRotationError=FMath::Max(MaxRotationError,RotationError);
            // The runtime also caches/recomposes parent locals after float curve sampling.
            // Use LabParityAndCost's .003 cm float-pose budget; the measured
            // extra local-cache round trip is .000140036 cm. History stays strict.
            TestTrue(*FString::Printf(TEXT("First endpoint %s: error %.9g cm / %.9g rad"),*Names[J].ToString(),PositionError,RotationError),
                PositionError<.003 && RotationError<1.e-6);
            TestTrue(TEXT("Previous stays outgoing"),Previous[J].Equals(Idle[J],1.e-5));
        }
        TestFalse(TEXT("Captured arm momentum moves immediately"),Current[Arm].GetRotation().Equals(Idle[Arm].GetRotation(),1.e-5));
        const auto Accepted=Current;
        Apply(A,10000,Previous,Current,Local);
        TestTrue(TEXT("Duplicate sample cannot advance inertia"),Current[Arm].Equals(Accepted[Arm],0));
        for(uint32 Tick=2;Tick<16;++Tick)
            FWorldDelegates::OnWorldPreActorTick.Broadcast(W,LEVELTICK_All,1.f/FPS);
        TestTrue(TEXT("Deadline requests NN"),NeedsInference(A));
        Previous=Current;Current=Earlier;Apply(A,20000,Previous,Current,Local);
        TestTrue(TEXT("Original tick-sixteen deadline is exact NN"),Current[Arm].Equals(Earlier[Arm],0));
        TestFalse(TEXT("Next interval retires"),Apply(A,30000,Previous,Current,Local));
        TestEqual(TEXT("No timer left after return"),ProphecyBlendClock::Consume(A,ProphecyBlendClock::EKind::FKReturn),0.);
    }
    AddInfo(FString::Printf(TEXT("Exit interval maximum round-trip error: %.9g cm / %.9g radians"),MaxPositionError,MaxRotationError));
    Remove(A);W->DestroyWorld(false);return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyFKReturnTrimTest,"Prophecy.NN.FKReturn.Trim",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyFKReturnTrimTest::RunTest(const FString&)
{
    using namespace ProphecyFKReturn;
    FCurve Original;Original.InverseDuration=1;Original.Coefficient=2;
    for(int32 G=0;G<GroupCount;++G)Original.Decay[G]=3;
    auto Trimmed=Original;Trimmed.TakeoverTimeScale=2;
    const auto Before=Original.Weights(.25f),After=Trimmed.Weights(.25f);
    TestEqual(TEXT("Half trim rescales coefficient-2 takeover"),After.NN,.25f);
    TestEqual(TEXT("Trimming does not speed up FK path"),After.Blend,Before.Blend);
    for(int32 G=0;G<GroupCount;++G)TestEqual(TEXT("Trimming does not alter inertia decay"),After.Momentum[G],Before.Momentum[G]);
    TestEqual(TEXT("Full NN at original midpoint"),Trimmed.Weights(.5f).NN,1.f);
    Trimmed.SetAlphaHold(.5f);
    TestEqual(TEXT("Hold is relative to new end"),Trimmed.Weights(.25f).NN,0.f);
    TestEqual(TEXT("Coefficient shapes new remaining window"),Trimmed.Weights(.375f).NN,.25f);
    auto* W=UWorld::CreateWorld(EWorldType::Editor,false);auto* A=W?W->SpawnActor<AProphecyAgent>():nullptr;if(!A)return false;
    using L=UProphecyFKReturnLibrary;
    TestFalse(TEXT("Negative trim rejected"),L::SetAttackFKReturn(A,true,1,0,-.1f));
    TestFalse(TEXT("Trim above one rejected"),L::SetAttackFKReturn(A,true,1,0,1.1f));
    TArray<FName> Names;TArray<int32> Parents;TArray<FTransform> Idle;
    Names.Add(TEXT("pelvis"));Parents.Add(INDEX_NONE);Idle.Add(FTransform::Identity);
    for(const auto& D:Data::Bones)
    {
        const int32 Parent=Names.IndexOfByKey(FName(D.Parent));Parents.Add(Parent);Names.Add(FName(D.Name));
        Idle.Add(FTransform(FQuat(D.Q[0],D.Q[1],D.Q[2],D.Q[3]).GetNormalized(),FVector(D.P[0],D.P[1],D.P[2]))*Idle[Parent]);
    }
    auto Attack=Idle;Attack.Last().SetRotation(FQuat(FVector::UpVector,1)*Attack.Last().GetRotation());
    for(float Trim:{0.f,.5f,.9f,1.f})for(const auto& Profile:Data::Profiles)
    {
        L::SetAttackFKReturn(A,true,2,.5f,Trim);
        Begin(A,FName(Profile.Attack),Names,Parents,Idle,Attack,0,1.f/30);
        if(Trim==1)
        {
            TestFalse(TEXT("Full trim bypasses every family"),IsActive(A));
            TestTrue(TEXT("Full trim requests vanilla inference"),NeedsInference(A));continue;
        }
        const uint64 Limit=uint64(FMath::Max(1.,FMath::CeilToDouble(double(Profile.Duration)*(1.-double(Trim))*60.-1.e-5)));
        TestEqual(TEXT("Global trim shortens each family deadline"),TickPhases.FindChecked(A).Limit,Limit);
        TestEqual(TEXT("Original profile duration preserved"),Active.FindChecked(A).Curve.InverseDuration,1.f/Profile.Duration);
        auto Previous=Idle,Current=Attack,Local=Idle;
        for(uint64 Tick=1;Tick<=Limit;++Tick)
        {
            FWorldDelegates::OnWorldPreActorTick.Broadcast(W,LEVELTICK_All,Tick==2?20.f:1.f/120);
            const bool Need=NeedsInference(A);
            if(Tick==Limit)TestTrue(TEXT("NN runs by trimmed deadline"),Need);
            Previous=Current;Current=Idle;Apply(A,double(Tick),Previous,Current,Local);
        }
        for(int32 J=0;J<Idle.Num();++J)TestTrue(TEXT("Exact NN at shortened deadline"),Current[J].Equals(Idle[J],0));
        TestTrue(TEXT("Final interpolation interval retained"),IsActive(A));
        TestFalse(TEXT("No FK influence after final interval"),Apply(A,double(Limit+1),Previous,Current,Local));
        TestFalse(TEXT("Timer state retired"),TickPhases.Contains(A));
    }
    L::SetAttackFKReturn(A,true,1,0,.5f);CaptureReset(A);
    Begin(A,TEXT("slashLU"),Names,Parents,Idle,Attack,0,1.f/30);
    const auto Limit=TickPhases.FindChecked(A).Limit;
    L::SetAttackFKReturn(A,true,1,0,0);
    TestEqual(TEXT("Trim changes latch next return"),TickPhases.FindChecked(A).Limit,Limit);
    RestoreReset(A);TestEqual(TEXT("Reset restores trim"),Trims.FindChecked(A),.5f);
    TestFalse(TEXT("Reset removes active return"),IsActive(A));
    L::SetAttackFKReturn(A,true,1,0,1);Begin(A,TEXT("slashLU"),Names,Parents,Idle,Attack,0,1.f/30);
    TestFalse(TEXT("Full trim starts no clock"),IsActive(A));
    TestEqual(TEXT("Full trim leaves no pending clock"),ProphecyBlendClock::Consume(A,ProphecyBlendClock::EKind::FKReturn),0.);
    Remove(A);TestFalse(TEXT("Removal clears trim settings"),Trims.Contains(A)||TrimBaselines.Contains(A));
    W->DestroyWorld(false);return !HasAnyErrors();
}
#endif
