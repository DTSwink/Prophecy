/* Live Final Harness angular-distance arming, shared by every attack family. */
(function(root){
'use strict';
const R=typeof module!=='undefined'?require('./recovery.js'):root.Recovery;
const clamp=x=>Math.max(0,Math.min(1,x));
function distance(a,b,indices){return indices.reduce((sum,i)=>sum+R.length(R.qlog(R.qm(b.q[i],R.qinv(a.q[i])))),0);}
function plan({from,targetAt,armed,fps,indices,names,minimum=0,speed=1,exponent=1}){
 const end=Math.max(0,armed),keys=[0];for(let f=1;f<end-1e-9;f++)keys.push(f);if(end>1e-9)keys.push(end);
 const poses=keys.map(targetAt),target=poses.at(-1);
 // Live Harness evaluates both clocks and keeps the faster admissible one.
 // This avoids source forearm axial motion dominating the entire body's clock.
 const candidates=[false,true].map(includeLowerArms=>{
  const measured=indices.filter(i=>includeLowerArms||!names[i].startsWith('lowerarm_'));
  let gtDistance=0;for(let k=1;k<poses.length;k++)gtDistance+=distance(poses[k-1],poses[k],measured);
  const liveDistance=distance(from,target,measured),ratio=gtDistance>1e-10?liveDistance/gtDistance:1;
  const effectiveRatio=ratio<=1?ratio:Math.pow(ratio,1/exponent),seconds=end/fps*effectiveRatio/speed;
  return {includeLowerArms,gtDistance,liveDistance,ratio,effectiveRatio,seconds};
 }).sort((a,b)=>a.seconds-b.seconds||Number(a.includeLowerArms)-Number(b.includeLowerArms));
 return {...candidates[0],duration:Math.max(1/60,minimum,candidates[0].seconds),minimum,candidates};
}
function direct({base,start,duration,armed,fps,parents,indices,targetAt}){
 const h=1e-4;
 const local=t=>{const p=base(t).pose;return R.localize(p.points,p.q,parents);};
 const from=local(start),prev=local(start-h),prev2=local(start-2*h),target=targetAt(armed),next=targetAt(armed+h*fps),next2=targetAt(armed+2*h*fps);
 const near=(v,e)=>R.length(R.sub(v,e))>Math.PI?R.sub(v,R.mul(R.unit(v),2*Math.PI)):v;
 const seeds=indices.map(i=>{
  const delta=q=>R.qlog(R.qm(q,R.qinv(from.q[i]))),e=delta(target.q[i]),a=delta(prev.q[i]),b=near(delta(prev2.q[i]),a),c=near(delta(next.q[i]),e),d=near(delta(next2.q[i]),e);
  return {i,e,v0:R.mul(R.add(R.mul(a,-4),b),duration/(2*h)),a0:R.mul(R.sub(b,R.mul(a,2)),duration*duration/(h*h)),v1:R.mul(R.sub(R.add(R.mul(e,-3),R.mul(c,4)),d),duration/(2*h)),a1:R.mul(R.add(R.sub(d,R.mul(c,2)),e),duration*duration/(h*h))};
 });
 return (time,frame=base(time))=>{
  const u=clamp((time-start)/duration),u2=u*u,u3=u2*u,u4=u3*u,u5=u4*u,pose=R.localize(frame.pose.points,frame.pose.q,parents);
  for(const z of seeds){const x=R.add(R.add(R.mul(z.e,10*u3-15*u4+6*u5),R.mul(z.v0,u-6*u3+8*u4-3*u5)),R.add(R.mul(z.v1,-4*u3+7*u4-3*u5),R.add(R.mul(z.a0,.5*(u2-3*u3+3*u4-u5)),R.mul(z.a1,.5*(u3-2*u4+u5)))));pose.q[z.i]=R.qm(R.qexp(x),from.q[z.i]);}
  return R.fk(pose,parents);
 };
}

const api={distance,plan,direct};if(typeof module!=='undefined')module.exports=api;else root.BodyflipAttackEntry=api;
})(globalThis);
