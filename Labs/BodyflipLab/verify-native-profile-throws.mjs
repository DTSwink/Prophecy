// Small exact-PHAT throw set: total launch, COM, anchors, and joint limits.
import fs from 'node:fs';import assert from 'node:assert/strict';import crypto from 'node:crypto';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),T=require('./throw-attack.js'),A=require('./attack-aim.js'),F=require('./flight.js'),I=require('./idle.js'),P=require('./rig-profile.js'),Target=require('./target-rig.js');
const read=p=>JSON.parse(fs.readFileSync(new URL(p,import.meta.url))),bytes=p=>{const b=fs.readFileSync(new URL(p,import.meta.url));return b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength);},hash=p=>crypto.createHash('sha256').update(fs.readFileSync(new URL(p,import.meta.url))).digest('hex');
const files=['rig-profile.js','mass.js','attack-inertia.js','joint-rig.js','target-rig.js','attack-aim.js','throw-attack.js','fixtures/native-rig.json'],before=Object.fromEntries(files.map(p=>[p,hash(p)]));
const manifest=read('data/manifest.json'),{names,parents}=manifest,reference=C.poseFromShared(manifest);P.install(read('fixtures/native-rig.json'),names,parents);T.load(read('data/throws.json'));
const f=R.rotate(reference.q[1],[0,-1,0]),base=R.qm(R.fromTo(R.unit([f[0],0,f[2]]),[0,0,1]),reference.q[1]),physical=C.centerPose(reference,C.orientation(0,0,0,base),[0,1.5,0]),rig=Target.create(names,parents,physical),project=p=>rig.project(p);
const idle=I.create(read('data/idle.json'),bytes('data/idle.bin'),manifest).motion(),jumps=['data/jumps.json','data/jumps-standing.json'].flatMap(p=>read(p).clips).map(F.decodeJump),rows=[];
let samples=0,maxConstraint=0,maxAnchor=0,maxCOM=0;
for(const [attack,charge,flip,twist,drift] of [['big-throw',100,180,90,[1,0,2]],['small-throw',37,-180,-90,[0,0,0]],['small-throw',100,90,120,[-1,.5,0]]]){
 const settings=C.sanitize({mode:'spaceGym',kickToArmed:true,aimWeight:1,spinLag:.6,trimOut:3,jumpEvents:[{id:'a',time:.1,jumpPercent:0,spinVersion:2,flip,twist,attack,throwCharge:charge}]}),seq=F.sequence(idle,jumps,settings,parents,reference,null,new Map(),{horizon:3}),track=seq.segments[0].attack;
 const sample=t=>{const p=seq.sample(t).pose;return {...p,points:p.points.map(x=>R.add(x,R.mul(drift,t)))};},launchAt=(p,map=x=>x)=>track.launchAt(p,track.transportVelocity(t=>map(sample(t),t))),plan=A.create({track,names,parents,reference,sampleHit:sample,project,launchAt});
 for(const direction of [[0,0,-1],[1,1,0]]){
  const target=R.add(plan.origin,R.mul(R.unit(direction),3)),at=t=>project(plan.apply(sample(t),t,target)),p=at(track.releaseTime),carrier=track.transportVelocity(at),packet=track.launchAt(p,carrier,track.transportAngularVelocity(at));
  const error=R.length(R.sub(R.unit(packet.v),R.unit(R.sub(target,A.launchCenter(packet))))),turn=R.qm(p.q[track.hand],R.qinv(track.releaseSource.q[track.hand]));
  assert(packet.p.concat(packet.q,packet.v,packet.omega).every(Number.isFinite));assert(R.length(R.sub(R.sub(packet.v,carrier),R.rotate(turn,track.model.launch.v)))<1e-8,'source impulse preserved');
  for(const time of [track.start,track.start+(track.releaseTime-track.start)*.25,track.start+(track.releaseTime-track.start)*.5,track.start+(track.releaseTime-track.start)*.75,track.releaseTime,track.releaseTime+.05]){
   const pose=at(time),checks=rig.joints.inspect(pose),angular=Math.max(...checks.map(c=>c.angularError)),anchor=Math.max(...checks.map(c=>c.anchorError)),com=R.length(R.sub(A.center(sample(time),plan.rig),A.center(pose,plan.rig)));
   assert(angular<1e-6,`native joint ${angular}`);assert(anchor<1e-8,`native anchor ${anchor}`);assert(com<1e-8,`COM moved ${com}`);maxConstraint=Math.max(maxConstraint,angular);maxAnchor=Math.max(maxAnchor,anchor);maxCOM=Math.max(maxCOM,com);samples++;
  }
  rows.push({attack,charge,flip,twist,drift,target,error,solverError:plan.solution(target).error});assert(error<1e-6,JSON.stringify(rows.at(-1)));console.log(attack,charge,direction,'pass',error);
 }
}
const after=Object.fromEntries(files.map(p=>[p,hash(p)]));assert.deepEqual(after,before,'sources changed during probe');
const report={passed:true,cases:rows.length,samples,mass:P.current().bodies.mass,bodies:P.current().bodies.length,maxDirection:Math.max(...rows.map(r=>r.error)),maxConstraint,maxAnchor,maxCOM,hashes:after,rows};fs.writeFileSync('Saved/Diagnostics/BodyflipPort20261030/native-profile-throws.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
