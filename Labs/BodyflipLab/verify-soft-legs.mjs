import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),A=require('./jump-attack.js'),G=require('./space-gym.js'),I=require('./idle.js'),H=require('./attack-inertia.js');
const read=p=>JSON.parse(fs.readFileSync(new URL(p,import.meta.url),'utf8')),buf=p=>{const b=fs.readFileSync(new URL(p,import.meta.url));return b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength);};
const m=read('data/manifest.json'),ref=C.poseFromShared(m),run=I.create(read('data/idle.json'),buf('data/idle.bin'),m).motion(),upper=A.bones(m.names,m.parents);
const base=t=>({pose:run.sample(t),phase:'SPACE'}),angle=(a,b)=>R.length(R.qlog(R.qm(a,R.qinv(b))));
const hinges=H.legHinges(m.names,ref);
let maxUpper=0,maxKnee=0,maxHingeError=0,maxFoot=0,maxPlannedResidual=0,maxStep=0,maxLag=0,elapsedMs=0,samples=0,maxJointStep=0,maxKneeStep=0,maxVelocityJump=0;
const bend=(pose,h)=>{const a=R.unit(R.sub(pose.points[h.knee],pose.points[h.hip])),b=R.unit(R.sub(pose.points[h.foot],pose.points[h.knee]));return Math.acos(Math.max(-1,Math.min(1,R.dot(a,b))));};
// Independent reference semantics: follow hip/knee extend through the strike,
// while the lead hip flexes. This is not the former symmetric speed envelope.
const armedAngles=H.humanAngles(-.16),hitAngles=H.humanAngles(0);
assert(hitAngles[0]<armedAngles[0]);assert(hitAngles[1]<armedAngles[1]);assert(hitAngles[2]>armedAngles[2]+40*Math.PI/180);
const clips=[];let worstStep=null;
// Full-body kicks have separate viewer/app parity coverage in verify-kick-integration.mjs.
for(const meta of read('data/vanilla.json').clips.filter(c=>!C.effector(c.name).startsWith('foot_'))){
 const clip=C.decode(meta,buf(meta.file),m.names,m.parents),catalog=new Map([[meta.name,clip]]),event={attack:meta.name},segment=G.action({time:.5},base);
 for(const amount of [.5,1]){
  const rigid=A.create(event,segment,catalog,m.names,m.parents,{...C.defaults,pelvisAttackCompensation:amount,softAttackLegs:false},ref);
  const soft=A.create(event,segment,catalog,m.names,m.parents,{...C.defaults,pelvisAttackCompensation:amount,softAttackLegs:true},ref),start=performance.now();assert(soft.inertia.legResponse,'Whole-leg response enabled for every attack');
  let previous=null;
  for(let t=.5;t<soft.inertia.stop;t+=1/120){
   const a=rigid.sample(t).pose,b=soft.sample(t).pose,la=R.localize(a.points,a.q,m.parents),lb=R.localize(b.points,b.q,m.parents);
   for(const i of upper)maxUpper=Math.max(maxUpper,angle(a.q[i],b.q[i]));
   for(const h of hinges){const delta=R.qlog(R.qm(R.qinv(la.q[h.knee]),lb.q[h.knee]));maxKnee=Math.max(maxKnee,R.length(delta));maxHingeError=Math.max(maxHingeError,R.length(R.cross(delta,h.kneeAxis)));}
   for(const side of ['l','r'])for(const bone of ['ball']){const i=m.names.indexOf(bone+'_'+side);maxFoot=Math.max(maxFoot,angle(la.q[i],lb.q[i]));}
   if(previous)for(const h of hinges)for(const i of [h.hip,h.knee]){const step=angle(lb.q[i],previous.q[i]);if(i===h.knee)maxKneeStep=Math.max(maxKneeStep,step);if(step>maxJointStep){maxJointStep=step;worstStep={name:meta.name,amount,t,bone:m.names[i],step};}}previous=lb;
   for(let i=0;i<m.names.length;i++)assert(R.length(R.sub(la.p[i],lb.p[i]))<1e-9,'Keep rigid joint sockets');
   assert(b.points.flat().every(Number.isFinite));samples++;
  }
  const snapshot=JSON.stringify(soft.sample(.9));soft.sample(10);soft.sample(.6);assert.equal(JSON.stringify(soft.sample(.9)),snapshot,'Deterministic reverse seeking');
  const ch=soft.inertia.choreography;
  // Whole-character flips carry the reference; world axes cannot redirect it.
  const rotation=R.qexp([.7,-.4,.25]),translation=[1,2,3];
  const transform=p=>({points:p.points.map(v=>R.add(R.rotate(rotation,v),translation)),q:p.q.map(q=>R.qm(rotation,q))});
  const tilted=ch.sample(ch.hitTime,transform(ref)),expected=transform(ch.sample(ch.hitTime,ref));
  for(let i=0;i<m.names.length;i++){assert(angle(tilted.q[i],expected.q[i])<1e-9);assert(R.length(R.sub(tilted.points[i],expected.points[i]))<1e-9);}
  // Check the actual transition velocities in the reference layer at entry,
  // Armed, Hit and return, without the independently sampled yaw solver.
  for(const t of [soft.start,ch.armedTime,ch.hitTime,soft.end,soft.end+C.sanitizeJump(event).attackOut]){
   const eps=1e-5,locals=[t-eps,t,t+eps].map(s=>{const p=ch.sample(s,ref);return R.localize(p.points,p.q,m.parents);});
   for(const h of hinges)for(const i of [h.hip,h.knee]){
    const left=R.mul(R.qlog(R.qm(R.qinv(locals[0].q[i]),locals[1].q[i])),1/eps),right=R.mul(R.qlog(R.qm(R.qinv(locals[1].q[i]),locals[2].q[i])),1/eps);
    maxVelocityJump=Math.max(maxVelocityJump,R.length(R.sub(left,right)));
   }
  }
  // Deeply folded starting legs may extend as well as flex; neither may invert.
  for(const desired of [0,30,120,149]){
   const local=R.localize(ref.points,ref.q,m.parents);
   for(const h of hinges)local.q[h.knee]=R.qm(local.q[h.knee],R.qexp(R.mul(h.kneeAxis,desired*Math.PI/180-bend(ref,h))));
   const posed=R.fk(local,m.parents);
   for(const t of [ch.armedTime,ch.hitTime])for(const h of hinges){const after=ch.sample(t,posed);assert(bend(after,h)<=150*Math.PI/180+1e-4);const v=R.unit(R.sub(after.points[h.knee],after.points[h.hip])),w=R.unit(R.sub(after.points[h.foot],after.points[h.knee]));assert(R.dot(R.cross(v,w),R.rotate(after.q[h.knee],h.kneeAxis))>=-1e-6,'Knee does not bend backward');}
  }
  const d=soft.inertia.diagnostics;maxPlannedResidual=Math.max(maxPlannedResidual,d.maxPlannedResidual);maxStep=Math.max(maxStep,d.maxStep);maxLag=Math.max(maxLag,d.maxLag);elapsedMs+=performance.now()-start;
  clips.push({name:meta.name,amount,...d});
 }
}
console.log({maxUpper,maxKnee,maxHingeError,maxFoot,maxPlannedResidual,maxLag,maxJointStep,maxKneeStep,maxVelocityJump,worstStep});
assert(maxUpper<1e-9);assert(maxHingeError<1e-9);assert(maxFoot<1e-9);assert(maxKnee>30*Math.PI/180&&maxKnee<135*Math.PI/180);assert(maxPlannedResidual<.005);assert(maxLag<=Math.PI/10+1e-8);assert(maxKneeStep<8*Math.PI/180);assert(maxVelocityJump<.05);
const result={samples,maxUpper,maxKnee,maxHingeError,maxFoot,maxPlannedResidual,maxStep,maxLag,maxJointStep,maxKneeStep,maxVelocityJump,elapsedMs,clips};
fs.writeFileSync(new URL('soft-legs-verification.json',import.meta.url),JSON.stringify(result,null,2));console.log({...result,clips:clips.length});
