'use strict';
// Direct transcription of canonical V8 fdlibm kernels, preserving operation order.
// Arguments outside the medium range use the identical native fdlibm fallback.
const fs=require('fs'),path=require('path');
const source=fs.readFileSync(path.join(__dirname,'v8-math/src/base/ieee754.cc'),'utf8');
function extract(signature){const start=source.indexOf(signature),open=source.indexOf('{',start);let depth=1,i=open+1;for(;depth;i++){if(source[i]==='{')depth++;if(source[i]==='}')depth--;}return source.slice(start,i);}
function cast(s){for(const kind of ['double','int32_t','int']){const prefix='static_cast<'+kind+'>(';let start;while((start=s.indexOf(prefix))>=0){let i=start+prefix.length,depth=1;for(;depth;i++){if(s[i]==='(')depth++;if(s[i]===')')depth--;}const inside=s.slice(start+prefix.length,i-1);s=s.slice(0,start)+(kind==='double'?'('+inside+')':'(('+inside+')|0)')+s.slice(i);}}return s;}
function js(s){return cast(s.replace(/\/\*[\s\S]*?\*\//g,'').replace(/\/\/[^\n]*/g,'').replace(/V8_INLINE\s+/g,'').replace(/\b(?:int32_t|double) (__\w+)\([^)]*\)/,'function $1(x,y,iy)').replace(/static\s+const\s+(?:double|int32_t)\s+/g,'const ').replace(/(?:double|int32_t|uint32_t) ([^;]+);/g,'let $1;').replace(/const (\w+)\[\] = \{([\s\S]*?)\};/g,'const $1=[$2];').replace(/let (\w+)\[3\];/g,'let $1=new Array(3);').replace(/GET_HIGH_WORD\((\w+),\s*([^;]+)\);/g,'$1=highWord($2);').replace(/INSERT_WORDS\((\w+),\s*([^,]+),\s*0\);/g,'$1=word($2);').replace(/\bfabs\(/g,'Math.abs('));}
let rem=extract('int32_t __ieee754_rem_pio2(double x, double *y) {');rem=rem.slice(0,rem.indexOf('/*\n   * all other'))+'return 0;}';
let text=source.slice(0,source.indexOf('#include'))+`(function(){
var bits=new DataView(new ArrayBuffer(8));
function highWord(x){bits.setFloat64(0,x,true);return bits.getInt32(4,true);}
function word(x){bits.setUint32(0,0,true);bits.setInt32(4,x,true);return bits.getFloat64(0,true);}
`+js(rem)+js(extract('V8_INLINE double __kernel_sin'))+js(extract('V8_INLINE double __kernel_cos'))+`
var tail=[0,0];
Math.sin=function(x){x=+x;var ix=highWord(x)&0x7fffffff;if(ix<=0x3fe921fb)return __kernel_sin(x,0,0);if(ix>=0x7ff00000)return x-x;if(ix>0x413921fb)return nativeSin(x);var n=__ieee754_rem_pio2(x,tail);switch(n&3){case 0:return __kernel_sin(tail[0],tail[1],1);case 1:return __kernel_cos(tail[0],tail[1]);case 2:return -__kernel_sin(tail[0],tail[1],1);default:return -__kernel_cos(tail[0],tail[1]);}};
Math.cos=function(x){x=+x;var ix=highWord(x)&0x7fffffff;if(ix<=0x3fe921fb)return __kernel_cos(x,0);if(ix>=0x7ff00000)return x-x;if(ix>0x413921fb)return nativeCos(x);var n=__ieee754_rem_pio2(x,tail);switch(n&3){case 0:return __kernel_cos(tail[0],tail[1]);case 1:return -__kernel_sin(tail[0],tail[1],1);case 2:return -__kernel_cos(tail[0],tail[1]);default:return __kernel_sin(tail[0],tail[1],1);}};
})();`;
const out=path.resolve(__dirname,'../../Saved/Diagnostics/FootIKPort20261030/native-v8/trig-js.js');fs.writeFileSync(out,text);new Function(text);console.log(out);
