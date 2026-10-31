/* Shared full-body kick used by the viewer, timeline and Attack button. */
(function(root){
'use strict';
const node=typeof module!=='undefined',R=node?require('./recovery.js'):root.Recovery,C=node?require('./core.js'):root.BodyflipCore,H=node?require('./attack-inertia.js'):root.BodyflipAttackInertia,K=node?require('./airborne-motion.js'):root.BodyflipAirborneMotion;
const cache=new WeakMap(),clamp=x=>Math.max(0,Math.min(1,x)),ease=x=>{x=clamp(x);return x*x*x*(10+x*(-15+6*x));};
const accepts=name=>C.effector(name).startsWith('foot_');
function preview({clip,names,parents,reference,lead=.18,tail=.45,directArmed=false,timingPose=reference}){
 let entries=cache.get(clip);if(!entries){entries=[];cache.set(clip,entries);}
 const found=entries.find(e=>e.reference===reference&&e.lead===lead&&e.tail===tail&&e.directArmed===directArmed&&e.timingPose===timingPose);if(found)return found;
 const track=K.recording({clip,names,parents,reference,lead,tail,directArmed,timingPose}),pelvis=names.indexOf('pelvis');
 let limb=names.indexOf(C.effector(clip.meta.name));while(limb>=0&&parents[limb]!==pelvis)limb=parents[limb];
 if(limb<0)throw Error('Kick needs a striking leg');
 const turn=K.bodyTurn(track,names,reference);
 const hitTime=track.lead+(clip.meta.phases.hit-track.sourceStart)/clip.meta.fps;
 // Recover only the added balance, while the complete source follow-through
 // keeps playing. Returning the pelvis's absolute Hit orientation erased
 // the rest of a turn and bent the torso against the recovering pelvis.
 const balanceEnd=Math.max(track.end,hitTime+tail);
 const conserved=K.createBalanced({source:turn.remove,names,parents,reference,duration:track.stop+1.2,strikeRoot:limb,strikeWeight:track.strikeWeight,recoveryStart:hitTime,recoveryEnd:balanceEnd});
 const response=turn.restore(conserved);
 const result={track,response,hitTime,reference,lead,tail,directArmed,timingPose};entries.push(result);if(entries.length>8)entries.shift();return result;
}
function create({clip,names,parents,reference,base,start=0,lead=.18,tail=.45,directArmed=false}){
 const plan=preview({clip,names,parents,reference,lead,tail,directArmed,timingPose:directArmed?base(start):reference}),{track,response}=plan,pelvis=names.indexOf('pelvis'),rest=R.localize(reference.points,reference.q,parents);
 const end=start+track.end,returnEnd=start+track.stop,hitTime=start+plan.hitTime;
 function sample(time){
  const baseline=base(time),age=time-start;if(age<=0||time>=returnEnd)return baseline;
  const pose=response.sample(age),local=R.localize(pose.points,pose.q,parents),b=R.localize(baseline.points,baseline.q,parents);
  // Fade the ongoing gait/pose out on entry and back in during recovery.
  // At full weight the actual viewer articulation replaces every body joint.
  // Root and pelvis facing still carry the kick with the moving character.
  const residual=1-ease(age/track.lead)*(1-ease((age-track.end)/tail));
  const q=local.q.map((v,i)=>i===0?b.q[i]:R.qm(R.qexp(R.mul(R.qlog(R.qm(b.q[i],R.qinv(rest.q[i]))),i===pelvis?1:residual)),v));
  const result=R.fk({p:b.p,q},parents),com=p=>K.center(H.bodies(p,response.rig),response.rig),shift=R.sub(com(baseline),com(result));
  result.points=result.points.map(p=>R.add(p,shift));result.points[0]=baseline.points[0].slice();return result;
 }
 return {sample,start,end,returnEnd,hitTime,plan,armedTime:start+track.armedTime,fullBodyKick:true,arming:track.arming};
}
const api={accepts,preview,create};if(node)module.exports=api;else root.BodyflipKickAttack=api;
})(globalThis);
