// Fit the actual held shaft to a world target; never redirect a launch packet.
import fs from 'node:fs';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),T=require('./throw-attack.js'),A=require('./attack-aim.js'),H=require('./attack-inertia.js'),M=require('./mass.js'),PA=require('./physical-aim.js'),Work=require('./preparation.js');
const read=p=>JSON.parse(fs.readFileSync(new URL(p,import.meta.url))),manifest=read('data/manifest.json'),{names,parents}=manifest,reference=C.poseFromShared(manifest),pelvis=names.indexOf('pelvis'),chest=names.indexOf('spine_05');T.load(read('data/throws.json'));
const distance=(a,b)=>R.length(R.sub(a,b)),angle=(a,b)=>R.length(R.qlog(R.qm(a,R.qinv(b))));
const project=H.createProjection(names,parents,reference),settings=C.sanitize({kickToArmed:true,motionCompensation:true,distributePelvisTurn:true}),rows=[];let checks=0,maxArmError=0,maxCOMError=0;
for(const motionCompensation of [false,true])for(const moving of [false,true]){
 const offset=[3,2,-5],velocity=moving?[1.7,.4,-.8]:[0,0,0],turn=t=>R.qexp([0,moving?.5+.4*t:0,0]);
 const base=t=>{const q=turn(t);return {pose:{...reference,points:reference.points.map(p=>R.add(R.rotate(q,p),R.add(offset,R.mul(velocity,t)))),q:reference.q.map(v=>R.qm(q,v))}};};
 const track=T.create({id:'target',attack:'big-throw',attackDelay:.25},{sample:base,jumpStart:0,airStart:0,abortTime:Infinity},null,names,parents,{...settings,motionCompensation},reference),raw=t=>project(track.sample(t).pose),launchAt=(pose,map=p=>p)=>{const sample=t=>map(raw(t),t);return track.launchAt(pose,track.releaseVelocity(sample),track.projectileAngularVelocity(sample));},plan=A.create({track,names,parents,reference,sampleHit:raw,launchAt,project});
 const initial=launchAt(raw(track.releaseTime)),anchor=raw(track.releaseTime).points[pelvis],carrier=R.mul(R.sub(base(track.releaseTime).pose.points[pelvis],base(track.releaseTime-.001).pose.points[pelvis]),1000);
 for(const range of [2,4,12])for(const yaw of [-180,-179,-135,-90,-45,0,45,90,135,179,180])for(const pitch of [-40,0,40]){
  const y=yaw*Math.PI/180,p=pitch*Math.PI/180,target=R.add(anchor,R.mul([Math.sin(y)*Math.cos(p),Math.sin(p),Math.cos(y)*Math.cos(p)],range)),at=t=>project(plan.apply(raw(t),t,target)),pose=at(track.releaseTime),packet=track.launchAt(pose,track.releaseVelocity(at),track.projectileAngularVelocity(at)),axis=R.unit(packet.axis),to=R.sub(target,packet.p),along=R.dot(axis,to),miss=R.length(R.cross(axis,to)),error=distance(axis,R.unit(to));
  rows.push({motionCompensation,moving,range,yaw,pitch,error,miss,along,parameters:plan.solution(target).parameters});
  assert.equal(plan.throwDirectionFor(target),null,'default spear solves the actual target point');
  const held=track.heldAt(pose);assert(distance(held.p,packet.p)<1e-12);assert(angle(held.q,packet.q)<1e-12);
  const transported=R.add(R.rotate(R.qm(packet.q,R.qinv(initial.q)),R.sub(initial.v,carrier)),carrier);assert(distance(packet.v,transported)<1e-8,'launch transports saved physics with the actual held frame');
  assert(R.length(R.cross(packet.omega,axis))<1e-8,'spin remains axial');checks+=5;
  for(const time of [track.start,(track.start+track.releaseTime)/2,track.releaseTime,track.end]){
   const before=raw(time),after=at(time),a=R.localize(before.points,before.q,parents),b=R.localize(after.points,after.q,parents);
   for(let i=0;i<names.length;i++)if(/^(clavicle|upperarm|lowerarm|hand|neck)_|^head$/.test(names[i]))maxArmError=Math.max(maxArmError,angle(a.q[i],b.q[i]));
   assert(angle(before.q[pelvis],after.q[pelvis])<1e-10,'aim never pitches pelvis');
   maxCOMError=Math.max(maxCOMError,distance(A.center(before,plan.rig),A.center(after,plan.rig)));checks++;
  }
  const returned=at(track.returnEnd),baseReturn=raw(track.returnEnd);assert(returned.q.every((q,i)=>angle(q,baseReturn.q[i])<1e-10),'shared return removes all aim');checks++;
 }
 // Translation of both the carrier and target leaves the articulation unchanged.
 const target=R.add(anchor,[2,1,-3]),shift=[100,-30,50],shifted=t=>{const p=raw(t);return {...p,points:p.points.map(v=>R.add(v,shift))};},other=A.create({track,names,parents,reference,sampleHit:shifted,launchAt:(p,map=x=>x)=>track.launchAt(p,track.releaseVelocity(t=>map(shifted(t),t))),project}),a=plan.apply(raw(track.releaseTime),track.releaseTime,target),b=other.apply(shifted(track.releaseTime),track.releaseTime,R.add(target,shift));assert(a.q.every((q,i)=>angle(q,b.q[i])<1e-8));checks++;
}
const worst=rows.toSorted((a,b)=>b.error-a.error).slice(0,5);console.log(JSON.stringify({cases:rows.length,checks,maxArmError,maxCOMError,worst},null,2));
assert(maxArmError<1e-9,'authored head and arms remain unchanged relative to torso');assert(maxCOMError<1e-9,'shared COM compensation retained');assert(rows.every(r=>r.error<1e-6&&r.miss<1e-5&&r.along>0),'every tested target lies on the forward release shaft ray');
// Include the existing angular-momentum response and a moving world carrier.
const rig=M.model(names,parents,reference),physicalRows=[];
for(const momentum3D of [false,true])for(const speed of [-2,2]){
 const track=T.create({id:'physical-target',attack:'big-throw',attackDelay:.2},{sample:()=>({pose:reference}),jumpStart:0,airStart:0,abortTime:Infinity},null,names,parents,settings,reference),zero={from:[0,0,0],to:[0,0,0],begin:0,duration:0},spinPlan={referenceI:M.tensor(reference,rig),flip:{...zero,to:[speed,0,0]},twist:zero},seedSource=()=>({pose:reference,root:reference.points[0],phase:'SPACE'}),raw=t=>{const q=R.qexp([Math.max(0,t)*speed,0,0]),pose=M.rotateAboutCOM(track.sample(t).pose,q,rig);return {pose,root:pose.points[0],phase:'SPACE',spin:{rotation:q,spinPlan}};},worldPose=(pose,t)=>({...pose,points:pose.points.map(p=>R.add(p,[2+t,1+.3*t,-4]))}),target=[4,2,-7],physical=PA.create(raw,{start:0,settings:{...settings,momentum3D},names,parents,reference,gravity:0,seedSource},{track,settings:{...settings,momentum3D,aim:true,target},project,worldPose});
 await Work.run(()=>physical.prepare());
 const at=t=>project(worldPose(physical.sample(t).pose,t)),packet=track.launchAt(at(track.releaseTime),track.releaseVelocity(at),track.projectileAngularVelocity(at)),toward=R.sub(target,packet.p),error=distance(R.unit(packet.axis),R.unit(toward)),miss=R.length(R.cross(R.unit(packet.axis),toward)),saved=JSON.stringify(at(track.releaseTime)),evaluations=physical.statistics.evaluations;
 physical.sample(track.returnEnd);physical.sample(0);assert.equal(JSON.stringify(at(track.releaseTime)),saved,'seeking never changes the solved throw');assert.equal(physical.statistics.evaluations,evaluations);
 assert(Math.abs(error-physical.statistics.error)<1e-9,'reported fit matches the actual final release');
 physicalRows.push({momentum3D,speed,...physical.statistics,error,miss,parameters:physical.plan.solution(target).parameters});
}
console.log(JSON.stringify({physical:physicalRows},null,2));assert(physicalRows.every(r=>r.error<1e-4),'final momentum-compensated release points at the target');
