IMPLEMENT_SIMPLE_AUTOMATION_TEST(FHolsterHeldArmRoll,"Prophecy.SwordHolster.HeldArmRoll",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FHolsterHeldArmRoll::RunTest(const FString&)
{
 auto Run=[&](bool Preserve){
  FActive S;S.Arm[0]=0;S.Arm[1]=1;S.Arm[2]=2;S.Spine[4]=3;S.Pose.Init(FTransform::Identity,4);
  S.Pose[1].SetLocation(FVector(30,.16,0));S.Pose[2].SetLocation(FVector(60,0,0));
  S.Sliding=true;S.Profile.Body[1].SwordPole=true;S.Profile.Body[1].Pole[0]=S.Profile.Body[1].Pole[1]=76;S.Authored.PoleAngle=76;
  double MaxStep=0;
  for(int Tick=0;Tick<120;++Tick){
   FTransform Seed[3];for(int K=0;K<3;++K)Seed[K]=S.Pose[K];
   const FTransform Target(FQuat::Identity,FVector(65,2*FMath::Sin(Tick*.15),2*FMath::Cos(Tick*.15)));
   Solve(S,S.Pose,Target);ApplyPole(S);const TArray<FTransform> Solved=S.Pose;
   if(Preserve)PreserveArmRoll(S,Seed);
   for(int K=0;K<2;++K){MaxStep=FMath::Max(MaxStep,Angle(Seed[K].GetRotation(),S.Pose[K].GetRotation()));
    TestTrue(TEXT("Roll transport preserves elbow and wrist targets"),S.Pose[K+1].GetLocation().Equals(Solved[K+1].GetLocation(),1.e-9));}
   TestTrue(TEXT("Roll transport preserves hand orientation"),Angle(S.Pose[2].GetRotation(),Target.GetRotation())<1.e-6);
  }
  return MaxStep;
 };
 const double Before=Run(false),After=Run(true);
 TestTrue(TEXT("Fixture exposes straight-arm axial flips"),Before>90);
 TestTrue(TEXT("Moving straight arm retains segment roll"),After<5);
 AddInfo(FString::Printf(TEXT("max_segment_step_deg before=%.9f after=%.9f"),Before,After));return !HasAnyErrors();
}
