// Identical recorded inputs on both sides; no physics or editor pivot assumptions.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FHolsterAcceptedMotion,"Prophecy.SwordHolster.AcceptedMotion",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FHolsterAcceptedMotion::RunTest(const FString&)
{
 const FString Dir=FPaths::ProjectSavedDir()/TEXT("Diagnostics/SwordAcceptedPort20261013");FString Text;TSharedPtr<FJsonObject> Root;
 if(!FFileHelper::LoadFileToString(Text,*(Dir/TEXT("motion-oracle.json")))||!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Root)){AddError(TEXT("Run export_accepted.cjs"));return false;}
 auto Transform=[](const TSharedPtr<FJsonObject>& J){auto T=JsonPose(J);T.SetScale3D(JsonVector(J->GetArrayField(TEXT("s"))));return T;};
 FString Trace=TEXT("motion,sheathe,inertia,tick,bone,position_cm,rotation_deg\n"),Summary;
 for(const auto& V:Root->GetArrayField(TEXT("rows"))){const auto Row=V->AsObject();const auto& Frames=Row->GetArrayField(TEXT("frames"));
  FActive S=AuthoredFixture(Root,Row->GetBoolField(TEXT("sheathe")),JsonPoses(Row->GetArrayField(TEXT("entry"))));
  if(!Row->GetBoolField(TEXT("inertia")))S.Profile.EntryInertia=0;S.Geometry.LeewayPhase=S.Profile.LeewayPhase;S.Geometry.TipTolerance=S.Profile.TipTolerance;S.Geometry.ShrinkDuration=S.Profile.ShrinkDuration;
  S.Geometry.AttachedSpeed=S.Profile.AttachedSpeed;S.Geometry.AttachedRotation=S.Profile.AttachedRotation;
  auto Feed=[&](int T){const auto F=Frames[T]->AsObject();S.Base=JsonPoses(F->GetArrayField(TEXT("base")));S.Full=Transform(F->GetObjectField(TEXT("full")));S.HolsterFrame=Transform(F->GetObjectField(TEXT("holster")));RefreshGeometry(S);};
  Feed(0);PlanReach(S);PreparePole(S);PrepareEntryInertia(S,JsonPoses(Row->GetArrayField(TEXT("prior"))));S.Pose=S.Before=S.Entry=S.LastBase=S.LastBody=S.Base;
  S.HeadReference=S.NeutralHead;S.HeadDelta=Log(S.Head*S.HeadReference.Inverse());S.HeadBaseDelta=S.HeadDelta;S.HeadFrom=S.HeadDelta;S.HeadInitialized=true;
  double MaxP=0,MaxQ=0;int End=-1;
  for(int T=1;T<Frames.Num();++T){Feed(T);Advance(S,1);
   if(!S.Sliding&&!S.Status.Aligning){
    const double Scale=S.Sheathe?ReachScale(S):S.Geometry.Retained;const FTransform Blade=GripAt(S,Scale)*S.Pose[S.Arm[2]];
    const bool Ready=S.Sheathe?SheatheReady(S,Blade):S.Status.ReachDone&&S.Status.HandError<=2&&Angle(S.Pose[S.Arm[2]].GetRotation(),S.Seat.GetRotation())<=5;
    if(Ready){S.EntryScale=Scale;if(S.Sheathe)CaptureArm(S,S.Pose,S.HeldArm);
     if(S.Sheathe&&S.Geometry.LeewayPhase){S.TipAlignment.Begin(S.HolsterFrame,S.Full,Blade,S.Geometry.TipLocal,S.Geometry.BaseLocal,S.Mouth,S.Pose[S.Arm[2]].GetLocation(),Scale,T,S.Profile.RotationTolerance,S.Geometry.AttachedSpeed,S.Geometry.AttachedRotation);S.Status.Aligning=true;}
     else{S.EntryRotation=(S.Full.GetRotation().Inverse()*Blade.GetRotation()).GetNormalized();S.EntryTipError=S.Full.GetRotation().UnrotateVector(Blade.TransformPosition(S.Geometry.TipLocal)-S.Mouth);StartSlide(S);}
    }
   }
   const auto Expected=JsonPoses(Frames[T]->AsObject()->GetArrayField(TEXT("pose")));
   for(int J:S.Upper){const double P=FVector::Distance(S.Pose[J].GetLocation(),Expected[J].GetLocation()),Q=Angle(S.Pose[J].GetRotation(),Expected[J].GetRotation());MaxP=FMath::Max(MaxP,P);MaxQ=FMath::Max(MaxQ,Q);
    Trace+=FString::Printf(TEXT("%s,%d,%d,%d,%s,%.12g,%.12g\n"),*Row->GetStringField(TEXT("motion")),S.Sheathe,Row->GetBoolField(TEXT("inertia")),T,*S.Names[J].ToString(),P,Q);}
   if(S.Status.Finished&&End<0)End=T;
  }
  const FString Label=Row->GetStringField(TEXT("motion"))+(S.Sheathe?TEXT(" S"):TEXT(" D"))+(Row->GetBoolField(TEXT("inertia"))?TEXT(" inertia"):TEXT(" no-inertia"));
  Summary+=FString::Printf(TEXT("%s reach=%d/%d slide=%d/%d duration=%d/%d finish=%d/%d max_cm=%.12g max_deg=%.12g\n"),*Label,S.Status.ReachTicks,int(Row->GetNumberField(TEXT("reachTicks"))),S.SlideStart,int(Row->GetNumberField(TEXT("slideStart"))),S.Status.SlideTicks,int(Row->GetNumberField(TEXT("slideTicks"))),End,int(Row->GetNumberField(TEXT("finish"))),MaxP,MaxQ);
  TestEqual(*(Label+TEXT(" reach timing")),S.Status.ReachTicks,int(Row->GetNumberField(TEXT("reachTicks"))));TestEqual(*(Label+TEXT(" slide admission")),S.SlideStart,int(Row->GetNumberField(TEXT("slideStart"))));
  TestTrue(*(Label+TEXT(" trajectory position")),MaxP<.001);TestTrue(*(Label+TEXT(" trajectory rotation")),MaxQ<.001);
 }
 FFileHelper::SaveStringToFile(Trace,*(Dir/TEXT("motion-difference.csv")));FFileHelper::SaveStringToFile(Summary,*(Dir/TEXT("motion-result.txt")));AddInfo(Summary);return !HasAnyErrors();
}
