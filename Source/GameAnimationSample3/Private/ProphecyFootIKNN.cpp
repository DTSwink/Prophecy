#include "ProphecyFootIKNN.h"
#include "Async/Async.h"
#include "Dom/JsonObject.h"
#include "HAL/CriticalSection.h"
#include "HAL/ThreadSafeBool.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/ScopeLock.h"
#include "Misc/ScopeExit.h"
#include "Misc/SecureHash.h"
#include "Policies/CondensedJsonPrintPolicy.h"
#include "HAL/PlatformProcess.h"
#include "HAL/PlatformTime.h"
THIRD_PARTY_INCLUDES_START
// Pure C ABI: no Ort::InitApi/global C++ wrapper state or exceptions are used.
#include "onnxruntime_c_api.h"
THIRD_PARTY_INCLUDES_END
#include "Serialization/JsonSerializer.h"

namespace FootIKNN
{
constexpr int32 Bodies=25,StateWidth=370,SeedInput=641,SeedOutput=373,StepInput=413,WindowRows=10;
using FValues=TArray<TSharedPtr<FJsonValue>>;
static TSharedPtr<FJsonObject> Parse(const FString& Text)
{TSharedPtr<FJsonObject> O;return FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),O)?O:nullptr;}
static bool Serialize(const TSharedPtr<FJsonObject>& O,FString& Text)
{return FJsonSerializer::Serialize(O,TJsonWriterFactory<TCHAR,TCondensedJsonPrintPolicy<TCHAR>>::Create(&Text));}
static bool Number(const TSharedPtr<FJsonValue>& V,float& Out)
{double X=0;if(!V||!V->TryGetNumber(X)||!FMath::IsFinite(X))return false;Out=float(X);return FMath::IsFinite(Out);}
static bool Vector(const TSharedPtr<FJsonValue>& V,float* Out)
{const FValues* A=nullptr;if(!V||!V->TryGetArray(A)||A->Num()!=3)return false;for(int32 I=0;I<3;I++)if(!Number((*A)[I],Out[I]))return false;return true;}
static FValues Values(const float* P,int32 N)
{FValues A;A.Reserve(N);for(int32 I=0;I<N;I++)A.Add(MakeShared<FJsonValueNumber>(P[I]));return A;}
static void Copy(float* To,const float* From,int32 Count){FMemory::Memcpy(To,From,Count*sizeof(float));}
static bool Cancelled(const FThreadSafeBool& Flag,FString& Error)
{if(!Flag)return false;Error=TEXT("Foot IK NN generation cancelled");return true;}
static bool Window(const TSharedPtr<FJsonObject>& R,TArray<float>& Out,FString& Error)
{
 const FValues* Roots=nullptr;const FValues* Yaw=nullptr;
 if(!R->TryGetArrayField(TEXT("roots"),Roots)||!R->TryGetArrayField(TEXT("rootYawDegrees"),Yaw)||Roots->Num()<WindowRows||Yaw->Num()<WindowRows){Error=TEXT("Foot IK NN requires previous/current plus eight future roots and headings");return false;}
 Out.SetNumUninitialized(40);for(int32 I=0;I<WindowRows;I++)if(!Vector((*Roots)[I],Out.GetData()+I*3)||!Number((*Yaw)[I],Out[30+I])){Error=TEXT("Foot IK NN root window contains an invalid value");return false;}return true;
}
static bool SeedInputValues(const FValues& Seeds,const TArray<float>& Window,bool bNormalize,TArray<float>& Out,FString& Error)
{
 if(Seeds.Num()!=2){Error=TEXT("Foot IK NN needs two complete history poses");return false;}
 Out.SetNumUninitialized(SeedInput);
 for(int32 I=0;I<2;I++)
 {
  const auto O=Seeds[I]->AsObject();const FValues* P=nullptr;const FValues* A=nullptr;
  if(!O||!O->TryGetArrayField(TEXT("points"),P)||!O->TryGetArrayField(TEXT("axes"),A)||P->Num()!=Bodies+1||A->Num()!=Bodies+1){Error=TEXT("Foot IK NN seed must contain the 26 named body points and row axes");return false;}
  for(int32 J=0;J<Bodies;J++)
  {
   if(!Vector((*P)[J+1],Out.GetData()+I*75+J*3)){Error=TEXT("Invalid Foot IK NN seed point");return false;}
   const FValues* Basis=nullptr;if(!(*A)[J+1]->TryGetArray(Basis)||Basis->Num()!=3){Error=TEXT("Invalid Foot IK NN seed axes");return false;}
   for(int32 K=0;K<3;K++)if(!Vector((*Basis)[K],Out.GetData()+150+I*225+J*9+K*3)){Error=TEXT("Nonfinite Foot IK NN seed axes");return false;}
  }
 }
 Copy(Out.GetData()+600,Window.GetData(),40);Out[640]=bNormalize?1.f:0.f;return true;
}
static TSharedPtr<FJsonObject> Pose(const float* Output,bool bVirtualRoot,const float* Offset=nullptr)
{
 auto O=MakeShared<FJsonObject>();FValues Points,Axes;
 if(bVirtualRoot){Points.Add(MakeShared<FJsonValueArray>(Values(Output+370,3)));Axes.Add(MakeShared<FJsonValueArray>(FValues{MakeShared<FJsonValueArray>(FValues{MakeShared<FJsonValueNumber>(1),MakeShared<FJsonValueNumber>(0),MakeShared<FJsonValueNumber>(0)}),MakeShared<FJsonValueArray>(FValues{MakeShared<FJsonValueNumber>(0),MakeShared<FJsonValueNumber>(1),MakeShared<FJsonValueNumber>(0)}),MakeShared<FJsonValueArray>(FValues{MakeShared<FJsonValueNumber>(0),MakeShared<FJsonValueNumber>(0),MakeShared<FJsonValueNumber>(1)})}));}
 for(int32 I=0;I<Bodies;I++)
 {
  float Point[3];for(int32 K=0;K<3;K++)Point[K]=Output[373+I*3+K]-(Offset?Offset[K]:0.f);Points.Add(MakeShared<FJsonValueArray>(Values(Point,3)));
  FValues Basis;for(int32 K=0;K<3;K++)Basis.Add(MakeShared<FJsonValueArray>(Values(Output+448+I*9+K*3,3)));Axes.Add(MakeShared<FJsonValueArray>(Basis));
 }
 O->SetArrayField(TEXT("points"),Points);O->SetArrayField(TEXT("axes"),Axes);return O;
}
struct FOrt
{
 const OrtApi* Api=nullptr;
 FOrt()
 {
  const FString Library=FPaths::EnginePluginsDir()/TEXT("NNE/NNERuntimeORT/Binaries/ThirdParty/Onnxruntime/Win64/onnxruntime.dll");
  void* Dll=FPlatformProcess::GetDllHandle(*Library);if(!Dll)return;
  using FGetApi=const OrtApiBase*(ORT_API_CALL*)();const auto Get=reinterpret_cast<FGetApi>(FPlatformProcess::GetDllExport(Dll,TEXT("OrtGetApiBase")));if(Get)Api=Get()->GetApi(ORT_API_VERSION);
  // The engine's shared ORT DLL stays loaded with the module. Only private
  // sessions/environments below are owned by this feature.
 }
 bool Check(OrtStatus* Status,FString& Error) const
 {if(!Status)return true;Error=UTF8_TO_TCHAR(Api->GetErrorMessage(Status));Api->ReleaseStatus(Status);return false;}
};
static FOrt& Ort(){static FOrt Value;return Value;}
struct FModel
{
 TArray64<uint8> Bytes;OrtSession* Session=nullptr;OrtEnv* Environment=nullptr;OrtMemoryInfo* Memory=nullptr;
 FString Path;int32 InputWidth=0,OutputWidth=0;
 ~FModel(){const auto* A=Ort().Api;if(A){if(Session)A->ReleaseSession(Session);if(Memory)A->ReleaseMemoryInfo(Memory);if(Environment)A->ReleaseEnv(Environment);}}
 bool Prepare(const FString& InPath,int32 In,int32 Out,FString& Error)
 {
  Path=InPath;
  if(!FFileHelper::LoadFileToArray(Bytes,*Path)){Error=TEXT("Missing frozen Foot IK NN graph: ")+Path;return false;}
  if(!Ort().Api){Error=TEXT("Engine ONNX Runtime C API is unavailable");return false;}InputWidth=In;OutputWidth=Out;return true;
 }
 bool Initialize(const FThreadSafeBool& Stop,FString& Error)
 {
  if(Cancelled(Stop,Error))return false;if(Session)return true;
  auto& O=Ort();const auto* A=O.Api;OrtSessionOptions* Options=nullptr;
  OrtEnv* NewEnvironment=nullptr;OrtMemoryInfo* NewMemory=nullptr;OrtSession* NewSession=nullptr;
  ON_SCOPE_EXIT{if(NewSession)A->ReleaseSession(NewSession);if(NewMemory)A->ReleaseMemoryInfo(NewMemory);if(NewEnvironment)A->ReleaseEnv(NewEnvironment);};
  if(!O.Check(A->CreateSessionOptions(&Options),Error))return false;ON_SCOPE_EXIT{A->ReleaseSessionOptions(Options);};
  if(!O.Check(A->SetIntraOpNumThreads(Options,1),Error)||!O.Check(A->SetInterOpNumThreads(Options,1),Error)||!O.Check(A->SetSessionExecutionMode(Options,ORT_SEQUENTIAL),Error)
   ||!O.Check(A->AddSessionConfigEntry(Options,"session.intra_op.allow_spinning","0"),Error)||!O.Check(A->AddSessionConfigEntry(Options,"session.inter_op.allow_spinning","0"),Error)
   ||!O.Check(A->SetSessionGraphOptimizationLevel(Options,ORT_ENABLE_ALL),Error)||!O.Check(A->CreateEnv(ORT_LOGGING_LEVEL_ERROR,"ProphecyFootIK",&NewEnvironment),Error)
   ||!O.Check(A->CreateCpuMemoryInfo(OrtArenaAllocator,OrtMemTypeDefault,&NewMemory),Error))return false;
  const double Start=FPlatformTime::Seconds();UE_LOG(LogTemp,Display,TEXT("Foot IK NN: initialize single-thread session %s"),*FPaths::GetCleanFilename(Path));
  if(!O.Check(A->CreateSessionFromArray(NewEnvironment,Bytes.GetData(),SIZE_T(Bytes.Num()),Options,&NewSession),Error))return false;
  size_t Count=0;if(!O.Check(A->SessionGetInputCount(NewSession,&Count),Error)||Count!=1){Error=TEXT("Foot IK NN input layout mismatch");return false;}
  if(!O.Check(A->SessionGetOutputCount(NewSession,&Count),Error)||Count!=1){Error=TEXT("Foot IK NN output layout mismatch");return false;}
  Environment=NewEnvironment;NewEnvironment=nullptr;Memory=NewMemory;NewMemory=nullptr;Session=NewSession;NewSession=nullptr;
  UE_LOG(LogTemp,Display,TEXT("Foot IK NN: ready %s in %.3fs (intra1/inter1, no spin)"),*FPaths::GetCleanFilename(Path),FPlatformTime::Seconds()-Start);
  Bytes.Empty();return !Cancelled(Stop,Error);
 }
 bool Run(TArray<float>& In,TArray<float>& Out,const FThreadSafeBool& Stop,FString& Error,FProphecyFootIKNN::FGenerateTiming* Timing=nullptr)
 {
  if(Cancelled(Stop,Error))return false;double Began=Timing?FPlatformTime::Seconds():0;
  if(!Initialize(Stop,Error))return false;if(Timing){Timing->InitializeSeconds+=FPlatformTime::Seconds()-Began;Began=FPlatformTime::Seconds();}
  if(In.Num()!=InputWidth){Error=TEXT("Foot IK NN input packing mismatch");return false;}
  auto& O=Ort();const auto* A=O.Api;Out.SetNumUninitialized(OutputWidth);const int64 InputShape[]={1,InputWidth},OutputShape[]={1,OutputWidth};OrtValue *Input=nullptr,*Output=nullptr;
  ON_SCOPE_EXIT{const double ReleaseStart=Timing?FPlatformTime::Seconds():0;if(Input)A->ReleaseValue(Input);if(Output)A->ReleaseValue(Output);if(Timing)Timing->TensorSeconds+=FPlatformTime::Seconds()-ReleaseStart;};
  if(!O.Check(A->CreateTensorWithDataAsOrtValue(Memory,In.GetData(),In.Num()*sizeof(float),InputShape,2,ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT,&Input),Error)
   ||!O.Check(A->CreateTensorWithDataAsOrtValue(Memory,Out.GetData(),Out.Num()*sizeof(float),OutputShape,2,ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT,&Output),Error))return false;
  const char* InputNames[]={"input"};const char* OutputNames[]={"output"};const OrtValue* Inputs[]={Input};
  if(Timing)Timing->TensorSeconds+=FPlatformTime::Seconds()-Began;
  if(Cancelled(Stop,Error))return false;Began=Timing?FPlatformTime::Seconds():0;
  OrtStatus* Status=A->Run(Session,nullptr,InputNames,Inputs,1,OutputNames,1,&Output);
  if(Timing){Timing->OrtSeconds+=FPlatformTime::Seconds()-Began;++Timing->Inferences;}
  if(!O.Check(Status,Error)||Cancelled(Stop,Error))return false;
  for(float X:Out)if(!FMath::IsFinite(X)){Error=TEXT("Foot IK NN produced a nonfinite value");return false;}return true;
 }
};
static double Setting(const TSharedPtr<FJsonObject>& O,const TCHAR* Name,double Default)
{double V=Default;O->TryGetNumberField(Name,V);return V;}
static int32 RoundEven(double X){const double Lo=FMath::FloorToDouble(X),Fraction=X-Lo;return int32(Lo)+(Fraction>.5||(Fraction==.5&&(int32(Lo)&1))?1:0);}
static bool LiveLowerContract(const FString& Folder,const TSharedPtr<FJsonObject>& SourceReceipt,const TArray64<uint8>& Candidate,FString& Error)
{
 FString Text;if(!FFileHelper::LoadFileToString(Text,*(Folder/TEXT("LiveLowerReceipt.json")))){Error=TEXT("Missing live lower Foot IK graph receipt");return false;}
 const auto Receipt=Parse(Text);const TSharedPtr<FJsonObject>* Resumes=nullptr;const TSharedPtr<FJsonObject>* Forward=nullptr;const TSharedPtr<FJsonObject>* Hashes=nullptr;
 FString Scope,Model,SourceModel,SourceHash,ExpectedHash,SourceSHA1,CandidateSHA1;double Schema=0,Input=0,Output=0;
 if(!Receipt||!Receipt->TryGetNumberField(TEXT("schema"),Schema)||Schema!=1||!Receipt->TryGetStringField(TEXT("scope"),Scope)||Scope!=TEXT("live-horizontal-forward")
  ||!Receipt->TryGetNumberField(TEXT("inputWidth"),Input)||Input!=413||!Receipt->TryGetNumberField(TEXT("outputWidth"),Output)||Output!=710
  ||!Receipt->TryGetStringField(TEXT("model"),Model)||Model!=TEXT("run-forward-live-lower-resume.onnx")
  ||!Receipt->TryGetStringField(TEXT("sourceModel"),SourceModel)||SourceModel!=TEXT("run-forward-resume.onnx")
  ||!Receipt->TryGetStringField(TEXT("sourceSha256"),ExpectedHash)||!Receipt->TryGetStringField(TEXT("sourceSha1"),SourceSHA1)||!Receipt->TryGetStringField(TEXT("sha1"),CandidateSHA1)
  ||!SourceReceipt->TryGetObjectField(TEXT("resumeGraphs"),Resumes)||!(*Resumes)->TryGetObjectField(TEXT("forward"),Forward)||!(*Forward)->TryGetObjectField(TEXT("sha256"),Hashes)
  ||!(*Hashes)->TryGetStringField(SourceModel,SourceHash)||!SourceHash.Equals(ExpectedHash,ESearchCase::IgnoreCase))
 {Error=TEXT("Live lower Foot IK graph does not match the validated full resume contract");return false;}
 // Core supports SHA1 byte verification on Windows. Retain SHA256 as the
 // source model contract used by the existing graph receipt, and verify both
 // deployed byte streams against the additional exact-build fingerprints.
 TArray64<uint8> Source;
 if(!FFileHelper::LoadFileToArray(Source,*(Folder/SourceModel))
  ||!FSHA1::HashBuffer(Source.GetData(),Source.Num()).ToString().Equals(SourceSHA1,ESearchCase::IgnoreCase)
  ||!FSHA1::HashBuffer(Candidate.GetData(),Candidate.Num()).ToString().Equals(CandidateSHA1,ESearchCase::IgnoreCase))
 {Error=TEXT("Live lower Foot IK source or candidate bytes differ from their verified receipt");return false;}
 return true;
}
}

