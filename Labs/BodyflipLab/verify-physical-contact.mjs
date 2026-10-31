import fs from 'node:fs';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),F=require('./flight.js'),I=require('./idle.js'),Target=require('./target-rig.js'),Mass=require('./mass.js');
const read=n=>JSON.parse(fs.readFileSync(new URL(n,import.meta.url))),bytes=n=>{const b=fs.readFileSync(new URL(n,import.meta.url));return b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength);};
const m=read('data/manifest.json'),{names,parents}=m,reference=C.poseFromShared(m),rig=Target.create(names,parents,reference),mass=Mass.model(names,parents,reference),run=I.create(read('data/idle.json'),bytes('data/idle.bin'),m).motion(),jumps=['data/jumps.json','data/jumps-standing.json'].flatMap(n=>read(n).clips).map(F.decodeJump),reports=[];
const fixtures=[
 {name:'stationary pair',rate:0,axis:3,early:0,status:'Push'},
 {name:'pair pushes then starts spin',rate:0,handRate:120,axis:3,early:0,status:'Push'},
 {name:'one hand releases',rate:240,axis:3,early:1,status:'Push'},
 {name:'both hands release before push',rate:240,axis:0,early:2,status:'Miss'},
 {name:'mirrored incoming spin',rate:-240,axis:9,early:1,status:'Push'}
];
for(const fixture of fixtures){
 const {rate,axis,handRate}=fixture,handSpin=handRate===undefined?{}:{flip:handRate,twist:0,instantSpin:true};
 const settings=C.sanitize({mode:'idle',ramps:false,surfaceIK:false,loadYMs:100,loadFullMs:100,supportAlpha:0,spinInertia:0,platforms:[{id:'floor',position:[0,-.2,0],size:[20,.4,40],rotation:[0,0,0,1]}],jumpEvents:[{id:'spin',time:0,jumpPercent:0,spinVersion:2,flip:rate,twist:0,turnIn:0,turnAxis:axis},{id:'hand',time:.1,pushWith:'handBoth',jumpPercent:50,spinVersion:2,...handSpin}]}),seq=F.sequence(run,jumps,settings,parents,reference,null,null,{horizon:.8}),segment=seq.segments[1],releases=segment.spinContact.releases;
 const report={...fixture,paired:!!segment.support.paired,releases,actualStatus:seq.events[1].status,maxAnchor:0,maxLimit:0,maxSeam:0,maxAngularSeam:0,maxCOMMetadataError:0,physicalFrames:0};
 assert(report.paired,fixture.name+' must exercise two hands');assert.equal(releases.filter(h=>h.early).length,fixture.early,fixture.name+' expected release ownership');assert.equal(report.actualStatus,fixture.status);
 for(let f=6;f<=48;f++){
  const frame=seq.sample(f/60),p=rig.project(frame.pose,seq.surfaces);assert(p.points.flat().concat(p.q.flat()).every(Number.isFinite));
  for(const e of rig.joints.inspect(p)){report.maxAnchor=Math.max(report.maxAnchor,e.anchorError);report.maxLimit=Math.max(report.maxLimit,e.angularError);}
  if(frame.physical){report.physicalFrames++;report.maxCOMMetadataError=Math.max(report.maxCOMMetadataError,R.length(R.sub(Mass.center(frame.pose,mass),frame.physical.com)));}
 }
 for(const release of releases){
  const a=seq.sample(release.time-1e-7).pose,b=seq.sample(release.time+1e-7).pose;
  report.maxSeam=Math.max(report.maxSeam,...a.points.slice(1).map((p,i)=>R.length(R.sub(p,b.points[i+1]))));
  report.maxAngularSeam=Math.max(report.maxAngularSeam,...a.q.slice(1).map((q,i)=>R.length(R.qlog(R.qm(q,R.qinv(b.q[i+1]))))));
 }
 assert(report.maxAnchor<1e-9&&report.maxLimit<1e-8,'Constrained target cannot stretch/break arms');
 assert(report.maxSeam<.003&&report.maxAngularSeam<.003,'Release pose is continuous '+JSON.stringify(report));
 assert(report.maxCOMMetadataError<1e-8,'Resolved carrier COM must be applied to physical metadata exactly once');
 if(releases.every(r=>r.early)&&segment.spinReleaseTime<=segment.jumpStart){assert.equal(seq.events[1].status,'Miss');assert.equal(segment.pushDebug(segment.jumpStart),null,'No phantom push after losing both hands');}
 assert(report.physicalFrames>0,'Successful stationary pushes also use the commanded COM launch');
 if(!rate&&!handRate)assert.equal(seq.sample(segment.spinReleaseTime+.01).physical.balanced,false,'Stationary push must not add angular compensation');
 const at=.3,saved=JSON.stringify(seq.sample(at));seq.sample(.8);seq.sample(.1);assert.equal(JSON.stringify(seq.sample(at)),saved,'Contact release is seek-order independent');
 reports.push(report);console.log(JSON.stringify(report));
}
const result={passed:true,cases:reports.length,maxSeam:Math.max(...reports.map(r=>r.maxSeam)),reports};
fs.writeFileSync(new URL('../../Saved/Diagnostics/BodyflipPort20261030/physical-contact.json',import.meta.url),JSON.stringify(result,null,2));console.log(JSON.stringify({passed:true,cases:reports.length,maxSeam:result.maxSeam}));
