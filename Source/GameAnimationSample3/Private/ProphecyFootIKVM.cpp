#include "ProphecyFootIKVM.h"
#include "ProphecyFootIKV8ABI.h"
#include "ProphecyFootIKArmKernel.h"
#include "ProphecyFootIKEntryKernel.h"
#include "ProphecyFootIKLegKernel.h"
#include "ProphecyFootIKFloorKernel.h"
#include "HAL/PlatformTime.h"
#include "HAL/PlatformProcess.h"
#include "HAL/Runnable.h"
#include "HAL/RunnableThread.h"
#include "HAL/Event.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/ScopeLock.h"
#include "Templates/Atomic.h"
#include "Windows/WindowsHWrapper.h"
namespace FootIKV8
{
struct Decoded{uint8 Type,Subtype;uint16 Flags;int32 Length;union{double Number;const wchar_t* Text;void* Object;};};
static_assert(sizeof(Decoded)==16);
struct FAPI
{
#define DECL(R,N,A) R(*N)A=nullptr;
    FOOTIK_V8_API(DECL)
#undef DECL
    bool Valid=false;
    FAPI()
    {
        const FString Path=FPaths::ConvertRelativePathToFull(FPaths::ProjectContentDir()/TEXT("FootIKLab/V8/ClearScriptV8.win-x64.dll"));
        // V8's platform singleton is process-wide; retain the DLL until exit.
        void* DLL=FPlatformProcess::GetDllHandle(*Path);if(!DLL)return;
#define LOAD(R,N,A) N=reinterpret_cast<decltype(N)>(FPlatformProcess::GetDllExport(DLL,TEXT(#N)));if(!N)return;
        FOOTIK_V8_API(LOAD)
#undef LOAD
        Valid=FString(V8SplitProxyNative_GetVersion()).StartsWith(TEXT("7.5.1"));
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
    void Start(){if(!Thread&&!Stopping)Thread=FRunnableThread::Create(this,TEXT("FootIK V8 callbacks"),1024*1024,TPri_BelowNormal);}
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
struct FFunction:FHost{enum EKind{NNCall,BraceFit,EntrySolve,LegContact,TerrainFloor,TerrainReach,TerrainRotation};FProphecyFootIKVM::FNN* NN;TAtomic<bool>* Canceled;EKind Kind;FFunction(FProphecyFootIKVM::FNN* N,TAtomic<bool>* C,EKind K=NNCall):NN(N),Canceled(C),Kind(K){}};
void* AddRef(void* O){if(O)++static_cast<FHost*>(O)->References;return O;}
void ReleaseHost(void* O){if(O&&--static_cast<FHost*>(O)->References==0)delete static_cast<FHost*>(O);}
void* NewCache(){return new FCache;}
void PutCache(void* C,void* K,void* V){static_cast<FCache*>(C)->Objects.Add(K,V);}
void* GetCache(void* C,void* K){return static_cast<FCache*>(C)->Objects.FindRef(K);}
uint8 RemoveCache(void* C,void* K){return static_cast<FCache*>(C)->Objects.Remove(K)!=0;}
void GetAllCache(void* C,void* A){auto& M=static_cast<FCache*>(C)->Objects;API().StdPtrArray_SetElementCount(A,M.Num());void** D=API().StdPtrArray_GetData(A);for(auto& P:M)*D++=P.Value;}
void Invalid(const void* M){if(CurrentError)*CurrentError=String(M);}
void Exception(const void*,const void* M,const void* S,uint8,uint8,const void*,const void*){if(CurrentError)*CurrentError=String(M)+TEXT("\n")+String(S);}
void ForwardException(const void*){if(CurrentError)*CurrentError=TEXT("FootIK native script exception");}
uint64 Unexpected(){HostError(TEXT("Unsupported FootIK native host operation"));return 0;}
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
    // Decode creates object-handle clones. Unlike primitive NN arguments,
    // typed-array arguments own handles that the host must release.
    struct FArguments{int32 Count;const Decoded* Args;~FArguments(){for(int32 I=0;I<Count;++I)if(Args[I].Type==8)ReleaseEntity(Args[I].Object);}} Arguments{N,A};
    if(F.Canceled->Load()){HostError(TEXT("FootIK preparation canceled"));return;}
    if(F.Kind==FFunction::BraceFit)
    {
        if(N!=96){HostError(TEXT("Invalid FootIK brace input"));return;}double Input[96],Output[34];
        for(int32 I=0;I<N;++I){if(A[I].Type!=4){HostError(TEXT("Invalid FootIK brace scalar"));return;}Input[I]=A[I].Number;}
        if(!ProphecyFootIKMath::ArmFit(Input,96,Output,34)){HostError(TEXT("FootIK brace kernel rejected input"));return;}
        if(F.Canceled->Load()){HostError(TEXT("FootIK preparation canceled"));return;}
        Value=TEXT("[");for(int32 I=0;I<34;++I){if(I)Value+=TEXT(",");Value+=FString::Printf(TEXT("%.17g"),Output[I]);}Value+=TEXT("]");
        API().V8Value_SetString(R,*Value,Value.Len());return;
    }
    if(F.Kind==FFunction::EntrySolve||F.Kind==FFunction::LegContact||F.Kind==FFunction::TerrainFloor||F.Kind==FFunction::TerrainReach||F.Kind==FFunction::TerrainRotation)
    {
        API().V8Value_SetNumber(R,0);if(N!=2||A[0].Type!=8||A[1].Type!=8)return;
        uint64_t Lengths[2]={};for(int32 I=0;I<2;++I)
        {
            uint64_t Offset=0,Size=0;void* Buffer=API().V8Value_New();
            API().V8Object_GetArrayBufferOrViewInfo(A[I].Object,Buffer,&Offset,&Size,&Lengths[I]);API().V8Value_Delete(Buffer);
            if(Size!=Lengths[I]*8||Offset%8||Lengths[I]>1000000)return;
        }
        bool Solved=false;
        TFunction<void(void*)> Input=[&](void* Data)
        {
            TFunction<void(void*)> Output=[&](void* Result)
            {
                Solved=F.Kind==FFunction::TerrainRotation
                    ?ProphecyFootIKMath::TerrainRotationClearance(static_cast<double*>(Data),int(Lengths[0]),static_cast<double*>(Result),int(Lengths[1]))
                    :F.Kind==FFunction::TerrainReach
                    ?ProphecyFootIKMath::TerrainReach(static_cast<double*>(Data),int(Lengths[0]),static_cast<double*>(Result),int(Lengths[1]))
                    :F.Kind==FFunction::TerrainFloor
                    ?ProphecyFootIKMath::TerrainFloor(static_cast<double*>(Data),int(Lengths[0]),static_cast<double*>(Result),int(Lengths[1]))
                    :F.Kind==FFunction::LegContact
                    ?ProphecyFootIKMath::LegContact(static_cast<double*>(Data),int(Lengths[0]),static_cast<double*>(Result),int(Lengths[1]))
                    :ProphecyFootIKMath::EntrySolve(static_cast<double*>(Data),int(Lengths[0]),static_cast<double*>(Result),int(Lengths[1]));
            };
            API().V8Object_InvokeWithArrayBufferOrViewData(A[1].Object,&Output);
        };
        API().V8Object_InvokeWithArrayBufferOrViewData(A[0].Object,&Input);
        if(F.Canceled->Load()){HostError(TEXT("FootIK preparation canceled"));return;}API().V8Value_SetNumber(R,Solved?1:0);return;
    }
    if(N!=1||A[0].Type!=5||!(*F.NN)||!(*F.NN)(FString(A[0].Length,A[0].Text),Value,Error)){HostError(Error.IsEmpty()?TEXT("Native FootIK NN continuation is unavailable"):Error);return;}
    if(F.Canceled->Load()){HostError(TEXT("FootIK preparation canceled"));return;}API().V8Value_SetString(R,*Value,Value.Len());
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
struct FProphecyFootIKVM::FImpl
{
    void* Isolate=nullptr;void* Context=nullptr;void* Solver=nullptr;void* Arguments=nullptr;void* ResultValue=nullptr;void* CommandName=nullptr;
    FCriticalSection InterruptMutex;void* InterruptContext=nullptr;TAtomic<bool> Canceled{false};FootIKV8::FScheduler Scheduler;FNN NN;double Elapsed=0;
    ~FImpl()
    {
        using namespace FootIKV8;if(!Isolate&&!Context)return;FScope Scope(&Scheduler,nullptr);Canceled.Store(true);
        {FScopeLock L(&InterruptMutex);if(InterruptContext)API().V8Context_Interrupt(InterruptContext);InterruptContext=nullptr;}
        Scheduler.Shutdown();ReleaseEntity(Solver);if(Arguments)API().StdV8ValueArray_Delete(Arguments);if(ResultValue)API().V8Value_Delete(ResultValue);if(CommandName)API().StdString_Delete(CommandName);
        ReleaseEntity(Context);ReleaseEntity(Isolate);Scheduler.Shutdown();
    }
};
FProphecyFootIKVM::FProphecyFootIKVM():Impl(MakeUnique<FImpl>()){}
FProphecyFootIKVM::~FProphecyFootIKVM()=default;
bool FProphecyFootIKVM::Initialize(FNN Generator,FString& Error)
{
    using namespace FootIKV8;if(!API().Valid){Error=TEXT("Missing or incompatible packaged FootIK V8 runtime (7.5.1.1)");return false;}
    auto& I=*Impl;if(I.Canceled.Load()){Error=TEXT("FootIK preparation canceled");return false;}if(I.Isolate){Error=TEXT("FootIK runtime already initialized");return false;}I.NN=MoveTemp(Generator);FScope Scope(&I.Scheduler,&Error);Error.Reset();
    FString Source;if(!FFileHelper::LoadFileToString(Source,*(FPaths::ProjectContentDir()/TEXT("FootIKLab/Runtime.js")))){Error=TEXT("Missing packaged FootIK solver");return false;}
    void* Name=String(FString(TEXT("Prophecy Foot IK")));I.Isolate=API().V8Isolate_Create(Name,24,192,0,64ull*1024*1024,0,0);
    if(I.Isolate){API().V8Isolate_SetMaxHeapSize(I.Isolate,256ull*1024*1024);I.Context=API().V8Isolate_CreateContext(I.Isolate,&I,Name,2,0);}API().StdString_Delete(Name);
    if(!I.Context){if(Error.IsEmpty())Error=TEXT("FootIK V8 context creation failed");return false;}{FScopeLock L(&I.InterruptMutex);I.InterruptContext=I.Context;}
    if(I.Canceled.Load()){Error=TEXT("FootIK preparation canceled");return false;}
    TFunction<void()> Locked=[&]
    {
        void* Key=nullptr,*Value=nullptr;
        const TCHAR* Names[]={TEXT("__footikNN"),TEXT("__footikBraceFit"),TEXT("__footikEntrySolve"),TEXT("__footikLegContact"),TEXT("__footikTerrainFloor"),TEXT("__footikTerrainReach"),TEXT("__footikTerrainRotationClearance")};
        for(int32 Kind=0;Kind<UE_ARRAY_COUNT(Names);++Kind){Key=String(FString(Names[Kind]));Value=API().V8Value_New();API().V8Value_SetHostObject(Value,new FFunction(&I.NN,&I.Canceled,FFunction::EKind(Kind)),1,0);API().V8Context_AddGlobalItem(I.Context,Key,Value,false);API().StdString_Delete(Key);API().V8Value_Delete(Value);}
        void* Code=String(Source),*Resource=String(FString(TEXT("FootIKLab/Runtime.js"))),*Map=String(FString());Value=API().V8Value_New();API().V8Context_ExecuteCode(I.Context,Resource,Map,1,0,nullptr,Code,false,Value);
        API().StdString_Delete(Code);API().StdString_Delete(Resource);API().StdString_Delete(Map);API().V8Value_Delete(Value);if(!Error.IsEmpty())return;
        Value=API().V8Value_New();API().V8Context_GetRootItem(I.Context,Value);Decoded Root{};API().V8Value_Decode(Value,&Root);API().V8Value_Delete(Value);if(Root.Type!=8){Error=TEXT("FootIK V8 global object unavailable");return;}
        Key=String(FString(TEXT("FootIKNative")));Value=API().V8Value_New();API().V8Object_GetNamedProperty(Root.Object,Key,Value);Decoded Solver{};API().V8Value_Decode(Value,&Solver);ReleaseEntity(Root.Object);API().StdString_Delete(Key);API().V8Value_Delete(Value);
        if(Solver.Type!=8){Error=TEXT("FootIK command object unavailable");return;}I.Solver=Solver.Object;I.CommandName=String(FString(TEXT("command")));I.Arguments=API().StdV8ValueArray_New(1);I.ResultValue=API().V8Value_New();
    };
    API().V8Context_InvokeWithLock(I.Context,&Locked);return Error.IsEmpty()&&I.Solver;
}
bool FProphecyFootIKVM::Command(const FString& Json,FString& Result,FString& Error)
{
    using namespace FootIKV8;auto& I=*Impl;if(!I.Context||!I.Solver){Error=TEXT("FootIK runtime is not initialized");return false;}if(I.Canceled.Load()){Error=TEXT("FootIK preparation canceled");return false;}
    double Start=FPlatformTime::Seconds();Error.Reset();FScope Scope(&I.Scheduler,&Error);
    TFunction<void()> Locked=[&]{API().V8Value_SetString(API().StdV8ValueArray_GetData(I.Arguments),*Json,Json.Len());API().V8Object_InvokeMethod(I.Solver,I.CommandName,I.Arguments,I.ResultValue);
        if(Error.IsEmpty()){Decoded V{};API().V8Value_Decode(I.ResultValue,&V);if(V.Type==5)Result=FString(V.Length,V.Text);else Error=TEXT("FootIK command returned a non-string result");}
        API().V8Value_SetUndefined(I.ResultValue);API().V8Value_SetUndefined(API().StdV8ValueArray_GetData(I.Arguments));};
    API().V8Context_InvokeWithLock(I.Context,&Locked);I.Elapsed=FPlatformTime::Seconds()-Start;return Error.IsEmpty();
}
double FProphecyFootIKVM::LastSeconds() const{return Impl->Elapsed;}
void FProphecyFootIKVM::Cancel()
{
    using namespace FootIKV8;auto& I=*Impl;I.Canceled.Store(true);FScopeLock L(&I.InterruptMutex);if(!I.InterruptContext)return;FScope Scope(&I.Scheduler,nullptr);API().V8Context_Interrupt(I.InterruptContext);
}
