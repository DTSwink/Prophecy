'use strict';
// Compile canonical V8 fdlibm into the embedded engine; do not change the lab.
const fs=require('fs'),path=require('path'),cp=require('child_process');
const root=path.resolve(__dirname,'../..'),out=path.join(root,'Saved/Diagnostics/FootIKPort20261030/native-v8/trig');fs.mkdirSync(out,{recursive:true});
const source=fs.readFileSync(path.join(__dirname,'v8-math/src/base/ieee754.cc'),'utf8');
const kernels=source.slice(source.indexOf('#define EXTRACT_WORDS'),source.indexOf('}  // namespace'));
function body(name){const from=source.indexOf('double fdlibm_'+name+'('),start=source.indexOf('#endif',from)+6;let i=source.indexOf('{',from),depth=1;const actual=source.indexOf('#endif',i)+6;for(i=actual;depth;i++){if(source[i]==='{')depth++;if(source[i]==='}')depth--;}return 'extern "C" double '+name+'(double x) {'+source.slice(start,i);}
const prefix=source.slice(0,source.indexOf('#include'))+`
typedef __INT32_TYPE__ int32_t;typedef __UINT32_TYPE__ uint32_t;typedef __UINT64_TYPE__ uint64_t;
#define V8_INLINE inline
#define V8_WARN_UNUSED_RESULT
namespace base {template<class T,class U>T bit_cast(U x){return __builtin_bit_cast(T,x);}}
inline double fabs(double x){return __builtin_fabs(x);}inline double floor(double x){return __builtin_floor(x);}
extern "C" double scalbn(double,int);
`;
const cpp=path.join(out,'trig.cpp'),wasm=path.join(out,'trig.wasm');fs.writeFileSync(cpp,prefix+kernels+body('sin')+body('cos'));
const clang=path.join(root,'Saved/Diagnostics/FootIKPort20261030/native-v8/zig/zig-x86_64-windows-0.15.2/zig.exe');
const object=path.join(out,'trig.o');let result=cp.spawnSync(clang,['c++','--target=wasm32-freestanding','-std=c++17','-O2','-nostdlib','-ffp-contract=off','-fno-exceptions','-fno-rtti','-c',cpp,'-o',object],{encoding:'utf8',windowsHide:true,env:{...process.env,ZIG_LOCAL_CACHE_DIR:path.join(out,'zig-local-cache'),ZIG_GLOBAL_CACHE_DIR:path.join(out,'zig-global-cache')}});if(result.status)throw Error(result.stderr);
result=cp.spawnSync('C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Tools/Llvm/x64/bin/wasm-ld.exe',['--no-entry','--export=sin','--export=cos','--allow-undefined','--strip-all',object,'-o',wasm],{encoding:'utf8',windowsHide:true});if(result.status)throw Error(result.stderr);
const bytes=[...fs.readFileSync(wasm)];const prelude=source.slice(0,source.indexOf('#include'))+`(function(){var m=new WebAssembly.Instance(new WebAssembly.Module(new Uint8Array(${JSON.stringify(bytes)})),{env:{scalbn:function(x,n){return x*Math.pow(2,n);}}});Math.sin=m.exports.sin;Math.cos=m.exports.cos;})();\n`;
fs.writeFileSync(path.join(out,'trig.js'),prelude);console.log(JSON.stringify({wasmBytes:bytes.length,preludeBytes:prelude.length,wasm}));
