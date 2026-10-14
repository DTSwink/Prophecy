IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSwordReturnPoleContinuity,"Prophecy.SwordHolster.ReturnPoleContinuity",
 EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FSwordReturnPoleContinuity::RunTest(const FString&)
{
 // Generate continuous geometric turns, then recover them only from the
 // vectors atan2 sees. Cross both seams repeatedly in moving root frames.
 for(double Sign:{-1.,1.})for(double Heading:{0.,1.7,-2.4}){
  double Goal=0,BlendAngle=0;
  for(int Tick=0;Tick<=720;++Tick){
   const double Expected=Sign*Tick*.02,ExpectedBlend=-Expected*.7;
   const FQuat Root(FVector(.2,.3,.9).GetSafeNormal(),Heading+Tick*.003);
   const FVector D=Root.RotateVector(FVector::ForwardVector),Initial=Root.RotateVector(FVector::RightVector);
   const FVector Wanted=FQuat(D,Expected).RotateVector(Initial);
   Goal=ContinueBendAngle(BendAngle(Initial,Wanted,D),Goal);
   BlendAngle=ContinueBendAngle(BendAngle(Initial,FQuat(D,ExpectedBlend).RotateVector(Initial),D),BlendAngle);
   TestTrue(TEXT("Goal keeps its continuous turn across both signed-angle seams"),FMath::Abs(Goal-Expected)<1.e-10);
   TestTrue(TEXT("FK/IK blend independently keeps its continuous turn"),FMath::Abs(BlendAngle-ExpectedBlend)<1.e-10);
   for(double Weight:{0.,.23,.5,1.})TestTrue(TEXT("Fractional turn follows geometric oracle, including root motion"),
    FQuat(D,Goal*Weight).RotateVector(Initial).Equals(FQuat(D,Expected*Weight).RotateVector(Initial),1.e-9));
  }
 }
 // Recorded first D: the moving reference crosses the same seam as the
 // target, so referencing it afresh changed +181.16 into -176.25 degrees.
 double Goal=FMath::DegreesToRadians(177.93);
 for(const FVector2D Sample:{FVector2D(-178.84,181.16),FVector2D(-176.25,183.75),FVector2D(-174.13,185.87)}){
  Goal=ContinueBendAngle(FMath::DegreesToRadians(Sample.X),Goal);
  TestTrue(TEXT("Recorded elbow-pop sequence keeps the same turn"),FMath::Abs(FMath::RadiansToDegrees(Goal)-Sample.Y)<1.e-8);
 }
 // Ordinary non-wrapping interpolation is unchanged; new return state starts
 // fresh, rather than inheriting a previous draw's accumulated angle.
 for(double Value:{-.9,-.1,0.,.1,.9})TestEqual(TEXT("No seam means no change"),ContinueBendAngle(Value,0),Value);
 FArmIKReturn State;State.GoalAngle=8;State.BlendAngle=-9;State=FArmIKReturn();
 TestTrue(TEXT("New return resets both angle histories"),State.GoalAngle==0&&State.BlendAngle==0&&!State.Anchored);
 return true;
}
