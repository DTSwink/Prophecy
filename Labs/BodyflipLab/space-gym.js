/* Zero-gravity marker sequence: no contacts, no NN requests, constant drift. */
(function(root){
'use strict';
const node=typeof module!=='undefined',R=node?require('./recovery.js'):root.Recovery,C=node?require('./core.js'):root.BodyflipCore,M=node?require('./jump-motion.js'):root.BodyflipJumpMotion,A=node?require('./jump-attack.js'):root.BodyflipJumpAttack,O=node?require('./spin.js'):root.BodyflipSpin,D=node?require('./mass.js'):root.BodyflipMass;
function action(event,sample){return {event,sample,supportStart:event.time,jumpStart:event.time,airStart:event.time,abortTime:Infinity,release:0,matchDistance:null,supportScores:[],support:{frames:[],terminal:{}},animationLeg:()=>null,coneDebug:()=>null,idealDebug:()=>null,pushDebug:()=>null};}
function sequence(run,jumps,settings,parents,events,catalog,reference=run.poses[0]){
 const segments=[],results=[],rig=D.model(run.names,parents,reference);
 let previous=t=>{const pose=run.sample?run.sample(t):run.poses[0];const delta=R.sub([0,1.2,0],pose.points[0]);return {pose:{...pose,points:pose.points.map(p=>R.add(p,delta))},root:[0,1.2,0],velocity:[0,0,0],phase:'SPACE',vy:0,speed:0,airTime:0};};
 if(settings.airFlip){const spin=O.create(previous,{start:0,event:{spinVersion:2},settings,names:run.names,parents,reference});previous=spin.sample;previous.atOrientation=spin.atOrientation;}
 const clip=jumps.find(c=>c.name.includes('_Start_Stand_')),height=Math.max(...clip.poses.map(p=>p.points[0][1]))-Math.min(...clip.poses.map(p=>p.points[0][1])),normalSpeed=Math.sqrt(2*9.81*height);
 for(const event of events){
  const e=C.sanitizeJump(event),prior=previous,impulse=[0,normalSpeed*Math.sqrt(e.jumpPercent/100),0];
  const inherited=prior(event.time).spin||null,origin=inherited?.rotation||[0,0,0,1];
  const segment=action(event,t=>{const f=prior.atOrientation&&t>=event.time?prior.atOrientation(t,origin):O.rebase(prior(t),origin,rig);if(t<event.time)return f;const age=t-event.time,delta=R.mul(impulse,age),velocity=R.add(f.velocity||[0,0,0],impulse),root=R.add(f.root,delta);return {...f,pose:{...f.pose,points:f.pose.points.map(p=>R.add(p,delta))},root,velocity,vy:velocity[1],airTime:age};});
  segment.motion=M.create(event,segment,jumps,run.names,parents,settings);if(segment.motion)segment.sample=segment.motion.sample;
  segment.attack=A.create(event,segment,catalog,run.names,parents,settings,reference);if(segment.attack)segment.sample=segment.attack.sample;
  segment.spin=O.create(segment.sample,{start:event.time,commandTime:event.time,event,settings,names:run.names,parents,reference,inherited});segment.sample=segment.spin.sample;
  segment.pushDebug=t=>e.jumpPercent>0&&t>=event.time&&t<event.time+3/60?{origin:segment.sample(event.time).pose.points[1],direction:[0,1,0]}:null;
  // Planning and overlapping return blends often ask for the same source frame.
  // Keep a bounded window large enough for overlapping 60 ms lookahead.
  // Nanosecond keys merge floating-point representations of the same tick.
  const sample=segment.sample,cache=new Map();segment.sample=t=>{const key=Math.round(t*1e9);if(cache.has(key))return cache.get(key);const frame=sample(t);cache.set(key,frame);if(cache.size>256)cache.delete(cache.keys().next().value);return frame;};
  segment.sample.atOrientation=segment.spin.atOrientation;segments.push(segment);previous=segment.sample;
  results.push({...event,status:'Space',reason:e.jumpPercent+'% push',pushTime:event.time,releaseTime:event.time});
 }
 const activeAt=t=>segments.findLast(s=>t>=s.supportStart)||null;
 const sample=t=>previous(t);
 return {sample,segments,events:results,surfaces:[],landings:[],edge:5,speed:0,activeAt,airStartAt:t=>activeAt(t)?.airStart??Infinity,
  animationLeg:()=>null,coneDebug:()=>null,idealDebug:()=>null,pushDebug:t=>activeAt(t)?.pushDebug(t)||null};
}
const api={sequence,action};if(node)module.exports=api;else root.BodyflipSpace=api;
})(globalThis);
