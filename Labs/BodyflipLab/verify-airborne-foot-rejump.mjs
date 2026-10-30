// Regression: a flipped body can have its root below ground while its planted leg is reachable.
import fs from 'node:fs';import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),base=process.cwd()+'/Labs/BodyflipLab/',R=require(base+'recovery.js'),C=require(base+'core.js');


const F=require(base+'flight.js'),read=f=>JSON.parse(fs.readFileSync(f,'utf8').replace(/^\uFEFF/,'')),state={settings:read(base+'fixtures/airborne-foot-rejump.json')},settings=C.sanitize({...state.settings,instantSpin:true,spinLag:.6}),manifest=read(base+'data/manifest.json'),{names,parents}=manifest,reference=C.poseFromShared(manifest),jumps=['jumps.json','jumps-standing.json'].flatMap(f=>read(base+'data/'+f).clips).map(F.decodeJump);
const gait=settings.mode==='jump'?'run':'walk',drawn=settings.attack==='pike'||settings.attack.startsWith('slash'),stem=gait+(drawn?'-drawn':'')+'-phases',meta=read(base+'data/'+stem+'.json'),width=3+meta.names.length*12,countFrames=Math.ceil(5*meta.fps)+2,phase=Math.round((settings.runPhase%1)*meta.stride),bytes=Buffer.alloc(countFrames*width*4),fd=fs.openSync(base+'data/'+stem+'.bin','r');
try{if(fs.readSync(fd,bytes,0,bytes.length,phase*meta.framesPerPhase*width*4)!==bytes.length)throw Error('Incomplete cached phase');}finally{fs.closeSync(fd);}
const roots=[],poses=[];for(let f=0;f<countFrames;f++){const row=Array.from({length:width},(_,i)=>bytes.readFloatLE((f*width+i)*4));roots.push(row.slice(0,3));poses.push({points:meta.names.map((_,i)=>row.slice(3+i*12,6+i*12)),axes:meta.names.map((_,i)=>[0,1,2].map(k=>row.slice(6+i*12+k*3,9+i*12+k*3)))});}
const run=F.decodeNN({...meta,duration:5,roots,poses});


// Keep physical geometry fixed while moving only the nonphysical root reference
// below the platform. This isolates the capsule bug from first-jump timing.
const sequence=F.sequence(run,jumps,settings,parents,reference,null,null,{horizon:2.2}),saved=sequence.segments[1],pose=saved.support.terminal.pose,root=pose.points[0].slice();root[1]-=.4;
const initial={...pose,points:pose.points.map((p,i)=>i?p:root)},incoming=saved.incomingVelocity;
const source=t=>({...initial,points:initial.points.map(p=>R.add(p,R.mul(incoming,t-.2)))});
const segment=F.create(run,jumps,settings,parents,reference,{time:.2,grounded:false,poseAt:source,velocityAt:()=>incoming,surface:saved.surface,surfaces:sequence.surfaces}),b=segment.bounce;
assert(sequence.events.every(e=>e.status==='Push'),'Both current saved jumps push');
assert(segment.support.terminal.pose.points[0][1]<-.15,'Fixture requires the root reference below the floor');
assert(b.loadDuration>0&&b.didPush&&b.released.v[1]>0,'Actual drive reverses incoming descent');
const first=b.frames[0],next=b.frames[1],dt=next.t-first.t;
assert(R.length(R.sub(next.p,R.add(first.p,R.add(R.mul(first.v,dt),[0,-.5*9.81*dt*dt,0]))))<1e-8,'Empty standing capsule cannot lift the airborne root');
for(let f=0;f<=16;f++){const p=segment.sample(.2+f/60).pose;assert(p.points.flat().concat(p.q.flat()).every(Number.isFinite),'Finite replay');}
console.log(JSON.stringify({passed:true,contact:segment.contactTime,push:segment.jumpStart,release:segment.airStart,releaseVelocity:b.released.v,load:b.loadDuration}));
