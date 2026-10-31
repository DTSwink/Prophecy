// Narrow moving-carrier checks. No browser, physics worker, or live settings.
import fs from 'node:fs';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),T=require('./throw-attack.js'),Aim=require('./attack-aim.js'),F=require('./flight.js'),I=require('./idle.js'),J=require('./joint-rig.js');
const read=p=>JSON.parse(fs.readFileSync(new URL(p,import.meta.url))),bytes=p=>{const b=fs.readFileSync(new URL(p,import.meta.url));return b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength);};
T.load(read('data/throws.json'));const manifest=read('data/manifest.json'),{names,parents}=manifest,reference=C.poseFromShared(manifest),projector=require('./target-rig.js').create(names,parents,reference),project=p=>projector.project(p);
const idle=I.create(read('data/idle.json'),bytes('data/idle.bin'),manifest).motion(),jumps=['data/jumps.json','data/jumps-standing.json'].flatMap(p=>read(p).clips).map(F.decodeJump),reports=[];
const distance=(a,b)=>R.length(R.sub(a,b)),zeros=()=>J.create(names,parents,reference).joints.map(c=>c.hinge?[0]:[0,0,0]);let checks=0;
const failures=[];const check=(value,message)=>{checks++;if(!value)failures.push(message);};
function setup(name,charge,drift,flip,twist,shift=[0,0,0]){
 const settings=C.sanitize({mode:'spaceGym',spinLag:.6,spinInertia:1,aimWeight:1,jumpEvents:[{id:'throw',time:.1,spinVersion:2,instantSpin:true,flip,twist,jumpPercent:0,attack:name,attackDelay:.2,throwCharge:charge}],trimOut:3}),seq=F.sequence(idle,jumps,settings,parents,reference,null,new Map(),{horizon:3}),track=seq.segments[0].attack;
 const sample=t=>{const p=seq.sample(t).pose,d=R.add(shift,R.mul(drift,t));return {...p,points:p.points.map(x=>R.add(x,d))};};
 const launchAt=(pose,mapPose=p=>p)=>track.launchAt(pose,track.transportVelocity(t=>mapPose(sample(t),t)),track.transportAngularVelocity(t=>mapPose(sample(t),t)));
 const plan=Aim.create({track,names,parents,reference,sampleHit:sample,launchAt,project});
 const launch=at=>track.launchAt(at(track.releaseTime),track.transportVelocity(at),track.transportAngularVelocity(at));
 return {track,sample,plan,launch,name,charge,drift,flip,twist};
}
function evaluate(s,target){
 const at=t=>project(s.plan.apply(s.sample(t),t,target)),pose=at(s.track.releaseTime),packet=s.launch(at),error=distance(R.unit(packet.v),R.unit(R.sub(target,Aim.launchCenter(packet)))),carrier=s.track.transportVelocity(at),source=s.track.model.launch.v,turn=R.qm(pose.q[s.track.hand],R.qinv(s.track.releaseSource.q[s.track.hand]));
 check(packet.p.concat(packet.q,packet.v,packet.omega).every(Number.isFinite),'finite launch');
 check(distance(R.sub(packet.v,carrier),R.rotate(turn,source))<1e-9,'approved launch vector unchanged; no hidden speed/charge boost');
 check(Math.abs(error-s.plan.solution(target).error)<1e-7,'reported error measures the applied moving-carrier result');
 return {at,pose,packet,error,carrier};
}
// Each target is made from a known legal yaw trajectory, then independently
// solved. Thus nonzero residual cannot be excused as a physically impossible aim.
const cases=[
 ['big-throw',100,[3,2,-1],240,-180],
 ['small-throw',37,[1,-.5,2],-240,210],
 ['small-throw',100,[-4,1,1],120,300],
 ['big-throw',100,[0,11,0],-180,120]
];
let saved;
for(const args of cases){const s=setup(...args);for(const yaw of [-1.1,1.3]){
 const known=t=>s.plan.applyRotation(s.sample(t),{yaw:R.qexp([0,yaw*s.plan.weight(t),0]),offsets:zeros()}),seed=s.launch(known),target=R.add(Aim.launchCenter(seed),R.mul(R.unit(seed.v),4)),r=evaluate(s,target);
 reports.push({type:'reachable',name:s.name,charge:s.charge,drift:s.drift,flip:s.flip,twist:s.twist,yaw,error:r.error,speed:R.length(r.packet.v),target});
 check(r.error<1e-6,`known-reachable moving throw missed: ${JSON.stringify(reports.at(-1))}`);
 saved??={s,target,r};console.log(JSON.stringify(reports.at(-1)));
}}
// A 10% bomb cannot reverse these carriers (ordinary jump speed and an extreme).
// Check the solver against a
// bounded independent rigid-orientation sweep, without allowing impulse boosts.
for(const drift of [[0,11,0],[12,0,0],[0,0,-100]]){
 const s=setup('small-throw',10,drift,0,0),target=R.sub(s.plan.origin,R.mul(R.unit(drift),50)),r=evaluate(s,target),neutral=s.launch(t=>project(s.sample(t)));
 const baseline=distance(R.unit(neutral.v),R.unit(R.sub(target,Aim.launchCenter(neutral))));let sweep=Infinity;
 for(let i=0;i<24;i++){
  const z=1-2*(i+.5)/24,a=i*Math.PI*(3-Math.sqrt(5)),d=[Math.sqrt(1-z*z)*Math.cos(a),z,Math.sqrt(1-z*z)*Math.sin(a)],q=Aim.between(R.unit(neutral.v),d,[0,1,0]),log=R.qlog(q),at=t=>s.plan.applyRotation(s.sample(t),{yaw:R.qexp(R.mul(log,s.plan.weight(t))),offsets:zeros()}),p=s.launch(at);
  sweep=Math.min(sweep,distance(R.unit(p.v),R.unit(R.sub(target,Aim.launchCenter(p)))));
 }
 check(r.error>1,'unreachable direction must remain reported as a miss');
 check(r.error<=baseline+1e-7,'best effort cannot worsen the initial solution');
 check(r.error<=sweep+2e-4,'best effort is at least as good as independent rigid candidates');
 reports.push({type:'unreachable',drift,error:r.error,baseline,sweep,speed:R.length(r.packet.v),carrierSpeed:R.length(r.carrier),sourceSpeed:R.length(s.track.model.launch.v)});console.log(JSON.stringify(reports.at(-1)));
}
// Translating the entire experiment cannot change velocities or the aim result.
const {s,target,r}=saved,shift=[4,-3,7],moved=setup(s.name,s.charge,s.drift,s.flip,s.twist,shift),translated=evaluate(moved,R.add(target,shift));
check(distance(translated.packet.p,R.add(r.packet.p,shift))<1e-5,'world-translation covariance of release origin');check(distance(translated.packet.v,r.packet.v)<1e-5,'world-translation invariance of release velocity');check(Math.abs(translated.error-r.error)<1e-7,'world-translation invariance of aiming residual');
// The launch adapter itself must be equivariant under arbitrary rigid rotation,
// including carrier angular transport. This checks the source launch unchanged.
const q=R.qexp([.7,-1.2,.4]),offset=[3,2,-5],rotated=t=>{const p=r.at(t),quat=p.q.map(x=>R.qm(q,x));return {...p,points:p.points.map(x=>R.add(offset,R.rotate(q,x))),q:quat,axes:quat.map(R.toAxes)};},turned=s.launch(rotated);
check(distance(turned.p,R.add(offset,R.rotate(q,r.packet.p)))<1e-8,'rotated release origin');check(distance(turned.v,R.rotate(q,r.packet.v))<1e-7,'rotated source plus carrier velocity');check(distance(turned.omega,R.rotate(q,r.packet.omega))<1e-7,'rotated source plus carrier angular velocity');check(distance(Aim.launchCenter(turned),R.add(offset,R.rotate(q,Aim.launchCenter(r.packet))))<1e-8,'rotated projectile COM');
const output={passed:!failures.length,checks,cases:reports,failures};fs.mkdirSync(new URL('../../Saved/BodyflipLab/ThrowAim/',import.meta.url),{recursive:true});fs.writeFileSync(new URL('../../Saved/BodyflipLab/ThrowAim/drift-results.json',import.meta.url),JSON.stringify(output,null,2));console.log(JSON.stringify({passed:!failures.length,checks,cases:reports.length}));assert.equal(failures.length,0,failures.join('\n'));
