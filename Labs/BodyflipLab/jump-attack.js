/* Authored pelvis and upper-body attack. Final Harness pre-Armed entry, then authored time. */
(function(root){
'use strict';
const PoseMotion=typeof module!=='undefined'?require('./jump-motion.js'):root.BodyflipJumpMotion;

const node=typeof module!=='undefined',R=node?require('./recovery.js'):root.Recovery,C=node?require('./core.js'):root.BodyflipCore,H=node?require('./attack-inertia.js'):root.BodyflipAttackInertia,K=node?require('./kick-attack.js'):root.BodyflipKickAttack,T=node?require('./throw-attack.js'):root.BodyflipThrowAttack;
const clamp=x=>Math.max(0,Math.min(1,x)),smooth=x=>{x=clamp(x);return x*x*(3-2*x);};
const Joint=node?require('./joint-rig.js'):root.BodyflipJointRig,Entry=node?require('./attack-entry.js'):root.BodyflipAttackEntry;
const labels={...T.labels,headbutt:'Headbutt',hookL:'Hook L',hookR:'Hook R',jabL:'Jab L',jabR:'Jab R',KickL:'Kick L',KickR:'Kick R',overL:'Over L',overR:'Over R',pike:'Pike',slashL:'Slash L',slashLD:'Slash LD',slashLU:'Slash LU',slashR:'Slash R',slashRD:'Slash RD',slashRU:'Slash RU',sweepKick:'Sweep kick'};
function bones(names,parents,includePelvis=true){const spine=names.indexOf('spine_01');return names.map((_,i)=>i).filter(i=>{if(includePelvis&&i===names.indexOf('pelvis'))return true;for(let j=i;j>=0;j=parents[j])if(j===spine)return true;return false;});}
function at(clip,frame,parents){
 clip.locals ||= clip.poses.map(p=>R.localize(p.points,p.q,parents));
 const f=Math.max(0,Math.min(clip.poses.length-1,frame)),i=Math.min(clip.poses.length-2,Math.floor(f)),u=f-i,a=clip.locals[i],b=clip.locals[i+1];
 return {p:a.p.map((p,j)=>R.add(p,R.mul(R.sub(b.p[j],p),u))),q:a.q.map((q,j)=>R.qslerp(q,b.q[j],u))};
}
// Keep the authored pelvis and spine rotations on their original joints.
function distributePelvis(target,reference,names,parents){
 const pelvis=names.indexOf('pelvis'),chain=['spine_01','spine_02','spine_03','spine_04','spine_05'].map(n=>names.indexOf(n));
 if(chain.some((i,k)=>i<0||parents[i]!== (k?chain[k-1]:pelvis)))throw Error('Pelvis transfer needs the five-spine chain');
 const turn=R.qlog(R.qm(R.qinv(reference.q[pelvis]),target.q[pelvis])),q=target.q.slice();
 let source=[0,0,0,1],previous=[0,0,0,1];
 for(let k=0;k<chain.length;k++){const i=chain[k];source=R.qm(source,target.q[i]);const distributed=R.qm(R.qexp(R.mul(turn,(k+1)/chain.length)),source);q[i]=R.qm(R.qinv(previous),distributed);previous=distributed;}
 q[pelvis]=reference.q[pelvis];return {...target,q};
}
function attackAt(clip,frame,names,parents,transfer=false){
 const reference=at(clip,0,parents),pelvis=names.indexOf('pelvis');
 // Remove the root coordinate frame before interpolation. Its translation is
 // carried by locomotion; its changing basis must not alter body articulation.
 clip.bodyLocals ||= clip.poses.map((pose,i)=>{const local=clip.locals[i],q=local.q.slice();q[pelvis]=R.qm(R.qinv(reference.q[0]),pose.q[pelvis]);q[0]=reference.q[0];return {...local,q};});
 const target=at({poses:clip.poses,locals:clip.bodyLocals},frame,parents);
 return transfer?distributePelvis(target,reference,names,parents):target;
}
// Authored attacks may exceed resting joint limits, including during recovery.
function armTrack(clip,names,parents,reference,transfer=false){return frame=>attackAt(clip,frame,names,parents,transfer);}
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
// Choose the duration once from the return-start pose. Use the existing timed
// transition so entry velocity and the ongoing base motion are retained.
function distanceReturn(track,base,clip,names,parents,settings,reference,poseOnly=false,baseFrame=null){
 const weight=settings.attackReturnDistance||0;if(!weight)return track;
 const original=t=>{const value=track.sample(t);return poseOnly?value:value.pose;},end=track.end,oldDuration=track.returnEnd-end,raw=original(end),baseline=base(end);
 let measured=raw;
 if(settings.aim){
  const Aim=node?require('./attack-aim.js'):root.BodyflipAttackAim;
  const launchAt=track.launchAt?(pose,transform=p=>p)=>track.launchAt(pose,track.releaseVelocity(t=>transform(original(t),t)),track.projectileAngularVelocity(t=>transform(original(t),t))):null;
  const plan=Aim.create({clip,track,names,parents,reference,sampleHit:original,launchAt,project:p=>p});
  measured=plan.apply(raw,end,settings.target,1);
 }
 const angle=Math.max(...measured.q.slice(1).map((q,i)=>R.length(R.qlog(R.qm(q,R.qinv(baseline.q[i+1])))))),duration=C.returnDuration(oldDuration,angle,weight),returnEnd=end+duration,returnPolicy=C.attackReturn({},duration);
 let returning=null;
 function sample(time,...args){
  if(time<=end)return track.sample(time,...args);
  const active=time<returnEnd,pose=active?{...(returning ||= C.transition(t=>original(end+t),t=>base(end+t),duration,parents))(time-end),attackFree:true}:base(time);
  if(poseOnly)return pose;
  const frame=baseFrame?baseFrame(time,...args):track.sample(time,...args);if(!active)return {...frame,pose};
  return {...PoseMotion.restrict(frame,track.indices,returnPolicy.factor(time-end)),pose,attack:{...track.sample(end).attack,phase:'RETURN'}};
 }
 return {...track,sample,returnPolicy,returnEnd,returnDistance:angle,returnBaseDuration:oldDuration};
}
function create(event,segment,catalog,names,parents,settings,reference=null,{wholeLeg=true,modifyPose=null,clipOverride=null}={}){
 const e=C.sanitizeJump(event),returnPolicy=C.attackReturn(settings,e.attackOut),clip=clipOverride||catalog?.get(e.attack);
 if(e.attack==='none'||!Number.isFinite(segment.airStart)||segment.jumpStart>=segment.abortTime||segment.bounce&&!segment.bounce.didPush)return null;
 if(T.accepts(e.attack)&&!clipOverride)return T.create(event,segment,catalog,names,parents,settings,reference);
 if(!clip)throw Error('Missing vanilla attack: '+e.attack);
 if(K.accepts(e.attack)){
  const start=segment.airStart+e.attackDelay,base=segment.sample;
  const kick=K.create({clip,names,parents,reference:reference||clip.poses[0],base:t=>base(t).pose,start,lead:e.attackIn,tail:returnPolicy.horizon,returnSettings:settings,directArmed:settings.kickToArmed});
  const duration=kick.plan.track.armedTime,sourceFrame=kick.plan.track.sourceFrame;
  return {...kick,match:0,score:0,duration,sourceFrame,indices:names.map((_,i)=>i).slice(1),sample(time,...args){
   const frame=base(time,...args);if(time<start||time>=kick.returnEnd)return frame;
   return {...PoseMotion.restrict(frame,names.map((_,i)=>i),time<start+duration?smooth((time-start)/duration):time<kick.end?1:kick.returnPolicy.factor(time-kick.end)),pose:kick.sample(time),attack:{name:e.attack,phase:time>=kick.end?'RETURN':time<start+duration?'ARM':'ATTACK',sourceFrame:Math.min(clip.poses.length-1,sourceFrame(time-start)),matchedFrame:0,armedTime:start+duration,start,end:kick.end}};
  }};
 }

 const base=segment.sample,start=segment.airStart+e.attackDelay,indices=bones(names,parents,!settings.distributePelvisTurn),fps=clip.meta.fps,armed=clip.meta.phases.armed;
 const targetAt=armTrack(clip,names,parents,reference||clip.poses[0],settings.distributePelvisTurn);
 const initial=base(start).pose,from=R.localize(initial.points,initial.q,parents);
 // Match the authored pelvis and upper-body pose in hierarchy-local axes.
 let match=0,score=Infinity;
 if(!settings.kickToArmed)for(let f=0;f<=Math.ceil(armed);f++){const frame=Math.min(armed,f),target=targetAt(frame),d=indices.reduce((sum,i)=>sum+R.length(R.qlog(R.qm(R.qinv(from.q[i]),target.q[i])))**2,0);if(d<score){score=d;match=frame;}}
 if(settings.kickToArmed){match=armed;score=0;}
 const arming=settings.kickToArmed?Entry.plan({from,targetAt,armed,fps,indices,names,minimum:e.attackIn}):null;
 const duration=arming?.duration??Math.max(e.attackIn,(armed-match)/fps,1/60),hitTime=start+duration+(clip.meta.phases.hit-armed)/fps;
 const endFrame=clip.meta.phases.end??clip.poses.length-1,end=hitTime+(endFrame-clip.meta.phases.hit)/fps,returnEnd=end+returnPolicy.horizon;
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
 let exit=null;const returning=t=>(exit ||= returnPolicy.transition(t=>entry(end+t),t=>base(end+t).pose,parents,indices))(t);
 function uncorrected(time,frame=base(time)){
  if(time<start||time>=end+returnPolicy.horizon)return frame.pose;
  const returned=time>=end?returning(time-end):null;
  const pose=time<end?entry(time,frame):overlay(frame.pose,R.localize(returned.points,returned.q,parents),indices,parents);
  return modifyPose?modifyPose(time,pose):pose;
 }
 const amount=settings.motionCompensation===false?0:(settings.pelvisAttackCompensation??C.defaults.pelvisAttackCompensation),legal=H.createProjection(names,parents,reference||clip.poses[0],true);
 const choreography=settings.softAttackLegs&&amount>0?H.referenceMotion({clip,names,parents,reference:reference||clip.poses[0],start,armedTime:start+duration,hitTime:start+duration+(clip.meta.phases.hit-armed)/fps,end,returnEnd:end+returnPolicy.horizon,amount}):null;
 const inertia=settings.softAttackLegs&&amount>0?H.create({attackFree:true,amount,wholeLeg,choreography,source:uncorrected,base:t=>base(t).pose,target:(t,raw,baseline)=>compensate(raw||uncorrected(t),baseline||base(t).pose,names,parents,amount),start,end:end+returnPolicy.horizon,recoveryStart:end,recoveryEnd:end+returnPolicy.horizon,names,parents,reference:reference||clip.poses[0]}):null;
 const displayed=(time,frame=base(time))=>{const raw=uncorrected(time,frame);return inertia?inertia.sample(time,raw):amount>0?legal(compensate(legal(raw),legal(frame.pose),names,parents,amount)):raw;};
 const recovery=R.pelvisReturn({source:displayed,base:uncorrected,parents,start:hitTime,end:returnEnd,pelvis:names.indexOf('pelvis')});
 function sample(time,...args){
  const frame=base(time,...args);
  if(time<start)return frame;
  if(time>=returnEnd)return frame;
  const pose=time<=hitTime||!(amount>0)?displayed(time,frame):legal(recovery.sample(time));
  const age=time-start;
  return {...PoseMotion.restrict(frame,indices,age<duration?smooth(age/duration):time<end?1:returnPolicy.factor(time-end)),pose:{...pose,attackFree:true},attack:{name:e.attack,phase:time>=end?'RETURN':age<duration?'ARM':'ATTACK',sourceFrame:Math.min(clip.poses.length-1,sourceFrame(age)),matchedFrame:match,armedTime:start+duration,start,end}};
 }
 const track={returnPolicy,sample,start,end,hitTime,returnEnd,recovery,match,score,duration,sourceFrame,indices,inertia,arming};
 return clipOverride?track:distanceReturn(track,t=>base(t).pose,clip,names,parents,settings,reference||clip.poses[0],false,base);
}
const api={distanceReturn,create,directEntry,at,attackAt,armTrack,distributePelvis,compensate,bones,overlay,labels};if(node)module.exports=api;else root.BodyflipJumpAttack=api;
})(globalThis);
