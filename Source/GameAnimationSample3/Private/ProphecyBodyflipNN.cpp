#include "ProphecyBodyflipNN.h"
#include "Dom/JsonObject.h"
#include "HAL/CriticalSection.h"
#include "HAL/PlatformProcess.h"
#include "HAL/PlatformTime.h"
#include "Misc/FileHelper.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "Misc/ScopeLock.h"
#include "Misc/ScopeExit.h"
#include "Modules/ModuleManager.h"
#if !defined(ONNXRUNTIME_SHAREDLIB_PATH)
#error Bodyflip requires the engine NNEOnnxruntime module's staged C API library.
#endif
THIRD_PARTY_INCLUDES_START
#include "onnxruntime_c_api.h"
THIRD_PARTY_INCLUDES_END
#include "Serialization/JsonSerializer.h"
#if PLATFORM_CPU_X86_FAMILY
#include <xmmintrin.h>
#endif

// The complete codecs, recurrent policies and decode are exported together.
// This boundary only packs their original float32 inputs and carries history.
// It never obtains or modifies the active locomotion manager/agent state.
namespace ProphecyBodyflip
{
namespace NN
{
constexpr int32 Bodies=25,Future=8,SeedInput=606,SeedOutput=370,StepInput=402,StepOutput=530;
constexpr int32 MaxFrames=18002,MaxRoots=18100;
using FValues=TArray<TSharedPtr<FJsonValue>>;
static bool Trace(){static const bool Enabled=FParse::Param(FCommandLine::Get(),TEXT("BodyflipTrace"));return Enabled;}
static bool Cancelled(const TFunction<bool()>& Check,FString& Error)
{if(Check&&Check()){Error=TEXT("Bodyflip native NN preparation cancelled");return true;}return false;}
static uint32 FloatingPointControl()
{
#if PLATFORM_CPU_X86_FAMILY
    return _mm_getcsr();
#else
    return 0;
#endif
}
static TSharedPtr<FJsonObject> ParseNNJson(const FString& Text)
{TSharedPtr<FJsonObject> Object;return FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Object)?Object:nullptr;}
static bool Number(const TSharedPtr<FJsonValue>& Value,float& Out)
{double X=0;if(!Value||!Value->TryGetNumber(X)||!FMath::IsFinite(X))return false;Out=float(X);return FMath::IsFinite(Out);}
static bool Flat(const FValues& Values,int32 Width,TArray<float>& Out)
{
    if(Values.Num()!=Width)return false;Out.SetNumUninitialized(Width);
    for(int32 I=0;I<Width;I++)if(!Number(Values[I],Out[I]))return false;return true;
}
static bool Vec(const TSharedPtr<FJsonValue>& Value,float* Out)
{
    const FValues* Values=nullptr;if(!Value||!Value->TryGetArray(Values)||Values->Num()!=3)return false;
    for(int32 I=0;I<3;I++)if(!Number((*Values)[I],Out[I]))return false;return true;
}
static FValues Values(const float* Data,int32 Count)
{FValues Out;Out.Reserve(Count);for(int32 I=0;I<Count;I++)Out.Add(MakeShared<FJsonValueNumber>(Data[I]));return Out;}
static FValues Row(const float* Data,int32 Count)
{return {MakeShared<FJsonValueArray>(Values(Data,Count))};}
static bool StateRow(const TSharedPtr<FJsonObject>& Object,const TCHAR* Name,int32 Width,float* Out)
{
    const FValues* Rows=nullptr;const FValues* Data=nullptr;TArray<float> FlatData;
    if(!Object->TryGetArrayField(Name,Rows)||Rows->Num()!=1||!(*Rows)[0]->TryGetArray(Data)||!Flat(*Data,Width,FlatData))return false;
    FMemory::Memcpy(Out,FlatData.GetData(),Width*sizeof(float));return true;
}
struct FSeed
{
    TArray<float> Points,Axes;
    FValues OriginalPoints,OriginalAxes;
};
static bool Seed(const TSharedPtr<FJsonObject>& Object,bool bVirtualRoot,FSeed& Out)
{
    const FValues* Points=nullptr;const FValues* Axes=nullptr;const int32 Skip=bVirtualRoot?1:0;
    if(!Object||!Object->TryGetArrayField(TEXT("points"),Points)||!Object->TryGetArrayField(TEXT("axes"),Axes)||Points->Num()!=Bodies+Skip||Axes->Num()!=Bodies+Skip)return false;
    Out.Points.SetNumUninitialized(Bodies*3);Out.Axes.SetNumUninitialized(Bodies*9);
    for(int32 I=0;I<Bodies;I++)
    {
        if(!Vec((*Points)[I+Skip],Out.Points.GetData()+I*3))return false;
        const FValues* Basis=nullptr;if(!(*Axes)[I+Skip]->TryGetArray(Basis)||Basis->Num()!=3)return false;
        for(int32 K=0;K<3;K++)if(!Vec((*Basis)[K],Out.Axes.GetData()+I*9+K*3))return false;
        Out.OriginalPoints.Add((*Points)[I+Skip]);Out.OriginalAxes.Add((*Axes)[I+Skip]);
    }
    return true;
}
struct FOrtLibrary
{
    const OrtApi* Api=nullptr;
    FOrtLibrary()
    {
        const FString Library=FPaths::EnginePluginsDir()/TEXT("NNE/NNERuntimeORT")/TEXT(PREPROCESSOR_TO_STRING(ONNXRUNTIME_SHAREDLIB_PATH));
        void* Handle=FPlatformProcess::GetDllHandle(*Library);
        if(!Handle)return;
        using FGetApi=const OrtApiBase*(ORT_API_CALL*)();
        const auto Get=reinterpret_cast<FGetApi>(FPlatformProcess::GetDllExport(Handle,TEXT("OrtGetApiBase")));
        if(Get)Api=Get()->GetApi(ORT_API_VERSION);
        // Retain this DLL reference for process lifetime, including destruction
        // of cached sessions after engine modules begin shutting down.
    }
};
static const OrtApi* PrivateOrtApi(){static FOrtLibrary Library;return Library.Api;}
struct FModel
{
    TArray64<uint8> Bytes;
    const OrtApi* Api=nullptr;
    OrtSession* Session=nullptr;
    OrtEnv* Environment=nullptr;
    OrtMemoryInfo* Memory=nullptr;
    FString SourcePath;
    int32 InputWidth=0,OutputWidth=0;
    FModel()=default;
    FModel(const FModel&)=delete;
    FModel& operator=(const FModel&)=delete;
    ~FModel()
    {
        if(!Api)return;
        if(Session)Api->ReleaseSession(Session);
        if(Memory)Api->ReleaseMemoryInfo(Memory);
        if(Environment)Api->ReleaseEnv(Environment);
    }
    bool Check(OrtStatus* Status,FString& Error) const
    {
        if(!Status)return true;
        Error=TEXT("Bodyflip CPU ORT: ")+FString(UTF8_TO_TCHAR(Api->GetErrorMessage(Status)));
        Api->ReleaseStatus(Status);return false;
    }
    bool Prepare(const FString& Path,int32 In,int32 Out,FString& Error)
    {
        check(IsInGameThread());
        if(!FFileHelper::LoadFileToArray(Bytes,*Path)){Error=TEXT("Missing native Bodyflip NN graph: ")+Path;return false;}
        Api=PrivateOrtApi();
        if(!Api){Error=TEXT("Engine ONNX Runtime C API is unavailable for Bodyflip");return false;}
        SourcePath=Path;InputWidth=In;OutputWidth=Out;return true;
    }
    bool ValidateTensor(const OrtSession* Candidate,bool bInput,int32 Width,FString& Error) const
    {
        const TCHAR* Kind=bInput?TEXT("input"):TEXT("output");size_t Count=0;
        if(!Check(bInput?Api->SessionGetInputCount(Candidate,&Count):Api->SessionGetOutputCount(Candidate,&Count),Error))return false;
        if(Count!=1){Error=FString::Printf(TEXT("Bodyflip NN %s count mismatch: %s"),Kind,*SourcePath);return false;}
        OrtTypeInfo* Type=nullptr;char* Name=nullptr;OrtAllocator* Allocator=nullptr;
        ON_SCOPE_EXIT{if(Name&&Allocator)Allocator->Free(Allocator,Name);if(Type)Api->ReleaseTypeInfo(Type);};
        if(!Check(bInput?Api->SessionGetInputTypeInfo(Candidate,0,&Type):Api->SessionGetOutputTypeInfo(Candidate,0,&Type),Error))return false;
        const OrtTensorTypeAndShapeInfo* Tensor=nullptr;
        if(!Check(Api->CastTypeInfoToTensorInfo(Type,&Tensor),Error))return false;
        if(!Tensor){Error=FString::Printf(TEXT("Bodyflip NN %s must be a tensor: %s"),Kind,*SourcePath);return false;}
        ONNXTensorElementDataType Element;size_t Rank=0;
        if(!Check(Api->GetTensorElementType(Tensor,&Element),Error)||!Check(Api->GetDimensionsCount(Tensor,&Rank),Error))return false;
        if(Element!=ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT||Rank!=2){Error=FString::Printf(TEXT("Bodyflip NN %s must be rank-2 float32: %s"),Kind,*SourcePath);return false;}
        int64 Dimensions[2];
        if(!Check(Api->GetDimensions(Tensor,Dimensions,2),Error))return false;
        if(Dimensions[0]!=1||Dimensions[1]!=Width){Error=FString::Printf(TEXT("Bodyflip NN %s shape must be [1,%d]: %s"),Kind,Width,*SourcePath);return false;}
        if(!Check(Api->GetAllocatorWithDefaultOptions(&Allocator),Error)
            ||!Check(bInput?Api->SessionGetInputName(Candidate,0,Allocator,&Name):Api->SessionGetOutputName(Candidate,0,Allocator,&Name),Error))return false;
        if(!Name||FCStringAnsi::Strcmp(Name,bInput?"input":"output")!=0){Error=FString::Printf(TEXT("Bodyflip NN %s name mismatch: %s"),Kind,*SourcePath);return false;}
        return true;
    }
    bool Initialize(FString& Error,const TFunction<bool()>& Stop)
    {
        if(Cancelled(Stop,Error))return false;if(Session)return true;
        // The same frozen ONNX graph runs in an owned CPU session. Per-session
        // one-thread execution avoids the editor's shared ORT pools without
        // changing the manager, Foot IK, or any engine setting.
        if(!Api){Error=TEXT("Bodyflip CPU ORT was not prepared");return false;}
        const FString Name=FPaths::GetCleanFilename(SourcePath);double Stage=FPlatformTime::Seconds();
        if(Trace())UE_LOG(LogTemp,Display,TEXT("Bodyflip NN model %s setup begin (MXCSR 0x%x; intra1/inter1, sequential, no spin)"),*Name,FloatingPointControl());
        OrtSessionOptions* Options=nullptr;OrtEnv* NewEnvironment=nullptr;OrtMemoryInfo* NewMemory=nullptr;OrtSession* Candidate=nullptr;
        ON_SCOPE_EXIT
        {
            if(Candidate)Api->ReleaseSession(Candidate);
            if(NewMemory)Api->ReleaseMemoryInfo(NewMemory);
            if(NewEnvironment)Api->ReleaseEnv(NewEnvironment);
            if(Options)Api->ReleaseSessionOptions(Options);
        };
        if(!Check(Api->CreateSessionOptions(&Options),Error)
            ||!Check(Api->SetIntraOpNumThreads(Options,1),Error)
            ||!Check(Api->SetInterOpNumThreads(Options,1),Error)
            ||!Check(Api->SetSessionExecutionMode(Options,ORT_SEQUENTIAL),Error)
            ||!Check(Api->AddSessionConfigEntry(Options,"session.intra_op.allow_spinning","0"),Error)
            ||!Check(Api->AddSessionConfigEntry(Options,"session.inter_op.allow_spinning","0"),Error)
            ||!Check(Api->SetSessionGraphOptimizationLevel(Options,ORT_ENABLE_ALL),Error)
            ||!Check(Api->EnableCpuMemArena(Options),Error)
            ||!Check(Api->CreateEnv(ORT_LOGGING_LEVEL_ERROR,"ProphecyBodyflip",&NewEnvironment),Error)
            ||!Check(Api->CreateCpuMemoryInfo(OrtDeviceAllocator,OrtMemTypeCPU,&NewMemory),Error))return false;
        if(Trace())UE_LOG(LogTemp,Display,TEXT("Bodyflip NN model %s setup %.3fs; create session begin"),*Name,FPlatformTime::Seconds()-Stage);
        if(Cancelled(Stop,Error))return false;Stage=FPlatformTime::Seconds();
        if(!Check(Api->CreateSessionFromArray(NewEnvironment,Bytes.GetData(),SIZE_T(Bytes.Num()),Options,&Candidate),Error))return false;
        if(Trace())UE_LOG(LogTemp,Display,TEXT("Bodyflip NN model %s session %.3fs; layout begin"),*Name,FPlatformTime::Seconds()-Stage);
        if(Cancelled(Stop,Error))return false;Stage=FPlatformTime::Seconds();
        if(!ValidateTensor(Candidate,true,InputWidth,Error)||!ValidateTensor(Candidate,false,OutputWidth,Error))return false;
        if(Trace())UE_LOG(LogTemp,Display,TEXT("Bodyflip NN model %s layout %.3fs"),*Name,FPlatformTime::Seconds()-Stage);
        if(Cancelled(Stop,Error))return false;
        Session=Candidate;Candidate=nullptr;Environment=NewEnvironment;NewEnvironment=nullptr;Memory=NewMemory;NewMemory=nullptr;
        Bytes.Empty();return true;
    }
    bool Run(TArray<float>& Input,TArray<float>& Output,FString& Error,const TFunction<bool()>& Stop)
    {
        if(Cancelled(Stop,Error))return false;
        if(Input.Num()!=InputWidth){Error=TEXT("Bodyflip NN input packing mismatch");return false;}
        if(!Session){Error=TEXT("Bodyflip CPU ORT session is not initialized");return false;}
        Output.SetNumUninitialized(OutputWidth);
        const int64 InputShape[]={1,InputWidth},OutputShape[]={1,OutputWidth};OrtValue* In=nullptr;OrtValue* Out=nullptr;
        ON_SCOPE_EXIT{if(In)Api->ReleaseValue(In);if(Out)Api->ReleaseValue(Out);};
        if(!Check(Api->CreateTensorWithDataAsOrtValue(Memory,Input.GetData(),SIZE_T(Input.Num())*sizeof(float),InputShape,2,ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT,&In),Error)
            ||!Check(Api->CreateTensorWithDataAsOrtValue(Memory,Output.GetData(),SIZE_T(Output.Num())*sizeof(float),OutputShape,2,ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT,&Out),Error))return false;
        const char* InputNames[]={"input"};const char* OutputNames[]={"output"};const OrtValue* Inputs[]={In};
        if(Cancelled(Stop,Error))return false;
        if(!Check(Api->Run(Session,nullptr,InputNames,Inputs,1,OutputNames,1,&Out),Error))return false;
        if(Cancelled(Stop,Error))return false;
        for(const float X:Output)if(!FMath::IsFinite(X)){Error=TEXT("Bodyflip NN continuation became non-finite");return false;}return true;
    }
};
struct FProfile
{
    FModel Encoder,Step;
    TSharedPtr<FJsonObject> Bank;
    FValues Names;
    TArray<float> Heading;
    float MaxSpeed=0;
};
struct FRegistry
{
    FCriticalSection Mutex;
    FCriticalSection WorkMutex;
    TMap<FString,TSharedPtr<FProfile>> Profiles;
};
static FRegistry& Registry(){static FRegistry Value;return Value;}
static TSharedPtr<FProfile> GetLocked(const FString& Gait,bool bDrawn,FString& Error)
{
    if(Gait!=TEXT("run")&&Gait!=TEXT("walk")){Error=TEXT("Bodyflip NN gait must be run or walk");return nullptr;}
    const FString Stem=Gait+(bDrawn?TEXT("-drawn"):TEXT("-unarmed"));auto& Store=Registry();
    if(const auto* Existing=Store.Profiles.Find(Stem))return *Existing;
    if(!IsInGameThread()){Error=TEXT("PrepareNN must prepare this Bodyflip model pair on the game thread before worker inference");return nullptr;}
    FModuleManager::Get().LoadModule(TEXT("NNERuntimeORT"));
    auto Profile=MakeShared<FProfile>();const FString Folder=FPaths::ProjectContentDir()/TEXT("BodyflipLab/NN");FString Text;
    if(!FFileHelper::LoadFileToString(Text,*(Folder/(Stem+TEXT("-seeds.json"))))||!(Profile->Bank=ParseNNJson(Text))){Error=TEXT("Missing Bodyflip NN seed bank: ")+Stem;return nullptr;}
    const FValues* Names=nullptr;const FValues* Heading=nullptr;double Scale=0;
    if(!Profile->Bank->TryGetArrayField(TEXT("names"),Names)||Names->Num()!=Bodies||!Profile->Bank->TryGetArrayField(TEXT("heading"),Heading)||Heading->Num()!=3||!Profile->Bank->TryGetNumberField(TEXT("maxSpeedScale"),Scale)||!FMath::IsFinite(Scale)||Scale<=0){Error=TEXT("Invalid Bodyflip NN bank metadata: ")+Stem;return nullptr;}
    Profile->Names=*Names;Profile->Heading.SetNumUninitialized(9);Profile->MaxSpeed=float(Scale);
    for(int32 I=0;I<3;I++)if(!Vec((*Heading)[I],Profile->Heading.GetData()+I*3)){Error=TEXT("Invalid Bodyflip NN heading basis");return nullptr;}
    if(!Profile->Encoder.Prepare(Folder/(Stem+TEXT("-seed.onnx")),SeedInput,SeedOutput,Error)||!Profile->Step.Prepare(Folder/(Stem+TEXT("-step.onnx")),StepInput,StepOutput,Error))return nullptr;
    Store.Profiles.Add(Stem,Profile);return Profile;
}
static int32 PhaseSlot(double Phase,int32 Stride)
{
    // The original Python bank uses round-to-even, including exact half slots.
    const double Scaled=(Phase-FMath::FloorToDouble(Phase))*Stride,Floor=FMath::FloorToDouble(Scaled),Fraction=Scaled-Floor;const int32 Lower=int32(Floor);
    return Lower+((Fraction>.5||(Fraction==.5&&(Lower&1)))?1:0);
}
static TSharedPtr<FJsonObject> PoseValue(const float* Points,const float* Axes,const float* Origin)
{
    auto Out=MakeShared<FJsonObject>();FValues P,Q;P.Reserve(Bodies);Q.Reserve(Bodies);
    for(int32 I=0;I<Bodies;I++)
    {
        float World[3];for(int32 J=0;J<3;J++)World[J]=Points[I*3+J]+Origin[J];P.Add(MakeShared<FJsonValueArray>(Values(World,3)));
        FValues Basis;for(int32 J=0;J<3;J++)Basis.Add(MakeShared<FJsonValueArray>(Values(Axes+I*9+J*3,3)));Q.Add(MakeShared<FJsonValueArray>(Basis));
    }
    Out->SetArrayField(TEXT("points"),P);Out->SetArrayField(TEXT("axes"),Q);return Out;
}
static void Copy(float* To,const float* From,int32 Count){FMemory::Memcpy(To,From,Count*sizeof(float));}
static float HeadingComponent(const float* V,const FProfile& P,int32 Column)
{return (V[0]*P.Heading[Column]+V[1]*P.Heading[3+Column])+V[2]*P.Heading[6+Column];}
} // namespace NN

