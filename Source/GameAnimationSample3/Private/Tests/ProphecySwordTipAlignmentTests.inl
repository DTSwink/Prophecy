IMPLEMENT_SIMPLE_AUTOMATION_TEST(FHolsterTipAlignmentTest,"Prophecy.SwordHolster.TipAlignment",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FHolsterTipAlignmentTest::RunTest(const FString&)
{
 FString Text;TSharedPtr<FJsonObject> Root;
 if(!FFileHelper::LoadFileToString(Text,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/TipAlignPort20261013/tip-oracle.json")))||!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Root)){AddError(TEXT("Run Tools/SwordHolster/export_tip_alignment.cjs"));return false;}
 double Position=0,Rotation=0;
 auto Transform=[](const TSharedPtr<FJsonObject>& J){auto T=JsonPose(J);T.SetScale3D(JsonVector(J->GetArrayField(TEXT("s"))));return T;};
 for(const auto& V:Root->GetArrayField(TEXT("rows"))){const auto R=V->AsObject();FProphecySwordTipAlignment Path;
  Path.Begin(Transform(R->GetObjectField(TEXT("holster"))),Transform(R->GetObjectField(TEXT("full"))),Transform(R->GetObjectField(TEXT("blade"))),
   JsonVector(R->GetArrayField(TEXT("tip"))),JsonVector(R->GetArrayField(TEXT("base"))),JsonVector(R->GetArrayField(TEXT("mouth"))),JsonVector(R->GetArrayField(TEXT("hand"))),
   R->GetNumberField(TEXT("scale")),R->GetNumberField(TEXT("tick")),R->GetNumberField(TEXT("tolerance")),R->GetNumberField(TEXT("reach")),R->GetNumberField(TEXT("rotation")));
  TestEqual(TEXT("Same alignment tick count as lab"),Path.Ticks,int(R->GetNumberField(TEXT("ticks"))));
  for(const auto& SV:R->GetArrayField(TEXT("samples"))){const auto F=SV->AsObject();FVector P;FQuat Q;
   Path.Sample(JsonPose(F->GetObjectField(TEXT("holster"))),F->GetNumberField(TEXT("tick")),P,Q);
   Position=FMath::Max(Position,FVector::Distance(P,JsonVector(F->GetArrayField(TEXT("tip")))));
   Rotation=FMath::Max(Rotation,Angle(Q,JsonQuat(F->GetArrayField(TEXT("q")))));
  }
 }
 TestTrue(TEXT("Lab tip path cm"),Position<1.e-8);TestTrue(TEXT("Lab rotation degrees"),Rotation<.0001);
 // Active stabilization has zero entry jump, follows pelvis translation, and
 // returns exactly to the local mount on the authored clock.
 for(double Weight:{0.,.5,1.})for(double Duration:{0.,.25,2.}){
  FActive S;S.Stabilizing=true;S.Geometry.GripStabilization=Weight;S.Geometry.HolsterReturnDuration=Duration;
  S.NeutralMount=FTransform(FQuat(FVector(1,2,3).GetSafeNormal(),.7),FVector(3,9,-10));
  FTransform Parent(FQuat(FVector::UpVector,.3),FVector(100,200,300));S.StableHolster=(S.NeutralMount*Parent).GetRotation();
  TestTrue(TEXT("Stabilization capture has no jump"),MountedHolster(S,Parent).Equals(S.NeutralMount*Parent,1.e-8));
  S.Sliding=true;S.SlideStart=10;S.Status.SlideTicks=20;S.Status.Tick=25;
  Parent.SetRotation(FQuat(FVector::UpVector,1.2));Parent.AddToTranslation(FVector(10,20,30));
  TestTrue(TEXT("Mesh pivot follows parent"),MountedHolster(S,Parent).GetLocation().Equals((S.NeutralMount*Parent).GetLocation(),1.e-8));
  if(Weight==1)TestTrue(TEXT("Full stabilization holds world rotation"),Angle(MountedHolster(S,Parent).GetRotation(),S.StableHolster)<1.e-5);
  S.Status.Tick=31+FMath::CeilToInt(Duration*60);
  TestTrue(TEXT("Return reaches exact neutral mount"),MountedHolster(S,Parent).Equals(S.NeutralMount*Parent,1.e-8));
 }
 // The equipment target must be independent of the solved arm, including
 // unreachable poses. Capture preserves both world transforms at transfer.
 for(double Scale:{.2,.8,1.}){
  FActive S;S.Geometry.Valid=true;S.Status.Aligning=true;S.Sheathe=true;
  S.Geometry.AssetScale=FVector(.8,.9,1.3);S.Geometry.TipLocal=FVector(0,0,70);
  const FTransform Hand(FQuat(FVector(1,2,3).GetSafeNormal(),.7),FVector(30,-40,150));
  const FTransform Blade(FQuat(FVector(2,1,3).GetSafeNormal(),.5),FVector(20,-30,140),S.Geometry.AssetScale*FVector(1,1,Scale));
  CaptureGrip(S,Blade,Hand,Scale);
  TestTrue(TEXT("Captured grip preserves world blade"),(GripAt(S,Scale)*Hand).Equals(Blade,1.e-8));
  S.HolsterFrame=FTransform(FQuat(FVector::UpVector,.9),FVector(5,10,95));
  S.Full=Blade;S.Mouth=Blade.TransformPosition(S.Geometry.TipLocal)+FVector(8,4,-9);
  S.TipAlignment.Begin(S.HolsterFrame,S.Full,Blade,S.Geometry.TipLocal,S.Geometry.BaseLocal,S.Mouth,Hand.GetLocation(),Scale,10,15,230,600);
  S.Status.Tick=10;double GotScale;const FTransform Capture=SwordHandTarget(S,GotScale);
  TestTrue(TEXT("Captured hand target has no jump"),Capture.Equals(Hand,1.e-8));
  for(int Tick=10;Tick<=10+S.TipAlignment.Ticks;++Tick){
   S.Status.Tick=Tick;const FTransform Expected=SwordHandTarget(S,GotScale);
   S.Pose.Init(FTransform(FQuat::Identity,FVector(10000,-20000,30000)),3);
   TestTrue(TEXT("Unreachable hand cannot move equipment"),SwordHandTarget(S,GotScale).Equals(Expected,1.e-8));
   FVector Tip;FQuat SampleRotation;S.TipAlignment.Sample(S.HolsterFrame,Tick,Tip,SampleRotation);
   const FTransform Sword=GripAt(S,GotScale)*Expected;
   TestTrue(TEXT("Actual equipment follows holster-local tip path"),Sword.TransformPosition(S.Geometry.TipLocal).Equals(Tip,1.e-8));
   if(Tick==10+S.TipAlignment.Ticks)TestTrue(TEXT("Unreachable arm cannot block tip arrival"),Sword.TransformPosition(S.Geometry.TipLocal).Equals(S.HolsterFrame.TransformPosition(S.TipAlignment.TargetTip),1.e-8));
  }
 }
 AddInfo(FString::Printf(TEXT("tip_cm=%.12g rotation_deg=%.12g"),Position,Rotation));return !HasAnyErrors();
}
