#include "ProphecyBodyflipVM.h"
#include "ProphecyBodyflipV8ABI.h"
#include "HAL/PlatformTime.h"
#include "HAL/PlatformProcess.h"
#include "HAL/Runnable.h"
#include "HAL/RunnableThread.h"
#include "HAL/Event.h"
#include "Misc/FileHelper.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "Misc/Paths.h"
#include "Misc/ScopeLock.h"
#include "Templates/Atomic.h"
#include "Windows/WindowsHWrapper.h"
namespace BodyflipV8
{
struct Decoded{uint8 Type,Subtype;uint16 Flags;int32 Length;union{double Number;const wchar_t* Text;void* Object;};};
static_assert(sizeof(Decoded)==16);
struct FAPI
{
#define DECL(R,N,A) R(*N)A=nullptr;
    BODYFLIP_V8_API(DECL)
#undef DECL
    bool Valid=false;
    FAPI()
    {
        const FString Path=FPaths::ConvertRelativePathToFull(FPaths::ProjectContentDir()/TEXT("FootIKLab/V8/ClearScriptV8.win-x64.dll"));
        // V8's platform singleton is process-wide; retain the DLL until exit.
        void* DLL=FPlatformProcess::GetDllHandle(*Path);if(!DLL)return;
#define LOAD(R,N,A) N=reinterpret_cast<decltype(N)>(FPlatformProcess::GetDllExport(DLL,TEXT(#N)));if(!N)return;
        BODYFLIP_V8_API(LOAD)
#undef LOAD
        Valid=FString(V8SplitProxyNative_GetVersion()).StartsWith(TEXT("7.5.1.1"));
    }
};
FAPI& API(){static FAPI A;return A;}
void ReleaseEntity(void* H){if(H){API().V8Entity_Release(H);API().V8Entity_DestroyHandle(H);}}
FString String(const void* V){int32 N=0;const auto* T=API().StdString_GetValue(V,&N);return T?FString(N,T):FString();}
void* String(const FString& V){return API().StdString_New(*V,V.Len());}
class FScheduler;
thread_local FScheduler* CurrentScheduler=nullptr;
thread_local FString* CurrentError=nullptr;
void** Table();
struct FScope
{
    void** Previous;FScheduler* Scheduler;FString* Error;
    FScope(FScheduler* S,FString* E):Previous(API().V8SplitProxyManaged_SetMethodTable(Table())),Scheduler(CurrentScheduler),Error(CurrentError){CurrentScheduler=S;CurrentError=E;}
    ~FScope(){CurrentScheduler=Scheduler;CurrentError=Error;API().V8SplitProxyManaged_SetMethodTable(Previous);}
};
void HostError(const FString& Error)
{
    if(CurrentError)*CurrentError=Error;void* M=String(Error),*V=API().V8Value_New();API().V8Value_SetUndefined(V);API().HostException_Schedule(M,V);API().StdString_Delete(M);API().V8Value_Delete(V);
}
// V8 asks its host to service callbacks even with --single_threaded. This
// lazy worker sleeps on an event; it never runs solver commands or drives NN.
class FScheduler final:public FRunnable
{
    struct FTask{void* Handle=nullptr;double Due=0;int32 Period=-1;~FTask(){ReleaseEntity(Handle);}};
    using FPtr=TSharedPtr<FTask,ESPMode::ThreadSafe>;
    FCriticalSection Mutex;TArray<FPtr> Queue;TMap<void*,FPtr> Timers;
    FEvent* Wake=FPlatformProcess::GetSynchEventFromPool(false);FRunnableThread* Thread=nullptr;bool Stopping=false;
    void Start(){if(!Thread&&!Stopping)Thread=FRunnableThread::Create(this,TEXT("Bodyflip V8 callbacks"),1024*1024,TPri_BelowNormal);}
public:
    ~FScheduler(){Shutdown();FPlatformProcess::ReturnSynchEventToPool(Wake);}
    void Enqueue(void* H)
    {
        auto P=MakeShared<FTask,ESPMode::ThreadSafe>();P->Handle=H;
        {FScopeLock L(&Mutex);if(Stopping)return;Queue.Add(P);Start();}Wake->Trigger();
    }
    void* NewTimer(int32 Delay,int32 Period,void* H)
    {
        auto P=MakeShared<FTask,ESPMode::ThreadSafe>();P->Handle=H;P->Due=Delay<0?DBL_MAX:FPlatformTime::Seconds()+Delay*.001;P->Period=Period;void* Key=&P.Get();
        {FScopeLock L(&Mutex);if(Stopping)return nullptr;Timers.Add(Key,P);Start();}Wake->Trigger();return Key;
    }
    uint8 Change(void* Key,int32 Delay,int32 Period)
    {
        {FScopeLock L(&Mutex);auto* P=Timers.Find(Key);if(!P||Stopping)return false;(*P)->Due=Delay<0?DBL_MAX:FPlatformTime::Seconds()+Delay*.001;(*P)->Period=Period;}Wake->Trigger();return true;
    }
    void Remove(void* Key){FPtr Removed;{FScopeLock L(&Mutex);Timers.RemoveAndCopyValue(Key,Removed);}Wake->Trigger();}
    uint32 Run() override
    {
        FString BackgroundError;FScope ThreadScope(this,&BackgroundError);
        for(;;)
        {
            TArray<FPtr> Ready;uint32 Wait=MAX_uint32;
            {FScopeLock L(&Mutex);if(Stopping)break;Ready=MoveTemp(Queue);double Now=FPlatformTime::Seconds();for(auto& Pair:Timers)
                {auto& P=Pair.Value;if(P->Due<=Now){Ready.Add(P);P->Due=P->Period>0?Now+P->Period*.001:DBL_MAX;}
                if(P->Due!=DBL_MAX)Wait=FMath::Min(Wait,uint32(FMath::Clamp((P->Due-Now)*1000.0,1.0,double(MAX_uint32-1))));}}
            for(const auto& P:Ready){BackgroundError.Reset();API().NativeCallback_Invoke(P->Handle);}
            if(!Ready.Num())Wake->Wait(Wait);
        }return 0;
    }
    void Shutdown()
    {
        {FScopeLock L(&Mutex);Stopping=true;}Wake->Trigger();
        // Join outside V8's isolate lock. A callback may be waiting for it.
        if(Thread){Thread->WaitForCompletion();delete Thread;Thread=nullptr;}
        // Release handles outside Mutex; their destructors can reenter us.
        for(;;){TArray<FPtr> Dropped;TMap<void*,FPtr> Old;{FScopeLock L(&Mutex);Dropped=MoveTemp(Queue);Old=MoveTemp(Timers);}if(!Dropped.Num()&&!Old.Num())break;}
    }
};

struct FHost{TAtomic<int32> References{1};virtual ~FHost()=default;};
struct FCache:FHost{TMap<void*,void*> Objects;};
struct FFunction:FHost
{
    FProphecyBodyflipVM::FNN* Function;
    TAtomic<bool>* Canceled;
    FFunction(FProphecyBodyflipVM::FNN* In,TAtomic<bool>* Stop):Function(In),Canceled(Stop){}
};

void* AddRef(void* O){if(O)++static_cast<FHost*>(O)->References;return O;}
void ReleaseHost(void* O){if(O&&--static_cast<FHost*>(O)->References==0)delete static_cast<FHost*>(O);}
void* NewCache(){return new FCache;}
void PutCache(void* C,void* K,void* V){static_cast<FCache*>(C)->Objects.Add(K,V);}
void* GetCache(void* C,void* K){return static_cast<FCache*>(C)->Objects.FindRef(K);}
uint8 RemoveCache(void* C,void* K){return static_cast<FCache*>(C)->Objects.Remove(K)!=0;}
void GetAllCache(void* C,void* A){auto& M=static_cast<FCache*>(C)->Objects;API().StdPtrArray_SetElementCount(A,M.Num());void** D=API().StdPtrArray_GetData(A);for(auto& P:M)*D++=P.Value;}
void Invalid(const void* M){if(CurrentError)*CurrentError=String(M);}
void Exception(const void*,const void* M,const void* S,uint8,uint8,const void*,const void*){if(CurrentError)*CurrentError=String(M)+TEXT("\n")+String(S);}
void ForwardException(const void*){if(CurrentError)*CurrentError=TEXT("Bodyflip native script exception");}
uint64 Unexpected(){HostError(TEXT("Unsupported Bodyflip native host operation"));return 0;}
void Action(void* A){(*static_cast<TFunction<void()>*>(A))();}
void BufferAction(void* Data,void* Action){(*static_cast<TFunction<void(void*)>*>(Action))(Data);}
uint32 Flags(){return 4;} // DisableBackgroundWork; JIT remains enabled.
uint32 StackSize(){return 768;} // V8 interprets this in KiB.
uint32 CacheSize(){return 32;}
int32 Invocable(void*){return 1;}
void Property(void*,const void*,void* V,uint8* Cacheable){API().V8Value_SetUndefined(V);*Cacheable=false;}

void Invoke(void* O,uint8,int32 N,const Decoded* A,void* R)
{
    auto& F=*static_cast<FFunction*>(O);FString Value,Error;API().V8Value_SetUndefined(R);
    // Decode clones object handles even for arguments rejected by this host.
    struct FArguments{int32 Count;const Decoded* Args;~FArguments(){for(int32 I=0;I<Count;++I)if(Args[I].Type==8)ReleaseEntity(Args[I].Object);}} Arguments{N,A};
    if(F.Canceled->Load()){HostError(TEXT("Bodyflip preparation was cancelled or exceeded its 120-second time limit"));return;}
    if(N!=1||A[0].Type!=5||!(*F.Function)||!(*F.Function)(FString(A[0].Length,A[0].Text),Value,Error))
    {HostError(Error.IsEmpty()?TEXT("Invalid Bodyflip native host request"):Error);return;}
    if(F.Canceled->Load()){HostError(TEXT("Bodyflip preparation was cancelled or exceeded its 120-second time limit"));return;}
    API().V8Value_SetString(R,*Value,Value.Len());
}

void Enqueue(void* H){if(CurrentScheduler)CurrentScheduler->Enqueue(H);else ReleaseEntity(H);}
void* NewTimer(int32 D,int32 P,void* H){if(CurrentScheduler)return CurrentScheduler->NewTimer(D,P,H);ReleaseEntity(H);return nullptr;}
uint8 ChangeTimer(void* T,int32 D,int32 P){return CurrentScheduler?CurrentScheduler->Change(T,D,P):false;}
void DeleteTimer(void* T){if(CurrentScheduler)CurrentScheduler->Remove(T);}
void** Table()
{
    struct FTable{void* P[62];FTable(){for(auto& V:P)V=(void*)&Unexpected;
        P[0]=(void*)&ForwardException;P[1]=(void*)&Invalid;P[2]=P[3]=(void*)&Exception;P[4]=(void*)&Action;P[6]=(void*)&BufferAction;
        P[9]=(void*)&NewCache;P[10]=(void*)&PutCache;P[11]=(void*)&GetCache;P[12]=(void*)&GetAllCache;P[13]=(void*)&RemoveCache;
        P[17]=P[18]=(void*)&CacheSize;P[19]=(void*)&AddRef;P[20]=(void*)&ReleaseHost;P[21]=(void*)&Invocable;P[22]=(void*)&Property;P[30]=(void*)&Invoke;
        P[51]=(void*)&Enqueue;P[52]=(void*)&NewTimer;P[53]=(void*)&ChangeTimer;P[54]=(void*)&DeleteTimer;P[58]=(void*)&Flags;P[59]=(void*)&StackSize;}};
    static FTable T;return T.P;
}
}

