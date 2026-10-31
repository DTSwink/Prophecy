/* Small, critically damped limb recoil from a change of spin command.
 * Four articulated chains use the same masses/hinges as the lab. This is an
 * animation response to an authored angular impulse, not a free-body solver. */
(function(root){
'use strict';
const node=typeof module!=='undefined',R=node?require('./recovery.js'):root.Recovery,M=node?require('./mass.js'):root.BodyflipMass,J=node?require('./joint-rig.js'):root.BodyflipJointRig;
const {add,sub,mul,dot,cross,length,rotate,qm,qinv,qexp,qlog}=R,axes=[[1,0,0],[0,1,0],[0,0,1]];
// Positive definite 4x4 articulated inertia, including distal segment rotation.
function solve(A,b){
 const a=A.map((row,i)=>[...row,b[i]]);
 for(let k=0;k<4;k++){const d=a[k][k];for(let j=k;j<=4;j++)a[k][j]/=d;for(let i=0;i<4;i++)if(i!==k){const s=a[i][k];for(let j=k;j<=4;j++)a[i][j]-=s*a[k][j];}}
 return a.map(row=>row[4]);
}
function create(names,parents,reference,strength){
 const rig=M.model(names,parents,reference),joints=J.create(names,parents,reference),chains=[];
 for(const kind of ['upperarm','thigh'])for(const side of ['l','r']){
  const i=names.indexOf(kind+'_'+side),h=joints.joints.find(j=>j.parent===i&&j.hinge),joint=joints.joints.find(j=>j.i===i);
  const descendants=rig.filter(b=>{let k=b.i;while(k>0&&k!==i)k=parents[k];return k===i;});
  chains.push({i,h,joint,bodies:descendants,frequency:kind==='upperarm'?14:17});
 }
 const zero=()=>({x:Array(16).fill(0),v:Array(16).fill(0)});
 function impulse(state,pose,delta){
  if(length(delta)<1e-12)return state;
  const c=M.center(pose,rig),v=state.v.slice();
  for(let k=0;k<chains.length;k++){
   const chain=chains[k],a=axes.map(v=>rotate(pose.q[parents[chain.i]],v));a.push(rotate(pose.q[chain.i],chain.h.axisLocal));
   const A=Array.from({length:4},()=>Array(4).fill(0)),b=Array(4).fill(0);
   for(const body of chain.bodies){
    const center=add(pose.points[body.i],rotate(pose.q[body.i],body.offset)),basis=R.toAxes(qm(pose.q[body.i],body.rotation));
    const inertia=v=>basis.reduce((r,u,j)=>add(r,mul(u,dot(u,v)*body.inertia[j])),[0,0,0]);
    const angular=a.map((u,j)=>j===3&&body.i===chain.i?[0,0,0]:u),linear=angular.map((u,j)=>cross(u,sub(center,pose.points[j===3?chain.h.i:chain.i])));
    const velocity=cross(delta,sub(center,c)),momentum=inertia(delta),angularInertia=angular.map(inertia);
    for(let i=0;i<4;i++){b[i]+=body.mass*dot(linear[i],velocity)+dot(angular[i],momentum);for(let j=0;j<4;j++)A[i][j]+=body.mass*dot(linear[i],linear[j])+dot(angular[i],angularInertia[j]);}
   }
   // A little joint impedance keeps nearly straight chains well conditioned.
   for(let j=0;j<4;j++)A[j][j]+=.002;
   const kick=solve(A,b);for(let j=0;j<4;j++)v[k*4+j]-=strength*kick[j];
  }
  return {x:state.x,v};
 }
 function drift(state,dt){
  const x=[],v=[];
  for(let k=0;k<chains.length;k++)for(let j=0;j<4;j++){
   const i=k*4+j,w=chains[k].frequency,e=Math.exp(-w*dt),c=state.v[i]+w*state.x[i];
   x[i]=(state.x[i]+c*dt)*e;v[i]=(state.v[i]-w*c*dt)*e;
  }
  return {x,v};
 }
 function apply(pose,state){
  if(!state||state.x.every(v=>Math.abs(v)<1e-12))return pose;
  const local=R.localize(pose.points,pose.q,parents),com=M.center(pose,rig);
  for(let k=0;k<chains.length;k++){
   const {i,h,joint}=chains[k],offset=state.x.slice(k*4,k*4+3),angle=length(offset),limit=.3;
   if(angle>1e-12)local.q[i]=joints.clampLocal(qm(qexp(mul(offset,limit*Math.tanh(angle/limit)/angle)),local.q[i]),joint);
   const delta=qlog(qm(local.q[h.i],qinv(h.bind))),bend=dot(delta,h.axisLocal),raw=state.x[k*4+3],room=Math.max(0,raw<0?bend-h.min:h.max-bend),cap=Math.min(.35,room);
   const flex=cap>1e-8?cap*Math.tanh(raw/cap):0;
   local.q[h.i]=qm(qexp(mul(h.axisLocal,flex)),local.q[h.i]);
  }
  let result=R.fk(local,parents);const shift=sub(com,M.center(result,rig));
  return {...pose,...result,points:result.points.map((p,i)=>i===0?p:add(p,shift))};
 }
 return {zero,impulse,drift,apply};
}
const api={create};if(node)module.exports=api;else root.BodyflipSpinResponse=api;
})(globalThis);
