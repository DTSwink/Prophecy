/* Free-flight balance of the final articulated pose. Contact owns the seed. */
(function(root){
'use strict';
const node=typeof module!=='undefined',R=node?require('./recovery.js'):root.Recovery,M=node?require('./mass.js'):root.BodyflipMass,H=node?require('./momentum.js'):root.BodyflipMomentum;
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
function create(source,{start,settings,names,parents,reference,gravity=9.81,cap=20,seedSource=source,velocityImpulse=[0,0,0],releaseVelocity=null,balance=true,stepSeconds=step}={}){
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
  if(seed)return;
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
  const first=source(start),shift=sub(seed.center,M.center(first.pose,rig));
  frames.push({...last,pose:{...first.pose,points:first.pose.points.map(p=>add(p,shift))},physical});
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
   return {...frame,phase,vy:path.velocity[1],pose:{...frame.pose,points:frame.pose.points.map(p=>add(p,shift))},root:add(frame.root||frame.pose.points[0],shift),physical};
  }
  const retained=length(drive.vector)>1e-10?drive.vector:frame.spin?.spinAxis||frame.spin?.axis;
  const axis=settings?.momentum3D===false&&retained&&length(retained)>1e-10?R.unit(retained):null;
  // Keep all authored articulation. Only the carrier's accumulated rigid
  // rotation changes, so joint limits and limb timing survive unchanged.
  const candidate=M.rotateAboutCOM(frame.pose,previous.physical.rotation,rig),target=add(seed.momentum,sub(drivenMomentum(drive,candidate),seed.command)),balanced=H.correct(previous.pose,candidate,target,rig,dt,{axis});
  const rotation=R.unit(qm(balanced.rotation,previous.physical.rotation)),shift=sub(path.center,M.center(balanced.pose,rig));
  const pose={...balanced.pose,points:balanced.pose.points.map(p=>add(p,shift))},physical={momentum:balanced.momentum,target,rotation,error:balanced.error,fullResidual:balanced.fullResidual,axis,com:path.center,velocity:path.velocity,iterations:balanced.iterations,balanced:true};
  const carrier=frame.spin?qm(rotation,frame.spin.rotation||identity):null;
  const spin=frame.spin?{...frame.spin,q:qm(rotation,frame.spin.q||identity),rotation:carrier,commandedOmega:frame.spin.omega,
   omega:mul(R.qlog(qm(carrier,R.qinv(previous.spin?.rotation||identity))),1/dt)}:frame.spin;
  return {...frame,phase,vy:path.velocity[1],pose,root:add(frame.root||frame.pose.points[0],shift),spin,physical};
 }
 function sample(t){
  if(t<=start)return seedSource(Math.min(t,start-epsilon));
  initialize();const index=Math.floor((t-start)/tick+1e-9);
  while(frames.length<=index){const n=frames.length;frames.push(advance(frames[n-1],start+n*tick,tick));}
  const at=start+index*tick,elapsed=t-at;
  return elapsed<1e-10?frames[index]:advance(frames[index],t,elapsed);
 }
 function state(t){initialize();return t<=start?frames[0].physical:sample(t).physical;}
 return {sample,state,rig,start,step:tick,get ticks(){return Math.max(0,frames.length-1);}};
}
const api={create,command};if(node)module.exports=api;else root.BodyflipPhysicalFlight=api;
})(globalThis);