struct FProphecyBodyflipVM::FImpl
{
    void* Isolate=nullptr;void* Context=nullptr;void* Solver=nullptr;void* Arguments=nullptr;void* ResultValue=nullptr;void* CommandName=nullptr;
    FCriticalSection InterruptMutex;void* InterruptContext=nullptr;TAtomic<bool> Canceled{false};BodyflipV8::FScheduler Scheduler;
    FNN NN,Attack;TMap<FString,FString> Attacks;FStatistics Stats;double Elapsed=0;
    bool Trace=FParse::Param(FCommandLine::Get(),TEXT("BodyflipTrace"));
    uint64 SoftHeapBytes=384ull*1024*1024;bool HeapExceeded=false;
    void Heap()
    {
        if(!Isolate)return;uint64 Total=0,Executable=0,Physical=0,Available=0,Used=0,Limit=0,External=0;
        BodyflipV8::API().V8Isolate_GetHeapStatistics(Isolate,&Total,&Executable,&Physical,&Available,&Used,&Limit,&External);
        Stats.HeapBytes=Total+External;Stats.PeakHeapBytes=FMath::Max(Stats.PeakHeapBytes,Stats.HeapBytes);
        // Match ClearScript's own monitor: transient garbage gets one full
        // collection before a budget failure. Only retained excess aborts.
        if(Total>SoftHeapBytes)
        {
            BodyflipV8::API().V8Isolate_CollectGarbage(Isolate,true);
            BodyflipV8::API().V8Isolate_GetHeapStatistics(Isolate,&Total,&Executable,&Physical,&Available,&Used,&Limit,&External);
            Stats.HeapBytes=Total+External;Stats.PeakHeapBytes=FMath::Max(Stats.PeakHeapBytes,Stats.HeapBytes);
        }
        HeapExceeded|=Total>SoftHeapBytes;
    }
    bool Checked(FString& Error)
    {
        if(HeapExceeded||Error.Contains(TEXT("memory limit"))||Error.Contains(TEXT("heap size")))
        {Canceled.Store(true);Error=TEXT("Bodyflip reached its script memory budget; shorten the prepared interval or reduce overlapping actions");return false;}
        if(Canceled.Load()){Error=TEXT("Bodyflip preparation was cancelled or exceeded its 120-second time limit");return false;}
        return Error.IsEmpty();
    }
    ~FImpl()
    {
        using namespace BodyflipV8;if(!Isolate&&!Context)return;FScope Scope(&Scheduler,nullptr);Canceled.Store(true);
        {FScopeLock L(&InterruptMutex);if(InterruptContext)API().V8Context_Interrupt(InterruptContext);InterruptContext=nullptr;}
        // The planner retires this object on its worker. Join outside V8's
        // isolate lock: a callback may be waiting for that same lock.
        Scheduler.Shutdown();ReleaseEntity(Solver);if(Arguments)API().StdV8ValueArray_Delete(Arguments);if(ResultValue)API().V8Value_Delete(ResultValue);if(CommandName)API().StdString_Delete(CommandName);
        ReleaseEntity(Context);ReleaseEntity(Isolate);Scheduler.Shutdown();
    }
};
FProphecyBodyflipVM::FProphecyBodyflipVM():Impl(MakeUnique<FImpl>()){}
#if WITH_DEV_AUTOMATION_TESTS
FProphecyBodyflipVM::FProphecyBodyflipVM(uint64 TestSoftHeapBytes):FProphecyBodyflipVM()
{Impl->SoftHeapBytes=FMath::Clamp<uint64>(TestSoftHeapBytes,1024ull*1024,Impl->SoftHeapBytes);}
#endif
FProphecyBodyflipVM::~FProphecyBodyflipVM()=default;
bool FProphecyBodyflipVM::Initialize(FNN Generator,FString& Error)
{
    using namespace BodyflipV8;auto& I=*Impl;Error.Reset();
    if(!API().Valid){Error=TEXT("Missing or incompatible pinned ClearScript V8 runtime (7.5.1.1)");return false;}
    if(I.Canceled.Load()){Error=TEXT("Bodyflip preparation cancelled");return false;}
    if(I.Isolate){Error=TEXT("Bodyflip runtime already initialized");return false;}
    FString IndexText;TSharedPtr<FJsonObject> Index;
    if(!FFileHelper::LoadFileToString(IndexText,*(FPaths::ProjectContentDir()/TEXT("BodyflipLab/AttackIndex.json")))||!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(IndexText),Index)||!Index)
    {Error=TEXT("Missing Bodyflip attack index");return false;}
    for(const auto& Pair:Index->Values){const FString File=Pair.Value->AsString();if(FPaths::GetCleanFilename(File)!=File){Error=TEXT("Invalid Bodyflip attack asset path");return false;}I.Attacks.Add(Pair.Key,FPaths::ProjectContentDir()/TEXT("BodyflipLab/Attacks")/File);}
    I.NN=[&I,Generator=MoveTemp(Generator)](const FString& Request,FString& Out,FString& E)
    {
        I.Heap();if(!I.Checked(E))return false;const double Started=FPlatformTime::Seconds();const uint32 Count=++I.Stats.NNCalls;
        if(I.Trace&&Count<=4){TSharedPtr<FJsonObject> Details;FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Request),Details);double Frames=0,Duration=0;if(Details){Details->TryGetNumberField(TEXT("frames"),Frames);Details->TryGetNumberField(TEXT("duration"),Duration);}UE_LOG(LogTemp,Display,TEXT("Bodyflip NN %u begin: frames %.0f, duration %.3f"),Count,Frames,Duration);}
        const bool Good=Generator&&Generator(Request,Out,E);const double Seconds=FPlatformTime::Seconds()-Started;I.Stats.NNSeconds+=Seconds;I.Stats.LongestNNSeconds=FMath::Max(I.Stats.LongestNNSeconds,Seconds);
        if(I.Trace&&(Count<=4||Seconds>.25||Count%25==0))UE_LOG(LogTemp,Display,TEXT("Bodyflip NN %u end: %.3fs, cumulative %.3fs, %d output characters, okay %d"),Count,Seconds,I.Stats.NNSeconds,Out.Len(),int32(Good));
        return Good;
    };
    I.Attack=[&I](const FString& Name,FString& Out,FString& E)
    {const FString* File=I.Attacks.Find(Name);if(!File||!FFileHelper::LoadFileToString(Out,**File)){E=TEXT("Missing packaged Bodyflip attack");return false;}return true;};
    FScope Scope(&I.Scheduler,&Error);FString Source;
    if(!FFileHelper::LoadFileToString(Source,*(FPaths::ProjectContentDir()/TEXT("BodyflipLab/Runtime.js")))){Error=TEXT("Missing packaged Bodyflip solver");return false;}
    void* Name=String(FString(TEXT("Prophecy Bodyflip")));
    // 384 MiB interrupt/GC threshold with spare V8 heap capacity for unwinding.
    // Array buffers are separately bounded. Background JIT workers are disabled.
    I.Isolate=API().V8Isolate_Create(Name,32,448,0,32ull*1024*1024,0,0);
    if(I.Isolate){API().V8Isolate_SetMaxHeapSize(I.Isolate,I.SoftHeapBytes);API().V8Isolate_SetHeapSizeSampleInterval(I.Isolate,50);I.Context=API().V8Isolate_CreateContext(I.Isolate,&I,Name,2,0);}
    API().StdString_Delete(Name);
    if(!I.Context){if(Error.IsEmpty())Error=TEXT("Bodyflip V8 context creation failed");return false;}
    {FScopeLock L(&I.InterruptMutex);I.InterruptContext=I.Context;}
    if(!I.Checked(Error))return false;
    TFunction<void()> Locked=[&]
    {
        void* Key=nullptr,*Value=nullptr;const TCHAR* Names[]={TEXT("__bodyflipNN"),TEXT("__bodyflipAttack")};FNN* Functions[]={&I.NN,&I.Attack};
        for(int32 K=0;K<2;++K){Key=String(FString(Names[K]));Value=API().V8Value_New();API().V8Value_SetHostObject(Value,new FFunction(Functions[K],&I.Canceled),1,0);API().V8Context_AddGlobalItem(I.Context,Key,Value,false);API().StdString_Delete(Key);API().V8Value_Delete(Value);}
        void* Code=String(Source),*Resource=String(FString(TEXT("BodyflipLab/Runtime.js"))),*Map=String(FString());Value=API().V8Value_New();API().V8Context_ExecuteCode(I.Context,Resource,Map,1,0,nullptr,Code,false,Value);
        API().StdString_Delete(Code);API().StdString_Delete(Resource);API().StdString_Delete(Map);API().V8Value_Delete(Value);if(!Error.IsEmpty())return;
        Value=API().V8Value_New();API().V8Context_GetRootItem(I.Context,Value);Decoded Root{};API().V8Value_Decode(Value,&Root);API().V8Value_Delete(Value);if(Root.Type!=8){Error=TEXT("Bodyflip V8 global object unavailable");return;}
        Key=String(FString(TEXT("BodyflipNative")));Value=API().V8Value_New();API().V8Object_GetNamedProperty(Root.Object,Key,Value);Decoded Solver{};API().V8Value_Decode(Value,&Solver);ReleaseEntity(Root.Object);API().StdString_Delete(Key);API().V8Value_Delete(Value);
        if(Solver.Type!=8){Error=TEXT("Bodyflip command object unavailable");return;}I.Solver=Solver.Object;I.CommandName=String(FString(TEXT("command")));I.Arguments=API().StdV8ValueArray_New(1);I.ResultValue=API().V8Value_New();I.Heap();
    };
    API().V8Context_InvokeWithLock(I.Context,&Locked);I.Heap();if(!I.Checked(Error)||!I.Solver)return false;
    FString Assets,Out;if(!FFileHelper::LoadFileToString(Assets,*(FPaths::ProjectContentDir()/TEXT("BodyflipLab/Assets.json")))){Error=TEXT("Missing Bodyflip authored clips");return false;}
    return Command(TEXT("{\"op\":\"assets\",\"value\":")+Assets+TEXT("}"),Out,Error);
}
bool FProphecyBodyflipVM::Command(const FString& Json,FString& Result,FString& Error)
{
    using namespace BodyflipV8;auto& I=*Impl;Result.Reset();Error.Reset();
    if(!I.Context||!I.Solver){Error=TEXT("Bodyflip runtime is not initialized");return false;}if(!I.Checked(Error))return false;
    const double Started=FPlatformTime::Seconds();const bool LogCommand=I.Trace&&(Json.StartsWith(TEXT("{\"op\":\"start\""))||Json.StartsWith(TEXT("{\"op\":\"prepare\"")));
    if(LogCommand)UE_LOG(LogTemp,Display,TEXT("Bodyflip VM begin %s"),*Json.Left(48));FScope Scope(&I.Scheduler,&Error);
    TFunction<void()> Locked=[&]
    {
        API().V8Value_SetString(API().StdV8ValueArray_GetData(I.Arguments),*Json,Json.Len());API().V8Object_InvokeMethod(I.Solver,I.CommandName,I.Arguments,I.ResultValue);
        if(Error.IsEmpty()){Decoded V{};API().V8Value_Decode(I.ResultValue,&V);if(V.Type==5)Result=FString(V.Length,V.Text);else{if(V.Type==8)ReleaseEntity(V.Object);Error=TEXT("Bodyflip command returned a non-string result");}}
        API().V8Value_SetUndefined(I.ResultValue);API().V8Value_SetUndefined(API().StdV8ValueArray_GetData(I.Arguments));I.Heap();
    };
    API().V8Context_InvokeWithLock(I.Context,&Locked);I.Elapsed=FPlatformTime::Seconds()-Started;const bool Good=I.Checked(Error);
    if(!Good)Result.Reset();if(LogCommand||!Good)UE_LOG(LogTemp,Display,TEXT("Bodyflip VM end: %.3fs, heap %.1f MiB, sampled peak %.1f MiB, NN %u/%.3fs, okay %d"),I.Elapsed,I.Stats.HeapBytes/1048576.,I.Stats.PeakHeapBytes/1048576.,I.Stats.NNCalls,I.Stats.NNSeconds,int32(Good));return Good;
}
double FProphecyBodyflipVM::LastSeconds() const{return Impl->Elapsed;}
FProphecyBodyflipVM::FStatistics FProphecyBodyflipVM::Statistics() const{return Impl->Stats;}
bool FProphecyBodyflipVM::IsCancelled() const{return Impl->Canceled.Load();}
void FProphecyBodyflipVM::Cancel()
{
    using namespace BodyflipV8;auto& I=*Impl;I.Canceled.Store(true);FScopeLock L(&I.InterruptMutex);if(!I.InterruptContext)return;FScope Scope(&I.Scheduler,nullptr);API().V8Context_Interrupt(I.InterruptContext);
}