bool PrepareNN(const FString& Gait,bool bDrawn,FString& Error)
{
    if(!IsInGameThread()){Error=TEXT("Bodyflip NN model preparation requires the game thread");return false;}
    FScopeLock Guard(&NN::Registry().Mutex);return NN::GetLocked(Gait,bDrawn,Error).IsValid();
}

bool GenerateNN(AProphecyAgent* Agent,const FString& RequestJson,FString& ResponseJson,FString& Error,TFunction<bool()> IsCancelled)
{
    using namespace NN;(void)Agent;ResponseJson.Reset();Error.Reset();const double Started=FPlatformTime::Seconds();
    if(Cancelled(IsCancelled,Error))return false;
    if(Trace())UE_LOG(LogTemp,Display,TEXT("Bodyflip NN native enter (MXCSR 0x%x)"),FloatingPointControl());
    const auto Request=NN::ParseNNJson(RequestJson);if(!Request){Error=TEXT("Invalid Bodyflip NN request JSON");return false;}
    FString Gait=TEXT("run");bool bDrawn=false;Request->TryGetStringField(TEXT("gait"),Gait);Request->TryGetBoolField(TEXT("drawn"),bDrawn);
    TSharedPtr<NN::FProfile> Profile;
    {FScopeLock Guard(&Registry().Mutex);Profile=GetLocked(Gait,bDrawn,Error);}
    if(!Profile)return false;
    // No recurrent state is shared across calls. Keep the long work lock
    // separate so GT PrepareNN never waits for worker model creation/inference.
    FScopeLock WorkGuard(&Registry().WorkMutex);
    if(Trace())UE_LOG(LogTemp,Display,TEXT("Bodyflip NN native work lock %.3fs"),FPlatformTime::Seconds()-Started);
    if(!Profile->Encoder.Initialize(Error,IsCancelled)||!Profile->Step.Initialize(Error,IsCancelled))return false;
    const FValues* SeedRows=nullptr;const FValues* RootRows=nullptr;FValues InitialSeeds,InitialRoots;bool bInitial=!Request->TryGetArrayField(TEXT("seeds"),SeedRows);int32 Count=0;double Phase=0,Duration=1;
    if(bInitial)
    {
        Request->TryGetNumberField(TEXT("phase"),Phase);Request->TryGetNumberField(TEXT("duration"),Duration);
        if(!FMath::IsFinite(Phase)||Phase<0||Phase>1||!FMath::IsFinite(Duration)||Duration<.1||Duration>600){Error=TEXT("Initial Bodyflip NN phase must be 0..1 and duration .1..600 seconds");return false;}
        const FValues* Phases=nullptr;double Stride=0;
        if(!Profile->Bank->TryGetArrayField(TEXT("phases"),Phases)||!Profile->Bank->TryGetNumberField(TEXT("stride"),Stride)){Error=TEXT("Bodyflip NN bank has no phase seeds");return false;}
        const int32 Slot=PhaseSlot(Phase,int32(Stride));if(!Phases->IsValidIndex(Slot)){Error=TEXT("Invalid Bodyflip NN phase index");return false;}
        const auto BankPose=(*Phases)[Slot]->AsObject();const FValues* BankSeeds=nullptr;const FValues* BankRoots=nullptr;
        if(!BankPose||!BankPose->TryGetArrayField(TEXT("seeds"),BankSeeds)||BankSeeds->Num()!=2||!BankPose->TryGetArrayField(TEXT("roots"),BankRoots)||BankRoots->Num()!=2){Error=TEXT("Invalid Bodyflip phase seed pair");return false;}
        InitialSeeds=*BankSeeds;SeedRows=&InitialSeeds;float Prev[3],Current[3];if(!Vec((*BankRoots)[0],Prev)||!Vec((*BankRoots)[1],Current)){Error=TEXT("Invalid Bodyflip phase roots");return false;}
        Count=FMath::CeilToInt(Duration*30)+2;const int32 RootCount=FMath::Max(12,Count+Future+1);InitialRoots.Reserve(RootCount);
        for(int32 I=0;I<RootCount;I++){float Root[3];for(int32 K=0;K<3;K++)Root[K]=Current[K]+float(I-1)*(Current[K]-Prev[K]);InitialRoots.Add(MakeShared<FJsonValueArray>(Values(Root,3)));}RootRows=&InitialRoots;
    }
    else
    {
        double Frames=0;const FValues* Names=nullptr;
        if(!Request->TryGetNumberField(TEXT("frames"),Frames)||!FMath::IsFinite(Frames)||Frames!=FMath::FloorToDouble(Frames)||Frames<2||Frames>MaxFrames){Error=TEXT("Invalid Bodyflip NN frame count");return false;}Count=int32(Frames);
        if(!Request->TryGetArrayField(TEXT("roots"),RootRows)||!Request->TryGetArrayField(TEXT("names"),Names)||Names->Num()!=Bodies+1||(*Names)[0]->AsString()!=TEXT("root")){Error=TEXT("Bodyflip NN requires full root/bone names and command roots");return false;}
        for(int32 I=0;I<Bodies;I++)if((*Names)[I+1]->AsString()!=Profile->Names[I]->AsString()){Error=TEXT("Bodyflip NN bone order differs from the frozen policy");return false;}
    }
    if(Count<2||Count>MaxFrames||SeedRows->Num()!=2||!RootRows||RootRows->Num()<12||RootRows->Num()>MaxRoots||Count+Future+1>RootRows->Num()){Error=TEXT("Bodyflip NN needs two poses and previous/current roots plus eight future commands");return false;}
    FSeed Seeds[2];for(int32 I=0;I<2;I++)if(!Seed((*SeedRows)[I]->AsObject(),!bInitial,Seeds[I])){Error=TEXT("Bodyflip NN requires two finite complete point/axis poses");return false;}
    TArray<float> Roots;Roots.SetNumUninitialized(RootRows->Num()*3);for(int32 I=0;I<RootRows->Num();I++)if(!Vec((*RootRows)[I],Roots.GetData()+I*3)){Error=TEXT("Invalid Bodyflip NN root path");return false;}
    const TSharedPtr<FJsonObject>* ContinuationPointer=nullptr;const bool bContinuation=Request->TryGetObjectField(TEXT("continuation"),ContinuationPointer);TSharedPtr<FJsonObject> Continuation=bContinuation?*ContinuationPointer:nullptr;
    float Origin[3];Copy(Origin,Roots.GetData()+3,3);
    if(bContinuation){const FValues* O=nullptr;TArray<float> V;if(!Continuation||!Continuation->TryGetArrayField(TEXT("origin"),O)||!Flat(*O,3,V)){Error=TEXT("Invalid Bodyflip NN continuation origin");return false;}Copy(Origin,V.GetData(),3);}
    for(int32 I=0;I<Roots.Num();I++)Roots[I]-=Origin[I%3];
    TArray<float> Input,Encoded,State,Output;Input.SetNumUninitialized(SeedInput);
    for(int32 I=0;I<2;I++){for(int32 K=0;K<Bodies*3;K++)Input[I*75+K]=Seeds[I].Points[K]-Origin[K%3];Copy(Input.GetData()+150+I*225,Seeds[I].Axes.GetData(),225);}Copy(Input.GetData()+600,Roots.GetData(),6);
    double InferenceStarted=FPlatformTime::Seconds();if(Trace())UE_LOG(LogTemp,Display,TEXT("Bodyflip NN encoder run begin; %d frames"),Count);
    if(!Profile->Encoder.Run(Input,Encoded,Error,IsCancelled))return false;State=Encoded;
    if(Trace())UE_LOG(LogTemp,Display,TEXT("Bodyflip NN encoder run %.6fs"),FPlatformTime::Seconds()-InferenceStarted);
    static const TCHAR* StateNames[]={TEXT("previous"),TEXT("current"),TEXT("prev_upper"),TEXT("cur_upper"),TEXT("prev_pelvis"),TEXT("cur_pelvis"),TEXT("base")};
    static const int32 StateWidths[]={41,41,90,90,9,9,90};
    if(bContinuation){int32 Offset=0;for(int32 I=0;I<7;I++){if(!StateRow(Continuation,StateNames[I],StateWidths[I],State.GetData()+Offset)){Error=TEXT("Incomplete or invalid Bodyflip NN recurrent continuation state: ")+FString(StateNames[I]);return false;}Offset+=StateWidths[I];}}
    FValues Rows;Rows.Reserve(Count);auto First=MakeShared<FJsonObject>();First->SetArrayField(TEXT("points"),Seeds[1].OriginalPoints);First->SetArrayField(TEXT("axes"),Seeds[1].OriginalAxes);Rows.Add(MakeShared<FJsonValueObject>(First));Input.SetNumUninitialized(StepInput);
    double TotalStepSeconds=0,LongestStepSeconds=0;
    for(int32 K=0;K<Count-1;K++)
    {
        Copy(Input.GetData(),State.GetData(),271);Copy(Input.GetData()+271,State.GetData()+280,90);Copy(Input.GetData()+361,Roots.GetData()+(K+1)*3,3);Copy(Input.GetData()+364,Roots.GetData()+(K+2)*3,3);
        float* Features=Input.GetData()+367;float Delta[3];for(int32 J=0;J<3;J++)Delta[J]=Roots[(K+1)*3+J]-Roots[K*3+J];Features[0]=HeadingComponent(Delta,*Profile,0)/Profile->MaxSpeed;Features[1]=HeadingComponent(Delta,*Profile,2)/Profile->MaxSpeed;Features[2]=0;
        for(int32 F=1;F<=Future;F++){for(int32 J=0;J<3;J++)Delta[J]=Roots[(K+1+F)*3+J]-Roots[(K+1)*3+J];const float Scale=float(F)*Profile->MaxSpeed;const int32 At=3+(F-1)*4;Features[At]=FMath::Clamp(HeadingComponent(Delta,*Profile,0)/Scale,-2.f,2.f);Features[At+1]=FMath::Clamp(HeadingComponent(Delta,*Profile,2)/Scale,-2.f,2.f);Features[At+2]=1;Features[At+3]=0;}
        InferenceStarted=FPlatformTime::Seconds();if(Trace()&&K<2)UE_LOG(LogTemp,Display,TEXT("Bodyflip NN step %d/%d begin (MXCSR 0x%x)"),K+1,Count-1,FloatingPointControl());
        if(!Profile->Step.Run(Input,Output,Error,IsCancelled))return false;
        const double StepSeconds=FPlatformTime::Seconds()-InferenceStarted;TotalStepSeconds+=StepSeconds;LongestStepSeconds=FMath::Max(LongestStepSeconds,StepSeconds);
        if(Trace()&&(K<2||(K+1)%32==0||K==Count-2))UE_LOG(LogTemp,Display,TEXT("Bodyflip NN step %d/%d %.6fs, total %.3fs, maximum %.6fs"),K+1,Count-1,StepSeconds,TotalStepSeconds,LongestStepSeconds);
        Rows.Add(MakeShared<FJsonValueObject>(PoseValue(Output.GetData()+230,Output.GetData()+305,Origin)));
        Copy(State.GetData(),State.GetData()+41,41);Copy(State.GetData()+41,Output.GetData(),41);Copy(State.GetData()+82,State.GetData()+172,90);Copy(State.GetData()+172,Output.GetData()+41,90);Copy(State.GetData()+262,State.GetData()+271,9);Copy(State.GetData()+271,Output.GetData()+131,9);Copy(State.GetData()+280,Output.GetData()+140,90);
    }
    auto Result=MakeShared<FJsonObject>();Result->SetArrayField(TEXT("names"),Profile->Names);Result->SetNumberField(TEXT("fps"),30);Result->SetNumberField(TEXT("duration"),double(Count-1)/30);Result->SetArrayField(TEXT("poses"),Rows);FValues ReturnedRoots;ReturnedRoots.Reserve(Count);
    for(int32 I=1;I<=Count;I++){float V[3];for(int32 J=0;J<3;J++)V[J]=Roots[I*3+J]+Origin[J];ReturnedRoots.Add(MakeShared<FJsonValueArray>(Values(V,3)));}Result->SetArrayField(TEXT("roots"),ReturnedRoots);
    Result->SetStringField(TEXT("source"),TEXT("landing-seeded lower + upper NN"));Result->SetNumberField(TEXT("inferences"),Count-1);Result->SetNumberField(TEXT("seconds"),FPlatformTime::Seconds()-Started);
    Result->SetArrayField(TEXT("seedLower"),{MakeShared<FJsonValueArray>(Values(Encoded.GetData(),41)),MakeShared<FJsonValueArray>(Values(Encoded.GetData()+41,41))});Result->SetArrayField(TEXT("seedUpper"),{MakeShared<FJsonValueArray>(Values(Encoded.GetData()+82,90)),MakeShared<FJsonValueArray>(Values(Encoded.GetData()+172,90))});
    auto Next=MakeShared<FJsonObject>();Next->SetArrayField(TEXT("origin"),Values(Origin,3));int32 Offset=0;for(int32 I=0;I<7;I++){Next->SetArrayField(StateNames[I],Row(State.GetData()+Offset,StateWidths[I]));Offset+=StateWidths[I];}Result->SetObjectField(TEXT("continuation"),Next);
    if(bInitial){Result->SetNumberField(TEXT("phase"),Phase);Result->SetStringField(TEXT("gait"),Gait);Result->SetNumberField(TEXT("periodSeconds"),Profile->Bank->GetNumberField(TEXT("stride"))/30);}
    return FJsonSerializer::Serialize(Result,TJsonWriterFactory<>::Create(&ResponseJson));
}
} // namespace ProphecyBodyflip
