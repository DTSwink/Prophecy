import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),K=require('./footik.js'),R=require('./recovery.js'),S=require('./support.js'),{load}=require('./test-bank.cjs');
const run=load('walk',.49),model=K.prepare(run,{phase:.49}),checks=[];
const check=(name,ok)=>{assert(ok,name);checks.push(name);};
const angle=(a,b)=>2*Math.acos(Math.min(1,Math.abs(R.dot(a,b))))*180/Math.PI;
const ankleError=(f,side)=>{
 const foot=run.names.indexOf('foot_'+side),calf=run.names.indexOf('calf_'+side);
 return angle(R.qm(R.qinv(f.pose.q[calf]),f.pose.q[foot]),R.qm(R.qinv(f.raw.q[calf]),f.raw.q[foot]));
};
check('Free swing retains NN ankle articulation', [60,65,70].every(n=>ankleError(model.sample(n/60),'l')<.001));
const reported=ankleError(model.sample(79/60),'l');
check('79 improves the ankle bend while preparing contact',reported<41);
let sum=0,count=0,freeSum=0,freeCount=0,maxPivotError=0,maxFootStep=0; const lastContact=[-999,-999];
for(let i=0;i<model.frames.length;i++)for(const [side,s] of ['l','r'].entries()){
 const f=model.frames[i],foot=run.names.indexOf('foot_'+s),contact=f.feet[side].contact;
 if(contact)lastContact[side]=i;
 if(f.feet[side].state==='SWING'){const error=ankleError(f,s);sum+=error;count++;if(i-lastContact[side]>24){freeSum+=error;freeCount++;}}
 if(contact)maxPivotError=Math.max(maxPivotError,R.length(R.sub(R.add(f.pose.points[foot],R.rotate(f.pose.q[foot],contact.localPoint)),contact.point)));
 if(i)maxFootStep=Math.max(maxFootStep,angle(f.pose.q[foot],model.frames[i-1].pose.q[foot]));
}
// Grounded push-off now authors the early swing ankle. Judge NN articulation
// after that 200ms handoff; retain contact and angular-speed checks throughout.
check('Mean ankle error after toe-off handoff stays below 10 degrees',freeSum/freeCount<10);
check('Heel/toe material pins remain fixed',maxPivotError<1e-6);
check('Contact transitions keep existing angular-motion limit',maxFootStep<15);
check('Rotation does not drive shoe corners through terrain',model.metrics.maxPenetration<1e-5);
const pitch=n=>{const f=model.sample(n/60),l=S.leg(f.pose,run.names,'L');return Math.asin(S.footFrame(f.pose,l.foot,l.toe,'L').forward[1])*180/Math.PI;};
const landingPitches=Array.from({length:23},(_,i)=>({frame:77+i/2,pitch:pitch(77+i/2)}));
check('Late swing does not reinstate the NN toe-up peak',Math.max(...landingPitches.map(s=>s.pitch))<=5.01);
check('Landing retains a shallow heel lead before settling flat',Math.abs(pitch(83)-5)<.01&&Math.abs(pitch(88))<1);
check('135-141 approach has no steep toe-up rebound',Math.max(...Array.from({length:13},(_,i)=>pitch(135+i/2)))<10);
const result={passed:true,checks,measured:{landingPitches,frame79AnkleErrorDeg:reported,meanSwingAnkleErrorDeg:sum/count,meanFreeSwingAnkleErrorDeg:freeSum/freeCount,swingSamples:count,maxPivotError,maxFootStepDeg:maxFootStep}};
fs.writeFileSync(new URL('ankle-verification.json',import.meta.url),JSON.stringify(result,null,2));
console.log(JSON.stringify(result));
