// Exercise destination updates through the wrist's 180-degree cut, including
// equivalent quaternion signs. Current lifecycle is covered by BoneOrder/Stagger.
static FString CheckReachContinuity(bool& Passed)
{
 Passed=true;FString Text;TSharedPtr<FJsonObject> Root;
 if(!FFileHelper::LoadFileToString(Text,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/SwordLabPort20261010/parity.json")))||!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Root)){Passed=false;return TEXT("Missing parity fixture");}
 double Step=0,OldStep=0,EndError=0,LengthError=0,DeadlineStep=0,DeadlineError=0;int Cases=0,Fits=0,DeadlineCases=0;
 for(const auto& RV:Root->GetArrayField(TEXT("rows"))){const FActive Seed=OptimizationFixture(Root,RV->AsObject());
  for(int Direction:{-1,1})for(int Sign:{-1,1}){
   FActive S=Seed;CaptureArm(S,S.Base,S.SourceArm);S.Status.ReachTicks=48;
   auto Target=[&](int Tick,FTransform* Out){for(int K=0;K<3;++K)Out[K]=S.SourceArm[K];Out[2].SetRotation((S.SourceArm[2].GetRotation()*FQuat(FVector(1,2,3).GetSafeNormal(),FMath::DegreesToRadians(Direction*(170.+Tick*.5))))*(Tick%8?Sign:1));};
   Target(0,S.DestinationArm);FQuat Previous=FQuat::Identity,PreviousOld=FQuat::Identity;
   for(int Tick=1;Tick<=88;++Tick){S.Status.Tick=Tick;S.Status.Progress=.8+.2*Clamp(Tick/48.);S.Status.ReachDone=Tick>=48;S.Pose=S.Base;
    ReachArm(S,Tick%4==0,[&](FTransform (&Out)[3]){Target(FMath::Min(Tick,48),Out);++Fits;});
    FTransform Local[3];CaptureArm(S,S.Pose,Local);const FQuat Q=Local[2].GetRotation(),Old=FQuat::Slerp(S.SourceArm[2].GetRotation(),S.DestinationArm[2].GetRotation(),S.Status.Progress);
    if(Tick>1){Step=FMath::Max(Step,Angle(Q,Previous));OldStep=FMath::Max(OldStep,Angle(Old,PreviousOld));}Previous=Q;PreviousOld=Old;
    for(int K=0;K<3;++K){Passed&=!Local[K].ContainsNaN()&&Local[K].GetRotation().IsNormalized();LengthError=FMath::Max(LengthError,FMath::Abs(Local[K].GetLocation().Size()-S.SourceArm[K].GetLocation().Size()));}
    if(Tick==88)EndError=FMath::Max(EndError,Angle(Q,S.DestinationArm[2].GetRotation()));
   }++Cases;
  }

  // A target update at the deadline must not bypass smoothing, regardless of
  // the agent's refit slot. Hold it afterward to verify eventual convergence.
  for(int Deadline:{47,48,49})for(int Slot=0;Slot<4;++Slot){
   FActive S=Seed;CaptureArm(S,S.Base,S.SourceArm);S.Status.ReachTicks=Deadline;
   for(int K=0;K<3;++K)S.DestinationArm[K]=S.SourceArm[K];
   FQuat Previous=S.SourceArm[0].GetRotation();
   for(int Tick=1;Tick<=Deadline+40;++Tick){
    S.Status.Tick=Tick;S.Status.Progress=Ease(Clamp(double(Tick)/Deadline));S.Status.ReachDone=Tick>=Deadline;S.Pose=S.Base;
    ReachArm(S,Tick%4==Slot,[&](FTransform (&Out)[3]){
     for(int K=0;K<3;++K)Out[K]=S.SourceArm[K];
     if(Tick>=Deadline)Out[0].SetRotation(S.SourceArm[0].GetRotation()*FQuat(FVector::UpVector,FMath::DegreesToRadians(30.)));
    });
    FTransform Local[3];CaptureArm(S,S.Pose,Local);const FQuat Q=Local[0].GetRotation();
    DeadlineStep=FMath::Max(DeadlineStep,Angle(Q,Previous));Previous=Q;
    if(Tick==Deadline+40)DeadlineError=FMath::Max(DeadlineError,Angle(Q,S.DestinationArm[0].GetRotation()));
   }++DeadlineCases;
  }
 }
 Passed&=Step<4&&OldStep>20&&EndError<.0001&&LengthError<.00001&&Fits==Cases*52&&DeadlineStep<8&&DeadlineError<.001;
 return FString::Printf(TEXT("passed=%d cases=%d fits=%d max_step_deg=%.12g old_step_deg=%.12g endpoint_deg=%.12g length_cm=%.12g deadline_cases=%d deadline_step_deg=%.12g deadline_settled_deg=%.12g\n"),Passed,Cases,Fits,Step,OldStep,EndError,LengthError,DeadlineCases,DeadlineStep,DeadlineError);
}
static FAutoConsoleCommand VerifyReachCommand(TEXT("Prophecy.Sword.VerifyReachContinuity"),TEXT("Run pure reach and bone-order checks without editor Automation."),FConsoleCommandDelegate::CreateLambda([]{
 bool Passed;const FString Result=CheckReachContinuity(Passed)+OrderResultText(CheckBoneOrder()),Dir=FPaths::ProjectSavedDir()/TEXT("Diagnostics/SwordReachJitter20261011");IFileManager::Get().MakeDirectory(*Dir,true);FFileHelper::SaveStringToFile(Result,*(Dir/TEXT("native-checks.txt")));UE_LOG(LogTemp,Display,TEXT("SwordReachContinuity %s"),*Result);
}));
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FHolsterReachContinuity,"Prophecy.SwordHolster.ReachContinuity",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FHolsterReachContinuity::RunTest(const FString&)
{bool Passed;AddInfo(CheckReachContinuity(Passed));TestTrue(TEXT("Destination continuity across deadline/refit slots, convergence and unchanged solve cadence"),Passed);return Passed;}
