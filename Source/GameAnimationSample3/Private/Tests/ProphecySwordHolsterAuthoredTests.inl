// Latest lab oracle, separate from the frozen historical optimizer regression.
static FActive AuthoredFixture(const TSharedPtr<FJsonObject>& Root,bool Sheathe,const TArray<FTransform>& Entry)
{
 FActive S;FString Error;LoadProfile(FPaths::ProjectContentDir()/TEXT("locomotion/SwordHolsterProfile.json"),S.Profile,Error);S.Sheathe=Sheathe;
 for(const auto& N:Root->GetArrayField(TEXT("names")))S.Names.Add(FName(*N->AsString()));for(const auto& P:Root->GetArrayField(TEXT("parents")))S.Parents.Add(int(P->AsNumber()));
 auto Find=[&](const TCHAR* N){return S.Names.IndexOfByKey(FName(N));};S.Pelvis=Find(TEXT("pelvis"));S.Clav=Find(TEXT("clavicle_r"));for(int K=0;K<5;++K)S.Spine[K]=Find(*FString::Printf(TEXT("spine_0%d"),K+1));
 const TCHAR* Arm[]={TEXT("upperarm_r"),TEXT("lowerarm_r"),TEXT("hand_r")},*Neck[]={TEXT("neck_01"),TEXT("neck_02"),TEXT("head")};for(int K=0;K<3;++K){S.Arm[K]=Find(Arm[K]);S.Neck[K]=Find(Neck[K]);}
 S.Base=S.Pose=S.Before=S.Entry=S.LastBase=S.LastBody=Entry;PrepareUpperOrder(S);PrepareAuthored(S);S.Groups.Init(-1,S.Names.Num());
 for(int J:S.Upper){const FString N=S.Names[J].ToString();if(N.StartsWith(TEXT("spine_")))S.Groups[J]=0;else if(N.StartsWith(TEXT("clavicle_")))S.Groups[J]=1;else if(N.StartsWith(TEXT("upperarm_")))S.Groups[J]=2;else if(N.StartsWith(TEXT("lowerarm_")))S.Groups[J]=3;else for(int K=0;K<3;++K)if(J==S.Neck[K])S.Groups[J]=K+4;}
 if(!Sheathe)S.Groups[S.Arm[2]]=7;
 const auto Setup=Root->GetObjectField(TEXT("setup"));S.Geometry.Valid=true;S.Geometry.Grip=JsonPose(Setup->GetObjectField(TEXT("grip")));S.Geometry.AssetScale=JsonVector(Setup->GetArrayField(TEXT("assetScale")));S.Geometry.BaseLocal=JsonVector(Setup->GetArrayField(TEXT("baseBladeLocal")));S.Geometry.TipLocal=JsonVector(Setup->GetArrayField(TEXT("tip")));S.Geometry.Retained=1-S.Profile.Shrink/100;
 S.SlideLength=Setup->GetNumberField(TEXT("bladeLength"))*S.Geometry.Retained;const auto& B=S.Profile.Body[Sheathe];S.ReachSpeed=B.Reach;S.RotationSpeed=B.Rotation;S.SlideSpeed=B.Sliding;
 S.Status.SlideTicks=FMath::CeilToInt(S.SlideLength/S.SlideSpeed*60);S.Head=S.HeadStart=Entry[S.Neck[2]].GetRotation();NeutralFacing(S);return S;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FHolsterAuthored,"Prophecy.SwordHolster.AuthoredLab",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FHolsterAuthored::RunTest(const FString&)
{
 const FString Dir=FPaths::ProjectSavedDir()/TEXT("Diagnostics/SwordPort20261012");FString Text;
 if(!FFileHelper::LoadFileToString(Text,*(Dir/TEXT("authored-oracle.json")))){AddError(TEXT("Run Tools/SwordHolster/export_authored.cjs"));return false;}
 TSharedPtr<FJsonObject> Root;if(!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Root))return false;
 double BodyP=0,BodyQ=0,PoleP=0,PoleQ=0,PoleAngle=0,EntryP=0,EntryQ=0;
 auto Compare=[](TConstArrayView<FTransform> A,TConstArrayView<FTransform> B,double& P,double& Q){for(int J=0;J<A.Num();++J){P=FMath::Max(P,FVector::Dist(A[J].GetLocation(),B[J].GetLocation()));Q=FMath::Max(Q,Angle(A[J].GetRotation(),B[J].GetRotation()));}};
 for(const auto& V:Root->GetArrayField(TEXT("body"))){const auto F=V->AsObject();FActive S=AuthoredFixture(Root,F->GetBoolField(TEXT("sheathe")),JsonPoses(F->GetArrayField(TEXT("entry"))));S.Profile.Body[S.Sheathe].Compensation=F->GetNumberField(TEXT("compensation"));S.Base=JsonPoses(F->GetArrayField(TEXT("base")));FQuat Target[3];AuthoredTarget(S,F->GetNumberField(TEXT("insertion")),Target);BodyPose(S,S.Base,FVector::ZeroVector,S.Pose,false,Target);Compare(S.Pose,JsonPoses(F->GetArrayField(TEXT("expected"))),BodyP,BodyQ);
  // Moving the character frame must carry the entire authored pose. The
  // compensation knob cancels pelvis gait, not the character's own heading.
  const FTransform Move(FQuat(FVector::UpVector,1.7),FVector(1200,-700,100));TArray<FTransform> Expected=S.Pose;
  for(auto& Bone:S.Base)Bone=Bone*Move;for(auto& Bone:Expected)Bone=Bone*Move;S.Authored.Frame=Move.GetRotation();
  BodyPose(S,S.Base,FVector::ZeroVector,S.Pose,false,Target);Compare(S.Pose,Expected,BodyP,BodyQ);
 }
 for(const auto& V:Root->GetArrayField(TEXT("pole"))){const auto F=V->AsObject();const auto& Frames=F->GetArrayField(TEXT("frames"));FActive S=AuthoredFixture(Root,F->GetBoolField(TEXT("sheathe")),JsonPoses(Frames[0]->AsObject()->GetArrayField(TEXT("pose"))));S.Status.ReachTicks=30;PreparePole(S);
  for(int T=0;T<Frames.Num();++T){const auto Frame=Frames[T]->AsObject();S.Pose=JsonPoses(Frame->GetArrayField(TEXT("pose")));S.Sliding=T>30;S.Status.SlideProgress=Clamp((T-30)/50.);ApplyPole(S,T>0);Compare(S.Pose,JsonPoses(Frame->GetArrayField(TEXT("expected"))),PoleP,PoleQ);PoleAngle=FMath::Max(PoleAngle,FMath::Abs(S.Authored.PoleAngle-Frame->GetNumberField(TEXT("angle"))));}
 }
 for(const auto& V:Root->GetArrayField(TEXT("inertia"))){const auto F=V->AsObject();FActive S=AuthoredFixture(Root,F->GetBoolField(TEXT("sheathe")),JsonPoses(F->GetArrayField(TEXT("first"))));S.Status.ReachTicks=F->GetNumberField(TEXT("reachTicks"));SeedEntryInertia(S,JsonPoses(F->GetArrayField(TEXT("before"))),JsonPoses(F->GetArrayField(TEXT("next"))),1.e-4);
  for(const auto& SV:F->GetArrayField(TEXT("samples"))){const auto Sample=SV->AsObject();S.Status.Tick=Sample->GetNumberField(TEXT("tick"));S.Pose=JsonPoses(Sample->GetArrayField(TEXT("pose")));ApplyEntryInertia(S);Compare(S.Pose,JsonPoses(Sample->GetArrayField(TEXT("expected"))),EntryP,EntryQ);}
 }
 TestTrue(TEXT("Authored body position matches lab"),BodyP<.001);TestTrue(TEXT("Authored body rotation matches lab"),BodyQ<.001);
 TestTrue(TEXT("Moving/sword-relative pole position matches lab"),PoleP<.001);TestTrue(TEXT("Moving/sword-relative pole rotation matches lab"),PoleQ<.001);TestTrue(TEXT("Pole arrives at scheduled rate"),PoleAngle<1.e-7);
 TestTrue(TEXT("Entry inertia position matches lab"),EntryP<.001);TestTrue(TEXT("Entry inertia rotation matches lab"),EntryQ<.001);
 for(const auto& V:Root->GetArrayField(TEXT("straight"))){const auto C=V->AsObject();FActive S;S.Sheathe=false;S.Profile.Body[0].Authored=true;S.Arm[0]=1;S.Arm[1]=2;S.Arm[2]=3;S.Spine[4]=4;S.Pose=JsonPoses(C->GetArrayField(TEXT("input")));
  const auto Basis=C->GetObjectField(TEXT("basis"));S.Authored.PoleValid=true;S.Authored.PoleDirection=JsonVector(Basis->GetArrayField(TEXT("d")));S.Authored.PoleZero=JsonVector(Basis->GetArrayField(TEXT("zero")));S.Authored.PoleAngle=C->GetNumberField(TEXT("angle"));
  Solve(S,S.Pose,JsonPose(C->GetObjectField(TEXT("goal"))));ApplyPole(S,false);double P=0,Q=0;Compare(S.Pose,JsonPoses(C->GetArrayField(TEXT("expected"))),P,Q);TestTrue(TEXT("Straight-arm plane transport matches lab"),P<.001&&Q<.001);
  const auto Before=JsonPoses(C->GetArrayField(TEXT("before")));for(int J:S.Arm)TestTrue(TEXT("No slide-entry axial flip"),Angle(Before[J].GetRotation(),S.Pose[J].GetRotation())<15);
 }
 FString Result=FString::Printf(TEXT("body_cm=%.12g body_deg=%.12g pole_cm=%.12g pole_deg=%.12g pole_angle=%.12g entry_cm=%.12g entry_deg=%.12g\n"),BodyP,BodyQ,PoleP,PoleQ,PoleAngle,EntryP,EntryQ);
 FString Trace=TEXT("motion,sheathe,tick,reach_ticks,slide_tick,returning,hand_error,head_step,lab_pose_cm,lab_pose_deg,pole_angle_error,pole_zero_dot\n");
 FString Bones=TEXT("motion,sheathe,tick,bone,position_error,angle_error\n");
 FString Bench=TEXT("motion,sheathe,repeat,agents,planning_ms,frames,mean_ms,peak_ms\n");
 int MotionIndex=0;
 for(const auto& V:Root->GetArrayField(TEXT("motions"))){const auto M=V->AsObject();const auto& Frames=M->GetArrayField(TEXT("frames"));FActive S=AuthoredFixture(Root,M->GetBoolField(TEXT("sheathe")),JsonPoses(M->GetArrayField(TEXT("entry"))));
  auto Feed=[&](int T){const auto F=Frames[T]->AsObject();S.Base=JsonPoses(F->GetArrayField(TEXT("base")));const auto Full=F->GetObjectField(TEXT("full"));S.Full=JsonPose(Full);S.Full.SetScale3D(JsonVector(Full->GetArrayField(TEXT("s"))));RefreshGeometry(S);};
  Feed(0);const FActive Unplanned=S;PlanReach(S);PreparePole(S);
  // The primitive inertia oracle above checks exact seeds; here approximate the
  // live snapshot derivative with the recorded NN interval available at entry.
  const auto& IM=Root->GetArrayField(TEXT("inertia"))[MotionIndex++];
  const auto EntryBefore=JsonPoses(IM->AsObject()->GetArrayField(TEXT("before"))),EntryNext=JsonPoses(IM->AsObject()->GetArrayField(TEXT("next")));
  SeedEntryInertia(S,EntryBefore,EntryNext,1.e-4);
  double Total=0,Peak=0;int Count=0;
  for(int T=1;T<Frames.Num()&&!S.Status.Finished;++T){Feed(T);const double Start=FPlatformTime::Seconds();Advance(S,1);const double Us=(FPlatformTime::Seconds()-Start)*1.e6;Total+=Us;Peak=FMath::Max(Peak,Us);++Count;
   const auto Expected=JsonPoses(Frames[T]->AsObject()->GetArrayField(TEXT("pose")));double P=0,Q=0;Compare(S.Pose,Expected,P,Q);
   for(int J:S.Upper)Bones+=FString::Printf(TEXT("%s,%d,%d,%s,%.9g,%.9g\n"),*M->GetStringField(TEXT("motion")),S.Sheathe,T,*S.Names[J].ToString(),FVector::Dist(S.Pose[J].GetLocation(),Expected[J].GetLocation()),Angle(S.Pose[J].GetRotation(),Expected[J].GetRotation()));
   const auto Pole=Frames[T]->AsObject()->GetObjectField(TEXT("pole"));
   Trace+=FString::Printf(TEXT("%s,%d,%d,%d,%d,%d,%.9g,%.9g,%.9g,%.9g,%.9g,%.9g\n"),*M->GetStringField(TEXT("motion")),S.Sheathe,T,S.Status.ReachTicks,S.SlideStart,S.Status.Returning,S.Status.HandError,S.Status.HeadStep,P,Q,S.Authored.PoleAngle-Pole->GetNumberField(TEXT("angle")),FVector::DotProduct(S.Authored.PoleZero,JsonVector(Pole->GetArrayField(TEXT("zero")))));
   for(const auto& Bone:S.Pose)if(Bone.ContainsNaN()){AddError(TEXT("Nonfinite authored motion"));return false;}
   if(!S.Sliding){const FTransform Blade=GripAt(S,1-(1-S.Geometry.Retained)*S.Status.Progress)*S.Pose[S.Arm[2]];
    const bool Ready=S.Sheathe?SheatheReady(S,Blade):S.Status.ReachDone&&S.Status.HandError<=2;
    if(Ready){S.EntryScale=1-(1-S.Geometry.Retained)*S.Status.Progress;S.EntryRotation=(S.Full.GetRotation().Inverse()*Blade.GetRotation()).GetNormalized();S.EntryTipError=S.Full.GetRotation().UnrotateVector(Blade.TransformPosition(S.Geometry.TipLocal)-S.Mouth);StartSlide(S);}
   }
  }
  TestTrue(*FString::Printf(TEXT("%s %s completes recorded motion"),*M->GetStringField(TEXT("motion")),S.Sheathe?TEXT("S"):TEXT("D")),S.Status.Finished);
  Result+=FString::Printf(TEXT("%s %d reach=%d lab_reach=%.0f slide_start=%d lab_slide_start=%.0f slide_ticks=%d finish=%d mean_us=%.9g peak_us=%.9g\n"),*M->GetStringField(TEXT("motion")),S.Sheathe,S.Status.ReachTicks,M->GetNumberField(TEXT("reachTicks")),S.SlideStart,M->GetNumberField(TEXT("slideStart")),S.Status.SlideTicks,S.Status.Tick,Total/FMath::Max(Count,1),Peak);
  // Warm 100-agent math benchmark. JSON, logging and fixture copies are outside
  // the clock; includes pose copies, planning, guides, body/head and return.
  // Does not include live NN reads, publication, equipment, physics or rendering.
  TArray<TArray<FTransform>> Bases;TArray<FTransform> Fulls;
  for(const auto& F:Frames){Bases.Add(JsonPoses(F->AsObject()->GetArrayField(TEXT("base"))));const auto Full=F->AsObject()->GetObjectField(TEXT("full"));auto T=JsonPose(Full);T.SetScale3D(JsonVector(Full->GetArrayField(TEXT("s"))));Fulls.Add(T);}
  for(int Repeat=-1;Repeat<7;++Repeat){TArray<FActive> Crowd;for(int I=0;I<100;++I)Crowd.Add(Unplanned);
   const double Start=FPlatformTime::Seconds();for(auto& C:Crowd){PlanReach(C);PreparePole(C);SeedEntryInertia(C,EntryBefore,EntryNext,1.e-4);}const double Planning=(FPlatformTime::Seconds()-Start)*1000;
   double Ms=0,Max=0;int N=0;
   for(int T=1;T<Bases.Num();++T){bool Running=false;const double Begin=FPlatformTime::Seconds();
    for(auto& C:Crowd){if(C.Status.Finished)continue;Running=true;C.Base=Bases[T];C.Full=Fulls[T];Advance(C,1);
     if(!C.Sliding&&C.Status.ReachDone){const auto Blade=GripAt(C,C.Geometry.Retained)*C.Pose[C.Arm[2]];if(C.Sheathe?SheatheReady(C,Blade):C.Status.HandError<=2){C.EntryScale=C.Geometry.Retained;C.EntryRotation=(C.Full.GetRotation().Inverse()*Blade.GetRotation()).GetNormalized();C.EntryTipError=C.Full.GetRotation().UnrotateVector(Blade.TransformPosition(C.Geometry.TipLocal)-C.Mouth);StartSlide(C);}}
    }
    const double Elapsed=(FPlatformTime::Seconds()-Begin)*1000;if(!Running)break;Ms+=Elapsed;Max=FMath::Max(Max,Elapsed);++N;
   }
   for(const auto& C:Crowd)TestTrue(TEXT("Authored benchmark completes"),C.Status.Finished);
   if(Repeat>=0)Bench+=FString::Printf(TEXT("%s,%d,%d,100,%.9g,%d,%.9g,%.9g\n"),*M->GetStringField(TEXT("motion")),S.Sheathe,Repeat,Planning,N,Ms/FMath::Max(1,N),Max);
  }
 }
 FFileHelper::SaveStringToFile(Bench,*(Dir/TEXT("authored-benchmark.csv")));
 AddInfo(Result);FFileHelper::SaveStringToFile(Result,*(Dir/TEXT("authored-result.txt")));FFileHelper::SaveStringToFile(Trace,*(Dir/TEXT("authored-motion.csv")));FFileHelper::SaveStringToFile(Bones,*(Dir/TEXT("authored-bones.csv")));return !HasAnyErrors();
}
static FAutoConsoleCommand VerifyAuthoredCommand(TEXT("Prophecy.Sword.VerifyAuthored"),TEXT("Numerical lab oracle without interactive Automation UI."),FConsoleCommandDelegate::CreateLambda([]{
 struct FDirectCheck:FHolsterAuthored{FDirectCheck():FHolsterAuthored(TEXT("Prophecy.SwordHolster.AuthoredConsole")){}using FHolsterAuthored::RunTest;};
 FDirectCheck Check;const bool Passed=Check.RunTest(FString());UE_LOG(LogTemp,Display,TEXT("Authored lab checks passed=%d"),Passed);
}));
