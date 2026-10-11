// Same-process comparisons keep compiler, inputs and machine load comparable.
static FActive OptimizationFixture(const TSharedPtr<FJsonObject>& Root,const TSharedPtr<FJsonObject>& Row)
{
 FActive S;FString Error;LoadProfile(FPaths::ProjectContentDir()/TEXT("locomotion/SwordHolsterProfile.json"),S.Profile,Error);
 for(const auto& N:Root->GetArrayField(TEXT("names")))S.Names.Add(FName(*N->AsString()));for(const auto& P:Root->GetArrayField(TEXT("parents")))S.Parents.Add(int(P->AsNumber()));
 S.Base=JsonPoses(Row->GetArrayField(TEXT("base")));S.Clear=JsonPose(Row->GetObjectField(TEXT("clear")));S.Seat=JsonPose(Row->GetObjectField(TEXT("seat")));S.Mouth=JsonVector(Row->GetArrayField(TEXT("mouth")));S.Sheathe=Row->GetBoolField(TEXT("sheathe"));
 auto Find=[&](const TCHAR* N){return S.Names.IndexOfByKey(FName(N));};S.Pelvis=Find(TEXT("pelvis"));S.Clav=Find(TEXT("clavicle_r"));for(int I=0;I<5;++I)S.Spine[I]=Find(*FString::Printf(TEXT("spine_0%d"),I+1));
 const TCHAR* Arm[]={TEXT("upperarm_r"),TEXT("lowerarm_r"),TEXT("hand_r")};const TCHAR* Neck[]={TEXT("neck_01"),TEXT("neck_02"),TEXT("head")};for(int I=0;I<3;++I){S.Arm[I]=Find(Arm[I]);S.Neck[I]=Find(Neck[I]);}
 S.Groups.Init(-1,S.Names.Num());for(int J=0;J<S.Names.Num();++J){for(int K=J;K>=0;K=S.Parents[K])if(K==S.Spine[0]){S.Upper.Add(J);break;}const FString N=S.Names[J].ToString();if(N.StartsWith(TEXT("spine_")))S.Groups[J]=0;else if(N.StartsWith(TEXT("clavicle_")))S.Groups[J]=1;else if(N.StartsWith(TEXT("upperarm_")))S.Groups[J]=2;else if(N.StartsWith(TEXT("lowerarm_")))S.Groups[J]=3;else if(J==S.Neck[0])S.Groups[J]=4;else if(J==S.Neck[1])S.Groups[J]=5;else if(J==S.Neck[2])S.Groups[J]=6;}
 S.SpineAxis=S.Base[S.Spine[4]].GetRotation().UnrotateVector(S.Base[S.Neck[0]].GetLocation()-S.Base[S.Spine[4]].GetLocation()).GetSafeNormal();const FVector Axis=S.Base[S.Clav].GetRotation().UnrotateVector(S.Base[S.Arm[0]].GetLocation()-S.Base[S.Clav].GetLocation()).GetSafeNormal();S.ClavU=FVector::CrossProduct(Axis,FMath::Abs(Axis.X)<.8?FVector::ForwardVector:FVector::RightVector).GetSafeNormal();S.ClavV=FVector::CrossProduct(Axis,S.ClavU);
 const auto P=Root->GetObjectField(TEXT("profile"));S.ReachSpeed=P->GetNumberField(TEXT("maxReachSpeed"));S.RotationSpeed=P->GetNumberField(TEXT("maxReachRotationSpeed"));S.SlideSpeed=P->GetNumberField(TEXT("slidingSpeed"));
 S.SlideLength=FVector::Distance(S.Clear.GetLocation(),S.Seat.GetLocation());S.Status.SlideTicks=FMath::Max(1,FMath::CeilToInt(S.SlideLength/S.SlideSpeed*60));
 S.Pose=S.LastBody=S.LastBase=S.Base;S.Head=S.HeadStart=S.Base[S.Neck[2]].GetRotation();PrepareUpperOrder(S);return S;
}
static void OptimizationPlan(FActive& S,bool Old)
{
 S.Desired=FVector::ZeroVector;S.Desired=Old?LegacyOptimize(S):Optimize(S);CaptureArm(S,S.Base,S.SourceArm);
 if(Old)LegacyEndpoint(S,S.Desired,S.Sheathe?S.Clear:S.Seat,S.SourceArm,S.DestinationArm);else Endpoint(S,S.Desired,S.Sheathe?S.Clear:S.Seat,S.SourceArm,S.DestinationArm);
 const double T=Old?LegacyArmDuration(S.SourceArm,S.DestinationArm,S.ReachSpeed,S.RotationSpeed):ArmDuration(S.SourceArm,S.DestinationArm,S.ReachSpeed,S.RotationSpeed);
 S.Status.ReachTicks=FMath::Max(1,FMath::CeilToInt(T*60));
}
static void OptimizationMovingBase(FActive& S,const TArray<FTransform>& Base,double Time)
{
 for(int J=0;J<Base.Num();++J){const int P=S.Parents[J];FTransform L=P>=0?Base[J].GetRelativeTransform(Base[P]):Base[J];
  if(P>=0&&S.Groups[J]>=0){const double A=.025*FMath::Sin(Time*2.1+J*.71);L.SetRotation((FQuat(FVector::UpVector,A)*L.GetRotation()).GetNormalized());}
  S.Base[J]=P>=0?L*S.Base[P]:L;
 }
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FHolsterOptimization,"Prophecy.SwordHolster.Optimization",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FHolsterOptimization::RunTest(const FString&)
{
 FString Text;const FString Dir=FPaths::ProjectSavedDir()/TEXT("Diagnostics/SwordOptimization20261010");IFileManager::Get().MakeDirectory(*Dir,true);
 if(!FFileHelper::LoadFileToString(Text,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/SwordLabPort20261010/parity.json")))){AddError(TEXT("Missing parity fixture"));return false;}
 TSharedPtr<FJsonObject> Root;if(!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Root))return false;
 double FitError=0,PoseError=0,PositionError=0,DurationError=0;int TimingMismatch=0;FRandomStream Random(551039);
 double TrigError=0;for(int I=0;I<=20000;++I){const double X=PI*(I/20000.-.5);double Sin,Cos;ShortArcSinCos(X,Sin,Cos);TrigError=FMath::Max3(TrigError,FMath::Abs(Sin-FMath::Sin(X)),FMath::Abs(Cos-FMath::Cos(X)));}
 TestTrue(TEXT("Bounded trig precision"),TrigError<2.e-14);
 double ThirdError=0;for(int I=0;I<=20000;++I){const FQuat Q(FVector(1,2,3).GetSafeNormal(),PI*(I/5000.-2));const FQuat Expected=FQuat::Slerp(FQuat::Identity,Q,1./3.),Actual=QuaternionThird(Q);ThirdError=FMath::Max(ThirdError,FMath::Min((Actual-Expected).SizeSquared(),(Actual+Expected).SizeSquared()));}
 TestTrue(TEXT("One-third rotation precision"),ThirdError<1.e-24);
 FString Bench=TEXT("motion,sheathe,repeat,old,stage,frames,total_ms,peak_ms\n");
 for(const auto& RV:Root->GetArrayField(TEXT("rows"))){const auto Row=RV->AsObject();const FActive Seed=OptimizationFixture(Root,Row);
  // Search equivalence on moving, differently sized geometry and limits.
  for(int I=0;I<160;++I){FActive A=Seed;OptimizationMovingBase(A,Seed.Base,I*.037);A.Profile.AngleLimit=I%8?Random.FRandRange(1,90):0;A.Clear.AddToTranslation(FVector(Random.FRandRange(-30,30),Random.FRandRange(-30,30),Random.FRandRange(-20,20)));A.Desired=FVector(Random.FRandRange(-1,1),Random.FRandRange(-1,1),Random.FRandRange(-1,1));
   const FVector Old=LegacyOptimize(A),New=Optimize(A);const double E=(Old-New).Size();FitError=FMath::Max(FitError,E);
   if(E>1.e-4)AddError(FString::Printf(TEXT("Search mismatch %d error %.9g old %s new %s"),I,E,*Old.ToString(),*New.ToString()));
  }
  // Signed head/neck behaviour is compared to the current JS lab oracle in LabChannels.
  // Velocity planning keeps the same 96 samples, including near-identical arcs.
  for(int I=0;I<200;++I){FTransform A[3],B[3];CaptureArm(Seed,Seed.Base,A);CaptureArm(Seed,Seed.Base,B);
   for(int J=0;J<3;++J){const FVector Axis=FVector(Random.FRandRange(-1,1),Random.FRandRange(-1,1),Random.FRandRange(-1,1)).GetSafeNormal();const double V=I%4?Random.FRandRange(-3,3):Random.FRandRange(-.01,.01);B[J].SetRotation((FQuat(Axis,V)*A[J].GetRotation()).GetNormalized());if(J)B[J].SetTranslation(FQuat(Axis,V*.3).RotateVector(A[J].GetLocation()));}
   if(I%5==0)A[0].SetScale3D(FVector(1.2));
   const double Linear=Random.FRandRange(20,1000),Angular=Random.FRandRange(10,3000),Old=LegacyArmDuration(A,B,Linear,Angular),New=ArmDuration(A,B,Linear,Angular);DurationError=FMath::Max(DurationError,FMath::Abs(Old-New));TimingMismatch+=FMath::CeilToInt(Old*60)!=FMath::CeilToInt(New*60);
  }
  // The NN normally publishes unit-scale bone transforms. Keep the generic
  // transform path equivalent when a scaled parent is supplied as well.
  {FActive Old=Seed,New=Seed;Old.Pose=New.Pose=JsonPoses(Row->GetArrayField(TEXT("end")));Old.LastBody=New.LastBody=JsonPoses(Row->GetArrayField(TEXT("before")));
   for(int J=0;J<Old.Base.Num();++J){Old.Base[J].SetScale3D(FVector(1.3));New.Base[J]=Old.Base[J];}Old.LastBase=New.LastBase=Old.Base;
   LegacyBeginReturn(Old);BeginReturn(New);Old.Pose=Old.Base;New.Pose=New.Base;LegacyReturnStep(Old,.3);ReturnStep(New,.3);
   for(int J:Old.Upper){PoseError=FMath::Max(PoseError,Angle(Old.Pose[J].GetRotation(),New.Pose[J].GetRotation()));PositionError=FMath::Max(PositionError,FVector::Distance(Old.Pose[J].GetLocation(),New.Pose[J].GetLocation()));}
  }
  // The historical lifecycle no longer specifies early return or tip entry.
  // BoneOrder/Stagger exercise the current lifecycle; these timings retain the old baseline.
  for(int Repeat=-1;Repeat<7;++Repeat)for(int Pass=0;Pass<2;++Pass){const bool Old=((Pass+(Repeat&1))%2)!=0;
   TArray<FActive> Crowd;Crowd.Reserve(100);for(int I=0;I<100;++I)Crowd.Add(Seed);
   double Start=FPlatformTime::Seconds();for(auto& C:Crowd)OptimizationPlan(C,Old);const double Planning=(FPlatformTime::Seconds()-Start)*1000;
   if(Repeat>=0)Bench+=FString::Printf(TEXT("%s,%d,%d,%d,planning,1,%.9f,%.9f\n"),*Row->GetStringField(TEXT("motion")),Seed.Sheathe,Repeat,Old,Planning,Planning);
   double Total=0,Peak=0;int Frames=0;
   for(int Frame=0;Frame<240;++Frame){bool Running=false;Start=FPlatformTime::Seconds();for(auto& C:Crowd){if(C.Status.Finished)continue;Running=true;if(C.Status.ReachDone&&!C.Sliding){C.Sliding=true;C.SlideStart=C.Status.Tick;}if(Old)LegacyAdvance(C,1);else Advance(C,1);}const double Ms=(FPlatformTime::Seconds()-Start)*1000;if(!Running)break;Total+=Ms;Peak=FMath::Max(Peak,Ms);++Frames;}
   TestTrue(TEXT("Timed crowd completes"),Crowd[0].Status.Finished);
   if(Repeat>=0)Bench+=FString::Printf(TEXT("%s,%d,%d,%d,cycle,%d,%.9f,%.9f\n"),*Row->GetStringField(TEXT("motion")),Seed.Sheathe,Repeat,Old,Frames,Total,Peak);
   for(int Stage=0;Stage<7;++Stage){
    for(auto& C:Crowd){C=Seed;OptimizationPlan(C,Old);C.Status.Tick=12;C.Pose=C.Base;
     if(Stage==2){C.Sliding=true;C.Status.SlideProgress=1;C.HeadOut=true;C.Head=(FQuat(FVector::UpVector,.3)*C.Head).GetNormalized();}
     if(Stage==3){C.Pose=JsonPoses(Row->GetArrayField(TEXT("end")));C.LastBody=JsonPoses(Row->GetArrayField(TEXT("before")));if(Old)LegacyBeginReturn(C);else BeginReturn(C);C.Pose=C.Base;}
     if(Stage==4)C.Desired=FVector::ZeroVector;
    }
    Start=FPlatformTime::Seconds();
    for(auto& C:Crowd){if(Stage==0||Stage==4)C.Desired=Old?LegacyOptimize(C):Optimize(C);else if(Stage<3){if(Old)LegacyHeadStep(C);else HeadStep(C);}else if(Stage==3){if(Old)LegacyReturnStep(C,.3);else ReturnStep(C,.3);}else if(Stage==5){C.ReturnDuration=Old?LegacyArmDuration(C.SourceArm,C.DestinationArm,C.ReachSpeed,C.RotationSpeed):ArmDuration(C.SourceArm,C.DestinationArm,C.ReachSpeed,C.RotationSpeed);}else{if(Old)LegacyEndpoint(C,C.Desired,C.Sheathe?C.Clear:C.Seat,C.SourceArm,C.DestinationArm);else Endpoint(C,C.Desired,C.Sheathe?C.Clear:C.Seat,C.SourceArm,C.DestinationArm);}}
    const double Ms=(FPlatformTime::Seconds()-Start)*1000;const TCHAR* Names[]={TEXT("fit"),TEXT("head_in"),TEXT("head_out"),TEXT("return"),TEXT("initial_fit"),TEXT("duration"),TEXT("endpoint")};
    if(Repeat>=0)Bench+=FString::Printf(TEXT("%s,%d,%d,%d,%s,1,%.9f,%.9f\n"),*Row->GetStringField(TEXT("motion")),Seed.Sheathe,Repeat,Old,Names[Stage],Ms,Ms);
   }
  }
 }
 TestTrue(TEXT("Body fit parity radians"),FitError<1.e-4);TestTrue(TEXT("Full pose parity degrees"),PoseError<.005);TestTrue(TEXT("Full pose parity cm"),PositionError<.005);TestTrue(TEXT("Duration parity seconds"),DurationError<.00001);TestEqual(TEXT("Authored tick decisions unchanged"),TimingMismatch,0);
 const FString Result=FString::Printf(TEXT("fit_rad=%.12g pose_deg=%.12g position_cm=%.12g duration_s=%.12g trig_error=%.12g third_quat_squared_error=%.12g timing_mismatch=%d\n"),FitError,PoseError,PositionError,DurationError,TrigError,ThirdError,TimingMismatch);
 AddInfo(Result);FFileHelper::SaveStringToFile(Result,*(Dir/TEXT("parity.txt")));FFileHelper::SaveStringToFile(Bench,*(Dir/TEXT("benchmark.csv")),FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);return !HasAnyErrors();
}
