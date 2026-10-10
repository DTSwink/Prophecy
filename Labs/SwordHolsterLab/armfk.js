/* Recovery-lab parent-local quaternion interpolation; IK builds guide poses only. */
(function(root){
'use strict';
const R=typeof module!=='undefined'?require('./recovery.js'):root.Recovery;
const {add,sub,mul,length:len,qm,qinv,rotate,qslerp,unit}=R;
const clamp=x=>Math.max(0,Math.min(1,x)),ease=x=>x*x*x*(10+x*(-15+6*x));
const angle=(a,b)=>len(R.qlog(qm(qinv(a),b)))*180/Math.PI;
function capture(pose,arm,parents){return arm.map(j=>({q:unit(qm(qinv(pose[parents[j]].q),pose[j].q)),p:rotate(qinv(pose[parents[j]].q),sub(pose[j].p,pose[parents[j]].p))}));}
function blend(a,b,t){return a.map((v,k)=>({q:qslerp(v.q,b[k].q,t),p:R.offsetBlend(v.p,b[k].p,t)}));}
function apply(base,arm,parents,local){
 const pose=base.slice();for(let k=0;k<arm.length;k++){const j=arm[k],parent=pose[parents[j]],v=local[k];
  const offset=k===0?v.p:mul(unit(v.p),len(sub(base[j].p,base[parents[j]].p)));
  pose[j]={...base[j],q:unit(qm(parent.q,v.q)),p:k===0?base[j].p:add(parent.p,rotate(parent.q,offset))};
 }return pose;
}
// Measure the FK curve in the moving clavicle frame. Base-motion/torso movement
// is carried normally; these caps govern the authored arm transition itself.
function duration(a,b,linearSpeed,angularSpeed){
 const chain=locals=>{let p=[0,0,0],q=[0,0,0,1];return locals.map((v,k)=>{if(k)p=add(p,rotate(q,v.p));q=unit(qm(q,v.q));return {p,q};});};
 let previous=chain(a),localPrevious=a,seconds=1/60;
 for(let i=1;i<=96;i++){
  const local=blend(a,b,ease(i/96)),pose=chain(local);
  seconds=Math.max(seconds,len(sub(pose[2].p,previous[2].p))*96/linearSpeed,angle(previous[2].q,pose[2].q)*96/angularSpeed);
  for(let j=0;j<3;j++)seconds=Math.max(seconds,angle(localPrevious[j].q,local[j].q)*96/angularSpeed);
  previous=pose;localPrevious=local;
 }return seconds*1.002;
}
function plan({arm,parents,frameAt,startTick,lastTick,o,solve,minimumEndTick=startTick+1,buildGuides=true}){
 const first=frameAt(startTick),source=capture(first.base,arm,parents);let endTick=Math.max(startTick+1,minimumEndTick),destination=source,solves=0;
 const endpoint=(tick,insertion,seed)=>{
  const f=frameAt(Math.min(lastTick,tick)),pose=apply(f.pose,arm,parents,seed);
  solve(pose,arm,f.goalAt(insertion));solves++;return capture(pose,arm,parents);
 };
 // Predict the moving destination, then lengthen until the FK arc obeys both caps.
 for(let iteration=0;iteration<16;iteration++){
  destination=endpoint(endTick,o.sheathe?0:1,source);
  let required=startTick+Math.ceil(duration(source,destination,o.maxReachSpeed,o.maxReachRotationSpeed)*60);
  if(!o.sheathe){let ready=Math.min(Math.max(endTick,required),lastTick);while(ready<=lastTick&&frameAt(ready).body.remainingDegrees>.25)ready++;required=Math.max(required,ready);}
  if(required<=endTick)break;
  endTick=required;
 }
 destination=endpoint(endTick,o.sheathe?0:1,source);
 const arrivalFrame=frameAt(Math.min(lastTick,endTick)),arrivalPose=apply(arrivalFrame.pose,arm,parents,destination),goal=arrivalFrame.goalAt(o.sheathe?0:1);
 const arrives=endTick<=lastTick&&len(sub(arrivalPose[arm[2]].p,goal.p))<=2&&angle(arrivalPose[arm[2]].q,goal.q)<=5;
 const slideTicks=Math.max(1,Math.ceil(first.slideLength/o.slidingSpeed*60)),slideEnd=endTick+slideTicks,keys=[{tick:endTick,local:destination}];
 if(arrives&&buildGuides){
  // Spaced guide poses keep the FK path near the straight sheath; no hand-path IK
  // runs while sampling the transition or playback. Reuse the preceding arm frame.
  const count=Math.min(slideTicks,Math.max(1,Math.ceil(slideTicks/4),Math.ceil(first.slideLength/2)));
  let seed=destination;
  for(let i=1;i<=count;i++){
   const tick=endTick+Math.round(slideTicks*i/count);if(tick>lastTick+4)break;
   const fraction=(tick-endTick)/slideTicks,insertion=o.sheathe?fraction:1-fraction;
   seed=endpoint(tick,insertion,seed);keys.push({tick,local:seed});
  }
 }
 return {source,destination,startTick,endTick,slideEnd,keys,arrives,endpointSolves:solves};
}
function at(plan,tick){
 if(tick<=plan.endTick||!plan.arrives){const progress=clamp((tick-plan.startTick)/(plan.endTick-plan.startTick));return {local:blend(plan.source,plan.destination,ease(progress)),progress:ease(progress)};}
 let k=1;while(k<plan.keys.length-1&&plan.keys[k].tick<tick)k++;
 const a=plan.keys[k-1],b=plan.keys[k]||a,t=clamp((tick-a.tick)/Math.max(1,b.tick-a.tick));
 return {local:blend(a.local,b.local,t),progress:1};
}
const api={capture,blend,apply,duration,plan,at,ease};if(typeof module!=='undefined')module.exports=api;else root.ArmFK=api;
})(globalThis);
