import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),C=require('./core.js'),R=require('./recovery.js'),A=require('./jump-attack.js'),G=require('./space-gym.js'),I=require('./idle.js');
const read=p=>JSON.parse(fs.readFileSync(new URL(p,import.meta.url),'utf8')),buf=p=>{const b=fs.readFileSync(new URL(p,import.meta.url));return b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength);};
const m=read('data/manifest.json'),ref=C.poseFromShared(m),idle=I.create(read('data/idle.json'),buf('data/idle.bin'),m).motion(),base=t=>({pose:idle.sample(t)}),results=[];
let maxRateError=0,maxAccelerationJump=0;
for(const name of ['slashL','slashRU']){
 const meta=read('data/vanilla.json').clips.find(c=>c.name===name),clip=C.decode(meta,buf(meta.file),m.names,m.parents),track=A.create({attack:name},G.action({time:.5},base),new Map([[name,clip]]),m.names,m.parents,{...C.defaults,pelvisAttackCompensation:.8},ref),response=track.inertia;
 track.sample(response.stop+1);
 const diagnostics=response.diagnostics,planned=response.plannedStates,states=response.states,ratio=diagnostics.maxAcceleration/diagnostics.maxPlannedAcceleration;
 assert(ratio<.25,'Remove the measured tick-to-tick acceleration spikes');
 const peak=states.reduce((v,s)=>Math.max(v,Math.abs(s.pelvis)),0),plannedPeak=planned.reduce((v,s)=>Math.max(v,Math.abs(s.pelvis)),0);
 assert(peak>plannedPeak*.7,'Retain the visible turn instead of merely shrinking it');
 // The instantaneous momentum target is deliberately relaxed. Measure the
 // displayed path rather than mistaking the planner's tiny residual for parity.
 const H=require('./attack-inertia.js'),pelvis=m.names.indexOf('pelvis');let old=null,actual=null,maxMomentumDifference=0;
 for(let i=0;i<=planned.length-1;i++){
  const t=.5+i/120,shown=track.sample(t).pose,unfiltered=response.samplePlanned(t),a=H.bodies(shown,response.rig),b=H.bodies(unfiltered,response.rig);
  if(actual){const axis=R.rotate(base(t).pose.q[pelvis],[1,0,0]);maxMomentumDifference=Math.max(maxMomentumDifference,Math.abs(R.dot(R.sub(H.momentum(actual,a,response.rig,1/120),H.momentum(old,b,response.rig,1/120)),axis)));}
  actual=a;old=b;
  const eps=1e-6,left=response.stateAt(t-eps),mid=response.stateAt(t),right=response.stateAt(t+eps);
  const angles=s=>[s.pelvis,...s.legs],rates=s=>[s.pelvisRate,...s.rates];
  for(let k=0;k<3;k++){
   const finiteRate=(angles(right)[k]-angles(left)[k])/(2*eps);
   maxRateError=Math.max(maxRateError,Math.abs(finiteRate-rates(mid)[k]));
   const accL=(rates(mid)[k]-rates(left)[k])/eps,accR=(rates(right)[k]-rates(mid)[k])/eps;
   maxAccelerationJump=Math.max(maxAccelerationJump,Math.abs(accR-accL));
  }
 }
 const tailTime=.5+(states.length-1)/120,eps=1e-6,tail=response.stateAt(tailTime),after=response.stateAt(tailTime+eps);
 assert(Math.abs((after.pelvis-tail.pelvis)/eps-tail.pelvisRate)<1e-5,'Cache end keeps its velocity');
 const settled=response.stateAt(tailTime+2),size=states.length;
 assert(Math.abs(settled.pelvisRate)<1e-10);
 assert(Math.abs(settled.pelvis-planned.at(-1).pelvis)<1e-10,'Settle at the planned final turn');
 const first=JSON.stringify(response.stateAt(.923));response.stateAt(600);response.stateAt(.51);assert.equal(JSON.stringify(response.stateAt(.923)),first);assert.equal(states.length,size);
 results.push({name,peakAccelerationBefore:diagnostics.maxPlannedAcceleration,peakAccelerationAfter:diagnostics.maxAcceleration,accelerationReduction:1-ratio,peakTurnRetained:peak/plannedPeak,maxMomentumDifference,cacheSize:size});
}
assert(maxRateError<1e-5,'Actual continuous sampler agrees with the integrated velocity');
assert(maxAccelerationJump<.05,'Acceleration is continuous through tick boundaries');
const report={maxRateError,maxAccelerationJump,results};fs.writeFileSync(new URL('inertial-response-verification.json',import.meta.url),JSON.stringify(report,null,2));console.log(report);
