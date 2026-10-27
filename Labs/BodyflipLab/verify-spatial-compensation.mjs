import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),A=require('./jump-attack.js'),H=require('./attack-inertia.js'),I=require('./idle.js');
const json=p=>JSON.parse(fs.readFileSync(new URL(p,import.meta.url),'utf8'));
const buf=p=>{const b=fs.readFileSync(new URL(p,import.meta.url));return b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength);};
const m=json('data/manifest.json'),ref=C.poseFromShared(m),rig=H.model(m.names,m.parents,ref),p=m.names.indexOf('pelvis'),s=m.names.indexOf('spine_01'),dt=1/60;
const error=(a,b)=>R.length(R.qlog(R.qm(a,R.qinv(b))));
let maxAngleError=0,maxPlannerTargetError=0;
const cases=[];
// Equal meaning on every axis and on a combined 3D rotation: 50% of 60 degrees
// targets 30 degrees opposite; 100% targets 60 degrees opposite.
const vectors=[...Array.from({length:3},(_,axis)=>[-1,1].map(sign=>[0,1,2].map(j=>j===axis?sign*Math.PI/3:0))).flat(),[.4,-.7,.3]];
for(const vector of vectors)for(const amount of [0,.5,1]){
 const base=()=>ref,rotation=t=>R.mul(vector,t>0&&t<1?Math.sin(Math.PI*t)**2:0);
 const source=t=>{const local=R.localize(ref.points,ref.q,m.parents);local.q[s]=R.qm(R.qexp(rotation(t)),local.q[s]);return R.fk(local,m.parents);};
 let targetCalls=0;
 const target=(t,raw,baseline)=>{
  targetCalls++;const pose=A.compensate(raw,baseline,m.names,m.parents,amount),actual=R.qm(R.qinv(baseline.q[p]),pose.q[p]),expected=R.qexp(R.mul(rotation(t),-amount));
  maxAngleError=Math.max(maxAngleError,error(actual,expected));
  return pose;
 };
 const options={source,base,target,start:0,end:1,names:m.names,parents:m.parents,reference:ref,amount},track=H.create(options);
 let previousTarget=H.bodies(target(0,source(0),ref),rig),previousPlan=H.bodies(track.samplePlanned(0),rig);
 for(let tick=1;tick<=60;tick++){
  const t=tick*dt,goal=H.bodies(target(t,source(t),ref),rig),plan=H.bodies(track.samplePlanned(t),rig);
  maxPlannerTargetError=Math.max(maxPlannerTargetError,R.length(R.sub(H.momentum(previousTarget,goal,rig,dt),H.momentum(previousPlan,plan,rig,dt))));
  previousTarget=goal;previousPlan=plan;
 }
 assert.equal(track.diagnostics.targetMode,'opposite-angle');assert(targetCalls>60,'Planner must sample the supplied angle target');
 // Changing metadata cannot silently turn Amount into a momentum percentage.
 const sameTarget=H.create({...options,amount:1-amount});
 for(const t of [.2,.5,.8,1.2]){
  const a=track.sample(t),b=sameTarget.sample(t);
  for(let i=0;i<m.names.length;i++)assert(error(a.q[i],b.q[i])<1e-10);
 }
 const saved=JSON.stringify(track.sample(.42));track.sample(10);track.sample(.12);assert.equal(JSON.stringify(track.sample(.42)),saved);
 cases.push({vector,amount,plannerResidual:track.diagnostics.maxPlannedResidual});
}
assert(maxAngleError<1e-9);assert(maxPlannerTargetError<.005);
const idle=I.create(json('data/idle.json'),buf('data/idle.bin'),m).motion(),base=t=>idle.sample(t),segment={sample:t=>({pose:base(t)}),airStart:.35,jumpStart:.35,abortTime:Infinity};
const attacks=[];
for(const name of ['slashL','headbutt']){
 const meta=json('data/vanilla.json').clips.find(c=>c.name===name),clip=C.decode(meta,buf(meta.file),m.names,m.parents),settings={...C.defaults,pelvisAttackCompensation:.95};
 const track=A.create({attack:name},segment,new Map([[name,clip]]),m.names,m.parents,settings,ref);
 const alias=name==='headbutt'?'slashL':'headbutt',renamed={...clip,meta:{...meta,name:alias}};
 const other=A.create({attack:alias},segment,new Map([[alias,renamed]]),m.names,m.parents,settings,ref);
 let peakYaw=0,peakAngle=0;
 for(let t=.35;t<2.4;t+=1/120){
  const a=track.sample(t).pose,b=other.sample(t).pose,q=R.qm(R.qinv(base(t).q[p]),a.q[p]),forward=R.rotate(q,[0,-1,0]);
  peakYaw=Math.max(peakYaw,Math.abs(Math.atan2(-forward[2],-forward[1]))*180/Math.PI);peakAngle=Math.max(peakAngle,R.length(R.qlog(q))*180/Math.PI);
  for(let i=0;i<m.names.length;i++)assert(error(a.q[i],b.q[i])<1e-10,'Clip name cannot select different compensation rules');
 }
 if(name==='slashL')assert(peakYaw<60,'Prevent the 125-degree momentum-percentage regression at95%');
 attacks.push({name,amount:.95,peakYaw,peakAngle});
}
const result={cases:cases.length,maxAngleError,maxPlannerTargetError,attacks,note:'Amount scales opposite spine rotation, not cancelled momentum. Soft-leg distribution and damping modify the displayed pelvis angle.'};
fs.writeFileSync(new URL('spatial-compensation-verification.json',import.meta.url),JSON.stringify(result,null,2));console.log(result);
