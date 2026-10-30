'use strict';
// Offline Bodyflip integration: no service calls, inference, physics worker,
// editor, browser, or user-state writes. Slide helpers must remain host-only.
const assert=require('node:assert/strict'),Module=require('node:module');
const originalLoad=Module._load;let checks=0;
const check=(value,message)=>{assert.ok(value,message);checks++;};
Module._load=function(request,...args){if(/(?:^|[/\\])slide-(?:entry|joints|arms)\.js$/.test(request))throw Error('Bodyflip shared IK loaded host-only '+request);return originalLoad.call(this,request,...args);};
try{
 const Surface=require('./surface.js'),R=require('../BodyflipLab/recovery.js'),S=require('../BodyflipLab/support.js'),Capsule=require('../BodyflipLab/capsule.js'),IK=require('../BodyflipLab/foot-ik.js'),Flight=require('../BodyflipLab/flight.js'),Bank=require('./test-bank.cjs');
 check(Surface.apiVersion===1,'Shared API version unchanged');
 for(const key of ['createFeet','gaitIntent','bodyRotation','settings','stableLeg'])check(typeof Surface[key]==='function','Shared '+key+' remains available');
 const cases=[];
 for(const gait of ['walk','run'])for(const approach of ['toward','parallel']){
  const run=Bank.load(gait,.21),{names,parents}=run,speed=R.length(R.sub(run.poses.at(-1).points[0],run.poses[0].points[0]))/run.duration,k=Math.SQRT1_2;
  const surface=approach==='toward'?S.rectangle('incline',[0,0,0],[1,0,0],[0,k,k],[-10,10,-10,30],.2):S.rectangle('incline',[0,0,0],[k,k,0],[0,0,1],[-10,10,-10,30],.2),surfaces=[surface];
  const motion=t=>{const p=Flight.at(run,t,parents),origin=run.poses[0].points[0];return {...p,points:p.points.map(v=>R.sub(v,origin))};},source=t=>{const pose=motion(t);return {pose,root:pose.points[0],phase:gait==='walk'?'WALK':'RUN',speed,vy:0,airTime:0};};
  const options={surfaces,speed,gait:motion,fallPose:()=>motion(0),phase:gait==='walk'?'WALK':'RUN'},plain=Capsule.track(source,options),adapted=Capsule.track(source,{...options,decorate:(src,opts)=>IK.track(src,{...opts,names,parents,gait})});
  adapted.prepare(2.8);let active=0,contacts=0,boneError=0,minGap=Infinity,kneeStep=0,last=null;
  for(let i=0;i<=336;i++){
   const a=adapted.sample(i/120),b=plain.sample(i/120);if(a.footIK){active++;contacts+=a.footIK.feet.filter(f=>f.contact).length;}
   check(a.pose.points.flat().every(Number.isFinite),'Finite adapted pose');check(R.length(R.sub(a.root,b.root))<1e-10,'Shared feet retain capsule root');
   for(let j=2;j<names.length;j++)boneError=Math.max(boneError,Math.abs(R.length(R.sub(a.pose.points[j],a.pose.points[parents[j]]))-R.length(R.sub(b.pose.points[j],b.pose.points[parents[j]]))));
   for(const side of ['L','R']){const l=S.leg(a.pose,names,side);minGap=Math.min(minGap,...S.footPoints(a.pose,l.foot,l.toe,side).map(v=>surface.local(R.add(a.pose.points[l.foot],v))[1]));if(last)kneeStep=Math.max(kneeStep,R.length(R.qlog(R.qm(a.pose.q[l.knee],R.qinv(last.pose.q[l.knee]))))*180/Math.PI);}
   last=a;
  }
  check(active>200&&contacts>0,'Shared terrain IK and contacts active');check(boneError<1e-8,'Bone lengths retained');check(minGap>-.0001,'Shoes clear surface');check(kneeStep<15,'Bounded knee motion');
  const exact=JSON.stringify(adapted.sample(1.123));adapted.sample(.2);adapted.sample(2.4);check(JSON.stringify(adapted.sample(1.123))===exact,'Reverse seeking deterministic');cases.push({gait,approach,active,contacts,boneError,minGap,kneeStep});
 }
 console.log(JSON.stringify({passed:true,checks,hostHelpersLoaded:false,cases}));
}finally{Module._load=originalLoad;}
