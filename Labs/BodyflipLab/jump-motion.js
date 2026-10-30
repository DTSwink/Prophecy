/* Per-jump air choreography. Stateless sampling; contacts/root stay with flight. */
(function(root){
'use strict';
const R=typeof module!=='undefined'?require('./recovery.js'):root.Recovery;
const C=typeof module!=='undefined'?require('./core.js'):root.BodyflipCore;
const rad=Math.PI/180,clamp=x=>Math.max(0,Math.min(1,x));
const ease=x=>{x=clamp(x);return x*x*x*(10+x*(-15+6*x));};
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
 const e=C.sanitizeJump(event);
 if(e.pose==='none'||!Number.isFinite(segment.airStart)||segment.jumpStart>=segment.abortTime||segment.bounce&&!segment.bounce.didPush)return null;
 const base=segment.sample,start=segment.airStart,pelvis=names.indexOf('pelvis');
 const target=e.pose==='none'?null:placeholders(jumps,parents).find(p=>p.id===e.pose).local;
 function values(time){return {pose:e.pose,poseWeight:poseWeight(time-start,e)};}
 function sample(time,flip=0,twist=0,legacyAxis=settings.axis){
  const frame=base(time,flip,twist,legacyAxis);
  if(time<=start)return frame;
  const motion=values(time);let pose=frame.pose;
  if(target&&motion.poseWeight>0){
   const local=R.localize(pose.points,pose.q,parents);
   // Rotations only: preserve all bone lengths, pelvis/root and hip sockets.
   for(let i=0;i<names.length;i++)if(i!==0&&i!==pelvis)local.q[i]=R.qslerp(local.q[i],target.q[i],motion.poseWeight);
   pose=R.fk(local,parents);
  }
  return {...frame,pose,jumpMotion:{...motion,flip,twist}};
 }
 return {sample,values,start,event:e};
}
const api={create,ease,poseWeight,placeholders};if(typeof module!=='undefined')module.exports=api;else root.BodyflipJumpMotion=api;
})(globalThis);
