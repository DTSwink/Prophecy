import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),S=require('./support.js'),K=require('./capsule.js'),IK=require('./foot-ik.js'),F=require('./flight.js'),C=require('./core.js'),Bank=require('../FootIKLab/test-bank.cjs');
const server=process.env.BODYFLIP_TEST_URL||'http://127.0.0.1:8876';
const checks=[],cases=[],check=(name,ok)=>{assert(ok,name);checks.push(name);};
for(const gait of ['walk','run'])for(const approach of ['toward','parallel']){
 const run=Bank.load(gait,.21),{names,parents}=run,speed=R.length(R.sub(run.poses.at(-1).points[0],run.poses[0].points[0]))/run.duration,k=Math.SQRT1_2;
 const surface=approach==='toward'?S.rectangle('incline',[0,0,0],[1,0,0],[0,k,k],[-10,10,-10,30],.2):S.rectangle('incline',[0,0,0],[k,k,0],[0,0,1],[-10,10,-10,30],.2),surfaces=[surface];
 const motion=t=>{const p=F.at(run,t,parents),origin=run.poses[0].points[0];return {...p,points:p.points.map(v=>R.sub(v,origin))};},source=t=>{const pose=motion(t);return {pose,root:pose.points[0],phase:gait==='walk'?'WALK':'RUN',speed,vy:0,airTime:0};};
 const options={surfaces,speed,gait:motion,fallPose:()=>motion(0),phase:gait==='walk'?'WALK':'RUN'};
 const plain=K.track(source,options),start=performance.now(),adapted=K.track(source,{...options,decorate:(src,opts)=>IK.track(src,{...opts,names,parents,gait})});
 adapted.prepare(2.8);const milliseconds=performance.now()-start;
 let contacts=0,active=0,minGap=Infinity,maxChange=0,maxBoneError=0,maxKneeStep=0,last=null;
 for(let frame=0;frame<=336;frame++){
  const t=frame/120,a=adapted.sample(t),b=plain.sample(t);if(a.footIK){active++;contacts+=a.footIK.feet.filter(f=>f.contact).length;}
  check(`${gait}/${approach}/${frame}: finite`,a.pose.points.flat().every(Number.isFinite));
  assert(R.length(R.sub(a.root,b.root))<1e-10,'Shared feet cannot change capsule trajectory');
  for(let i=2;i<names.length;i++)maxBoneError=Math.max(maxBoneError,Math.abs(R.length(R.sub(a.pose.points[i],a.pose.points[parents[i]]))-R.length(R.sub(b.pose.points[i],b.pose.points[parents[i]]))));
  for(const side of ['L','R']){
   const l=S.leg(a.pose,names,side),gap=Math.min(...S.footPoints(a.pose,l.foot,l.toe,side).map(v=>surface.local(R.add(a.pose.points[l.foot],v))[1]));
   minGap=Math.min(minGap,gap);maxChange=Math.max(maxChange,R.length(R.sub(a.pose.points[l.foot],b.pose.points[l.foot])));
   if(last)maxKneeStep=Math.max(maxKneeStep,R.length(R.qlog(R.qm(a.pose.q[l.knee],R.qinv(last.pose.q[l.knee]))))*180/Math.PI);
  }
  last=a;
 }
 check(`${gait}/${approach}: shared IK active and changes feet`,active>200&&maxChange>.01);
 check(`${gait}/${approach}: lengths retained`,maxBoneError<1e-8);
 check(`${gait}/${approach}: actual contacts and shoe clearance`,contacts>0&&minGap>-.0001);
 check(`${gait}/${approach}: no knee pop`,maxKneeStep<15);
 const sample=JSON.stringify(adapted.sample(1.123));adapted.sample(.2);adapted.sample(2.4);check(`${gait}/${approach}: seek deterministic`,JSON.stringify(adapted.sample(1.123))===sample);
 cases.push({gait,approach,milliseconds,active,contacts,minGap,maxChange,maxBoneError,maxKneeStep});
}
// Real authored jumps and seeded NN return use the same corrected incoming pose.
const jumps=['data/jumps.json','data/jumps-standing.json'].flatMap(n=>JSON.parse(fs.readFileSync(new URL(n,import.meta.url))).clips).map(F.decodeJump);
const run=Bank.load('walk',.21),{names,parents}=run,k=Math.SQRT1_2;
const ramp=S.rectangle('floor',[0,0,0],[k,k,0],[0,0,1],[-10,10,-4,100],.2);
const settings=C.sanitize({mode:'walk',platforms:[S.platformRecord(ramp)],jumpEvents:[{id:'a',time:.9,surface:'auto'}]});
const requests=[];
const sequence=await F.prepare(run,jumps,settings,parents,undefined,async request=>{requests.push(request);const response=await fetch(server+'/resume',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(request)});const data=await response.json();assert(response.ok,data.error);return data;});
check('Inclined locomotion uses shared IK before support',!!sequence.sample(.5).footIK);
check('Jump on incline pushes and lands',sequence.events[0].status==='Push'&&sequence.landings.length>0&&requests.length>0);
const gap=(a,b)=>Math.max(...a.points.map((p,i)=>R.length(R.sub(p,b.points[i]))));
const supportGap=gap(sequence.sample(.9).pose,sequence.sample(.9-1e-7).pose);
check('Support starts from corrected pose without a snap',supportGap<1e-4);
const landing=sequence.landings[0].time,landingGap=gap(sequence.sample(landing).pose,sequence.sample(landing-1e-7).pose);
check('Landing still seeds the NN seamlessly',landingGap<1e-4);
check('Shared IK resumes after inclined landing',!!sequence.sample(landing+.25).footIK);
for(let i=0;i<=180;i++){const frame=sequence.sample(.9+i/120);if(['SUPPORT','PUSH','RISE','FALL'].includes(frame.phase))check('Authored jump owns feet at '+i,!frame.footIK);}
const before=JSON.stringify(sequence.sample(landing+.25));sequence.sample(.3);sequence.sample(landing+.6);check('Jump and landing reverse seeking deterministic',JSON.stringify(sequence.sample(landing+.25))===before);
cases.push({inclinedJump:true,supportGap,landingGap,landing,nnRequests:requests.length});
// A joined course exercises entering/leaving the slope and leaving the edge.
const surfaces=[S.rectangle('entry',[0,0,0],[1,0,0],[0,0,1],[-4,4,-4,0],.2),S.rectangle('ramp',[0,0,0],[1,0,0],[0,k,k],[-4,4,0,2/k],.2),S.rectangle('exit',[0,2,2],[1,0,0],[0,0,1],[-4,4,0,2],.2)];
const origin=run.poses[0].points[0],motion=t=>{const p=F.at(run,t,parents);return {...p,points:p.points.map(v=>R.add(R.sub(v,origin),[0,0,-1]))};},speed=2;
const source=t=>{const pose=motion(t);return {pose,root:pose.points[0],phase:'WALK',speed,vy:0};};
const carrier=K.track(source,{surfaces,speed,gait:motion,fallPose:(_from,_elapsed,current)=>current,phase:'WALK',decorate:(src,opts)=>IK.track(src,{...opts,names,parents,gait:'walk'})});
carrier.prepare(3.5);let maxStep=0,maxAt=null,previous=null,hadIncline=false,hadFlat=false,hadFall=false;
for(let i=0;i<=420;i++){
 const frame=carrier.sample(i/120);hadIncline||=!!frame.footIK;hadFlat||=i>240&&frame.phase==='WALK'&&!frame.footIK;hadFall||=frame.phase==='FALL';
 if(previous){const d=gap(frame.pose,previous.pose);if(d>maxStep){maxStep=d;maxAt={frame:i,phase:frame.phase,prior:previous.phase,footIK:frame.footIK?.surfaceId,priorIK:previous.footIK?.surfaceId,joint:names[frame.pose.points.map((p,j)=>R.length(R.sub(p,previous.pose.points[j]))).indexOf(d)],root:frame.root,feet:frame.footIK?.feet};}}previous=frame;
}
check('Joined course enters incline, recovers flat NN, then falls',hadIncline&&hadFlat&&hadFall);
check('Incline transitions avoid position pops',maxStep<.16);
const fixed=JSON.stringify(carrier.sample(2.49));carrier.sample(.4);carrier.sample(3.4);check('Edge transition is seek deterministic',JSON.stringify(carrier.sample(2.49))===fixed);
cases.push({joinedCourse:true,maxStep,maxAt});
fs.writeFileSync(new URL('foot-ik-verification.json',import.meta.url),JSON.stringify({passed:checks.length,cases},null,2)+'\n');
console.log(JSON.stringify({passed:checks.length,cases},null,2));
