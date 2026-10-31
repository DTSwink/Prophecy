// Full returned-frame comparison, not just the displayed bone positions.
// Serial isolated processes; no editor, browser, game or live scene mutation.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawnSync} from 'node:child_process';
import assert from 'node:assert/strict';

const trigDiagnostic=process.argv.includes('--trig-diagnostic');
const dir='Saved/Diagnostics/BodyflipPort20261030',out=dir+(trigDiagnostic?'/v8-trig-diagnostic':'/v8-parity');
fs.mkdirSync(out,{recursive:true});
const runtime=fs.readFileSync('Content/BodyflipLab/Runtime.js','utf8');
const hash=x=>crypto.createHash('sha256').update(x).digest('hex');
const nodeOracle=out+'/node-oracle.cjs';
fs.writeFileSync(nodeOracle,`const fs=require('node:fs'),vm=require('node:vm');
const began=performance.now(),context=vm.createContext({Date,readFile:p=>fs.readFileSync(p,'utf8'),print:s=>process.stdout.write(s+'\\n')});
if(process.argv[4])vm.runInContext(fs.readFileSync(process.argv[4],'utf8'),context);
vm.runInContext(fs.readFileSync(process.argv[2],'utf8'),context);vm.runInContext(fs.readFileSync(process.argv[3],'utf8'),context);
const r=process.resourceUsage();process.stderr.write(JSON.stringify({cpuMs:(r.userCPUTime+r.systemCPUTime)/1000,wallMs:performance.now()-began,peakBytes:r.maxRSS*1024})+'\\n');
`);
const base={mode:'spaceGym',motion:'kinematic',aim:false,spinLag:.6,trimOut:1.2};
const event={id:'action',time:.1,jumpPercent:0,spinVersion:2,flip:180,twist:35,attack:'none'};
const floor={id:'floor',position:[0,-.2,0],size:[10,.4,20],rotation:[0,0,0,1]};
let cases=[
  {name:'mixed-ramp',settings:{...base,jumpEvents:[event]}},
  {name:'instant-reversal',settings:{...base,jumpEvents:[{...event,instantSpin:true},{...event,id:'reverse',time:.35,flip:-90,twist:120,instantSpin:true}]}},
  {name:'native-kick',native:true,settings:{...base,kickToArmed:true,jumpEvents:[{...event,attack:'KickL'}]}},
  {name:'native-slash',native:true,settings:{...base,kickToArmed:true,aim:true,target:[-.3,2.7,14.5],pelvisAttackCompensation:1,jumpEvents:[{...event,flip:-200,twist:150,attack:'slashL'}]}},
  {name:'native-armed-big-throw',native:true,settings:{...base,kickToArmed:true,aim:true,target:[-1,1,-2],jumpEvents:[{...event,attack:'big-throw'}]}},
  {name:'native-armed-small-throw',native:true,settings:{...base,kickToArmed:true,aim:true,target:[-1,1,-2],jumpEvents:[{...event,attack:'small-throw',throwCharge:37}]}},
  {name:'sweep-behind',settings:{...base,aim:true,target:[-1,1.3,-2],jumpEvents:[{...event,flip:190,twist:80,attack:'sweepKick'}]}},
  {name:'big-throw',settings:{...base,aim:true,target:[-1,1,-2],jumpEvents:[{...event,attack:'big-throw',throwCharge:37}]}},
  {name:'weak-small-throw',settings:{...base,aim:true,target:[-1,1,-2],jumpEvents:[{...event,attack:'small-throw',throwCharge:.37}]}},
  {name:'native-foot',native:true,settings:{...base,mode:'idle',ramps:false,platforms:[floor],jumpEvents:[{...event,jumpPercent:35,flip:100}]}},
  {name:'native-hands',native:true,settings:{...base,mode:'idle',ramps:false,platforms:[floor],jumpEvents:[{...event,jumpPercent:35,pushWith:'handBoth',flip:60}]}},
];
const filter=process.argv.find(x=>x.startsWith('--case='))?.slice(7);
if(filter)cases=cases.filter(x=>x.name.includes(filter));
assert(cases.length,'No matching parity cases');
const times=[0,1/60,.1,.2,.3,.5,.8,1.2];
const oracle=process.argv.includes('--chakra');
const reports=[];let comparisons=0,maxDifference=0,worstPath='';
const receiptFile=`${out}/${oracle?'chakra':'v8'}-receipt.json`;
function receipt(passed,error){const r={passed,engine:oracle?'Chakra JSRT':'ClearScript V8 7.5.1.1',trigDiagnostic,trigSha256:trigDiagnostic?hash(fs.readFileSync('Tools/FootIK/v8-trig.js')):null,runtimeSha256:hash(runtime),rigSha256:hash(fs.readFileSync('Labs/BodyflipLab/fixtures/native-rig.json')),requestedCases:cases.length,frames:reports.length*times.length,numericComparisons:comparisons,maxDifference,worstPath,cases:reports};if(error)r.error=error;fs.writeFileSync(receiptFile,JSON.stringify(r,null,2));return r;}
receipt(false,'In progress');
function compare(a,b,where){
  assert.equal(typeof a,typeof b,where+' type');
  if(typeof a==='number'){
    assert(Number.isFinite(a)&&Number.isFinite(b),where+' finite');
    const difference=Math.abs(a-b);comparisons++;
    if(difference>maxDifference){maxDifference=difference;worstPath=where;}
    assert(difference<=1e-7+1e-10*Math.max(Math.abs(a),Math.abs(b)),where+': '+a+' vs '+b);
  }else if(a===null||typeof a!=='object')assert.equal(a,b,where);
  else{assert.deepEqual(Object.keys(a).sort(),Object.keys(b).sort(),where+' keys');for(const key of Object.keys(a))compare(a[key],b[key],where+'.'+key);}
}
try{for(const c of cases){
  const script=`
globalThis.__bodyflipAttack=id=>{const index=JSON.parse(readFile('Content/BodyflipLab/AttackIndex.json'));return readFile('Content/BodyflipLab/Attacks/'+index[id]);};
globalThis.__bodyflipNN=json=>{const r=JSON.parse(json),last=r.seeds.at(-1),origin=last.points[0];return JSON.stringify({names:r.names.slice(1),fps:30,duration:(r.frames-1)/30,roots:r.roots.slice(0,r.frames),poses:Array.from({length:r.frames},(_,i)=>({points:last.points.slice(1).map(p=>p.map((v,k)=>v-origin[k]+r.roots[i][k])),axes:last.axes.slice(1)}))});};
const B=BodyflipNative.raw;B({op:'assets',value:JSON.parse(readFile('Content/BodyflipLab/Assets.json'))});
const start=B({op:'start',settings:${JSON.stringify(c.settings)},rigProfile:${c.native?"JSON.parse(readFile('Labs/BodyflipLab/fixtures/native-rig.json'))":'null'},horizon:1/60});
const frames=${JSON.stringify(times)}.map(time=>B({op:'sample',time}));print(JSON.stringify({start,frames}));
`;
  const scriptFile=`${out}/${c.name}.js`;fs.writeFileSync(scriptFile,script);
  // The oracle process exits before native V8 is launched. The driver retains
  // only compact output frames, never both engines' authored-asset heaps.
  const before=performance.now(),reference=spawnSync(process.execPath,['--max-old-space-size=256',nodeOracle,'Content/BodyflipLab/Runtime.js',scriptFile,...(trigDiagnostic?['Tools/FootIK/v8-trig.js']:[])],{encoding:'utf8',timeout:180000,maxBuffer:16*1024*1024});
  fs.writeFileSync(`${out}/${c.name}-node.log`,reference.stderr||'');
  assert.equal(reference.status,0,reference.error?.message||reference.stderr||reference.stdout);
  const nodeSeconds=(performance.now()-before)/1000,expected=JSON.parse(reference.stdout.trim()),nodeMetrics=JSON.parse(reference.stderr.trim());
  fs.writeFileSync(`${out}/${c.name}-expected.json`,reference.stdout);
  const exe=oracle?dir+'/chakra-build/Release/bodyflip_chakra_probe.exe':'Saved/Diagnostics/FootIKPort20261030/math-build/Release/footik_v8_probe.exe';
  const begun=performance.now(),run=spawnSync(exe,[...(trigDiagnostic?['Tools/FootIK/v8-trig.js']:[]),'Content/BodyflipLab/Runtime.js',scriptFile],{encoding:'utf8',timeout:180000,maxBuffer:16*1024*1024,env:{...process.env,FOOTIK_V8_DLL:path.resolve('Content/FootIKLab/V8/ClearScriptV8.win-x64.dll'),BODYFLIP_PROBE_WATERMARK_MB:'384',BODYFLIP_PROBE_LIMIT_MB:'512'}});
  fs.writeFileSync(`${out}/${c.name}-${oracle?'chakra':'v8'}.log`,run.stderr||'');
  assert.equal(run.status,0,run.error?.message||run.stderr||run.stdout);
  const actual=JSON.parse(run.stdout.trim());fs.writeFileSync(`${out}/${c.name}-${oracle?'chakra':'v8'}.json`,run.stdout);
  compare(actual,expected,c.name);
  const nativeMetrics=run.stderr.match(/PROBE_METRICS (\{[^\n]+\})/);
  reports.push({name:c.name,frames:times.length,nodeSeconds,nativeSeconds:(performance.now()-begun)/1000,nodeMetrics,nativeMetrics:nativeMetrics?JSON.parse(nativeMetrics[1]):null,processMetrics:run.stderr.trim()});
  receipt(false,'In progress');console.log(JSON.stringify({completed:c.name,...reports.at(-1)}));
}}catch(error){receipt(false,String(error.stack||error));throw error;}
console.log(JSON.stringify(receipt(true),null,2));
