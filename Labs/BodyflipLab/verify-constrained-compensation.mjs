import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),A=require('./jump-attack.js'),H=require('./attack-inertia.js'),J=require('./joint-rig.js'),P=require('./rig-profile.js'),W=require('./wrist.js'),M=require('./mass.js');
const read=p=>JSON.parse(fs.readFileSync(new URL(p,import.meta.url))),bytes=p=>{const b=fs.readFileSync(new URL(p,import.meta.url));return b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength);};
const manifest=read('data/manifest.json'),{names,parents}=manifest,reference=C.poseFromShared(manifest),pelvis=names.indexOf('pelvis'),spine=names.indexOf('spine_01');
const clips=read('data/vanilla.json').clips.filter(m=>!['KickL','KickR','sweepKick'].includes(m.name)).map(m=>C.decode(m,bytes(m.file),names,parents));
const angle=(a,b)=>R.length(R.qlog(R.qm(a,R.qinv(b))));
let samples=0,cases=0,maxConstraint=0,maxLateCorrection=0,maxInvisibleResponse=0,maxComShift=0;const reports=[];
for(const native of [false,true]){
 P.install(native?read('fixtures/native-rig.json'):null,names,parents);
 const joints=J.create(names,parents,reference),legal=H.createProjection(names,parents,reference),basePose=legal(reference),rig=M.model(names,parents,reference),rest=R.localize(reference.points,reference.q,parents);
 // Two motions that differ only beyond the spine limit must not generate
 // different pelvis reactions: the displayed torso is identical in both.
 const c=joints.joints.find(c=>c.i===spine),source=offset=>t=>{
  const q=rest.q.slice(),twist=offset+.1*Math.sin(t*5);
  q[spine]=R.qm(R.qm(c.parentBasis,W.compose([0,0,0,1],R.qexp([twist,0,0]))),R.qinv(c.basis));
  return R.fk({p:rest.p,q},parents);
 };
 const tracks=[1.2,1.7].map(offset=>H.create({source:source(offset),base:()=>basePose,target:(t,p,b)=>A.compensate(p,b,names,parents,1),start:0,end:.7,names,parents,reference,amount:1}));
 for(let t=0;t<.7;t+=1/60){const a=tracks[0].sample(t),b=tracks[1].sample(t);maxInvisibleResponse=Math.max(maxInvisibleResponse,angle(a.q[pelvis],b.q[pelvis]));}
 for(const clip of clips)for(const soft of [true,false]){
  const settings={...C.defaults,kickToArmed:true,pelvisAttackCompensation:1,softAttackLegs:soft},segment={sample:()=>({pose:basePose}),airStart:.2,jumpStart:.2,abortTime:Infinity};
  const track=A.create({attack:clip.meta.name,attackIn:.2,attackOut:.25},segment,new Map([[clip.meta.name,clip]]),names,parents,settings,reference);
  for(let t=track.start;t<track.returnEnd;t+=1/60){
   const pose=track.sample(t).pose,projected=joints.project(pose);assert(pose.q.flat().concat(pose.points.flat()).every(Number.isFinite));
   const error=Math.max(...joints.inspect(pose).map(c=>c.angularError));maxConstraint=Math.max(maxConstraint,error);
   for(let i=1;i<names.length;i++)maxLateCorrection=Math.max(maxLateCorrection,angle(pose.q[i],projected.q[i]));
   const recentered=legal(pose);maxComShift=Math.max(maxComShift,R.length(R.sub(M.center(pose,rig),M.center(recentered,rig))));samples++;
  }
  const time=track.start+.11,saved=JSON.stringify(track.sample(time));track.sample(track.returnEnd+1);track.sample(0);assert.equal(JSON.stringify(track.sample(time)),saved);
  reports.push({attack:clip.meta.name,native,soft,residual:track.inertia?.diagnostics.maxPlannedResidual??null});cases++;
 }
}
P.install(null,names,parents);
assert(maxConstraint<1e-7,'Compensation output must satisfy the joint limits');
assert(maxLateCorrection<1e-7,'Later anatomical projection must not remove compensation-driven torso motion');
assert(maxInvisibleResponse<1e-6,'Discarded source rotation must not drive the pelvis');
assert(maxComShift<1e-8,'Constraint projection preserves COM');
const result={passed:true,cases,samples,maxConstraint,maxLateCorrection,maxInvisibleResponse,maxComShift,reports};fs.writeFileSync(new URL('constrained-compensation-verification.json',import.meta.url),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify({...result,reports:undefined},null,2));
