import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {createProjectileSystem} from './projectile.js';
const require=createRequire(import.meta.url),R=require('./recovery.js'),C=require('./core.js'),V=require('./vanilla.js'),A=require('./attack.js');
const read=p=>JSON.parse(fs.readFileSync(new URL(p,import.meta.url))),data=read('./data/clips.json'),assets=read('./data/objects.json');
const rig=A.rig(data.names,data.parents),hand=data.names.indexOf('hand_l'),forearm=data.names.indexOf('lowerarm_l');
const near=(a,b,tol=1e-8)=>assert(R.length(R.sub(a,b))<tol,JSON.stringify({a,b,tol}));
const sameQ=(a,b,tol=1e-9)=>assert(1-Math.abs(R.dot(a,b))<tol,JSON.stringify({a,b}));
const close=(a,b,tol=1e-8)=>assert(Math.abs(a-b)<tol,JSON.stringify({a,b,tol}));
const clip=C.decode(data.clips.find(c=>c.id==='small-throw'),data.parents),armed=18,releaseFrame=34.25,end=clip.duration*60,referenceRelease=releaseFrame/60;
assert(end>releaseFrame);
const raw=t=>C.sample(clip,t,data.parents),timing=p=>A.chargeTiming(armed,releaseFrame,p),smooth=u=>{u=Math.max(0,Math.min(1,u));return u*u*u*(10+u*(-15+6*u));};
const curve=A.chargeCurve(f=>raw(f/60),armed,releaseFrame,end,rig),arcEnd=curve.peak;
const sourceFrame=(p,elapsed)=>p===1?armed+elapsed:A.chargeFrame(curve,p,elapsed);
const bodyPlans=new WeakMap();
function bodyPlan(full,p,returnFrame=releaseFrame){
 let plans=bodyPlans.get(full);if(!plans){plans=new Map();bodyPlans.set(full,plans);}
 const key=p+':'+returnFrame;
 if(!plans.has(key))plans.set(key,A.prepareBody({sample:f=>full(f/60),rig,amount:p,trigger:armed*p,returnFrame,end}));
 return plans.get(key);
}
const carryPlans=new WeakMap();
function reducedRaw(t,p,full=raw,blend=0,carry=true){
 const source=full(t),frame=Math.min(t,clip.duration)*60,when=timing(p);
 if(p===1||frame<=when.trigger)return source;
 const speed=A.chargeSpeed(curve,p,blend),finish=when.trigger+(arcEnd-armed)/speed.multiplier,recover=smooth((frame-finish)/(end-finish));
 const elapsed=Math.max(0,Math.min(arcEnd-armed,(frame-when.trigger)*speed.multiplier)),entry=elapsed/Math.max(1e-9,Math.min(4,when.forward));
 const pose=A.partialPose({source,charged:full(when.trigger/60),action:full(sourceFrame(p,elapsed)/60),rig,amount:p,recover,entry,ending:full(clip.duration),anchor:frame>finish?full(finish/60):source,body:bodyPlan(full,p),frame,anchorFrame:Math.min(frame,finish)});
 if(!carry||p===0)return pose;
 let plans=carryPlans.get(full);if(!plans){plans=new Map();carryPlans.set(full,plans);}
 const key=p+':'+blend;
 if(!plans.has(key)){const base=f=>reducedRaw(f/60,p,full,blend,false);plans.set(key,{
  entry:A.prepareCarry({incoming:f=>full(f/60),outgoing:base,rig,frame:when.trigger,duration:Math.min(4,when.forward)/speed.multiplier}),
  exit:A.prepareCarry({incoming:base,outgoing:base,rig,frame:finish,duration:Math.min(8,end-finish)})});}
 return A.carryPose(pose,frame<finish?plans.get(key).entry:plans.get(key).exit,frame);
}
let prefixSamples=0,poseSamples=0,launchCases=0,maxCutoffPositionGap=0;
for(const p of [0,.05,.18,.25,.5,.75,.99,1]){
 const when=timing(p);close(when.trigger,p*armed);close(when.forward,releaseFrame-armed);close(when.release,when.trigger+when.forward);
 if(p<1)assert(when.release<releaseFrame,'Early trigger release must release the object earlier');
}
assert.deepEqual(timing(1),{trigger:armed,release:releaseFrame,forward:releaseFrame-armed});
assert.equal(timing(.5).trigger,9);assert.equal(timing(.5).release,25.25);
for(const half of [false,true])for(const aim of [false,true]){
 const plan=A.prepare({rig,initial:raw(0),armedPose:raw(armed/60),releasePose:raw(referenceRelease),velocity:[1,2,5],target:[4,3,5],half,aim,armed});
 const full=t=>plan.apply(raw(t),Math.min(t,clip.duration)*60);
 for(const p of [0,.05,.18,.25,.5,.75,.99,1]){
  const when=timing(p);
  for(let i=0;i<=30;i++){
   const frame=when.trigger*i/30;
   assert.deepEqual(reducedRaw(frame/60,p,full),full(frame/60),'Normal-speed charge prefix, including Half/Aim');prefixSamples++;
  }
  const charged=full(when.trigger/60),at=reducedRaw(when.trigger/60,p,full),after=reducedRaw((when.trigger+1e-7)/60,p,full);
  assert.deepEqual(at,charged);
  for(let j=0;j<data.names.length;j++){
   maxCutoffPositionGap=Math.max(maxCutoffPositionGap,R.length(R.sub(after.points[j],charged.points[j])));
   near(after.points[j],charged.points[j],2e-6);sameQ(after.q[j],charged.q[j],1e-9);
  }
  if(p<1){
   const fullArmed=full(armed/60),distance=R.length(R.sub(charged.points[hand],fullArmed.points[hand]));
   if(distance>.001)assert(R.length(R.sub(after.points[hand],fullArmed.points[hand]))>distance*.99,'Cutoff must not jump toward full Armed');
  }
  const startLocal=R.localize(charged.points,charged.q,data.parents),initialLocal=R.localize(full(0).points,full(0).q,data.parents);
  for(let i=0;i<=30;i++){
   const frame=when.trigger+when.forward*i/30,source=full(frame/60),forward=full(sourceFrame(p,frame-when.trigger)/60),pose=reducedRaw(frame/60,p,full);
   const local=R.localize(pose.points,pose.q,data.parents),from=R.localize(forward.points,forward.q,data.parents),sourceLocal=R.localize(source.points,source.q,data.parents);
   assert([...pose.points.flat(),...pose.q.flat()].every(Number.isFinite));
   for(let j=0;j<data.names.length;j++){
    if(!rig.upper[j]){
     if(half||p===1){near(pose.points[j],source.points[j]);sameQ(pose.q[j],source.q[j]);}
    }
    else{
     if(p===0)sameQ(local.q[j],startLocal.q[j]);
     else if(rig.throwArm.has(j)){
      if(frame-when.trigger>=Math.min(4,when.forward)){sameQ(local.q[j],from.q[j]);sameQ(pose.q[j],forward.q[j]);}
     }
     close(R.length(local.p[j]),R.length((p===0?initialLocal:sourceLocal).p[j]),1e-8);
    }
   }
   poseSamples++;
  }
  const last=reducedRaw(clip.duration,p,full),lastLocal=R.localize(last.points,last.q,data.parents),originalLast=full(clip.duration),originalLastLocal=R.localize(originalLast.points,originalLast.q,data.parents);for(let j=0;j<data.names.length;j++)if(j===rig.shoulder||rig.throwArm.has(j))sameQ(lastLocal.q[j],originalLastLocal.q[j]);
 }
 for(let frame=0;frame<=end;frame+=.5)assert.deepEqual(reducedRaw(frame/60,1,full),full(frame/60),'100% restores the original full motion');
}
// Reached charge motion must be preserved; only the remaining body motion is
// reduced. Compare total forward-cycle effort, not the obsolete p*neutral pose.
const effortChecks=[],localExcursionOvershoot=[],initial=raw(0),initialLocal=R.localize(initial.points,initial.q,data.parents),fullRelease=raw(referenceRelease),fullLocal=R.localize(fullRelease.points,fullRelease.q,data.parents);
for(const p of [.05,.25,.43,.5,.75,1]){
 let peakRadians=0,peakFrame=0,peakBones=[];
 for(let f=0;f<=releaseFrame;f+=.25){
  const pose=reducedRaw(f/60,p),local=R.localize(pose.points,pose.q,data.parents);
  const bones=[...rig.spines,12,13,14,17].map(j=>({bone:data.names[j],radians:R.length(R.qlog(R.qm(R.qinv(initialLocal.q[j]),local.q[j])))})),total=bones.reduce((sum,bone)=>sum+bone.radians,0);
  if(total>peakRadians){peakRadians=total;peakFrame=f;peakBones=bones;}
 }
 if(effortChecks.length&&peakRadians<=effortChecks.at(-1).peakRadians)localExcursionOvershoot.push({percent:p*100,peakRadians,previous:effortChecks.at(-1),note:'Incoming support-arm angular velocity is retained briefly; local-angle peaks can exceed full charge without larger world body motion. No joint clamp is applied.'});
 effortChecks.push({percent:p*100,peakRadians,peakFrame,peakBones});
}
// Elbow and wrist come from the same source frame, without rotating the
// arm to a synthetic direction. The half-strength peak is midway from neutral to the full arc.
const elbow=pose=>Math.acos(Math.max(-1,Math.min(1,R.dot(R.unit(R.sub(pose.points[9],pose.points[8])),R.unit(R.sub(pose.points[10],pose.points[9]))))))*180/Math.PI;
const halfElbows=[];
for(const f of [13,17,20,25.25]){
 const selected=sourceFrame(.5,f-9),actual=elbow(reducedRaw(f/60,.5)),expected=elbow(raw(selected/60));
 close(actual,expected,1e-5);halfElbows.push({frame:f,sourceFrame:selected,bendDegrees:actual});
}
const basis=A.swingBasis(raw(0),raw(referenceRelease),rig),fullPeak=raw(arcEnd/60),fullAngle=A.swingAngle(A.armDirection(fullPeak,rig),basis);
const arcChecks=[];
for(const p of [.25,.5,.75]){
 const finish=timing(p).trigger+arcEnd-armed,peak=reducedRaw(finish/60,p),angle=A.swingAngle(A.armDirection(peak,rig),basis);
 close(angle,fullAngle*p,.001);arcChecks.push({percent:p*100,frame:finish,degrees:angle*180/Math.PI});
 // After the finite follow-through, recovery rejoins the exact original FK return.
 const stopLocal=R.localize(peak.points,peak.q,data.parents),last=raw(clip.duration),lastLocal=R.localize(last.points,last.q,data.parents);
 for(let f=finish+8;f<end;f+=1){const pose=reducedRaw(f/60,p),local=R.localize(pose.points,pose.q,data.parents),u=smooth((f-finish)/(end-finish));for(let j=0;j<data.names.length;j++)if(j===rig.shoulder||rig.throwArm.has(j))sameQ(local.q[j],R.qslerp(stopLocal.q[j],lastLocal.q[j],u));}
}
assert(arcChecks[1].degrees>40&&arcChecks[1].degrees<55,'Half arc should be roughly45 degrees forward from neutral');
// User's current case:5%, Armed18, default release34, no Half/Aim. Check
// actual world motion, since small spine-local deltas alone missed this bug.
const fiveCurve=A.chargeCurve(f=>raw(f/60),18,34,end,rig),fiveTiming=A.chargeTiming(18,34,.05),fiveFinish=fiveTiming.trigger+fiveCurve.peak-18;
const currentFive=f=>{
 const source=raw(f/60);if(f<=fiveTiming.trigger)return source;
 return A.partialPose({source,charged:raw(fiveTiming.trigger/60),action:raw(A.chargeFrame(fiveCurve,.05,f-fiveTiming.trigger)/60),rig,amount:.05,entry:(f-fiveTiming.trigger)/4,recover:smooth((f-fiveFinish)/(end-fiveFinish)),ending:raw(clip.duration),anchor:f>fiveFinish?raw(fiveFinish/60):source,body:bodyPlan(raw,.05,34),frame:f,anchorFrame:Math.min(f,fiveFinish)});
};
const measure=sample=>{
 const start=raw(0),max={headMetres:0,chestMetres:0,pelvisMetres:0,pelvisDegrees:0};
 for(let f=0;f<=end;f+=.25){const pose=sample(f);for(const [name,j] of [['headMetres',17],['chestMetres',6],['pelvisMetres',1]])max[name]=Math.max(max[name],R.length(R.sub(pose.points[j],start.points[j])));max.pelvisDegrees=Math.max(max.pelvisDegrees,R.length(R.qlog(R.qm(pose.q[1],R.qinv(start.q[1]))))*180/Math.PI);}
 return max;
};
const worldMotion={fivePercent:measure(currentFive),seventyFivePercent:measure(f=>reducedRaw(f/60,.75)),full:measure(f=>raw(f/60))};
assert(worldMotion.fivePercent.headMetres<.02,'5% must barely move the head in world space');
assert(worldMotion.fivePercent.chestMetres<.015);assert(worldMotion.fivePercent.pelvisMetres<.005);assert(worldMotion.fivePercent.pelvisDegrees<1);
assert(worldMotion.fivePercent.headMetres/worldMotion.full.headMetres<.1);
// Independent whole-cycle body displacement, not summed local quaternion
// angles, captures the visible effort and the reported excess torso motion.
worldMotion.byCharge=[];
for(const p of [.05,.25,.43,.5,.75,1]){
 const peak=measure(f=>reducedRaw(f/60,p)),previous=worldMotion.byCharge.at(-1);
 for(const key of Object.keys(peak)){
  assert(peak[key]<=worldMotion.full[key]+1e-8,'Partial charge exceeds full world motion: '+JSON.stringify({p,key,peak:peak[key],full:worldMotion.full[key]}));
  if(previous)assert(peak[key]>=previous.peak[key]-1e-8,'World body effort must increase with charge: '+JSON.stringify({p,key,peak:peak[key],previous:previous.peak[key]}));
 }
 worldMotion.byCharge.push({percent:p*100,peak});
}
// Reproduce the reported43%, slowdown blend.06, Armed18/Throw34 case over
// the full cycle. Event-join continuity alone missed the old F10→14 reversal.
const headCurve=A.chargeCurve(f=>raw(f/60),18,34,end,rig),headTiming=A.chargeTiming(18,34,.43),headSpeed=A.chargeSpeed(headCurve,.43,.06),headFinish=headTiming.trigger+(headCurve.peak-18)/headSpeed.multiplier;
const currentHead=f=>{
 const source=raw(f/60);if(f<=headTiming.trigger)return source;
 const elapsed=(f-headTiming.trigger)*headSpeed.multiplier;
 return A.partialPose({source,charged:raw(headTiming.trigger/60),action:raw(A.chargeFrame(headCurve,.43,elapsed)/60),rig,amount:.43,entry:elapsed/4,recover:smooth((f-headFinish)/(end-headFinish)),ending:raw(clip.duration),anchor:f>headFinish?raw(headFinish/60):source,body:bodyPlan(raw,.43,34),frame:f,anchorFrame:Math.min(f,headFinish)});
};
const headForward=R.unit(R.sub(raw(24/60).points[17],raw(8/60).points[17])),headZSign=Math.sign(raw(24/60).points[17][2]-raw(8/60).points[17][2])||1,headRows=[];
for(let f=0;f<=end;f+=.25){const point=currentHead(f).points[17];headRows.push({frame:f,forward:R.dot(point,headForward),worldZ:point[2]*headZSign});}
const headChanges=[];let previousDirection=0,minimumForwardStep=Infinity;
for(let i=1;i<headRows.length;i++){
 const change=headRows[i].forward-headRows[i-1].forward,direction=Math.abs(change)>1e-8?Math.sign(change):0;
 if(headRows[i-1].frame>=8&&headRows[i].frame<=headTiming.trigger+bodyPlan(raw,.43,34).settle)minimumForwardStep=Math.min(minimumForwardStep,change);
 if(direction&&previousDirection&&direction!==previousDirection)headChanges.push({frame:headRows[i].frame,from:previousDirection,to:direction});
 if(direction)previousDirection=direction;
}
const headTrajectory={percent:43,slowdownBlend:.06,projectionAxis:headForward,minimumForwardStep,changes:headChanges,peakFrame:headRows.reduce((best,row)=>row.forward>best.forward?row:best).frame};
assert(minimumForwardStep>=-1e-8,'43% head must retain incoming forward motion during settling: '+JSON.stringify(headTrajectory));
assert.equal(headChanges.filter(change=>change.from===1&&change.to===-1).length,1,'Head should have only one forward-to-return transition: '+JSON.stringify(headTrajectory));
const zChanges=[];let previousZDirection=0,minimumZStep=Infinity;
for(let i=1;i<headRows.length;i++){
 const change=headRows[i].worldZ-headRows[i-1].worldZ,direction=Math.abs(change)>1e-8?Math.sign(change):0;
 if(headRows[i-1].frame>=8&&headRows[i].frame<=headTiming.trigger+bodyPlan(raw,.43,34).settle)minimumZStep=Math.min(minimumZStep,change);
 if(direction&&previousZDirection&&direction!==previousZDirection)zChanges.push({frame:headRows[i].frame,from:previousZDirection,to:direction});
 if(direction)previousZDirection=direction;
}
headTrajectory.worldZ={forwardSign:headZSign,minimumForwardStep:minimumZStep,changes:zChanges,peakFrame:headRows.reduce((best,row)=>row.worldZ>best.worldZ?row:best).frame};
assert(minimumZStep>=-1e-8,'43% head world-Z must retain incoming forward motion during settling');
assert.equal(zChanges.filter(change=>change.from===1&&change.to===-1).length,1,'Head world-Z should have one forward-to-return transition');
// Only clavicles release their retained wind-up early; chest motion is preserved.
const claviclePlan=bodyPlan(raw,.37,34),clavicleNeutral=R.localize(raw(0).points,raw(0).q,data.parents);
const clavicleAngle=(f,j)=>R.length(R.qlog(R.qm(R.qinv(clavicleNeutral.q[j]),claviclePlan.local(raw(f/60),f).q[j])))*180/Math.PI;
for(const j of [7,11]){assert(clavicleAngle(26,j)<clavicleAngle(19.857,j));assert(clavicleAngle(26,j)<5,'Retained clavicle wind-up must unwind by F26');}
assert.deepEqual(headChanges.map(c=>[c.from,c.to]),[[1,-1]],'No extra head reversal');
assert.deepEqual(zChanges.map(c=>[c.from,c.to]),[[1,-1]],'No extra head Z reversal');
// Added transitions must not arrest torso/pelvis velocity. Compare one-sided
// derivatives in metres/second and radians/second at each procedural join.
const bodySmoothness=[];
for(const p of [.05,.25,.43,.5,.76,.99]){
 const when=timing(p),body=bodyPlan(raw,p),finish=when.trigger+arcEnd-armed;
 for(const [join,f] of [['trigger',when.trigger],['bodySettled',when.trigger+body.settle],['bodyReturn',body.returnStart],['clavicleReturn',body.clavicleReturnEnd],['armPeak',finish]]){
  const h=1e-4,a=reducedRaw((f-h)/60,p),b=reducedRaw(f/60,p),c=reducedRaw((f+h)/60,p);
  const v0=R.mul(R.sub(b.points[17],a.points[17]),60/h),v1=R.mul(R.sub(c.points[17],b.points[17]),60/h);
  const w0=R.mul(R.qlog(R.qm(b.q[1],R.qinv(a.q[1]))),60/h),w1=R.mul(R.qlog(R.qm(c.q[1],R.qinv(b.q[1]))),60/h);
  // Original30fps key boundaries can change slope; only demand exact smooth
  // joins where the source itself has no key boundary.
  const sourceBoundary=Math.abs(f/2-Math.round(f/2))<1e-6;
  if(!sourceBoundary){assert(R.length(R.sub(v1,v0))<.001,'Artificial torso velocity jump '+p+' '+join);assert(R.length(R.sub(w1,w0))<.005,'Artificial pelvis velocity jump '+p+' '+join);}
  bodySmoothness.push({percent:p*100,join,frame:f,headVelocityJump:R.length(R.sub(v1,v0)),pelvisAngularVelocityJump:R.length(R.sub(w1,w0)),sourceBoundary});
 }
}
// A shortened throw must advance over the WHOLE forward interval. Merely
// checking continuity at event boundaries missed the old ten-frame plateau.
const sourceProgress=[];
for(const p of [.05,.18,.25,.33,.5,.76,.99]){
 const span=arcEnd-armed,start=sourceFrame(p,0),last=sourceFrame(p,span),range=last-start;
 assert(range>0,'Nonzero charge must have a forward source segment');
 for(let f=.25;f<span;f+=.25)close((sourceFrame(p,f)-start)/range,f/span,1e-9);
 const t=timing(p).trigger,basis=A.swingBasis(raw(0),raw(referenceRelease),rig);
 let previous=-Infinity;
 for(let f=4;f<=span;f+=.25){const angle=A.swingAngle(A.armDirection(reducedRaw((t+f)/60,p),rig),basis);assert(angle>previous,'Forward arc stalled/reversed after entry');previous=angle;}
 sourceProgress.push({percent:p*100,startFrame:start,endFrame:last,firstTenFrameFraction:(sourceFrame(p,10)-start)/range});
}
assert.equal(V.config({}).slowdownBlend,0);
assert.equal(V.config({slowdownBlend:2}).slowdownBlend,1);
assert.equal(V.config({slowdownBlend:-1}).slowdownBlend,0);
const speedBlendCases=[];
for(const p of [.05,.18,.33,.5,.99])for(const blend of [0,.25,.5,.75,1]){
 const speed=A.chargeSpeed(curve,p,blend),when=timing(p),release=when.trigger+when.forward/speed.multiplier,finish=when.trigger+(arcEnd-armed)/speed.multiplier;
 close(speed.rate,speed.baseRate+(1-speed.baseRate)*blend);
 if(blend===0)assert.equal(speed.multiplier,1);if(blend===1)close(speed.rate,1);
 const dt=(finish-when.trigger)/100,at=when.trigger+(finish-when.trigger)/2;
 close((sourceFrame(p,(at+dt-when.trigger)*speed.multiplier)-sourceFrame(p,(at-when.trigger)*speed.multiplier))/dt,speed.rate,1e-7);
 close(sourceFrame(p,(release-when.trigger)*speed.multiplier),sourceFrame(p,when.forward));
 const before=reducedRaw(when.trigger/120,p,raw,blend);assert.deepEqual(before,raw(when.trigger/120));
 const normal=reducedRaw(timing(p).release/60,p),fast=reducedRaw(release/60,p,raw,blend);
 for(const j of [rig.shoulder,rig.elbow,rig.hand])sameQ(normal.q[j],fast.q[j]);
 speedBlendCases.push({percent:p*100,blend,rate:speed.rate,releaseFrame:release,peakFrame:finish});
}
// Scan all joints over the whole timeline, then refine detected discontinuities.
// Original or retimed source key boundaries are reported separately, never hidden.
const audit=require('./motion-audit.js'),motionAudits=[];
for(const p of [.05,.25,.37,.5,.75,.99])for(const blend of [0,.06,1]){
 const speed=A.chargeSpeed(curve,p,blend),when=timing(p),finish=when.trigger+(arcEnd-armed)/speed.multiplier;
 const report=audit.scan({sample:f=>reducedRaw(f/60,p,raw,blend),end,names:data.names});
 const classified=report.discontinuities.map(r=>{
  const original=Math.abs(r.frame/2-Math.round(r.frame/2))<.002;
  const phase=sourceFrame(p,Math.max(0,r.frame-when.trigger)*speed.multiplier);
  const retimed=r.frame>when.trigger&&r.frame<finish&&Math.abs(phase/2-Math.round(phase/2))<.002;
  return {...r,origin:original?'source key':retimed?'retimed source key':'procedural'};
 });
 assert(!classified.some(r=>r.origin==='procedural'),'Unexplained velocity discontinuity: '+JSON.stringify({p,blend,classified}));
 for(const f of [when.trigger,finish]){
  const h=1e-5,a=reducedRaw((f-h)/60,p,raw,blend),b=reducedRaw(f/60,p,raw,blend),c=reducedRaw((f+h)/60,p,raw,blend);
  const jump=R.length(R.mul(R.sub(R.sub(c.points[hand],b.points[hand]),R.sub(b.points[hand],a.points[hand])),60/h));
  assert(jump<.003,'Hand velocity must carry through transition: '+JSON.stringify({p,blend,f,jump}));
 }
 motionAudits.push({percent:p*100,blend,samples:report.samples,flags:classified});
}
const oldScan=audit.scan({sample:f=>reducedRaw(f/60,.37,raw,.06,false),end,names:data.names});
const oldTrigger=timing(.37).trigger,oldFinish=oldTrigger+(arcEnd-armed)/A.chargeSpeed(curve,.37,.06).multiplier;
assert(oldScan.discontinuities.some(r=>Math.abs(r.frame-oldTrigger)<.01),'Detector must catch original entry stop');
assert(oldScan.discontinuities.some(r=>Math.abs(r.frame-oldFinish)<.01),'Detector must catch original recovery stop');
fs.writeFileSync(new URL('../../Saved/ThrowLab/motion-audit-sweep.json',import.meta.url),JSON.stringify({cases:motionAudits,negativeControl:oldScan},null,2));
const controls=V.config({armed,twist:8.5,speedScale:1.3,velocityRotation:[9,-12,4],keys:[{frame:25,rotation:[12,4,-7]},{frame:26,rotation:[7,-3,8]}],forearmKeys:[{frame:25,rotation:[9,-4,3]},{frame:26,rotation:[2,5,-6]}]},end,releaseFrame);
const keyed=(pose,t)=>V.pose(V.pose(pose,data.parents,forearm,controls.forearmKeys,t*60,true),data.parents,hand,controls.keys,t*60);
const baseline=t=>keyed(raw(t),t),reduced=(t,p,blend=0)=>keyed(reducedRaw(t,p,raw,blend),t);
const plain=reducedRaw(25/60,.5),keyedPose=reduced(25/60,.5),armPose=V.pose(plain,data.parents,forearm,controls.forearmKeys,25,true);
sameQ(keyedPose.q[hand],R.qm(armPose.q[hand],V.rotation(controls.keys[0].rotation)));
const sim=await createProjectileSystem(assets,R,V);
try{
 for(const kind of ['bomb','spear']){
  const base={key:'small-throw-strength-'+kind,kind,release:referenceRelease,hand,duration:clip.duration,sample:baseline,controls,target:[20,20,20],radius:.16,grip:{position:[.015,-.01,.02],rotation:[4,-7,5]},scale:[1,1,1]};
  const original=structuredClone(sim.preview(base));
  for(const p of [0,.05,.5,1])for(const blend of p===.5?[0,.5,1]:p===.05?[1]:[0]){
   const release=(timing(p).trigger+timing(p).forward/A.chargeSpeed(curve,p,blend).multiplier)/60,sample=t=>reduced(t,p,blend),options={...base,release,referenceRelease,baseSample:baseline,sample,preserveLaunch:true,launchScale:p,launchRotation:[0,0,0,1]};
   const seed=structuredClone(sim.preview(options)),held=sim.held({...options,pose:sample(release)});
   assert.deepEqual(sim.reference(options),original,'Reference stays at authored full-strength Throw frame');
   near(seed.p,held.p);sameQ(seed.q,held.q);near(seed.v,R.mul(original.v,p));assert.equal(seed.twist,8.5);close(R.length(seed.omega),8.5*60*Math.PI/180);
   const before=sim.at(release-1e-7,options);assert.equal(before.phase,'held');near(before.p,held.p,2e-5);sameQ(before.q,held.q,1e-7);
   const exact=sim.at(release,options);assert.notEqual(exact.phase,'held');near(exact.p,held.p,1e-6);sameQ(exact.q,held.q);near(exact.v,seed.v,1e-5);
   const flight=sim.at(release+.1,options);assert([...flight.p,...flight.q,...flight.v].every(Number.isFinite));
   sim.at(release+.025,options);assert.deepEqual(sim.at(release+.1,options),flight,'Exact reduced-throw replay');
   if(p===1){near(seed.p,original.p);sameQ(seed.q,original.q);near(seed.v,original.v);}
   launchCases++;
  }
  const release=timing(.5).release/60,sample=t=>reduced(t,.5),half={...base,release,referenceRelease,baseSample:baseline,sample,preserveLaunch:true,launchScale:.5};
  const halfFlight=sim.at(release+.1,half),quarter={...half,launchScale:.25};
  near(sim.preview(quarter).v,R.mul(original.v,.25));const quarterFlight=sim.at(release+.1,quarter);
  assert(R.length(R.sub(halfFlight.p,quarterFlight.p))>1e-4,'launchScale must invalidate replay');assert.deepEqual(sim.at(release+.1,half),halfFlight);
  const otherReference={...half,referenceRelease:referenceRelease-.15},otherSeed=sim.preview(otherReference);
  assert(R.length(R.sub(otherSeed.v,sim.preview(half).v))>1e-4,'referenceRelease must invalidate reference velocity');
 }
 const receipt={success:true,prefixSamples,poseSamples,launchCases,maxCutoffPositionGap,halfElbows,arcEnd,arcChecks,effortChecks,localExcursionOvershoot,worldMotion,headTrajectory,bodySmoothness,sourceProgress,speedBlendCases,halfChargeFrame:timing(.5).trigger,halfReleaseFrame:timing(.5).release,fullReleaseFrame:releaseFrame,checks:'Continuous shortened source clock (no armed plateau); normal-speed causal prefixes including Half/Aim; cutoff continuity; forward shoulder arc measured from neutral (25/50/75%), whole source arm pose retained, including world forearm/hand quaternion and palm roll; causal body remainder preserves reached pose and incoming velocity, then settles;43% full-trajectory head regression on fixed3D projection and worldZ; monotonic world head/chest/pelvis effort; root/pelvis/leg motion reduced after causal trigger (Half remains fixed);5% world head/chest/pelvis bounds; direct recovery from reduced forward peak; earlier fractional release; full-Throw reference velocity scaled once; zero drop; exact100%/endpoint restoration; actual-frame keys; manual twist; cache invalidation and Jolt replay.'};
 fs.writeFileSync(new URL('../../Saved/ThrowLab/strength-verification.json',import.meta.url),JSON.stringify(receipt,null,2));console.log(JSON.stringify({success:receipt.success,prefixSamples,poseSamples,launchCases,localExcursionOvershoot,worldMotion,headTrajectory}));
}finally{sim.dispose();}
