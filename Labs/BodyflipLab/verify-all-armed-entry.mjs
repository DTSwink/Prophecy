import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),H=require('./attack-inertia.js'),A=require('./jump-attack.js'),K=require('./kick-attack.js'),F=require('./flight.js');
const read=p=>JSON.parse(fs.readFileSync(new URL(p,import.meta.url),'utf8')),bytes=p=>{const b=fs.readFileSync(new URL(p,import.meta.url));return b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength);};
const m=read('data/manifest.json'),{names,parents}=m,reference=C.poseFromShared(m),meta=read('data/vanilla.json'),upper=A.bones(names,parents),p=names.indexOf('pelvis'),run=F.decodeNN(read('data/run-default-drawn.json'));
const base=t=>{const f=Math.max(0,Math.min(run.poses.length-1,t*run.fps)),i=Math.min(run.poses.length-2,Math.floor(f));return C.blend(run.poses[i],run.poses[i+1],f-i,parents);};
const angle=(a,b)=>R.length(R.qlog(R.qm(a,R.qinv(b)))),dist=(a,b)=>R.length(R.sub(a,b)),error=(a,b)=>Math.max(...a.q.map((q,i)=>angle(q,b.q[i])),...a.points.map((v,i)=>dist(v,b.points[i])));
const code=fs.readFileSync(new URL('app.js',import.meta.url),'latin1'),manual=code.slice(code.indexOf('function manualPose('),code.indexOf('function targetPose('));
const legal=H.createProjection(names,parents,reference);
let samples=0,maxNativeError=0,maxEndpointError=0,maxEntryStep=0,maxArmedVelocityJump=0,maxManualParity=0;const checked=[];
for(const metadata of meta.clips){
 const clip=C.decode(metadata,bytes(metadata.file),names,parents),settings={...C.defaults,kickToArmed:true,pelvisAttackCompensation:.5},start=.35,segment={sample:t=>({pose:base(t)}),airStart:start,jumpStart:start,abortTime:Infinity},event={attack:metadata.name,attackIn:.2,attackOut:.25};
 const track=A.create(event,segment,new Map([[metadata.name,clip]]),names,parents,settings,reference),duration=track.duration,armedAt=start+duration;
 assert(Math.abs(track.hitTime-armedAt-(metadata.phases.hit-metadata.phases.armed)/metadata.fps)<1e-10,'Native Armed-to-Hit clock');
 for(const t of [start,track.returnEnd,track.returnEnd+.3])maxEndpointError=Math.max(maxEndpointError,error(legal(track.sample(t).pose),legal(base(t))));
 maxEntryStep=Math.max(maxEntryStep,error(legal(track.sample(start+1e-7).pose),legal(base(start+1e-7))));
 if(!track.fullBodyKick){
  const raw=A.create(event,segment,new Map([[metadata.name,clip]]),names,parents,{...settings,pelvisAttackCompensation:0},reference),targetAt=A.armTrack(clip,names,parents,reference);
  for(let t=start;t<=track.returnEnd;t+=1/120){const pose=track.sample(t).pose;assert(pose.points.flat().every(Number.isFinite));samples++;
   if(t>=armedAt&&t<track.end){const target=A.overlay(base(t),targetAt(metadata.phases.armed+(t-armedAt)*metadata.fps),upper,parents);for(const i of upper)maxNativeError=Math.max(maxNativeError,angle(raw.sample(t).pose.q[i],target.q[i]));}
  }
  const eps=1e-6,local=t=>R.localize(raw.sample(t).pose.points,raw.sample(t).pose.q,parents),a=local(armedAt-eps),b=local(armedAt),c=local(armedAt+eps),rate=(a,b)=>R.mul(R.qlog(R.qm(b,R.qinv(a))),1/eps);
  for(const i of upper)maxArmedVelocityJump=Math.max(maxArmedVelocityJump,dist(rate(a.q[i],b.q[i]),rate(b.q[i],c.q[i])));
  // Pre-Armed keys set the GT distance clock, but are not played on entry.
  for(let i=0;i<=8;i++)assert.equal(raw.sourceFrame(duration*i/8),metadata.phases.armed,'Direct entry skips recorded pre-Armed poses');
  assert(raw.arming&&raw.arming.gtDistance>0,'Distance clock is installed');

 }
 const group=m.clips.find(c=>c.name===metadata.name),variant=group.variants[0],selected=C.decode(variant,bytes(variant.file),names,parents),rate=checked.length%2?.5:2;
 const ctx=vm.createContext({R,C,BodyflipJumpAttack:A,BodyflipKickAttack:K,BodyflipAttackInertia:H,clamp:(v,a,b)=>Math.max(a,Math.min(b,v)),names,parents,idle:reference,clip:selected,settings:{...settings,attack:metadata.name,attackRate:rate,aim:false},flight:{sample:t=>({pose:base(t)})},vanillaManifest:meta,manualResponse:null,simTime:0,attackTime:0});vm.runInContext(manual,ctx);
 const manualAt=t=>{ctx.simTime=t/rate;ctx.attackTime=t;ctx.basePose=base(t/rate);vm.runInContext('output=manualSoft(manualPose(attackTime,basePose),basePose)',ctx);return ctx.output;};
 manualAt(0);const planned=A.create({attack:metadata.name,attackIn:.15,attackOut:.45},{sample:t=>({pose:base(t/rate)}),airStart:0,jumpStart:0,abortTime:Infinity},new Map([[metadata.name,selected]]),names,parents,settings,reference);
 for(let t=0;t<planned.returnEnd+.1;t+=1/60){maxManualParity=Math.max(maxManualParity,error(manualAt(t),planned.sample(t).pose));samples++;}
 assert(Math.abs(ctx.manualResponse.response.returnEnd-planned.returnEnd)<1e-10);const before=JSON.stringify(track.sample(armedAt+.03));track.sample(100);track.sample(0);assert.equal(JSON.stringify(track.sample(armedAt+.03)),before,'Reverse seek deterministic');checked.push(metadata.name);
}
assert.equal(checked.length,meta.clips.length);assert(maxNativeError<1e-8,'Uncompensated authored follow-through retained');assert(maxEndpointError<1e-8);assert(maxEntryStep<1e-5);assert(maxArmedVelocityJump<.03);assert(maxManualParity<1e-8);
const result={attacks:checked.length,samples,maxNativeError,maxEndpointError,maxEntryStep,maxArmedVelocityJump,maxManualParity,checked};fs.writeFileSync(new URL('all-armed-entry-verification.json',import.meta.url),JSON.stringify(result,null,2)+'\n');console.log(result);