struct FProphecyFootIKNN::FImpl
{
 FootIKNN::FModel Encoder,Step,Resume;TSharedPtr<FJsonObject> Settings,Bank;FootIKNN::FValues Names;
 TArray<float> State;FString Direction,Gait;int32 PinWidth=0;bool bInitialized=false,bPrepared=false,bLiveLowerOnly=false;
 FThreadSafeBool Stop=false;FCriticalSection Work;
 bool Encode(const FootIKNN::FValues& Seeds,const TArray<float>& Window,bool Normalize,TArray<float>& Encoded,FString& Error,FProphecyFootIKNN::FGenerateTiming* Timing=nullptr)
 {TArray<float> Input;return FootIKNN::SeedInputValues(Seeds,Window,Normalize,Input,Error)&&Encoder.Run(Input,Encoded,Stop,Error,Timing);}
 bool Advance(const TArray<float>& Window,const float* Origin,TArray<float>& Output,FString& Error,bool bResume=false,FProphecyFootIKNN::FGenerateTiming* Timing=nullptr)
 {if(bLiveLowerOnly&&!bResume){Error=TEXT("Live lower Foot IK forecasts cannot drive a surface stream");return false;}TArray<float> Input;Input.SetNumUninitialized(FootIKNN::StepInput);FootIKNN::Copy(Input.GetData(),State.GetData(),370);FootIKNN::Copy(Input.GetData()+370,Window.GetData(),40);FootIKNN::Copy(Input.GetData()+410,Origin,3);if(!(bResume?Resume:Step).Run(Input,Output,Stop,Error,Timing))return false;FootIKNN::Copy(State.GetData(),Output.GetData(),370);return true;}
};
FProphecyFootIKNN::FProphecyFootIKNN():Impl(MakeUnique<FImpl>()){}
FProphecyFootIKNN::~FProphecyFootIKNN()=default;
void FProphecyFootIKNN::Cancel(){Impl->Stop=true;}

