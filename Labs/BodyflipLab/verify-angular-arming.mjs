import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),A=require('./jump-attack.js'),E=require('./attack-entry.js'),T=require('./throw-attack.js');
const read=p=>JSON.parse(fs.readFileSync(new URL(p,import.meta.url))),bytes=p=>{const b=fs.readFileSync(new URL(p,import.meta.url));return b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength);};
const m=read('data/manifest.json'),{names,parents}=m,reference=C.poseFromShared(m),rest=R.localize(reference.points,reference.q,parents);
const clips=read('data/vanilla.json').clips.map(c=>C.decode(c,bytes(c.file),names,parents)),catalog=new Map(clips.map(c=>[c.meta.name,c]));T.load(read('data/throws.json'));
let checks=0;const near=(a,b,label,tol=1e-8)=>{assert(Math.abs(a-b)<tol,`${label}: ${a} vs ${b}`);checks++;};
// Independent scalar examples: cumulative GT path, not endpoint-only distance.
const scalar=x=>({q:[R.qexp([0,x,0])]}),plan=(from,keys)=>E.plan({from:scalar(from),targetAt:f=>scalar(keys[f]),armed:keys.length-1,fps:10,indices:[0],names:['spine_01']});
near(plan(0,[0,.5,1]).duration,.2,'GT-sized travel keeps GT duration');
near(plan(.5,[0,.5,1]).duration,.1,'Half travel takes half the time');
near(plan(-1,[0,.5,1]).duration,.4,'Twice travel takes twice the time');
near(plan(-.5,[0,1,0]).seconds,.05,'GT reversals count toward accumulated distance');
near(plan(1,[0,.5,1]).duration,1/60,'Identical target has only numerical frame floor');

// Optional direct oracle: execute the real live Final Harness distance/LUT
// functions, rather than reproducing their implementation in the assertion.
const harness='C:/Users/singerie/Documents/Cursor/stepper/training/slashes2/final_harness_live_standalone/index.html';
let oracle=null,maxOracleError=0;
if(fs.existsSync(harness)){
 const html=fs.readFileSync(harness,'utf8');
 const extract=name=>{const start=html.indexOf('function '+name+'(');assert(start>=0);const open=html.indexOf('{',start);let depth=1,end=open+1;for(;depth;end++){if(html[end]==='{')depth++;if(html[end]==='}')depth--;}return html.slice(start,end);};
 oracle=vm.createContext({parents,clamp:(x,a,b)=>Math.max(a,Math.min(b,x)),quatFromAxesArray:R.fromAxes,localAxesFromWorld:(a,b)=>R.toAxes(R.qm(R.qinv(R.fromAxes(a)),R.fromAxes(b)))});
 for(const name of ['standaloneLiveAxesAngleDeg','standaloneLiveJointAngularDistanceRad','standaloneLivePoseAngularDistanceRad','standaloneLiveBuildGtAngularLut'])vm.runInContext(extract(name),oracle);
}
const reports=[];
for(const name of [...catalog.keys(),'big-throw','small-throw']){
 const clip=catalog.get(name),event={attack:name,attackIn:1/60,attackOut:.25,throwCharge:37},start=.3;
 const build=pose=>A.create(event,{sample:()=>({pose}),airStart:start,jumpStart:start,abortTime:Infinity},catalog,names,parents,{...C.defaults,kickToArmed:true,pelvisAttackCompensation:0,softAttackLegs:false},reference);
 const a=build(reference),posed={p:rest.p,q:rest.q.slice()};posed.q[names.indexOf('spine_01')]=R.qm(R.qexp([.6,-.4,.3]),posed.q[names.indexOf('spine_01')]);posed.q[names.indexOf('upperarm_r')]=R.qm(R.qexp([-.5,.8,.2]),posed.q[names.indexOf('upperarm_r')]);
 const b=build(R.fk(posed,parents));assert(a.arming&&b.arming,`${name}: shared timing installed`);checks++;
 near(a.arming.duration,a.duration??a.plan.track.lead,`${name} entry uses clock`);
 const armed=a.armedTime??a.start+a.duration,hit=a.hitTime;
 if(clip)near(hit-armed,(clip.meta.phases.hit-clip.meta.phases.armed)/clip.meta.fps,`${name} native Armed-to-Hit`);
 else near(hit-armed,(a.model.releaseFrame-a.model.trigger)/60,`${name} native Armed-to-Release`);
 for(const t of [a.start,a.returnEnd]){const p=a.sample(t),pose=p.pose||p;for(let i=0;i<names.length;i++)near(R.length(R.sub(pose.points[i],reference.points[i])),0,`${name} endpoint`);}
 const saved=JSON.stringify(a.sample((armed+hit)/2));a.sample(a.returnEnd+1);a.sample(0);assert.equal(JSON.stringify(a.sample((armed+hit)/2)),saved,'Reverse seeking');checks++;
 if(oracle&&clip&&!a.fullBodyKick){
  const indices=A.bones(names,parents),set=new Set(indices),targetAt=A.armTrack(clip,names,parents,reference);
  // Remove the external carrier transform, exactly as the airborne controller
  // does. Internal parent-child orientation still uses the harness FK metric.
  const world=local=>{const q=local.q.map((v,i)=>set.has(parents[i])?null:v);for(const i of indices)q[i]=set.has(parents[i])?R.qm(q[parents[i]],local.q[i]):local.q[i];return {axes:q.map(R.toAxes)};};
  oracle.poseFromClipAt=f=>world(targetAt(f));oracle.from=world(rest);oracle.target=world(targetAt(clip.meta.phases.armed));oracle.indices=set;oracle.armed=clip.meta.phases.armed;
  for(const c of a.arming.candidates){oracle.excluded=new Set(indices.filter(i=>!c.includeLowerArms&&names[i].startsWith('lowerarm_')));const expected=vm.runInContext('({gt:standaloneLiveBuildGtAngularLut(armed,indices,excluded).totalDistanceRad,live:standaloneLivePoseAngularDistanceRad(from,target,indices,excluded)})',oracle);maxOracleError=Math.max(maxOracleError,Math.abs(expected.gt-c.gtDistance),Math.abs(expected.live-c.liveDistance));near(expected.gt,c.gtDistance,'Live Harness GT distance',2e-6);near(expected.live,c.liveDistance,'Live Harness current distance',2e-6);}
 }
 reports.push({name,firstDuration:a.arming.duration,changedPoseDuration:b.arming.duration,ratio:a.arming.ratio,postArmedSeconds:hit-armed});
}
assert(reports.every(x=>Math.abs(x.firstDuration-x.changedPoseDuration)>1e-7),'Every attack family responds to the current pose');checks++;
for(const charge of [0,10,100]){
 const track=A.create({attack:'small-throw',throwCharge:charge,attackIn:.2},{sample:()=>({pose:reference}),airStart:0,jumpStart:0,abortTime:Infinity},catalog,names,parents,{...C.defaults,kickToArmed:true},reference);
 near(track.releaseTime-track.armedTime,(track.model.releaseFrame-track.model.trigger)/60,'Charged throw keeps its post-Armed clock');
 for(const t of [0,track.armedTime,track.releaseTime,track.returnEnd]){const pose=track.sample(t).pose;assert(pose.q.flat().concat(pose.points.flat()).every(Number.isFinite),'Zero/full charge remains finite');checks++;}
}
const result={passed:true,checks,attacks:reports.length,liveHarnessOracle:!!oracle,maxOracleError,reports};fs.writeFileSync(new URL('angular-arming-verification.json',import.meta.url),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result,null,2));
