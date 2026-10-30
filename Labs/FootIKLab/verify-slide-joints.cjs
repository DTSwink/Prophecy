'use strict';
// Isolated math/geometry checks. Does not start a viewer, server or Jolt world.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const R=require('./recovery.js'),{build}=require('./slide-joints.js');
const {add,sub,mul,length,unit,rotate,qm,qinv,qexp,qlog}=R;
const s=build(),rig=JSON.parse(fs.readFileSync(path.join(__dirname,'data/rig.json'),'utf8'));
const RAD=Math.PI/180;let checks=0,worstTarget=0,worstHinge=0;
function check(value,message){checks++;assert.ok(value,message);}
function close(a,b,tol=1e-9,message='Values differ'){check(Math.abs(a-b)<tol,`${message}: ${a} vs ${b}`);}
const qdistance=(a,b)=>length(qlog(qm(qinv(a),b)));
const constraintToWorld=(j,q,parent=s.reference.q[j.parent])=>unit(qm(qm(qm(parent,j.c1),q),qinv(j.c2)));
check(s.reference.sha256===rig.sharedIdle.sha256,'Embedded sharedIdle provenance');
for(let i=0;i<rig.names.length;i++){
 close(length(sub(s.reference.points[i],rig.sharedIdle.points[i])),0,1e-12,'Reference positions');
 close(qdistance(s.reference.q[i],R.fromAxes(rig.sharedIdle.axes[i])),0,1e-12,'Reference axes');
}
for(const j of s.joints.filter(Boolean)){
 const parent=s.reference.q[j.parent],child=s.reference.q[j.index];
 check(s.diagnose(j.index,parent,child).withinLimits,`Neutral ${j.name}`);
 close(qdistance(s.project(j.index,parent,child).q,child),0,1e-9,'Neutral remains unchanged');
}
for(const name of ['foot_l','foot_r','ball_l','ball_r','hand_l','hand_r']){
 const i=rig.names.indexOf(name),j=s.joints[i],parent=s.reference.q[j.parent];
 for(const axis of [0,1,2])for(const sign of [-1,1]){
  const v=[0,0,0];v[axis]=sign*100*RAD;
  const desired=constraintToWorld(j,qexp(v)),out=s.project(i,parent,desired);
  check(out.after.withinLimits,`${name} axis ${axis} bound`);
  const expected=[0,0,0];expected[axis]=sign*(axis===0?j.twist:axis===1?j.swingY:j.swingZ);
  close(qdistance(out.q,constraintToWorld(j,qexp(expected))),0,1e-8,'Correct Jolt axis mapping');
 }
 for(let k=0;k<120;k++){
  const desired=constraintToWorld(j,qexp(mul(unit([Math.sin(k*2.1+.3),Math.cos(k*3.9+.7),Math.sin(k*1.3+.9)]),(k%37)*.109)));
  const out=s.project(i,parent,desired),again=s.project(i,parent,out.q);
  check(out.after.withinLimits,`${name} compound bound ${k}`);
  close(qdistance(out.q,again.q),0,1e-8,'Projection idempotent');
  close(qdistance(out.q,s.project(i,parent,mul(desired,-1)).q),0,1e-8,'Quaternion hemisphere invariant');
  const global=qexp([.7,-1.1,.32]);
  const transformed=s.project(i,qm(global,parent),qm(global,desired));
  close(qdistance(qm(global,out.q),transformed.q),0,1e-8,'Projection independent of world orientation');
 }
}
for(const side of ['l','r']){
 const a=s.arms[side],j=a.j;
 for(const deg of [-40,0,40,155,175]){
  const parent=s.reference.q[a.upper],q=qm(parent,s.hingeRelative(j,deg*RAD));
  const out=s.project(a.lower,parent,q);
  check(out.after.withinLimits,`Elbow hinge ${side} ${deg}`);
  close(out.after.bendDeg,Math.max(0,Math.min(155,deg)),1e-7,'Elbow flexion clamp');
 }
 for(let k=0;k<60;k++){
  const p=structuredClone(s.reference),start=p.points[a.upper],l1=length(sub(p.points[a.lower],start)),l2=length(sub(p.points[a.hand],p.points[a.lower]));
  const axis=unit([Math.sin(k*1.23+.2),Math.cos(k*.9+.4),Math.sin(k*.53+1.1)]),distance=(l1+l2)*(.3+.69*(k%19)/18);
  const near=Math.sqrt(l1*l1+l2*l2+2*l1*l2*Math.cos(155*RAD)),d=Math.max(near,distance),target=add(start,mul(axis,d));
  s.solveArm(p,side,target,[.3,-.7,.9]);
  const err=length(sub(p.points[a.hand],target)),diag=s.diagnose(a.lower,p.q[a.upper],p.q[a.lower]);
  worstTarget=Math.max(worstTarget,err);worstHinge=Math.max(worstHinge,diag.hingeError);
  close(err,0,1e-8,'Arm target reached');
  close(length(sub(p.points[a.lower],start)),l1,1e-10,'Upperarm length');
  close(length(sub(p.points[a.hand],p.points[a.lower])),l2,1e-10,'Forearm length');
  check(diag.withinLimits,`True hinge arm ${side} ${k}`);
  close(qdistance(qm(qinv(p.q[a.lower]),p.q[a.hand]),s.joints[a.hand].refRelative),0,1e-8,'Unspecified wrist stays neutral');
  for(const i of [a.upper,a.lower,a.hand])close(qdistance(R.fromAxes(p.axes[i]),p.q[i]),0,1e-9,'Returned axes coherent');
 }
 const p=structuredClone(s.reference),original=p.points[a.hand].slice(),pole=sub(p.points[a.lower],p.points[a.upper]);
 s.solveArm(p,side,original,pole,p.q[a.hand]);
 close(length(sub(p.points[a.hand],original)),0,1e-9,'Rest hand recovered');
 close(qdistance(p.q[a.upper],s.reference.q[a.upper]),0,1e-9,'Rest upperarm recovered');
 close(qdistance(p.q[a.lower],s.reference.q[a.lower]),0,1e-9,'Rest elbow recovered');
 // Impossible near and far targets must obey the same limits and lengths.
 for(const distance of [0,5]){
  const pose=structuredClone(s.reference),start=pose.points[a.upper];
  s.solveArm(pose,side,add(start,[distance,0,0]),[0,1,0],qexp([2,1,-2]));
  check(s.diagnose(a.lower,pose.q[a.upper],pose.q[a.lower]).withinLimits,'Unreachable arm respects elbow');
  check(s.diagnose(a.hand,pose.q[a.lower],pose.q[a.hand]).withinLimits,'Brace wrist projected');
 }
 // Generate reachable targets from valid shoulder/hinge configurations, then
 // request an unrelated pole. A swivel must find a legal shoulder without
 // changing the hand location or relaxing the elbow hinge.
 for(let k=0;k<90;k++){
  const p=structuredClone(s.reference),start=p.points[a.upper],shoulder=s.joints[a.upper],parentQ=p.q[shoulder.parent];
  const upperQ=constraintToWorld(shoulder,qexp([.45*Math.sin(k*.7),.55*Math.cos(k*.4),.5*Math.sin(k*.3)]),parentQ);
  const lowerQ=qm(upperQ,s.hingeRelative(j,(15+k%130)*RAD));
  const upperOffset=rotate(qinv(s.reference.q[a.upper]),sub(s.reference.points[a.lower],s.reference.points[a.upper]));
  const lowerOffset=rotate(qinv(s.reference.q[a.lower]),sub(s.reference.points[a.hand],s.reference.points[a.lower]));
  const target=add(add(start,rotate(upperQ,upperOffset)),rotate(lowerQ,lowerOffset));
  s.solveArm(p,side,target,[Math.sin(k*.8),Math.cos(k*.9),Math.sin(k*.6)],qexp([.3,.2,.4]));
  check(s.diagnose(a.upper,p.q[shoulder.parent],p.q[a.upper]).withinLimits,'Feasible shoulder swivel found');
  check(s.diagnose(a.lower,p.q[a.upper],p.q[a.lower]).withinLimits,'Swivel preserves elbow hinge');
  close(length(sub(p.points[a.hand],target)),0,1e-8,'Swivel preserves hand target');
 }
}
let kneeSwivelCases=0,maxKneeSwivelDegrees=0;
for(const side of ['l','r']){
 const hip=rig.names.indexOf('thigh_'+side),knee=rig.names.indexOf('calf_'+side),foot=rig.names.indexOf('foot_'+side),hj=s.joints[hip],kj=s.joints[knee];
 const upperOffset=rotate(qinv(s.reference.q[hip]),sub(s.reference.points[knee],s.reference.points[hip]));
 const lowerOffset=rotate(qinv(s.reference.q[knee]),sub(s.reference.points[foot],s.reference.points[knee]));
 for(let k=0;k<100;k++){
  const p=structuredClone(s.reference),start=p.points[hip],parentQ=p.q[hj.parent];
  const legalHip=constraintToWorld(hj,qexp([.4*Math.sin(k*.3),.6*Math.sin(k*.6),.5*Math.cos(k*.4)]),parentQ);
  const legalKnee=qm(legalHip,s.hingeRelative(kj,(20+k%110)*RAD));
  const legalKneePoint=add(start,rotate(legalHip,upperOffset)),target=add(legalKneePoint,rotate(legalKnee,lowerOffset));
  const axis=unit(sub(target,start)),perturb=qexp(mul(axis,(k%2?1:-1)*(90+k%70)*RAD));
  p.q[hip]=qm(perturb,legalHip);p.q[knee]=qm(perturb,legalKnee);
  p.points[knee]=add(start,rotate(perturb,sub(legalKneePoint,start)));p.points[foot]=target.slice();
  const beforeRelative=qm(qinv(p.q[hip]),p.q[knee]),delta=sub(p.points[knee],start),pole=unit(sub(delta,mul(axis,R.dot(delta,axis))));
  const theta=s.feasibleSwivel(hip,parentQ,p.q[hip],axis,pole,pole),turn=qexp(mul(axis,theta));
  p.q[hip]=qm(turn,p.q[hip]);p.q[knee]=qm(turn,p.q[knee]);p.points[knee]=add(start,rotate(turn,delta));
  kneeSwivelCases++;maxKneeSwivelDegrees=Math.max(maxKneeSwivelDegrees,Math.abs(theta)/RAD);
  check(s.diagnose(hip,parentQ,p.q[hip]).withinLimits,'Hip swivel finds feasible cone');
  check(s.diagnose(knee,p.q[hip],p.q[knee]).withinLimits,'Hip swivel preserves signed knee hinge');
  close(qdistance(beforeRelative,qm(qinv(p.q[hip]),p.q[knee])),0,1e-9,'Hip swivel does not change knee flexion');
  close(length(sub(add(start,rotate(p.q[hip],upperOffset)),p.points[knee])),0,1e-9,'Swivel knee position follows thigh');
  close(length(sub(add(p.points[knee],rotate(p.q[knee],lowerOffset)),target)),0,1e-9,'Swivel calf still reaches fixed ankle');
 }
}
let actualArmRows=0,maxSweepDegrees=0,actualHipRows=0;
for(const fixture of [2,5]){
 const file=path.join(__dirname,'snapshots',`slide-joints-model-${fixture}.json`);if(!fs.existsSync(file))continue;
 const model=JSON.parse(fs.readFileSync(file,'utf8')),joints=build(undefined,model.names,model.parents);
 for(let frame=0;frame<model.frames.length;frame++){
  const f=model.frames[frame];if(f.surface?.mode!=='SLIDE'||frame/120-f.surface.slide.time<.25)continue;
  for(const side of ['l','r']){
   const a=joints.arms[side],p=structuredClone(f.pose),target=p.points[a.hand].slice();
   joints.solveArm(p,side,target,sub(p.points[a.lower],p.points[a.upper]),p.q[a.hand]);actualArmRows++;
   check(joints.diagnose(a.upper,p.q[model.parents[a.upper]],p.q[a.upper]).withinLimits,'Actual slide shoulder');
   check(joints.diagnose(a.lower,p.q[a.upper],p.q[a.lower]).withinLimits,'Actual slide elbow');
   close(length(sub(p.points[a.hand],target)),0,1e-8,'Actual slide hand contact');
   const hip=model.names.indexOf('thigh_'+side),knee=model.names.indexOf('calf_'+side),foot=model.names.indexOf('foot_'+side),axis=unit(sub(p.points[foot],p.points[hip]));
   const delta=sub(p.points[knee],p.points[hip]),pole=unit(sub(delta,mul(axis,R.dot(delta,axis)))),oldRelative=qm(qinv(p.q[hip]),p.q[knee]);
   const theta=joints.feasibleSwivel(hip,p.q[model.parents[hip]],p.q[hip],axis,pole,pole),turn=qexp(mul(axis,theta));
   p.q[hip]=qm(turn,p.q[hip]);p.q[knee]=qm(turn,p.q[knee]);actualHipRows++;
   check(joints.diagnose(hip,p.q[model.parents[hip]],p.q[hip]).withinLimits,'Actual slide hip feasible');
   close(qdistance(oldRelative,qm(qinv(p.q[hip]),p.q[knee])),0,1e-9,'Actual slide signed knee unchanged');
  }
 }
 // Nearby target perturbations must produce a continuous pole solution.
 const f=model.frames[400];if(!f)continue;
 for(const side of ['l','r']){
  const a=joints.arms[side],target=f.pose.points[a.hand],pole=sub(f.pose.points[a.lower],f.pose.points[a.upper]);let previous;
  for(let k=0;k<=240;k++){
   const p=structuredClone(f.pose),t=k/240*Math.PI*2;
   joints.solveArm(p,side,add(target,[.01*Math.sin(t),.01*Math.cos(t),.01*Math.sin(t)]),pole,p.q[a.hand]);
   check(joints.diagnose(a.upper,p.q[model.parents[a.upper]],p.q[a.upper]).withinLimits,'Smooth sweep shoulder');
   if(previous){const degrees=qdistance(previous,p.q[a.upper])/RAD;maxSweepDegrees=Math.max(maxSweepDegrees,degrees);check(degrees<1,'No coarse swivel snapping');}previous=p.q[a.upper];
  }
 }
}
console.log(JSON.stringify({checks,worstTargetMetres:worstTarget,worstHingeRadians:worstHinge,kneeSwivelCases,maxKneeSwivelDegrees,actualArmRows,actualHipRows,maxSweepDegrees}));
