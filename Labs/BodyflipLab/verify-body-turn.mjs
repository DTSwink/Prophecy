// Regression for authored revolutions: parity alone can agree on a broken pose.
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),K=require('./kick-attack.js'),B=require('./airborne-motion.js'),H=require('./attack-inertia.js');
const read=p=>JSON.parse(fs.readFileSync(new URL(p,import.meta.url))),buffer=p=>{const b=fs.readFileSync(new URL(p,import.meta.url));return b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength);};
const {names,parents,...manifest}=read('data/manifest.json'),reference=C.poseFromShared({...manifest,names,parents}),metadata=read('data/vanilla.json'),pelvis=names.indexOf('pelvis'),rig=H.model(names,parents,reference);
const distance=(a,b)=>R.length(R.sub(a,b)),angle=(a,b)=>R.length(R.qlog(R.qm(a,R.qinv(b)))),com=p=>B.center(H.bodies(p,rig),rig),error=(a,b)=>Math.max(...a.q.map((q,i)=>angle(q,b.q[i])),...a.points.slice(1).map((p,i)=>distance(p,b.points[i+1])));
const centered=p=>({...p,points:p.points.map(x=>R.add(x,R.sub(com(reference),com(p))))});
const forward=R.rotate(R.qinv(reference.q[pelvis]),[0,0,1]);
let samples=0,maxStrikeError=0,maxReconstructionError=0,maxCOMError=0,maxJoinError=0,maxFinalError=0;
const results=[];
for(const name of ['KickL','KickR','sweepKick'])for(const directArmed of [false,true]){
 const meta=metadata.clips.find(c=>c.name===name),clip=C.decode(meta,buffer(meta.file),names,parents),plan=K.preview({clip,names,parents,reference,directArmed}),{track,response}=plan;
 let hip=names.indexOf(C.effector(name));while(parents[hip]!==pelvis)hip=parents[hip];
 const chain=names.map((_,i)=>i).filter(i=>{for(let j=i;j>=0;j=parents[j])if(j===hip)return true;return false;});
 const turn=B.bodyTurn(track,names,reference),root=reference.q[0];
 let sourceYaw=0,actualYaw=0,maxYawError=0,largestSourceStep=0,largestActualStep=0;
 for(let n=0;n<=Math.ceil(track.stop*240);n++){
  const t=Math.min(track.stop,n/240),raw=track.sample(t),p=response.sample(t);
  assert(p.points.flat().every(Number.isFinite));
  maxCOMError=Math.max(maxCOMError,distance(com(p),com(reference)));
  maxReconstructionError=Math.max(maxReconstructionError,error(response.uncorrected(t),centered(raw)));
  assert(angle(turn.remove(t).q[0],root)<1e-12,'Removing body turn must preserve root orientation');
  assert(angle(p.q[0],root)<1e-12,'Restoring body turn must preserve root orientation');
  if(t<=track.end){
   for(const i of chain)maxStrikeError=Math.max(maxStrikeError,angle(p.q[i],raw.q[i]),distance(R.sub(p.points[i],p.points[hip]),R.sub(raw.points[i],raw.points[hip])));
   const a=R.rotate(raw.q[pelvis],forward),b=R.rotate(p.q[pelvis],forward),yaw=v=>Math.atan2(v[0],v[2]);
   const step=(v,previous)=>Math.atan2(Math.sin(v-previous),Math.cos(v-previous));
   const sa=step(yaw(a),sourceYaw),sb=step(yaw(b),actualYaw);sourceYaw+=sa;actualYaw+=sb;
   maxYawError=Math.max(maxYawError,Math.abs(sourceYaw-actualYaw));largestSourceStep=Math.max(largestSourceStep,Math.abs(sa));largestActualStep=Math.max(largestActualStep,Math.abs(sb));
  }
  samples++;
 }
 // Recovery keeps the source's follow-through. It removes added balance,
 // rather than replacing the absolute pelvis trajectory with a Hit-to-idle arc.
 const end=response.recoveryEnd;assert(end<=track.stop,'No longer animation');
 maxFinalError=Math.max(maxFinalError,error(response.sample(end),centered(track.sample(end))),error(response.sample(track.stop),reference));
 const eps=1e-6;
 for(const t of [track.lead,plan.hitTime,response.recoveryEnd,track.end,track.stop]){
  const p=[t-eps,t,t+eps].map(x=>response.sample(x));
  for(let i=1;i<names.length;i++){
   const left=R.mul(R.qlog(R.qm(p[1].q[i],R.qinv(p[0].q[i]))),1/eps),right=R.mul(R.qlog(R.qm(p[2].q[i],R.qinv(p[1].q[i]))),1/eps);
   maxJoinError=Math.max(maxJoinError,distance(left,right));
  }
 }
 if(name==='sweepKick'){
  assert(Math.abs(sourceYaw+2*Math.PI)<.03,'Fixture contains a full revolution');
  assert(Math.abs(actualYaw-sourceYaw)<.03,'Processed pelvis must finish the revolution');
  assert(maxYawError<.75,'Balance must not unwind the body against its authored heading');
  assert(largestActualStep<.25,'No heading wrap snap at intermediate frames');
 }
 const seek=JSON.stringify(response.sample(plan.hitTime+.07));response.sample(0);response.sample(100);assert.equal(JSON.stringify(response.sample(plan.hitTime+.07)),seek);
 results.push({name,directArmed,sourceYawDegrees:sourceYaw*180/Math.PI,actualYawDegrees:actualYaw*180/Math.PI,maxYawErrorDegrees:maxYawError*180/Math.PI,largestSourceStepDegrees:largestSourceStep*180/Math.PI,largestActualStepDegrees:largestActualStep*180/Math.PI,diagnostics:response.diagnostics});
}
assert(maxStrikeError<1e-8,'Keep the entire striking-leg motion, including after Hit');
assert(maxReconstructionError<1e-8,'Turn decomposition must reconstruct every recorded pose');
assert(maxCOMError<1e-8);assert(maxFinalError<1e-8,'No residual final tilt');
assert(maxJoinError<.05,'Continuous angular velocity at entry/Hit/return: '+maxJoinError);
const result={samples,maxStrikeError,maxReconstructionError,maxCOMError,maxJoinError,maxFinalError,results};
fs.writeFileSync(new URL('body-turn-verification.json',import.meta.url),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result,null,2));
