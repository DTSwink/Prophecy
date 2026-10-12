/* Elbow preference in the moving arm/spine-up frame. Degrees, authored seconds. */
(function(root){
'use strict';
const R=typeof module!=='undefined'?require('./recovery.js'):root.Recovery;
const {sub,add,mul,dot,cross,length:len,unit,rotate,qinv,qm,qexp,fromTo}=R,RAD=Math.PI/180;
const wrap=v=>((v+180)%360+360)%360-180;
const project=(v,d)=>sub(v,mul(d,dot(v,d)));
const rotation=(pose,reference)=>typeof reference==='number'?pose[reference].q:reference.q;
function frame(pose,arm,spine,previous=null,maxTurn=Infinity){
 const [a,b,c]=arm,q=rotation(pose,spine),inv=qinv(q),d=unit(rotate(inv,sub(pose[c].p,pose[a].p)));
 const carried=previous?unit(project(rotate(fromTo(previous.d,d),previous.zero),d)):null;
 let zero=project(spine.down||[-1,0,0],d); // Optional carried sword reference; otherwise spine-down.
 if(len(zero)<1e-4){
  zero=carried||project(rotate(inv,sub(pose[b].p,pose[a].p)),d);
  if(len(zero)<1e-7){ // Straight arm at the vertical singularity: use its bone frame.
   zero=project(rotate(qm(inv,pose[a].q),[0,1,0]),d);
   if(len(zero)<1e-7)zero=project(rotate(qm(inv,pose[a].q),[0,0,1]),d);
  }
 }
 zero=unit(zero);
 // Preserve the continuous frame branch when crossing the undefined vertical pole.
 if(carried&&dot(zero,carried)<0)zero=mul(zero,-1);
 // The reference projection is ill-conditioned near its axis. Spend only the
 // unused pole-speed budget turning toward it; transport itself is unbounded.
 if(carried&&Number.isFinite(maxTurn)){
  const turn=Math.atan2(dot(d,cross(carried,zero)),dot(carried,zero));
  zero=rotate(qexp(mul(d,Math.max(-maxTurn*RAD,Math.min(maxTurn*RAD,turn)))),carried);
 }
 return {d,zero};
}
function measure(pose,arm,spine,basis){
 const pole=unit(project(rotate(qinv(rotation(pose,spine)),sub(pose[arm[1]].p,pose[arm[0]].p)),basis.d));
 return Math.atan2(dot(basis.d,cross(basis.zero,pole)),dot(basis.zero,pole))/RAD;
}
function interpolate(a,b,t){
 const d=unit(add(mul(a.d,1-t),mul(b.d,t)));
 const x=unit(project(rotate(fromTo(a.d,d),a.zero),d)),y=unit(project(rotate(fromTo(b.d,d),b.zero),d));
 const turn=Math.atan2(dot(d,cross(x,y)),dot(x,y));
 return {d,zero:rotate(qexp(mul(d,turn*t)),x)};
}
const target=(targets,insertion)=>targets.clear.pole+wrap(targets.seated.pole-targets.clear.pole)*insertion;
const advance=(angle,wanted,speed,dt)=>angle+Math.max(-speed*dt,Math.min(speed*dt,wrap(wanted-angle)));
function apply(pose,arm,spine,angle,basis){
 const [a,b,c]=arm,A=pose[a].p,d=unit(sub(pose[c].p,A));
 const existing=unit(project(sub(pose[b].p,A),d));
 const wanted=rotate(rotation(pose,spine),rotate(qexp(mul(basis.d,angle*RAD)),basis.zero));
 const turn=Math.atan2(dot(d,cross(existing,wanted)),dot(existing,wanted)),q=qexp(mul(d,turn)),out=pose.slice();
 out[a]={...pose[a],q:unit(qm(q,pose[a].q))};
 out[b]={...pose[b],p:add(A,rotate(q,sub(pose[b].p,A))),q:unit(qm(q,pose[b].q))};
 return out; // Wrist position/orientation and both segment lengths stay unchanged.
}
const api={frame,measure,target,advance,apply,wrap,interpolate};if(typeof module!=='undefined')module.exports=api;else root.ElbowPole=api;
})(globalThis);
