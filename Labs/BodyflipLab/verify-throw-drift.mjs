// Release inherits the complete held trajectory, including translation and spin.
import fs from 'node:fs';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),T=require('./throw-attack.js'),A=require('./attack-aim.js');
const read=p=>JSON.parse(fs.readFileSync(new URL(p,import.meta.url))),m=read('data/manifest.json'),{names,parents}=m,reference=C.poseFromShared(m);T.load(read('data/throws.json'));
const distance=(a,b)=>R.length(R.sub(a,b)),reports=[];let checks=0;const near=(a,b,message,tol=1e-7)=>{assert(distance(a,b)<tol,message+': '+distance(a,b));checks++;};
for(const name of ['big-throw','small-throw'])for(const charge of name==='big-throw'?[100]:[10,37,100]){
 const settings=C.sanitize({distributePelvisTurn:true,kickToArmed:true,motionCompensation:false}),event={attack:name,throwCharge:charge},segment={sample:()=>({pose:reference}),airStart:0,jumpStart:0,abortTime:Infinity},track=T.create(event,segment,null,names,parents,settings,reference),at=t=>track.sample(t).pose,release=sample=>track.launchAt(sample(track.releaseTime),track.releaseVelocity(sample),track.releaseAngularVelocity(sample)),base=release(at);
 for(const drift of [[3,2,-1],[0,11,0],[-5,-2,7]]){
  const offset=[2,-1,4],moved=t=>{const p=at(t),d=R.add(offset,R.mul(drift,t));return {...p,points:p.points.map(v=>R.add(v,d))};},p=release(moved);
  near(p.v,R.add(base.v,drift),'moving body adds exactly its velocity');near(p.omega,base.omega,'translation cannot add spin');near(p.p,R.add(base.p,R.add(offset,R.mul(drift,track.releaseTime))),'release location moves with hand');
 }
 const turn=R.qexp([.7,-1.2,.4]),turned=t=>{const p=at(t);return {...p,points:p.points.map(v=>R.rotate(turn,v)),q:p.q.map(q=>R.qm(turn,q))};},rotated=release(turned);
 near(rotated.v,R.rotate(turn,base.v),'rotation covariance');near(rotated.omega,R.rotate(turn,base.omega),'angular covariance');
 // A deliberately prescribed moving held object has an analytic COM tangent.
 const held=at(track.releaseTime),center=A.launchCenter(base),omega=[1.2,-.7,.3],drift=[2,3,-1],sample=t=>{const d=t-track.releaseTime,q=R.qexp(R.mul(omega,d));return {...held,points:held.points.map(v=>R.add(R.rotate(q,v),R.mul(drift,d))),q:held.q.map(v=>R.qm(q,v))};},p=release(sample);
 near(p.v,R.add(drift,R.cross(omega,center)),'analytic rigid-body point velocity',1e-5);near(p.omega,omega,'analytic angular velocity');
 const faster=T.create({...event,throwSpeed:2},segment,null,names,parents,settings,reference),fastAt=t=>faster.sample(t).pose;
 near(faster.releaseVelocity(fastAt),R.mul(base.v,2),'speed control speeds up the motion itself',.02);
 assert.equal(T.create({...event,throwSpeed:0},segment,null,names,parents,settings,reference),null,'zero playback speed cannot launch');checks++;
 reports.push({name,charge,speed:R.length(base.v),doubleSpeed:R.length(faster.releaseVelocity(fastAt))});
}
console.log(JSON.stringify({passed:true,checks,reports},null,2));