bool FProphecyFootIKNN::Prepare(const FString& SettingsJson,FString& Error)
{
 using namespace FootIKNN;Error.Reset();
 auto Settings=Parse(SettingsJson);if(!Settings){Error=TEXT("Invalid Foot IK NN settings JSON");return false;}const TSharedPtr<FJsonObject>* Nested=nullptr;if(Settings->TryGetObjectField(TEXT("settings"),Nested))Settings=*Nested;
 auto Next=MakeUnique<FImpl>();Next->Settings=Settings;Next->Direction=TEXT("forward");Next->Gait=TEXT("walk");Settings->TryGetStringField(TEXT("direction"),Next->Direction);Settings->TryGetStringField(TEXT("gait"),Next->Gait);
 if((Next->Direction!=TEXT("forward")&&Next->Direction!=TEXT("backward")&&Next->Direction!=TEXT("left")&&Next->Direction!=TEXT("right"))||(Next->Gait!=TEXT("walk")&&Next->Gait!=TEXT("run"))){Error=TEXT("Invalid Foot IK command gait/direction");return false;}
 if(const auto* Flag=Settings->Values.Find(TEXT("liveLowerOnly")))
 {
  if(!Flag->IsValid()||(*Flag)->Type!=EJson::Boolean){Error=TEXT("Invalid private live lower forecast flag");return false;}
  Next->bLiveLowerOnly=(*Flag)->AsBool();
 }
 if(Next->bLiveLowerOnly&&Next->Direction!=TEXT("forward")){Error=TEXT("Live lower Foot IK forecasting requires the validated forward coordinate context");return false;}
 // Walk/run, phase and terrain settings share this direction's exact graphs.
 // Reset only recurrence/commands; avoid recompiling the same ORT sessions on
 // each lab reconfiguration or fixture. Never wait for inference on the GT.
 if(Impl->bPrepared&&Impl->Direction==Next->Direction&&Impl->bLiveLowerOnly==Next->bLiveLowerOnly)
 {
  if(!Impl->Work.TryLock()){Error=TEXT("Foot IK NN reconfiguration requires completed inference");return false;}
  ON_SCOPE_EXIT{Impl->Work.Unlock();};
  Impl->Settings=Settings;Impl->Gait=Next->Gait;Impl->State.Reset();Impl->bInitialized=false;Impl->Stop=false;return true;
 }
 const FString Folder=FPaths::ProjectContentDir()/TEXT("FootIKLab/NN"),Stem=TEXT("run-")+Next->Direction;FString Text;
 if(!FFileHelper::LoadFileToString(Text,*(Folder/(Stem+TEXT("-seed.json"))))||!(Next->Bank=Parse(Text))){Error=TEXT("Missing Foot IK directional seed bank: ")+Stem;return false;}
 const FValues* Names=nullptr;if(!Next->Bank->TryGetArrayField(TEXT("names"),Names)||Names->Num()!=Bodies){Error=TEXT("Invalid Foot IK NN bone order");return false;}Next->Names=*Names;
 if(!FFileHelper::LoadFileToString(Text,*(Folder/TEXT("Receipt.json")))){Error=TEXT("Missing Foot IK NN graph receipt");return false;}auto Receipt=Parse(Text);double Width=0,Pins=0;
 if(!Receipt||!Receipt->TryGetNumberField(TEXT("stepOutput"),Width)||!Receipt->TryGetNumberField(TEXT("pinWidth"),Pins)||Pins<1||Pins>8||Width!=673+Pins+35){Error=TEXT("Invalid Foot IK NN graph widths");return false;}Next->PinWidth=int32(Pins);
 const FString ResumeName=Next->bLiveLowerOnly?TEXT("run-forward-live-lower-resume.onnx"):Stem+TEXT("-resume.onnx");
 if(!Next->Encoder.Prepare(Folder/(Stem+TEXT("-seed.onnx")),SeedInput,SeedOutput,Error)||
    (!Next->bLiveLowerOnly&&!Next->Step.Prepare(Folder/(Stem+TEXT("-step.onnx")),StepInput,int32(Width),Error))||
    !Next->Resume.Prepare(Folder/ResumeName,StepInput,int32(Width),Error))return false;
 if(Next->bLiveLowerOnly&&!LiveLowerContract(Folder,Receipt,Next->Resume.Bytes,Error))return false;
 Next->bPrepared=true;Impl=MoveTemp(Next);return true;
}

