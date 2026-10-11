const {assertHeadBudget}=require('./head-test-helpers.cjs');
const assert=require('node:assert/strict'),H=require('./holster.js'),L=require('./headlook.js'),R=require('./recovery.js');
const data=require('./data/motions.json'),setup=require('./data/unreal-setup.json');
// User's failing 162-degree gaze fixture; independent of live settings/snapshots.
const profile={"gazeYaw":162,"sheatheRotationTolerance":15,"slideRotationCorrection":0.25,"motion":"idle","sheathe":true,"startTick":25,"maxReachSpeed":250,"maxReachRotationSpeed":2500,"slidingSpeed":150,"shrinkPercent":15,"unshrinkDuration":0.5,"holsterX":0,"holsterY":0,"holsterZ":0,"holsterPitch":0,"holsterYaw":0,"holsterRoll":0,"duration":8,"spineClavicleAngleLimit":45,"maxSpineClavicleAngularSpeed":90,"drawReturn":{"enabled":true,"duration":1,"returnEasing":1,"inertia":1,"inertiaHold":0,"inertiaDecay":1,"worldInertia":false,"springReturn":false,"angleTimeSeconds":0.29,"upperArmTwistRemoval":0,"boneInertia":{"spine":1,"clavicle":1,"upperarm":1,"lowerarm":1,"neck_01":1,"neck_02":1,"head":1}},"sheatheReturn":{"enabled":true,"duration":1,"returnEasing":1,"inertia":1,"inertiaHold":0,"inertiaDecay":1,"worldInertia":false,"springReturn":false,"angleTimeSeconds":0.29,"upperArmTwistRemoval":0,"boneInertia":{"spine":1,"clavicle":1,"upperarm":1,"lowerarm":1,"neck_01":1,"neck_02":1,"head":1}},"headLookAtAlpha":0.5,"headLookInExponent":2,"headLookOutExponent":2,"maxHeadLookInVelocity":120,"maxHeadLookOutVelocity":110,"drawHeadLookOutThreshold":0.3,"sheatheHeadLookOutThreshold":0.5,"drawCurve":[[0.12035926109088917,0.06965517232365878],[0.38862275386866246,0.4437027977650636],[0.5663472710639236,0.688768305251455],[0.9050299670725398,0.9918757535169326]],"sheatheCurve":[[0.20083831851807013,0.06119108139624617],[0.4020359141167777,0.3320528156629226],[0.6166466699636005,0.564220086752473],[0.8983233549689856,0.9249662598391809]],"drawSlideCurve":[[0.2,0.2],[0.4,0.4],[0.6,0.6],[0.8,0.8]],"sheatheSlideCurve":[[0.13712572739078147,0.04043271696188657],[0.650179602563385,0.7111385494636496],[0.8849101307618773,0.9562043029634382],[0.9553293659722167,0.9884497709488423]]};
const head=data.names.indexOf('head'),neck=data.names.indexOf('neck_02'),dist=(a,b)=>R.length(R.sub(a,b)),reports=[];
for(const gazeYaw of [162,-162])for(const motion of ['idle','walk'])for(const sheathe of [true,false]){
 const m=H.prepare(data,setup,{...profile,gazeYaw,motion,sheathe});assert(m.plan.arrives&&m.completionTick!==null,'large turns complete');
 let maxHeadStep=0,maxNeckStep=0;
 for(let i=1;i<m.frames.length;i++){
  const a=m.frames[i-1],f=m.frames[i],body=H.sampleBody(m,i/60),neutral=H.motion(data,motion,i/60)[head].q;
  maxHeadStep=Math.max(maxHeadStep,dist(a.pose[head].p,f.pose[head].p));maxNeckStep=Math.max(maxNeckStep,H.angle(a.pose[neck].q,f.pose[neck].q));
  if(i>m.o.startTick)assertHeadBudget(m,i);
  for(const j of m.headContext.chain)assert(Math.abs(dist(f.pose[j].p,f.pose[data.parents[j]].p)-dist(body.pose[j].p,body.pose[data.parents[j]].p))<1e-6,'neck lengths preserved');
  if(f.headLook.mode==='Look in'&&f.headLook.remainingDegrees<.01)assert(R.dot(R.rotate(f.pose[head].q,[0,1,0]),R.rotate(neutral,[0,1,0]))>=-1e-4,'half-strength look stays in forward hemisphere');
 }
 assert(maxNeckStep<5,'no 120-degree neck branch jumps');
 if(motion==='idle')assert(maxHeadStep<.3,'idle head position remains continuous');
 const last=m.frames.at(-1),neutral=H.motion(data,motion,m.playbackDuration,gazeYaw)[head].q;
 assert(H.angle(last.pose[head].q,neutral)<.001,'look-out returns to the independent gaze-facing target');
 assert(R.length(m.headTrack.at(-1).correction)<Math.PI,'no extra full turn stored in the neck');
 for(const tick of [132.999,133,133.001,m.plan.endTick+.3,m.plan.slideEnd+.3]){
  const a=H.sample(m,tick/60),b=H.sample(m,(tick+.001)/60);assert(dist(a.pose[head].p,b.pose[head].p)<.01,'subframe neck continuity');
 }
 reports.push({gazeYaw,motion,sheathe,entry:m.plan.endTick,slideEnd:m.plan.slideEnd,complete:m.completionTick,maxHeadStepCm:maxHeadStep,maxNeckStepDeg:maxNeckStep});
}
// A continuous correction crossing 180 degrees must not flip its weighted neck shares.
const pose=H.motion(data,'idle',0),ctx=L.make(data);let reference=null,previous=null;
for(const degrees of [179,180,181]){const q=R.qm(R.qexp([0,0,degrees*Math.PI/180]),pose[head].q);reference=L.correctionLog(R.qm(q,R.qinv(pose[head].q)),reference);const f=L.apply(ctx,pose,q,reference);if(previous)for(const j of ctx.chain)assert(H.angle(previous[j].q,f[j].q)<1.01);previous=f;}
console.log(JSON.stringify({passed:true,reports},null,2));
