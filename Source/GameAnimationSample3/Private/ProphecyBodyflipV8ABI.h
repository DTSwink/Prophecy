#pragma once
#include <cstdint>
// Pinned ClearScript 7.5.1.1 native ABI (upstream MIT; staged License.txt).
// https://github.com/microsoft/ClearScript/blob/7.5.1.1/ClearScriptV8/V8SplitProxyNative.h
#define BODYFLIP_V8_API(X) \
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
 X(void*,V8Isolate_Create,(const void*,int32_t,int32_t,double,uint64_t,int32_t,int32_t)) \
 X(void*,V8Isolate_CreateContext,(const void*,void*,const void*,int32_t,int32_t)) \
 X(void,V8Context_AddGlobalItem,(const void*,const void*,const void*,uint8_t)) \
 X(void,V8Context_InvokeWithLock,(const void*,void*)) \
 X(void,V8Context_ExecuteCode,(const void*,void*,void*,uint64_t,int32_t,void*,const void*,uint8_t,void*)) \
 X(void,V8Entity_Release,(void*)) \
 X(void,V8Entity_DestroyHandle,(void*)) \
 X(void,NativeCallback_Invoke,(void*)) \
 X(void,StdPtrArray_SetElementCount,(void*,int32_t)) \
 X(void**,StdPtrArray_GetData,(void*)) \
 X(void,V8Context_GetRootItem,(const void*,void*)) \
 X(void,V8Context_Interrupt,(const void*)) \
 X(void,V8Isolate_SetMaxHeapSize,(const void*,size_t)) \
 X(void,V8Isolate_SetHeapSizeSampleInterval,(const void*,double)) \
 X(void,V8Isolate_GetHeapStatistics,(const void*,uint64_t*,uint64_t*,uint64_t*,uint64_t*,uint64_t*,uint64_t*,uint64_t*)) \
 X(void,V8Isolate_CollectGarbage,(const void*,uint8_t)) \
 X(void,V8Object_GetNamedProperty,(const void*,const void*,void*)) \
 X(void,V8Object_InvokeMethod,(const void*,const void*,const void*,void*)) \
 X(void,V8Object_GetArrayBufferOrViewInfo,(const void*,void*,uint64_t*,uint64_t*,uint64_t*)) \
 X(void,V8Object_InvokeWithArrayBufferOrViewData,(const void*,void*)) \
 X(void*,StdV8ValueArray_New,(int32_t)) \
 X(void*,StdV8ValueArray_GetData,(void*)) \
 X(void,StdV8ValueArray_Delete,(void*)) \
 X(void,HostException_Schedule,(void*,void*))

