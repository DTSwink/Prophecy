import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),A=require('./jump-attack.js'),G=require('./space-gym.js');
const read=n=>JSON.parse(fs.readFileSync(new URL(n,import.meta.url),'utf8'));
const m=read('data/manifest.json'),{names,parents}=m,reference=C.poseFromShared(m),pelvis=names.indexOf('pelvis'),spine=names.indexOf('spine_01');
const upper=A.bones(names,parents),lower=names.map((_,i)=>i).filter(i=>!upper.includes(i));
const angle=(a,b)=>R.length(R.qlog(R.qm(a,R.qinv(b)))),distance=(a,b)=>R.length(R.sub(a,b));
const base=t=>{const q=R.qm(R.qexp([.4+t*.1,-.6,.2]),reference.q[pelvis]),pose=C.centerPose(reference,q,[0,1.2+t*.03,0]);return {pose,root:pose.points[0]};};
let samples=0,maxUpperError=0,maxLowerError=0,maxBoundaryStep=0;
for(const meta of read('data/vanilla.json').clips){
 const bytes=fs.readFileSync(new URL(meta.file,import.meta.url)),clip=C.decode(meta,bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),names,parents);
 const first=clip.poses[0],sourceJSON=JSON.stringify(clip.poses);
 // Independent world-space oracle: preserve the source upper-body orientation
 // after aligning its initial pelvis with the destination pelvis.
 for(let f=0;f<clip.poses.length-1;f+=.5){
  const source=R.fk(A.at(clip,f,parents),parents),baseline=base(f/meta.fps).pose;
  const expectedAlignment=R.qm(baseline.q[pelvis],R.qinv(first.q[pelvis]));
  const target=A.attackAt(clip,f,names,parents),actual=A.overlay(baseline,target,upper,parents);
  for(const i of upper)maxUpperError=Math.max(maxUpperError,angle(actual.q[i],R.qm(expectedAlignment,source.q[i])));
  for(const i of lower)maxLowerError=Math.max(maxLowerError,distance(actual.points[i],baseline.points[i]),angle(actual.q[i],baseline.q[i]));
  const raw=A.at(clip,f,parents);for(const i of upper.filter(i=>i!==spine))assert(angle(target.q[i],raw.q[i])<1e-7,'Do not double-add pelvis on descendants');
  samples++;
 }
 const attack=A.create({attack:meta.name},G.action({time:.5},base),new Map([[meta.name,clip]]),names,parents,C.defaults);
 for(const time of [attack.start,attack.start+attack.duration,attack.end,attack.end+.25]){
  const a=attack.sample(time-1e-7).pose,b=attack.sample(time+1e-7).pose;
  for(const i of upper)maxBoundaryStep=Math.max(maxBoundaryStep,distance(a.points[i],b.points[i]),angle(a.q[i],b.q[i]));
 }
 assert.equal(JSON.stringify(clip.poses),sourceJSON,'Raw authored clips must remain untouched');
}
assert(maxUpperError<1e-7,'Transferred torso must preserve the complete source rotation');
assert(maxLowerError<1e-7,'Root, pelvis and legs must remain unchanged');
assert(maxBoundaryStep<1e-4,'Entry, Armed and return boundaries must remain continuous');
const result={samples,maxUpperErrorRad:maxUpperError,maxLowerError,maxBoundaryStep};
fs.writeFileSync(new URL('pelvis-transfer-verification.json',import.meta.url),JSON.stringify(result,null,2));console.log(result);
