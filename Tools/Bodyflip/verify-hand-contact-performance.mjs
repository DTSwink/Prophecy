// Focused exact checks first; --full also replays the saved complete hand fixture.
// Run serially with --max-old-space-size=384 --max-semi-space-size=8 --expose-gc.
import fs from 'node:fs';import vm from 'node:vm';import path from 'node:path';import crypto from 'node:crypto';import assert from 'node:assert/strict';import {spawnSync} from 'node:child_process';
import {sourceRuntime} from './source-runtime-test.mjs';
const base='Saved/Diagnostics/BodyflipPort20261030/v8-parity',out=path.join(base,'hand-profile'),source=sourceRuntime(),hash=s=>crypto.createHash('sha256').update(s).digest('hex');
const official=fs.readFileSync('Content/BodyflipLab/Runtime.js','utf8');let former=source.runtime;
for(const file of ['support','hand-support','bounce']){const current=fs.readFileSync('Labs/BodyflipLab/'+file+'.js','utf8'),previous=fs.readFileSync(path.join(out,file+'-before.js'),'utf8');assert.ok(former.includes(current));former=former.replace(current,previous);}
const assetText=fs.readFileSync('Content/BodyflipLab/Assets.json','utf8'),profileText=fs.readFileSync('Labs/BodyflipLab/fixtures/native-rig.json','utf8'),frameText=fs.readFileSync(path.join(base,'native-hands-expected.json'),'utf8');
function localsProbe(){
 const R=BodyflipRequire('BodyflipLab/recovery.js'),localize=R.localize;let localCalls=0;R.localize=(...args)=>{localCalls++;return localize(...args);};
 const S=BodyflipRequire('BodyflipLab/support.js'),H=BodyflipRequire('BodyflipLab/hand-support.js'),P=BodyflipRequire('BodyflipLab/rig-profile.js'),C=BodyflipRequire('BodyflipLab/core.js');
 const data=JSON.parse(assetText),profile=JSON.parse(profileText),frames=JSON.parse(frameText).frames,results=[],postures=[];let checks=0;
 const freeze=value=>{if(value&&typeof value==='object'&&!Object.isFrozen(value)){for(const x of Object.values(value))freeze(x);Object.freeze(value);}return value;};
 const pose=p=>({...p,axes:p.q.map(R.toAxes)}),floor=S.platformSurface({id:'floor',position:[0,-.2,0],size:[10,.4,20],rotation:[0,0,0,1]});
 for(const native of [false,true]){
  P.install(native?profile:null,data.names,data.parents);H.registerRig(data.reference);
  for(const frame of frames){const p=freeze(pose(frame.pose)),prepared=freeze(localize(p.points,p.q,data.parents));
   for(const kind of ['leg','hand'])for(const side of ['L','R']){
    const l=kind==='leg'?S.leg(p,data.names,side):H.arm(p,data.names,side);
    for(const shift of [[0,0,0],[0,-.2,.1],[.3,.1,-.2],[0,2,0],[0,-2,0]]){
     const target=R.add(p.points[l.foot],shift),solved=S.solve(p,l,target,data.parents,.99,l,.125,.75,prepared);results.push(solved);checks++;
    }
   }
  }
  for(const inverted of [false,true]){
   const original=pose(frames[0].pose),turn=R.qexp([inverted?Math.PI:0,0,0]),origin=R.add(original.points[0],[0,inverted?1:0,0]);
   const p=freeze(pose({points:original.points.map(v=>R.add(origin,R.rotate(turn,R.sub(v,original.points[0])))),q:original.q.map(q=>R.qm(turn,q))})),prepared=freeze(localize(p.points,p.q,data.parents));
   for(const side of ['L','R']){
    const l=H.arm(p,data.names,side),target=floor.closest(p.points[l.foot]),posture=H.posture(p,data.names,data.parents,l,target,floor,C.defaults);
    postures.push({native,inverted,side,canCrouch:posture.canCrouch,amount:posture.amount});
    for(const shift of [[0,0,0],[.1,.1,0],[-.2,.2,.1]]){results.push(posture.solve(p,l,R.add(target,shift),data.parents,.99,l,.125,.75,prepared));checks++;}
    const posed=posture.solve(p,l,target,data.parents,.99,l,.125,.75,prepared),terminal={pose:posed,foot:posed.points[l.foot],rotation:{footQ:posed.q[l.foot],toeQ:posed.q[l.foot]}};
    const contact=H.contactMotion(terminal,l,floor,C.defaults,null,null,{parents:data.parents,solve:posture.solve,bodyAt:()=>p});
    for(const time of [0,.003,.01,.03,.1]){const root=R.add(p.points[0],[time*.2,time*.1,0]);results.push(contact.sample(time,root));checks++;}
   }
  }
 }
 if(!postures.some(p=>p.canCrouch)||!postures.some(p=>!p.canCrouch))throw Error('Both posture branches required');
 return {results,postures,checks,localCalls};
}
const pairSource=fs.readFileSync('Labs/BodyflipLab/verify-pair-bounce.mjs','utf8');
const pairBody=pairSource.slice(pairSource.indexOf('const {add,sub,mul,length,dot}=R')).replace(/console\.log\(JSON\.stringify\(\{passed:true,[^\n]+\}\)\);/,'');
const pairSetup=`(()=>{const R=BodyflipRequire('BodyflipLab/recovery.js'),B=BodyflipRequire('BodyflipLab/bounce.js'),original=B.create,tracks=[];let constraintCalls=0;B.create=config=>{const fn=config.constraints,b=original({...config,...(fn?{constraints:(...args)=>{constraintCalls++;return fn(...args);}}:{})});tracks.push(b);return b;};${pairBody}\nreturn {checks:checks.length,constraintCalls,tracks:tracks.map(b=>({...b,samples:Array.from({length:181},(_,i)=>b.sample(i/60))}))};})()`;
function probe(runtime,code){const context=vm.createContext({assetText,profileText,frameText,structuredClone,assert,crypto});vm.runInContext(runtime,context,{timeout:20000});return JSON.parse(JSON.stringify(vm.runInContext(code,context,{timeout:45000})));}
let result;
if(process.argv.includes('--replay-only')){
 result=JSON.parse(fs.readFileSync(path.join(out,'contact-focused-summary.json'),'utf8'));assert.equal(result.passed,true);assert.deepEqual(result.sources,source.hashes,'Focused checks do not cover current source');
}else{
const localCode='('+localsProbe.toString()+')()';let before=probe(former,localCode),after=probe(source.runtime,localCode);
assert.deepEqual(after.results,before.results);assert.deepEqual(after.postures,before.postures);const local={checks:after.checks,digest:hash(JSON.stringify(after.results)),formerLocalizations:before.localCalls,candidateLocalizations:after.localCalls,postures:after.postures};
before=null;after=null;global.gc?.();before=probe(former,pairSetup);after=probe(source.runtime,pairSetup);assert.deepEqual(after.tracks,before.tracks);assert.equal(after.checks,before.checks);
const pair={cases:after.tracks.length,checks:after.checks,digest:hash(JSON.stringify(after.tracks)),formerConstraintCalls:before.constraintCalls,candidateConstraintCalls:after.constraintCalls};before=null;after=null;former=null;global.gc?.();
result={passed:true,sources:source.hashes,local,pair};fs.writeFileSync(path.join(out,'contact-focused-summary.json'),JSON.stringify(result,null,2));console.log(JSON.stringify({focused:true,local,pair}));
}
if(process.argv.includes('--full')||process.argv.includes('--replay-only')){
 const compile=spawnSync('Saved/Diagnostics/BodyflipPort20261030/esbuild/package/esbuild.exe',['--target=es2017'],{input:source.runtime+fs.readFileSync('Tools/Bodyflip/runtime-adapter.js','utf8'),encoding:'utf8',maxBuffer:8*1024*1024});assert.equal(compile.status,0,compile.stderr);
 const runtime=fs.readFileSync('Tools/Bodyflip/runtime-polyfills.js','utf8')+'\nif(typeof WebAssembly!=="undefined"&&typeof WebAssembly.Module==="function"&&typeof WebAssembly.Instance==="function"){\n'+fs.readFileSync('Tools/FootIK/v8-trig.js','utf8')+'\n}\n'+compile.stdout;
 fs.writeFileSync(path.join(out,'contact-candidate-runtime.js'),runtime);let output;const context=vm.createContext({Date,readFile:p=>fs.readFileSync(p,'utf8'),print:s=>{output=JSON.parse(s);}}),began=performance.now(),cpu=process.cpuUsage();
 vm.runInContext(runtime,context,{timeout:20000});vm.runInContext(fs.readFileSync(path.join(base,'native-hands.js'),'utf8'),context,{timeout:180000});
 const used=process.cpuUsage(cpu);assert.deepEqual(output,JSON.parse(frameText));result.full={frames:output.frames.length,cpuMs:(used.user+used.system)/1000,wallMs:performance.now()-began,peakBytes:process.resourceUsage().maxRSS*1024,candidateSha256:hash(runtime)};
 fs.writeFileSync(path.join(out,'contact-full-summary.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result.full));
}
assert.equal(hash(fs.readFileSync('Content/BodyflipLab/Runtime.js','utf8')),hash(official),'Official package changed');assert.deepEqual(sourceRuntime().hashes,source.hashes,'Candidate sources changed');
