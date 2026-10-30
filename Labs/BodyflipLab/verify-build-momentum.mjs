// Buildup must author pose without braking the root or freezing source animation.
import fs from 'node:fs';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),S=require('./support.js'),B=require('./bounce.js'),F=require('./flight.js');
const read=n=>JSON.parse(fs.readFileSync(new URL(n,import.meta.url))),manifest=read('data/manifest.json'),{names,parents}=manifest,reference=C.poseFromShared(manifest),jumps=['data/jumps.json','data/jumps-standing.json'].flatMap(n=>read(n).clips).map(F.decodeJump);
const distance=(a,b)=>R.length(R.sub(a,b)),angle=(a,b)=>R.length(R.qlog(R.qm(a,R.qinv(b)))),ease=x=>{const u=Math.max(0,Math.min(1,x));return u*u*u*(10+u*(-15+6*u));},checks=[];
const check=(label,value)=>{assert(value,label);checks.push(label);};
const shared={normal:[0,1,0],direction:[0,1,0],foot:[0,0,0],loadMs:100,buildMs:300,rebound:.5,launchSpeed:4,cap:20,rolling:()=>({foot:[0,0,0],valid:true}),carry:F.carryVelocity};
const free=B.create({...shared,root:[0,1.5,0],hip:[0,1.5,0],incoming:[2,1,0],reach:2,maxReach:1.98,anchorOffset:t=>[0,-.15*ease(t/.3),0]});
check('Airborne fixture completes requested buildup',Math.abs(free.loadDuration-.3)<1e-10);
for(const f of free.frames){check('Airborne velocity is incoming plus gravity at '+f.t,distance(f.v,[2,1-9.81*f.t,0])<1e-10);check('Airborne position stays ballistic at '+f.t,distance(f.p,[2*f.t,1.5+f.t-4.905*f.t*f.t,0])<1e-10);}
const floor=(p,d)=>{const q=R.add(p,d);return {root:[q[0],Math.max(0,q[1]),q[2]],contacts:q[1]<0?[{normal:[0,1,0]}]:[]};};
const grounded=B.create({...shared,root:[0,0,0],hip:[0,.7,0],incoming:[0,0,2],reach:1.2,maxReach:1.188,anchorOffset:t=>[0,.7-.1*ease(t/.3),0],resolveRoot:floor});
check('Grounded fixture completes requested buildup',Math.abs(grounded.loadDuration-.3)<1e-10);
check('Pelvis crouch does not brake or reverse the grounded root',grounded.frames.every(f=>distance(f.v,[0,0,2])<1e-10&&distance(f.p,[0,0,2*f.t])<1e-10));
const run=F.decodeNN(read('data/walk-default.json')),loop=jumps.find(j=>j.name.endsWith('_Loop_Fall')),surface=S.rectangle('floor',[0,0,0],[1,0,0],[0,0,1],[-10,10,-10,20],.4);
const settings=C.sanitize({mode:'walk',motion:'kinematic',ramps:false,surfaceIK:false,supportAlpha:0,loadMs:100,loadYMs:200,loadFullMs:300,buildDepth:.15});
const sourceCases=[{label:'NN walk',pose:t=>F.at(run,t,parents),velocity:[0,0,2]},{label:'jump animation',pose:t=>F.localRoot(F.at(loop,t,parents,true)),velocity:[0,0,0]}],reports=[];
for(const source of sourceCases){
 const context={time:.1,poseAt:source.pose,velocityAt:()=>source.velocity,surface,surfaces:[surface]},segment=F.create(run,jumps,settings,parents,reference,context);
 check(source.label+' reaches support',Number.isFinite(segment.contactTime)&&segment.bounce?.loadDuration>0);
 const l=segment.support.leg,excluded=new Set(['L','R'].flatMap(side=>{const a=S.leg(source.pose(segment.contactTime),names,side);return [a.hip,a.knee,a.foot,a.toe];})),start=segment.contactTime,end=segment.jumpStart;
 let maxRotationError=0,previousDrop=-Infinity,drop=0;
 for(let i=0;i<=16;i++){
  const t=start+(end-start)*i/17,frame=segment.sample(t),local=R.localize(frame.pose.points,frame.pose.q,parents),target=source.pose(t),wanted=R.localize(target.points,target.q,parents);
  for(let j=0;j<names.length;j++)if(!excluded.has(j))maxRotationError=Math.max(maxRotationError,angle(local.q[j],wanted.q[j]));
  const height=R.dot(R.sub(frame.pose.points[names.indexOf('pelvis')],frame.root),surface.normal),sourceHeight=R.dot(R.sub(target.points[names.indexOf('pelvis')],target.points[0]),surface.normal);drop=sourceHeight-height;
  check(source.label+' crouch deepens relative to the continuing source',drop>=previousDrop-1e-9);previousDrop=drop;
 }
 check(source.label+' upper-body source joint motion continues',maxRotationError<1e-7);
 check(source.label+' lowers pelvis relative to root',drop>0);
 check(source.label+' keeps tangent momentum',segment.bounce.frames.every(f=>Math.abs(f.v[2]-source.velocity[2])<1e-9));
 reports.push({source:source.label,load:end-start,drop,maxRotationError});
}
console.log(JSON.stringify({passed:true,checks:checks.length,reports},null,2));
