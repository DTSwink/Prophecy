import fs from 'node:fs';
import vm from 'node:vm';
import {spawnSync} from 'node:child_process';
import assert from 'node:assert/strict';

const dir='Saved/Diagnostics/BodyflipPort20261030',runtime=fs.readFileSync('Content/BodyflipLab/Runtime.js','utf8');
const script=`
globalThis.__bodyflipAttack=id=>readFile('Content/BodyflipLab/Attacks/'+id+'.json');
const B=BodyflipNative.raw,profile=JSON.parse(readFile('Labs/BodyflipLab/fixtures/native-rig.json'));
B({op:'assets',value:JSON.parse(readFile('Content/BodyflipLab/Assets.json'))});
const settings={mode:'spaceGym',trimOut:.4,aim:false,spinLag:.6,kickToArmed:true,jumpEvents:[{id:'kick',time:0,jumpPercent:0,spinVersion:2,flip:120,twist:60,attack:'KickL'}]},results=[];
for(const native of [true,false]){const start=B({op:'start',settings,rigProfile:native?profile:null,horizon:1/60});const frames=[0,.1,.2,.35].map(time=>B({op:'sample',time}));results.push({native,start,frames});}
print(JSON.stringify(results));
`;
let output;const context=vm.createContext({Date,readFile:p=>fs.readFileSync(p,'utf8'),print:s=>output=s});vm.runInContext(runtime,context);vm.runInContext(script,context);const expected=JSON.parse(output);
const compile=spawnSync(dir+'/esbuild/package/esbuild.exe',['--target=es2017'],{input:script,encoding:'utf8'});assert.equal(compile.status,0,compile.stderr);fs.writeFileSync(dir+'/profile-embedded-probe.js',compile.stdout);
const begin=performance.now(),run=spawnSync(dir+'/chakra-build/Release/bodyflip_chakra_probe.exe',['Content/BodyflipLab/Runtime.js',dir+'/profile-embedded-probe.js'],{encoding:'utf8',timeout:60000,maxBuffer:4*1024*1024,env:{...process.env,BODYFLIP_PROBE_WATERMARK_MB:'384',BODYFLIP_PROBE_LIMIT_MB:'512'}});
assert.equal(run.status,0,run.stderr||run.stdout);const actual=JSON.parse(run.stdout);assert.equal(actual[0].start.rigSchema,'bodyflip-native-rig-v1');assert.equal(actual[1].start.rigSchema,undefined);
let position=0,quaternion=0;for(let c=0;c<2;c++)for(let f=0;f<4;f++){const a=actual[c].frames[f],e=expected[c].frames[f];assert.equal(a.phase,e.phase);for(let b=0;b<26;b++){position=Math.max(position,Math.hypot(...a.pose.points[b].map((v,k)=>v-e.pose.points[b][k])));quaternion=Math.max(quaternion,1-Math.abs(a.pose.q[b].reduce((s,v,k)=>s+v*e.pose.q[b][k],0)));}}
assert(position<1e-8&&quaternion<1e-10,JSON.stringify({position,quaternion}));
const report={passed:true,frames:8,nativeProfileInstalled:true,defaultRestored:true,maxPosition:position,maxQuaternion:quaternion,jsrtSeconds:(performance.now()-begin)/1000,runtime:JSON.parse(fs.readFileSync('Content/BodyflipLab/Receipt.json','utf8')).runtime};fs.writeFileSync(dir+'/profile-embedded-parity.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report));
