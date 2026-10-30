import fs from 'node:fs';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),base=process.cwd()+'/Labs/BodyflipLab/',R=require(base+'recovery.js'),C=require(base+'core.js');


const F=require(base+'flight.js'),read=f=>JSON.parse(fs.readFileSync(f,'utf8').replace(/^\uFEFF/,'')),state={settings:read(base+'fixtures/leg-contact-continuity.json')},settings=C.sanitize({...state.settings}),manifest=read(base+'data/manifest.json'),{names,parents}=manifest,reference=C.poseFromShared(manifest),jumps=['jumps.json','jumps-standing.json'].flatMap(f=>read(base+'data/'+f).clips).map(F.decodeJump);
const gait=settings.mode==='jump'?'run':'walk',drawn=settings.attack==='pike'||settings.attack.startsWith('slash'),stem=gait+(drawn?'-drawn':'')+'-phases',meta=read(base+'data/'+stem+'.json'),width=3+meta.names.length*12,countFrames=Math.ceil(5*meta.fps)+2,phase=Math.round((settings.runPhase%1)*meta.stride),bytes=Buffer.alloc(countFrames*width*4),fd=fs.openSync(base+'data/'+stem+'.bin','r');
try{if(fs.readSync(fd,bytes,0,bytes.length,phase*meta.framesPerPhase*width*4)!==bytes.length)throw Error('Incomplete cached phase');}finally{fs.closeSync(fd);}
const roots=[],poses=[];for(let f=0;f<countFrames;f++){const row=Array.from({length:width},(_,i)=>bytes.readFloatLE((f*width+i)*4));roots.push(row.slice(0,3));poses.push({points:meta.names.map((_,i)=>row.slice(3+i*12,6+i*12)),axes:meta.names.map((_,i)=>[0,1,2].map(k=>row.slice(6+i*12+k*3,9+i*12+k*3)))});}



import assert from 'node:assert/strict';
const run=F.decodeNN({...meta,duration:5,roots,poses}),S=require(base+'support.js'),T=require(base+'target-rig.js').create(names,parents,reference),M=require(base+'mass.js'),mass=M.model(names,parents,reference),checks=[];
const check=(ok,label)=>{assert(ok,label);checks.push(label);},dist=(a,b)=>R.length(R.sub(a,b)),angle=(a,b)=>Math.acos(Math.max(-1,Math.min(1,R.dot(R.unit(a),R.unit(b)))))*180/Math.PI,qa=(a,b)=>R.length(R.qlog(R.qm(a,R.qinv(b))))*180/Math.PI;
const measure=p=>Object.fromEntries(['L','R'].map(side=>{const l=S.leg(p,names,side),local=R.localize(p.points,p.q,parents);return [side,{bend:180-angle(R.sub(p.points[l.hip],p.points[l.knee]),R.sub(p.points[l.foot],p.points[l.knee])),hip:local.q[l.hip],dir:R.sub(p.points[l.foot],p.points[l.hip])}];}));
const started=performance.now(),seq=F.sequence(run,jumps,settings,parents,reference,null,null,{horizon:2.55}),rows=[];
check(seq.events.length===2&&seq.events.every(e=>e.status==='Push'),'Both current markers produce a push');
let maxHip=0,maxKnee=0,hipAt=null,kneeAt=null;
for(let f=54*4;f<=146*4;f++){
 const time=f/240,frame=seq.sample(time),p=T.project(frame.pose,seq.surfaces),m=measure(p),previous=rows.at(-1);rows.push({f:f/4,m});
 check(p.points.flat().concat(p.q.flat()).every(Number.isFinite),'Finite displayed pose '+f);
 for(const side of ['L','R']){
  const l=S.leg(p,names,side),rest=S.leg(reference,names,side);
  check(Math.abs(l.upper-rest.upper)<1e-5&&Math.abs(l.lower-rest.lower)<1e-5,'No leg stretch '+f+side);
  if(previous){const hip=qa(m[side].hip,previous.m[side].hip),knee=Math.abs(m[side].bend-previous.m[side].bend);if(hip>maxHip){maxHip=hip;hipAt=[f/4,side];}if(knee>maxKnee){maxKnee=knee;kneeAt=[f/4,side];}}
 }
}
const report={maxHipPer240Hz:maxHip,hipAt,maxKneePer240Hz:maxKnee,kneeAt,segments:seq.segments.map(s=>({side:s.supportFoot,push:s.jumpStart*60,release:s.airStart*60,knee:measure(T.project(seq.sample(s.airStart).pose,seq.surfaces))[s.supportFoot].bend}))};

check(maxHip<10,'No hidden thigh rotation snap between rendered frames');
check(maxKnee<8,'No hidden knee pop between rendered frames');
for(const s of seq.segments){
 const at=s.airStart,side=s.supportFoot,a=measure(T.project(seq.sample(at-1e-6).pose,seq.surfaces))[side],b=measure(T.project(seq.sample(at+1e-6).pose,seq.surfaces))[side];
 check(Math.abs(a.bend-b.bend)<.05&&qa(a.hip,b.hip)<.05,'Continuous displayed departure '+side+at);
 check(s.spinContact.activeBones(at+.001).length===0,'Follow does not renew contact '+at);
 const t=at+.12,wanted=JSON.stringify(seq.sample(t).pose);seq.sample(at+.4);seq.sample(at-.1);check(JSON.stringify(seq.sample(t).pose)===wanted,'Seek-stable leg continuation '+at);
}
const first=seq.segments[0],a=first.bounce.sample(first.bounce.loadDuration),b=first.bounce.released;
check(Math.abs(a.v[2]-b.v[2])<.01,'Push preserves incoming forward momentum');

// A release almost on a regular collision tick must not manufacture velocity
// by dividing a normal contact-skin correction by a microscopic time step.
const K=require(base+'capsule.js'),skin=1e-6;
for(const delta of [-1e-7,0,1e-7]){
 const boundary=.1+delta,source=t=>{const root=[t,.1*t,0];return {root,pose:{points:[root],q:[[0,0,0,1]],axes:[R.toAxes([0,0,0,1])]},phase:'RISE',airTime:t};};
 const body={move:(a,b)=>({root:R.add(b.points[0],[0,skin,0]),contacts:[]}),resolve:p=>({root:p.points[0],contacts:[]})};
 const track=K.track(source,{start:0,surfaces:[],speed:1,gait:t=>source(t).pose,forceSource:true,body,bodyDuringSupport:true,exactSource:true,breakTimes:[boundary,Infinity,-1]});
 for(const t of [boundary,boundary+1e-7,boundary+.001])check(Math.abs(track.state(t).velocity[1]-.1)<.01,'No collision-skin velocity spike near aligned release '+delta+':'+t);
}
console.log(JSON.stringify({passed:true,checks:checks.length,milliseconds:performance.now()-started,report},null,2));
