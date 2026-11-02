#include "ProphecyFootIKNN.h"
#include "Async/Async.h"
#include "Dom/JsonObject.h"
#include "HAL/PlatformTime.h"
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Policies/CondensedJsonPrintPolicy.h"
#include "Serialization/JsonSerializer.h"

#if WITH_DEV_AUTOMATION_TESTS
namespace FootIKLiveLowerTest
{
using FValues=TArray<TSharedPtr<FJsonValue>>;
static TSharedPtr<FJsonObject> Parse(const FString& Text)
{TSharedPtr<FJsonObject> O;return FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),O)?O:nullptr;}
static FString Text(const TSharedPtr<FJsonObject>& O)
{FString Out;FJsonSerializer::Serialize(O,TJsonWriterFactory<TCHAR,TCondensedJsonPrintPolicy<TCHAR>>::Create(&Out));return Out;}
struct FState
{
 FProphecyFootIKNN Full,Lower;
 FString Error;FValues Cases;
 int32 Frames=0,Numbers=0,RejectedMisuses=0;double Maximum=0,FullSeconds=0,LowerSeconds=0;
};
static bool Exact(const TSharedPtr<FJsonValue>& A,const TSharedPtr<FJsonValue>& B,FState& State)
{
 if(!A||!B||A->Type!=B->Type)return false;
 if(A->Type==EJson::Null)return true;
 if(A->Type==EJson::Number)
 {
  const double X=A->AsNumber(),Y=B->AsNumber();if(!FMath::IsFinite(X)||!FMath::IsFinite(Y))return false;
  State.Maximum=FMath::Max(State.Maximum,FMath::Abs(X-Y));++State.Numbers;
  // Both results came from the SAME engine ORT, so backend tolerance is not
  // needed here. The unchanged authoritative float32 lanes must be bit-exact.
  const float FX=float(X),FY=float(Y);return FMemory::Memcmp(&FX,&FY,sizeof(float))==0;
 }
 if(A->Type==EJson::Array)
 {
  const auto& X=A->AsArray();const auto& Y=B->AsArray();if(X.Num()!=Y.Num())return false;
  for(int32 I=0;I<X.Num();++I)if(!Exact(X[I],Y[I],State))return false;return true;
 }
 if(A->Type==EJson::String)return A->AsString()==B->AsString();
 return false;
}
static bool Compare(const TSharedPtr<FJsonObject>& Full,const TSharedPtr<FJsonObject>& Lower,FState& State)
{
 for(const TCHAR* Key:{TEXT("names"),TEXT("roots"),TEXT("rootYawDegrees"),TEXT("pins"),TEXT("fps"),TEXT("duration"),TEXT("inferences")})
 {
  const auto* A=Full->Values.Find(Key);const auto* B=Lower->Values.Find(Key);
  if(!A||!B||!Exact(*A,*B,State)){State.Error=FString(TEXT("Live lower authoritative field differs: "))+Key;return false;}
 }
 bool Marked=false;if(!Lower->TryGetBoolField(TEXT("liveLowerOnly"),Marked)||!Marked||Full->HasField(TEXT("liveLowerOnly"))){State.Error=TEXT("Private forecast scope metadata is missing or leaked into the full graph");return false;}
 const auto& A=Full->GetArrayField(TEXT("poses"));const auto& B=Lower->GetArrayField(TEXT("poses"));if(A.Num()!=B.Num()||A.Num()!=37){State.Error=TEXT("Live lower frame count differs from the real forecast horizon");return false;}
 for(int32 Frame=0;Frame<A.Num();++Frame)
 {
  const auto AP=A[Frame]->AsObject(),BP=B[Frame]->AsObject();if(!AP||!BP){State.Error=TEXT("Missing live lower pose");return false;}
  for(const TCHAR* Key:{TEXT("points"),TEXT("axes")})
  {
   const auto& X=AP->GetArrayField(Key);const auto& Y=BP->GetArrayField(Key);
   if(X.Num()!=25||Y.Num()!=25){State.Error=TEXT("Live lower skeleton layout changed");return false;}
   for(int32 Bone=0;Bone<25;++Bone)
    if((Frame==0||Bone==0||Bone>=17)&&!Exact(X[Bone],Y[Bone],State))
    {State.Error=FString::Printf(TEXT("Live lower %s differs at frame%d bone%d"),Key,Frame,Bone);return false;}
  }
  ++State.Frames;
 }
 return true;
}
static bool Run(const TSharedRef<FState,ESPMode::ThreadSafe>& State,const FString& Folder)
{
 if(!State->Full.PrewarmSessions(State->Error,EProphecyFootIKNNWarmup::Continuation)||!State->Lower.PrewarmSessions(State->Error,EProphecyFootIKNNWarmup::Continuation))return false;
 FString Output,Error;
 if(State->Lower.Initialize(Output,Error)||!Error.Contains(TEXT("reference course"))){State->Error=TEXT("Private lower graph accepted reference-course initialization");return false;}++State->RejectedMisuses;
 for(const auto Mode:{EProphecyFootIKNNWarmup::Stream,EProphecyFootIKNNWarmup::All})
 {if(State->Lower.PrewarmSessions(Error,Mode)||!Error.Contains(TEXT("continuation"))){State->Error=TEXT("Private lower graph accepted stream warmup");return false;}++State->RejectedMisuses;}
 for(const TCHAR* Name:{TEXT("app-walk-stairs-continuation.json"),TEXT("app-run-stairs-continuation.json"),TEXT("app-walk-down-continuation.json"),TEXT("app-run-down-continuation.json"),TEXT("app-walk-uneven-continuation.json"),TEXT("app-run-uneven-continuation.json")})
 {
  FString Raw;if(!FFileHelper::LoadFileToString(Raw,*(Folder/Name))){State->Error=FString(TEXT("Missing existing canonical continuation fixture: "))+Name;return false;}
  const auto Fixture=Parse(Raw);const TSharedPtr<FJsonObject>* Original=nullptr;
  if(!Fixture||!Fixture->TryGetObjectField(TEXT("request"),Original)){State->Error=TEXT("Invalid canonical continuation fixture");return false;}
  auto Request=MakeShared<FJsonObject>(**Original);Request->SetNumberField(TEXT("frames"),37);
  for(const TCHAR* Key:{TEXT("roots"),TEXT("rootYawDegrees")})
  {FValues Rows=Request->GetArrayField(Key);if(Rows.Num()<46){State->Error=TEXT("Canonical fixture has insufficient future roots");return false;}Rows.SetNum(46);Request->SetArrayField(Key,Rows);}
  const FString Json=Text(Request);TSharedPtr<FJsonObject> Full,Lower;FProphecyFootIKNN::FGenerateTiming FullTiming,LowerTiming;
  UE_LOG(LogTemp,Display,TEXT("Foot IK live lower fixture BEGIN %s"),Name);
  if(!State->Full.GenerateResult(Json,Full,State->Error,&FullTiming)||!State->Lower.GenerateResult(Json,Lower,State->Error,&LowerTiming)||!Compare(Full,Lower,*State))return false;
  if(FullTiming.Inferences!=37||LowerTiming.Inferences!=37){State->Error=TEXT("Live lower changed encoder/continuation inference count");return false;}
  if(State->Cases.IsEmpty())
  {
   int32 Checks=0;TSharedPtr<FJsonObject> Aborted,Resumed;FProphecyFootIKNN::FGenerateTiming InterruptedTiming;
   if(State->Lower.GenerateResult(Json,Aborted,Error,&InterruptedTiming,[&]{return ++Checks>5;})||Aborted||
      !Error.Contains(TEXT("superseded"))||InterruptedTiming.Inferences<=0||InterruptedTiming.Inferences>=37)
   {State->Error=TEXT("Obsolete continuation did not retire between policy inferences");return false;}
   if(!State->Lower.GenerateResult(Json,Resumed,State->Error)||Text(Resumed)!=Text(Lower))
   {State->Error=TEXT("Retiring an obsolete continuation changed the next exact forecast");return false;}
   UE_LOG(LogTemp,Display,TEXT("Foot IK obsolete forecast retired after %d inferences; next full continuation exact"),InterruptedTiming.Inferences);
  }
  State->FullSeconds+=FullTiming.OrtSeconds;State->LowerSeconds+=LowerTiming.OrtSeconds;
  auto Row=MakeShared<FJsonObject>();Row->SetStringField(TEXT("fixture"),Name);Row->SetNumberField(TEXT("frames"),37);Row->SetNumberField(TEXT("fullOrtMs"),FullTiming.OrtSeconds*1000);Row->SetNumberField(TEXT("lowerOrtMs"),LowerTiming.OrtSeconds*1000);State->Cases.Add(MakeShared<FJsonValueObject>(Row));
  UE_LOG(LogTemp,Display,TEXT("Foot IK live lower fixture END %s exact; full %.3fms lower %.3fms"),Name,FullTiming.OrtSeconds*1000,LowerTiming.OrtSeconds*1000);
  Request->SetNumberField(TEXT("frames"),2);FProphecyFootIKNN::FGenerateTiming RejectedTiming;
  if(State->Lower.Generate(Text(Request),Output,Error,&RejectedTiming)||RejectedTiming.Inferences!=0||!Error.Contains(TEXT("surface stream")))
  {State->Error=TEXT("Private lower graph accepted stream generation or began inference before rejection");return false;}++State->RejectedMisuses;
 }
 State->Lower.Cancel();FProphecyFootIKNN::FGenerateTiming CancelTiming;
 if(State->Lower.Generate(TEXT("{}"),Output,Error,&CancelTiming)||CancelTiming.Inferences!=0||!Error.Contains(TEXT("cancelled"))){State->Error=TEXT("Cancelled private forecast continued inference");return false;}++State->RejectedMisuses;
 return true;
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FFootIKLiveLowerForecastTest,"Prophecy.FootIK.NN.LiveLowerForecast",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FFootIKLiveLowerForecastTest::RunTest(const FString& Parameters)
{
 using namespace FootIKLiveLowerTest;(void)Parameters;
 FProphecyFootIKNN Invalid;FString Error;
 TestFalse(TEXT("Private lower graph rejects an unvalidated coordinate context"),Invalid.Prepare(TEXT("{\"direction\":\"backward\",\"liveLowerOnly\":true}"),Error));TestTrue(TEXT("Nonforward rejection is explicit"),Error.Contains(TEXT("forward")));
 TestFalse(TEXT("Private lower flag must be boolean"),Invalid.Prepare(TEXT("{\"liveLowerOnly\":\"true\"}"),Error));
 auto State=MakeShared<FState,ESPMode::ThreadSafe>();
 if(!State->Full.Prepare(TEXT("{\"gait\":\"run\",\"direction\":\"forward\"}"),Error)||!State->Lower.Prepare(TEXT("{\"gait\":\"run\",\"direction\":\"forward\",\"liveLowerOnly\":true}"),Error)){AddError(Error);return false;}
 const FString Folder=FPaths::ProjectSavedDir()/TEXT("Diagnostics/FootIKPort20261030/NN");
 auto Job=Async(EAsyncExecution::ThreadPool,[State,Folder]{return FootIKLiveLowerTest::Run(State,Folder);});
 // Only the worker captures the state. On timeout cancellation cannot leave a
 // dangling stack reference, and no further inference starts after its stop.
 if(!Job.WaitFor(FTimespan::FromSeconds(120))){State->Full.Cancel();State->Lower.Cancel();AddError(TEXT("Live lower actual-engine test exceeded its 120s cold-load watchdog"));return false;}
 const bool Passed=Job.Get();if(!Passed)AddError(State->Error);
 TestEqual(TEXT("Six existing terrain/gait seed pairs covered at the unchanged horizon"),State->Frames,222);
 TestEqual(TEXT("Initializer, warmup, stream and canceled misuse paths reject"),State->RejectedMisuses,10);
 TestEqual(TEXT("All authoritative outputs are identical in the same engine ORT"),State->Maximum,0.);
 auto Receipt=MakeShared<FJsonObject>();Receipt->SetBoolField(TEXT("passed"),Passed&&!HasAnyErrors());Receipt->SetNumberField(TEXT("frames"),State->Frames);Receipt->SetNumberField(TEXT("floatValues"),State->Numbers);Receipt->SetNumberField(TEXT("maximumDifference"),State->Maximum);Receipt->SetNumberField(TEXT("fullOrtMs"),State->FullSeconds*1000);Receipt->SetNumberField(TEXT("lowerOrtMs"),State->LowerSeconds*1000);Receipt->SetArrayField(TEXT("cases"),State->Cases);Receipt->SetStringField(TEXT("scope"),TEXT("Actual engine ORT authoritative lower/root/pins; full source and slide graphs unchanged; upper publication tested independently"));
 FFileHelper::SaveStringToFile(Text(Receipt),*(Folder/TEXT("native-live-lower-summary.json")));
 return Passed&&!HasAnyErrors();
}
#endif
