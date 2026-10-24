import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),F=require('./flight.js'),C=require('./core.js'),R=require('./recovery.js');
const read=n=>JSON.parse(fs.readFileSync(new URL(n,import.meta.url),'utf8'));
const m=read('data/manifest.json'),jumps=read('data/jumps.json').clips.map(F.decodeJump),ref=C.poseFromShared(m),checks=[],measurements=[];
const check=(name,ok)=>{assert(ok,name);checks.push(name);},dist=(a,b)=>R.length(R.sub(a,b)),angle=(a,b)=>R.length(R.qlog(R.qm(a,R.qinv(b))));
for(const gait of ['run','walk'])for(const drawn of [false,true])for(const foot of ['L','R'])for(const blend of [0,.08,.2,1]){
 const run=F.decodeNN(read('data/'+gait+'-default'+(drawn?'-drawn':'')+'.json'));
 const f=F.create(run,jumps,{...C.defaults,matchLeg:false,mode:gait==='walk'?'walk':'jump',jumpFoot:foot,jumpBlend:blend,supportAlpha:.03},m.parents,ref),tag=[gait,drawn,foot,blend].join('/');
 check(tag+' takeoff possible',Number.isFinite(f.jumpStart));
 const launch=f.sample(f.jumpStart).pose,offset=R.sub(launch.points[1],launch.points[0]),l=f.support.leg;
 let pelvisError=0,orientationError=0,hipDrop=0,drift=0,reach=0;
 for(let i=0;i<=120;i++){
  const t=f.apex*i/120,p=f.sample(f.jumpStart+t).pose;
  pelvisError=Math.max(pelvisError,dist(R.sub(p.points[1],p.points[0]),offset));orientationError=Math.max(orientationError,angle(p.q[1],launch.q[1]));
  if(t<=f.release){hipDrop=Math.max(hipDrop,launch.points[l.hip][1]-p.points[l.hip][1]);drift=Math.max(drift,dist(p.points[l.foot],f.support.terminal.foot));reach=Math.max(reach,dist(p.points[l.hip],p.points[l.foot]));}
 }
 check(tag+' pelvis follows root without animation dip',pelvisError<1e-8&&orientationError<1e-8&&hipDrop<1e-8);
 check(tag+' support remains planted within reach',drift<2e-5&&reach<=f.support.maxReach+2e-5);
 const a=f.sample(f.airStart-1e-7).pose,b=f.sample(f.airStart+1e-7).pose;
 // Zero blend explicitly requests an immediate leg handoff; positive blends must be continuous.
 if(blend>0)check(tag+' release has no snap',Math.max(...a.points.map((v,i)=>dist(v,b.points[i])))<1e-4);
 const after=Math.max(blend,f.release+blend)+.01,p=f.sample(f.jumpStart+after).pose,source=F.at(F.trimStart(jumps[foot==='L'?0:1]),after,m.parents),local=R.localize(p.points,p.q,m.parents),expected=R.localize(source.points,source.q,m.parents);
 check(tag+' remaining joints reach animation locally',m.names.every((_,i)=>i<2||angle(local.q[i],expected.q[i])<1e-6));
 const end=f.sample(20).pose;check(tag+' prolonged fall keeps procedural pelvis',dist(R.sub(end.points[1],end.points[0]),offset)<1e-8&&end.points.flat().every(Number.isFinite));
 measurements.push({gait,drawn,foot,blend,pin:f.release,pelvisError,hipDrop,drift});
}
fs.writeFileSync(new URL('pelvis-verification.json',import.meta.url),JSON.stringify({passed:true,checks,measurements},null,2));
console.log(JSON.stringify({passed:true,checks:checks.length,maxHipDrop:Math.max(...measurements.map(m=>m.hipDrop)),pins:measurements.filter(m=>m.drawn&&m.blend===.08)}));
