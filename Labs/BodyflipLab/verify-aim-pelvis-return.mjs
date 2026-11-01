import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),A=require('./attack-aim.js');
const manifest=JSON.parse(fs.readFileSync(new URL('data/manifest.json',import.meta.url))),{names,parents}=manifest,reference=C.poseFromShared(manifest);
const meta=JSON.parse(fs.readFileSync(new URL('data/vanilla.json',import.meta.url))).clips.find(c=>c.name==='slashL'),bytes=fs.readFileSync(new URL(meta.file,import.meta.url)),clip=C.decode(meta,bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),names,parents);
const track={start:1,armedTime:1.2,hitTime:1.5,end:1.8,returnEnd:2.2},target=[.1,2,1],identity=[0,0,0,1];
const plan=A.create({clip,track,names,parents,reference,sampleHit:()=>reference,evaluateMotion:(delta,context)=>({pose:context.applyDeltaAt(reference,track.hitTime,delta)}),motionSolve:{seed:[.25,.1,-.1,.2,.3,0,0,0],iterations:0}});
const angle=q=>R.length(R.qlog(q)),difference=(a,b)=>angle(R.qm(a,R.qinv(b))),checks=[];
const check=(text,value)=>{assert(value,text);checks.push(text);};
const correction=plan.correction(target),pelvis=names.indexOf('pelvis');
for(const amount of [0,.5,1]){
 for(const time of [1,1.1,1.3,1.5]){
  const d=plan.rotation(time,target,amount,true),expected=R.qexp(R.mul(R.qlog(correction.yaw),amount*plan.weight(time,true)));
  check('Before and at Hit the pelvis aim is retained',difference(d.yaw,expected)<1e-10);
 }
 const time=1.9,returned=plan.rotation(time,target,amount,true),held=plan.rotation(time,target,amount,false);
 check('Pelvis aim finishes within Attack out after Hit',angle(returned.yaw)<1e-10);
 check('Undo rotation off retains aiming orientation',difference(held.yaw,R.qexp(R.mul(R.qlog(correction.yaw),amount)))<1e-10);
 const expected=correction.offsets.map(row=>row.map(v=>v*amount*plan.weight(time,true)));
 check('Joint aim offsets retain original post-hit follow-through',R.length(R.sub(returned.offsets.flat(),expected.flat()))<1e-10);
 const oldPose=plan.applyRotation(reference,{...returned,yaw:held.yaw}),newPose=plan.applyRotation(reference,returned),a=R.localize(oldPose.points,oldPose.q,parents),b=R.localize(newPose.points,newPose.q,parents);
 check('Only pelvis correction changes; limb/spine local rotations are preserved',a.q.every((q,i)=>i===pelvis||difference(q,b.q[i])<1e-10));
}
const end=track.hitTime+track.returnEnd-track.end;
check('Return begins with zero angular velocity at Hit',difference(plan.rotation(track.hitTime+1e-5,target).yaw,plan.rotation(track.hitTime,target).yaw)<1e-10);
check('Return ends with zero angular velocity',angle(plan.rotation(end-1e-5,target).yaw)<1e-10);
const staticPlan=A.create({clip,track,names,parents,reference,sampleHit:()=>reference}),staticGoal=staticPlan.correction(target);
check('Flipless aiming keeps its accepted hold until clip end',difference(staticPlan.rotation(1.7,target).yaw,staticGoal.yaw)<1e-10);
console.log(JSON.stringify({passed:true,checks:checks.length}));
