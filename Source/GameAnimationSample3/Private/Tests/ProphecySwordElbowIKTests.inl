IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSwordElbowIKParity,"Prophecy.SwordHolster.ElbowIKParity",
 EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FSwordElbowIKParity::RunTest(const FString&)
{
 const FString Dir=FPaths::ProjectSavedDir()/TEXT("Diagnostics/ElbowIKRestore20261014");FString Text,Error;
 if(!FFileHelper::LoadFileToString(Text,*(Dir/TEXT("oracle.json")))){AddError(TEXT("Run Tools/SwordHolster/export_elbow_ik.cjs"));return false;}
 TSharedPtr<FJsonObject> Root;if(!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Root))return false;
 double MaxPosition=0,MaxAngle=0,MaxDuration=0;int Samples=0;FString Trace=TEXT("case,position_cm,angle_deg,bone,time\n");
 for(const auto& Value:Root->GetArrayField(TEXT("cases"))){
  const auto C=Value->AsObject(),Input=C->GetObjectField(TEXT("input"));FActive S;
  if(!LoadProfile(Dir/FString::Printf(TEXT("profile-%d.json"),int(C->GetNumberField(TEXT("id")))),S.Profile,Error)){AddError(Error);return false;}
  for(const auto& N:Input->GetArrayField(TEXT("names")))S.Names.Add(FName(*N->AsString()));
  for(const auto& P:Input->GetArrayField(TEXT("parents")))S.Parents.Add(int(P->AsNumber()));
  auto Find=[&](const TCHAR* N){return S.Names.IndexOfByKey(FName(N));};
  S.Pelvis=Find(TEXT("pelvis"));S.Clav=Find(TEXT("clavicle_r"));for(int I=0;I<5;++I)S.Spine[I]=Find(*FString::Printf(TEXT("spine_0%d"),I+1));
  const TCHAR* Arm[]={TEXT("upperarm_r"),TEXT("lowerarm_r"),TEXT("hand_r")};const TCHAR* Neck[]={TEXT("neck_01"),TEXT("neck_02"),TEXT("head")};
  for(int I=0;I<3;++I){S.Arm[I]=Find(Arm[I]);S.Neck[I]=Find(Neck[I]);}
  S.Groups.Init(-1,S.Names.Num());for(int J=0;J<S.Names.Num();++J){
   for(int K=J;K>=0;K=S.Parents[K])if(K==S.Spine[0]){S.Upper.Add(J);break;}
   for(int K=J;K>=0;K=S.Parents[K])if(K==S.Clav){S.GripUpper.Add(J);break;}
   const FString N=S.Names[J].ToString();if(N.StartsWith(TEXT("spine_")))S.Groups[J]=0;else if(N.StartsWith(TEXT("clavicle_")))S.Groups[J]=1;else if(N.StartsWith(TEXT("upperarm_")))S.Groups[J]=2;else if(N.StartsWith(TEXT("lowerarm_")))S.Groups[J]=3;else if(J==S.Neck[0])S.Groups[J]=4;else if(J==S.Neck[1])S.Groups[J]=5;else if(J==S.Neck[2])S.Groups[J]=6;else if(J==S.Arm[2])S.Groups[J]=7;
  }
  S.Base=JsonPoses(Input->GetArrayField(TEXT("base")));S.Pose=JsonPoses(Input->GetArrayField(TEXT("last")));S.LastBody=JsonPoses(Input->GetArrayField(TEXT("previous")));S.LastBase=JsonPoses(Input->GetArrayField(TEXT("previousBase")));
  S.OnlyGrip=Input->GetBoolField(TEXT("handInertia"));BeginReturn(S);
  MaxDuration=FMath::Max(MaxDuration,FMath::Abs(S.ReturnDuration-C->GetNumberField(TEXT("duration"))));
  double CasePosition=0,CaseAngle=0,WorstTime=0;FString WorstBone;
  for(const auto& FV:C->GetArrayField(TEXT("frames"))){const auto F=FV->AsObject();S.Base=JsonPoses(F->GetArrayField(TEXT("base")));S.Pose=S.Base;
   ReturnStep(S,F->GetNumberField(TEXT("time")));const auto Expected=JsonPoses(F->GetArrayField(TEXT("expected")));
   for(int J:(S.OnlyGrip?S.GripUpper:S.Upper)){const int P=S.Parents[J];const auto Actual=S.OnlyGrip?S.Pose[J].GetRelativeTransform(S.Pose[P]):S.Pose[J];const auto Wanted=S.OnlyGrip?Expected[J].GetRelativeTransform(Expected[P]):Expected[J];
    const double Position=FVector::Distance(Actual.GetLocation(),Wanted.GetLocation()),Rotation=Angle(Actual.GetRotation(),Wanted.GetRotation());
    if(Position>CasePosition){CasePosition=Position;WorstTime=F->GetNumberField(TEXT("time"));WorstBone=S.Names[J].ToString();}CaseAngle=FMath::Max(CaseAngle,Rotation);
    MaxPosition=FMath::Max(MaxPosition,Position);MaxAngle=FMath::Max(MaxAngle,Rotation);
   }++Samples;
  }
  Trace+=FString::Printf(TEXT("%d,%.12g,%.12g,%s,%.12g\n"),int(C->GetNumberField(TEXT("id"))),CasePosition,CaseAngle,*WorstBone,WorstTime);
 }
 FFileHelper::SaveStringToFile(Trace,*(Dir/TEXT("native-cases.csv")));
 const FString Result=FString::Printf(TEXT("samples=%d position_cm=%.12g angle_deg=%.12g duration_seconds=%.12g"),Samples,MaxPosition,MaxAngle,MaxDuration);AddInfo(Result);FFileHelper::SaveStringToFile(Result,*(Dir/TEXT("native-parity.txt")));
 TestTrue(TEXT("Lab moving-input return positions"),MaxPosition<.0001);TestTrue(TEXT("Lab moving-input return rotations"),MaxAngle<.001);TestTrue(TEXT("Unchanged duration"),MaxDuration<1.e-8);return !HasAnyErrors();
}
