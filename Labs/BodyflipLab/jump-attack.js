/* Vanilla upper-body attack. Final Harness pre-Armed entry, then authored time. */
(function(root){
'use strict';
const node=typeof module!=='undefined',R=node?require('./recovery.js'):root.Recovery,C=node?require('./core.js'):root.BodyflipCore,H=node?require('./attack-inertia.js'):root.BodyflipAttackInertia;
const clamp=x=>Math.max(0,Math.min(1,x)),smooth=x=>{x=clamp(x);return x*x*(3-2*x);};
const labels={headbutt:'Headbutt',hookL:'Hook L',hookR:'Hook R',jabL:'Jab L',jabR:'Jab R',KickL:'Kick L',KickR:'Kick R',overL:'Over L',overR:'Over R',pike:'Pike',slashL:'Slash L',slashLD:'Slash LD',slashLU:'Slash LU',slashR:'Slash R',slashRD:'Slash RD',slashRU:'Slash RU'};
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
function overlay(pose,target,indices,parents,amount=1){
 const local=R.localize(pose.points,pose.q,parents);
 // Hierarchy-local axes, as standaloneBlendPoseLocalAxes in Final Harness.
 // FK preserves the lab's actual sockets/lengths instead of lerping world points.
 for(const i of indices)local.q[i]=R.qslerp(local.q[i],target.q[i],amount);
 return R.fk(local,parents);
}
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
function create(event,segment,catalog,names,parents,settings,reference=null,{wholeLeg=true}={}){
 const e=C.sanitizeJump(event),clip=catalog?.get(e.attack);
 if(e.attack==='none'||!Number.isFinite(segment.airStart)||segment.jumpStart>=segment.abortTime||segment.bounce&&!segment.bounce.didPush)return null;
 if(!clip)throw Error('Missing vanilla attack: '+e.attack);
 const base=segment.sample,start=segment.airStart+e.attackDelay,indices=bones(names,parents),fps=clip.meta.fps,armed=clip.meta.phases.armed;
 const initial=base(start).pose,from=R.localize(initial.points,initial.q,parents);
 // Match the transferred upper pose, including authored pelvis rotation at spine_01.
 let match=0,score=Infinity;
 for(let f=0;f<=Math.ceil(armed);f++){const frame=Math.min(armed,f),target=attackAt(clip,frame,names,parents),d=indices.reduce((sum,i)=>sum+R.length(R.qlog(R.qm(R.qinv(from.q[i]),target.q[i])))**2,0);if(d<score){score=d;match=frame;}}
 const duration=Math.max(e.attackIn,(armed-match)/fps,1/60),end=start+duration+(clip.poses.length-1-armed)/fps;
 function sourceFrame(age){return age<duration?match+(armed-match)*clamp(age/duration):armed+(age-duration)*fps;}
 function entry(time,frame=base(time)){
  const age=time-start,target=attackAt(clip,sourceFrame(age),names,parents);
  // Final Harness standaloneIndependentStartPoseAt + standalonePlannedEasyEntry:
  // continuing start motion blends into the moving pre-Armed source; Armed->End
  // advances one source frame per authored frame. Smooth weight avoids entry stops.
  return overlay(frame.pose,target,indices,parents,smooth(age/duration));
 }
 let exit=null;const returning=t=>(exit ||= C.transition(t=>entry(end+t),t=>base(end+t).pose,e.attackOut,parents,indices,true))(t);
 function uncorrected(time,frame=base(time)){
  if(time<start||time>=end+e.attackOut)return frame.pose;
  const returned=time>=end?returning(time-end):null;
  return time<end?entry(time,frame):overlay(frame.pose,R.localize(returned.points,returned.q,parents),indices,parents);
 }
 const amount=settings.pelvisAttackCompensation??C.defaults.pelvisAttackCompensation;
 const choreography=settings.softAttackLegs&&amount>0?H.referenceMotion({clip,names,parents,reference:reference||clip.poses[0],start,armedTime:start+duration,hitTime:start+duration+(clip.meta.phases.hit-armed)/fps,end,returnEnd:end+e.attackOut,amount}):null;
 const inertia=settings.softAttackLegs&&amount>0?H.create({amount,wholeLeg,choreography,source:uncorrected,base:t=>base(t).pose,target:(t,raw,baseline)=>compensate(raw||uncorrected(t),baseline||base(t).pose,names,parents,amount),start,end:end+e.attackOut,names,parents,reference:reference||clip.poses[0]}):null;
 function sample(time,...args){
  const frame=base(time,...args);
  if(time<start)return frame;
  const active=time<end+e.attackOut,raw=uncorrected(time,frame),pose=inertia?inertia.sample(time,raw):active?compensate(raw,frame.pose,names,parents,amount):raw;
  if(!active)return inertia?{...frame,pose}:frame;
  const age=time-start;
  return {...frame,pose,attack:{name:e.attack,phase:time>=end?'RETURN':age<duration?'ARM':'ATTACK',sourceFrame:Math.min(clip.poses.length-1,sourceFrame(age)),matchedFrame:match,armedTime:start+duration,start,end}};
 }
 return {sample,start,end,match,score,duration,sourceFrame,indices,inertia};
}
const api={create,at,attackAt,carryPelvis,compensate,bones,overlay,labels};if(node)module.exports=api;else root.BodyflipJumpAttack=api;
})(globalThis);
