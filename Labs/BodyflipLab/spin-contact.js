/* Contact ownership during a continuing whole-body turn. */
(function(root){
'use strict';
const node=typeof module!=='undefined',R=node?require('./recovery.js'):root.Recovery,C=node?require('./core.js'):root.BodyflipCore,J=node?require('./joint-rig.js'):root.BodyflipJointRig;
const Mass=node?require('./mass.js'):root.BodyflipMass;
const Hands=node?require('./hand-support.js'):root.BodyflipHandSupport;
const Feet=node?require('./support.js'):root.BodyflipSupport;
const Targets=node?require('./target-rig.js'):root.BodyflipTargetRig;
const {add,sub,length}=R,step=1/240;
function create(segment,settings,names,parents,reference){
 const limbs=segment.support.limbs||[segment.support.leg],rig=J.create(names,parents,reference),hand=segment.supportKind==='hand',end=segment.airStart;
 const mass=Mass.model(names,parents,reference),targets=Targets.create(names,parents,reference);
 const releases=new Map(),recoveries=new Map(),followTargets=new Map();let planned=false,planning=false;
 const pure=t=>segment.spin.sample(t,false);
 function contacts(pose,time,frame,force=false){
  frame=segment.unturned(time,0,0,settings.axis);
  if(frame.supportState==='PIN'||force){
   const age=Math.max(0,time-segment.contactTime),c=hand?segment.contactMotion.sample(age,pose.points[0],pose):segment.contactMotion.sample(age,pose.points[0]);
   return c.hands||[{...c,leg:segment.support.leg}];
  }
  return limbs.map(l=>({leg:l,foot:frame.pose.points[l.foot],rotation:{footQ:frame.pose.q[l.foot],toeQ:frame.pose.q[l.toe>=0?l.toe:l.foot]}}));
 }
 function fit(pose,time,frame,selected=limbs,force=false){
  for(const c of contacts(pose,time,frame,force))if(selected.includes(c.leg))pose=segment.solveSupport(pose,c.leg,c.foot,parents,settings.supportReach,c.rotation);
  return pose;
 }
 function plan(){
  if(planned||planning)return;planning=true;
  for(const l of limbs)releases.set(l,end);
  if(hand&&limbs.length>1&&Number.isFinite(end)&&segment.spin.active){
   const remaining=new Set(limbs),start=segment.supportStart;
   for(let t=start;t<end&&remaining.size;t+=step){
    const f=pure(t);if(!['APPROACH','PIN'].includes(f.supportState))continue;
    const c=contacts(f.pose,t,f),posed=fit(f.pose,t,f,[...remaining]),errors=rig.inspect(posed);
    const scores=[...remaining].map(l=>{const target=c.find(c=>c.leg===l),reach=length(sub(target.foot,f.pose.points[l.hip]))/(l.reach*settings.supportReach),joint=errors.filter(e=>e.name===names[l.hip]||e.name===names[l.knee]).reduce((v,e)=>Math.max(v,e.angularError),0);return {l,reach,joint,cost:Math.max(reach-1,joint-.025)};}).sort((a,b)=>b.cost-a.cost);
    for(const s of scores)if(s.cost>1e-5){
     // Start releasing before the exact limit, so there is no straight-arm
     // lock followed by a sudden handoff. Keep the better-fitting hand.
     releases.set(s.l,Math.max(start,t-Math.min(.08,settings.legBlend*.5)));remaining.delete(s.l);
    }
   }
  }
  planning=false;planned=true;
 }
 const returnBlend=hand?settings.handReturn:settings.legBlend;
 const followSeconds=hand?settings.handFollow:(settings.legFollow??.2);
 const followDuration=l=>followSeconds>0&&releases.get(l)>segment.jumpStart+1e-8&&segment.bounce?.didPush!==false?followSeconds:0;
 const chain=l=>[l.hip,l.knee,l.foot,...(hand?[]:[l.toe])].filter(i=>i>=0);
 // A foot has one release trajectory: preserve its departing pose, extend
 // toward the fixed world contact, then inertialize once into the animation.
 // Do not repeatedly choose a shortest arc between two moving leg poses.
 function footFollow(pose,time,l,animation,releaseSource){
  const release=releases.get(l),duration=followDuration(l),age=time-release,key=(releaseSource?'carrier,':'foot,')+l.side;
  let target=followTargets.get(key);
  if(!target){
   const source=t=>{const f=pure(t),p=releaseSource?releaseSource(t).pose:apply(f.pose,t,f);return targets.project(p,segment.surfaces||[segment.surface]);};
   const at=release-1e-7,last=source(at),previous=source(at-C.motionStep),limb=Feet.leg(last,names,l.side);
   const bend=p=>Math.acos(Math.max(-1,Math.min(1,(length(sub(p.points[l.foot],p.points[l.hip]))**2-limb.upper**2-limb.lower**2)/(2*limb.upper*limb.lower))));
   target={foot:last.points[l.foot].slice(),limb,rotation:{footQ:last.q[l.foot],toeQ:last.q[l.toe]},axis:R.unit(sub(last.points[l.foot],last.points[l.hip])),pole:limb.pole,bend:bend(last),bendSpeed:(bend(last)-bend(previous))/C.motionStep};
   followTargets.set(key,target);
  }
  const reachAt=(p,t)=>{
   const a=target.limb,elapsed=Math.max(0,t-release),max=a.reach*settings.supportReach,minBend=Math.acos(Math.max(-1,Math.min(1,(max*max-a.upper*a.upper-a.lower*a.lower)/(2*a.upper*a.lower)))),error=Math.max(0,target.bend-minBend),omega=3/Math.max(1/15,duration),speed=Math.max(-omega*error,target.bendSpeed),bend=Math.min(Math.PI*150/180,minBend+(error+(speed+omega*error)*elapsed)*Math.exp(-omega*elapsed));
   const reach=Math.sqrt(Math.max(0,a.upper*a.upper+a.lower*a.lower+2*a.upper*a.lower*Math.cos(bend))),delta=sub(target.foot,p.points[l.hip]),distance=length(delta),aim=add(p.points[l.hip],R.mul(R.unit(delta),Math.min(reach,distance)));
   // The bend plane belongs to the departing world-space leg. A body flip
   // must not carry that plane around with the pelvis after contact releases.
   const worldLimb={...a,axisLocal:R.rotate(R.qinv(p.q[a.pelvis]),target.axis),poleLocal:R.rotate(R.qinv(p.q[a.pelvis]),target.pole)};
   return targets.project(Feet.solve(p,worldLimb,aim,parents,settings.supportReach,target.rotation));
  };
  let reached;
  if(age<duration)reached=reachAt(pose,time);
  else {
   let recovery=recoveries.get(key);
   if(!recovery){
    const at=release+duration,offset=sub(pose.points[0],pure(time).pose.points[0]);
    const source=t=>{const p=pure(t).pose;return {...p,points:p.points.map(v=>add(v,offset))};};
    recovery=C.transition(t=>reachAt(source(at+t),at+t),t=>pure(at+t).pose,returnBlend,parents,chain(l),true);recoveries.set(key,recovery);
   }
   reached=recovery(age-duration);
  }
  const local=R.localize(pose.points,pose.q,parents),limb=R.localize(reached.points,reached.q,parents);
  for(const i of chain(l))local.q[i]=limb.q[i];return R.fk(local,parents);
 }
 function follow(pose,time,l,animation=pose,entry=true,releaseSource=null){return hand?handFollow(pose,time,l,animation,entry,releaseSource):footFollow(pose,time,l,animation,releaseSource);}
 function handFollow(pose,time,l,animation=pose,entry=true,releaseSource=null){
  const release=releases.get(l),duration=followDuration(l),age=time-release;
  const targetKey=releaseSource?'carrier,'+l.side:l;
  let target=followTargets.get(targetKey);
  if(!target){
   const at=release-1e-7,f=pure(at),last=releaseSource?releaseSource(at).pose:apply(f.pose,at,f);
   target={foot:last.points[l.foot].slice(),rotation:{footQ:last.q[l.foot].slice()},limb:Hands.arm(last,names,l.side)};
   followTargets.set(targetKey,target);
  }
  // Reach back toward the same world point after release. This is articulation,
  // not a renewed pin: the shoulder may move away and the arm cannot stretch.
  const reached=Hands.limitWrist(Hands.solve(pose,target.limb,target.foot,parents,settings.supportReach,target.rotation),target.limb);
  const a=R.localize(reached.points,reached.q,parents),b=R.localize(pose.points,pose.q,parents),anim=animation===pose?b:R.localize(animation.points,animation.q,parents);
  const u=Math.max(0,Math.min(1,(age-duration)/Math.max(1/240,returnBlend))),w=u*u*u*(10+u*(-15+6*u));
  for(const i of chain(l)){
   // The common target projector enforces shoulder/elbow/wrist constraints
   // on both sides of release. Do not introduce a second clamp only here.
   b.q[i]=R.qslerp(a.q[i],anim.q[i],w);
  }
  let out=R.fk(b,parents);
  // Keep the displayed release position and velocity while entering the
  // continued world-space reach. This short handoff does not delay the push.
  if(entry&&age<1/30){
   const offset=sub(pose.points[0],pure(time).pose.points[0]),shifted=t=>{const f=pure(t);return {...f,root:add(f.root,offset),pose:{...f.pose,points:f.pose.points.map(p=>add(p,offset))}};};
   const key=['follow',releaseSource?'carrier':'raw',l.side,...offset.map(v=>Math.round(v*1e7))].join(',');let transition=recoveries.get(key);
   if(!transition){
    const outgoing=t=>{const at=release+Math.min(t,-1e-7);if(releaseSource)return releaseSource(at).pose;const f=shifted(at);return apply(f.pose,at,f);};
    const incoming=t=>{const f=shifted(release+t);return follow(f.pose,release+t,l,f.pose,false,releaseSource);};
    transition=C.transition(outgoing,incoming,1/30,parents,chain(l),true,false);recoveries.set(key,transition);if(recoveries.size>256)recoveries.delete(recoveries.keys().next().value);
   }
   const local=R.localize(out.points,out.q,parents),entryPose=transition(age),q=R.localize(entryPose.points,entryPose.q,parents).q;
   for(const i of chain(l))local.q[i]=q[i];out=R.fk(local,parents);
  }
  return out;
 }
 function apply(pose,time,frame,spinState=null,releaseSource=null){
  plan();
  if(!segment.spin.active&&!limbs.some(l=>followDuration(l)>0&&time>=releases.get(l)&&time<releases.get(l)+followDuration(l)+returnBlend))return pose;
  if(limbs.every(l=>time>=releases.get(l)+followDuration(l)+returnBlend))return pose;
  let out=pose;
  // Carrier correction can call this on an already followed pose. Always
  // blend against the untouched animation, never against the previous blend.
  const animation=pure(time).pose;
  const offset=sub(pose.points[0],pure(time).pose.points[0]),shifted=t=>{const f=pure(t);return {...f,root:add(f.root,offset),pose:{...f.pose,points:f.pose.points.map(p=>add(p,offset))}};};
  const active=limbs.filter(l=>time<releases.get(l)-1e-9);
  if(['APPROACH','PIN'].includes(frame.supportState))out=fit(out,time,frame,active);
  for(const l of limbs){
   const release=releases.get(l),age=time-release,duration=followDuration(l);if(age<0||!Number.isFinite(release)||age>=duration+returnBlend)continue;
   if(duration>0){out=follow(out,time,l,animation,true,releaseSource);continue;}
   const recoveryKey=releaseSource?'carrier,'+l.side:[l.side,...offset.map(v=>Math.round(v*1e7))].join(',');let recovery=recoveries.get(recoveryKey);
   if(!recovery){
    const incoming=t=>shifted(release+t).pose;
    // A collision after release must not move the earlier planted hip and
    // rebuild its knee angle. Seed once from the actual departing contact.
    const outgoing=t=>{const at=Math.min(release-1e-7,release+Math.min(t,0));if(releaseSource)return releaseSource(at).pose;const f=shifted(at);return apply(f.pose,at,f);};
    recovery=C.transition(outgoing,incoming,returnBlend,parents,[l.hip,l.knee,l.foot,l.toe].filter(i=>i>=0),true,true);recoveries.set(recoveryKey,recovery);if(recoveries.size>256)recoveries.delete(recoveries.keys().next().value);
   }
   const a=R.localize(out.points,out.q,parents),b=R.localize(recovery(age).points,recovery(age).q,parents);
   for(const i of [l.hip,l.knee,l.foot,l.toe].filter(i=>i>=0))a.q[i]=b.q[i];out=R.fk(a,parents);
  }
  // Pinning alters articulation after the rigid COM turn. Move the sockets
  // just enough to retain that COM, then solve the same fixed contacts again.
  // This keeps the inherited ballistic/loading momentum while the limbs bend.
  const goal=Mass.center(pose,mass);
  for(let pass=0;pass<14;pass++){
   const delta=sub(goal,Mass.center(out,mass));if(length(delta)<1e-11)break;
   out={...out,points:out.points.map((p,i)=>i===0?p:add(p,delta))};
   if(active.length&&['APPROACH','PIN'].includes(frame.supportState))out=fit(out,time,frame,active);
   for(const l of limbs){const age=time-releases.get(l),duration=followDuration(l);if(duration>0&&age>=0&&age<duration+returnBlend)out=follow(out,time,l,animation,true,releaseSource);}
  }
  const aims=limbs.filter(l=>hand&&followDuration(l)>0&&time>=releases.get(l)&&time<releases.get(l)+followDuration(l)+returnBlend).map(l=>{
   const age=time-releases.get(l),u=Math.max(0,Math.min(1,(age-followDuration(l))/Math.max(1/240,returnBlend))),v=Math.max(0,Math.min(1,age*30)),ease=x=>x*x*x*(10+x*(-15+6*x));
   return {shoulder:l.hip,wrist:l.foot,target:followTargets.get(l).foot,returning:u>0,weight:ease(v)*(1-ease(u))};
  });
  return aims.length?{...out,handFollow:aims}:out;
 }
 return {apply,plan,get releases(){plan();return limbs.map(l=>({side:l.side,time:releases.get(l),early:releases.get(l)<end-1e-7}));},get releaseTime(){plan();return Math.max(...releases.values());},activeBones(time){plan();return limbs.filter(l=>time<releases.get(l)).flatMap(l=>hand?['hand_'+l.side.toLowerCase()]:['foot_'+l.side.toLowerCase(),'ball_'+l.side.toLowerCase()]);}};
}
const api={create};if(node)module.exports=api;else root.BodyflipSpinContact=api;
})(globalThis);
