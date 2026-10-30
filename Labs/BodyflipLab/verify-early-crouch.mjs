// Early crouch: saved running setup, source continuity and trimmed preparation.
import fs from 'node:fs';import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),base=process.cwd()+'/Labs/BodyflipLab/',R=require(base+'recovery.js'),C=require(base+'core.js');


const F=require(base+'flight.js'),read=f=>JSON.parse(fs.readFileSync(f,'utf8').replace(/^\uFEFF/,'')),state={settings:read(base+'fixtures/airborne-foot-rejump.json')},settings=C.sanitize({...state.settings,instantSpin:true,spinLag:.6}),manifest=read(base+'data/manifest.json'),{names,parents}=manifest,reference=C.poseFromShared(manifest),jumps=['jumps.json','jumps-standing.json'].flatMap(f=>read(base+'data/'+f).clips).map(F.decodeJump);
const gait=settings.mode==='jump'?'run':'walk',drawn=settings.attack==='pike'||settings.attack.startsWith('slash'),stem=gait+(drawn?'-drawn':'')+'-phases',meta=read(base+'data/'+stem+'.json'),width=3+meta.names.length*12,countFrames=Math.ceil(5*meta.fps)+2,phase=Math.round((settings.runPhase%1)*meta.stride),bytes=Buffer.alloc(countFrames*width*4),fd=fs.openSync(base+'data/'+stem+'.bin','r');
try{if(fs.readSync(fd,bytes,0,bytes.length,phase*meta.framesPerPhase*width*4)!==bytes.length)throw Error('Incomplete cached phase');}finally{fs.closeSync(fd);}
const roots=[],poses=[];for(let f=0;f<countFrames;f++){const row=Array.from({length:width},(_,i)=>bytes.readFloatLE((f*width+i)*4));roots.push(row.slice(0,3));poses.push({points:meta.names.map((_,i)=>row.slice(3+i*12,6+i*12)),axes:meta.names.map((_,i)=>[0,1,2].map(k=>row.slice(6+i*12+k*3,9+i*12+k*3)))});}
const run=F.decodeNN({...meta,duration:5,roots,poses});

const S=require(base+'support.js'),T=require(base+'target-rig.js').create(names,parents,reference),pelvis=names.indexOf('pelvis');
const distance=(a,b)=>R.length(R.sub(a,b)),angle=(a,b)=>R.length(R.qlog(R.qm(a,R.qinv(b))));
const sequence=F.sequence(run,jumps,settings,parents,reference,null,null,{horizon:2.2});
const baseline=F.sequence(run,jumps,{...settings,jumpEvents:[]},parents,reference,null,null,{horizon:1.1});
const segment=sequence.segments[0],checks=[];
function check(ok,label){assert(ok,label);checks.push(label);}
check(sequence.events.every(e=>e.status==='Push'),'Both saved jumps still push');
check(Math.abs(segment.preparationStart-(segment.supportStart-.2))<1e-9,'Full jump starts extra preparation 200 ms early');
check(segment.preparationDepth(segment.contactTime)>.09,'Pelvis is already lowered before immediate foot contact');
check(segment.preparationDepth(segment.jumpStart)>.11,'Crouch reaches over 11 cm before pushing');
let upperError=0,footError=0,rootError=0;
for(let i=0;i<=56;i++){
 const t=i/60,p=sequence.sample(t).pose,original=baseline.sample(t).pose;
 if(t<segment.preparationStart)check(Math.max(...p.points.map((v,j)=>distance(v,original.points[j])))<1e-8,'Earlier gait unchanged '+i);
 if(t<segment.supportStart){
  for(const side of ['L','R']){const leg=S.leg(original,names,side);footError=Math.max(footError,distance(p.points[leg.foot],original.points[leg.foot]));}
 }
 if(t>=segment.preparationStart){
  const authored=segment.authoredSample(t).pose,a=R.localize(authored.points,authored.q,parents),b=R.localize(original.points,original.q,parents);
  for(let j=0;j<names.length;j++)if(!/^(thigh|calf|foot|ball)_/.test(names[j]))upperError=Math.max(upperError,angle(a.q[j],b.q[j]));
  rootError=Math.max(rootError,distance(p.points[0],original.points[0]));
 }
}
check(upperError<1e-7,'Upper-body animation continues through preparation');
check(footError<1e-7,'Gait feet retain their original world trajectories before support');
check(rootError<1e-7,'Crouching does not change forward root motion');
check(segment.bounce.frames.every(f=>Math.abs(f.v[2]-sequence.speed)<1e-7),'Loading keeps incoming forward speed');
const t=segment.contactTime,display=T.project(sequence.sample(t).pose,sequence.surfaces),original=T.project(baseline.sample(t).pose,baseline.surfaces),visibleDrop=original.points[pelvis][1]-display.points[pelvis][1];
check(visibleDrop>.09,'Displayed constrained pelvis retains the crouch');
for(const boundary of [segment.preparationStart,segment.jumpStart,segment.airStart]){
 const a=sequence.sample(boundary-1e-7).pose,b=sequence.sample(boundary+1e-7).pose;
 check(Math.max(...a.points.map((v,j)=>distance(v,b.points[j])))<1e-3,'No snap at '+boundary);
}
// Preparing only the anticipatory portion must produce the same earlier frames
// after the trim is extended past the marker and push.
const partial=F.sequence(run,jumps,settings,parents,reference,null,null,{horizon:.85,defer:true});partial.prepareThrough(.85);
const prefix=JSON.stringify(partial.sample(.8));partial.prepareThrough(1.1);
check(JSON.stringify(partial.sample(.8))===prefix,'Extending trim retains the prepared crouch');
check(distance(partial.sample(.8).pose.points[pelvis],sequence.sample(.8).pose.points[pelvis])<1e-8,'Trimmed and whole crouch agree');
for(const [percent,depth,lead] of [[25,.15,0],[50,.15,.1],[100,.15,.2],[100,0,0]]){
 const input={...settings,buildDepth:depth,jumpEvents:[{...settings.jumpEvents[0],jumpPercent:percent}]};
 const q=F.sequence(run,jumps,input,parents,reference,null,null,{horizon:1.1}),s=q.segments[0];
 check(Math.abs(s.supportStart-s.preparationStart-lead)<1e-8,'Tier lead '+percent+' depth '+depth);
 check(q.sample(.95).pose.points.flat().every(Number.isFinite),'Finite tier '+percent);
}
console.log(JSON.stringify({passed:true,checks:checks.length,visibleDropCm:visibleDrop*100,depthAtPushCm:segment.preparationDepth(segment.jumpStart)*100,upperError,footError,rootError,events:sequence.events.map(e=>({status:e.status,push:e.pushTime}))},null,2));

