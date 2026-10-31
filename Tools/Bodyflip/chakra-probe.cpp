#define USE_EDGEMODE_JSRT
#include <windows.h>
#include <jsrt.h>
#include <stdio.h>
#include <string>
#include <vector>
#define FN_LIST(X) X(JsCreateRuntime) X(JsCreateContext) X(JsSetCurrentContext) X(JsRunScript) X(JsGetGlobalObject) X(JsGetPropertyIdFromName) X(JsSetProperty) X(JsCreateFunction) X(JsGetUndefinedValue) X(JsConvertValueToString) X(JsStringToPointer) X(JsPointerToString) X(JsGetAndClearException) X(JsGetProperty) X(JsDisposeRuntime) X(JsGetRuntimeMemoryUsage) X(JsCollectGarbage) X(JsSetRuntimeMemoryLimit) X(JsSetRuntimeMemoryAllocationCallback) X(JsDisableRuntimeExecution)
#define DECL(N) decltype(&::N) p##N;
FN_LIST(DECL)
JsErrorCode guardedRun(const wchar_t* text,JsSourceContext id,const wchar_t* name,JsValueRef* out){__try{return pJsRunScript(text,id,name,out);}__except(GetExceptionCode()==0x8007000eUL?EXCEPTION_EXECUTE_HANDLER:EXCEPTION_CONTINUE_SEARCH){return JsErrorOutOfMemory;}}
JsRuntimeHandle probeRuntime;
size_t allocated=0,watermark=0;bool interrupted=false;
bool CALLBACK allocation(void*,JsMemoryEventType kind,size_t size){if(kind==JsMemoryAllocate){allocated+=size;if(watermark&&allocated>watermark&&!interrupted){interrupted=true;auto status=pJsDisableRuntimeExecution(probeRuntime);fprintf(stderr,"Memory watermark interruption: %zu bytes, status %x\n",allocated,status);}}else if(kind==JsMemoryFree)allocated=allocated>size?allocated-size:0;return true;}
JsValueRef CALLBACK heap(JsValueRef,bool,JsValueRef*,unsigned short,void*){size_t n=0;pJsGetRuntimeMemoryUsage(probeRuntime,&n);auto s=std::to_wstring(n);JsValueRef value;pJsPointerToString(s.data(),s.size(),&value);return value;}
JsValueRef CALLBACK collect(JsValueRef,bool,JsValueRef*,unsigned short,void*){pJsCollectGarbage(probeRuntime);JsValueRef u;pJsGetUndefinedValue(&u);return u;}
std::wstring wide(const char*s,size_t n){int count=MultiByteToWideChar(CP_UTF8,0,s,(int)n,nullptr,0);std::wstring w(count,0);MultiByteToWideChar(CP_UTF8,0,s,(int)n,w.data(),count);return w;}
std::string narrow(const wchar_t*s,size_t n){int count=WideCharToMultiByte(CP_UTF8,0,s,(int)n,nullptr,0,nullptr,nullptr);std::string a(count,0);WideCharToMultiByte(CP_UTF8,0,s,(int)n,a.data(),count,nullptr,nullptr);return a;}
JsValueRef CALLBACK print(JsValueRef,bool,JsValueRef*args,unsigned short count,void*){for(int i=1;i<count;i++){JsValueRef str;pJsConvertValueToString(args[i],&str);const wchar_t*s;size_t n;pJsStringToPointer(str,&s,&n);puts(narrow(s,n).c_str());}JsValueRef u;pJsGetUndefinedValue(&u);return u;}
JsValueRef CALLBACK readFile(JsValueRef,bool,JsValueRef*args,unsigned short count,void*){const wchar_t*s;size_t len;pJsStringToPointer(args[1],&s,&len);std::wstring path(s,len);FILE*f=_wfopen(path.c_str(),L"rb");if(!f)abort();fseek(f,0,SEEK_END);long n=ftell(f);rewind(f);std::string text(n,0);fread(text.data(),1,n,f);fclose(f);auto w=wide(text.data(),text.size());JsValueRef result;pJsPointerToString(w.data(),w.size(),&result);return result;}
int main(int count,char**args){setvbuf(stdout,nullptr,_IONBF,0);HMODULE dll=LoadLibraryExW(L"chakra.dll",nullptr,LOAD_LIBRARY_SEARCH_SYSTEM32);if(!dll)return 2;
#define LOAD(N) p##N=(decltype(p##N))GetProcAddress(dll,#N);if(!p##N){fprintf(stderr,"Missing "#N);return 3;}
FN_LIST(LOAD)
JsRuntimeHandle runtime;JsContextRef context;auto status=pJsCreateRuntime(JsRuntimeAttributes(JsRuntimeAttributeDisableBackgroundWork|JsRuntimeAttributeAllowScriptInterrupt),nullptr,&runtime);if(status)return status;probeRuntime=runtime;if(const char*limit=getenv("BODYFLIP_PROBE_LIMIT_MB"))pJsSetRuntimeMemoryLimit(runtime,atoll(limit)*1024*1024);if(const char*limit=getenv("BODYFLIP_PROBE_WATERMARK_MB"))watermark=atoll(limit)*1024*1024;pJsGetRuntimeMemoryUsage(runtime,&allocated);pJsSetRuntimeMemoryAllocationCallback(runtime,nullptr,allocation);pJsCreateContext(runtime,&context);pJsSetCurrentContext(context);JsValueRef global;pJsGetGlobalObject(&global);
for(auto pair:std::vector<std::pair<const wchar_t*,JsNativeFunction>>{{L"print",print},{L"readFile",readFile},{L"heap",heap},{L"collect",collect}}){JsPropertyIdRef id;pJsGetPropertyIdFromName(pair.first,&id);JsValueRef fn;pJsCreateFunction(pair.second,nullptr,&fn);pJsSetProperty(global,id,fn,true);}
for(int i=1;i<count;i++){FILE*f=fopen(args[i],"rb");if(!f)return 4;fseek(f,0,SEEK_END);long n=ftell(f);rewind(f);std::string text(n,0);fread(text.data(),1,n,f);fclose(f);auto w=wide(text.data(),text.size());JsValueRef result;status=guardedRun(w.c_str(),i,L"bodyflip-probe",&result);if(interrupted||status==JsErrorOutOfMemory){fprintf(stderr,"Bodyflip memory budget exceeded; handled %x\n",status);break;}if(status){JsValueRef e;pJsGetAndClearException(&e);JsValueRef a[]={global,e};print(nullptr,false,a,2,nullptr);JsPropertyIdRef id;pJsGetPropertyIdFromName(L"stack",&id);pJsGetProperty(e,id,&a[1]);print(nullptr,false,a,2,nullptr);break;}}
pJsSetCurrentContext(nullptr);pJsDisposeRuntime(runtime);if(interrupted)fprintf(stderr,"Interrupted runtime disposed cleanly\n");FreeLibrary(dll);return status;}