bool FProphecyFootIKNN::PrewarmSessions(FString& Error,EProphecyFootIKNNWarmup Mode)
{
 using namespace FootIKNN;FScopeLock Lock(&Impl->Work);Error.Reset();
 if(!Impl->bPrepared){Error=TEXT("Prepare Foot IK NN before warming sessions");return false;}
 if(Impl->bLiveLowerOnly&&Mode!=EProphecyFootIKNNWarmup::Continuation){Error=TEXT("Live lower Foot IK only supports horizontal forecast continuation sessions");return false;}
 if(Cancelled(Impl->Stop,Error))return false;
 return Impl->Encoder.Initialize(Impl->Stop,Error)
  &&(Mode==EProphecyFootIKNNWarmup::Continuation||Impl->Step.Initialize(Impl->Stop,Error))
  &&(Mode==EProphecyFootIKNNWarmup::Stream||Impl->Resume.Initialize(Impl->Stop,Error))
  &&!Cancelled(Impl->Stop,Error);
}

bool FProphecyFootIKNN::Generate(const FString& RequestJson,FString& OutResponseJson,FString& Error,FGenerateTiming* Timing)
{
 OutResponseJson.Reset();TSharedPtr<FJsonObject> Result;
 if(!GenerateResult(RequestJson,Result,Error,Timing))return false;
 const double Began=Timing?FPlatformTime::Seconds():0;
 const bool Okay=FootIKNN::Serialize(Result,OutResponseJson);
 if(Timing){const double Elapsed=FPlatformTime::Seconds()-Began;Timing->SerializeSeconds+=Elapsed;Timing->TotalSeconds+=Elapsed;}
 return Okay;
}

