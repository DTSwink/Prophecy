// Real single-thread Jolt replay. No browser, persistent workers or scene writes.
import fs from 'node:fs';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),F=require('./flight.js'),G=require('./space-gym.js'),I=require('./idle.js');
const read=n=>JSON.parse(fs.readFileSync(new URL(n,import.meta.url))),bytes=n=>{const b=fs.readFileSync(new URL(n,import.meta.url));return b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength);};
const manifest=read('data/manifest.json'),{names,parents}=manifest,reference=C.poseFromShared(manifest),run=I.create(read('data/idle.json'),bytes('data/idle.bin'),manifest).motion(),jumps=['data/jumps.json','data/jumps-standing.json'].flatMap(n=>read(n).clips).map(F.decodeJump),catalog=new Map(read('data/vanilla.json').clips.map(meta=>[meta.name,C.decode(meta,bytes(meta.file),names,parents)]));
globalThis.Recovery=R;const {createPhysics}=await import('./physics.mjs'),physics=await createPhysics(manifest,reference),reports=[];
const distance=(a,b)=>R.length(R.sub(a,b));
function replay(label,seq,end,space){
 physics.configure({dynamic:true,surfaces:seq.surfaces,zeroGravity:space,cap:20});physics.reset(seq.sample(0).pose,seq.sample(0).velocity||[0,0,0]);
 const report={label,frames:0,maxPose:0,maxPelvis:0,maxAnchor:0,maxHingeExcess:0,meanPose:0,peak:0};
 for(let i=1;i<=Math.ceil(end*240);i++){
  const time=i/240,frame=seq.sample(time),target=physics.target(frame.pose);physics.step(target,1/240);const actual=physics.read(),d=physics.diagnostics();
  assert(d.finite&&d.dynamicBodies===25&&d.pelvisDynamic,label+' stays fully simulated');
  const error=Math.max(...target.points.slice(1).map((p,j)=>distance(p,actual.points[j+1])));if(error>report.maxPose){report.maxPose=error;report.peak=time*60;}
  report.maxPelvis=Math.max(report.maxPelvis,distance(actual.points[1],target.points[1]));report.maxAnchor=Math.max(report.maxAnchor,d.anchorError);report.meanPose+=error;report.frames++;
  for(const h of d.hinges)report.maxHingeExcess=Math.max(report.maxHingeExcess,h.min-h.angle,h.angle-h.max);
 }
 report.meanPose/=report.frames;reports.push(report);console.log(JSON.stringify(report));
}
try{
 for(const axis of process.argv.includes('--contact-only')?[]:[0,3,6,9]){
  const s=C.sanitize({mode:'spaceGym',axis,spinInertia:1}),events=[{time:0,spinVersion:2,jumpPercent:0,flip:axis===6?-240:180,twist:90,turnAxis:axis,turnIn:.2,pose:'pose1',poseIn:.3,poseHold:.5,poseOut:.3},{time:1.2,jumpPercent:0,spinVersion:2,flip:-120,twist:-90,turnIn:.2,turnOut:.2}];
  replay('axis '+axis,G.sequence(run,jumps,s,parents,events,catalog,reference),2,true);
 }
 for(const rate of process.argv.includes('--contact-only')?[]:[720,1440,3600]){
  const s=C.sanitize({mode:'spaceGym',spinInertia:1}),events=[{time:0,spinVersion:2,jumpPercent:0,flip:rate,twist:rate/2,turnIn:.2,pose:'pose1'}];replay('fast '+rate,G.sequence(run,jumps,s,parents,events,catalog,reference),1.2,true);
 }
 for(const [attack,clip] of process.argv.includes('--contact-only')?[]:catalog){
  const s=C.sanitize({mode:'spaceGym',spinInertia:1}),events=[{id:'a',time:.1,spinVersion:2,jumpPercent:0,flip:120,twist:45,turnIn:.2,attack}];
  replay(attack,G.sequence(run,jumps,s,parents,events,catalog,reference),Math.min(3.5,clip.duration+1),true);
 }
 const floor={id:'floor',position:[0,-.2,0],size:[20,.4,40],rotation:[0,0,0,1]};
 for(const pushWith of ['foot','handL','handBoth']){
  const s=C.sanitize({mode:'idle',ramps:false,surfaceIK:false,platforms:[floor],jumpEvents:[{id:'jump',time:.1,pushWith,spinVersion:2,flip:120,twist:30,jumpPercent:50,turnIn:.2}]}),seq=F.sequence(run,jumps,s,parents,reference,null,catalog,{horizon:1.8});replay(pushWith,seq,1.8,false);
 }
 for(const [label,rate,axis,rotation,pushWith] of [
  ['paired inherited',120,3,[0,0,0,1],'handBoth'],
  ['paired lost',240,3,[0,0,0,1],'handBoth'],
  ['foot inherited',-120,0,[0,0,0,1],'foot'],
  ['incline foot',90,0,R.qexp([Math.PI/4,0,0]),'foot'],
  ['incline hand',60,3,R.qexp([-Math.PI/4,0,0]),'handBoth'],
  ['wall hand',60,3,R.qexp([Math.PI/2,0,0]),'handBoth']]){
  const platform={...floor,rotation,position:label==='wall hand'?[0,1,1]:floor.position};
  const s=C.sanitize({mode:'idle',ramps:false,surfaceIK:false,spinInertia:0,loadYMs:100,loadFullMs:100,platforms:[platform],jumpEvents:[{id:'spin',time:0,jumpPercent:0,spinVersion:2,flip:rate,twist:0,turnIn:0,turnAxis:axis},{id:'push',time:.1,pushWith,jumpPercent:50,spinVersion:2}]}),seq=F.sequence(run,jumps,s,parents,reference,null,null,{horizon:1.2});replay(label,seq,1.2,false);
 }
}finally{physics.dispose();}
fs.mkdirSync(new URL('../../Saved/BodyflipLab/AngularMotion/',import.meta.url),{recursive:true});fs.writeFileSync(new URL('../../Saved/BodyflipLab/AngularMotion/'+(process.argv.includes('--contact-only')?'sim-contacts.json':'sim-sweep.json'),import.meta.url),JSON.stringify(reports,null,2));
assert(reports.every(r=>r.maxAnchor<.015&&r.maxHingeExcess<.06),'Jolt joints remain attached and within physical limits');
assert(reports.every(r=>r.maxPose<.12&&r.maxPelvis<.03&&r.meanPose<.03),'No sustained simulated tracking divergence');
console.log(JSON.stringify({passed:true,cases:reports.length,frames:reports.reduce((n,r)=>n+r.frames,0),maxPose:Math.max(...reports.map(r=>r.maxPose))}));
