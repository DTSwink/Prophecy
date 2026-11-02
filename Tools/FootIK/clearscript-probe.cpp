// Isolated diagnostic, not the gameplay bridge. ClearScript 7.5.1.1 native C ABI.
// ABI layouts/signatures: official MIT-licensed ClearScriptV8 split-proxy headers.
#include <windows.h>
#include <cstdio>
#include <cstdint>
#include <string>
#include <vector>
#include <unordered_map>
#include <cstdlib>
#include <functional>
#include <memory>
#include <psapi.h>
#include "src/base/ieee754.h"
#include "ProphecyFootIKArmKernel.h"
#include "ProphecyFootIKEntryKernel.h"
#include "ProphecyFootIKLegKernel.h"
#include "ProphecyFootIKFloorKernel.h"
LONG WINAPI crash(EXCEPTION_POINTERS*p){fprintf(stderr,"crash %lx RIP=%p access=%p\n",p->ExceptionRecord->ExceptionCode,(void*)p->ContextRecord->Rip,(void*)p->ExceptionRecord->ExceptionInformation[1]);void*frames[32];auto n=CaptureStackBackTrace(0,32,frames,nullptr);for(int i=0;i<n;i++){MEMORY_BASIC_INFORMATION m{};VirtualQuery(frames[i],&m,sizeof(m));wchar_t file[1024];GetModuleFileNameW((HMODULE)m.AllocationBase,file,1024);fwprintf(stderr,L"%s + %llx\n",file,(uint64_t)frames[i]-(uint64_t)m.AllocationBase);}return EXCEPTION_EXECUTE_HANDLER;}
struct Decoded { uint8_t type,subtype;uint16_t flags;int32_t length;union{double number;const wchar_t* text;void* object;};};
static_assert(sizeof(Decoded)==16);
#define API(X) \
 X(void**,V8SplitProxyManaged_SetMethodTable,(void**)) \
 X(const wchar_t*,V8SplitProxyNative_GetVersion,()) \
 X(void*,StdString_New,(const wchar_t*,int32_t)) \
 X(const wchar_t*,StdString_GetValue,(const void*,int32_t*)) \
 X(void,StdString_Delete,(void*)) \
 X(void*,V8Value_New,()) \
 X(void,V8Value_Delete,(void*)) \
 X(void,V8Value_SetUndefined,(void*)) \
 X(void,V8Value_SetString,(void*,const wchar_t*,int32_t)) \
 X(void,V8Value_SetNumber,(void*,double)) \
 X(void,V8Value_SetHostObject,(void*,void*,uint8_t,uint16_t)) \
 X(void,V8Value_Decode,(const void*,Decoded*)) \
 X(void,V8Object_GetArrayBufferOrViewInfo,(const void*,void*,uint64_t*,uint64_t*,uint64_t*)) \
 X(void,V8Object_InvokeWithArrayBufferOrViewData,(const void*,void*)) \
 X(void*,V8Isolate_Create,(const void*,int32_t,int32_t,double,uint64_t,int32_t,int32_t)) \
 X(void*,V8Isolate_CreateContext,(const void*,void*,const void*,int32_t,int32_t)) \
 X(void,V8Context_AddGlobalItem,(const void*,const void*,const void*,uint8_t)) \
 X(void,V8Context_InvokeWithLock,(const void*,void*)) \
 X(void,V8Context_ExecuteCode,(const void*,void*,void*,uint64_t,int32_t,void*,const void*,uint8_t,void*)) \
 X(void,V8Entity_Release,(void*)) \
 X(void,V8Entity_DestroyHandle,(void*)) \
 X(void,NativeCallback_Invoke,(void*)) \
 X(void,StdPtrArray_SetElementCount,(void*,int32_t)) \
 X(void**,StdPtrArray_GetData,(void*))
