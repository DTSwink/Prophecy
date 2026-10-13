IMPLEMENT_SIMPLE_AUTOMATION_TEST(FHolsterLabChannels,"Prophecy.SwordHolster.LabChannels",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FHolsterLabChannels::RunTest(const FString&)
{
 const FString Dir=FPaths::ProjectSavedDir()/TEXT("Diagnostics/SwordLabSync20261011");FString Text;
 if(!FFileHelper::LoadFileToString(Text,*(Dir/TEXT("channels.json")))){AddError(TEXT("Run Tools/SwordHolster/export_channels.cjs"));return false;}
 TSharedPtr<FJsonObject> Root;if(!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Root))return false;
 FActive Seed;for(const auto& N:Root->GetArrayField(TEXT("names")))Seed.Names.Add(FName(*N->AsString()));for(const auto& P:Root->GetArrayField(TEXT("parents")))Seed.Parents.Add(int(P->AsNumber()));
 auto Find=[&](const TCHAR* N){return Seed.Names.IndexOfByKey(FName(N));};Seed.Pelvis=Find(TEXT("pelvis"));Seed.Clav=Find(TEXT("clavicle_r"));for(int I=0;I<5;++I)Seed.Spine[I]=Find(*FString::Printf(TEXT("spine_0%d"),I+1));
 const TCHAR* Arm[]={TEXT("upperarm_r"),TEXT("lowerarm_r"),TEXT("hand_r")};const TCHAR* Neck[]={TEXT("neck_01"),TEXT("neck_02"),TEXT("head")};for(int I=0;I<3;++I){Seed.Arm[I]=Find(Arm[I]);Seed.Neck[I]=Find(Neck[I]);}PrepareUpperOrder(Seed);
 double HeadError=0,NeckError=0,PositionError=0,GeometryPosition=0,GeometryAngle=0;int DoneMismatch=0,Samples=0;
 for(const auto& Value:Root->GetArrayField(TEXT("rows"))){const auto Row=Value->AsObject();FActive S=Seed;
  S.GazeInput.X=Row->GetNumberField(TEXT("gaze"))/170;S.Gaze=S.StartGaze=FMath::Abs(S.GazeInput.X);S.Profile.HeadAlpha=.7;S.Profile.HeadSpeedAlpha=.3;
  S.Profile.HeadMaxTilt=Row->GetNumberField(TEXT("tilt"));
  S.Profile.HeadInSpeed=S.Profile.HeadInMaxGaze=180;S.Profile.HeadOutSpeed=S.Profile.HeadOutMaxGaze=240;S.Profile.HeadInExponent=S.Profile.HeadOutExponent=Row->GetNumberField(TEXT("exponent"));S.Status.ReachTicks=75;
  const auto& Frames=Row->GetArrayField(TEXT("frames"));
  for(int Tick=0;Tick<Frames.Num();++Tick){const auto F=Frames[Tick]->AsObject();S.Base=JsonPoses(F->GetArrayField(TEXT("base")));S.Pose=JsonPoses(F->GetArrayField(TEXT("pose")));S.Mouth=JsonVector(F->GetArrayField(TEXT("target")));S.Status.Tick=Tick;S.Sliding=Tick>=90;S.Status.Insertion=S.Status.SlideProgress=S.Sliding?1:0;
   if(Tick==0){S.Head=JsonQuat(F->GetArrayField(TEXT("q")));NeutralFacing(S);S.HeadReference=S.NeutralHead;S.HeadDelta=Log(S.Head*S.HeadReference.Inverse());S.HeadBaseDelta=S.HeadDelta;S.HeadFrom=S.HeadDelta;S.HeadInitialized=true;continue;}
   HeadStep(S);HeadError=FMath::Max(HeadError,Angle(S.Head,JsonQuat(F->GetArrayField(TEXT("q")))));DoneMismatch+=S.HeadDone!=F->GetBoolField(TEXT("done"));
   const auto Expected=JsonPoses(F->GetArrayField(TEXT("neck")));for(int K=0;K<3;++K){NeckError=FMath::Max(NeckError,Angle(S.Pose[S.Neck[K]].GetRotation(),Expected[K].GetRotation()));PositionError=FMath::Max(PositionError,FVector::Dist(S.Pose[S.Neck[K]].GetLocation(),Expected[K].GetLocation()));}
   if(S.Profile.HeadMaxTilt>=90)TestTrue(TEXT("Independent head velocity cap"),S.Status.HeadStep<=(S.HeadOut?240:180)/60.+.0001);++Samples;
  }
 }
 const auto Setup=Root->GetObjectField(TEXT("setup"));Seed.Geometry.Valid=true;Seed.Geometry.Grip=JsonPose(Setup->GetObjectField(TEXT("grip")));Seed.Geometry.AssetScale=JsonVector(Setup->GetArrayField(TEXT("assetScale")));Seed.Geometry.BaseLocal=JsonVector(Setup->GetArrayField(TEXT("baseBladeLocal")));Seed.Geometry.TipLocal=JsonVector(Setup->GetArrayField(TEXT("tip")));Seed.Geometry.Retained=.85;Seed.Sheathe=true;
 for(const auto& Value:Root->GetArrayField(TEXT("geometry"))){const auto F=Value->AsObject();FActive S=Seed;S.Full=JsonPose(F->GetObjectField(TEXT("full")));S.Full.SetScale3D(JsonVector(F->GetObjectField(TEXT("full"))->GetArrayField(TEXT("s"))));S.Mouth=S.Full.TransformPosition(S.Geometry.BaseLocal);
  const auto Entry=F->GetObjectField(TEXT("entry"));S.EntryScale=Entry->GetNumberField(TEXT("scale"));S.EntryRotation=JsonQuat(Entry->GetArrayField(TEXT("q")));S.EntryTipError=JsonVector(Entry->GetArrayField(TEXT("tipError")));S.Profile.RotationCorrection=F->GetNumberField(TEXT("alpha"));
  const FTransform Got=SlideGoal(S,F->GetNumberField(TEXT("insertion")),F->GetNumberField(TEXT("time"))),Expected=JsonPose(F->GetObjectField(TEXT("goal")));
  GeometryPosition=FMath::Max(GeometryPosition,FVector::Dist(Got.GetLocation(),Expected.GetLocation()));GeometryAngle=FMath::Max(GeometryAngle,Angle(Got.GetRotation(),Expected.GetRotation()));
 }
 TestTrue(TEXT("Lab signed head path"),HeadError<.001);TestTrue(TEXT("Lab neck rotation"),NeckError<.001);TestTrue(TEXT("Lab neck position"),PositionError<.001);TestEqual(TEXT("Lab head completion ticks"),DoneMismatch,0);
 TestTrue(TEXT("Independent slide rotation position"),GeometryPosition<.001);TestTrue(TEXT("Independent slide rotation angle"),GeometryAngle<.001);
 const FString Result=FString::Printf(TEXT("head_samples=%d head_deg=%.9g neck_deg=%.9g neck_cm=%.9g done_mismatches=%d slide_cm=%.9g slide_deg=%.9g\n"),Samples,HeadError,NeckError,PositionError,DoneMismatch,GeometryPosition,GeometryAngle);AddInfo(Result);FFileHelper::SaveStringToFile(Result,*(Dir/TEXT("channels-result.txt")));return !HasAnyErrors();
}
