#define USE_EDGEMODE_JSRT
#include <windows.h>
#include <jsrt.h>
#include <cstdio>
#include <string>
#include <vector>
#include <cmath>
#include <limits>
#include "src/base/ieee754.h"
#define FN_LIST(X) X(JsCreateRuntime) X(JsCreateContext) X(JsSetCurrentContext) X(JsRunScript) X(JsGetGlobalObject) X(JsGetPropertyIdFromName) X(JsSetProperty) X(JsCreateFunction) X(JsGetUndefinedValue) X(JsConvertValueToString) X(JsStringToPointer) X(JsPointerToString) X(JsGetAndClearException) X(JsGetProperty) X(JsDisposeRuntime) X(JsNumberToDouble) X(JsDoubleToNumber)
#define DECL(N) decltype(&::N) p##N;
FN_LIST(DECL)
std::wstring wide(const char*s,size_t n){int count=MultiByteToWideChar(CP_UTF8,0,s,(int)n,nullptr,0);std::wstring w(count,0);MultiByteToWideChar(CP_UTF8,0,s,(int)n,w.data(),count);return w;}
std::string narrow(const wchar_t*s,size_t n){int count=WideCharToMultiByte(CP_UTF8,0,s,(int)n,nullptr,0,nullptr,nullptr);std::string a(count,0);WideCharToMultiByte(CP_UTF8,0,s,(int)n,a.data(),count,nullptr,nullptr);return a;}
JsValueRef CALLBACK print(JsValueRef,bool,JsValueRef*args,unsigned short count,void*){for(int i=1;i<count;i++){JsValueRef str;pJsConvertValueToString(args[i],&str);const wchar_t*s;size_t n;pJsStringToPointer(str,&s,&n);puts(narrow(s,n).c_str());}JsValueRef u;pJsGetUndefinedValue(&u);return u;}
JsValueRef CALLBACK readFile(JsValueRef,bool,JsValueRef*args,unsigned short,void*){const wchar_t*s;size_t len;pJsStringToPointer(args[1],&s,&len);std::wstring path(s,len);FILE*f=_wfopen(path.c_str(),L"rb");if(!f)abort();fseek(f,0,SEEK_END);long n=ftell(f);rewind(f);std::string text(n,0);fread(text.data(),1,n,f);fclose(f);auto w=wide(text.data(),text.size());JsValueRef result;pJsPointerToString(w.data(),w.size(),&result);return result;}
struct MathEntry { const wchar_t* Name; double(*Unary)(double); double(*Binary)(double,double); };
// V8 13.6 src/numbers/ieee754.cc, use_std_math_pow path (V8 BSD license).
double v8Pow(double x,double y){if(std::isnan(y)||(std::isinf(y)&&(x==1||x==-1)))return std::numeric_limits<double>::quiet_NaN();if(std::isnan(x))x=std::numeric_limits<double>::quiet_NaN();if(y==2)return x*x;if(y==.5)return std::isinf(x)?std::numeric_limits<double>::infinity():std::sqrt(x+0.0);return std::pow(x,y);}
JsValueRef CALLBACK mathCall(JsValueRef,bool,JsValueRef*args,unsigned short count,void*state){auto* e=static_cast<MathEntry*>(state);double a=0,b=0;if(count>1)pJsNumberToDouble(args[1],&a);if(count>2)pJsNumberToDouble(args[2],&b);double v=e->Unary?e->Unary(a):e->Binary(a,b);JsValueRef result;pJsDoubleToNumber(v,&result);return result;}
int main(int count,char**args){SetPriorityClass(GetCurrentProcess(),BELOW_NORMAL_PRIORITY_CLASS);HMODULE dll=LoadLibraryExW(L"chakra.dll",nullptr,LOAD_LIBRARY_SEARCH_SYSTEM32);if(!dll)return 2;
#define LOAD(N) p##N=(decltype(p##N))GetProcAddress(dll,#N);if(!p##N){fprintf(stderr,"Missing "#N);return 3;}
FN_LIST(LOAD)
JsRuntimeHandle runtime;JsContextRef context;auto status=pJsCreateRuntime(JsRuntimeAttributeDisableBackgroundWork,nullptr,&runtime);if(status)return status;pJsCreateContext(runtime,&context);pJsSetCurrentContext(context);JsValueRef global;pJsGetGlobalObject(&global);
for(auto pair:std::vector<std::pair<const wchar_t*,JsNativeFunction>>{{L"print",print},{L"readFile",readFile}}){JsPropertyIdRef id;pJsGetPropertyIdFromName(pair.first,&id);JsValueRef fn;pJsCreateFunction(pair.second,nullptr,&fn);pJsSetProperty(global,id,fn,true);}
namespace M=v8::base::ieee754;
MathEntry entries[]={{L"sin",M::sin,nullptr},{L"cos",M::cos,nullptr},{L"tan",M::tan,nullptr},{L"acos",M::acos,nullptr},{L"asin",M::asin,nullptr},{L"atan",M::atan,nullptr},{L"atan2",nullptr,M::atan2},{L"exp",M::exp,nullptr},{L"log",M::log,nullptr},{L"log1p",M::log1p,nullptr},{L"pow",nullptr,v8Pow}};
JsPropertyIdRef mathId;pJsGetPropertyIdFromName(L"Math",&mathId);JsValueRef math;pJsGetProperty(global,mathId,&math);
for(auto& e:entries){JsPropertyIdRef id;pJsGetPropertyIdFromName(e.Name,&id);JsValueRef fn;pJsCreateFunction(mathCall,&e,&fn);pJsSetProperty(math,id,fn,true);}
for(int i=1;i<count;i++){FILE*f=fopen(args[i],"rb");if(!f)return 4;fseek(f,0,SEEK_END);long n=ftell(f);rewind(f);std::string text(n,0);fread(text.data(),1,n,f);fclose(f);auto w=wide(text.data(),text.size());JsValueRef result;status=pJsRunScript(w.c_str(),i,L"footik-math-probe",&result);if(status){JsValueRef e;pJsGetAndClearException(&e);JsValueRef a[]={global,e};print(nullptr,false,a,2,nullptr);JsPropertyIdRef id;pJsGetPropertyIdFromName(L"stack",&id);pJsGetProperty(e,id,&a[1]);print(nullptr,false,a,2,nullptr);break;}}
pJsSetCurrentContext(nullptr);pJsDisposeRuntime(runtime);FreeLibrary(dll);return status;}
