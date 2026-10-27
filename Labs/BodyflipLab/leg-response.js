/* Whole-leg angular response shared by scheduled attacks, manual attacks and the viewer. */
(function(root){
'use strict';
const node=typeof module!=='undefined',R=node?require('./recovery.js'):root.Recovery;
const {add,sub,mul,dot,cross,unit,length,rotate,qm,qinv,qlog,qexp}=R,clamp=(x,a,b)=>Math.max(a,Math.min(b,x)),kneeLimit=150*Math.PI/180;
function kneeBend(p,h){const a=unit(sub(p.points[h.knee],p.points[h.hip])),b=unit(sub(p.points[h.foot],p.points[h.knee]));return clamp(Math.atan2(dot(cross(a,b),rotate(p.q[h.knee],h.kneeAxis)),dot(a,b)),0,kneeLimit);}
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
function create({source,base,start,stop,names,parents,reference,hinges,frequency=24,anticipation=0,sampleRate=120}){
 const pelvis=names.indexOf('pelvis'),spine=names.indexOf('spine_01'),dt=1/sampleRate,count=Math.ceil((stop-start)/dt);
 const bones=[pelvis,...hinges.map(h=>h.hip),...hinges.map(h=>h.foot)],frequencies=[...Array(3).fill(32),...Array(16).fill(frequency)];
 const targets=[],states=[];
 function target(t,previous){
  // Offline attack lookahead only affects the correction target. The output
  // still carries the current gait, root and authored upper-body animation.
  const pose=source(t+anticipation),rest=base(t+anticipation),local=R.localize(pose.points,pose.q,parents),restLocal=R.localize(rest.points,rest.q,parents),x=[];
  // Root-relative absolute segment orientation: pelvis motion cannot instantly
  // drag the thigh/foot around. Base gait/facing still carries the response.
  for(const bone of bones){
   const a=qm(qinv(rest.q[0]),rest.q[bone]),b=qm(qinv(pose.q[0]),pose.q[bone]);
   x.push(...continuousLog(qm(b,qinv(a)),previous?.slice(x.length,x.length+3)));
  }
  for(const h of hinges){
   let delta=qm(qinv(restLocal.q[h.knee]),local.q[h.knee]);if(delta[3]<0)delta=mul(delta,-1);
   const angle=2*Math.atan2(dot(delta.slice(0,3),h.kneeAxis),delta[3]),bend=kneeBend(rest,h);
   // Track fractions of available extension/flexion, not a stale angle offset.
   // Each critical response stays in [0,1]; their sum preserves the current
   // gait's knee limits without clipping the displayed pose or its velocity.
   x.push(clamp(-angle/Math.max(1e-8,bend),0,1),clamp(angle/Math.max(1e-8,kneeLimit-bend),0,1));
  }
  return x;
 }
 targets.push(target(start));states.push({x:target(start-anticipation),v:targets[0].map(()=>0)});
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
   const bend=kneeBend(rest,h),delta=-bend*state.x[15+k*2]+(kneeLimit-bend)*state.x[16+k*2];
   local.q[h.knee]=qm(restLocal.q[h.knee],qexp(mul(h.kneeAxis,delta)));
   const calf=qm(hip,local.q[h.knee]);local.q[h.foot]=qm(qinv(calf),world[3+k]);
  }
  return R.fk(local,parents);
 }
 return {sample,stateAt,states,targets,stop,start,frequencies};
}
const api={create};if(node)module.exports=api;else root.BodyflipLegResponse=api;
})(globalThis);
