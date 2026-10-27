/* Zero-gravity marker sequence: no contacts, no NN requests, constant drift. */
(function(root){
'use strict';
const node=typeof module!=='undefined',R=node?require('./recovery.js'):root.Recovery,C=node?require('./core.js'):root.BodyflipCore,M=node?require('./jump-motion.js'):root.BodyflipJumpMotion,A=node?require('./jump-attack.js'):root.BodyflipJumpAttack;
function action(event,sample){return {event,sample,supportStart:event.time,jumpStart:event.time,airStart:event.time,abortTime:Infinity,release:0,matchDistance:null,supportScores:[],support:{frames:[],terminal:{}},animationLeg:()=>null,coneDebug:()=>null,idealDebug:()=>null,pushDebug:()=>null};}
function sequence(run,jumps,settings,parents,events,catalog,reference=run.poses[0]){
 const segments=[],results=[];
 let previous=t=>{const pose=run.sample?run.sample(t):run.poses[0];const delta=R.sub([0,1.2,0],pose.points[0]);return {pose:{...pose,points:pose.points.map(p=>R.add(p,delta))},root:[0,1.2,0],velocity:[0,0,0],phase:'SPACE',vy:0,speed:0,airTime:0};};
 const clip=jumps.find(c=>c.name.includes('_Start_Stand_')),height=Math.max(...clip.poses.map(p=>p.points[0][1]))-Math.min(...clip.poses.map(p=>p.points[0][1])),normalSpeed=Math.sqrt(2*9.81*height);
 for(const event of events){
  const e=C.sanitizeJump(event),prior=previous,impulse=[0,normalSpeed*Math.sqrt(e.jumpPercent/100),0];
  const segment=action(event,t=>{const f=prior(t);if(t<event.time)return f;const age=t-event.time,delta=R.mul(impulse,age),velocity=R.add(f.velocity||[0,0,0],impulse),root=R.add(f.root,delta);return {...f,pose:{...f.pose,points:f.pose.points.map(p=>R.add(p,delta))},root,velocity,vy:velocity[1],airTime:age};});
  segment.motion=M.create(event,segment,jumps,run.names,parents,settings);if(segment.motion)segment.sample=segment.motion.sample;
  segment.attack=A.create(event,segment,catalog,run.names,parents,settings,reference);if(segment.attack)segment.sample=segment.attack.sample;
  segment.pushDebug=t=>e.jumpPercent>0&&t>=event.time&&t<event.time+3/60?{origin:segment.sample(event.time).pose.points[1],direction:[0,1,0]}:null;
  // Planning and overlapping return blends often ask for the same source frame.
  // Keep a bounded window large enough for overlapping 60 ms lookahead.
  // Nanosecond keys merge floating-point representations of the same tick.
  const sample=segment.sample,cache=new Map();segment.sample=t=>{const key=Math.round(t*1e9);if(cache.has(key))return cache.get(key);const frame=sample(t);cache.set(key,frame);if(cache.size>256)cache.delete(cache.keys().next().value);return frame;};
  segments.push(segment);previous=segment.sample;
  results.push({...event,status:'Space',reason:e.jumpPercent+'% push',pushTime:event.time,releaseTime:event.time});
 }
 const activeAt=t=>segments.findLast(s=>t>=s.supportStart)||null;
 function sample(t){
  const frame=previous(t),active=activeAt(t);
  if(!settings.airFlip||!active||active.motion?.turns)return frame;
  const age=Math.max(0,t-active.airStart),flip=settings.flipAngle+settings.flipSpeed*age,twist=settings.twistAngle+settings.twistSpeed*age;
  const rotation=C.orientation(flip,twist,settings.axis,frame.pose.q[1]),pose=C.centerPose(frame.pose,rotation,frame.pose.points[1]);pose.points[0]=frame.root;
  const delta=R.qm(rotation,R.qinv(frame.pose.q[1]));pose.q[0]=R.qm(delta,frame.pose.q[0]);pose.axes[0]=R.toAxes(pose.q[0]);
  return {...frame,pose,jumpMotion:{...frame.jumpMotion,flip,twist}};
 }
 return {sample,segments,events:results,surfaces:[],landings:[],edge:5,speed:0,activeAt,airStartAt:t=>activeAt(t)?.airStart??Infinity,
  animationLeg:()=>null,coneDebug:()=>null,idealDebug:()=>null,pushDebug:t=>activeAt(t)?.pushDebug(t)||null};
}
const api={sequence,action};if(node)module.exports=api;else root.BodyflipSpace=api;
})(globalThis);
