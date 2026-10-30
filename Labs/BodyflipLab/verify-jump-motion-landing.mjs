// Deterministic landing/NN contract. The saved-scene replay separately runs real NN.
import fs from 'node:fs';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),F=require('./flight.js'),C=require('./core.js'),R=require('./recovery.js'),I=require('./idle.js'),P=require('./body-contact.js');
const read=n=>JSON.parse(fs.readFileSync(new URL(n,import.meta.url))),m=read('data/manifest.json'),reference=C.poseFromShared(m),bytes=fs.readFileSync(new URL('data/idle.bin',import.meta.url)),idle=I.create(read('data/idle.json'),bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),m).motion(),jumps=['data/jumps.json','data/jumps-standing.json'].flatMap(n=>read(n).clips).map(F.decodeJump),body=P.create(m.names,m.parents,reference);
const checks=[],check=(name,ok)=>{assert(ok,name);checks.push(name);},requests=[],distance=(a,b)=>R.length(R.sub(a,b)),poseError=(a,b)=>Math.max(...a.points.slice(1).map((v,i)=>distance(v,b.points[i+1])));
const events=[{id:'a',time:.1,surface:'floor',spinVersion:2,flip:180,twist:45,pose:'pose2',poseIn:.2,poseHold:1.5,poseOut:.3},{id:'b',time:3,surface:'floor',spinVersion:2,flip:-120,twist:0,turnDelay:.1,turnAxis:3,pose:'pose4'}];
const settings=C.sanitize({mode:'idle',ramps:false,surfaceIK:false,jumpEvents:events,trimOut:5,platforms:[{id:'floor',position:[0,-.2,0],size:[20,.4,30],rotation:[0,0,0,1]}]}),input=JSON.stringify(settings);
const generate=async request=>{requests.push(request);const seed=request.seeds[1],origin=request.roots[1];return {names:request.names.slice(1),fps:30,duration:(request.frames-1)/30,roots:request.roots.slice(1,request.frames+1),poses:Array.from({length:request.frames},(_,i)=>({points:seed.points.slice(1).map(p=>R.add(p,R.sub(request.roots[i+1],origin))),axes:seed.axes.slice(1)})),continuation:{ticks:request.frames-1}};};
const plan=await F.prepare(idle,jumps,settings,m.parents,reference,generate);
check('Two marker commands are constructed',plan.segments.length===2);
check('At least one actual body landing requests continuation',plan.landings.length>0&&requests.length>0);
let maxLandingError=0,maxSeedError=0;
for(const landing of plan.landings){
 const entry=plan.sample(landing.time),before=plan.sample(landing.time-1e-7),request=requests.find(q=>poseError(q.seeds[1],entry.pose)<1e-7);maxLandingError=Math.max(maxLandingError,poseError(entry.pose,before.pose));
 check('NN receives exact displayed contact pose '+landing.time,!!request);if(request)maxSeedError=Math.max(maxSeedError,poseError(request.seeds[1],entry.pose));
 check('Landing ends flight instead of spinning the NN '+landing.time,entry.returnedToLocomotion&&!entry.spin);
 const gap=Math.min(...body.shapes(entry.pose).flatMap(s=>plan.surfaces.map(sf=>P.query(s,sf).gap)));check('Landing occurs at real body contact '+landing.time,Math.abs(gap)<.0002);
}
check('Landing is continuous: '+maxLandingError,maxLandingError<.001);
check('New marker retains independent target and axis',plan.segments[1].spin.target.flip===-120&&plan.segments[1].event.turnAxis===3);
const t=plan.landings[0].time-.01;check('Spin is still commanded just before landing',plan.sample(t).spin.target.flip>0);
const saved=JSON.stringify(plan.sample(4.9));plan.sample(.5);plan.sample(4);check('Continuation is deterministic under reverse seeking',JSON.stringify(plan.sample(4.9))===saved);
check('Inputs remain unchanged',JSON.stringify(settings)===input);
console.log(JSON.stringify({passed:true,checks:checks.length,maxLandingError,maxSeedError,landings:plan.landings,events:plan.events.map(e=>({id:e.id,status:e.status}))},null,2));
