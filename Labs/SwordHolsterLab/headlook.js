/* Authored head aim with a distributed neck; spine_05 remains the anchor. */
(function(root){
'use strict';
const R=typeof module!=='undefined'?require('./recovery.js'):root.Recovery;
const {add,sub,mul,dot,length:len,unit,qm,qinv,qslerp,rotate,fromTo}=R,I=[0,0,0,1];
const angle=(a,b)=>2*Math.acos(Math.max(-1,Math.min(1,Math.abs(dot(a,b)))))*180/Math.PI;
function make(data){return {parents:data.parents,anchor:data.names.indexOf('spine_05'),chain:['neck_01','neck_02','head'].map(n=>data.names.indexOf(n)),head:data.names.indexOf('head')};}
function apply(ctx,pose,headQ){
 const correction=unit(qm(headQ,qinv(pose[ctx.head].q))),out=pose.slice();
 for(const [k,j] of ctx.chain.entries()){
  const parent=ctx.parents[j],inherited=unit(qm(out[parent].q,qinv(pose[parent].q)));
  out[j]={...pose[j],p:add(out[parent].p,rotate(inherited,sub(pose[j].p,pose[parent].p))),q:unit(qm(qslerp(I,correction,(k+1)/ctx.chain.length),pose[j].q))};
 }
 return out;
}
function step(ctx,pose,base,target,state,{tick,startTick,lookOutTick,maxLookIn,maxLookOut,lookAtAlpha=1,lookInExponent=1,lookOutExponent=1}){
 if(tick<=startTick)return {pose,state:{q:pose[ctx.head].q},info:{mode:tick<startTick?'Idle':'Look in',done:tick<startTick,target,lookOutTick,angularStep:0}};
 const lookingOut=tick>=lookOutTick,speed=lookingOut?maxLookOut:maxLookIn,previous=state.q;
 const exponent=lookingOut?lookOutExponent:lookInExponent;
 let transition=state.transition;
 if(!transition||transition.lookingOut!==lookingOut)transition={lookingOut,q:previous,startTick:lookingOut?tick-1:startTick,duration:null};
 const cap=speed/60,limited=desired=>{const d=angle(previous,desired);return qslerp(previous,desired,d>cap?cap/d:1);};
 let headQ=previous,desired=base[ctx.head].q,result=pose;
 // Neck rotation moves the head origin. Re-evaluate aim there, while applying
 // the angular budget once relative to the previous frame, never per iteration.
 for(let iteration=0;iteration<(lookingOut?1:8);iteration++){
  const p=apply(ctx,pose,headQ)[ctx.head].p,direction=sub(target,p);
  const aimed=unit(qm(fromTo(rotate(base[ctx.head].q,[0,1,0]),direction),base[ctx.head].q));
  desired=lookingOut||len(direction)<1e-8?base[ctx.head].q:qslerp(base[ctx.head].q,aimed,lookAtAlpha);
  if(exponent>1){
   // A symmetric power sigmoid shapes the turn, on the head's own clock.
   // Its peak slope is exponent, so enlarge duration to respect max speed.
   // Retain the angular cap too: the target itself can move with locomotion.
   if(transition.duration===null)transition={...transition,duration:Math.max(1,exponent*angle(transition.q,desired)/speed*60)};
   const u=Math.max(0,Math.min(1,(tick-transition.startTick)/transition.duration));
   const a=Math.pow(u,exponent),b=Math.pow(1-u,exponent),alpha=a/(a+b);
   headQ=limited(qslerp(transition.q,desired,alpha));
  }else headQ=limited(desired);
 }
 result=apply(ctx,pose,headQ);
 const remaining=angle(headQ,desired),done=lookingOut&&remaining<.001;
 const forward=rotate(headQ,[0,1,0]),direction=unit(sub(target,result[ctx.head].p));
 return {pose:result,state:{q:headQ,transition},info:{mode:done?'Forward':lookingOut?'Look out':'Look in',done,target,lookOutTick,remainingDegrees:remaining,aimErrorDegrees:Math.acos(Math.max(-1,Math.min(1,dot(forward,direction))))*180/Math.PI,angularStep:angle(previous,headQ),speedLimit:speed,exponent}};
}
const api={make,apply,step,angle};if(typeof module!=='undefined')module.exports=api;else root.HeadLook=api;
})(globalThis);
