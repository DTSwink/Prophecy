import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {createProjectileSystem} from './projectile.js';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),V=require('./vanilla.js');
const data=JSON.parse(fs.readFileSync(new URL('./data/clips.json',import.meta.url))),assets=JSON.parse(fs.readFileSync(new URL('./data/objects.json',import.meta.url)));
const near=(a,b,tolerance=1e-6)=>assert(R.length(R.sub(a,b))<tolerance,JSON.stringify({a,b}));
assert.equal(assets.spear.hulls.length,9);assert.equal(assets.spear.triangles.length/3,21112);
// Reframing the sword must preserve the original visible attachment exactly.
const original=JSON.parse(fs.readFileSync(new URL('../BodyflipLab/data/sword.json',import.meta.url))),bytes=Buffer.from(original.vertices_b64,'base64'),matrix=original.local_to_hand;
let defaultSwordError=0;
for(let i=0;i<assets.sword.vertices.length;i++){
 const v=[0,1,2].map(k=>bytes.readFloatLE(i*12+k*4)),expected=[0,1,2].map(k=>(matrix[k]*v[0]+matrix[4+k]*v[1]+matrix[8+k]*v[2]+matrix[12+k])*(k===2?1:-1));
 const actual=R.add(assets.sword.bind.position,R.rotate(assets.sword.bind.rotation,assets.sword.vertices[i]));defaultSwordError=Math.max(defaultSwordError,R.length(R.sub(actual,expected)));
}
assert(defaultSwordError<1e-8,'Sword default geometry changed');
const zs=assets.spear.vertices.map(v=>v[2]);assert(Math.abs(Math.max(...zs)-Math.min(...zs)-2.2)<1e-6);
const sim=await createProjectileSystem(assets,R,V),cases=[],hand=data.names.indexOf('hand_l');
try{
 for(const raw of data.clips)for(const kind of ['sword','spear']){
  const clip=C.decode(raw,data.parents),sample=t=>C.sample(clip,t,data.parents),release=(raw.id==='big-throw'?33.25:15.75)/60;
  const grip={position:[.08,-.035,.13],rotation:[35,-27,18]},controls=V.config({twist:2.5}),o={key:raw.id,kind,grip,controls,release,sample,hand,duration:clip.duration,target:[20,20,20],radius:.16};
  const bind=assets[kind].bind||{position:[0,0,0],rotation:[0,0,0,1]};
  let relative;
  for(const frame of [0,3.25,8.5,release*60-.001]){
   const pose=sample(frame/60),held=sim.at(frame/60,o),localP=R.rotate(R.qinv(pose.q[hand]),R.sub(held.p,pose.points[hand])),localQ=R.qm(R.qinv(pose.q[hand]),held.q);
   near(localP,R.add(bind.position,R.rotate(bind.rotation,grip.position)));
   assert(Math.abs(R.dot(localQ,R.qm(bind.rotation,V.rotation(grip.rotation))))>1-1e-10);
   if(relative)near(localP,relative);relative=localP;
  }
  const seed=sim.preview(o),held=sim.held({...o,pose:sample(release)}),exact=sim.at(release,o);
  near(exact.p,held.p);assert(Math.abs(R.dot(exact.q,held.q))>1-1e-7);
  const earlier=sim.held({...o,pose:sample(release-1/120)}),com=t=>R.add(t.p,R.rotate(t.q,seed.comOffset));
  near(seed.v,R.mul(R.sub(com(held),com(earlier)),120));near(R.cross(seed.omega,seed.axis),[0,0,0]);
  if(kind==='spear')near(seed.axis,R.rotate(held.q,[0,0,1]));
  const flight=sim.at(release+.15,o);assert([...flight.p,...flight.q,...flight.omega].every(Number.isFinite));sim.at(0,o);assert.deepEqual(sim.at(release+.15,o),flight);
  grip.position[0]+=.04;const changed=sim.preview(o);assert(R.length(R.sub(changed.p,seed.p))>.039);assert(R.length(R.sub(changed.v,seed.v))>.001);
  const end=sim.at(clip.duration+3,o);assert([...end.p,...end.q].every(Number.isFinite));
  const minHeight=Math.min(...assets[kind].collision.map(v=>R.add(end.p,R.rotate(end.q,v))[1]));assert(minHeight>-.015,'Final collision geometry must stay above floor');
  cases.push({clip:raw.id,kind,minHeight,phase:end.phase});
 }
 // A falling spear must contact the target using its compound UCX shape.
 const staticSample=()=>({points:[[0,3,0]],q:[[0,0,0,1]]});
 const hitOptions={key:'drop',kind:'spear',hand:0,release:.1,duration:1,sample:staticSample,grip:{position:[0,0,0],rotation:[0,0,0]},controls:V.config({twist:0}),target:[.07126077,1.5,-.00062174],radius:.3};
 const hit=sim.at(.8,hitOptions),miss=sim.at(.8,{...hitOptions,target:[10,1.5,10]});assert(R.length(R.sub(hit.p,miss.p))>.1,'Compound spear must collide with target');

 assert.deepEqual(C.sanitize({weaponScales:{"big-throw":{spear:.6}}}).weaponScales["big-throw"].spear,[.6,.6,.6]);
 for(const scale of [.1,.6,1,2,[.6,.85,.45],[1.5,.3,.7]]){
  const sizes=Array.isArray(scale)?scale:[scale,scale,scale];
  const o={...hitOptions,scale,target:[20,20,20]},seed=sim.preview(o),base=sim.preview({...o,scale:1});near(seed.p,base.p);near(seed.comOffset,base.comOffset.map((v,i)=>v*sizes[i]));
  const start=sim.at(o.release,o);near(start.p,seed.p);const end=sim.at(5,o);assert([...end.p,...end.q].every(Number.isFinite));
  const lowest=Math.min(...assets.spear.collision.map(v=>R.add(end.p,R.rotate(end.q,v.map((n,i)=>n*sizes[i])))[1]));assert(lowest>-.02&&lowest<.025,'Scaled collision must rest at visible floor: '+lowest);sim.at(0,o);assert.deepEqual(sim.at(5,o),end);
 }
 const receipt={success:true,defaultSwordError,cases,checks:['Full 2.2m FBX mesh, nine UCX hulls','Weapon-local sword basis preserves its original default mesh pose','Constant local attachment on both throws and both weapons','Grip-aware release continuity, COM velocity, cache invalidation and exact replay','Spear shaft-only twist, compound target/floor contacts and finite simulation','Scalar migration, uniform and independent XYZ scaled COM, continuous release, collision floor alignment and replay']};
 fs.writeFileSync(new URL('../../Saved/ThrowLab/grip-verification.json',import.meta.url),JSON.stringify(receipt,null,2));console.log(JSON.stringify(receipt,null,2));
}finally{sim.dispose();}
