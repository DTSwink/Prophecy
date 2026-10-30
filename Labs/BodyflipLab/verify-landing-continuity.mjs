import fs from 'node:fs';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),base=process.cwd()+'/Labs/BodyflipLab/',R=require(base+'recovery.js'),C=require(base+'core.js');


const F=require(base+'flight.js'),read=f=>JSON.parse(fs.readFileSync(f,'utf8').replace(/^\uFEFF/,'')),fixture=read(base+'fixtures/'+(process.argv.includes('--backward')?'landing-heading':'landing-continuity')+'.json'),state={settings:fixture.settings},settings=C.sanitize({...state.settings,...JSON.parse(process.env.AUDIT_SETTINGS||'{}')}),manifest=read(base+'data/manifest.json'),{names,parents}=manifest,reference=C.poseFromShared(manifest),jumps=['jumps.json','jumps-standing.json'].flatMap(f=>read(base+'data/'+f).clips).map(F.decodeJump);
const gait=settings.mode==='jump'?'run':'walk',drawn=settings.attack==='pike'||settings.attack.startsWith('slash'),stem=gait+(drawn?'-drawn':'')+'-phases',meta=read(base+'data/'+stem+'.json'),width=3+meta.names.length*12,countFrames=Math.ceil(5*meta.fps)+2,phase=Math.round((settings.runPhase%1)*meta.stride),bytes=Buffer.alloc(countFrames*width*4),fd=fs.openSync(base+'data/'+stem+'.bin','r');
try{if(fs.readSync(fd,bytes,0,bytes.length,phase*meta.framesPerPhase*width*4)!==bytes.length)throw Error('Incomplete cached phase');}finally{fs.closeSync(fd);}
const roots=[],poses=[];for(let f=0;f<countFrames;f++){const row=Array.from({length:width},(_,i)=>bytes.readFloatLE((f*width+i)*4));roots.push(row.slice(0,3));poses.push({points:meta.names.map((_,i)=>row.slice(3+i*12,6+i*12)),axes:meta.names.map((_,i)=>[0,1,2].map(k=>row.slice(6+i*12+k*3,9+i*12+k*3)))});}




import assert from 'node:assert/strict';
const check=(ok,label)=>{assert(ok,label);checks++;};let checks=0,requests=0;
const run=F.decodeNN({...meta,duration:5,roots,poses}),T=require(base+'target-rig.js').create(names,parents,reference),M=require(base+'mass.js'),mass=M.model(names,parents,reference);
const generate=async q=>{requests++;for(let k=0;k<2;k++)for(let i=1;i<names.length;i++)check(R.length(R.sub(q.seeds[k].points[i],fixture.request.seeds[k].points[i]))<1e-7,'Recorded NN uses actual physical landing seeds');return fixture.result;};
const seq=await F.prepare(run,jumps,{...settings,trimOut:3.8},parents,reference,generate),rows=[];
const qa=(a,b)=>R.length(R.qlog(R.qm(a,R.qinv(b))))*180/Math.PI;
let maxRight=0,minForward=Infinity,maxSide=0;
for(let f=184*4;f<=220*4;f++){
 const frame=seq.sample(f/240),pose=T.project(frame.pose,seq.surfaces),local=R.localize(pose.points,pose.q,parents),com=M.center(pose,mass),last=rows.at(-1);rows.push({f:f/4,pose,com,local});
 check(pose.points.flat().concat(pose.q.flat()).every(Number.isFinite),'Finite recovery at '+f/4);
 if(last&&frame.capsule.landed){const turn=qa(local.q[names.indexOf('thigh_r')],last.local.q[names.indexOf('thigh_r')]),v=R.mul(R.sub(com,last.com),240);maxRight=Math.max(maxRight,turn);minForward=Math.min(minForward,v[2]);maxSide=Math.max(maxSide,Math.abs(v[0]));check(turn<6,'No right-thigh loop at '+f/4);check(v[2]>3.5,'No phantom backwards COM at '+f/4);check(Math.abs(v[0])<1,'No root-frame orbit at '+f/4);}
}
const time=seq.landings[0].time,a=seq.sample(time-1e-7).pose,b=seq.sample(time).pose;
for(let i=1;i<names.length;i++){check(R.length(R.sub(a.points[i],b.points[i]))<1e-5,'Physical landing position continuous '+names[i]);check(qa(a.q[i],b.q[i])<.01,'Physical landing rotation continuous '+names[i]);}
const pelvis=names.indexOf('pelvis'),turn=R.qm(b.q[pelvis],R.qinv(reference.q[pelvis])),forward=R.rotate(turn,[0,0,1]),heading=R.qexp([0,Math.atan2(forward[0],forward[2]),0]);
check(qa(b.q[0],heading)<1e-6,'Root heading equals landing pelvis heading');
for(const r of rows.filter(r=>r.f/60>=time))check(qa(r.pose.q[0],heading)<1e-6,'Recovery retains landing heading '+r.f);
if(process.argv.includes('--backward')){const last=seq.sample(3.8).pose,face=R.rotate(R.qm(last.q[pelvis],R.qinv(reference.q[pelvis])),[0,0,1]);check(face[2]<-.8,'Backward landing stays backward instead of snapping to RunF');}
const saved=JSON.stringify(seq.sample(195/60));seq.sample(3.8);seq.sample(1);check(saved===JSON.stringify(seq.sample(195/60)),'Seek-stable recovery');check(requests===1,'One bounded seeded rollout');
console.log(JSON.stringify({passed:true,checks,maxRightDegreesPer240Hz:maxRight,minForwardCOMSpeed:minForward,maxSideCOMSpeed:maxSide,landingFrame:time*60}));
