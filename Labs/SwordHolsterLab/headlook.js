/* Authored head aim with a distributed neck; spine_05 remains the anchor. */
(function(root){
'use strict';
const R=typeof module!=='undefined'?require('./recovery.js'):root.Recovery;
const {add,sub,mul,dot,length:len,unit,qm,qinv,rotate,fromTo,qlog,qexp}=R;
const angle=(a,b)=>2*Math.acos(Math.max(-1,Math.min(1,Math.abs(dot(a,b)))))*180/Math.PI;
function make(data){return {parents:data.parents,anchor:data.names.indexOf('spine_05'),chain:['neck_01','neck_02','head'].map(n=>data.names.indexOf(n)),head:data.names.indexOf('head')};}
function limitDown(ctx,pose,q,degrees){
 if(degrees>=90)return q;
 const up=rotate(pose[ctx.anchor].q,[1,0,0]),headUp=rotate(q,[1,0,0]);
 const vertical=dot(headUp,up),limit=Math.max(0,degrees)*Math.PI/180;
 if(vertical>=Math.cos(limit))return q;
 let horizontal=sub(headUp,mul(up,vertical));
 // Clamp the head's vertical swing, not the nose's elevation. Shortening
 // this swing preserves the twist around the spine's vertical (free yaw).
 if(len(horizontal)<1e-8){const forward=rotate(q,[0,1,0]);horizontal=sub(forward,mul(up,dot(forward,up)));}
 const target=add(mul(unit(horizontal),Math.sin(limit)),mul(up,Math.cos(limit)));
 return unit(qm(fromTo(headUp,target),q));
}
function correctionLog(q,reference){
 const v=qlog(q),a=len(v);
 if(!reference)return v;
 const axis=a>1e-8?mul(v,1/a):len(reference)>1e-8?unit(reference):[1,0,0];
 const turns=Math.round((dot(reference,axis)-a)/(2*Math.PI));
 return mul(axis,a+turns*2*Math.PI);
}
function apply(ctx,pose,headQ,reference=null,neckBase=null,gazeNeckBase=null,maxDownAngle=90,parentReference=null,frameDeltas=null){
 headQ=limitDown(ctx,pose,headQ,maxDownAngle);
 const base=gazeNeckBase||neckBase||pose;
 const parentCorrection=correctionLog(unit(qm(pose[ctx.anchor].q,qinv(base[ctx.anchor].q))),parentReference);
 const correction=correctionLog(unit(qm(headQ,qinv(base[ctx.head].q))),reference),out=pose.slice();
 for(const [k,j] of ctx.chain.entries()){
  const parent=ctx.parents[j],w=(k+1)/ctx.chain.length,inherited=unit(qm(out[parent].q,qinv(base[parent].q)));
  // Keep parent cancellation and the authored head path separate. Combining
  // them in one logarithm can leave a full turn shared across the neck at exit.
  const headDelta=frameDeltas?qm(qexp(mul(frameDeltas.head,w)),qexp(mul(frameDeltas.base,-w))):qexp(mul(correction,w));
  out[j]={...pose[j],p:add(out[parent].p,rotate(inherited,mul(unit(sub(base[j].p,base[parent].p)),len(sub(pose[j].p,pose[parent].p))))),q:j===ctx.head?headQ:unit(qm(qm(headDelta,qexp(mul(parentCorrection,1-w))),base[j].q))};
 }
 return out;
}
function step(ctx,pose,base,target,state,{tick,startTick,lookOutTick,maxLookIn,maxLookOut,lookAtAlpha=1,lookInExponent=1,lookOutExponent=1,lookOutQ=null,lookInSpeedAlpha=1,handArrivalTick=null,neckBase=null,gazeNeckBase=null,maxDownAngle=90}){
 const initialPose=pose,initialQ=pose[ctx.head].q;
 const currentBase=gazeNeckBase||neckBase||base;
 if(tick<=startTick){
  const q=initialQ,correction=qlog(unit(qm(q,qinv(currentBase[ctx.head].q))));
  const worldDelta=qlog(unit(qm(q,qinv(base[ctx.head].q))));
  return {pose:initialPose,state:{q,correction,parentCorrection:[0,0,0],referenceQ:base[ctx.head].q,worldDelta,baseDelta:worldDelta},info:{mode:tick<startTick?'Idle':'Look in',done:tick<startTick,target,lookOutTick,angularStep:0}};
 }
 const lookingOut=tick>=lookOutTick,speed=lookingOut?maxLookOut:maxLookIn,previous=state.q;
 const exponent=lookingOut?lookOutExponent:lookInExponent;
 const referenceQ=state.referenceQ||base[ctx.head].q;
 const previousDelta=state.worldDelta||qlog(unit(qm(previous,qinv(referenceQ))));
 const baseDelta=correctionLog(unit(qm(currentBase[ctx.head].q,qinv(referenceQ))),state.baseDelta||previousDelta);
 let transition=state.transition;
 if(!transition||transition.lookingOut!==lookingOut)transition={lookingOut,from:previousDelta,startTick:lookingOut?tick-1:startTick,duration:null};
 const cap=speed/60*Math.PI/180,forwardQ=lookingOut&&lookOutQ?lookOutQ:base[ctx.head].q;
 let headQ=previous,desired=forwardQ,result=pose,worldDelta=previousDelta;
 for(let iteration=0;iteration<(lookingOut?1:8);iteration++){
  desired=forwardQ;
  if(!lookingOut){
   const p=apply(ctx,pose,headQ,state.correction,currentBase,null,90,state.parentCorrection,{head:worldDelta,base:baseDelta})[ctx.head].p,direction=sub(target,p);
   if(len(direction)>=1e-8){
    const aimDelta=correctionLog(fromTo(rotate(forwardQ,[0,1,0]),direction),transition.aimDelta);
    transition={...transition,aimDelta};
    desired=unit(qm(qexp(mul(aimDelta,lookAtAlpha)),forwardQ));
   }
  }
  desired=limitDown(ctx,pose,desired,maxDownAngle);
  // Keep the ungazed world reference captured at action start for BOTH phases.
  // A look-out must return through the same signed coordinates, not pick the
  // other side by measuring a fresh shortest arc from the current head.
  const targetDelta=correctionLog(unit(qm(desired,qinv(referenceQ))),transition.targetDelta||(lookingOut?baseDelta:null));
  transition={...transition,targetDelta};
  let wanted=targetDelta;
  const timeWithHand=!lookingOut&&lookInSpeedAlpha<1&&Number.isFinite(handArrivalTick)&&handArrivalTick>startTick;
  if(exponent>1||timeWithHand){
   if(transition.duration===null){
    const fastest=Math.max(1,exponent*len(sub(targetDelta,transition.from))*180/Math.PI/speed*60);
    transition={...transition,duration:timeWithHand?fastest+(Math.max(fastest,handArrivalTick-startTick)-fastest)*(1-lookInSpeedAlpha):fastest};
   }
   const u=Math.max(0,Math.min(1,(tick-transition.startTick)/transition.duration));
   const a=Math.pow(u,exponent),b=Math.pow(1-u,exponent);
   wanted=add(transition.from,mul(sub(targetDelta,transition.from),a/(a+b)));
  }
  // Refine the target without spending the tick's angular budget again.
  // Bounding the rotation-vector step also bounds world head speed.
  const change=sub(wanted,previousDelta),distance=len(change);
  worldDelta=add(previousDelta,mul(change,distance>0?Math.min(1,cap/distance):1));
  const unlimited=unit(qm(qexp(worldDelta),referenceQ));
  headQ=limitDown(ctx,pose,unlimited,maxDownAngle);
  if(headQ!==unlimited){
   // Follow the tilt boundary without spending extra angular speed on the
   // projection. A moving spine can itself require a minimum correction.
   if(angle(previous,headQ)>speed/60+1e-8){
    let best=limitDown(ctx,pose,previous,maxDownAngle),lo=0,hi=1;
    if(angle(previous,best)<=speed/60){
     const delta=sub(worldDelta,previousDelta);
     for(let k=0;k<20;k++){
      const u=(lo+hi)/2,q=limitDown(ctx,pose,unit(qm(qexp(add(previousDelta,mul(delta,u))),referenceQ)),maxDownAngle);
      if(angle(previous,q)<=speed/60){lo=u;best=q;}else hi=u;
     }
     headQ=best;
    }else headQ=best;
   }
   worldDelta=correctionLog(unit(qm(headQ,qinv(referenceQ))),worldDelta);
  }
 }
 const correction=correctionLog(unit(qm(headQ,qinv(currentBase[ctx.head].q))),state.correction);
 const parentCorrection=correctionLog(unit(qm(pose[ctx.anchor].q,qinv(currentBase[ctx.anchor].q))),state.parentCorrection);
 result=apply(ctx,pose,headQ,correction,currentBase,null,90,parentCorrection,{head:worldDelta,base:baseDelta});
 const remaining=Math.max(angle(headQ,desired),len(sub(worldDelta,transition.targetDelta))*180/Math.PI),done=lookingOut&&remaining<.001;
 const forward=rotate(headQ,[0,1,0]),direction=unit(sub(target,result[ctx.head].p));
 return {pose:result,state:{q:headQ,transition,correction,parentCorrection,referenceQ,worldDelta,baseDelta},info:{mode:done?'Forward':lookingOut?'Look out':'Look in',done,target,lookOutTick,remainingDegrees:remaining,aimErrorDegrees:Math.acos(Math.max(-1,Math.min(1,dot(forward,direction))))*180/Math.PI,angularStep:angle(previous,headQ),speedLimit:speed,exponent}};
}
const api={make,apply,step,angle,correctionLog,limitDown};if(typeof module!=='undefined')module.exports=api;else root.HeadLook=api;
})(globalThis);
