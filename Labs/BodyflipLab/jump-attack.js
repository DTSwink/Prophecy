/* Vanilla upper-body attack. Final Harness pre-Armed entry, then authored time. */
(function(root){
'use strict';
const node=typeof module!=='undefined',R=node?require('./recovery.js'):root.Recovery,C=node?require('./core.js'):root.BodyflipCore,H=node?require('./attack-inertia.js'):root.BodyflipAttackInertia,K=node?require('./kick-attack.js'):root.BodyflipKickAttack,T=node?require('./throw-attack.js'):root.BodyflipThrowAttack;
const clamp=x=>Math.max(0,Math.min(1,x)),smooth=x=>{x=clamp(x);return x*x*(3-2*x);};
const Joint=node?require('./joint-rig.js'):root.BodyflipJointRig,Entry=node?require('./attack-entry.js'):root.BodyflipAttackEntry;
const labels={...T.labels,headbutt:'Headbutt',hookL:'Hook L',hookR:'Hook R',jabL:'Jab L',jabR:'Jab R',KickL:'Kick L',KickR:'Kick R',overL:'Over L',overR:'Over R',pike:'Pike',slashL:'Slash L',slashLD:'Slash LD',slashLU:'Slash LU',slashR:'Slash R',slashRD:'Slash RD',slashRU:'Slash RU',sweepKick:'Sweep kick'};
function bones(names,parents){const spine=names.indexOf('spine_01');return names.map((_,i)=>i).filter(i=>{for(let j=i;j>=0;j=parents[j])if(j===spine)return true;return false;});}
function at(clip,frame,parents){
 clip.locals ||= clip.poses.map(p=>R.localize(p.points,p.q,parents));
 const f=Math.max(0,Math.min(clip.poses.length-1,frame)),i=Math.min(clip.poses.length-2,Math.floor(f)),u=f-i,a=clip.locals[i],b=clip.locals[i+1];
 return {p:a.p.map((p,j)=>R.add(p,R.mul(R.sub(b.p[j],p),u))),q:a.q.map((q,j)=>R.qslerp(q,b.q[j],u))};
}
// Fold the authored pelvis delta into its first spine child. Quaternion order
// matters: referencePelvis * correctedSpine = sourcePelvis * sourceSpine.
// Root/world facing and pelvis translation are deliberately not transferred.
function carryPelvis(target,reference,spine,parents){
 const pelvis=parents[spine],q=target.q.slice();
 q[spine]=R.qm(R.qm(R.qinv(reference.q[pelvis]),target.q[pelvis]),target.q[spine]);
 return {...target,q};
}
function attackAt(clip,frame,names,parents){
 const target=at(clip,frame,parents);
 return carryPelvis(target,clip.locals[0],names.indexOf('spine_01'),parents);
}
// Prepare legal arm endpoints before blending. An authored forearm may contain
// axial rotation that our elbow hinge cannot reproduce. Blending that raw
// rotation first can pass through the hinge projection's 180-degree singularity.
function armTrack(clip,names,parents,reference){
 const joints=Joint.create(names,parents,reference),arms=names.map((n,i)=>/^(clavicle|upperarm|lowerarm|hand)_/.test(n)?i:-1).filter(i=>i>=0);
 const frames=clip.poses.map((_,frame)=>{const legal=joints.project(R.fk(attackAt(clip,frame,names,parents),parents));return R.localize(legal.points,legal.q,parents).q;});
 return frame=>{const f=Math.max(0,Math.min(frames.length-1,frame)),i=Math.min(frames.length-2,Math.floor(f)),u=f-i,target=attackAt(clip,f,names,parents),q=target.q.slice();for(const j of arms)q[j]=R.qslerp(frames[i][j],frames[i+1][j],u);return {...target,q};};
}
function overlay(pose,target,indices,parents,amount=1){
 const local=R.localize(pose.points,pose.q,parents);
 // Hierarchy-local axes, as standaloneBlendPoseLocalAxes in Final Harness.
 // FK preserves the lab's actual sockets/lengths instead of lerping world points.
 for(const i of indices)local.q[i]=R.qslerp(local.q[i],target.q[i],amount);
 return R.fk(local,parents);
}
// Current pose directly to Armed, in hierarchy-local axes. The endpoint
// derivatives come only from Armed onward; no recorded pre-Armed pose is used.
function directEntry(options){const {clip}=options;return Entry.direct({...options,armed:clip.meta.phases.armed,fps:clip.meta.fps});}
// Full attack-added spine rotation in the underlying pelvis frame. Upper
// world orientation is restored after applying the opposite pelvis rotation.
function compensate(pose,baseline,names,parents,amount){
 if(!(amount>0))return pose;
 const spine=names.indexOf('spine_01'),pelvis=parents[spine],local=R.localize(pose.points,pose.q,parents);
 const base=R.qm(R.qinv(baseline.q[pelvis]),baseline.q[spine]);
 const delta=R.qm(local.q[spine],R.qinv(base)),counter=R.qexp(R.mul(R.qlog(delta),-clamp(amount)));
 local.q[pelvis]=R.qm(local.q[pelvis],counter);
 local.q[spine]=R.qm(R.qinv(counter),local.q[spine]);
 return R.fk(local,parents);
}
function create(event,segment,catalog,names,parents,settings,reference=null,{wholeLeg=true,modifyPose=null}={}){
 const e=C.sanitizeJump(event),clip=catalog?.get(e.attack);
 if(e.attack==='none'||!Number.isFinite(segment.airStart)||segment.jumpStart>=segment.abortTime||segment.bounce&&!segment.bounce.didPush)return null;
 if(T.accepts(e.attack))return T.create(event,segment,catalog,names,parents,settings,reference);
 if(!clip)throw Error('Missing vanilla attack: '+e.attack);
 if(K.accepts(e.attack)){
  const start=segment.airStart+e.attackDelay,base=segment.sample;
  const kick=K.create({clip,names,parents,reference:reference||clip.poses[0],base:t=>base(t).pose,start,lead:e.attackIn,tail:e.attackOut,directArmed:settings.kickToArmed});
  const duration=kick.plan.track.armedTime,sourceFrame=kick.plan.track.sourceFrame;
  return {...kick,match:0,score:0,duration,sourceFrame,indices:names.map((_,i)=>i).slice(1),sample(time,...args){
   const frame=base(time,...args);if(time<start||time>=kick.returnEnd)return frame;
   return {...frame,pose:kick.sample(time),attack:{name:e.attack,phase:time>=kick.end?'RETURN':time<start+duration?'ARM':'ATTACK',sourceFrame:Math.min(clip.poses.length-1,sourceFrame(time-start)),matchedFrame:0,armedTime:start+duration,start,end:kick.end}};
  }};
 }

 const base=segment.sample,start=segment.airStart+e.attackDelay,indices=bones(names,parents),fps=clip.meta.fps,armed=clip.meta.phases.armed;
 const targetAt=armTrack(clip,names,parents,reference||clip.poses[0]);
 const initial=base(start).pose,from=R.localize(initial.points,initial.q,parents);
 // Match the transferred upper pose, including authored pelvis rotation at spine_01.
 let match=0,score=Infinity;
 if(!settings.kickToArmed)for(let f=0;f<=Math.ceil(armed);f++){const frame=Math.min(armed,f),target=targetAt(frame),d=indices.reduce((sum,i)=>sum+R.length(R.qlog(R.qm(R.qinv(from.q[i]),target.q[i])))**2,0);if(d<score){score=d;match=frame;}}
 if(settings.kickToArmed){match=armed;score=0;}
 const arming=settings.kickToArmed?Entry.plan({from,targetAt,armed,fps,indices,names,minimum:e.attackIn}):null;
 const duration=arming?.duration??Math.max(e.attackIn,(armed-match)/fps,1/60),end=start+duration+(clip.poses.length-1-armed)/fps,hitTime=start+duration+(clip.meta.phases.hit-armed)/fps,returnEnd=end+e.attackOut;
 function sourceFrame(age){return age<duration?match+(armed-match)*clamp(age/duration):armed+(age-duration)*fps;}
 const direct=settings.kickToArmed?directEntry({base,start,duration,clip,names,parents,indices,targetAt}):null;
 function entry(time,frame=base(time)){
  if(direct&&time<start+duration)return direct(time,frame);
  const age=time-start,target=targetAt(sourceFrame(age));
  // Final Harness standaloneIndependentStartPoseAt + standalonePlannedEasyEntry:
  // continuing start motion blends into the moving pre-Armed source; Armed->End
  // advances one source frame per authored frame. Smooth weight avoids entry stops.
  return overlay(frame.pose,target,indices,parents,smooth(age/duration));
 }
 let exit=null;const returning=t=>(exit ||= C.transition(t=>entry(end+t),t=>base(end+t).pose,e.attackOut,parents,indices,true))(t);
 function uncorrected(time,frame=base(time)){
  if(time<start||time>=end+e.attackOut)return frame.pose;
  const returned=time>=end?returning(time-end):null;
  const pose=time<end?entry(time,frame):overlay(frame.pose,R.localize(returned.points,returned.q,parents),indices,parents);
  return modifyPose?modifyPose(time,pose):pose;
 }
 const amount=settings.pelvisAttackCompensation??C.defaults.pelvisAttackCompensation,legal=H.createProjection(names,parents,reference||clip.poses[0]);
 const choreography=settings.softAttackLegs&&amount>0?H.referenceMotion({clip,names,parents,reference:reference||clip.poses[0],start,armedTime:start+duration,hitTime:start+duration+(clip.meta.phases.hit-armed)/fps,end,returnEnd:end+e.attackOut,amount}):null;
 const inertia=settings.softAttackLegs&&amount>0?H.create({amount,wholeLeg,choreography,source:uncorrected,base:t=>base(t).pose,target:(t,raw,baseline)=>compensate(raw||uncorrected(t),baseline||base(t).pose,names,parents,amount),start,end:end+e.attackOut,recoveryStart:end,recoveryEnd:end+e.attackOut,names,parents,reference:reference||clip.poses[0]}):null;
 const displayed=(time,frame=base(time))=>{const raw=uncorrected(time,frame);return inertia?inertia.sample(time,raw):amount>0?legal(compensate(legal(raw),legal(frame.pose),names,parents,amount)):raw;};
 const recovery=R.pelvisReturn({source:displayed,base:t=>base(t).pose,parents,start:hitTime,end:returnEnd,pelvis:names.indexOf('pelvis')});
 function sample(time,...args){
  const frame=base(time,...args);
  if(time<start)return frame;
  if(time>=returnEnd)return frame;
  const pose=time<=hitTime?displayed(time,frame):amount>0?legal(recovery.sample(time)):recovery.sample(time);
  const age=time-start;
  return {...frame,pose,attack:{name:e.attack,phase:time>=end?'RETURN':age<duration?'ARM':'ATTACK',sourceFrame:Math.min(clip.poses.length-1,sourceFrame(age)),matchedFrame:match,armedTime:start+duration,start,end}};
 }
 return {sample,start,end,hitTime,returnEnd,recovery,match,score,duration,sourceFrame,indices,inertia,arming};
}
const api={create,directEntry,at,attackAt,armTrack,carryPelvis,compensate,bones,overlay,labels};if(node)module.exports=api;else root.BodyflipJumpAttack=api;
})(globalThis);
