import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),A=require('./jump-attack.js'),I=require('./idle.js'),H=require('./attack-inertia.js'),V=require('./viewer-leg-response.js');
const read=p=>JSON.parse(fs.readFileSync(new URL(p,import.meta.url),'utf8')),buf=p=>{const b=fs.readFileSync(new URL(p,import.meta.url));return b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength);};
const m=read('data/manifest.json'),meta=read('data/vanilla.json').clips.find(c=>c.name==='slashL'),clip=C.decode(meta,buf(meta.file),m.names,m.parents),ref=C.poseFromShared(m),idle=I.create(read('data/idle.json'),buf('data/idle.bin'),m).motion(),base=t=>({pose:idle.sample(t)}),upper=A.bones(m.names,m.parents),hinges=H.legHinges(m.names,ref),results=[];
const qerror=(a,b)=>R.length(R.qlog(R.qm(a,R.qinv(b))));
let maxUpperError=0,maxSocketError=0,maxKneeOffHinge=0,minKnee=Infinity,maxKnee=0,maxStateRateError=0;
for(const amount of [0,.5,1]){
 const before=A.create({attack:'slashL'},{sample:base,airStart:.35,jumpStart:.35,abortTime:Infinity},new Map([['slashL',clip]]),m.names,m.parents,{...C.defaults,pelvisAttackCompensation:amount},ref),stop=before.end+.25+1;
 const response=amount?V.create({source:t=>before.inertia.samplePlanned(t),base:t=>base(t).pose,start:before.start,stop,names:m.names,parents:m.parents,reference:ref}):null;
 const traces=[[],[]],started=performance.now();
 for(let frame=0;frame<Math.ceil(stop*120);frame++){
  const t=frame/120,a=before.sample(t).pose,b=response?response.sample(t):a,la=R.localize(a.points,a.q,m.parents),lb=R.localize(b.points,b.q,m.parents),basePose=base(t).pose,baseLocal=R.localize(basePose.points,basePose.q,m.parents);
  for(const j of upper)maxUpperError=Math.max(maxUpperError,qerror(a.q[j],b.q[j]));
  for(let j=0;j<m.names.length;j++)maxSocketError=Math.max(maxSocketError,R.length(R.sub(la.p[j],lb.p[j])));
  for(const h of hinges){
   const delta=R.qlog(R.qm(R.qinv(baseLocal.q[h.knee]),lb.q[h.knee]));maxKneeOffHinge=Math.max(maxKneeOffHinge,R.length(R.cross(delta,h.kneeAxis)));
   const v=R.unit(R.sub(b.points[h.knee],b.points[h.hip])),w=R.unit(R.sub(b.points[h.foot],b.points[h.knee])),angle=Math.atan2(R.dot(R.cross(v,w),R.rotate(b.q[h.knee],h.kneeAxis)),R.dot(v,w));minKnee=Math.min(minKnee,angle);maxKnee=Math.max(maxKnee,angle);
  }
  for(let k=0;k<2;k++)traces[k].push({t,directions:hinges.map(h=>R.unit(R.rotate(R.qinv([a,b][k].q[0]),R.sub([a,b][k].points[h.foot],[a,b][k].points[h.hip]))))});
  assert(b.points.flat().every(Number.isFinite));
 }
 function metrics(rows,side){let previous=null,maxSpeed=0,maxAcceleration=0;const origin=rows[0].directions[side];let excursion=0;
  for(let i=1;i<rows.length;i++){const omega=R.mul(R.qlog(R.fromTo(rows[i-1].directions[side],rows[i].directions[side])),120);maxSpeed=Math.max(maxSpeed,R.length(omega));if(previous)maxAcceleration=Math.max(maxAcceleration,R.length(R.sub(omega,previous))*120);previous=omega;excursion=Math.max(excursion,Math.acos(Math.max(-1,Math.min(1,R.dot(origin,rows[i].directions[side])))));}
  return {maxSpeed,maxAcceleration,excursion};
 }
 const legs=hinges.map((_,k)=>({side:k?'right':'left',before:metrics(traces[0],k),after:metrics(traces[1],k)}));
 if(response){
  const snapshot=JSON.stringify(response.sample(.86));response.sample(stop+3);response.sample(.4);assert.equal(JSON.stringify(response.sample(.86)),snapshot);
  for(let i=1;i<response.states.length-1;i++){const t=response.start+i/120,e=1e-6,a=response.stateAt(t-e),b=response.stateAt(t),c=response.stateAt(t+e);for(let j=0;j<b.x.length;j++)maxStateRateError=Math.max(maxStateRateError,Math.abs((c.x[j]-a.x[j])/(2*e)-b.v[j]));}
  const count=response.states.length;response.sample(600);assert.equal(response.states.length,count);
  for(const leg of legs){assert(leg.after.maxAcceleration<leg.before.maxAcceleration*.6,'Smooth the actual hip-to-foot vector, not just a controller scalar');assert(leg.after.excursion>leg.before.excursion*.7,'Retain most of the leg swing');}
 }
 results.push({amount,legs,elapsedMs:performance.now()-started});
}
assert(maxUpperError<1e-9);assert(maxSocketError<1e-9);assert(maxKneeOffHinge<1e-9);assert(minKnee>0&&maxKnee<150*Math.PI/180);assert(maxStateRateError<1e-5);
const result={maxUpperError,maxSocketError,maxKneeOffHinge,minKnee,maxKnee,maxStateRateError,results};fs.writeFileSync(new URL('viewer-leg-response-verification.json',import.meta.url),JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));
