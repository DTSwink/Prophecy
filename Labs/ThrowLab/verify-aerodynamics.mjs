import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {airShape,airForces} from './aerodynamics.js';
import {createProjectileSystem} from './projectile.js';
const require=createRequire(import.meta.url),R=require('./recovery.js'),V=require('./vanilla.js'),C=require('./core.js');
const read=p=>JSON.parse(fs.readFileSync(new URL(p,import.meta.url))),data=read('./data/clips.json'),assets=read('./data/objects.json'),saved=C.sanitize(read('./approved/2026-10-27/saved-profile.json').settings);
const angle=(a,b)=>Math.acos(Math.max(-1,Math.min(1,R.dot(R.unit(a),R.unit(b)))))*180/Math.PI;
let alignCases=0,forceCases=0;
for(const root of [[0,0,0],[50,-80,120]])for(const velocity of [[0,0,1],[2,-1,3]])for(const target of [[0,0,-1],[1,2,3]])for(const initial of [[0,0,0],[70,100,-50]]){
 const q=V.rotation(root),next=V.alignVelocity(velocity,q,target,initial),c=V.config({velocityRotation:next,speedScale:1.7,twist:5});
 const result=V.launch(velocity,[0,0,0],[0,0,0,1],q,[0,0,1],c);
 assert(angle(result.velocity,target)<1e-5);assert(Math.abs(R.length(result.velocity)-R.length(velocity)*1.7)<1e-8);assert.equal(c.twist,5);alignCases++;
}
assert.equal(V.alignVelocity([0,0,0],[0,0,0,1],[0,0,1],[0,0,0]),null);
for(const scale of [[1,1,1],[.1,.1,.1],[.5,1.8,.8]])for(const strength of [0,1,10])for(const pressure of [0,.27,.5])for(const damping of [0,1,10]){
 const shape=airShape(R,assets.spear,scale,[0,0,1]),q=V.rotation([30,70,-15]),axis=R.rotate(q,[0,0,1]),velocity=[100,-30,60],omega=[14,-30,18],inverse=v=>R.mul(v,10/(scale[2]**2));
 const {force,torque}=airForces(R,shape,{strength,pressure,damping},q,velocity,omega,inverse,1/120);
 assert([...force,...torque].every(Number.isFinite));assert(R.dot(force,velocity)+R.dot(torque,omega)<=1e-8,'Air must dissipate mechanical energy');
 assert(Math.abs(R.dot(torque,axis))<1e-8,'No imposed longitudinal spin torque');
 if(strength===0)assert.equal(R.length(force)+R.length(torque),0);forceCases++;
}
const sim=await createProjectileSystem(assets,R,V),cases=[];
try{
 for(const raw of data.clips)for(const kind of ['spear','sword','bomb']){
  const clip=C.decode(raw,data.parents),controls=V.config(saved.vanilla[raw.id]||{},clip.duration*60),hand=data.names.indexOf('hand_l'),arm=data.names.indexOf('lowerarm_l');
  const sample=t=>{const pose=V.pose(V.pose(C.sample(clip,t,data.parents),data.parents,arm,controls.forearmKeys,t*60,true),data.parents,hand,controls.keys,t*60);return {...pose,points:pose.points.map(p=>R.add(p,[0,40,0]))};};
  const o={key:raw.id,kind,scale:saved.weaponScales[raw.id][kind],grip:saved.grips[raw.id][kind],release:raw.id==='big-throw'?34.25/60:15.75/60,sample,hand,duration:clip.duration,target:[1000,1000,1000],radius:.16,controls};
  controls.aero.enabled=false;
  const original=structuredClone(sim.preview(o)),before=structuredClone(controls),aligned=V.alignVelocity(original.authoredVelocity,sample(o.release).q[0],original.axis,controls.velocityRotation);
  controls.velocityRotation=aligned;const seed=structuredClone(sim.preview(o));
  assert(angle(seed.v,seed.axis)<1e-5);assert(Math.abs(R.length(seed.v)-R.length(original.v))<1e-8);assert.equal(seed.twist,original.twist);
  assert.deepEqual({...controls,velocityRotation:before.velocityRotation},before);
  const off=sim.at(o.release+1,o),offAngle=angle(R.rotate(off.q,assets[kind].longAxis||[0,0,1]),off.v);assert.equal(sim.diagnostics.airSteps,0);
  controls.aero.enabled=true;sim.at(o.release-.001,o);assert.equal(sim.diagnostics.airSteps,0);
  assert.deepEqual(sim.preview(o),seed,'Air must not alter release pose or launch velocity');
  const on=sim.at(o.release+1,o),onAngle=angle(R.rotate(on.q,assets[kind].longAxis||[0,0,1]),on.v),steps=sim.diagnostics.airSteps;
  if(kind==='bomb'){assert.deepEqual(on,off);assert.equal(steps,0);}else {assert(steps>0);assert.notDeepEqual(on.q,off.q);}
  assert([...on.p,...on.q,...on.v,...on.omega].every(Number.isFinite));
  sim.at(o.release+.2,o);assert.deepEqual(sim.at(o.release+1,o),on);assert.equal(sim.diagnostics.airSteps,steps,'Cached seeks must not reapply air');
  controls.aero.enabled=false;assert.deepEqual(sim.at(o.release+1,o),off,'Off must restore exact original simulation');
  // Actual floor/target replay and extreme strength remain finite at each scale.
  const groundSample=t=>{const p=sample(t);return {...p,points:p.points.map(v=>R.sub(v,[0,40,0]))};};
  for(const scale of [[.1,.1,.1],o.scale]){
   controls.aero={enabled:true,strength:10,pressure:.5,damping:10};
   const contactOptions={...o,scale,sample:groundSample,target:saved.target,radius:saved.radius};
   for(let frame=0;frame<=180;frame+=3){const p=sim.at(o.release+frame/60,contactOptions);assert([...p.p,...p.q,...p.v,...p.omega].every(Number.isFinite));}
  }
  cases.push({clip:raw.id,kind,offAngle,onAngle,airSteps:steps});
 }
 // Reproduce the user's actual "stays flat" F54 scene, without snapping its
 // existing launch velocity or changing pressure/damping/weapon settings.
 const fixture=read('./fixtures/flat-spear-flight.json'),s=C.sanitize(fixture.settings),clip=C.decode(data.clips.find(c=>c.id===s.clip),data.parents),c=s.vanilla[clip.id],hand=data.names.indexOf('hand_l'),arm=data.names.indexOf('lowerarm_l');
 const sample=t=>V.pose(V.pose(C.sample(clip,t,data.parents),data.parents,arm,c.forearmKeys,t*60,true),data.parents,hand,c.keys,t*60);
 const o={key:clip.id,kind:'spear',scale:s.weaponScales[clip.id].spear,grip:s.grips[clip.id].spear,release:s.releases[clip.id],sample,hand,duration:clip.duration,target:s.target,radius:s.radius,controls:c};
 const seed=structuredClone(sim.preview(o)),p=sim.at(54/60,o),axis=R.rotate(p.q,[0,0,1]),pitch=Math.asin(axis[1])*180/Math.PI,error=angle(axis,p.v);
 assert(pitch<-8&&pitch>-35,'Default short-flight response must visibly tip the nose down');assert(error<16,'Nose should approach the velocity direction');
 c.aero.enabled=false;assert.deepEqual(sim.preview(o),seed);const off=sim.at(54/60,o),offPitch=Math.asin(R.rotate(off.q,[0,0,1])[1])*180/Math.PI;assert(Math.abs(offPitch)<1);
 const latest=read('./fixtures/stronger-spear-flight.json'),ls=C.sanitize(latest.settings),lc=ls.vanilla[clip.id];
 const latestSample=t=>V.pose(V.pose(C.sample(clip,t,data.parents),data.parents,arm,lc.forearmKeys,t*60,true),data.parents,hand,lc.keys,t*60);
 const latestOptions={...o,controls:lc,sample:latestSample,scale:ls.weaponScales[clip.id].spear,grip:ls.grips[clip.id].spear,target:ls.target,radius:ls.radius,release:ls.releases[clip.id]};
 const latestPose=sim.at(62/60,latestOptions),latestAxis=R.rotate(latestPose.q,[0,0,1]),latestError=angle(latestAxis,latestPose.v),latestPitch=Math.asin(latestAxis[1])*180/Math.PI;
 assert(latestError<6);assert(latestPitch<-12);
 for(const kind of ['sword','spear'])for(const twist of [0,6,-6,12,-12]){
  lc.twist=twist;const opt={...latestOptions,kind,grip:ls.grips[clip.id][kind],scale:ls.weaponScales[clip.id][kind]},seed=sim.preview(opt),initial=sim.at(opt.release,opt),expected=R.mul(seed.axis,twist*60*Math.PI/180);
  assert(R.length(R.sub(seed.omega,expected))<1e-8);assert(R.length(R.sub(initial.omega,expected))<1e-5);assert(R.length(R.cross(seed.omega,seed.axis))<1e-8);
  const flight=sim.at(opt.release+20/60,opt);assert([...flight.q,...flight.omega].every(Number.isFinite));
 }
 const receipt={success:true,alignCases,forceCases,cases,manualTwistCases:10,strongerFlight:{frame:62,error:latestError,pitch:latestPitch},flatFlightRegression:{frame:54,pitch,error,offPitch}};fs.writeFileSync(new URL('../../Saved/ThrowLab/aerodynamics-verification.json',import.meta.url),JSON.stringify(receipt,null,2));console.log(JSON.stringify(receipt,null,2));
}finally{sim.dispose();}
