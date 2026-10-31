// Small diagnostic only: no authored assets, solver state or production patches.
import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import assert from 'node:assert/strict';
const trigDiagnostic=process.argv.includes('--trig-diagnostic');
const out='Saved/Diagnostics/BodyflipPort20261030/'+(trigDiagnostic?'math-engines-trig':'math-engines');fs.mkdirSync(out,{recursive:true});
const inputFile=out+'/input.js';
fs.writeFileSync(inputFile,`
const inputs=[0,-0,1,-1,Math.PI,-Math.PI,Math.PI/2,1e-12,-1e-12,1-1e-12,-1+1e-12];
let seed=123456789;for(let i=0;i<96;i++){seed=(Math.imul(seed,1664525)+1013904223)|0;inputs.push(seed/2147483648*6);}
const funcs=[['sin',x=>Math.sin(x),x=>[x]],['cos',x=>Math.cos(x),x=>[x]],['acos',x=>Math.acos(x),x=>[Math.max(-1,Math.min(1,x/6))]],['atan2',(x,y)=>Math.atan2(x,y),x=>[x,1.5*x+.1]],['hypot',(x,y,z)=>Math.hypot(x,y,z),x=>[x,x/3,.1-x/2]],['exp',x=>Math.exp(x),x=>[x]]];
const bytes=new DataView(new ArrayBuffer(8)),hex=x=>{bytes.setFloat64(0,x);return bytes.getUint32(0).toString(16).padStart(8,'0')+bytes.getUint32(4).toString(16).padStart(8,'0');};
function sample(){return funcs.flatMap(([name,fn,args])=>inputs.map(x=>{const a=args(x),v=fn(...a);return {name,args:a,value:v,bits:hex(v)};}));}
const cold=sample();let sink=0;for(let pass=0;pass<128;pass++)for(const [,fn,args]of funcs)for(const x of inputs)sink+=fn(...args(x));const warm=sample();print(JSON.stringify({cold,warm,sink}));
`);
const files=[...(trigDiagnostic?['Tools/FootIK/v8-trig.js']:[]),inputFile];
const node=spawnSync(process.execPath,['--max-old-space-size=64','-e',"globalThis.print=x=>console.log(x);for(const f of process.argv.slice(1))require('node:vm').runInThisContext(require('node:fs').readFileSync(f,'utf8'));",...files],{encoding:'utf8',timeout:30000,maxBuffer:1024*1024});
assert.equal(node.status,0,node.stderr||node.error?.message);fs.writeFileSync(out+'/node.json',node.stdout);
const native=spawnSync('Saved/Diagnostics/FootIKPort20261030/math-build/Release/footik_v8_probe.exe',files,{encoding:'utf8',timeout:30000,maxBuffer:1024*1024,env:{...process.env,FOOTIK_V8_DLL:path.resolve('Content/FootIKLab/V8/ClearScriptV8.win-x64.dll')}});
assert.equal(native.status,0,native.stderr||native.error?.message);fs.writeFileSync(out+'/v8.json',native.stdout);
const a=JSON.parse(node.stdout),b=JSON.parse(native.stdout),differences=[];
for(const phase of ['cold','warm'])for(let i=0;i<a[phase].length;i++){const x=a[phase][i],y=b[phase][i];assert.deepEqual(x.args,y.args);if(x.bits!==y.bits)differences.push({phase,name:x.name,args:x.args,node:x.value,v8:y.value,absolute:Math.abs(x.value-y.value),ulp:String(BigInt('0x'+x.bits)>BigInt('0x'+y.bits)?BigInt('0x'+x.bits)-BigInt('0x'+y.bits):BigInt('0x'+y.bits)-BigInt('0x'+x.bits))});}
const runtimeReceipt=JSON.parse(fs.readFileSync('Content/BodyflipLab/Receipt.json','utf8')),clockReferences=[];
for(const name of Object.keys(runtimeReceipt.sources)){const lines=fs.readFileSync('Labs/'+name,'utf8').split('\n');for(let i=0;i<lines.length;i++)if(/performance\.now|Date\.now|nativeThreadMilliseconds/.test(lines[i]))clockReferences.push({name,line:i+1,text:lines[i].trim()});}
const report={trigDiagnostic,samplesPerPhase:a.cold.length,phases:2,differences,clockReferences,nativeMetrics:native.stderr.trim()};fs.writeFileSync(out+'/receipt.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
