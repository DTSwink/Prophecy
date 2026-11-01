/* Predict the carrier turn, then steer the authored stroke as one chain. */
(function(root){
'use strict';
const node=typeof module!=='undefined',A=node?require('./attack-aim.js'):root.BodyflipAttackAim,P=node?require('./physical-flight.js'):root.BodyflipPhysicalFlight,R=node?require('./recovery.js'):root.Recovery,M=node?require('./mass.js'):root.BodyflipMass,Work=node?require('./preparation.js'):root.BodyflipPreparation;
function create(rawSource,physicalOptions,{track,clip,settings,project=null,worldPose=p=>p}){
 const {names,parents,reference}=physicalOptions,start=physicalOptions.start??0,identity=p=>p,finish=project||identity,aim=settings.aim!==false,amount=1,undo=settings.undoRotation!==false,target=settings.target.slice(),hitTime=track.releaseTime??track.hitTime;
 const rig=M.model(names,parents,reference),rawCache=new Map(),originalSource=rawSource;
 rawSource=t=>{const key=Math.round(t*1e9);if(rawCache.has(key))return rawCache.get(key);const frame=originalSource(t);rawCache.set(key,frame);if(rawCache.size>1024)rawCache.delete(rawCache.keys().next().value);return frame;};
 const statistics={evaluations:0},neutral=P.create(rawSource,physicalOptions);
 let plan=null,physical=null,prediction=null,pending=null,best=null,previous=null,neutralHit=null,predictionTrack=neutral,throwAimOrigin=null;
 // A point-targeted spear must fit the final release after momentum response.
 // Rotating a predicted pose and then applying that world turn before the
 // carrier rotation is not equivalent: those two rotations do not commute.
 // Fit the same two spine angles against the actual trajectory instead.
 const pointThrow=track.isThrow&&track.kind==='spear'&&!track.throwDirection,candidates=new Map();let pointContext=null;
 function candidate(delta,context){
  const key=JSON.stringify(delta.throwAngles||delta.throwTurn);if(candidates.has(key))return candidates.get(key);
  const path=P.create(t=>{const f=rawSource(t);return {...f,pose:finish(context.applyDeltaAt(f.pose,t,delta))};},physicalOptions);
  candidates.set(key,path);if(candidates.size>4)candidates.delete(candidates.keys().next().value);statistics.evaluations++;return path;
 }
 function preparePointThrow(){
  if(!plan){
   // Shaft fitting needs only the held transform, never release velocities.
   // Reading the sequence's carrier velocity while that sequence is being
   // prepared would recursively enter this same aim plan. The actual spawn
   // still computes its unchanged complete velocities after preparation.
   const sampleHit=t=>finish(worldPose(rawSource(t).pose,t)),launchAt=pose=>track.launchAt(pose,[0,0,0],[0,0,0]);
   neutralHit ||= neutral.sample(hitTime);
   const base=launchAt(sampleHit(hitTime)),carried=track.heldAt(finish(worldPose(neutralHit.pose,hitTime))),toward=R.unit(R.rotate(R.qinv(neutralHit.physical.rotation),R.sub(target,carried.p))),direction=R.unit(base.axis),yaw=Math.atan2(toward[0],toward[2])-Math.atan2(direction[0],direction[2]),seed=[Math.atan2(Math.sin(yaw),Math.cos(yaw)),Math.asin(direction[1])-Math.asin(toward[1])];
   plan=A.create({clip,track,names,parents,reference,sampleHit,launchAt,project,evaluationAmount:amount,evaluationUndoRotation:undo,
    evaluateMotion:(delta,context)=>{
     pointContext=context;const path=candidate(delta,context),sample=t=>finish(worldPose(path.sample(t).pose,t)),pose=sample(hitTime);
     return {pose,sample,launch:launchAt(pose)};
    // Conservation can make one heading branch unreachable. The opposite
    // winding is the same two-angle fit, without adding pelvis/arm freedom.
    },motionSolve:{throwSeeds:[seed,[seed[0]+(seed[0]<0?2:-2)*Math.PI,seed[1]]],iterations:24,maxStep:.6,tolerance:1e-7}});
  }
  const solved=plan.solution(target);physical=candidate(solved.state,pointContext);statistics.error=solved.error;candidates.clear();
 }
 function prepare(){
  if(physical)return;
  if(!aim||amount<=0){physical=neutral;return;}
  if(pointThrow){preparePointThrow();return;}
  if(track.isThrow&&!throwAimOrigin){const time=Number.isFinite(track.aimReferenceTime)?track.aimReferenceTime:track.start;throwAimOrigin=worldPose(rawSource(time).pose,time).points[names.indexOf('pelvis')].slice();}
  neutralHit ||= neutral.sample(hitTime);
  prediction ||= neutralHit.physical.rotation;
  while(statistics.evaluations<6){
   if(!pending){
    const turn=prediction.slice(),carrier=predictionTrack,carrierHit=carrier.sample(hitTime).physical.rotation,predicted=t=>{
     const correction=track.launchAt?R.qm(R.qm(carrier.sample(t).physical.rotation,R.qinv(carrierHit)),turn):turn;
     const base=rawSource(t).pose,p=M.rotateAboutCOM(base,correction,rig),center=neutral.sample(t).physical.com,shift=R.sub(center,M.center(p,rig));
     return finish(worldPose({...p,points:p.points.map(v=>R.add(v,shift))},t));
    },hit=predicted(hitTime);
    // The predictor owns this carrier sample; querying the outer sequence here
    // would recursively request the plan currently being prepared.
    const launchAt=track.launchAt?(pose,transform=identity)=>{const sample=t=>transform(predicted(t),t);return track.launchAt(pose,track.releaseVelocity(sample,undefined,predicted),track.projectileAngularVelocity(sample));}:null;
    const neutralPlan=A.create({clip,track,names,parents,reference,sampleHit:predicted,launchAt,project,throwAimOrigin,evaluateMotion:()=>({pose:hit}),motionSolve:{seed:[0,0,0,0,0,0],iterations:0}});
    const basis=R.qm(hit.q[names.indexOf('pelvis')],R.qinv(reference.q[names.indexOf('pelvis')])),world=A.between(neutralPlan.direction,neutralPlan.throwDirectionFor?.(target)||R.sub(target,neutralPlan.origin),R.rotate(basis,[0,1,0])),local=R.qm(R.qm(R.qinv(basis),world),basis),twist=R.unit([0,local[1],0,local[3]]),swing=R.qlog(R.qm(local,R.qinv(twist))),yaw=R.qlog(twist)[1];
    const candidatePlan=A.create({clip,track,names,parents,reference,sampleHit:predicted,launchAt,project,throwAimOrigin,evaluationAmount:amount,evaluationUndoRotation:undo,
     evaluateMotion:(delta,context)=>{const sample=t=>finish(context.applyDeltaAt(predicted(t),t,delta));return {pose:sample(hitTime),sample};},
     motionSolve:{seed:[yaw,swing[0],swing[2],0,0,0],iterations:18,maxStep:.6,indices:[0,1,2,3,4,5],scales:[1,1,1,.25,.25,1]}});
    pending={turn,plan:candidatePlan,track:null};
   }
   const attempt=pending;attempt.plan.correction(target);
   attempt.track ||= P.create(t=>{const f=rawSource(t);return {...f,pose:finish(attempt.plan.apply(f.pose,t,target,amount,undo))};},physicalOptions);
   const frame=attempt.track.sample(hitTime),pose=finish(worldPose(frame.pose,hitTime)),base=finish(worldPose(neutralHit.pose,hitTime));
   const launch=(physical,p)=>{const sample=t=>finish(worldPose(physical.sample(t).pose,t));return track.launchAt(p,track.releaseVelocity(sample,undefined,sample),track.projectileAngularVelocity?.(sample)||[0,0,0]);};
   const packet=track.launchAt?launch(attempt.track,pose):null,basePacket=track.launchAt?launch(neutral,base):null;
   const aimed=packet?A.launchAim(packet,target,attempt.plan.throwDirectionFor?.(target)):null,origin=aimed?aimed.origin:M.center(pose,rig),ray=R.unit(aimed?aimed.direction:R.sub(attempt.plan.point(pose),origin)),baseRay=R.unit(basePacket?A.launchAim(basePacket).direction:R.sub(attempt.plan.point(base),M.center(base,rig))),goal=R.rotate(R.qslerp([0,0,0,1],A.between(baseRay,aimed?aimed.wanted:R.sub(target,origin),[0,1,0]),amount),baseRay);
   const error=R.length(R.sub(ray,goal));statistics.evaluations++;
   if(!best||error<best.error)best={...attempt,error};
   const residual=R.qlog(R.qm(frame.physical.rotation,R.qinv(attempt.turn))),axis=frame.physical.axis;
   if(error<1e-4)break;
   let step=R.mul(residual,.6);
   // Axis balance leaves one scalar prediction to reconcile. A secant update
   // uses the last two completed flights instead of dozens of pose derivatives.
   if(axis&&previous){
    const change=R.dot(R.qlog(R.qm(attempt.turn,R.qinv(previous.turn))),axis),value=R.dot(residual,axis),old=R.dot(previous.residual,axis),slope=(value-old)/(change||1e-12);
    if(Math.abs(change)>1e-5&&Math.abs(slope)>.15)step=R.mul(axis,Math.max(-.8,Math.min(.8,-value/slope)));
   }
   previous={turn:attempt.turn,residual};predictionTrack=attempt.track;prediction=R.qm(R.qexp(step),attempt.turn);pending=null;Work.checkpoint();
  }
  plan=best.plan;physical=best.track;statistics.error=best.error;pending=null;
 }
 function sample(t){if(t<start)return rawSource(t);prepare();return {...physical.sample(t),physicalAim:true};}
 return {sample,prepare,statistics,get plan(){prepare();return plan;},get physical(){prepare();return physical;}};
}
const api={create};if(node)module.exports=api;else root.BodyflipPhysicalAim=api;
})(globalThis);
