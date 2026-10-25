import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),K=require('./footik.js'),R=require('./recovery.js'),S=require('./support.js'),T=require('./terrain.js'),{load}=require('./test-bank.cjs');
const before=JSON.parse(fs.readFileSync(new URL('data/first-riser-before.json',import.meta.url))),terrain=T.create(before.settings),run=load('walk',before.settings.phase);
const start=performance.now(),model=K.prepare(run,before.settings),prepareMs=performance.now()-start,checks=[];
const check=(name,ok)=>{assert(ok,name);checks.push(name);};
// Independent surface sampling: bilinear grids over all six shoe faces,
// without using the production polygon clipping or floorFor implementation.
function penetration(points,resolution=12){
 let worst=0;
 for(let base=0;base<points.length;base+=8)for(const fixed of [1,2,4])for(const sign of [0,fixed]){
  const varying=[1,2,4].filter(b=>b!==fixed),a=points[base+sign],b=points[base+sign+varying[0]],c=points[base+sign+varying[1]];
  for(let u=0;u<=resolution;u++)for(let v=0;v<=resolution;v++){
   const p=a.map((x,j)=>x+(b[j]-x)*u/resolution+(c[j]-x)*v/resolution);
   const tile=terrain.hit(p[0],p[2]);if(tile)worst=Math.max(worst,tile.y-p[1]);
  }
 }return worst;
}
const points=(f,side)=>{const l=S.leg(f.pose,run.names,side);return S.footPoints(f.pose,l.foot,l.toe,side).map(o=>R.add(f.pose.points[l.foot],o));};
const oldPenetration=penetration(before.points,64),newPenetration=penetration(points(model.sample(41/60),'L'),64);
check('Independent shoe-face sampling reproduces the old frame41 riser clip',oldPenetration>.06);
check('Frame41 left shoe clears the first riser across its faces and edges',newPenetration<1e-5);
let maxPenetration=0,maxAngle=0,maxDistance=0,maxEntryDistance=0,maxPinError=0;
for(let i=0;i<model.frames.length;i++)for(const side of ['L','R']){
 const f=model.frames[i],l=S.leg(f.pose,run.names,side),contact=f.feet[side==='L'?0:1].contact;
 // Terrain IK leaves pure flat NN frames alone, including source sole noise.
 if(f.influence>0)maxPenetration=Math.max(maxPenetration,penetration(points(f,side)));
 if(contact)maxPinError=Math.max(maxPinError,R.length(R.sub(R.add(f.pose.points[l.foot],R.rotate(f.pose.q[l.foot],contact.localPoint)),contact.point)));
 if(i)for(const j of [l.hip,l.knee,l.foot,l.toe]){
  const p=model.frames[i-1].pose;
  maxAngle=Math.max(maxAngle,2*Math.acos(Math.min(1,Math.abs(R.dot(f.pose.q[j],p.q[j]))))*180/Math.PI);
  const distance=R.length(R.sub(f.pose.points[j],p.points[j]));
  maxDistance=Math.max(maxDistance,distance);
  if(i>=56&&i<=110)maxEntryDistance=Math.max(maxEntryDistance,distance);
 }
}
check('Current phase whole-course corrected shoe faces clear terrain',maxPenetration<1e-5);
check('Current phase retains the walking angular-motion bound',maxAngle<15);
check('Current phase whole-course retains the walking displacement bound',maxDistance<.09);
check('Current phase first-stair approach retains the walking displacement bound',maxEntryDistance<.09);
check('Material heel/toe pins remain fixed',maxPinError<1e-6);
check('Leg targets remain reachable',model.metrics.maxReachError<1e-5);
check('Flat approach and exit retain exact NN poses',model.frames.filter(f=>f.influence===0).every(f=>f.pose===f.raw));
const result={passed:true,checks,phase:before.settings.phase,prepareMs,oldPenetration,newPenetration,maxPenetration,maxAngle,maxDistance,maxEntryDistance,maxPinError};
fs.writeFileSync(new URL('riser-verification.json',import.meta.url),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
