/* Authored airborne poses. Spin response is evaluated causally by free flight. */
(function(root){
'use strict';
const node=typeof module!=='undefined',R=node?require('./recovery.js'):root.Recovery,C=node?require('./core.js'):root.BodyflipCore;
const {qm,qinv,qlog,qexp,qslerp,rotate,add,mul,dot}=R,rad=Math.PI/180,clamp=x=>Math.max(0,Math.min(1,x));
const ease=x=>{x=clamp(x);return x*x*x*(10+x*(-15+6*x));};
// Independent start/finish easing, then per-joint angular-distance shaping.
// Freeze each joint's distance at entry so targets/physical iterations cannot
// change its clock. Analytic weights keep reverse seeks deterministic.
function transitionProgress(time,settings){
 const t=clamp(time);if(t===0||t===1)return t;
 const a=t**(1+2*(settings.poseEaseIn??.15)),b=(1-t)**(1+2*(settings.poseEaseOut??.5));return a/(a+b);
}
function jointProgress(progress,angle,exponent){
 if(progress<=0||progress>=1)return clamp(progress);
 const gain=(1+angle/(Math.PI/2))**(exponent-1);
 return -Math.expm1(gain*Math.log1p(-progress));
}
function transitionWeights(pose,target,parents,settings){
 const local=R.localize(pose.points,pose.q,parents),angles=target.map((q,i)=>R.length(qlog(qm(q,qinv(local.q[i])))));
 return progress=>angles.map(angle=>jointProgress(progress,angle,settings.poseExponent??2));
}
let library=null,poses=null;
function configure(data){
 if(data?.schema!=='bodyflip-authored-poses-v1'||data.clips.length!==4)throw Error('Invalid authored pose library');
 library=data;poses=data.clips.map(clip=>{if(clip.frames.length!==3)throw Error('Authored pose needs three frames');return {...clip,locals:clip.frames.map(p=>R.localize(p.points,p.q,data.parents))};});
}
if(node)configure(require('./data/poses.json'));
const fallCache=new WeakMap();
function falling(jumps,parents){
 if(fallCache.has(jumps))return fallCache.get(jumps);
 const clip=jumps.find(c=>c.name.endsWith('_Loop_Fall'));if(!clip)throw Error('Missing falling wobble source');
 const frames=clip.poses.map(p=>R.localize(p.points,p.q,parents).q),mean=frames[0].map((q,j)=>{let m=q;for(let pass=0;pass<3;pass++){let d=[0,0,0];for(const f of frames.slice(0,-1))d=add(d,qlog(qm(qinv(m),f[j])));m=qm(m,qexp(mul(d,1/(frames.length-1))));}return m;});
 const sample=time=>{const f=((time%clip.duration)+clip.duration)%clip.duration*clip.fps,i=Math.min(frames.length-2,Math.floor(f));return frames[i].map((q,j)=>qlog(qm(qinv(mean[j]),qslerp(q,frames[i+1][j],f-i))));};
 const result={sample,mean};fallCache.set(jumps,result);return result;
}
function poseWeight(age,event){
 if(age<=0||event.pose==='none')return 0;
 return ease(age/event.poseIn);
}
// Freeze the same distance-weighted duration rule as attack returns, measuring
// only the destination articulation in the current pelvis frame.
function blendTiming(pose,target,parents,pelvis,seconds,weight){
 const local=R.localize(pose.points,pose.q,parents);
 for(let i=1;i<parents.length;i++)if(i!==pelvis)local.q[i]=target[i];
 const goal=R.fk(local,parents),angle=Math.max(...goal.q.map((q,i)=>i&&i!==pelvis?R.length(qlog(qm(q,qinv(pose.q[i])))):0));
 return {duration:C.returnDuration(seconds,angle,weight),angle,baseDuration:seconds};
}
// Attacks retain authority over their own joints; pose response fades underneath
// using the same entry/return envelope, rather than altering the authored strike.
function restrict(frame,indices,weight){
 if(!frame.poseMotion)return frame;
 const selected=new Set(indices),motion=frame.poseMotion;
 return {...frame,poseMotion:{...motion,mask:motion.mask.map((v,i)=>selected.has(i)?v*(1-clamp(weight)):v)}};
}
function create(event,segment,jumps,names,parents,settings){
 const e=C.sanitizeJump(event);
 if(!Number.isFinite(segment.airStart)||segment.jumpStart>=segment.abortTime||segment.bounce&&!segment.bounce.didPush)return null;
 const base=segment.sample,start=segment.airStart,pelvis=names.indexOf('pelvis');
 if(e.pose==='keep'){
  // A real support/push may replace the incoming articulation before release.
  // Re-enter the retained pose then, continuing its existing wobble clock.
  const inherited=segment.inheritedPose,priorMotion=inherited?.heldPoseMotion?.motion||inherited?.poseMotion;
  if(!base(start).airPoseBase&&inherited?.airPoseBase&&C.poseNames[inherited.jumpMotion?.pose])return create({...event,pose:inherited.jumpMotion.pose},{...segment,poseClock:priorMotion?.startedAt},jumps,names,parents,settings);
  return {start,event:e,sample(time,...args){
  const frame=base(time,...args),held=frame.heldPoseMotion;
  if(time<start||frame.poseMotion||!held||!frame.airPoseBase)return frame;
  // Continue the same pose clock/filter. Remove the previous carrier's applied
  // variation before the new carrier evaluates it from its own angular speed.
  return {...frame,pose:held.motion.undo(frame.pose,held.speed,held.motion.mask).pose,poseMotion:{...held.motion,continued:true}};
 }};}
 if(e.pose==='none'){
  // A later marker explicitly clears the held pose. Restore the ongoing base
  // articulation in the current pelvis frame, never the previous world pose.
  const initial=base(start);if(!initial.airPoseBase)return null;
  const tuning=C.poseSettings(settings,initial.jumpMotion?.pose),timing=blendTiming(initial.pose,initial.airPoseBase,parents,pelvis,e.poseOut,tuning.blendDistance??1);
  const weightsAt=transitionWeights(initial.pose,initial.airPoseBase,parents,settings);
  const values=time=>({pose:'none',poseWeight:1-transitionProgress((time-start)/timing.duration,settings)});
  return {start,event:e,values,...timing,sample(time,...args){
   const frame=base(time,...args);if(time<=start||!frame.airPoseBase)return frame;
   const motion=values(time),weights=weightsAt(1-motion.poseWeight),local=R.localize(frame.pose.points,frame.pose.q,parents),unposedPelvis=qm(frame.pose.q[pelvis],frame.airPosePelvisOffset||[0,0,0,1]);
   for(let i=1;i<names.length;i++)if(i!==pelvis)local.q[i]=qslerp(local.q[i],frame.airPoseBase[i],weights[i]);
   const pelvisQ=qslerp(frame.pose.q[pelvis],unposedPelvis,1-motion.poseWeight);local.q[pelvis]=qm(qinv(frame.pose.q[parents[pelvis]]),pelvisQ);
   const active=motion.poseWeight>0,pose={...frame.pose,...R.fk(local,parents),authoredPose:active,attackFree:active||!!frame.attack};
   return {...frame,pose,airPoseBase:active?frame.airPoseBase:null,airPosePelvisOffset:active?qm(qinv(pelvisQ),unposedPelvis):null,poseMotion:null,heldPoseMotion:null,jumpMotion:{...frame.jumpMotion,...motion,poseSpeed:0,poseVariant:0,poseResponse:0}};
  }};
 }
 if(!poses||names.some((n,i)=>n!==library.names[i]||parents[i]!==library.parents[i]))throw Error('Authored pose rig mismatch');
 const clip=poses.find(p=>p.id===e.pose),tuning=C.poseSettings(settings,e.pose);
 const variantFor=speed=>(speed>=0)!==!!settings.invertPoseVariants?clip.positiveFrame:clip.negativeFrame;
 const wobble=falling(jumps,parents),wobbleStart=segment.poseClock??start,limbs=names.map(n=>/^(clavicle|upperarm|lowerarm|hand|thigh|calf|foot|ball)_/.test(n));
 const initial=base(start),speed=dot(initial.spin?.omega||[0,0,0],rotate(initial.pose.q[pelvis],[1,0,0]))/rad,amount=clamp(Math.abs(speed)/tuning.responseSpeed),variant=variantFor(speed);
 const waves=tuning.wobbleAmplitude>0&&tuning.wobbleSpeed>0?wobble.sample((start-wobbleStart)*tuning.wobbleSpeed):null;
 const destination=clip.locals[clip.neutralFrame].q.map((q,i)=>{const turn=qslerp(q,clip.locals[variant].q[i],amount);return waves&&limbs[i]?qm(turn,qexp(mul(waves[i],tuning.wobbleAmplitude))):turn;});
 const timing=blendTiming(initial.pose,destination,parents,pelvis,tuning.blendIn??e.poseIn,tuning.blendDistance??1);
 const weightsAt=transitionWeights(initial.pose,destination,parents,settings);
 function values(time){return {pose:e.pose,poseWeight:transitionProgress((time-start)/timing.duration,settings)};}
 function sample(time,...args){
  const frame=base(time,...args),motion=values(time),weight=motion.poseWeight,weights=weightsAt(weight);if(weight<=0)return frame;
  const local=R.localize(frame.pose.points,frame.pose.q,parents),neutral=clip.locals[clip.neutralFrame].q;
  const waves=tuning.wobbleAmplitude>0&&tuning.wobbleSpeed>0?wobble.sample((time-wobbleStart)*tuning.wobbleSpeed):null;
  const wobbleQ=(q,i)=>waves&&limbs[i]?qm(q,qexp(mul(waves[i],tuning.wobbleAmplitude))):q;
  const target=neutral.map(wobbleQ),unmodified=local.q.slice();
  // The pose is articulation below the live pelvis. Source pelvis/root
  // orientation must never replace the flight or flip orientation.
  for(let i=1;i<names.length;i++)if(i!==pelvis)local.q[i]=qslerp(unmodified[i],target[i],weights[i]);
  // Hold the incoming pelvis basis, not the FBX pelvis. Otherwise the idle
  // loop keeps swaying the whole held pose even with additive wobble at zero.
  // Spin/physical carrier rotation is applied downstream and remains active.
  const pelvisQ=qslerp(frame.pose.q[pelvis],initial.pose.q[pelvis],weight),unposedPelvis=qm(frame.pose.q[pelvis],frame.airPosePelvisOffset||[0,0,0,1]);
  local.q[pelvis]=qm(qinv(frame.pose.q[parents[pelvis]]),pelvisQ);
  // Keep authored ranges through both target projection and optional spin recoil.
  const neutralBlended=local.q.slice(),pose={...frame.pose,...R.fk(local,parents),attackFree:true,authoredPose:true};
  const response=(candidate,speed,mask,inverse=false)=>{
   const amount=clamp(Math.abs(speed)/tuning.responseSpeed),variant=variantFor(speed);
   if(amount<1e-12)return {pose:candidate,poseSpeed:speed,poseVariant:clip.neutralFrame,poseResponse:0};
   const altered=R.localize(candidate.points,candidate.q,parents),extreme=clip.locals[variant].q;
   for(let i=1;i<names.length;i++)if(i!==pelvis&&mask[i]>0){const goal=wobbleQ(qslerp(neutral[i],extreme[i],amount),i),blended=qslerp(unmodified[i],goal,weights[i]),delta=qm(blended,qinv(neutralBlended[i])),turn=qslerp([0,0,0,1],delta,mask[i]);altered.q[i]=qm(inverse?qinv(turn):turn,altered.q[i]);}
   return {pose:{...candidate,...R.fk(altered,parents)},poseSpeed:speed,poseVariant:variant,poseResponse:amount};
  };
  return {...frame,pose,airPoseBase:frame.airPoseBase||unmodified,airPosePelvisOffset:qm(qinv(pelvisQ),unposedPelvis),jumpMotion:{...frame.jumpMotion,...motion,poseSpeed:0,poseVariant:clip.neutralFrame,poseResponse:0},poseMotion:{key:e.pose+'/'+start,startedAt:wobbleStart,responseTime:tuning.responseTime??.15,responseSpeed:tuning.responseSpeed,applySpeed:response,undo:(candidate,speed,mask)=>response(candidate,speed,mask,true),apply:(candidate,omega,mask)=>response(candidate,dot(omega,rotate(candidate.q[pelvis],[1,0,0]))/rad,mask),mask:names.map((_,i)=>i&&i!==pelvis?1:0)}};
 }
 return {sample,values,start,event:e,clip,tuning,...timing};
}
const api={create,ease,poseWeight,transitionProgress,jointProgress,configure,restrict,get poses(){return poses;}};if(node)module.exports=api;else root.BodyflipJumpMotion=api;
})(globalThis);
