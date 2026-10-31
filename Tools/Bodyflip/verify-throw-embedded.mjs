// Focused numerical parity of weak/partial throws in Node and native JSRT.
// No editor, browser, scene writes, or physics worlds.
import fs from 'node:fs';
import vm from 'node:vm';
import {spawnSync} from 'node:child_process';
import assert from 'node:assert/strict';
const dir='Saved/Diagnostics/BodyflipPort20261030',runtimeSource=fs.readFileSync('Content/BodyflipLab/Runtime.js','utf8');
const runtime=runtimeSource;
const settings={mode:'spaceGym',motion:'kinematic',aim:true,ramps:false,surfaceIK:false,trimOut:1.4,target:[-1,1,-2],spinLag:.6};
const cases=[.37,37].map(charge=>({name:`small throw ${charge}%`,settings:{...settings,jumpEvents:[{id:'a',time:.1,attack:'small-throw',throwCharge:charge,flip:150,twist:-60,spinVersion:2,jumpPercent:0}]}}));
const times=[0,.1,.10817133334319769,.3,.5,.8,1.2];
const script=`globalThis.__bodyflipAttack=id=>readFile('Content/BodyflipLab/Attacks/'+id+'.json');const B=BodyflipNative.raw;B({op:'assets',value:JSON.parse(readFile('Content/BodyflipLab/Assets.json'))});const cases=${JSON.stringify(cases)},results=[];for(const c of cases){const start=Date.now();B({op:'start',settings:c.settings,horizon:1.4});results.push({name:c.name,samples:${JSON.stringify(times)}.map(time=>B({op:'sample',time})),ms:Date.now()-start});}print(JSON.stringify({results}));`;
let output;const context=vm.createContext({Date,readFile:p=>fs.readFileSync(p,'utf8'),print:s=>output=s});vm.runInContext(runtime,context);vm.runInContext(script,context);const expected=JSON.parse(output);
fs.writeFileSync(dir+'/throw-embedded-expected.json',JSON.stringify(expected));
const compile=spawnSync(dir+'/esbuild/package/esbuild.exe',['--target=es2017'],{input:script,encoding:'utf8'});assert.equal(compile.status,0,compile.stderr);const probe=dir+'/throw-embedded-probe.js';fs.writeFileSync(probe,compile.stdout);
const run=spawnSync(dir+'/chakra-build/Release/bodyflip_chakra_probe.exe',['Content/BodyflipLab/Runtime.js',probe],{encoding:'utf8',maxBuffer:20*1024*1024,timeout:180000,env:{...process.env,BODYFLIP_PROBE_LIMIT_MB:'512',BODYFLIP_PROBE_WATERMARK_MB:'384'}});
assert.equal(run.status,0,run.stderr+' '+run.stdout);const actual=JSON.parse(run.stdout.trim());fs.writeFileSync(dir+'/throw-embedded-actual.json',JSON.stringify(actual));
let maxPosition=0,maxQuaternion=0,maxLaunchVelocity=0,maxLaunchDirection=0;const rows=[];
for(let c=0;c<cases.length;c++){
 let position=0,quaternion=0,launchVelocity=0,launchDirection=0;
 for(let i=0;i<times.length;i++){
  const a=actual.results[c].samples[i],e=expected.results[c].samples[i];assert.equal(a.phase,e.phase);assert.equal(a.releases.length,e.releases.length);
  for(let b=0;b<e.pose.q.length;b++){position=Math.max(position,Math.hypot(...a.pose.points[b].map((x,k)=>x-e.pose.points[b][k])));quaternion=Math.max(quaternion,Math.min(Math.hypot(...a.pose.q[b].map((x,k)=>x-e.pose.q[b][k])),Math.hypot(...a.pose.q[b].map((x,k)=>x+e.pose.q[b][k]))));}
  for(let j=0;j<e.releases.length;j++){const av=a.releases[j].v,ev=e.releases[j].v;launchVelocity=Math.max(launchVelocity,Math.hypot(...av.map((x,k)=>x-ev[k])));launchDirection=Math.max(launchDirection,Math.hypot(...av.map((x,k)=>x/Math.hypot(...av)-ev[k]/Math.hypot(...ev))));}
 }
 maxPosition=Math.max(maxPosition,position);maxQuaternion=Math.max(maxQuaternion,quaternion);maxLaunchVelocity=Math.max(maxLaunchVelocity,launchVelocity);maxLaunchDirection=Math.max(maxLaunchDirection,launchDirection);rows.push({name:cases[c].name,position,quaternion,launchVelocity,launchDirection,nodeMs:expected.results[c].ms,jsrtMs:actual.results[c].ms});
}
const passed=maxPosition<1e-7&&maxQuaternion<1e-7&&maxLaunchVelocity<1e-7&&maxLaunchDirection<1e-6,report={passed,engine:'Windows Chakra JSRT',frames:cases.length*times.length,maxPosition,maxQuaternion,maxLaunchVelocity,maxLaunchDirection,rows};fs.writeFileSync(dir+'/throw-embedded-parity.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));assert(passed,'Weak-throw cross-engine parity differs; see receipt.');
