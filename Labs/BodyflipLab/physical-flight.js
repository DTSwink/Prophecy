/* Free-flight balance of the final articulated pose. Contact owns the seed. */
(function(root){
'use strict';
const Work=typeof module!=='undefined'?require('./preparation.js'):root.BodyflipPreparation;
const node=typeof module!=='undefined',R=node?require('./recovery.js'):root.Recovery,M=node?require('./mass.js'):root.BodyflipMass,H=node?require('./momentum.js'):root.BodyflipMomentum;
const Target=node?require('./target-rig.js'):root.BodyflipTargetRig;
const {add,sub,mul,length,qm}=R,identity=[0,0,0,1],step=1/240,epsilon=1e-7,velocityStep=.0001;
function curveAt(curve,t){
 if(!curve)return [0,0,0];if(t<curve.begin&&curve.prior)return curveAt(curve.prior,t);
 let u=t<curve.begin?0:curve.duration>0?Math.max(0,Math.min(1,(t-curve.begin)/curve.duration)):1;u=u*u*u*(10+u*(-15+6*u));
 return add(curve.from,mul(sub(curve.to,curve.from),u));
}
function command(frame,t){
 const plan=frame.spin?.spinPlan;if(!plan)return {vector:[0,0,0],momentum:[0,0,0]};
 const vector=add(curveAt(plan.flip,t),curveAt(plan.twist,t));return {vector,momentum:M.product(plan.referenceI,vector)};
}
function create(source,{start,settings,names,parents,reference,gravity=9.81,cap=20,seedSource=source,velocityImpulse=[0,0,0],releaseVelocity=null,balance=true,stepSeconds=step,articulation=null,angularCommand=null}={}){
 if(!Number.isFinite(start))throw Error('Physical flight needs a finite release time');
 if(!(stepSeconds>0&&Number.isFinite(stepSeconds)))throw Error('Physical flight needs a positive finite timestep');
 const tick=stepSeconds,rig=M.model(names,parents,reference),inertia=settings?.spinInertia??1,frames=[];let seed=null;
 function drivenMomentum(drive,pose){
  if(inertia===1)return drive.momentum;
  // At zero, this is an authored speed controller: changing inertia changes
  // commanded momentum. Articulation still receives its opposing reaction.
  const current=M.product(M.tensor(pose,rig),drive.vector);
  return add(mul(current,1-inertia),mul(drive.momentum,inertia));
 }
 function initialize(){
  if(frames.length)return;
  // These reads stay strictly on the completed contact side. The owning
  // carrier may still be constructing the first released frame.
  const before=seedSource(start-step),last=seedSource(start-epsilon),elapsed=step-epsilon;
  const center=M.center(last.pose,rig),momentum=balance?H.momentum(before.pose,last.pose,rig,elapsed):[0,0,0];
  // A short push can gain most of its speed in the last integration tick.
  // Seed translation from the instantaneous contact-side derivative, not
  // that tick's average velocity, which would discard the final push impulse.
  const c1=M.center(seedSource(start-epsilon-velocityStep).pose,rig),c2=M.center(seedSource(start-epsilon-2*velocityStep).pose,rig);
  const velocity=mul(add(sub(mul(center,3),mul(c1,4)),c2),1/(2*velocityStep)),acceleration=mul(add(sub(center,mul(c1,2)),c2),1/(velocityStep*velocityStep));
  const measured=add(velocity,mul(acceleration,epsilon)),outgoing=releaseVelocity?releaseVelocity(measured,last):measured;
  seed={frame:last,center:add(center,add(mul(velocity,epsilon),mul(acceleration,.5*epsilon*epsilon))),velocity:add(outgoing,velocityImpulse),momentum,command:drivenMomentum(command(last,start-epsilon),last.pose)};
  const physical={momentum,target:momentum,rotation:identity,error:0,axis:null,com:seed.center,velocity:seed.velocity,iterations:0,balanced:balance};
  // Contact supplies the momentum/COM state; the release source supplies the
  // captured, constrained limb pose. Starting from the pre-projection joints
  // would turn their correction into an instantaneous whole-body rotation.
  const first=source(start);let initialPose=first.pose;
  if(first.poseMotion?.continued&&last.physical?.poseState?.key===first.poseMotion.key){physical.poseState={...last.physical.poseState};initialPose=first.poseMotion.applySpeed(initialPose,physical.poseState.value*first.poseMotion.responseSpeed,first.poseMotion.mask).pose;}
  const shift=sub(seed.center,M.center(initialPose,rig));
  let pose={...initialPose,points:initialPose.points.map(p=>add(p,shift))};if(follow)pose=follow(pose,start);
  frames.push({...last,pose,physical,...(first.poseMotion?{spin:first.spin||last.spin}:{})});
 }
 function ballistic(t){
  const age=Math.max(0,t-start),v=seed.velocity,g=Math.max(0,gravity),terminal=Math.max(0,cap);
  const until=g>0?Math.max(0,(v[1]+terminal)/g):Infinity,h=Math.min(age,until);
  const y=g>0?v[1]*h-.5*g*h*h-terminal*(age-h):v[1]*age;
  return {center:add(seed.center,[v[0]*age,y,v[2]*age]),velocity:[v[0],g>0?Math.max(-terminal,v[1]-g*age):v[1],v[2]]};
 }
 function advance(previous,t,dt){
  const frame=source(t),drive=command(frame,t);
  const path=ballistic(t);
  const phase=releaseVelocity&&['RISE','FALL','FALL LOOP'].includes(frame.phase)?path.velocity[1]>0?'RISE':frame.phase==='RISE'?'FALL':frame.phase:frame.phase;
  if(!balance){
   const shift=sub(path.center,M.center(frame.pose,rig)),physical={...previous.physical,com:path.center,velocity:path.velocity};
   let pose={...frame.pose,points:frame.pose.points.map(p=>add(p,shift))};if(follow)pose=follow(pose,t);
   return {...frame,phase,vy:path.velocity[1],pose,root:add(frame.root||frame.pose.points[0],shift),physical};
  }
  const retained=length(drive.vector)>1e-10?drive.vector:frame.spin?.spinAxis||frame.spin?.axis;
  const axis=settings?.momentum3D===false&&retained&&length(retained)>1e-10?R.unit(retained):null;
  // Keep all authored articulation. Only the carrier's accumulated rigid
  // rotation changes, so joint limits and limb timing survive unchanged.
  let candidate=M.rotateAboutCOM(frame.pose,previous.physical.rotation,rig);
  const move=sub(path.center,M.center(candidate,rig));candidate={...candidate,points:candidate.points.map(p=>add(p,move))};
  const constrained=follow?.active(t),worldFollow=constrained&&follow.worldActive(t);
  const previousCarrier=previous.spin?.rotation||identity;
  const poseState=frame.poseMotion&&previous.physical.poseState?.key===frame.poseMotion.key?previous.physical.poseState:{value:0,rate:0};
  const frequency=frame.poseMotion?1/frame.poseMotion.responseTime:0,decay=Math.exp(-frequency*dt),gain=1-(1+frequency*dt)*decay;
  const baseResponse=(poseState.value+(poseState.rate+frequency*poseState.value)*dt)*decay;
  function balanceCandidate(value){
   const response=frame.poseMotion?frame.poseMotion.applySpeed(candidate,(baseResponse+gain*value)*frame.poseMotion.responseSpeed,frame.poseMotion.mask):null;
   let posed=response?Target.create(names,parents,reference).project(response.pose):candidate;
   if(constrained&&!worldFollow)posed=follow(posed,t);
   let target=add(seed.momentum,sub(drivenMomentum(drive,posed),seed.command));
   if(angularCommand)target=add(target,M.product(M.tensor(posed,rig),angularCommand(t,posed,dt)));
   const solved=H.correct(previous.pose,posed,target,rig,dt,{axis,project:worldFollow?p=>follow(p,t):null});
   let speed=0;
   if(response){const rotation=R.unit(qm(solved.rotation,previous.physical.rotation)),carrier=qm(rotation,frame.spin?.rotation||identity),omega=mul(R.qlog(qm(carrier,R.qinv(previousCarrier))),1/dt);speed=R.dot(omega,R.rotate(solved.pose.q[names.indexOf('pelvis')],[1,0,0]))*180/Math.PI;}
   return {solved,target,response,speed,error:response?value-Math.max(-1,Math.min(1,speed/frame.poseMotion.responseSpeed)):0,value};
  }
  let result=balanceCandidate(0),responseIterations=0;
  if(frame.poseMotion){
   // Damped pose response and angular reaction are coupled within this tick.
   // Only one scalar is fitted; the authored pose and fall wobble remain fixed.
   let lo=-1,hi=1,low=null,high=null;
   while(Math.abs(result.error)>1e-5&&responseIterations<12){
    if(result.error<0){lo=result.value;low=result;}else {hi=result.value;high=result;}
    let next=low&&high?(lo*high.error-hi*low.error)/(high.error-low.error):Math.max(-1,Math.min(1,result.value-result.error));
    if(next<lo||next>hi||Math.abs(next-result.value)<1e-9)next=(lo+hi)/2;
    result=balanceCandidate(next);responseIterations++;
   }
  }
  const balanced=result.solved,target=result.target,poseResponse=result.response;
  const rotation=R.unit(qm(balanced.rotation,previous.physical.rotation)),shift=sub(path.center,M.center(balanced.pose,rig));
  const pose={...balanced.pose,...(poseResponse?{authoredPose:true}:{}),points:balanced.pose.points.map(p=>add(p,shift))},physical={momentum:balanced.momentum,target,rotation,error:balanced.error,fullResidual:balanced.fullResidual,axis,com:path.center,velocity:path.velocity,iterations:balanced.iterations,balanced:true,...(frame.poseMotion?{poseState:{key:frame.poseMotion.key,value:baseResponse+gain*result.value,rate:(poseState.rate-frequency*(poseState.rate+frequency*(poseState.value-result.value))*dt)*decay}}:{})};
  const carrier=frame.spin?qm(rotation,frame.spin.rotation||identity):null;
  const spin=frame.spin?{...frame.spin,q:qm(rotation,frame.spin.q||identity),rotation:carrier,commandedOmega:frame.spin.omega,
   omega:mul(R.qlog(qm(carrier,R.qinv(previous.spin?.rotation||identity))),1/dt)}:frame.spin;
  // A later marker may use this completed frame as its source. Consume the
  // deferred deformation so that it cannot be applied a second time there.
  return {...frame,phase,vy:path.velocity[1],pose,root:add(frame.root||frame.pose.points[0],add(move,shift)),spin,physical,...(poseResponse?{poseMotion:null,heldPoseMotion:{motion:frame.poseMotion,speed:poseResponse.poseSpeed},jumpMotion:{...frame.jumpMotion,poseSpeed:result.speed,poseVariant:poseResponse.poseVariant,poseResponse:poseResponse.poseResponse,poseResponseError:result.error,poseResponseIterations:responseIterations}}:{})};
 }
 function sample(t){
  if(t<=start)return seedSource(Math.min(t,start-epsilon));
  initialize();const index=Math.floor((t-start)/tick+1e-9);
  while(frames.length<=index){const n=frames.length;frames.push(advance(frames[n-1],start+n*tick,tick));Work.checkpoint();}
  const at=start+index*tick,elapsed=t-at;
  return elapsed<1e-10?frames[index]:advance(frames[index],t,elapsed);
 }
 function state(t){initialize();return t<=start?frames[0].physical:sample(t).physical;}
 const follow=articulation?.({sample,source,start,step:tick});
 return {sample,state,rig,start,step:tick,get ticks(){return Math.max(0,frames.length-1);}};
}
const api={create,command};if(node)module.exports=api;else root.BodyflipPhysicalFlight=api;
})(globalThis);