#define DECL(R,N,A) R(*p##N)A;
API(DECL)
std::wstring wide(const char*s,size_t n){int z=MultiByteToWideChar(CP_UTF8,0,s,(int)n,nullptr,0);std::wstring w(z,0);MultiByteToWideChar(CP_UTF8,0,s,(int)n,w.data(),z);return w;}
std::string narrow(const wchar_t*s,size_t n){int z=WideCharToMultiByte(CP_UTF8,0,s,(int)n,nullptr,0,nullptr,nullptr);std::string a(z,0);WideCharToMultiByte(CP_UTF8,0,s,(int)n,a.data(),z,nullptr,nullptr);return a;}
std::wstring read(const wchar_t* path){FILE*f=_wfopen(path,L"rb");if(!f){fwprintf(stderr,L"Cannot read %s\n",path);exit(4);}fseek(f,0,SEEK_END);auto n=ftell(f);rewind(f);std::string a(n,0);fread(a.data(),1,n,f);fclose(f);return wide(a.data(),a.size());}
std::string error;
uint64_t floorCallCount=0;
void invalid(const void*str){int32_t n;auto s=pStdString_GetValue(str,&n);error=narrow(s,n);}
void exception(const void*,const void*msg,const void*stack,uint8_t,uint8_t,const void*,const void*){invalid(msg);int32_t n;auto s=pStdString_GetValue(stack,&n);error+='\n'+narrow(s,n);}
template<size_t I>void unexpected(){fprintf(stderr,"Unsupported host callback %zu\n",I);abort();}
template<size_t... I>void initialize(void**table,std::index_sequence<I...>){((table[I]=reinterpret_cast<void*>(static_cast<void(*)()>(&unexpected<I>))),...);}
uint32_t flags(){return 4;}// V8GlobalFlags.DisableBackgroundWork; retain JIT.
uint32_t stackSize(){return 4096;}// V8 --stack_size is in KiB.
uint32_t cacheSize(){return 32;}
void* addRef(void*p){return p;}
void release(void*){}
void bufferAction(void*data,void*action){(*static_cast<std::function<void(void*)>*>(action))(data);}
void action(void*p){(*static_cast<std::function<void()>*>(p))();}
int32_t invocable(void*){return 1;}
using Cache=std::unordered_map<void*,void*>;
std::vector<Cache*> caches;
void* createCache(){auto c=new Cache;caches.push_back(c);return c;}
void putCache(void*c,void*k,void*v){(*static_cast<Cache*>(c))[k]=v;}
void* getCache(void*c,void*k){auto&m=*static_cast<Cache*>(c);auto i=m.find(k);return i==m.end()?nullptr:i->second;}
uint8_t removeCache(void*c,void*k){return static_cast<Cache*>(c)->erase(k)!=0;}
void getAllCache(void*c,void*array){auto&m=*static_cast<Cache*>(c);pStdPtrArray_SetElementCount(array,(int32_t)m.size());auto p=pStdPtrArray_GetData(array);for(auto&i:m)*p++=i.second;}
void entry(const Decoded* args,void*out,int kind=0){
 struct Handles{const Decoded* args;~Handles(){for(int i=0;i<2;i++)if(args[i].type==8){pV8Entity_Release(args[i].object);pV8Entity_DestroyHandle(args[i].object);}}} handles{args};
 pV8Value_SetNumber(out,0);if(args[0].type!=8||args[1].type!=8)return;
 uint64_t lengths[2]={};for(int i=0;i<2;i++){uint64_t offset=0,size=0;auto value=pV8Value_New();pV8Object_GetArrayBufferOrViewInfo(args[i].object,value,&offset,&size,&lengths[i]);pV8Value_Delete(value);if(size!=lengths[i]*8||offset%8||lengths[i]>1000000)return;}
 bool success=false;std::function<void(void*)> input=[&](void*data){std::function<void(void*)> output=[&](void*result){success=kind==4?ProphecyFootIKMath::TerrainRotationClearance(static_cast<double*>(data),int(lengths[0]),static_cast<double*>(result),int(lengths[1])):kind==3?ProphecyFootIKMath::TerrainReach(static_cast<double*>(data),int(lengths[0]),static_cast<double*>(result),int(lengths[1])):kind==2?ProphecyFootIKMath::TerrainFloor(static_cast<double*>(data),int(lengths[0]),static_cast<double*>(result),int(lengths[1])):kind==1?ProphecyFootIKMath::LegContact(static_cast<double*>(data),int(lengths[0]),static_cast<double*>(result),int(lengths[1])):ProphecyFootIKMath::EntrySolve(static_cast<double*>(data),int(lengths[0]),static_cast<double*>(result),int(lengths[1]));};pV8Object_InvokeWithArrayBufferOrViewData(args[1].object,&output);};pV8Object_InvokeWithArrayBufferOrViewData(args[0].object,&input);pV8Value_SetNumber(out,success?1:0);
}
uint64_t reachCallCount=0,rotationCallCount=0;
void invoke(void*id,uint8_t,int32_t n,const Decoded* args,void*out){if(id==(void*)14){pV8Value_SetNumber(out,double(rotationCallCount));return;}if(id==(void*)13){++rotationCallCount;if(n!=2){error="Rotation kernel expects two buffers";return;}entry(args,out,4);return;}if(id==(void*)12){pV8Value_SetNumber(out,double(reachCallCount));return;}if(id==(void*)11){++reachCallCount;if(n!=2){error="Reach kernel expects two buffers";return;}entry(args,out,3);return;}if(id==(void*)10){pV8Value_SetNumber(out,double(floorCallCount));return;}if(id==(void*)9)++floorCallCount;if(id==(void*)7||id==(void*)8||id==(void*)9){if(n!=2){error="Entry kernel expects two buffers";return;}entry(args,out,id==(void*)9?2:id==(void*)8?1:0);return;}pV8Value_SetUndefined(out);if(id==(void*)6){if(n!=96){error="Brace kernel expects96 numbers";return;}double values[96],result[34];for(int i=0;i<n;i++){if(args[i].type!=4){error="Brace kernel expects finite numbers";return;}values[i]=args[i].number;}if(!ProphecyFootIKMath::ArmFit(values,96,result,34)){error="Brace kernel rejected input";return;}std::wstring json=L"[";for(int i=0;i<34;i++){wchar_t number[64];swprintf(number,64,L"%.17g",result[i]);if(i)json+=L",";json+=number;}json+=L"]";pV8Value_SetString(out,json.data(),(int32_t)json.size());return;}if(id==(void*)5){FILETIME created,exited,kernel,user;GetThreadTimes(GetCurrentThread(),&created,&exited,&kernel,&user);auto ticks=[](FILETIME t){return ((uint64_t)t.dwHighDateTime<<32)|t.dwLowDateTime;};pV8Value_SetNumber(out,(ticks(kernel)+ticks(user))/10000.0);return;}if(id==(void*)3||id==(void*)4){if(n!=1||args[0].type!=4){error="Math callback expects a number";return;}pV8Value_SetNumber(out,id==(void*)3?v8::base::ieee754::sin(args[0].number):v8::base::ieee754::cos(args[0].number));return;}if(n<1||args[0].type!=5){error="Host callback expects a string";return;}std::wstring s(args[0].text,args[0].length);if(id==(void*)1){auto a=narrow(s.data(),s.size());puts(a.c_str());}else{auto a=read(s.c_str());pV8Value_SetString(out,a.data(),(int32_t)a.size());}}
void getProperty(void*,const void*,void*out,uint8_t*cacheable){pV8Value_SetUndefined(out);*cacheable=0;}
std::vector<void*> queued;
void queue(void*p){queued.push_back(p);}
struct Timer{void*callback;uint64_t due;int32_t period;};
std::unordered_map<void*,std::unique_ptr<Timer>> timers;
void*newTimer(int32_t due,int32_t period,void*p){auto t=std::make_unique<Timer>();t->callback=p;t->due=due<0?UINT64_MAX:GetTickCount64()+due;t->period=period;auto key=t.get();timers[key]=std::move(t);return key;}
uint8_t changeTimer(void*key,int32_t due,int32_t period){auto i=timers.find(key);if(i==timers.end())return 0;i->second->due=due<0?UINT64_MAX:GetTickCount64()+due;i->second->period=period;return 1;}
void deleteTimer(void*key){auto i=timers.find(key);if(i==timers.end())return;auto p=i->second->callback;timers.erase(i);pV8Entity_Release(p);pV8Entity_DestroyHandle(p);}
void drain(){while(!queued.empty()){auto jobs=std::move(queued);queued.clear();for(auto p:jobs){pNativeCallback_Invoke(p);pV8Entity_Release(p);pV8Entity_DestroyHandle(p);}}}
int main(int argc,char**argv){SetUnhandledExceptionFilter(crash);SetPriorityClass(GetCurrentProcess(),getenv("FOOTIK_DIAG_NORMAL_PRIORITY")?NORMAL_PRIORITY_CLASS:BELOW_NORMAL_PRIORITY_CLASS);wchar_t path[32768];DWORD n=GetEnvironmentVariableW(L"FOOTIK_V8_DLL",path,32768);if(!n){fputs("Set FOOTIK_V8_DLL to pinned native library\n",stderr);return 2;}auto dll=LoadLibraryExW(path,nullptr,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);if(!dll){fprintf(stderr,"Load error %lu\n",GetLastError());return 2;}
#define LOAD(R,N,A) p##N=(decltype(p##N))GetProcAddress(dll,#N);if(!p##N){fputs("Missing " #N "\n",stderr);return 3;}
API(LOAD)
void*table[62];initialize(table,std::make_index_sequence<62>{});
table[1]=(void*)invalid;table[2]=table[3]=(void*)exception;table[9]=(void*)createCache;table[10]=(void*)putCache;table[11]=(void*)getCache;table[12]=(void*)getAllCache;table[13]=(void*)removeCache;table[17]=table[18]=(void*)cacheSize;table[19]=(void*)addRef;table[20]=(void*)release;table[21]=(void*)invocable;table[22]=(void*)getProperty;table[30]=(void*)invoke;table[58]=(void*)flags;table[59]=(void*)stackSize;
table[4]=(void*)action;table[6]=(void*)bufferAction;
table[51]=(void*)queue;
table[52]=(void*)newTimer;table[53]=(void*)changeTimer;table[54]=(void*)deleteTimer;
bool old=std::wstring(pV8SplitProxyNative_GetVersion()).find(L"7.5.0")==0;if(old){table[47]=(void*)queue;table[48]=(void*)newTimer;table[49]=(void*)changeTimer;table[50]=(void*)deleteTimer;table[54]=(void*)flags;}
pV8SplitProxyManaged_SetMethodTable(table);
auto wallStart=GetTickCount64();auto name=pStdString_New(L"FootIK native V8 probe",21);auto isolate=pV8Isolate_Create(name,-1,-1,0,UINT64_MAX,0,0);if(!isolate){fprintf(stderr,"%s\n",error.c_str());return 5;}auto context=old?reinterpret_cast<void*(*)(const void*,const void*,int32_t,int32_t)>(pV8Isolate_CreateContext)(isolate,name,2,0):pV8Isolate_CreateContext(isolate,nullptr,name,2,0);if(!context){fprintf(stderr,"%s\n",error.c_str());return 6;}pStdString_Delete(name);
std::function<void()> locked=[&](){int id=0;for(auto s:{L"print",L"readFile",L"nativeSin",L"nativeCos",L"nativeThreadMilliseconds",L"__footikBraceFit",L"__footikEntrySolve",L"__footikLegContact",L"__footikTerrainFloor",L"nativeFloorCallCount",L"__footikTerrainReach",L"nativeReachCallCount",L"__footikTerrainRotationClearance",L"nativeRotationCallCount"}){auto key=pStdString_New(s,(int32_t)wcslen(s));auto value=pV8Value_New();pV8Value_SetHostObject(value,(void*)(uintptr_t)++id,1,0);pV8Context_AddGlobalItem(context,key,value,0);pV8Value_Delete(value);pStdString_Delete(key);}
for(int i=1;i<argc&&error.empty();i++){auto wp=wide(argv[i],strlen(argv[i]));auto text=read(wp.c_str());auto code=pStdString_New(text.data(),(int32_t)text.size());auto resource=pStdString_New(wp.data(),(int32_t)wp.size());auto map=pStdString_New(L"",0);auto value=pV8Value_New();pV8Context_ExecuteCode(context,resource,map,i,0,nullptr,code,0,value);pV8Value_Delete(value);pStdString_Delete(code);pStdString_Delete(resource);pStdString_Delete(map);}};pV8Context_InvokeWithLock(context,&locked);
if(!error.empty())fprintf(stderr,"%s\n",error.c_str());drain();pV8Entity_Release(context);pV8Entity_DestroyHandle(context);pV8Entity_Release(isolate);pV8Entity_DestroyHandle(isolate);drain();while(!timers.empty())deleteTimer(timers.begin()->first);for(auto c:caches)delete c;
FILETIME created,exited,kernel,user;GetProcessTimes(GetCurrentProcess(),&created,&exited,&kernel,&user);auto ticks=[](FILETIME t){return ((uint64_t)t.dwHighDateTime<<32)|t.dwLowDateTime;};PROCESS_MEMORY_COUNTERS memory{};GetProcessMemoryInfo(GetCurrentProcess(),&memory,sizeof(memory));fprintf(stderr,"PROBE_METRICS {\"cpuMs\":%.3f,\"wallMs\":%llu,\"peakBytes\":%llu}\n",(ticks(kernel)+ticks(user))/10000.0,GetTickCount64()-wallStart,(uint64_t)memory.PeakWorkingSetSize);return error.empty()?0:7;}
