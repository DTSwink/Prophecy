#include "ProphecyDodgeLower.h"
#include "ProphecyDefenseNetwork.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyCombatDodgeParityTest,"Prophecy.NN.Defense.CombatDodgeParity20261005",
 EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyCombatDodgeParityTest::RunTest(const FString&)
{
 using namespace ProphecyDefense;
 const FString Models=FPaths::ProjectContentDir()/TEXT("locomotion/NN/defense");
 ProphecyDefense::FGeometry G;FDodgeLowerSettings Settings[2];FProphecyDefenseNetwork Lower[2],Upper;FString Error;
 if(!G.Load(Models/TEXT("dodge_skeleton.json"),true,Error)||!Upper.Initialize(Models/TEXT("prophecy_dodge_upper.onnx"),362,112,Error)){AddError(Error);return false;}
 for(int32 I=0;I<2;++I){const FString K=I?TEXT("run"):TEXT("walk");if(!Settings[I].Load(Models/TEXT("dodge_lower_settings.json"),K,Error)||!Lower[I].Initialize(Models/(TEXT("prophecy_dodge_")+K+TEXT(".onnx")),152,43,Error)){AddError(Error);return false;}}
 for(int32 Row:{0,2,5})
 {
  FString Text;TSharedPtr<FJsonObject> Doc;const FString Dir=FPaths::ProjectSavedDir()/FString::Printf(TEXT("Diagnostics/CombatParity20261005/dodge_witness/%d"),Row);
  if(!G.Load(Dir/TEXT("skeleton.json"),true,Error)){AddError(Error);return false;}
  if(!FFileHelper::LoadFileToString(Text,*(Dir/TEXT("trace.json")))||!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Doc)){AddError(TEXT("Missing exact replay witness"));return false;}
  TMap<FString,TArray<float>> Data;
  for(const auto& P:Doc->Values){auto& V=Data.Add(P.Key);for(const auto& X:P.Value->AsArray())V.Add(float(X->AsNumber()));}
  auto Get=[&](const FString& K)->const float* {return Data.FindChecked(K).GetData();};
  float Max=0;FString Worst;
  auto Candidate=MakeShared<FJsonObject>();
  auto Check=[&](const FString& K,const float* V,int32 N){TArray<TSharedPtr<FJsonValue>> Values;for(int32 I=0;I<N;++I)Values.Add(MakeShared<FJsonValueNumber>(V[I]));Candidate->SetArrayField(K,Values);const auto& E=Data.FindChecked(K);if(E.Num()!=N){AddError(K+TEXT(" width"));return;}for(int32 I=0;I<N;++I){const float D=FMath::Abs(V[I]-E[I]);if(!FMath::IsFinite(V[I])){AddError(K+TEXT(" nonfinite"));return;}if(D>Max){Max=D;Worst=K+FString::Printf(TEXT("[%d]"),I);}}};
  const float* L=Get(TEXT("episode/lower_primers")),*U=Get(TEXT("episode/upper_primers")),*R=Get(TEXT("episode/root_primers"));
  FDodgeState S;S.Initialize(L,U,R,L+41,U+90,R+12,Get(TEXT("limits")));
  const int32 Category=int32(*Get(TEXT("category"))),Frames=Data.FindChecked(TEXT("episode/valid")).Num();
  for(int32 F=2;F<Frames;++F)
  {
   const FString P=FString::Printf(TEXT("frame/%03d/"),F);float LI[152],LO[43],Frozen[41],Pins[2];
   DodgeLowerInput(S,Settings[Category],LI);Check(P+(Category?TEXT("run/input/0"):TEXT("walk/input/0")),LI,152);
   if(!Lower[Category].Run(MakeArrayView(LI),MakeArrayView(LO)))return false;
   CleanDodgeLower(LO,S.CurrentLower,G,Settings[Category],Frozen,Pins);Check(P+TEXT("frozen_cleaned/output/0"),Frozen,41);
   FContext C;C.TargetWorld=Read(Get(TEXT("episode/target_world")));FMemory::Memcpy(C.AttackControls,Get(TEXT("episode/attack_type")),sizeof(C.AttackControls));C.Event=Get(TEXT("episode/event"))[F];
   for(int32 I=0;I<2;++I){FMemory::Memcpy(C.AttackerPelvis[I],Get(TEXT("episode/pelvis"))+9*(F-1+I),9*sizeof(float));FMemory::Memcpy(C.AttackerCollider[I],Get(TEXT("episode/collider"))+9*(F-1+I),9*sizeof(float));}
   FDodgeWork W;float UI[362],UO[112];FPose Pose;
   if(!PrepareDodge(S,Frozen,C,W,UI)||!Upper.Run(MakeArrayView(UI),MakeArrayView(UO)))return false;
   Check(P+TEXT("upper/input/0"),UI,362);Check(P+TEXT("upper/output/0"),UO,112);
   if(!CompleteDodge(S,W,Frozen,UO,G,Pose,nullptr,nullptr,nullptr,true,Upper.UsesExactForearms()))return false;
   float Positions[75],Rotations[225];for(int32 I=0;I<25;++I){Write(Positions+3*I,Pose.P[I]);for(int32 J=0;J<3;++J)Write(Rotations+I*9+J*3,Pose.R[I].V[J]);}
   Check(P+TEXT("proposal/positions"),Positions,75);Check(P+TEXT("proposal/rotations"),Rotations,225);
   Check(P+TEXT("proposal/state/current_lower"),S.CurrentLower,41);Check(P+TEXT("proposal/state/current_upper"),S.CurrentUpper,90);
   float Point[3];Write(Point,S.CurrentRoot.P);Check(P+TEXT("proposal/state/current_root"),Point,3);
  }
  FJsonSerializer::Serialize(Candidate,TJsonWriterFactory<>::Create(&Text));FFileHelper::SaveStringToFile(Text,*(Dir/TEXT("native.json")));
  AddInfo(FString::Printf(TEXT("Replay row %d maximum error %.9g at %s"),Row,Max,*Worst));TestTrue(TEXT("Full recurrent replay agrees with training policy within 0.0002"),Max<.0002f);
 }
 return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyCombatParryParityTest,"Prophecy.NN.Defense.CombatParryParity20261005",
 EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyCombatParryParityTest::RunTest(const FString&)
{
 using namespace ProphecyDefense;
 const FString Models=FPaths::ProjectContentDir()/TEXT("locomotion/NN/defense");
 FProphecyDefenseNetwork Upper;FString Error;
 if(!Upper.Initialize(Models/TEXT("prophecy_parry_upper.onnx"),258,90,Error)){AddError(Error);return false;}
 for(int32 Row:{0,14,15})
 {
  FString Text;TSharedPtr<FJsonObject> Doc;const FString Dir=FPaths::ProjectSavedDir()/FString::Printf(TEXT("Diagnostics/CombatParity20261005/parry_witness/%d"),Row);
  ProphecyDefense::FGeometry G;
  if(!G.Load(Dir/TEXT("skeleton.json"),false,Error)){AddError(Error);return false;}
  if(!FFileHelper::LoadFileToString(Text,*(Dir/TEXT("trace.json")))||!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Doc)){AddError(TEXT("Missing exact parry witness"));return false;}
  TMap<FString,TArray<float>> Data;
  for(const auto& P:Doc->Values){auto& V=Data.Add(P.Key);for(const auto& X:P.Value->AsArray())V.Add(float(X->AsNumber()));}
  auto Get=[&](const FString& K)->const float* {return Data.FindChecked(K).GetData();};
  float Max=0;FString Worst;auto Candidate=MakeShared<FJsonObject>();
  auto Check=[&](const FString& K,const float* V,int32 N){TArray<TSharedPtr<FJsonValue>> Values;for(int32 I=0;I<N;++I)Values.Add(MakeShared<FJsonValueNumber>(V[I]));Candidate->SetArrayField(K,Values);const auto& E=Data.FindChecked(K);if(E.Num()!=N){AddError(K+TEXT(" width"));return;}for(int32 I=0;I<N;++I){const float D=FMath::Abs(V[I]-E[I]);if(!FMath::IsFinite(V[I])){AddError(K+TEXT(" nonfinite"));return;}if(D>Max){Max=D;Worst=K+FString::Printf(TEXT("[%d]"),I);}}};
  const float* L=Get(TEXT("cache/lower")),*U=Get(TEXT("episode/upper_primers")),*R=Get(TEXT("cache/roots")),*B=Get(TEXT("cache/baseline_upper"));
  FParryState S;S.Initialize(L,U,R,L+41,U+90,R+12,B+90);
  const int32 Frames=Data.FindChecked(TEXT("episode/valid")).Num();
  for(int32 F=2;F<Frames;++F)
  {
   const FString P=FString::Printf(TEXT("frame/%03d/"),F);FContext C;C.TargetWorld=Read(Get(TEXT("episode/target_world")));FMemory::Memcpy(C.AttackControls,Get(TEXT("episode/attack_type")),sizeof(C.AttackControls));C.Event=Get(TEXT("episode/event"))[F];
   for(int32 I=0;I<2;++I){FMemory::Memcpy(C.AttackerPelvis[I],Get(TEXT("episode/pelvis"))+9*(F-1+I),9*sizeof(float));FMemory::Memcpy(C.AttackerCollider[I],Get(TEXT("episode/collider"))+9*(F-1+I),9*sizeof(float));}
   const auto Next=FRootFrame::Read12(R+12*F);FPose Frozen,Pose;const float* FP=Get(TEXT("cache/positions"))+75*F,*FR=Get(TEXT("cache/rotations"))+225*F;
   for(int32 I=0;I<25;++I){Frozen.P[I]=Read(FP+3*I);Frozen.R[I]=Rows(FR+9*I);}
   FParryWork W;float UI[258],UO[90];
   if(!PrepareParry(S,L+41*F,B+90*F,Next,C,*Get(TEXT("drawn")),W,UI)||!Upper.Run(MakeArrayView(UI),MakeArrayView(UO)))return false;
   Check(P+TEXT("upper/input/0"),UI,258);Check(P+TEXT("upper/output/0"),UO,90);
   if(!CompleteParry(S,W,UO,L+41*F,B+90*F,Next,Frozen,G,Pose,Upper.UsesExactForearms()))return false;
   float Positions[75],Rotations[225];for(int32 I=0;I<25;++I){Write(Positions+3*I,Pose.P[I]);for(int32 J=0;J<3;++J)Write(Rotations+I*9+J*3,Pose.R[I].V[J]);}
   Check(P+TEXT("proposal/1"),Positions,75);Check(P+TEXT("proposal/2"),Rotations,225);Check(P+TEXT("proposal/0/current_upper"),S.CurrentUpper,90);
  }
  FJsonSerializer::Serialize(Candidate,TJsonWriterFactory<>::Create(&Text));FFileHelper::SaveStringToFile(Text,*(Dir/TEXT("native.json")));
  AddInfo(FString::Printf(TEXT("Parry row %d maximum error %.9g at %s"),Row,Max,*Worst));TestTrue(TEXT("Full recurrent parry agrees with training policy within 0.0002"),Max<.0002f);
 }
 return !HasAnyErrors();
}
#endif

