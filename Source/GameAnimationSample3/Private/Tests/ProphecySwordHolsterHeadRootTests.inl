IMPLEMENT_SIMPLE_AUTOMATION_TEST(FHolsterHeadRoot,"Prophecy.SwordHolster.HeadRootFrame",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FHolsterHeadRoot::RunTest(const FString&)
{
 FString Text;if(!FFileHelper::LoadFileToString(Text,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/SwordLabSync20261011/channels.json")))){AddError(TEXT("Missing recorded head fixture"));return false;}
 TSharedPtr<FJsonObject> Root;if(!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Root))return false;
 FActive Seed;for(const auto& N:Root->GetArrayField(TEXT("names")))Seed.Names.Add(FName(*N->AsString()));for(const auto& P:Root->GetArrayField(TEXT("parents")))Seed.Parents.Add(int(P->AsNumber()));
 for(int K=0;K<5;++K)Seed.Spine[K]=Seed.Names.IndexOfByKey(FName(*FString::Printf(TEXT("spine_0%d"),K+1)));
 const TCHAR* Neck[]={TEXT("neck_01"),TEXT("neck_02"),TEXT("head")};for(int K=0;K<3;++K)Seed.Neck[K]=Seed.Names.IndexOfByKey(Neck[K]);
 const auto F=Root->GetArrayField(TEXT("rows"))[0]->AsObject()->GetArrayField(TEXT("frames"))[0]->AsObject();
 const auto Base=JsonPoses(F->GetArrayField(TEXT("base"))),Pose=JsonPoses(F->GetArrayField(TEXT("pose")));const FVector Mouth=JsonVector(F->GetArrayField(TEXT("target")));
 Seed.Base=Base;Seed.Head=Base[Seed.Neck[2]].GetRotation();Seed.Profile.HeadInSpeed=Seed.Profile.HeadOutSpeed=100;Seed.Profile.HeadInMaxGaze=Seed.Profile.HeadOutMaxGaze=100;
 Seed.Profile.HeadInExponent=Seed.Profile.HeadOutExponent=2;Seed.Profile.HeadMaxTilt=45;Seed.Status.ReachTicks=60;
 double MaxAngle=0,MaxPosition=0,MaxRate=0;int CompletionMismatch=0;
 for(double Spin:{-2.,2.,7.}){FActive Fixed=Seed,Turning=Seed;
  for(int Tick=1;Tick<=720;++Tick){const FQuat Heading(FVector::UpVector,FMath::DegreesToRadians(Spin*Tick));const FTransform Frame(Heading,FVector(Tick*2,-Tick,0));
   Fixed.Base=Base;Fixed.Pose=Pose;Fixed.Mouth=Mouth;Turning.Base=Base;Turning.Pose=Pose;
   for(auto& T:Turning.Base)T=T*Frame;for(auto& T:Turning.Pose)T=T*Frame;Turning.Mouth=Frame.TransformPosition(Mouth);SetRootFrame(Turning,Frame);
   if(Tick==1)Turning.Head=(Heading*Fixed.Head).GetNormalized();
   Fixed.Status.Tick=Turning.Status.Tick=Tick;Fixed.Sliding=Turning.Sliding=Tick>=90;Fixed.Status.Insertion=Turning.Status.Insertion=Fixed.Status.SlideProgress=Turning.Status.SlideProgress=Tick>=90?1:0;
   HeadStep(Fixed);HeadStep(Turning);CompletionMismatch+=Fixed.HeadDone!=Turning.HeadDone;
   for(int J:Fixed.Neck){const FTransform Expected=Fixed.Pose[J]*Frame;MaxAngle=FMath::Max(MaxAngle,Angle(Expected.GetRotation(),Turning.Pose[J].GetRotation()));MaxPosition=FMath::Max(MaxPosition,FVector::Distance(Expected.GetLocation(),Turning.Pose[J].GetLocation()));}
   MaxRate=FMath::Max(MaxRate,FMath::Abs(Fixed.Status.HeadStep-Turning.Status.HeadStep));
  }
  TestTrue(TEXT("Head return completes despite faster root turn"),Fixed.HeadDone&&Turning.HeadDone);
 }
 TestTrue(TEXT("Root turning cannot change the head/neck local path"),MaxAngle<.00001&&MaxPosition<.00001);
 TestTrue(TEXT("Head speed is measured in root frame"),MaxRate<.00001);TestEqual(TEXT("Root heading cannot change completion timing"),CompletionMismatch,0);
 // Compensation affects the pelvis rotation, while root motion carries the
 // whole mounted assembly identically at every stabilization/return weight.
 double MountError=0;
 for(double Weight:{0.,.48,1.}){FActive A;A.Stabilizing=true;A.Geometry.GripStabilization=Weight;A.Geometry.HolsterReturnDuration=.25;A.Sliding=true;A.SlideStart=0;A.Status.SlideTicks=20;
  A.NeutralMount=FTransform(FQuat(FVector::ForwardVector,.4),FVector(8,-16,10));A.StableHolster=FQuat(FVector::RightVector,.3);
  for(int Tick=1;Tick<=40;++Tick){A.Status.Tick=Tick;const FTransform Pelvis(FQuat(FVector::ForwardVector,.15*FMath::Sin(Tick*.3)),FVector(1,2,90));
   const FTransform RootFrame(FQuat(FVector::UpVector,Tick*.12),FVector(Tick,0,0));FActive B=A;SetRootFrame(B,RootFrame);
   const FTransform Expected=MountedHolster(A,Pelvis)*RootFrame,Got=MountedHolster(B,Pelvis*RootFrame);
   MountError=FMath::Max3(MountError,Angle(Expected.GetRotation(),Got.GetRotation()),FVector::Distance(Expected.GetLocation(),Got.GetLocation()));
  }
 }
 TestTrue(TEXT("Holster stabilization and return are root-local"),MountError<.00001);
 AddInfo(FString::Printf(TEXT("root_covariance_deg=%.9g cm=%.9g step_deg=%.9g completion_mismatch=%d"),MaxAngle,MaxPosition,MaxRate,CompletionMismatch));return !HasAnyErrors();
}
