// Attack interpolation must stay on each elbow hinge before target projection.
// Otherwise a smooth source quaternion can cause a discontinuous legal arm.
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),A=require('./jump-attack.js'),F=require('./flight.js'),J=require('./joint-rig.js'),P=require('./rig-profile.js');
const read=p=>JSON.parse(fs.readFileSync(new URL(p,import.meta.url))),bytes=p=>{const b=fs.readFileSync(new URL(p,import.meta.url));return b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength);};
const manifest=read('data/manifest.json'),{names,parents}=manifest,reference=C.poseFromShared(manifest),run=F.decodeNN(read('data/run-default-drawn.json'));
const clips=read('data/vanilla.json').clips.filter(m=>!['KickL','KickR','sweepKick'].includes(m.name)).map(m=>C.decode(m,bytes(m.file),names,parents));
const angle=(a,b)=>R.length(R.qlog(R.qm(a,R.qinv(b))));
const results=[];let samples=0,maxHingeError=0,maxLimitExcursion=0,maxUntouchedError=0,maxEndpointError=0;
for(const native of [false,true]){
 P.install(native?read('fixtures/native-rig.json'):null,names,parents);
 const joints=J.create(names,parents,reference),elbows=joints.joints.filter(j=>j.name.startsWith('lowerarm_'));
 const base=t=>{const f=Math.max(0,Math.min(run.poses.length-1,t*run.fps)),i=Math.min(run.poses.length-2,Math.floor(f));return joints.project(C.blend(run.poses[i],run.poses[i+1],f-i,parents));};
 for(const clip of clips){
  const target=A.armTrack(clip,names,parents,reference);
  for(let f=0;f<clip.poses.length-1;f+=.5){const a=target(f),b=A.attackAt(clip,f,names,parents);for(let i=0;i<names.length;i++)if(!/^(clavicle|upperarm|lowerarm|hand)_/.test(names[i]))maxUntouchedError=Math.max(maxUntouchedError,angle(a.q[i],b.q[i]));}
  for(const direct of [false,true]){
   const start=.35,event={attack:clip.meta.name,attackIn:.2,attackOut:.25},segment={sample:t=>({pose:base(t)}),airStart:start,jumpStart:start,abortTime:Infinity};
   const track=A.create(event,segment,new Map([[clip.meta.name,clip]]),names,parents,{...C.defaults,kickToArmed:direct,softAttackLegs:false,pelvisAttackCompensation:0},reference);
   let maxStep=0,excursion=0,last=null;
   for(let t=start;t<=track.returnEnd;t+=1/240){const pose=track.sample(t).pose,local=R.localize(pose.points,pose.q,parents);for(const j of elbows){const coordinate=joints.coordinates(local.q[j.i],j)[0],error=angle(local.q[j.i],R.qm(R.qexp(R.mul(j.axisLocal,coordinate)),j.bind));excursion=Math.max(excursion,coordinate-j.max,j.min-coordinate);maxLimitExcursion=Math.max(maxLimitExcursion,excursion);maxHingeError=Math.max(maxHingeError,error);assert(error<1e-6,`${clip.meta.name} ${native?'native':'lab'} direct=${direct} t=${t}: elbow off hinge ${error} ${JSON.stringify({q:local.q[j.i],coord:joints.coordinates(local.q[j.i],j),min:j.min,max:j.max})}`);if(last)maxStep=Math.max(maxStep,angle(local.q[j.i],last[j.i]));}last=local.q;samples++;}
   const end=track.sample(track.returnEnd).pose,b=base(track.returnEnd);maxEndpointError=Math.max(maxEndpointError,...end.q.map((q,i)=>angle(q,b.q[i])));
   assert(Math.abs(track.hitTime-track.start-track.duration-(clip.meta.phases.hit-clip.meta.phases.armed)/clip.meta.fps)<1e-10,'Unchanged Armed-to-Hit duration');
   results.push({attack:clip.meta.name,native,direct,limitExcursionDegrees:excursion*180/Math.PI,maxElbowStepDegrees240Hz:maxStep*180/Math.PI});
  }
 }
}
P.install(null,names,parents);
assert(maxUntouchedError<1e-8,'Arm preparation must preserve spine, root and leg source rotations');
assert(maxEndpointError<1e-8,'Return reaches the continuing base pose');
const result={cases:results.length,samples,maxHingeError,maxLimitExcursion,maxUntouchedError,maxEndpointError,results};
fs.writeFileSync(new URL('arm-entry-verification.json',import.meta.url),JSON.stringify(result,null,2)+'\n');
console.log(JSON.stringify({...result,results:undefined},null,2));
