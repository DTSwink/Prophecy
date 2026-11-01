// Direction authoring is independent of the animated release origin and pose.
import fs from 'node:fs';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),T=require('./throw-attack.js'),A=require('./attack-aim.js'),H=require('./attack-inertia.js'),PA=require('./physical-aim.js');
const read=p=>JSON.parse(fs.readFileSync(new URL(p,import.meta.url))),m=read('data/manifest.json'),{names,parents}=m,reference=C.poseFromShared(m),pelvis=names.indexOf('pelvis'),project=H.createProjection(names,parents,reference),distance=(a,b)=>R.length(R.sub(a,b));T.load(read('data/throws.json'));
const jumpStart=.4,airStart=.9,offset=[5,2,-3],drift=[2,.3,-1],base=t=>{const dt=t-jumpStart,q=R.qexp([0,.5*dt,0]),pivot=reference.points[pelvis],p={...reference,points:reference.points.map(v=>R.add(R.add(pivot,R.rotate(q,R.sub(v,pivot))),R.add(offset,R.mul(drift,dt)))),q:reference.q.map(v=>R.qm(q,v))};return {pose:p};};
const segment={sample:base,jumpStart,airStart,abortTime:Infinity},settings=C.sanitize({kickToArmed:true,motionCompensation:true,distributePelvisTurn:true}),rows=[];let checks=0;
const near=(a,b,message,tol=1e-8)=>{assert(distance(a,b)<tol,message+': '+distance(a,b));checks++;};
for(const name of ['big-throw','small-throw']){
 const event={id:'direction',attack:name,attackDelay:.3,throwCharge:37},track=T.create(event,segment,null,names,parents,settings,reference),raw=t=>project(track.sample(t).pose),launchAt=(p,map=x=>x)=>{const at=t=>map(raw(t),t);return track.launchAt(p,track.releaseVelocity(at),track.projectileAngularVelocity(at));},plan=A.create({track,names,parents,reference,sampleHit:raw,launchAt,project});
 const anchor=raw(jumpStart).points[pelvis],neutral=launchAt(raw(track.releaseTime)),ray=name==='big-throw'?neutral.axis:[neutral.v[0],0,neutral.v[2]],direction=R.unit(ray),target=R.add(anchor,R.mul(direction,4));
 near(plan.aimReferenceOrigin,anchor,'origin uses jump frame zero');assert(distance(plan.aimReferenceOrigin,raw(track.releaseTime).points[pelvis])>.5,'carrier moves substantially before release');checks++;
 if(name==='small-throw'){
  near(plan.throwDirectionFor(target),direction,'small throw retains frozen azimuth');
  const far=R.add(anchor,R.mul(direction,40));near(plan.throwDirectionFor(far),direction,'small range along same ray does not alter direction');
  const at=t=>project(plan.apply(raw(t),t,target)),packet=track.launchAt(at(track.releaseTime),track.releaseVelocity(at));near(R.unit([packet.v[0],0,packet.v[2]]),direction,'small launch follows frozen azimuth',1e-5);
 }else {assert.equal(plan.throwDirectionFor(target),null,'default spear now fits a point');checks++;}
 // An explicitly game-authored world direction still wins over target position.
 const author=R.mul(R.rotate(R.qexp([0,.25,0]),direction),7),wanted=R.unit(author),authored=T.create({...event,throwDirection:author},segment,null,names,parents,settings,reference),source=t=>project(authored.sample(t).pose),launch=(p,map=x=>x)=>authored.launchAt(p,authored.releaseVelocity(t=>map(source(t),t))),fixed=A.create({track:authored,names,parents,reference,sampleHit:source,launchAt:launch,project});author[0]+=100;
 near(fixed.throwDirectionFor([900,-100,700]),wanted,'explicit direction is normalized and copied');assert.equal(fixed.solution(target),fixed.solution([-500,200,-800]),'target changes cannot re-aim an authored vector');checks++;
 const at=t=>project(fixed.apply(source(t),t,target)),packet=authored.launchAt(at(authored.releaseTime),authored.releaseVelocity(at));near(name==='big-throw'?R.unit(packet.axis):R.unit([packet.v[0],0,packet.v[2]]),wanted,'explicit release follows the authored ray',1e-5);
 for(let k=0;k<=40;k++){
  const time=track.start+(track.returnEnd-track.start)*k/40,before=source(time),after=at(time),a=R.localize(before.points,before.q,parents),b=R.localize(after.points,after.q,parents);
  near(R.qlog(R.qm(after.q[pelvis],R.qinv(before.q[pelvis]))),[0,0,0],'authored aim does not tilt pelvis');
  for(let i=0;i<names.length;i++)if(/^(clavicle|upperarm|lowerarm|hand)_/.test(names[i]))near(R.qlog(R.qm(a.q[i],R.qinv(b.q[i]))),[0,0,0],'authored steering preserves relative arms');
 }
 const shifted=t=>{const p=source(t);return {...p,points:p.points.map(v=>R.add(v,[Math.max(0,t-jumpStart)*30,0,0]))};},other=A.create({track:authored,names,parents,reference,sampleHit:shifted,launchAt:(p,map=x=>x)=>authored.launchAt(p,authored.releaseVelocity(t=>map(shifted(t),t))),project});near(other.throwDirectionFor(target),wanted,'future release displacement cannot change an authored ray');
 rows.push({name,anchor,direction,releaseTime:track.releaseTime});
}
for(const invalid of [null,[0,0,0],[1,2],[NaN,1,0],[Infinity,0,0]]){assert.equal(C.sanitizeJump({throwDirection:invalid}).throwDirection,null);checks++;}
const worldDirection=[.2,.3,1],packed=C.sanitize({jumpEvents:[{time:0,attack:'big-throw',throwDirection:worldDirection}]});near(packed.jumpEvents[0].throwDirection,R.unit(worldDirection),'settings round trip retains authored direction');
// Physical prediction must freeze the unpredicted frame-zero world position.
const track=T.create({attack:'big-throw',attackDelay:.2,throwDirection:[0,0,1]},{sample:()=>({pose:reference}),jumpStart:0,airStart:0,abortTime:Infinity},null,names,parents,settings,reference),source=t=>({pose:project(track.sample(t).pose)}),worldPose=(p,t)=>({...p,points:p.points.map(v=>R.add(v,[3+t,2,-4]))}),physical=PA.create(source,{start:0,settings,names,parents,reference,gravity:0,seedSource:()=>({pose:reference})},{track,settings:{...settings,target:[20,10,30]},project,worldPose});
near(physical.plan.aimReferenceOrigin,R.add(reference.points[pelvis],[3,2,-4]),'physical prediction uses frame-zero world coordinates');near(physical.plan.throwDirectionFor([99,99,99]),[0,0,1],'physical correction cannot rotate the authored direction');
fs.mkdirSync(new URL('../../Saved/BodyflipLab/ThrowDirection/',import.meta.url),{recursive:true});fs.writeFileSync(new URL('../../Saved/BodyflipLab/ThrowDirection/results.json',import.meta.url),JSON.stringify({passed:true,checks,rows},null,2));console.log(JSON.stringify({passed:true,checks,rows},null,2));
