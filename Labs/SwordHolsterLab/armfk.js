/* Recovery-lab parent-local quaternion interpolation; IK builds guide poses only. */
(function(root){
'use strict';
const R=typeof module!=='undefined'?require('./recovery.js'):root.Recovery;
const {add,sub,mul,length:len,qm,qinv,rotate,qslerp,unit}=R;
const clamp=x=>Math.max(0,Math.min(1,x));
const angle=(a,b)=>len(R.qlog(qm(qinv(a),b)))*180/Math.PI;
function capture(pose,arm,parents){return arm.map(j=>({q:unit(qm(qinv(pose[parents[j]].q),pose[j].q)),p:rotate(qinv(pose[parents[j]].q),sub(pose[j].p,pose[parents[j]].p))}));}
function blend(a,b,t){return a.map((v,k)=>({q:qslerp(v.q,b[k].q,t),p:R.offsetBlend(v.p,b[k].p,t)}));}
// Select the wrist arc in the neutral joint hemisphere, not independently
// against its starting pose. Otherwise a small target edit across 180 degrees
// reverses the wrist while the rest of the arm keeps turning the same way.
function reachDestination(source,target,neutral){
 return target.map((v,k)=>{const anchor=k===2?neutral[k].q:source[k].q;
  const sign=k===2&&R.dot(anchor,source[k].q)<0?-1:1;
  return {...v,q:R.dot(anchor,v.q)*sign<0?mul(v.q,-1):v.q};
 });
}
function reach(a,b,t){return a.map((v,k)=>{
 const q=b[k].q,d=Math.max(-1,Math.min(1,R.dot(v.q,q))),theta=Math.acos(d),sn=Math.sin(theta);
 // The selected arc is retained as the live destination moves across 180°.
 const rotation=t<=0?v.q:t>=1?q:d>.9995?unit(add(mul(v.q,1-t),mul(q,t))):
  Math.abs(sn)>1e-8?unit(add(mul(v.q,Math.sin((1-t)*theta)/sn),mul(q,Math.sin(t*theta)/sn))):v.q;
 return {q:rotation,p:R.offsetBlend(v.p,b[k].p,t)};
});}
function apply(base,arm,parents,local){
 const pose=base.slice();for(let k=0;k<arm.length;k++){const j=arm[k],parent=pose[parents[j]],v=local[k];
  const offset=k===0?v.p:mul(unit(v.p),len(sub(base[j].p,base[parents[j]].p)));
  pose[j]={...base[j],q:unit(qm(parent.q,v.q)),p:k===0?base[j].p:add(parent.p,rotate(parent.q,offset))};
 }return pose;
}
// Measure the FK curve in the moving clavicle frame. Base-motion/torso movement
// is carried normally; these caps govern the authored arm transition itself.
function duration(a,b,linearSpeed,angularSpeed,neutral=null){
 if(neutral)b=reachDestination(a,b,neutral);
 const chain=locals=>{let p=[0,0,0],q=[0,0,0,1];return locals.map((v,k)=>{if(k)p=add(p,rotate(q,v.p));q=unit(qm(q,v.q));return {p,q};});};
 let previous=chain(a),localPrevious=a,seconds=1/60;
 for(let i=1;i<=96;i++){
  const local=neutral?reach(a,b,i/96):blend(a,b,i/96),pose=chain(local);
  seconds=Math.max(seconds,len(sub(pose[2].p,previous[2].p))*96/linearSpeed,angle(previous[2].q,pose[2].q)*96/angularSpeed);
  for(let j=0;j<3;j++)seconds=Math.max(seconds,angle(localPrevious[j].q,local[j].q)*96/angularSpeed);
  previous=pose;localPrevious=local;
 }return seconds*1.002;
}
function plan({arm,parents,neutral,frameAt,startTick,lastTick,o,solve,minimumEndTick=startTick+1,buildGuides=true,arrivalCheck=null,beginSlide=null,earlyArrival=true}){
 const first=frameAt(startTick),source=capture(first.base,arm,parents);let endTick=Math.max(startTick+1,minimumEndTick),destination=source,solves=0;
 const endpoint=(tick,insertion,seed)=>{
  const f=frameAt(Math.min(lastTick,tick)),pose=apply(f.pose,arm,parents,seed);
  solve(pose,arm,f.goalAt(insertion));solves++;return capture(pose,arm,parents);
 };
 // Predict the moving destination, then lengthen until the FK arc obeys both caps.
 for(let iteration=0;iteration<16;iteration++){
  destination=reachDestination(source,endpoint(endTick,o.sheathe?0:1,source),neutral);
  let required=startTick+Math.ceil(duration(source,destination,o.maxReachSpeed,o.maxReachRotationSpeed,neutral)*60);
  // The arm destination is parent-local to the turned shoulder. Give the body
  // enough time to reach that shoulder pose before freezing the arm endpoint.
  const turn=frameAt(Math.min(lastTick,Math.max(endTick,required))).body.requiredDegrees;
  required=Math.max(required,startTick+Math.ceil(turn/o.maxSpineClavicleAngularSpeed*60));
  if(!o.sheathe){let ready=Math.min(Math.max(endTick,required),lastTick);while(ready<=lastTick&&frameAt(ready).body.remainingDegrees>.25)ready++;required=Math.max(required,ready);}
  if(required<=endTick)break;
  endTick=required;
 }
 destination=reachDestination(source,endpoint(endTick,o.sheathe?0:1,source),neutral);
 // Keep the speed-bounded curve aimed at perfect alignment. S may leave that
 // curve on the first acceptable tick; do not retime it to the earlier endpoint.
 const reachEndTick=endTick,reachTarget=destination;
 let arrivalFrame,arrivalPose,arrivalProgress=1,arrives=false;
 if(o.sheathe&&arrivalCheck){
  for(let tick=earlyArrival?startTick:reachEndTick;tick<=(earlyArrival?lastTick:Math.min(lastTick,reachEndTick));tick++){
   const f=frameAt(tick),progress=clamp((tick-startTick)/(reachEndTick-startTick)),local=reach(source,reachTarget,progress),pose=apply(f.pose,arm,parents,local);
   if(arrivalCheck(f,pose,progress)){endTick=tick;destination=local;arrivalFrame=f;arrivalPose=pose;arrivalProgress=progress;arrives=true;break;}
  }
 }else{
  arrivalFrame=frameAt(Math.min(lastTick,endTick));arrivalPose=apply(arrivalFrame.pose,arm,parents,destination);
  const goal=arrivalFrame.goalAt(o.sheathe?0:1);
  arrives=endTick<=lastTick&&len(sub(arrivalPose[arm[2]].p,goal.p))<=2&&angle(arrivalPose[arm[2]].q,goal.q)<=5;
 }
 if(arrives&&beginSlide)beginSlide(arrivalFrame,arrivalPose,endTick,arrivalProgress);
 const slideTicks=Math.max(1,Math.ceil(first.slideLength/o.slidingSpeed*60)),slideEnd=endTick+slideTicks,keys=[{tick:endTick,local:destination}];
 if(arrives&&buildGuides){
  // Spaced guide poses keep the FK path near the straight sheath; no hand-path IK
  // runs while sampling the transition or playback. Reuse the preceding arm frame.
  const count=Math.min(slideTicks,Math.max(1,Math.ceil(slideTicks/4),Math.ceil(first.slideLength/2)));
  let seed=destination;
  const ticks=Array.from({length:count},(_,i)=>endTick+Math.round(slideTicks*(i+1)/count));
  if(o.sheathe&&o.slideRotationCorrection>0)ticks.push(endTick+slideTicks*o.slideRotationCorrection);
  ticks.sort((a,b)=>a-b);
  for(const tick of [...new Set(ticks)]){
   if(tick>lastTick+4)break;
   const fraction=(tick-endTick)/slideTicks,insertion=o.sheathe?fraction:1-fraction;
   seed=endpoint(tick,insertion,seed);keys.push({tick,local:seed});
  }
 }
 return {source,destination,reachDestination:reachTarget,reachEndTick,startTick,endTick,slideEnd,keys,arrives,endpointSolves:solves};
}
function at(plan,tick){
 if(tick<=plan.endTick||!plan.arrives){
  const progress=clamp((tick-plan.startTick)/(plan.reachEndTick-plan.startTick));
  return {local:reach(plan.source,plan.reachDestination,progress),progress};
 }
 let k=1;while(k<plan.keys.length-1&&plan.keys[k].tick<tick)k++;
 const a=plan.keys[k-1],b=plan.keys[k]||a,t=clamp((tick-a.tick)/Math.max(1e-12,b.tick-a.tick));
 return {local:blend(a.local,b.local,t),progress:1};
}
const api={capture,blend,reach,reachDestination,apply,duration,plan,at};if(typeof module!=='undefined')module.exports=api;else root.ArmFK=api;
})(globalThis);