bool FProphecyFootIKNN::GenerateResult(const FString& RequestJson,TSharedPtr<FJsonObject>& OutResponse,FString& Error,FGenerateTiming* Timing,const TFunction<bool()>& Superseded)
{
 using namespace FootIKNN;FScopeLock Lock(&Impl->Work);if(Timing)*Timing={};const double Began=Timing?FPlatformTime::Seconds():0;
 ON_SCOPE_EXIT{if(Timing)Timing->TotalSeconds=FPlatformTime::Seconds()-Began;};
 const auto Write=[&](const TSharedPtr<FJsonObject>& Result){OutResponse=Result;return true;};
 OutResponse.Reset();Error.Reset();if(!Impl->bPrepared){Error=TEXT("Prepare Foot IK NN before generation");return false;}if(Cancelled(Impl->Stop,Error))return false;
 const auto Obsolete=[&]{if(Superseded&&Superseded()){Error=TEXT("Foot IK forecast superseded");return true;}return false;};
 if(Obsolete())return false;
 const double ParseStart=Timing?FPlatformTime::Seconds():0;auto R=Parse(RequestJson);if(Timing)Timing->ParseSeconds=FPlatformTime::Seconds()-ParseStart;
 if(!R){Error=TEXT("Invalid Foot IK NN request JSON");return false;}FString Direction=Impl->Direction,Policy=TEXT("run");R->TryGetStringField(TEXT("direction"),Direction);R->TryGetStringField(TEXT("policy"),Policy);bool Drawn=false;R->TryGetBoolField(TEXT("drawn"),Drawn);
 if(Direction!=Impl->Direction||Policy!=TEXT("run")||Drawn){Error=TEXT("Foot IK NN request differs from the frozen directional unarmed Run policy");return false;}
 TArray<float> Window,Output;if(!FootIKNN::Window(R,Window,Error))return false;bool Reset=false;R->TryGetBoolField(TEXT("reset"),Reset);
 double CountValue=2;R->TryGetNumberField(TEXT("frames"),CountValue);
 if(!FMath::IsFinite(CountValue)||CountValue<2||CountValue>18002||CountValue!=FMath::FloorToDouble(CountValue)){Error=TEXT("Invalid Foot IK continuation frame count");return false;}
 if(Impl->bLiveLowerOnly&&CountValue<=2){Error=TEXT("Live lower Foot IK cannot publish a surface stream pose");return false;}
 if(CountValue>2)
 {
  // Handoff.prepare uses /resume, a separate course seeded by BOTH corrected
  // poses. Preserve the retained surface stream if this callback is shared.
  const int32 Count=int32(CountValue);const FValues* Names=nullptr;const FValues* Seeds=nullptr;const FValues* Roots=nullptr;const FValues* Yaws=nullptr;
  if(!R->TryGetArrayField(TEXT("names"),Names)||Names->Num()!=Bodies+1||(*Names)[0]->AsString()!=TEXT("root")||!R->TryGetArrayField(TEXT("seeds"),Seeds)||Seeds->Num()!=2||!R->TryGetArrayField(TEXT("roots"),Roots)||!R->TryGetArrayField(TEXT("rootYawDegrees"),Yaws)||Roots->Num()<Count+9||Yaws->Num()!=Roots->Num())
  {Error=TEXT("Foot IK continuation needs two full history poses and a complete future course");return false;}
  for(int32 I=0;I<Bodies;I++)if((*Names)[I+1]->AsString()!=Impl->Names[I]->AsString()){Error=TEXT("Foot IK continuation bone order differs");return false;}
  TArray<float> SavedState=MoveTemp(Impl->State);const bool WasInitialized=Impl->bInitialized;
  ON_SCOPE_EXIT{Impl->State=MoveTemp(SavedState);Impl->bInitialized=WasInitialized;};
  if(!Impl->Encode(*Seeds,Window,true,Output,Error,Timing))return false;
  float Origin[3];Copy(Origin,Output.GetData()+370,3);Impl->State.SetNumUninitialized(370);Copy(Impl->State.GetData(),Output.GetData(),370);
  const auto Seed=(*Seeds)[1]->AsObject();auto First=MakeShared<FJsonObject>();FValues FirstPoints,FirstAxes;for(int32 I=1;I<=Bodies;I++){FirstPoints.Add(Seed->GetArrayField(TEXT("points"))[I]);FirstAxes.Add(Seed->GetArrayField(TEXT("axes"))[I]);}First->SetArrayField(TEXT("points"),FirstPoints);First->SetArrayField(TEXT("axes"),FirstAxes);
  FValues Poses,VisibleRoots,VisibleYaw,Pins;Poses.Reserve(Count);Poses.Add(MakeShared<FJsonValueObject>(First));Pins.Add(MakeShared<FJsonValueNull>());
  for(int32 I=0;I<Count;I++)
  {
   float Angle=0;if(!Number((*Yaws)[I+1],Angle)){Error=TEXT("Invalid Foot IK continuation heading");return false;}
   VisibleRoots.Add((*Roots)[I+1]);Angle=(Angle*float(PI))/180.f;VisibleYaw.Add(MakeShared<FJsonValueNumber>((Angle*180.f)/float(PI)));
  }
  for(int32 K=0;K<Count-1;K++)
  {
   if(Cancelled(Impl->Stop,Error)||Obsolete())return false;
   for(int32 I=0;I<WindowRows;I++)if(!Vector((*Roots)[K+I],Window.GetData()+I*3)||!Number((*Yaws)[K+I],Window[30+I])){Error=TEXT("Invalid Foot IK continuation root window");return false;}
   // /resume rebases and decodes using the authored root directly. Only the
   // surface Stream variant caps its next root to the first feature command.
   if(!Impl->Advance(Window,Origin,Output,Error,true,Timing))return false;
   const double PoseStart=Timing?FPlatformTime::Seconds():0;Poses.Add(MakeShared<FJsonValueObject>(Pose(Output.GetData(),false)));Pins.Add(MakeShared<FJsonValueArray>(Values(Output.GetData()+673,Impl->PinWidth)));if(Timing)Timing->PoseSeconds+=FPlatformTime::Seconds()-PoseStart;
  }
  auto Result=MakeShared<FJsonObject>();Result->SetArrayField(TEXT("names"),Impl->Names);Result->SetArrayField(TEXT("poses"),Poses);Result->SetArrayField(TEXT("roots"),VisibleRoots);Result->SetArrayField(TEXT("pins"),Pins);Result->SetArrayField(TEXT("rootYawDegrees"),VisibleYaw);
  Result->SetNumberField(TEXT("fps"),30);Result->SetNumberField(TEXT("duration"),(Count-1)/30.);Result->SetNumberField(TEXT("inferences"),Count-1);Result->SetBoolField(TEXT("nnRootWindow"),true);Result->SetStringField(TEXT("direction"),Direction);Result->SetObjectField(TEXT("directionMeta"),Impl->Bank->GetObjectField(TEXT("directionMeta")));Result->SetStringField(TEXT("source"),Impl->bLiveLowerOnly?TEXT("private live lower forecast; game upper preserved at publication"):TEXT("terrain-seeded directional lower + upper NN (native)"));
  if(Impl->bLiveLowerOnly)Result->SetBoolField(TEXT("liveLowerOnly"),true);
  return Write(Result);
 }
 if(!Impl->bInitialized||Reset)
 {
  const FValues* Names=nullptr;const FValues* Seeds=nullptr;if(!R->TryGetArrayField(TEXT("names"),Names)||Names->Num()!=Bodies+1||(*Names)[0]->AsString()!=TEXT("root")||!R->TryGetArrayField(TEXT("seeds"),Seeds)){Error=TEXT("First/reset Foot IK NN request needs matching names and two history seeds");return false;}
  for(int32 I=0;I<Bodies;I++)if((*Names)[I+1]->AsString()!=Impl->Names[I]->AsString()){Error=TEXT("Foot IK NN seed bone order differs");return false;}
  if(!Impl->Encode(*Seeds,Window,false,Output,Error,Timing))return false;Impl->State.SetNumUninitialized(370);Copy(Impl->State.GetData(),Output.GetData(),370);Impl->bInitialized=true;
 }
 const float Origin[3]={0,0,0};if(!Impl->Advance(Window,Origin,Output,Error,false,Timing))return false;
 const double PoseStart=Timing?FPlatformTime::Seconds():0;auto Result=MakeShared<FJsonObject>();Result->SetObjectField(TEXT("pose"),Pose(Output.GetData(),true));Result->SetArrayField(TEXT("pins"),Values(Output.GetData()+673,Impl->PinWidth));if(Timing)Timing->PoseSeconds+=FPlatformTime::Seconds()-PoseStart;return Write(Result);
}

