import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {createProjectileSystem} from './projectile.js';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),V=require('./vanilla.js'),A=require('./attack.js');
const read=p=>JSON.parse(fs.readFileSync(new URL(p,import.meta.url))),data=read('./data/clips.json'),assets=read('./data/objects.json'),saved=C.sanitize(read('./fixtures/attack-presets.json').settings);
const rig=A.rig(data.names,data.parents),hand=data.names.indexOf('hand_l'),arm=data.names.indexOf('lowerarm_l'),top=rig.spines.at(-1);
const near=(a,b,tol=1e-8)=>assert(R.length(R.sub(a,b))<tol,JSON.stringify({a,b}));
const sameQ=(a,b)=>assert(1-Math.abs(R.dot(a,b))<1e-9);
const finite=pose=>assert([...pose.points.flat(),...pose.q.flat()].every(Number.isFinite));
const targets=[saved.target,[4,3,4],[-4,.3,4],[4,2,-4],[-4,5,-4],[0,8,1],[0,-2,4]];
const sim=await createProjectileSystem(assets,R,V);let poseCases=0,launchCases=0,maxError=0;
try{
 for(const raw of data.clips){
  const clip=C.decode(raw,data.parents),release=raw.id==='big-throw'?34.25/60:15.75/60,controls=V.config(saved.vanilla[raw.id]||{},clip.duration*60,release*60);controls.armed=Math.min(25,Math.floor(release*60));
  assert.equal(controls.halfAttack,false);assert.equal(controls.aimAtTarget,false);
  const sample=t=>V.pose(V.pose(C.sample(clip,t,data.parents),data.parents,arm,controls.forearmKeys,t*60,true),data.parents,hand,controls.keys,t*60),initial=sample(0),releasePose=sample(release);
  const off=A.prepare({rig,initial,releasePose,velocity:[1,2,3],target:saved.target});assert.equal(off.apply(releasePose,release*60),releasePose);
  const halfOff=A.prepare({rig,initial,releasePose,velocity:[1,2,3],target:saved.target,half:true});
  for(let f=0;f<=clip.duration*60;f+=.5){
   const source=sample(f/60),pose=halfOff.apply(source,f);finite(pose);
   for(let j=0;j<data.names.length;j++){
    if(rig.upper[j])sameQ(pose.q[j],source.q[j]);
    else {assert.deepEqual(pose.points[j],initial.points[j]);assert.deepEqual(pose.q[j],initial.q[j]);}
   }
   poseCases++;
  }
  for(const kind of ['spear','sword','bomb']){
   const base={key:raw.id,kind,release,sample,hand,duration:clip.duration,target:saved.target,radius:.16,controls,grip:saved.grips[raw.id][kind],scale:saved.weaponScales[raw.id][kind]};
   const original=structuredClone(sim.preview(base));assert.deepEqual(sim.reference(base),original);
   const halfOnly={...base,baseSample:sample,sample:t=>halfOff.apply(sample(t),t*60),preserveLaunch:true,launchRotation:halfOff.rotation};
   const halfSeed=sim.preview(halfOnly);near(halfSeed.v,original.v);near(halfSeed.omega,original.omega);sameQ(halfSeed.q,original.q);
   for(const half of [false,true])for(const target of targets){
    const plan=A.prepare({rig,initial,releasePose,velocity:original.v,...(kind!=='bomb'?{aimAxis:original.axis,aimPoint:original.p,aimBone:hand}:{}),target,half,aim:true,armed:controls.armed});
    const transformed=t=>plan.apply(sample(t),t*60),o={...base,target,baseSample:sample,sample:transformed,preserveLaunch:true,launchRotation:plan.rotation};
    const pose=transformed(release),seed=sim.preview(o),direction=R.unit(R.sub(target,kind==='bomb'?pose.points[top]:seed.p)),error=R.length(R.sub(kind==='bomb'?R.unit(seed.v):seed.axis,direction));maxError=Math.max(maxError,error);assert(error<1e-7,JSON.stringify({raw:raw.id,kind,half,target,error}));
    assert(Math.abs(R.length(seed.v)-R.length(original.v))<1e-8);assert.equal(seed.twist,original.twist);sameQ(seed.q,R.qm(plan.rotation,original.q));near(seed.v,R.rotate(plan.rotation,original.v));
    if(kind!=='bomb'){const toward=R.sub(target,seed.p);assert(R.dot(toward,seed.axis)>0);assert(R.length(R.cross(toward,seed.axis))<1e-6,'Shaft ray must intersect target');}
    if(kind!=='bomb')for(const velocity of [[0,0,0],R.mul(original.v,-2)]){
     const independent=A.prepare({rig,initial,releasePose,velocity,aimAxis:original.axis,aimPoint:original.p,aimBone:hand,target,half,aim:true,armed:controls.armed});
     assert.equal(independent.valid,true);sameQ(independent.rotation,plan.rotation);
    }
    for(const f of [0,controls.armed/2,controls.armed,release*60,release*60+20]){
     const source=sample(f/60),p=transformed(f/60);finite(p);
     if(half){for(let j=0;j<data.names.length;j++)if(!rig.upper[j]){near(p.points[j],initial.points[j]);sameQ(p.q[j],initial.q[j]);}}
     else {const delta=R.qm(p.q[rig.pelvis],R.qinv(source.q[rig.pelvis]));near(R.rotate(delta,[0,1,0]),[0,1,0]);}
     // FK sockets and other local rotations are preserved. All five spines
     // receive a share, rather than placing all the turn at spine_01.
     const basePose=half?A.halfPose(source,initial,rig):source,local=R.localize(p.points,p.q,data.parents),before=R.localize(basePose.points,basePose.q,data.parents);
     for(let j=1;j<data.names.length;j++){near(local.p[j],before.p[j]);if(!rig.spines.includes(j))sameQ(local.q[j],before.q[j]);}
     if(f>=controls.armed){const angles=rig.spines.map(j=>R.length(R.qlog(R.qm(local.q[j],R.qinv(before.q[j])))));assert(Math.max(...angles)-Math.min(...angles)<1e-7,JSON.stringify(angles));}
     poseCases++;
    }
    const start=sim.at(release,o);near(start.p,seed.p,1e-5);sameQ(start.q,seed.q);near(start.v,seed.v,1e-4);
    const flight=sim.at(release+.15,o);assert([...flight.p,...flight.q,...flight.v].every(Number.isFinite));const steps=sim.diagnostics.steps;sim.at(release+.05,o);assert.deepEqual(sim.at(release+.15,o),flight);assert.equal(sim.diagnostics.steps,steps);
    const beforeArmed=transformed(controls.armed/60-1e-7),atArmed=transformed(controls.armed/60);near(beforeArmed.points[hand],atArmed.points[hand],1e-4);
    launchCases++;
   }
   assert.deepEqual(sim.preview(base),original,'Off restores original seed exactly');
  }
  for(const half of [false,true]){
   const armed=controls.armed,rawSample=t=>C.sample(clip,t,data.parents),rawInitial=rawSample(0),armedPose=rawSample(armed/60);
   const direct=A.prepare({rig,initial:rawInitial,armedPose,releasePose:rawSample(release),velocity:[-2,1,9],target:saved.target,half,aim:true,armed});
   const first=direct.apply(rawSample(0),0);for(let j=0;j<data.names.length;j++){near(first.points[j],rawInitial.points[j]);sameQ(first.q[j],rawInitial.q[j]);}
   const entry=direct.apply(rawSample(armed/120),armed/2),firstLocal=R.localize(rawInitial.points,rawInitial.q,data.parents),armedLocal=R.localize(armedPose.points,armedPose.q,data.parents),entryLocal=R.localize(entry.points,entry.q,data.parents);
   for(let j=1;j<data.names.length;j++)if(!rig.spines.includes(j)&&(!half||rig.upper[j]))sameQ(entryLocal.q[j],R.qslerp(firstLocal.q[j],armedLocal.q[j],.5));
   const before=direct.apply(rawSample(armed/60-1e-7),armed-6e-6),at=direct.apply(armedPose,armed);near(before.points[hand],at.points[hand],1e-4);
   // The direct entry layer still accepts current whole-frame key edits.
   const f=10,basePose=direct.apply(rawSample(f/60),f),keyed=V.pose(basePose,data.parents,hand,[{frame:f,rotation:[20,0,0]}],f);
   sameQ(keyed.q[hand],R.qm(basePose.q[hand],V.rotation([20,0,0])));
   const zero=A.prepare({rig,initial,releasePose,velocity:[0,0,0],target:saved.target,half,aim:true,armed:0});assert.equal(zero.valid,false);finite(zero.apply(releasePose,0));
   const origin=half?A.halfPose(releasePose,initial,rig):releasePose,coincident=A.prepare({rig,initial,releasePose,velocity:[1,0,0],target:origin.points[top],half,aim:true});assert.equal(coincident.valid,false);finite(coincident.apply(releasePose,0));
  }
 }
 const receipt={success:true,poseCases,launchCases,maxDirectionError:maxError,checks:'Both clips and all weapons; half pelvis/legs fixed and authored upper world rotations; exact off/preset speed/twist; release shaft ray intersects target; five-spine distribution; no added pelvis tilt; fractional release, deterministic Jolt flight, Armed continuity, zero velocity/coincident target.'};
 fs.writeFileSync(new URL('../../Saved/ThrowLab/attack-verification.json',import.meta.url),JSON.stringify(receipt,null,2));console.log(JSON.stringify(receipt));
}finally{sim.dispose();}
