import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {createProjectileSystem} from './projectile.js';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js');
const dir=path.dirname(fileURLToPath(import.meta.url)),data=JSON.parse(fs.readFileSync(path.join(dir,'data/clips.json'))),assets=JSON.parse(fs.readFileSync(path.join(dir,'data/objects.json')));
assert.deepEqual(data.clips.map(c=>c.id),['big-throw','small-throw']);
const sim=await createProjectileSystem(assets,R),receipt={checks:[],cases:[]},h=1/120;
const distance=(a,b)=>R.length(R.sub(a,b));
function attachment(pose,hand,kind){const b=assets[kind].bind||{};return {p:R.add(pose.points[hand],R.rotate(pose.q[hand],b.position||[0,0,0])),q:R.qm(pose.q[hand],b.rotation||[0,0,0,1])};}
try{
 for(const raw of data.clips)for(const kind of ['sword','bomb']){
  const clip=C.decode(raw,data.parents),hand=data.names.indexOf('hand_l'),release=Math.round(clip.duration*.5*60)/60;
  const o={key:raw.id,kind,release,sample:t=>C.sample(clip,t,data.parents),hand,duration:clip.duration,target:[0,1.5,3],radius:.16};
  const before=sim.at(release-h,o),pose=attachment(o.sample(release-h),hand,kind);assert.equal(before.phase,'held');assert(distance(before.p,pose.p)<1e-10);assert.equal(sim.diagnostics.steps,0);
  const exact=sim.at(release,o),p=attachment(o.sample(release),hand,kind);assert(distance(exact.p,p.p)<1e-6);assert(Math.abs(R.dot(exact.q,p.q))>1-1e-6);
  const seed=sim.diagnostics.seed,previous=attachment(o.sample(release-h),hand,kind),expected=R.mul(R.sub(R.add(p.p,R.rotate(p.q,seed.comOffset)),R.add(previous.p,R.rotate(previous.q,seed.comOffset))),1/h);
  assert(distance(seed.v,expected)<1e-10);
  const incoming=sim.at(release+.2,o),end=sim.at(clip.duration+3,o),steps=sim.diagnostics.steps;
  assert([...end.p,...end.q,...end.v].every(Number.isFinite));
  const lowest=Math.min(...assets[kind].collision.map(v=>R.add(end.p,R.rotate(end.q,v))[1]));assert(lowest>-.003,'Floor penetration '+kind+' '+lowest);
  sim.at(release-h,o);assert.deepEqual(sim.at(release+.2,o),incoming);assert.deepEqual(sim.at(clip.duration+3,o),end);assert.equal(sim.diagnostics.steps,steps);
  receipt.cases.push({clip:raw.id,kind,release,velocity:seed.v,angularVelocity:seed.omega,lowestHullMetres:lowest,steps});
 }
 receipt.checks.push('Both objects follow left hand on both clips, release without a pose jump, inherit COM/angular velocity, and reverse-seek exactly');
 const staticPose={points:[[0,2,0]],q:[[0,0,0,1]]},drop={key:'gravity',kind:'bomb',release:0,sample:()=>staticPose,hand:0,duration:1,target:[10,2,0],radius:.16};
 const falling=sim.at(.2,drop),expectedY=2-9.81*.5*(.2*.2+.2*h);assert(Math.abs(falling.p[1]-expectedY)<2e-6);assert(Math.abs(falling.v[1]+9.81*.2)<2e-6);
 sim.at(5,drop);const asleep=sim.at(10,drop),steps=sim.diagnostics.steps;assert.equal(asleep.phase,'resting');sim.at(11,drop);assert.equal(sim.diagnostics.steps,steps);receipt.checks.push('Gravity matches fixed-step integration; sleeping objects stop stepping');
 const moving=t=>({points:[[-2+5*t,2,0]],q:[[0,0,0,1]]}),hit={key:'collision',kind:'bomb',release:.1,sample:moving,hand:0,duration:1,target:[0,1.8,0],radius:.3};
 const struck=sim.at(.5,hit),clear=sim.at(.5,{...hit,target:[10,1.8,0]});assert(struck.v[0]<1&&clear.v[0]>4.9);assert(clear.p[0]-struck.p[0]>.4);receipt.targetCollision={hitVelocity:struck.v,clearVelocity:clear.v};receipt.checks.push('Static target physically deflects the bomb; changing target invalidates the replay');
 // User's sword-impact fixture: release F33, target hit near F40. No live state writes.
 const swordClip=C.decode(data.clips[0],data.parents),swordHit={key:'sword-impact-F33',kind:'sword',release:33/60,sample:t=>C.sample(swordClip,t,data.parents),hand:data.names.indexOf('hand_l'),duration:swordClip.duration,target:[.050144706859098005,1.0499841374748848,2.863185181308968],radius:.16};
 const postHit=sim.at(42/60,swordHit),later=sim.at(54/60,swordHit),seed=sim.diagnostics.seed;
 assert.equal(seed.gyroscopic,true);assert.equal(seed.allowedDOFs,63);
 const axisChange=Math.acos(Math.max(-1,Math.min(1,R.dot(R.unit(postHit.omega),R.unit(later.omega)))))*180/Math.PI;
 assert(axisChange>20,'Sword rotation axis should evolve after an off-axis hit');
 sim.at(33/60,swordHit);assert.deepEqual(sim.at(54/60,swordHit),later);
 const landed=sim.at(swordClip.duration+3,swordHit),lowest=Math.min(...assets.sword.collision.map(v=>R.add(landed.p,R.rotate(landed.q,v))[1]));assert(lowest>-.003);assert([...landed.p,...landed.q,...landed.v,...landed.omega].every(Number.isFinite));
 const unobstructed=sim.at(42/60,{...swordHit,target:[100,100,100]});assert(distance(postHit.v,unobstructed.v)>1);
 receipt.swordImpact={releaseFrame:33,axisChangeDegreesF42toF54:axisChange,lowestHullMetres:lowest,gyroscopic:seed.gyroscopic,allowedDOFs:seed.allowedDOFs};receipt.checks.push('F33 sword target impact tumbles with all axes free, lands and reverse-replays deterministically');
 receipt.success=true;const out=path.resolve(dir,'../../Saved/ThrowLab/projectile-verification.json');fs.writeFileSync(out,JSON.stringify(receipt,null,2));console.log(JSON.stringify(receipt,null,2));
}finally{sim.dispose();}
