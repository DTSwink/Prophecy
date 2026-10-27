/* Per-jump air choreography. Stateless sampling; contacts/root stay with flight. */
(function(root){
'use strict';
const R=typeof module!=='undefined'?require('./recovery.js'):root.Recovery;
const C=typeof module!=='undefined'?require('./core.js'):root.BodyflipCore;
const rad=Math.PI/180,clamp=x=>Math.max(0,Math.min(1,x));
// Zero velocity and acceleration at both ends, with unwrapped scalar angles.
const ease=x=>{x=clamp(x);return x*x*x*(10+x*(-15+6*x));};
function turnProgress(time,event){
 const duration=event.turnDuration;
 if(time<=0)return 0;if(time>=duration)return 1;
 const fit=Math.min(1,duration/(event.turnIn+event.turnOut||1));
 const entry=event.turnIn*fit,exit=event.turnOut*fit,area=duration-(entry+exit)*7/15;
 // Integral of a smooth speed ramp, with constant speed between the ramps.
 // Equal half-duration ramps are exactly the former quintic progress curve.
 const integral=u=>u*u*u*(4/3-u+u*u/5);
 if(entry>0&&time<entry)return entry*integral(time/entry)/area;
 if(exit>0&&time>duration-exit)return 1-exit*integral((duration-time)/exit)/area;
 return (entry*8/15+time-entry)/area;
}
const slots=new WeakMap();
function placeholders(jumps,parents){
 let poses=slots.get(jumps);if(poses)return poses;
 const stand=jumps.find(c=>c.name.includes('_Start_Stand_'));
 const run=jumps.find(c=>c.name.includes('_Start_Run_'));
 const fall=jumps.find(c=>c.name.endsWith('_Loop_Fall'));
 // Temporary source snapshots, deliberately separate from the pose-slot IDs.
 // Replace these four targets when the user supplies the authored poses.
 poses=[ [stand,.45], [run,.4], [stand,.12], [fall,.5] ].map(([clip,fraction],i)=>{
  if(!clip)throw Error('Missing placeholder pose source');
  const frame=Math.round((clip.poses.length-1)*fraction);
  return {id:'pose'+(i+1),source:clip.name,frame,local:R.localize(clip.poses[frame].points,clip.poses[frame].q,parents)};
 });
 slots.set(jumps,poses);return poses;
}
function poseWeight(age,event){
 if(age<=0||event.pose==='none')return 0;
 if(age<event.poseIn)return ease(age/event.poseIn);
 const outStart=event.poseIn+event.poseHold;
 if(age<=outStart)return 1;
 return 1-ease((age-outStart)/event.poseOut);
}
function create(event,segment,jumps,names,parents,settings){
 const e=C.sanitizeJump(event),turns=e.flip!==0||e.twist!==0;
 if((!turns&&e.pose==='none')||!Number.isFinite(segment.airStart)||segment.jumpStart>=segment.abortTime||segment.bounce&&!segment.bounce.didPush)return null;
 const base=segment.sample,start=segment.airStart,pelvis=names.indexOf('pelvis');
 const target=e.pose==='none'?null:placeholders(jumps,parents).find(p=>p.id===e.pose).local;
 // Capture root heading before release, excluding the pelvis' gait sway.
 const rootRotation=base(Math.max(segment.jumpStart,start-1e-7)).pose.q[0];
 const direction=R.rotate(rootRotation,[0,0,1]);
 const heading=R.qexp([0,Math.hypot(direction[0],direction[2])>1e-7?Math.atan2(direction[0],direction[2]):0,0]);
 const axis=R.rotate(heading,C.flipAxis(e.turnAxis??settings.axis));
 function values(time){
  const age=time-start,u=turnProgress(age-e.turnDelay,e);
  return {flip:e.flip*u,twist:e.twist*u,pose:e.pose,poseWeight:poseWeight(age,e),axis:turns?axis:null};
 }
 function sample(time,flip=0,twist=0,legacyAxis=settings.axis){
  const frame=base(time,turns?0:flip,turns?0:twist,legacyAxis);
  if(time<=start)return frame;
  const motion=values(time);let pose=frame.pose;
  if(target&&motion.poseWeight>0){
   const local=R.localize(pose.points,pose.q,parents);
   // Rotations only: preserve all bone lengths, pelvis/root and hip sockets.
   for(let i=0;i<names.length;i++)if(i!==0&&i!==pelvis)local.q[i]=R.qslerp(local.q[i],target.q[i],motion.poseWeight);
   pose=R.fk(local,parents);
  }
  if(turns){
   const rotation=R.qm(R.qm(R.qexp(R.mul(axis,motion.flip*rad)),pose.q[pelvis]),R.qexp([motion.twist*rad,0,0]));
   const rootQ=R.qm(R.qm(rotation,R.qinv(pose.q[pelvis])),pose.q[0]);
   pose=C.centerPose(pose,rotation,pose.points[pelvis]);pose.points[0]=frame.root;
   pose.q[0]=rootQ;pose.axes[0]=R.toAxes(rootQ);
  }
  return {...frame,pose,jumpMotion:turns?motion:{...motion,flip,twist}};
 }
 return {sample,values,start,turns,event:e};
}
const api={create,ease,turnProgress,poseWeight,placeholders};if(typeof module!=='undefined')module.exports=api;else root.BodyflipJumpMotion=api;
})(globalThis);
