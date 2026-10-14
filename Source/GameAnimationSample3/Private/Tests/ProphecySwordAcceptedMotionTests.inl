// Identical recorded inputs on both sides; no physics or editor pivot assumptions.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FHolsterAcceptedMotion,"Prophecy.SwordHolster.AcceptedMotion",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FHolsterAcceptedMotion::RunTest(const FString&)
{
 const FString Dir=FPaths::ProjectSavedDir()/TEXT("Diagnostics/SwordHolsterParity");FString Text;TSharedPtr<FJsonObject> Root;
 if(!FFileHelper::LoadFileToString(Text,*(Dir/TEXT("motion-oracle.json")))||!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Root)){AddError(TEXT("Run export_accepted.cjs"));return false;}
 auto Transform=[](const TSharedPtr<FJsonObject>& J){auto T=JsonPose(J);T.SetScale3D(JsonVector(J->GetArrayField(TEXT("s"))));return T;};
 FString Trace=TEXT("motion,sheathe,inertia,tick,bone,position_cm,rotation_deg\n"),Summary;
 // Exercise the actual PHAT/NN list too: root omitted, neck_02 after head.
 for(bool NativeLayout:{false,true}){
  auto Layout=MakeShared<FJsonObject>(*Root);TArray<int32> Map;TArray<TSharedPtr<FJsonValue>> Names,Parents;
  const auto& FullNames=Root->GetArrayField(TEXT("names"));const auto& FullParents=Root->GetArrayField(TEXT("parents"));
  if(NativeLayout){for(const TCHAR* Name:{TEXT("pelvis"),TEXT("spine_01"),TEXT("spine_02"),TEXT("spine_03"),TEXT("spine_04"),TEXT("spine_05"),TEXT("clavicle_l"),TEXT("upperarm_l"),TEXT("lowerarm_l"),TEXT("hand_l"),TEXT("clavicle_r"),TEXT("upperarm_r"),TEXT("lowerarm_r"),TEXT("hand_r"),TEXT("neck_01"),TEXT("head"),TEXT("thigh_l"),TEXT("calf_l"),TEXT("foot_l"),TEXT("thigh_r"),TEXT("calf_r"),TEXT("foot_r"),TEXT("neck_02"),TEXT("ball_l"),TEXT("ball_r")})Map.Add(FullNames.IndexOfByPredicate([&](const auto& N){return N->AsString()==Name;}));}
  else for(int J=0;J<FullNames.Num();++J)Map.Add(J);
  for(int J:Map){check(J!=INDEX_NONE);Names.Add(FullNames[J]);int P=int(FullParents[J]->AsNumber());while(P>=0&&!Map.Contains(P))P=int(FullParents[P]->AsNumber());Parents.Add(MakeShared<FJsonValueNumber>(Map.IndexOfByKey(P)));}
  Layout->SetArrayField(TEXT("names"),Names);Layout->SetArrayField(TEXT("parents"),Parents);
  auto Poses=[&](const TArray<TSharedPtr<FJsonValue>>& Json){const auto Full=JsonPoses(Json);TArray<FTransform> Out;for(int J:Map)Out.Add(Full[J]);return Out;};
  const int RootIndex=FullNames.IndexOfByPredicate([](const auto& N){return N->AsString()==TEXT("root");});
 for(const auto& V:Root->GetArrayField(TEXT("rows"))){const auto Row=V->AsObject();const auto& Frames=Row->GetArrayField(TEXT("frames"));
  FActive S=AuthoredFixture(Layout,Row->GetBoolField(TEXT("sheathe")),Poses(Row->GetArrayField(TEXT("entry"))));
  const TSharedPtr<FJsonObject>* Variant;if(Row->TryGetObjectField(TEXT("variant"),Variant)){auto& R=S.Profile.Return[S.Sheathe];R.Spring=(*Variant)->GetBoolField(TEXT("spring"));R.World=(*Variant)->GetBoolField(TEXT("world"));R.StartFraction=(*Variant)->GetNumberField(TEXT("startFraction"));R.HandRotationFKAlpha=(*Variant)->GetNumberField(TEXT("handAlpha"));}
  if(!Row->GetBoolField(TEXT("inertia")))S.Profile.EntryInertia=0;S.Geometry.LeewayPhase=S.Profile.LeewayPhase;S.Geometry.TipTolerance=S.Profile.TipTolerance;S.Geometry.ShrinkDuration=S.Profile.ShrinkDuration;
  S.Geometry.AttachedSpeed=S.Profile.AttachedSpeed;S.Geometry.AttachedRotation=S.Profile.AttachedRotation;
  auto Feed=[&](int T){const auto F=Frames[T]->AsObject();S.Base=Poses(F->GetArrayField(TEXT("base")));SetRootFrame(S,JsonPoses(F->GetArrayField(TEXT("base")))[RootIndex]);S.Full=Transform(F->GetObjectField(TEXT("full")));S.HolsterFrame=Transform(F->GetObjectField(TEXT("holster")));RefreshGeometry(S);};
  Feed(0);S.PreviousRootFrame=S.RootFrame;PlanReach(S);PreparePole(S);PrepareEntryInertia(S,Poses(Row->GetArrayField(TEXT("prior"))));S.Pose=S.Before=S.Entry=S.LastBase=S.LastBody=S.Base;
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
   const auto Expected=Poses(Frames[T]->AsObject()->GetArrayField(TEXT("pose")));
   for(int J:S.Upper){const double P=FVector::Distance(S.Pose[J].GetLocation(),Expected[J].GetLocation()),Q=Angle(S.Pose[J].GetRotation(),Expected[J].GetRotation());MaxP=FMath::Max(MaxP,P);MaxQ=FMath::Max(MaxQ,Q);
    Trace+=FString::Printf(TEXT("%s,%d,%d,%d,%s,%.12g,%.12g\n"),*Row->GetStringField(TEXT("motion")),S.Sheathe,Row->GetBoolField(TEXT("inertia")),T,*S.Names[J].ToString(),P,Q);}
   if(S.Status.Finished&&End<0)End=T;
  }
  const FString Label=(NativeLayout?FString(TEXT("live-layout ")):FString(TEXT("lab-layout ")))+Row->GetStringField(TEXT("motion"))+(S.Sheathe?TEXT(" S"):TEXT(" D"))+(Row->GetBoolField(TEXT("inertia"))?TEXT(" inertia"):TEXT(" no-inertia"));
  Summary+=FString::Printf(TEXT("%s reach=%d/%d slide=%d/%d duration=%d/%d finish=%d/%d max_cm=%.12g max_deg=%.12g\n"),*Label,S.Status.ReachTicks,int(Row->GetNumberField(TEXT("reachTicks"))),S.SlideStart,int(Row->GetNumberField(TEXT("slideStart"))),S.Status.SlideTicks,int(Row->GetNumberField(TEXT("slideTicks"))),End,int(Row->GetNumberField(TEXT("finish"))),MaxP,MaxQ);
  TestEqual(*(Label+TEXT(" reach timing")),S.Status.ReachTicks,int(Row->GetNumberField(TEXT("reachTicks"))));TestEqual(*(Label+TEXT(" slide admission")),S.SlideStart,int(Row->GetNumberField(TEXT("slideStart"))));
  TestEqual(*(Label+TEXT(" slide duration")),S.Status.SlideTicks,int(Row->GetNumberField(TEXT("slideTicks"))));
  TestEqual(*(Label+TEXT(" completion")),End,int(Row->GetNumberField(TEXT("finish"))));
  TestTrue(*(Label+TEXT(" trajectory position")),MaxP<.001);TestTrue(*(Label+TEXT(" trajectory rotation")),MaxQ<.001);
 }}
 FFileHelper::SaveStringToFile(Trace,*(Dir/TEXT("motion-difference.csv")));FFileHelper::SaveStringToFile(Summary,*(Dir/TEXT("motion-result.txt")));AddInfo(Summary);return !HasAnyErrors();
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FHolsterReturnBlend,"Prophecy.SwordHolster.ReturnBlend",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FHolsterReturnBlend::RunTest(const FString&)
{
 FString Text;TSharedPtr<FJsonObject> Root;
 if(!FFileHelper::LoadFileToString(Text,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/SwordHolsterParity/motion-oracle.json")))||!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Root)){AddError(TEXT("Run export_accepted.cjs"));return false;}
 for(int Action=0;Action<2;++Action){
  const auto Row=Root->GetArrayField(TEXT("rows"))[Action*2]->AsObject();const auto& Frames=Row->GetArrayField(TEXT("frames"));
  const int Release=int(Row->GetNumberField(TEXT("slideStart"))+Row->GetNumberField(TEXT("slideTicks")));
  auto At=Frames[Release]->AsObject(),Before=Frames[Release-1]->AsObject();
  FActive S=AuthoredFixture(Root,Action!=0,JsonPoses(At->GetArrayField(TEXT("base"))));
  S.Pose=JsonPoses(At->GetArrayField(TEXT("pose")));S.LastBody=JsonPoses(Before->GetArrayField(TEXT("pose")));S.LastBase=JsonPoses(Before->GetArrayField(TEXT("base")));
  S.Sliding=true;S.SlideStart=0;S.Status.SlideTicks=1;S.Status.Tick=1;BeginReturn(S);
  S.Profile.ReturnBlend[0]={.5,.8};S.Profile.ReturnBlend[1]={.6,.9};
  for(double Fraction:{.49,.5,.6,.65,.8,.9,1.}){
   FActive V=S;V.BodyElapsed=V.ReturnDuration*Fraction;
   const double Expected=Action?Clamp((Fraction-.6)/.3):Clamp((Fraction-.5)/.3);
   const double Alpha=ReturnBlendAlpha(V);TestTrue(TEXT("D/S ranges select independent linear weights on return completion"),FMath::Abs(Alpha-Expected)<1.e-12);
   BlendReturnToNN(V,Alpha);
   for(int J=0;J<V.Pose.Num();++J){
    if(!S.Upper.Contains(J)||Alpha==0)TestTrue(TEXT("No change outside upper body or before window"),V.Pose[J].Equals(S.Pose[J],1.e-8));
    else if(Alpha==1)TestTrue(TEXT("Window end exactly matches live NN"),V.Pose[J].Equals(S.Base[J],1.e-8));
    if(S.Upper.Contains(J)){const int P=S.Parents[J];const double Length=V.Pose[J].GetRelativeTransform(V.Pose[P]).GetLocation().Size();
     const double TargetLength=FMath::Lerp(S.Pose[J].GetRelativeTransform(S.Pose[P]).GetLocation().Size(),S.Base[J].GetRelativeTransform(S.Base[P]).GetLocation().Size(),Alpha);
     TestTrue(TEXT("Blending does not shorten bones"),FMath::Abs(Length-TargetLength)<1.e-7);}
   }
   FActive Moved=S;const FTransform Carrier(FQuat(FVector::UpVector,1.2),FVector(100,-200,15));
   for(auto* Poses:{&Moved.Pose,&Moved.Base})for(auto& T:*Poses)T=T*Carrier;
   BlendReturnToNN(Moved,Alpha);
   for(int J:S.Upper)TestTrue(TEXT("Root turns/translations carry the blend"),Moved.Pose[J].Equals(V.Pose[J]*Carrier,1.e-6));
  }
  FActive End=S;End.BodyElapsed=End.ReturnDuration*.91;Advance(End,1);
  TestTrue(TEXT("Ends on authored tick clock without waiting for an NN boundary"),End.Status.Finished);
  for(int J:End.Upper)TestTrue(TEXT("Last published upper pose equals live NN"),End.Pose[J].Equals(End.Base[J],1.e-8));
 }
 return !HasAnyErrors();
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FHolsterHandAxisRoot,"Prophecy.SwordHolster.HandAxisRootFrame",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FHolsterHandAxisRoot::RunTest(const FString&)
{
 double MaxError=0;
 for(double Speed:{-800.,800.})for(double Exponent:{1.,1.5}){
  FActive Fixed;Fixed.Sheathe=false;Fixed.Status.Returning=true;Fixed.ReturnDuration=1;Fixed.Names={TEXT("upperarm_r"),TEXT("lowerarm_r"),TEXT("hand_r")};
  for(int J=0;J<3;++J)Fixed.Arm[J]=J;Fixed.Pose.Init(FTransform::Identity,3);
  auto& R=Fixed.Profile.Return[0];R.Enabled=true;R.SwordPointSpeed=Speed;R.SwordPointExponent=Exponent;R.SwordPointCutoff=.4;
  const FQuat Start=Exp(FVector(.3,-.2,.1));Fixed.Pose[2].SetRotation(Start);FActive Turning=Fixed;
  HandAxisStep(Fixed,0);HandAxisStep(Turning,0);TestTrue(TEXT("Missing root bone cannot disable the hand turn"),Fixed.HandAxis.Active&&Turning.HandAxis.Active);
  for(int Tick=1;Tick<=65;++Tick){
   const FTransform Carrier(FQuat(FVector::UpVector,Tick*.07),FVector(Tick*3,Tick*-2,0));const FQuat Base=(Start*Exp(FVector(0,Tick*.002,0))).GetNormalized();
   Fixed.Status.Tick=Turning.Status.Tick=Tick;Fixed.Pose[2].SetRotation(Base);Turning.Pose[2].SetRotation((Carrier.GetRotation()*Base).GetNormalized());SetRootFrame(Turning,Carrier);
   HandAxisStep(Fixed,0);HandAxisStep(Turning,0);
   MaxError=FMath::Max(MaxError,Angle((Carrier.GetRotation()*Fixed.Pose[2].GetRotation()).GetNormalized(),Turning.Pose[2].GetRotation()));
   if(Tick==24){const FQuat Expected=(Start*Exp(FVector(FMath::DegreesToRadians(Speed)*.4/Exponent,0,0))).GetNormalized();TestTrue(TEXT("Signed local-X angular budget reaches the exact cutoff"),Angle(Fixed.Pose[2].GetRotation(),Expected)<.00001);}
  }
  TestFalse(TEXT("Completed hand turn retires"),Fixed.HandAxis.Active);
 }
 TestTrue(TEXT("Character motion carries the hand turn and continuation"),MaxError<.00001);AddInfo(FString::Printf(TEXT("root_covariance_deg=%.12g"),MaxError));return !HasAnyErrors();
}
