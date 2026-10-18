// Position/bend, wrist twist, and body reach have separate responsibilities.
// A straight forearm is valid for measuring reach, never for choosing a pole.
(function(root){
'use strict';
const R=root.Recovery,W=root.ReachWrist;
const {add,sub,mul,dot,cross,unit,length,rotate,qm,qinv,qexp,fromTo}=R;
const P=t=>t.slice(0,3),Q=t=>t.slice(3),clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const move=(a,b,d)=>{const v=sub(b,a),n=length(v);return n>d?add(a,mul(v,d/n)):b;};
const align=(q,a,b)=>unit(qm(fromTo(a,b),q));
function solve(input){
 const {shoulder,rawElbow,previous,upperLength:L1,lowerLength:L2,desired,command,anchor,palm,joint,speed}=input;
 const oldS=P(previous[0]),oldE=P(previous[1]),oldH=P(previous[2]);
 const oldUpper=sub(oldE,oldS),oldLower=sub(oldH,oldE),step=speed/60;
 const oldAxis=unit(sub(oldH,oldS)),bend=sub(oldUpper,mul(oldAxis,dot(oldUpper,oldAxis)));
 let handQ=command,result,evaluations=0;
 // Two fixed-point passes couple the achievable hand rotation and wrist goal.
 for(let outer=0;outer<2;outer++){
  const goal=sub(anchor,rotate(handQ,palm));
  let hand=move(oldH,goal,step),axis=sub(hand,shoulder),d=length(axis);
  axis=d>1e-8?mul(axis,1/d):unit(sub(P(input.baseHand),shoulder));
  d=clamp(d,Math.abs(L1-L2)+.0001,L1+L2-.0001);hand=add(shoulder,mul(axis,d));
  const along=(L1*L1-L2*L2+d*d)/(2*d),height=Math.sqrt(Math.max(0,L1*L1-along*along));
  const center=add(shoulder,mul(axis,along));
  // Carry the established bend plane with the reach direction. Projecting the
  // old elbow against the new axis can flip the plane near full extension.
  let u=rotate(fromTo(oldAxis,axis),bend);u=sub(u,mul(axis,dot(u,axis)));
  if(length(u)<1e-6){u=sub(rawElbow,center);u=sub(u,mul(axis,dot(u,axis)));}
  if(length(u)<1e-6)u=cross(axis,Math.abs(axis[2])<.9?[0,0,1]:[0,1,0]);
  u=unit(u);const v=cross(axis,u);
  let elbowStep=Math.min(8*Math.PI/180,step*1.2/Math.max(height,.1));
  let rollStep=4*Math.PI/180;
  function follow(theta,roll){
   const elbow=add(center,mul(add(mul(u,Math.cos(theta)),mul(v,Math.sin(theta))),height));
   const lower=sub(hand,elbow),dir=unit(lower);
   const forearm=unit(qm(qexp(mul(dir,roll)),align(Q(previous[1]),oldLower,lower)));
   return {elbow,forearm};
  }
  // Follow the explicit terminal bend, including when attached. It is defined
  // even at full extension and responds to the same blend as ordinary reaching.
  let best;
  if(input.forearmHint){
   const hint=input.forearmHint,localLower=rotate(qinv(Q(previous[1])),oldLower);
   let theta=0;
   if(input.poleHint){
    const wantedHand=sub(anchor,rotate(desired,palm)),goalAxis=unit(sub(wantedHand,shoulder));
    const offset=rotate(fromTo(goalAxis,axis),input.poleHint);
    theta=Math.atan2(dot(offset,v),dot(offset,u));
   }
   const elbow=add(center,mul(add(mul(u,Math.cos(theta)),mul(v,Math.sin(theta))),height));
   const direction=unit(sub(hand,elbow)),aligned=align(hint,rotate(hint,localLower),direction);
   let delta=qm(aligned,qinv(align(Q(previous[1]),oldLower,direction)));if(delta[3]<0)delta=mul(delta,-1);
   const roll=2*Math.atan2(dot(delta.slice(0,3),direction),delta[3]);
   best=follow(clamp(theta,-elbowStep,elbowStep),clamp(roll,-rollStep,rollStep));
  }else best=follow(0,0);
  handQ=W.constrain(joint,best.forearm,command);evaluations++;
  result={upper:[...shoulder,...align(Q(previous[0]),oldUpper,sub(best.elbow,shoulder))],lower:[...best.elbow,...best.forearm],hand:[...hand,...handQ],evaluations};
  if(length(sub(sub(anchor,rotate(handQ,palm)),goal))<.01)break;
 }
 result.goal=sub(anchor,rotate(handQ,palm));
 return result;
}
// Look ahead over admissible forearm rolls before requesting body motion.
// Cache for the target/contact/limits, not the arm's own movement toward it.
function planExtent({shoulder,wrist,desired,joint,localLower}){
 const delta=sub(wrist,shoulder),distance=length(delta),direction=distance>1e-8?mul(delta,1/distance):[0,1,0];
 const aligned=fromTo(unit(localLower),direction),reverse={...joint,handFirst:!joint.handFirst};
 let evaluations=0;
 function evaluate(roll){
  evaluations++;
  const candidate=qm(qexp(mul(direction,roll)),aligned);
  const forearm=W.constrain(reverse,desired,candidate),cos=clamp(dot(unit(rotate(forearm,localLower)),direction),-1,1);
  return {roll,forearm,cos};
 }
 let best=evaluate(0);
 if(best.cos>=1-1e-10||joint.modes.every(m=>m===2))return {forearm:best.forearm,cos:best.cos,evaluations};
 for(let i=1;i<8;i++){const x=evaluate(i*Math.PI/4);if(x.cos>best.cos)best=x;}
 for(const step of [Math.PI/8,Math.PI/16,Math.PI/32]){
  const a=evaluate(best.roll-step),b=evaluate(best.roll+step);
  if(a.cos>best.cos)best=a;if(b.cos>best.cos)best=b;
 }
 return {forearm:best.forearm,cos:best.cos,evaluations};
}
function trackExtent({prior,shoulder,wrist,desired,joint,localLower}){
 const rotation=qm(desired,qinv(prior.rotation));
 const candidate=align(qm(rotation,prior.forearm),rotate(rotation,sub(prior.wrist,shoulder)),sub(wrist,shoulder));
 const forearm=W.constrain({...joint,handFirst:!joint.handFirst},desired,candidate);
 return {forearm,cos:clamp(dot(unit(rotate(forearm,localLower)),unit(sub(wrist,shoulder))),-1,1),evaluations:1};
}
const smooth=(a,b,v)=>{const t=clamp((v-a)/(b-a),0,1);return t*t*(3-2*t);};
function preferred(axis,sign,blend){
 // The whole-body kernel's outward/down policy, evaluated at the actual wrist
 // goal rather than its virtual body-assistance endpoint. Never invert the
 // outward canonical pole: that would select the inward half of the circle.
 const outward=sub([sign,0,0],mul(axis,sign*axis[0]));
 let projected=sub([sign,-.22,-.28],mul(axis,dot([sign,-.22,-.28],axis)));
 if(length(projected)<1e-7)projected=sub([0,-.65,-.35],mul(axis,dot([0,-.65,-.35],axis)));
 let bend=unit(projected);const o=length(outward);
 if(o>1e-5){
  const out=mul(outward,1/o),amount=dot(bend,out);
  if(amount<.55){
   const transverse=unit(mul(cross(axis,out),sign)),canonical=unit(add(mul(out,.55),mul(transverse,Math.sqrt(1-.55*.55))));
   const weight=smooth(.25,.55,o)*smooth(0,.15,.55-amount);bend=unit(add(mul(bend,1-weight),mul(canonical,weight)));
  }
 }
 const weight=(1-.3*smooth(0,.65,axis[1]))*smooth(.25,.65,Math.hypot(axis[0],axis[1]))*blend;
 const down=sub([0,0,-1],mul(axis,-axis[2])),relaxed=unit(add(down,mul(outward,.2)));
 return unit(add(mul(bend,1-weight),mul(relaxed,weight)));
}
function posture(input,extent,roll=0){
 const {shoulder,wrist,localLower,upperLength:L1}=input,L2=length(localLower),delta=sub(wrist,shoulder);
 const axis=length(delta)>1e-8?unit(delta):[0,1,0],d=clamp(length(delta),Math.abs(L1-L2)+.0001,L1+L2-.0001);
 const along=(L1*L1-L2*L2+d*d)/(2*d),height=Math.sqrt(Math.max(0,L1*L1-along*along));
 const pole=preferred(axis,input.sign,input.blend);
 const direction=unit(sub(mul(axis,d-along),mul(pole,height)));
 const twist=W.fitForearm(input.joint,input.desired,localLower,direction,roll);
 return {...twist,pole,extent,cos:extent.cos,evaluations:extent.evaluations};
}
function plan(input){return posture(input,planExtent(input));}
function track(input){
 const {prior}=input;
 const extent=input.sameTarget?prior.extent:trackExtent({...input,prior:{...prior,forearm:prior.extent.forearm}});
 return posture(input,extent,prior.roll);
}
root.ReachCoupled={solve,plan,track,preferred};
})(globalThis);
