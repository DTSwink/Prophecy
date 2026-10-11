// This pure-math probe also runs directly after a layout-safe Live Coding patch.
// It does not start the editor Automation framework or touch actors/assets.
struct FOrderResult
{
 bool Passed=true;int Cases=0,Samples=0,TimingMismatch=0,NonFinite=0;
 double Degrees=0,Position=0,Length=0,SeedRate=0,FixtureSensitivity=0;
 FString Error;
};
static FActive ReorderFixture(const FActive& Source,const FBoneOrder& Map)
{
 FActive S=Source;FBoneOrder Inverse;Inverse.Init(INDEX_NONE,Source.Names.Num());
 for(int J=0;J<Map.Num();++J)Inverse[Map[J]]=J;
 S.Names.SetNum(Map.Num());S.Parents.SetNum(Map.Num());S.Groups.SetNum(Map.Num());S.Base.SetNum(Map.Num());
 S.Pose.SetNum(Map.Num());S.LastBody.SetNum(Map.Num());S.LastBase.SetNum(Map.Num());
 for(int J=0;J<Map.Num();++J){const int Old=Map[J];int P=Source.Parents[Old];while(P>=0&&Inverse[P]<0)P=Source.Parents[P];
  S.Names[J]=Source.Names[Old];S.Parents[J]=P<0?P:Inverse[P];S.Groups[J]=Source.Groups[Old];S.Base[J]=Source.Base[Old];
  S.Pose[J]=Source.Pose[Old];S.LastBody[J]=Source.LastBody[Old];S.LastBase[J]=Source.LastBase[Old];
 }
 S.Pelvis=Inverse[Source.Pelvis];S.Clav=Inverse[Source.Clav];
 for(int K=0;K<5;++K)S.Spine[K]=Inverse[Source.Spine[K]];
 for(int K=0;K<3;++K){S.Arm[K]=Inverse[Source.Arm[K]];S.Neck[K]=Inverse[Source.Neck[K]];}
 PrepareUpperOrder(S);return S;
}
static FOrderResult CheckBoneOrder()
{
 FOrderResult Result;FString Text;
 if(!FFileHelper::LoadFileToString(Text,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/SwordLabPort20261010/parity.json")))){Result.Passed=false;Result.Error=TEXT("Missing lab parity fixture");return Result;}
 TSharedPtr<FJsonObject> Root;if(!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Root)){Result.Passed=false;Result.Error=TEXT("Invalid parity fixture");return Result;}
 FBoneOrder Order;const int32 Cycle[]={1,0},Invalid[]={-1,8};
 Result.Passed&=!HierarchyOrder(MakeArrayView(Cycle),Order)&&!HierarchyOrder(MakeArrayView(Invalid),Order);
 const TCHAR* LiveNames[]={TEXT("pelvis"),TEXT("spine_01"),TEXT("spine_02"),TEXT("spine_03"),TEXT("spine_04"),TEXT("spine_05"),TEXT("clavicle_l"),TEXT("upperarm_l"),TEXT("lowerarm_l"),TEXT("hand_l"),TEXT("clavicle_r"),TEXT("upperarm_r"),TEXT("lowerarm_r"),TEXT("hand_r"),TEXT("neck_01"),TEXT("head"),TEXT("thigh_l"),TEXT("calf_l"),TEXT("foot_l"),TEXT("thigh_r"),TEXT("calf_r"),TEXT("foot_r"),TEXT("neck_02"),TEXT("ball_l"),TEXT("ball_r")};
 FRandomStream Random(270411);
 for(const auto& RV:Root->GetArrayField(TEXT("rows"))){const FActive Lab=OptimizationFixture(Root,RV->AsObject());FBoneOrder WithoutRoot;
  for(int J=0;J<Lab.Names.Num();++J)if(Lab.Names[J]!=TEXT("root"))WithoutRoot.Add(J);
  const FActive Seed=ReorderFixture(Lab,WithoutRoot);const int N=Seed.Names.Num();
  if(N!=UE_ARRAY_COUNT(LiveNames)){Result.Passed=false;Result.Error=TEXT("Unexpected fixture skeleton");return Result;}
  for(int Permutation=0;Permutation<10;++Permutation){FBoneOrder Map;
   for(int J=0;J<N;++J)Map.Add(Permutation==0?Seed.Names.IndexOfByKey(FName(LiveNames[J])):Permutation==1?N-1-J:J);
   if(Map.Contains(INDEX_NONE)){Result.Passed=false;Result.Error=TEXT("Missing live bone name");return Result;}
   if(Permutation>=2)for(int J=N-1;J>0;--J)Swap(Map[J],Map[Random.RandRange(0,J)]);
   // The live-order fixture must expose the old body traversal even without
   // depending on arbitrary contents of uninitialized return buffers.
   if(Permutation==0){FActive Good=ReorderFixture(Seed,Map),Bad=Good;Bad.Upper.Sort();TArray<FTransform> A,B;
    BodyPose(Good,Good.Base,FVector(.6,.2,-.2),A);BodyPose(Bad,Bad.Base,FVector(.6,.2,-.2),B);
    Result.FixtureSensitivity=FMath::Max(Result.FixtureSensitivity,Angle(A[Good.Neck[2]].GetRotation(),B[Good.Neck[2]].GetRotation()));
   }
   for(int Mode=0;Mode<12;++Mode){FActive A=Seed;auto& R=A.Profile.Return[A.Sheathe];R.World=(Mode%2)!=0;R.Spring=((Mode/2)%2)!=0;R.TwistRemoval=Mode%3?.65:0;R.Easing=(Mode%3)*.5;R.Inertia=Mode>=8?0:.7;R.Hold=.13;R.Decay=.9;
    for(int G=0;G<7;++G)R.Weights[G]=(G+1)/7.;
    A.Profile.HeadInExponent=1+Mode%4;A.Profile.HeadOutExponent=1+(Mode+2)%4;
    FActive B=ReorderFixture(A,Map);PrepareUpperOrder(A);OptimizationPlan(A,false);OptimizationPlan(B,false);
    // Deliberately dirty reusable storage: initialization must overwrite every
    // consumed value before it can affect a child's incoming angular velocity.
    A.ReturnWorld.Init(FQuat(FVector::ForwardVector,1.7),N);B.ReturnWorld.Init(FQuat(FVector::RightVector,-2.4),N);
    Result.TimingMismatch+=A.Status.ReachTicks!=B.Status.ReachTicks;
    for(int Tick=0;Tick<420&&!A.Status.Finished;++Tick){
     OptimizationMovingBase(A,Seed.Base,Tick/60.);for(int J=0;J<N;++J)B.Base[J]=A.Base[Map[J]];
     A.Clear=B.Clear=FTransform(Seed.Clear.GetRotation(),Seed.Clear.GetLocation()+FVector(FMath::Sin(Tick*.09)*2,0,0));
     if(A.Status.ReachDone&&!A.Sliding){A.Sliding=B.Sliding=true;A.SlideStart=B.SlideStart=A.Status.Tick;}
     Advance(A,1);Advance(B,1);++Result.Samples;
     Result.TimingMismatch+=(A.Status.ReachDone!=B.Status.ReachDone)||(A.Status.Returning!=B.Status.Returning)||(A.Status.Finished!=B.Status.Finished);
     for(int J=0;J<N;++J){const int K=Map[J],P=B.Parents[J];
      if(B.Pose[J].ContainsNaN()||!B.Pose[J].GetRotation().IsNormalized()){++Result.NonFinite;continue;}
      Result.Degrees=FMath::Max(Result.Degrees,Angle(A.Pose[K].GetRotation(),B.Pose[J].GetRotation()));
      Result.Position=FMath::Max(Result.Position,FVector::Distance(A.Pose[K].GetLocation(),B.Pose[J].GetLocation()));
      if(P>=0)Result.Length=FMath::Max(Result.Length,FMath::Abs(FVector::Distance(A.Pose[K].GetLocation(),A.Pose[Map[P]].GetLocation())-FVector::Distance(B.Pose[J].GetLocation(),B.Pose[P].GetLocation())));
      if(A.Status.Returning)Result.SeedRate=FMath::Max(Result.SeedRate,(A.WorldVelocity[K]-B.WorldVelocity[J]).Size());
     }
    }
    Result.Passed&=A.Status.Finished&&B.Status.Finished;++Result.Cases;
   }
  }
 }
 Result.Passed&=Result.NonFinite==0&&Result.TimingMismatch==0&&Result.Degrees<.0001&&Result.Position<.00001&&Result.Length<.00001&&Result.SeedRate<.00001&&Result.FixtureSensitivity>1;
 return Result;
}
static FString OrderResultText(const FOrderResult& R)
{
 return FString::Printf(TEXT("passed=%d cases=%d samples=%d timing_mismatch=%d nonfinite=%d max_deg=%.12g max_cm=%.12g length_cm=%.12g seed_rate_rad_s=%.12g old_order_fixture_deg=%.12g error=%s\n"),R.Passed,R.Cases,R.Samples,R.TimingMismatch,R.NonFinite,R.Degrees,R.Position,R.Length,R.SeedRate,R.FixtureSensitivity,*R.Error);
}
static FAutoConsoleCommand VerifyOrderCommand(TEXT("Prophecy.Sword.VerifyBoneOrder"),TEXT("Run pure D/S bone-order regression without starting editor Automation."),FConsoleCommandDelegate::CreateLambda([]{
 const FString Result=OrderResultText(CheckBoneOrder()),Dir=FPaths::ProjectSavedDir()/TEXT("Diagnostics/SwordHeadFix20261011");IFileManager::Get().MakeDirectory(*Dir,true);
 FFileHelper::SaveStringToFile(Result,*(Dir/TEXT("bone-order.txt")));UE_LOG(LogTemp,Display,TEXT("SwordBoneOrder %s"),*Result);
}));
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FHolsterBoneOrder,"Prophecy.SwordHolster.BoneOrder",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FHolsterBoneOrder::RunTest(const FString&)
{const auto Result=CheckBoneOrder();AddInfo(OrderResultText(Result));TestTrue(TEXT("Bone order cannot alter pose, lengths, inertia or event ticks"),Result.Passed);return Result.Passed;}
