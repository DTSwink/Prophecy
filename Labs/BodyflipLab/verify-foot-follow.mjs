import fs from 'node:fs';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),base=process.cwd()+'/Labs/BodyflipLab/',R=require(base+'recovery.js'),C=require(base+'core.js');


const F=require(base+'flight.js'),read=f=>JSON.parse(fs.readFileSync(f,'utf8').replace(/^\uFEFF/,'')),state={settings:read(base+'fixtures/airborne-foot-rejump.json')},settings=C.sanitize({...state.settings,instantSpin:true,spinLag:.6,jumpEvents:state.settings.jumpEvents.map((e,i)=>({...e,time:i?116/60:e.time,jumpPercent:i?80:e.jumpPercent,flip:i?-300:e.flip}))}),manifest=read(base+'data/manifest.json'),{names,parents}=manifest,reference=C.poseFromShared(manifest),jumps=['jumps.json','jumps-standing.json'].flatMap(f=>read(base+'data/'+f).clips).map(F.decodeJump);
const gait=settings.mode==='jump'?'run':'walk',drawn=settings.attack==='pike'||settings.attack.startsWith('slash'),stem=gait+(drawn?'-drawn':'')+'-phases',meta=read(base+'data/'+stem+'.json'),width=3+meta.names.length*12,countFrames=Math.ceil(5*meta.fps)+2,phase=Math.round((settings.runPhase%1)*meta.stride),bytes=Buffer.alloc(countFrames*width*4),fd=fs.openSync(base+'data/'+stem+'.bin','r');
try{if(fs.readSync(fd,bytes,0,bytes.length,phase*meta.framesPerPhase*width*4)!==bytes.length)throw Error('Incomplete cached phase');}finally{fs.closeSync(fd);}
const roots=[],poses=[];for(let f=0;f<countFrames;f++){const row=Array.from({length:width},(_,i)=>bytes.readFloatLE((f*width+i)*4));roots.push(row.slice(0,3));poses.push({points:meta.names.map((_,i)=>row.slice(3+i*12,6+i*12)),axes:meta.names.map((_,i)=>[0,1,2].map(k=>row.slice(6+i*12+k*3,9+i*12+k*3)))});}

const assert=(await import('node:assert/strict')).default,S=require(base+'support.js'),M=require(base+'mass.js'),run=F.decodeNN({...meta,duration:5,roots,poses}),mass=M.model(names,parents,reference),T=require(base+'target-rig.js').create(names,parents,reference),checks=[];
const check=(ok,label)=>{assert(ok,label);checks.push(label);},distance=(a,b)=>R.length(R.sub(a,b)),angle=(a,b)=>Math.acos(Math.max(-1,Math.min(1,R.dot(R.unit(a),R.unit(b)))))*180/Math.PI;
const seq=F.sequence(run,jumps,settings,parents,reference,null,null,{horizon:2.5}),seg=seq.segments[1],l=seg.support.leg,release=seg.spinReleaseTime,point=seq.sample(release-1e-7).pose.points[l.foot];
check(seq.events.every(e=>e.status==='Push'),'Both saved foot jumps still push');
let maxAim=0,maxExtension=0,lastBend=null,maxCOM=0;
for(let i=0;i<=96;i++){
 const t=release+i/240,frame=seq.sample(t),p=T.project(frame.pose,seq.surfaces),hip=p.points[l.hip],knee=p.points[l.knee],foot=p.points[l.foot],bend=180-angle(R.sub(hip,knee),R.sub(foot,knee));
 if(i>=8&&i<=48)maxAim=Math.max(maxAim,angle(R.sub(foot,hip),R.sub(point,hip)));
 if(lastBend!==null)maxExtension=Math.max(maxExtension,lastBend-bend);lastBend=bend;
 const pure=seg.spin.sample(t,false),comError=distance(M.center(frame.pose,mass),R.add(M.center(pure.pose,mass),R.sub(frame.root,pure.root)));maxCOM=Math.max(maxCOM,comError);
 check(p.points.flat().every(Number.isFinite),'Finite pose '+i);
 check(Math.abs(distance(hip,knee)-l.upper)<1e-5&&Math.abs(distance(knee,foot)-l.lower)<1e-5,'No leg stretching '+i);
 check(seg.spinContact.activeBones(t).length===0,'Follow does not renew the ground pin '+i);
}
check(maxAim<3,'Displayed leg aims at its fixed world push point during follow');
check(maxExtension<4,'Extension stays smooth between 60Hz frames');
check(maxCOM<1e-7,'Follow preserves COM after carrier translation');
const t=release+settings.legFollow+settings.legBlend+.001,full=seq.sample(t),pure=seg.spin.sample(t,false),a=R.localize(full.pose.points,full.pose.q,parents),b=R.localize(pure.pose.points,pure.pose.q,parents);
check([l.hip,l.knee,l.foot,l.toe].every(i=>R.length(R.qlog(R.qm(a.q[i],R.qinv(b.q[i]))))<1e-8),'Leg returns fully to the moving animation');
const saved=JSON.stringify(seq.sample(release+.12).pose);seq.sample(release+.4);seq.sample(release-.1);check(JSON.stringify(seq.sample(release+.12).pose)===saved,'Seek stable');
const still=F.sequence(run,jumps,{...settings,spinLag:0,jumpEvents:[{...settings.jumpEvents[0],flip:0,twist:0}]},parents,reference,null,null,{horizon:1.4}),s=still.segments[0],q=still.sample(s.airStart+.1).pose,contact=still.sample(s.airStart-1e-7).pose.points[s.support.leg.foot];
check(angle(R.sub(q.points[s.support.leg.foot],q.points[s.support.leg.hip]),R.sub(contact,q.points[s.support.leg.hip]))<1,'World follow also works without body rotation');
check(C.sanitize({legFollow:0}).legFollow===0&&C.sanitize({legFollow:.35}).legFollow===.35,'Duration persists including zero');
const html=fs.readFileSync(base+'index.html','latin1'),panel=html.slice(html.indexOf('id="minorOptions"'),html.indexOf('<div class="readouts">'));
check(panel.indexOf('id="legFollow"')>panel.indexOf('id="spinLag"')&&html.split('id="legFollow"').length===2,'One control appended at the bottom');
console.log(JSON.stringify({passed:true,checks:checks.length,maxAimDegrees:maxAim,maxExtensionPer240Hz:maxExtension,maxCOMError:maxCOM},null,2));


