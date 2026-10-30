// Regression: an airborne planted foot must release without straightening its knee.
import fs from 'node:fs';import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),base=process.cwd()+'/Labs/BodyflipLab/',R=require(base+'recovery.js'),C=require(base+'core.js');


const F=require(base+'flight.js'),read=f=>JSON.parse(fs.readFileSync(f,'utf8').replace(/^\uFEFF/,'')),state={settings:read(base+'fixtures/airborne-foot-rejump.json')},settings=C.sanitize({...state.settings,legFollow:0,instantSpin:true,spinLag:.6,jumpEvents:state.settings.jumpEvents.map((e,i)=>({...e,time:i?116/60:e.time}))}),manifest=read(base+'data/manifest.json'),{names,parents}=manifest,reference=C.poseFromShared(manifest),jumps=['jumps.json','jumps-standing.json'].flatMap(f=>read(base+'data/'+f).clips).map(F.decodeJump);
const gait=settings.mode==='jump'?'run':'walk',drawn=settings.attack==='pike'||settings.attack.startsWith('slash'),stem=gait+(drawn?'-drawn':'')+'-phases',meta=read(base+'data/'+stem+'.json'),width=3+meta.names.length*12,countFrames=Math.ceil(5*meta.fps)+2,phase=Math.round((settings.runPhase%1)*meta.stride),bytes=Buffer.alloc(countFrames*width*4),fd=fs.openSync(base+'data/'+stem+'.bin','r');
try{if(fs.readSync(fd,bytes,0,bytes.length,phase*meta.framesPerPhase*width*4)!==bytes.length)throw Error('Incomplete cached phase');}finally{fs.closeSync(fd);}
const roots=[],poses=[];for(let f=0;f<countFrames;f++){const row=Array.from({length:width},(_,i)=>bytes.readFloatLE((f*width+i)*4));roots.push(row.slice(0,3));poses.push({points:meta.names.map((_,i)=>row.slice(3+i*12,6+i*12)),axes:meta.names.map((_,i)=>[0,1,2].map(k=>row.slice(6+i*12+k*3,9+i*12+k*3)))});}
const run=F.decodeNN({...meta,duration:5,roots,poses});

const S=require(base+'support.js'),target=require(base+'target-rig.js').create(names,parents,reference);
const seq=F.sequence(run,jumps,settings,parents,reference,null,null,{horizon:2.2}),seg=seq.segments[1],checks=[];
const check=(value,label)=>{assert(value,label);checks.push(label);};
const bend=p=>{const l=seg.support.leg,a=R.unit(R.sub(p.points[l.hip],p.points[l.knee])),b=R.unit(R.sub(p.points[l.foot],p.points[l.knee]));return 180-Math.acos(Math.max(-1,Math.min(1,R.dot(a,b))))*180/Math.PI;};
const displayed=t=>target.project(seq.sample(t).pose,seq.surfaces);
check(seq.events.every(e=>e.status==='Push'),'Both jumps still push');
// A foot-driven push may release earlier; check the actual pinned interval.
for(let f=Math.ceil(seg.supportStart*60);f/60<seg.airStart;f++){
 const t=f/60,frame=seq.sample(t),source=seg.rawSample(t);
 check(frame.capsule.poseContact,'Airborne support uses posed body at F'+f);
 check(R.length(R.sub(frame.root,source.root))<1e-5,'Standing capsule does not lift the airborne body at F'+f);
}
const at119=bend(displayed(119/60)),at120=bend(displayed(120/60));
check(at119>75&&at120>70,'Knee remains flexed across release');
check(Math.abs(at119-at120)<20,'No F119 to F120 straightening pop');
let previous=bend(displayed(119/60)),maxExtension=0;
for(let f=119*4+1;f<=128*4;f++){
 const p=displayed(f/240),angle=bend(p);maxExtension=Math.max(maxExtension,previous-angle);previous=angle;
 check(p.points.flat().concat(p.q.flat()).every(Number.isFinite),'Finite release '+f);
 for(const side of ['L','R']){const l=S.leg(p,names,side),rest=S.leg(reference,names,side);check(Math.abs(l.upper-rest.upper)<1e-5&&Math.abs(l.lower-rest.lower)<1e-5,'Leg lengths preserved '+f+side);}
}
check(maxExtension<6,'No hidden extension spike between rendered frames');
const at=121/60,expected=JSON.stringify(seq.sample(at).pose);seq.sample(2.15);seq.sample(1.95);
check(JSON.stringify(seq.sample(at).pose)===expected,'Seek order cannot change the release seed');
// Force a subsequent root displacement while holding the departing contact
// pose fixed. A post-release collision may translate the body, not rewrite
// the knee from the earlier planted pose.
const original=seg.spin.sample(at),moved={...original.pose,points:original.pose.points.map(p=>R.add(p,[0,.1,0]))};
const departure=t=>seg.spin.sample(t),plain=seg.spinContact.apply(original.pose,at,original,null,departure),shifted=seg.spinContact.apply(moved,at,original,null,departure);
check(Math.abs(bend(plain)-bend(shifted))<1e-8,'Later collision offset does not change release knee angle');
console.log(JSON.stringify({passed:true,checks:checks.length,kneeF119:at119,kneeF120:at120,maxExtensionPer240Hz:maxExtension},null,2));

