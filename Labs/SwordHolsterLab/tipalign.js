// Sword ownership changes at the rotation gate. All alignment is holster-local.
(function(root){
'use strict';
const R=typeof module!=='undefined'?require('./recovery.js'):root.Recovery;
const {add,sub,mul,dot,length:len,unit,qm,qinv,rotate,qslerp,fromTo}=R;
const clamp=x=>Math.max(0,Math.min(1,x));
const relative=(a,b)=>({p:rotate(qinv(b.q),sub(a.p,b.p)).map((x,i)=>x/(b.s?.[i]??1)),q:unit(qm(qinv(b.q),a.q)),s:a.s.map((x,i)=>x/(b.s?.[i]??1))});
function begin(H,setup,tip,sword,holster,hand,scale,tick,o){
 const local=relative(sword,holster),full=H.seatedSword(setup,holster),mouth=H.point(full,setup.baseBladeLocal);
 // Swing the held blade toward the entrance, then project into the allowed
 // full-rotation ball. Translation closes the residual; no remote hand target.
 const swing=fromTo(sub(H.point(sword,tip),hand.p),sub(mouth,hand.p));
 const aim=unit(qm(swing,sword.q)),angle=H.angle(full.q,aim);
 const endWorld=qslerp(full.q,aim,angle>o.sheatheRotationTolerance?o.sheatheRotationTolerance/angle:1);
 const endQ=unit(qm(qinv(holster.q),endWorld));
 const startHand=rotate(qinv(holster.q),sub(H.handForTip(setup,scale,tip,H.point(sword,tip),sword.q).p,holster.p));
 const zeroHand=H.handForTip(setup,scale,tip,mouth,endWorld);
 const axis=rotate(full.q,[0,0,1]),seat=H.compose(H.scaledGrip(setup,scale),H.seatHandAtScale(setup,full,scale));
 const span=dot(sub(H.point(seat,tip),mouth),axis);
 // Keep the grip's axial position. Align sideways at the depth already reached,
 // rather than pulling the hand back until the blade tip is exactly at 0%.
 const depth=dot(sub(hand.p,zeroHand.p),axis),insertion=depth/Math.max(span,1e-8);
 const targetTip=add(mouth,mul(axis,depth));
 const endHand=rotate(qinv(holster.q),sub(H.handForTip(setup,scale,tip,targetTip,endWorld).p,holster.p));
 const tipLocal=rotate(qinv(holster.q),sub(targetTip,holster.p));
 const rotation=H.angle(local.q,endQ),distance=len(sub(endHand,startHand));
 // Translation and rotation each run at their own speed, then stop at target.
 const translationTicks=distance/o.maxAttachedSpeed*60,rotationTicks=rotation/o.maxAttachedRotationSpeed*60;
 return {tick,ticks:Math.max(1,Math.ceil(Math.max(translationTicks,rotationTicks))),translationTicks,rotationTicks,scale,local,startHand,endHand,endQ,tipLocal,insertion};
}
function sample(H,setup,tip,dock,holster,tick){
 const elapsed=Math.max(0,tick-dock.tick),fraction=duration=>duration>0?clamp(elapsed/duration):elapsed>0?1:0;
 const q=unit(qm(holster.q,qslerp(dock.local.q,dock.endQ,fraction(dock.rotationTicks))));
 const grip=H.scaledGrip(setup,dock.scale);
 // Rotate about the grip, not the blade tip. The endpoint is still defined by
 // tip-at-mouth geometry, but its long lever cannot add hand translation.
 const goal={p:add(holster.p,rotate(holster.q,add(dock.startHand,mul(sub(dock.endHand,dock.startHand),fraction(dock.translationTicks))))),q:unit(qm(q,qinv(grip.q))),s:[1,1,1]};
 const sword=H.compose(grip,goal);
 return {goal,sword,progress:clamp(elapsed/dock.ticks)};
}
const api={begin,sample,relative};if(typeof module!=='undefined')module.exports=api;else root.HolsterTipAlign=api;
})(globalThis);
