/* Viewer-only experiment. The lab's production samplers do not import this. */
(function(root){
'use strict';
const node=typeof module!=='undefined',R=node?require('./recovery.js'):root.Recovery,H=node?require('./attack-inertia.js'):root.BodyflipAttackInertia;
const {add,sub,mul,dot,length,rotate,qm,qinv,qlog,qexp}=R,clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
function step(state,a,b,dt,frequencies){
 if(dt<=0)return state;
 const x=[],v=[];
 for(let j=0;j<a.length;j++){
  const w=frequencies[j],speed=(b[j]-a[j])/dt,offset=-2*speed/w,z=state.x[j]-a[j]-offset,d=state.v[j]-speed,c=d+w*z,e=Math.exp(-w*dt);
  x[j]=b[j]+offset+(z+c*dt)*e;v[j]=speed+(d-w*c*dt)*e;
 }
 return {x,v};
}
function continuousLog(q,previous){
 const v=qlog(q),n=length(v);if(!previous||n<1e-8)return v;
 const axis=mul(v,1/n),turns=Math.round(dot(sub(previous,v),axis)/(2*Math.PI));
 return add(v,mul(axis,turns*2*Math.PI));
}
function create({source,base,start,stop,names,parents,reference,frequency=24}){
 const pelvis=names.indexOf('pelvis'),spine=names.indexOf('spine_01'),hinges=H.legHinges(names,reference),dt=1/120,count=Math.ceil((stop-start)/dt);
 const bones=[pelvis,...hinges.map(h=>h.hip),...hinges.map(h=>h.foot)],frequencies=[...Array(3).fill(32),...Array(12).fill(frequency),frequency,frequency];
 const targets=[],states=[];
 function target(t,previous){
  const pose=source(t),rest=base(t),local=R.localize(pose.points,pose.q,parents),restLocal=R.localize(rest.points,rest.q,parents),x=[];
  // Root-relative absolute segment orientation: pelvis motion cannot instantly
  // drag the thigh/foot around. Base gait/facing still carries the response.
  for(const bone of bones){
   const a=qm(qinv(rest.q[0]),rest.q[bone]),b=qm(qinv(pose.q[0]),pose.q[bone]);
   x.push(...continuousLog(qm(b,qinv(a)),previous?.slice(x.length,x.length+3)));
  }
  for(const h of hinges){
   let delta=qm(qinv(restLocal.q[h.knee]),local.q[h.knee]);if(delta[3]<0)delta=mul(delta,-1);
   x.push(2*Math.atan2(dot(delta.slice(0,3),h.kneeAxis),delta[3]));
  }
  return x;
 }
 targets.push(target(start));states.push({x:targets[0].slice(),v:targets[0].map(()=>0)});
 function stateAt(t){
  if(t<=start)return states[0];
  const f=clamp((t-start)/dt,0,count),i=Math.floor(f),u=f-i;
  while(states.length<=Math.min(count,i+1)){
   const n=states.length,goal=target(start+n*dt,targets[n-1]);
   states.push(step(states[n-1],targets[n-1],goal,dt,frequencies));targets.push(goal);
  }
  if(i===count)return step(states[i],targets[i],targets[i],Math.max(0,t-(start+count*dt)),frequencies);
  const goal=targets[i].map((v,k)=>v+(targets[i+1][k]-v)*u);
  return step(states[i],targets[i],goal,u*dt,frequencies);
 }
 function sample(t,pose=source(t)){
  if(t<=start)return pose;
  const state=stateAt(t),rest=base(t),local=R.localize(pose.points,pose.q,parents),restLocal=R.localize(rest.points,rest.q,parents);
  const world=bones.map((bone,j)=>qm(qm(qm(rest.q[0],qexp(state.x.slice(j*3,j*3+3))),qinv(rest.q[0])),rest.q[bone]));
  local.q[pelvis]=qm(qinv(pose.q[parents[pelvis]]),world[0]);
  // Keep the authored attack's complete upper-body world orientation.
  local.q[spine]=qm(qinv(world[0]),pose.q[spine]);
  for(let k=0;k<2;k++){
   const h=hinges[k],hip=world[1+k];
   local.q[h.hip]=qm(qinv(world[0]),hip);
   // Only flexion at the knee: no filtered knee position or changing IK pole.
   local.q[h.knee]=qm(restLocal.q[h.knee],qexp(mul(h.kneeAxis,state.x[15+k])));
   const calf=qm(hip,local.q[h.knee]);local.q[h.foot]=qm(qinv(calf),world[3+k]);
  }
  return R.fk(local,parents);
 }
 return {sample,stateAt,states,targets,stop,start,frequencies};
}
const api={create};if(node)module.exports=api;else root.BodyflipViewerLegResponse=api;
})(globalThis);
