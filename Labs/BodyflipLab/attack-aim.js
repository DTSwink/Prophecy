/* Static aim: pelvis yaw and distributed contact-chain bend, calibrated at Hit. */
(function(root){
'use strict';
const node=typeof module!=='undefined',R=node?require('./recovery.js'):root.Recovery,C=node?require('./core.js'):root.BodyflipCore,H=node?require('./attack-inertia.js'):root.BodyflipAttackInertia;
const {add,sub,mul,dot,cross,length,unit,rotate,qm,qinv,qexp}=R;
const direct=new Set(['KickL','KickR','jabL','jabR','pike']);
const smooth=x=>{x=Math.max(0,Math.min(1,x));return x*x*x*(10+x*(-15+6*x));};
function center(pose,rig){const total=rig.reduce((s,b)=>s+b.mass,0);return rig.reduce((p,b)=>add(p,mul(add(pose.points[b.i],rotate(pose.q[b.i],b.offset)),b.mass/total)),[0,0,0]);}
function between(from,to,up){
 const a=unit(from),b=unit(to),d=Math.max(-1,Math.min(1,dot(a,b)));
 if(length(from)<1e-8||length(to)<1e-8)return [0,0,0,1];
 if(d>0&&length(cross(a,b))<1e-12)return [0,0,0,1];
 let axis=cross(a,b);const sine=length(axis);
 if(length(axis)<1e-8){axis=sub(up,mul(a,dot(up,a)));if(length(axis)<1e-8)axis=cross(a,Math.abs(a[0])<.9?[1,0,0]:[0,0,1]);}
 return qexp(mul(unit(axis),Math.atan2(sine,d)));
}
function create({clip,track,names,parents,reference,sampleHit}){
 if(!clip?.meta.hitTarget)throw Error('Missing original hit target for '+clip?.meta.name);
 const f=clip.meta.phases.hit,i=Math.min(clip.poses.length-2,Math.floor(f)),source=C.blend(clip.poses[i],clip.poses[i+1],f-i,parents),bone=names.indexOf(C.effector(clip.meta.name));
 // Contact is attached to the effector, including the original blade hit location.
 const offset=rotate(qinv(source.q[bone]),sub(clip.meta.hitTarget,source.points[bone]));
 const point=pose=>add(pose.points[bone],rotate(pose.q[bone],offset));
 const rig=H.model(names,parents,reference),hit=sampleHit(track.hitTime),origin=center(hit,rig),direction=sub(point(hit),origin);
 const start=track.start??0,armed=track.armedTime??start+track.duration,ready=direct.has(clip.meta.name)?armed:track.hitTime;
 const end=track.end,returnEnd=track.returnEnd;
 const weight=(t,undoRotation=true)=>smooth((t-start)/Math.max(1e-8,ready-start))*(undoRotation?1-smooth((t-end)/Math.max(1e-8,returnEnd-end)):1);
 // Only bones on the contact path receive bend: five spines for hand/head
 // contacts, the hip for foot contacts. Descendants inherit the cumulative bend.
 const chain=[];for(let j=bone;j>0;j=parents[j])if(/^spine_/.test(names[j])||/^thigh_/.test(names[j]))chain.unshift(j);
 const factors=names.map((_,i)=>{let n=0;for(let j=i;j>0;j=parents[j])if(chain.includes(j))n++;return chain.length?n/chain.length:0;});
 const identity=[0,0,0,1],neutral={yaw:identity,bends:names.map(()=>identity)};
 const state=p=>({yaw:qexp([0,p[0],0]),bends:factors.map(w=>qexp([p[1]*w,0,p[2]*w]))});
 const blendQ=(a,b,w)=>qm(qexp(mul(R.qlog(qm(b,qinv(a))),w)),a);
 function mix(a,b,w){if(Array.isArray(a))a=neutral;return {yaw:blendQ(a.yaw,b.yaw,w),bends:a.bends.map((q,i)=>blendQ(q,b.bends[i],w))};}
 function applyRotation(pose,delta){
  if(Array.isArray(delta))delta=neutral;
  const pivot=center(pose,rig),world=delta.bends.map(q=>qm(q,delta.yaw)),points=[],q=[];
  for(let i=0;i<names.length;i++){
   q[i]=qm(world[i],pose.q[i]);const parent=parents[i];
   points[i]=parent<0?add(pivot,rotate(delta.yaw,sub(pose.points[i],pivot))):add(points[parent],rotate(world[parent],sub(pose.points[i],pose.points[parent])));
  }
  const shift=sub(pivot,center({points,q},rig));for(let i=1;i<points.length;i++)points[i]=add(points[i],shift);
  points[0]=pose.points[0].slice();return {...pose,points,q,axes:q.map(R.toAxes)};
 }
 function solve3(matrix,rhs){
  const a=matrix.map((row,i)=>[...row,rhs[i]]);
  for(let i=0;i<3;i++){
   let k=i;for(let j=i+1;j<3;j++)if(Math.abs(a[j][i])>Math.abs(a[k][i]))k=j;
   [a[i],a[k]]=[a[k],a[i]];const d=a[i][i];if(Math.abs(d)<1e-15)return [0,0,0];
   for(let j=i;j<4;j++)a[i][j]/=d;
   for(let k=0;k<3;k++)if(k!==i){const d=a[k][i];for(let j=i;j<4;j++)a[k][j]-=d*a[i][j];}
  }
  return a.map(row=>row[3]);
 }
 const solutions=new Map();
 function solution(target){
  const key=target.join(',');if(solutions.has(key))return solutions.get(key);
  const desired=unit(sub(target,origin));
  if(length(sub(target,origin))<1e-8)return {state:neutral,parameters:[0,0,0],error:0};
  const azimuth=v=>Math.atan2(v[0],v[2]),wrap=a=>Math.atan2(Math.sin(a),Math.cos(a));
  const yaw=Math.hypot(desired[0],desired[2])<1e-8?0:wrap(azimuth(desired)-azimuth(direction));
  const initial=R.qlog(between(rotate(qexp([0,yaw,0]),direction),desired,[0,1,0]));
  let p=[yaw,initial[0],initial[2]];
  const evaluate=p=>unit(sub(point(applyRotation(hit,state(p))),origin));
  let value=evaluate(p),error=length(sub(value,desired));
  // A tiny three-parameter solve runs only when the target changes, never per tick.
  // Its Jacobian includes the moved contact and COM; rigid-body aiming would miss
  // after moving the pivot from the pelvis into the articulated spine.
  for(let n=0;n<32&&error>1e-8;n++){
   const h=1e-4,columns=p.map((_,j)=>{const v=p.slice();v[j]+=h;return mul(sub(evaluate(v),value),1/h);});
   const residual=sub(desired,value),matrix=columns.map((a,i)=>columns.map((b,j)=>dot(a,b)+(i===j?1e-5*(i===0?.1:1):0))),rhs=columns.map(a=>dot(a,residual));
   let step=solve3(matrix,rhs),size=length(step);if(size>.4)step=mul(step,.4/size);
   let improved=false;
   for(let scale=1;scale>=1/32;scale*=.5){
    const candidate=add(p,mul(step,scale)),v=evaluate(candidate),e=length(sub(v,desired));
    if(e<error){p=candidate;value=v;error=e;improved=true;break;}
   }
   if(!improved)break;
  }
  const result={state:state(p),parameters:p,error};solutions.set(key,result);if(solutions.size>8)solutions.delete(solutions.keys().next().value);return result;
 }
 function correction(target){return solution(target).state;}
 function rotation(time,target,amount=1,undoRotation=true,from=neutral){
  const goal=mix(neutral,correction(target),Math.max(0,Math.min(1,amount)));
  return mix(from,goal,weight(time,undoRotation));
 }
 function apply(pose,time,target,amount=1,undoRotation=true){return applyRotation(pose,rotation(time,target,amount,undoRotation));}
 return {apply,applyRotation,rotation,point,weight,correction,ready,origin,direction,rig,chain,factors,solution,deadline:direct.has(clip.meta.name)?'Armed':'Hit'};
}
const api={create,center,between};if(node)module.exports=api;else root.BodyflipAttackAim=api;
})(globalThis);
