import fs from 'node:fs';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),F=require('./flight.js'),I=require('./idle.js'),Target=require('./target-rig.js');
const read=n=>JSON.parse(fs.readFileSync(new URL(n,import.meta.url))),bytes=n=>{const b=fs.readFileSync(new URL(n,import.meta.url));return b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength);};
const m=read('data/manifest.json'),{names,parents}=m,reference=C.poseFromShared(m),rig=Target.create(names,parents,reference),run=I.create(read('data/idle.json'),bytes('data/idle.bin'),m).motion(),jumps=['data/jumps.json','data/jumps-standing.json'].flatMap(n=>read(n).clips).map(F.decodeJump),reports=[];
for(const [rate,axis] of [[0,3],[60,3],[120,3],[240,3],[120,0],[-120,9]]){
 const settings=C.sanitize({mode:'idle',ramps:false,surfaceIK:false,loadYMs:100,loadFullMs:100,supportAlpha:0,spinInertia:0,platforms:[{id:'floor',position:[0,-.2,0],size:[20,.4,40],rotation:[0,0,0,1]}],jumpEvents:[{id:'spin',time:0,jumpPercent:0,spinVersion:2,flip:rate,twist:0,turnIn:0,turnAxis:axis},{id:'hand',time:.1,pushWith:'handBoth',jumpPercent:50,spinVersion:2}]}),seq=F.sequence(run,jumps,settings,parents,reference,null,null,{horizon:.8}),segment=seq.segments[1],releases=segment.spinContact.releases;
 const report={rate,axis,paired:!!segment.support.paired,releases,status:seq.events[1].status,maxAnchor:0,maxLimit:0,maxSeam:0};assert(report.paired,'Fixture must exercise a pair');
 for(let f=6;f<=48;f++){const frame=seq.sample(f/60),p=rig.project(frame.pose,seq.surfaces);assert(p.points.flat().concat(p.q.flat()).every(Number.isFinite));for(const e of rig.joints.inspect(p)){report.maxAnchor=Math.max(report.maxAnchor,e.anchorError);report.maxLimit=Math.max(report.maxLimit,e.angularError);}if(f/60<Math.min(segment.spinReleaseTime,seq.landings[0]?.time??Infinity))assert(Math.abs(frame.spin.target.flip-rate)<1e-9,'Support keeps the incoming spin command');}
 for(const release of releases){const a=seq.sample(release.time-1e-7).pose,b=seq.sample(release.time+1e-7).pose;report.maxSeam=Math.max(report.maxSeam,...a.points.slice(1).map((p,i)=>R.length(R.sub(p,b.points[i+1]))));}
 assert(report.maxAnchor<1e-9&&report.maxLimit<1e-8,'Constrained target cannot stretch/break arms');
 assert(report.maxSeam<.003,'Releasing a hand is continuous '+JSON.stringify(report));
 if(releases.every(r=>r.early)&&segment.spinReleaseTime<=segment.jumpStart){assert(seq.events[1].status==='Miss','No push after losing both hands');assert(segment.pushDebug(segment.jumpStart)===null,'No phantom push arrow');}
 const at=.3,saved=JSON.stringify(seq.sample(at));seq.sample(.8);seq.sample(.1);assert(JSON.stringify(seq.sample(at))===saved,'Contact release is seek-order independent');reports.push(report);
}
assert(reports.some(r=>r.releases.filter(h=>h.early).length===1),'Includes one-hand release with the other retained');
assert(reports.some(r=>r.releases.every(h=>h.early)),'Includes loss of both contacts');
assert(reports.some(r=>r.releases.every(h=>!h.early)),'A compatible pair remains attached');
fs.writeFileSync(new URL('../../Saved/BodyflipLab/AngularMotion/spin-contact-checks.json',import.meta.url),JSON.stringify(reports,null,2));console.log(JSON.stringify({passed:true,cases:reports.length,reports},null,2));
