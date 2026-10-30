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
 const floor={id:'floor',position:[0,-.2,0],size:[20,.4,40],rotation:[0,0,0,1]};
 for(const pushWith of ['foot','handL','handBoth']){
  const s=C.sanitize({spinLag:.6,mode:'idle',ramps:false,surfaceIK:false,platforms:[floor],jumpEvents:[{id:'jump',instantSpin:true,time:.1,pushWith,spinVersion:2,flip:120,twist:30,jumpPercent:50,turnIn:.2}]}),seq=F.sequence(run,jumps,s,parents,reference,null,catalog,{horizon:1.8});replay(pushWith,seq,1.8,false);
 }
}finally{physics.dispose();}
fs.mkdirSync(new URL('../../Saved/BodyflipLab/InstantSpin/',import.meta.url),{recursive:true});fs.writeFileSync(new URL('../../Saved/BodyflipLab/InstantSpin/sim.json',import.meta.url),JSON.stringify(reports,null,2));
assert(reports.every(r=>r.maxAnchor<.015&&r.maxHingeExcess<.06),'Jolt joints remain attached and within physical limits');
assert(reports.every(r=>r.maxPose<.12&&r.maxPelvis<.03&&r.meanPose<.03),'No sustained simulated tracking divergence');
console.log(JSON.stringify({passed:true,cases:reports.length,frames:reports.reduce((n,r)=>n+r.frames,0),maxPose:Math.max(...reports.map(r=>r.maxPose))}));
