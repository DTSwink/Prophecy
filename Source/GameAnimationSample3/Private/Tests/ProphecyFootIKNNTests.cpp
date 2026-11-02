#include "ProphecyFootIKNN.h"
#include "Async/Async.h"
#include "Dom/JsonObject.h"
#include "HAL/FileManager.h"
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Policies/CondensedJsonPrintPolicy.h"
#include "Serialization/JsonSerializer.h"
#include <limits>

#if WITH_DEV_AUTOMATION_TESTS
namespace FootIKNNTest
{
using FValues=TArray<TSharedPtr<FJsonValue>>;
static FString Text(const TSharedPtr<FJsonObject>& O){FString S;FJsonSerializer::Serialize(O,TJsonWriterFactory<>::Create(&S));return S;}
static FString CompactText(const TSharedPtr<FJsonObject>& O){FString S;FJsonSerializer::Serialize(O,TJsonWriterFactory<TCHAR,TCondensedJsonPrintPolicy<TCHAR>>::Create(&S));return S;}
static TSharedPtr<FJsonObject> Parse(const FString& S){TSharedPtr<FJsonObject> O;FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(S),O);return O;}
static bool SameData(const TSharedPtr<FJsonValue>& A,const TSharedPtr<FJsonValue>& B)
{
 if(!A||!B||A->Type!=B->Type)return false;
 switch(A->Type)
 {
 case EJson::Null:return true;
 case EJson::Boolean:return A->AsBool()==B->AsBool();
 case EJson::String:return A->AsString()==B->AsString();
 case EJson::Number:{const double X=A->AsNumber(),Y=B->AsNumber();return FMemory::Memcmp(&X,&Y,sizeof(double))==0;}
 case EJson::Array:{const auto& X=A->AsArray();const auto& Y=B->AsArray();if(X.Num()!=Y.Num())return false;for(int32 I=0;I<X.Num();++I)if(!SameData(X[I],Y[I]))return false;return true;}
 case EJson::Object:{const auto X=A->AsObject(),Y=B->AsObject();if(!X||!Y||X->Values.Num()!=Y->Values.Num())return false;for(const auto& Field:X->Values){const auto* Other=Y->Values.Find(Field.Key);if(!Other||!SameData(Field.Value,*Other))return false;}return true;}
 default:return false;
 }
}
static bool SameObject(const TSharedPtr<FJsonObject>& A,const TSharedPtr<FJsonObject>& B)
{return A&&B&&SameData(MakeShared<FJsonValueObject>(A),MakeShared<FJsonValueObject>(B));}
static void Numbers(const TSharedPtr<FJsonValue>& V,TArray<double>& A){if(V->Type==EJson::Number)A.Add(V->AsNumber());else if(V->Type==EJson::Array)for(const auto& I:V->AsArray())Numbers(I,A);}
static double Difference(const TSharedPtr<FJsonValue>& A,const TSharedPtr<FJsonValue>& B){TArray<double> X,Y;Numbers(A,X);Numbers(B,Y);if(X.Num()!=Y.Num())return 1e9;double D=0;for(int32 I=0;I<X.Num();I++)D=FMath::Max(D,FMath::Abs(X[I]-Y[I]));return D;}
static double PoseDifference(const TSharedPtr<FJsonObject>& A,const TSharedPtr<FJsonObject>& B){return FMath::Max(Difference(A->Values[TEXT("points")],B->Values[TEXT("points")]),Difference(A->Values[TEXT("axes")],B->Values[TEXT("axes")]));}
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FFootIKNNJsonTransportTest,"Prophecy.FootIK.NN.JsonTransport",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FFootIKNNJsonTransportTest::RunTest(const FString& Parameters)
{
 using namespace FootIKNNTest;(void)Parameters;
 auto Edge=MakeShared<FJsonObject>();FValues Values;
 for(double V:{0.,-0.,std::numeric_limits<double>::denorm_min(),std::numeric_limits<double>::min(),std::numeric_limits<double>::max(),-std::numeric_limits<double>::max(),1.+std::numeric_limits<double>::epsilon(),9007199254740991.,double(float(.1)),double(float(-.7))})Values.Add(MakeShared<FJsonValueNumber>(V));
 Values.Add(MakeShared<FJsonValueNull>());Values.Add(MakeShared<FJsonValueBoolean>(true));Values.Add(MakeShared<FJsonValueString>(TEXT("quote\" slash\\ newline\n \u03b1")));Edge->SetArrayField(TEXT("values"),Values);Edge->SetObjectField(TEXT("empty"),MakeShared<FJsonObject>());
 const FString Pretty=Text(Edge),Compact=CompactText(Edge);
 TestTrue(TEXT("Compact transport removes only formatting"),Compact.Len()<Pretty.Len());
 TestTrue(TEXT("Parsed edge-case values including signed zero are bit-exact"),SameObject(Parse(Pretty),Parse(Compact)));
 TestTrue(TEXT("Structured edge-case values equal the former JSON round-trip"),SameObject(Edge,Parse(Pretty)));
 const FString Folder=FPaths::ProjectSavedDir()/TEXT("Diagnostics/FootIKPort20261030/NN");TArray<FString> Files;IFileManager::Get().FindFiles(Files,*(Folder/TEXT("*.json")),true,false);int32 Cases=0;
 for(const auto& Name:Files)
 {
  FString Raw;if(!FFileHelper::LoadFileToString(Raw,*(Folder/Name)))continue;const auto Fixture=Parse(Raw);const TSharedPtr<FJsonObject>* Expected=nullptr;if(!Fixture||!Fixture->TryGetObjectField(TEXT("expected"),Expected))continue;
  TestTrue(Name+TEXT(" compact versus pretty parsed payload"),SameObject(Parse(Text(*Expected)),Parse(CompactText(*Expected))));
  TestTrue(Name+TEXT(" direct structured payload preserves every value"),SameObject(*Expected,Parse(Text(*Expected))));++Cases;
 }
 TestTrue(TEXT("Canonical source and continuation payloads covered without inference"),Cases>=6);return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FFootIKNNFrozenStreamTest,"Prophecy.FootIK.NN.FrozenRootWindowAndSource",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FFootIKNNFrozenStreamTest::RunTest(const FString& Parameters)
{
 using namespace FootIKNNTest;(void)Parameters;
 const FString Folder=FPaths::ProjectSavedDir()/TEXT("Diagnostics/FootIKPort20261030/NN");TArray<FString> Files;IFileManager::Get().FindFiles(Files,*(Folder/TEXT("*.json")),true,false);Files.Sort();
 // One direction's graph sessions at a time; gait/phase/reset fixtures reuse
 // them. Keep memory bounded instead of retaining all four model sets.
 TMap<FString,FString> DirectionByFile;
 for(const FString& Name:Files){FString Raw;if(!FFileHelper::LoadFileToString(Raw,*(Folder/Name)))continue;const auto Fixture=Parse(Raw);const TSharedPtr<FJsonObject>* Settings=nullptr;if(Fixture&&Fixture->TryGetObjectField(TEXT("settings"),Settings)){FString Direction=TEXT("forward");(*Settings)->TryGetStringField(TEXT("direction"),Direction);DirectionByFile.Add(Name,Direction);}}
 Files.StableSort([&](const FString& A,const FString& B){const FString DA=DirectionByFile.FindRef(A),DB=DirectionByFile.FindRef(B);return DA==DB?A<B:DA<DB;});
 int32 Fixtures=0,Poses=0,ResetCases=0,ContinuationCases=0;double Maximum=0;auto Receipt=MakeShared<FJsonObject>();FValues Cases;
 FProphecyFootIKNN NN;
 for(const auto& Name:Files)
 {
  FString Raw,Error,Out;if(!FFileHelper::LoadFileToString(Raw,*(Folder/Name)))continue;auto Fixture=Parse(Raw);FString Kind;if(!Fixture||!Fixture->TryGetStringField(TEXT("kind"),Kind)||(Kind!=TEXT("initialize")&&Kind!=TEXT("stream")&&Kind!=TEXT("continuation")))continue;
  const double Began=FPlatformTime::Seconds();UE_LOG(LogTemp,Display,TEXT("Foot IK NN fixture BEGIN %s (%s)"),*Name,*Kind);
  const double Tolerance=Fixture->GetNumberField(TEXT("tolerance"));double ErrorMax=0;
  auto Job=Async(EAsyncExecution::ThreadPool,[&]{
   // The production owner warms private sessions off the game thread without
   // advancing a seed or a retained stream. The same fixtures validate both.
   if(!NN.Prepare(Text(Fixture->GetObjectField(TEXT("settings"))),Error)||!NN.PrewarmSessions(Error))return false;
   if(Kind==TEXT("initialize"))
   {
    if(!NN.Initialize(Out,Error))return false;const auto Actual=Parse(Out),Expected=Fixture->GetObjectField(TEXT("expected"));if(!Actual){Error=TEXT("Invalid native source JSON");return false;}
    const auto& A=Actual->GetArrayField(TEXT("poses"));const auto& E=Expected->GetArrayField(TEXT("poses"));if(A.Num()!=E.Num()){Error=TEXT("Native source frame count differs");return false;}
    for(int32 I=0;I<A.Num();I++)ErrorMax=FMath::Max(ErrorMax,PoseDifference(A[I]->AsObject(),E[I]->AsObject()));
    ErrorMax=FMath::Max(ErrorMax,Difference(Actual->Values[TEXT("roots")],Expected->Values[TEXT("roots")]));ErrorMax=FMath::Max(ErrorMax,Difference(Actual->Values[TEXT("rootYawDegrees")],Expected->Values[TEXT("rootYawDegrees")]));
    ErrorMax=FMath::Max(ErrorMax,FMath::Abs(Actual->GetNumberField(TEXT("referenceHeight"))-Expected->GetObjectField(TEXT("directionMeta"))->GetNumberField(TEXT("referenceHeight"))));Poses+=A.Num();
   }
   else if(Kind==TEXT("continuation"))
   {
    TSharedPtr<FJsonObject> Actual;if(!NN.GenerateResult(Text(Fixture->GetObjectField(TEXT("request"))),Actual,Error))return false;const auto Expected=Fixture->GetObjectField(TEXT("expected"));
    if(!SameObject(Actual,Parse(Text(Actual)))||!SameObject(Actual,Parse(CompactText(Actual)))){Error=TEXT("Structured continuation differs from the previous parsed numeric payload");return false;}
    const auto& A=Actual->GetArrayField(TEXT("poses"));const auto& E=Expected->GetArrayField(TEXT("poses"));if(A.Num()!=E.Num()||Actual->GetNumberField(TEXT("inferences"))!=E.Num()-1||Actual->GetNumberField(TEXT("fps"))!=30){Error=TEXT("Native continuation frame contract differs");return false;}
    if(PoseDifference(A[0]->AsObject(),E[0]->AsObject())!=0){Error=TEXT("Native continuation changed the supplied current pose");return false;}
    for(int32 I=0;I<A.Num();I++)ErrorMax=FMath::Max(ErrorMax,PoseDifference(A[I]->AsObject(),E[I]->AsObject()));
    for(const TCHAR* Key:{TEXT("roots"),TEXT("rootYawDegrees"),TEXT("pins")})ErrorMax=FMath::Max(ErrorMax,Difference(Actual->Values[Key],Expected->Values[Key]));Poses+=A.Num();ContinuationCases++;
   }
   else
   {
    for(const auto& Row:Fixture->GetArrayField(TEXT("steps")))
    {
     if(!NN.PrewarmSessions(Error))return false;
     const auto Item=Row->AsObject(),Request=Item->GetObjectField(TEXT("request"));if(!NN.Generate(Text(Request),Out,Error))return false;const auto Actual=Parse(Out),Expected=Item->GetObjectField(TEXT("expected"));if(!Actual){Error=TEXT("Invalid native stream JSON");return false;}
     ErrorMax=FMath::Max(ErrorMax,PoseDifference(Actual->GetObjectField(TEXT("pose")),Expected->GetObjectField(TEXT("pose"))));ErrorMax=FMath::Max(ErrorMax,Difference(Actual->Values[TEXT("pins")],Expected->Values[TEXT("pins")]));Poses++;bool Reset=false;if(Request->TryGetBoolField(TEXT("reset"),Reset)&&Reset)ResetCases++;
    }
   }
   return true;
  });
  if(!Job.Get()){AddError(Name+TEXT(": ")+Error);return false;}TestTrue(Name+TEXT(" frozen policy/source parity"),ErrorMax<=Tolerance);Maximum=FMath::Max(Maximum,ErrorMax);Fixtures++;
  UE_LOG(LogTemp,Display,TEXT("Foot IK NN fixture END %s %.3fs error %.9g tolerance %.9g"),*Name,FPlatformTime::Seconds()-Began,ErrorMax,Tolerance);
  auto Row=MakeShared<FJsonObject>();Row->SetStringField(TEXT("fixture"),Name);Row->SetNumberField(TEXT("maxAbsoluteError"),ErrorMax);Row->SetNumberField(TEXT("tolerance"),Tolerance);Cases.Add(MakeShared<FJsonValueObject>(Row));
  NN.Cancel();TestFalse(TEXT("Cancelled native NN does not begin another inference"),NN.Generate(TEXT("{}"),Out,Error));TestTrue(TEXT("Cancellation is reported"),Error.Contains(TEXT("cancelled")));
  TestFalse(TEXT("Cancelled session warming cannot resume inference"),NN.PrewarmSessions(Error));
 }
 TestTrue(TEXT("All four direction contexts and both gait commands covered"),Fixtures>=12);TestEqual(TEXT("Reset from both history poses covered for every direction"),ResetCases,4);
 TestEqual(TEXT("Whole-app post-terrain continuation covered for walk/run stairs/down/uneven"),ContinuationCases,6);
 Receipt->SetNumberField(TEXT("fixtures"),Fixtures);Receipt->SetNumberField(TEXT("poses"),Poses);Receipt->SetNumberField(TEXT("maxAbsoluteError"),Maximum);Receipt->SetArrayField(TEXT("cases"),Cases);Receipt->SetBoolField(TEXT("passed"),!HasAnyErrors());FFileHelper::SaveStringToFile(Text(Receipt),*(Folder/TEXT("native-nne-summary.json")));
 AddInfo(FString::Printf(TEXT("Foot IK NNE: %d fixtures, %d poses, %d reset cases; max absolute error %.9g"),Fixtures,Poses,ResetCases,Maximum));return !HasAnyErrors();
}
#endif
