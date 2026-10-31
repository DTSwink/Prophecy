/* Calibrate aim against the same balanced trajectory that is finally played. */
(function(root){
'use strict';
const node=typeof module!=='undefined',A=node?require('./attack-aim.js'):root.BodyflipAttackAim,P=node?require('./physical-flight.js'):root.BodyflipPhysicalFlight;
function create(rawSource,physicalOptions,{track,clip,settings,project=null}){
 const {names,parents,reference}=physicalOptions,start=physicalOptions.start??0,identity=p=>p,finish=project||identity,aim=settings.aim!==false,amount=settings.aimWeight??1,undo=settings.undoRotation!==false,target=settings.target.slice();
 const rawCache=new Map(),originalSource=rawSource;rawSource=t=>{const key=Math.round(t*1e9);if(rawCache.has(key))return rawCache.get(key);const frame=originalSource(t);rawCache.set(key,frame);if(rawCache.size>1024)rawCache.delete(rawCache.keys().next().value);return frame;};
 const statistics={evaluations:0},launchAt=track.launchAt?(pose,transform=identity)=>track.launchAt(pose,track.transportVelocity(t=>transform(rawSource(t).pose,t))):null;
 let plan=null,physical=null;
 function evaluateMotion(delta,{applyDeltaAt,hitTime}){
  statistics.evaluations++;
  const candidate=P.create(t=>{const f=rawSource(t);return {...f,pose:finish(applyDeltaAt(f.pose,t,delta))};},{...physicalOptions,stepSeconds:1/60}),sample=t=>finish(candidate.sample(t).pose),pose=sample(hitTime);
  const launch=track.launchAt?track.launchAt(pose,track.transportVelocity(sample),track.transportAngularVelocity?.(sample)||[0,0,0]):null;
  return {pose,sample,launch};
 }
 function prepare(){
  if(physical)return;
  if(aim){
   const common={clip,track,names,parents,reference,sampleHit:t=>rawSource(t).pose,launchAt,project},initial=A.create(common).solution(target);
   plan=A.create({...common,evaluateMotion,evaluationAmount:amount,evaluationUndoRotation:undo,motionSolve:{seed:initial.parameters,maxStep:2,indices:settings.momentum3D===false?[0,1,2]:[1,2]}});
  }
  // Resolve once before constructing the final source; candidate trajectories
  // are discarded after solving, and no final sample starts another plan.
  const delta=plan?.correction(target),rotation=delta?(t=>plan.rotation(t,target,amount,undo)):null;
  physical=P.create(t=>{const frame=rawSource(t);return rotation?{...frame,pose:finish(plan.applyRotation(frame.pose,rotation(t)))}:frame;},physicalOptions);
 }
 function sample(t){if(t<start)return rawSource(t);prepare();const frame=physical.sample(t);return {...frame,physicalAim:true};}
 return {sample,prepare,statistics,get plan(){prepare();return plan;},get physical(){prepare();return physical;}};
}
const api={create};if(node)module.exports=api;else root.BodyflipPhysicalAim=api;
})(globalThis);
