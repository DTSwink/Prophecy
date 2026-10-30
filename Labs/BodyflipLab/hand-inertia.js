/* Keep a released hand-push body's mass centre ballistic while it articulates.
 * Apply after animation/attack/flip overlays and before the capsule carrier. */
(function(root){
'use strict';
const R=typeof module!=='undefined'?require('./recovery.js'):root.Recovery;
const S=typeof module!=='undefined'?require('./support.js'):root.BodyflipSupport;
const {add,sub,mul}=R,gravity=9.81,seedStep=.0001;
const vector=(v,n)=>Array.isArray(v)&&v.length===n&&v.every(Number.isFinite);
function create(source,{release,cap=20,names,parents,reference}={}){
 if(typeof source!=='function')throw new TypeError('Hand inertia requires a frame sampler');
 const diagnostics={enabled:false,reason:null,release,seedStep,cap:Number.isFinite(cap)&&cap>0?cap:20};
 const passthrough={sample:(t,...args)=>source(t,...args),trajectory:()=>null,diagnostics};
 const validPose=p=>p&&Array.isArray(p.points)&&p.points.length===names.length&&p.points.every(v=>vector(v,3))&&Array.isArray(p.q)&&p.q.length===names.length&&p.q.every(v=>vector(v,4));
 const validFrame=f=>f&&vector(f.root,3)&&validPose(f.pose);
 if(!Number.isFinite(release)){diagnostics.reason='No finite hand release';return passthrough;}
 if(!Array.isArray(names)||names.length<2||!names.every(n=>typeof n==='string')||!Array.isArray(parents)||parents.length!==names.length||!validPose(reference)){
  diagnostics.reason='Invalid mass reference';return passthrough;
 }
 // Left-sided samples include the final pinned pose. Sampling the free side
 // would inherit the old animation-induced impulse we are removing.
 const frames=[source(release),source(release-seedStep),source(release-2*seedStep)];
 if(!frames.every(validFrame)){diagnostics.reason='Invalid release pose';return passthrough;}
 const centres=frames.map(f=>S.com(f.pose,names,parents,reference));
 const origin=centres[0],velocity=mul(add(sub(mul(centres[0],3),mul(centres[1],4)),centres[2]),1/(2*seedStep));
 if(!vector(origin,3)||!vector(velocity,3)){diagnostics.reason='Invalid release mass centre';return passthrough;}
 // Do not abruptly slow a body already falling faster than the requested cap
 // at release. Retain that inherited speed, without accelerating it further.
 const effectiveCap=Math.max(diagnostics.cap,-velocity[1]),capTime=Math.max(0,(velocity[1]+effectiveCap)/gravity);
 Object.assign(diagnostics,{enabled:true,position:origin.slice(),velocity:velocity.slice(),effectiveCap,capTime:release+capTime});
 function trajectory(time){
  if(!Number.isFinite(time)||time<release)return null;
  const elapsed=time-release,accelerating=Math.min(elapsed,capTime);
  const y=velocity[1]*accelerating-.5*gravity*accelerating*accelerating-effectiveCap*Math.max(0,elapsed-capTime);
  const position=add(origin,[velocity[0]*elapsed,y,velocity[2]*elapsed]);
  return vector(position,3)?{position,velocity:[velocity[0],Math.max(-effectiveCap,velocity[1]-gravity*elapsed),velocity[2]]}:null;
 }
 function sample(time,...args){
  const frame=source(time,...args);
  if(!Number.isFinite(time)||time<=release||!validFrame(frame))return frame;
  const desired=trajectory(time),actual=S.com(frame.pose,names,parents,reference);
  if(!desired||!vector(actual,3))return frame;
  const correction=sub(desired.position,actual),points=frame.pose.points.map(p=>add(p,correction)),position=add(frame.root,correction);
  if(!vector(position,3)||!points.every(p=>vector(p,3)))return frame;
  // A uniform translation preserves every authored joint angle and length.
  // Root velocity is not COM velocity; the capsule computes its own velocity
  // from this corrected root and may then add genuine collision impulses.
  return {...frame,pose:{...frame.pose,points},root:position,handInertia:{com:desired.position,velocity:desired.velocity,correction}};
 }
 return {sample,trajectory,diagnostics};
}
// The approaching hand has no support force yet. Moving its torso/arms must
// therefore move the root oppositely, keeping the whole-body COM on its incoming
// trajectory. Wrist targets remain world-fixed throughout this coupled solve.
function fitApproach(pose,time,solveTargets,{comAt,resolveRoot=null,names,parents,reference}){
 const wanted=comAt(time),baseRoot=pose.points[0];
 if(!vector(wanted,3))return {pose:solveTargets(pose),residual:0,freeResidual:0,contacts:[],iterations:0};
 let result=solveTargets(pose),contacts=[],residual=Infinity,freeResidual=Infinity,iterations=0;
 const translate=(p,d)=>({...p,points:p.points.map(v=>add(v,d))});
 for(let i=0;i<20;i++){
  const error=sub(wanted,S.com(result,names,parents,reference));
  if(!vector(error,3))break;
  residual=R.length(error);iterations=i+1;
  if(residual<2e-9){freeResidual=residual;break;}
  const previous=result,shifted=translate(result,error);
  const resolved=resolveRoot?resolveRoot(baseRoot,sub(shifted.points[0],baseRoot),shifted):{root:shifted.points[0],contacts:[]};
  if(!vector(resolved.root,3))break;
  contacts=resolved.contacts||[];
  result=solveTargets(translate(shifted,sub(resolved.root,shifted.points[0])));
  const remaining=sub(wanted,S.com(result,names,parents,reference));let free=remaining;
  // A capsule contact can supply an external normal force. Never undo that
  // collision merely to satisfy a free-flight COM equation inside the floor.
  for(let pass=0;pass<3;pass++)for(const contact of contacts)if(vector(contact.normal,3))free=sub(free,mul(contact.normal,Math.min(0,R.dot(free,contact.normal))));
  residual=R.length(remaining);freeResidual=R.length(free);
  if(freeResidual<2e-9&&R.length(sub(result.points[0],previous.points[0]))<2e-9)break;
 }
 return {pose:result,residual,freeResidual,contacts,iterations};
}
const api={create,fitApproach,seedStep};if(typeof module!=='undefined')module.exports=api;else root.BodyflipHandInertia=api;
})(globalThis);