bool FProphecyFootIKNN::Initialize(FString& OutSourceJson,FString& Error)
{
 using namespace FootIKNN;FScopeLock Lock(&Impl->Work);OutSourceJson.Reset();Error.Reset();if(!Impl->bPrepared){Error=TEXT("Prepare Foot IK NN before initialization");return false;}if(Cancelled(Impl->Stop,Error))return false;
 if(Impl->bLiveLowerOnly){Error=TEXT("Live lower Foot IK forecasts cannot initialize a displayed reference course");return false;}
 const auto& S=Impl->Settings;const double Phase=Setting(S,TEXT("phase"),0),Omega=Setting(S,TEXT("rootYawSpeed"),0),YawStart=Setting(S,TEXT("rootYawStart"),0),YawStop=Setting(S,TEXT("rootYawStop"),TNumericLimits<double>::Max()),TotalDuration=Setting(S,TEXT("totalDuration"),Setting(S,TEXT("duration"),5));
 if(!FMath::IsFinite(Phase)||Phase<0||Phase>1||!FMath::IsFinite(Omega)||FMath::Abs(Omega)>360||!FMath::IsFinite(YawStart)||YawStart<0||YawStop<YawStart||!FMath::IsFinite(TotalDuration)||TotalDuration<.1||TotalDuration>600){Error=TEXT("Invalid Foot IK phase/yaw/course duration");return false;}
 FString Terrain=TEXT("stairs");S->TryGetStringField(TEXT("terrain"),Terrain);bool Coupled=Terrain==TEXT("incline");const TSharedPtr<FJsonObject>* Layouts=nullptr;const FValues* Custom=nullptr;if(S->TryGetObjectField(TEXT("platformLayouts"),Layouts)&&(*Layouts)->TryGetArrayField(Terrain,Custom))Coupled=true;
 const double Duration=Coupled?.1:TotalDuration;const auto Meta=Impl->Bank->GetObjectField(TEXT("directionMeta"));const auto Strides=Impl->Bank->GetObjectField(TEXT("strideTicks"));const double Speed=Impl->Gait==TEXT("walk")?Impl->Bank->GetNumberField(TEXT("walkSpeed")):Meta->GetNumberField(TEXT("commandSpeed")),Stride=Strides->GetNumberField(Impl->Gait)/2;
 const int32 Start=60+RoundEven((Phase-FMath::FloorToDouble(Phase))*Stride),Count=FMath::CeilToInt(Duration*30)+2,Total=Start+Count,HistoryStart=FMath::Max(0,Start-FMath::CeilToInt(Stride));
 const auto& Seeds=Impl->Bank->GetArrayField(TEXT("seeds"));const auto& SeedRoots=Impl->Bank->GetArrayField(TEXT("roots"));float Previous[3],Current[3];if(SeedRoots.Num()!=2||!Vector(SeedRoots[0],Previous)||!Vector(SeedRoots[1],Current)){Error=TEXT("Invalid Foot IK command seed roots");return false;}
 TArray<float> Roots,Yaw;Roots.SetNumUninitialized((Total+9)*3);Yaw.SetNumUninitialized(Total+9);Copy(Roots.GetData(),Previous,3);
 for(int32 I=0;I<Total+9;I++)
 {
  if(I){Copy(Roots.GetData()+I*3,Current,3);Roots[I*3+2]+=float(Speed*double(I-1)/30);}
  const double Time=double(I-1-Start)/30;double Distance=FMath::Max(0.,Speed*Time);Distance=FMath::Min(Distance,YawStop);Yaw[I]=float(Speed>1e-8?Omega*FMath::Max(0.,Distance-YawStart)/Speed:0.);
 }
 auto WindowAt=[&](int32 Index,TArray<float>& W){W.SetNumUninitialized(40);Copy(W.GetData(),Roots.GetData()+Index*3,30);Copy(W.GetData()+30,Yaw.GetData()+Index,10);};
 TArray<float> Window,Output;WindowAt(0,Window);if(!Impl->Encode(Seeds,Window,true,Output,Error))return false;float Origin[3];Copy(Origin,Output.GetData()+370,3);Impl->State.SetNumUninitialized(370);Copy(Impl->State.GetData(),Output.GetData(),370);
 float VisibleOrigin[3];Copy(VisibleOrigin,Roots.GetData()+(Start+1)*3,3);VisibleOrigin[1]=0;FValues Poses,VisibleRoots,VisibleYaw,Pins;Poses.Reserve(Count);double HeightSum=0;
 for(int32 K=0;K<Total-1;K++)
 {
  if(Cancelled(Impl->Stop,Error))return false;WindowAt(K,Window);if(!Impl->Advance(Window,Origin,Output,Error))return false;const int32 Row=K+1;
  if(Row>=HistoryStart&&Row<Start)HeightSum+=double(Output[374])-double(Roots[(Row+1)*3+1]);
  if(Row<Start)continue;Poses.Add(MakeShared<FJsonValueObject>(Pose(Output.GetData(),false,VisibleOrigin)));float Root[3];for(int32 J=0;J<3;J++)Root[J]=Roots[(Row+1)*3+J]-VisibleOrigin[J];VisibleRoots.Add(MakeShared<FJsonValueArray>(Values(Root,3)));
  const float Angle=(Yaw[Row+1]*float(PI))/180.f;VisibleYaw.Add(MakeShared<FJsonValueNumber>((Angle*180.f)/float(PI)));Pins.Add(MakeShared<FJsonValueArray>(Values(Output.GetData()+673,Impl->PinWidth)));
 }
 // Initialization is a separate warmup stream. The first live request must
 // encode its actual displayed current/previous pair, as surface_nn.Stream does.
 Impl->State.Reset();Impl->bInitialized=false;if(Cancelled(Impl->Stop,Error))return false;
 auto Result=MakeShared<FJsonObject>();Result->SetArrayField(TEXT("names"),Impl->Names);Result->SetArrayField(TEXT("roots"),VisibleRoots);Result->SetArrayField(TEXT("poses"),Poses);Result->SetArrayField(TEXT("pins"),Pins);Result->SetArrayField(TEXT("rootYawDegrees"),VisibleYaw);
 Result->SetNumberField(TEXT("fps"),30);Result->SetNumberField(TEXT("duration"),Duration);Result->SetNumberField(TEXT("totalDuration"),TotalDuration);Result->SetNumberField(TEXT("phase"),Phase);Result->SetNumberField(TEXT("periodSeconds"),Stride/30);Result->SetNumberField(TEXT("rootYawSpeed"),Omega);Result->SetNumberField(TEXT("rootYawStart"),YawStart);if(YawStop<TNumericLimits<double>::Max())Result->SetNumberField(TEXT("rootYawStop"),YawStop);else Result->SetField(TEXT("rootYawStop"),MakeShared<FJsonValueNull>());
 const double ReferenceHeight=HeightSum/double(Start-HistoryStart);Result->SetNumberField(TEXT("referenceHeight"),ReferenceHeight);Result->SetBoolField(TEXT("nnRootWindow"),true);Result->SetStringField(TEXT("gait"),Impl->Gait);Result->SetStringField(TEXT("direction"),Impl->Direction);Result->SetStringField(TEXT("source"),TEXT("Run 181751 + Upper 82500 - native root-window NN"));
 auto Info=MakeShared<FJsonObject>(*Meta);Info->SetNumberField(TEXT("commandSpeed"),Speed);Info->SetStringField(TEXT("policyGait"),TEXT("run"));Info->SetStringField(TEXT("commandGait"),Impl->Gait);Info->SetNumberField(TEXT("referenceHeight"),ReferenceHeight);Info->SetNumberField(TEXT("totalDuration"),TotalDuration);Result->SetObjectField(TEXT("directionMeta"),Info);return Serialize(Result,OutSourceJson);
}
