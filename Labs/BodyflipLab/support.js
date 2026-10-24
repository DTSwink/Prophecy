/* Deterministic support planning and two-bone IK. No inference or playback history. */
(function(root){
'use strict';
const R=typeof module!=='undefined'?require('./recovery.js'):root.Recovery;
const {add,sub,mul,dot,cross,length,unit,rotate,qm,qinv,qslerp,fromTo}=R;
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const toward=(a,b,d)=>add(a,mul(sub(b,a),Math.min(1,d/(length(sub(b,a))||1))));
function ground(edge){return {normal:[0,1,0],project:p=>[p[0],0,p[2]],closest:p=>[clamp(p[0],-1.8,1.8),0,clamp(p[2],-3,edge)]};}
function com(p,names,parents,reference){
 let sum=[0,0,0],total=0;
 for(let i=1;i<names.length;i++){
  const child=parents.findIndex((v,j)=>v===i&&!names[j].startsWith('clavicle')&&!names[j].startsWith('thigh'));
  const delta=child>0?sub(reference.points[child],reference.points[i]):rotate(reference.q[i],[names[i]==='head'?.12:.045,0,0]);
  const offset=rotate(qinv(reference.q[i]),mul(delta,.5)),mass=names[i]==='pelvis'?8:names[i].startsWith('thigh')?5:names[i].startsWith('spine')?2:1;
  sum=add(sum,mul(add(p.points[i],rotate(p.q[i],offset)),mass));total+=mass;
 }
 return mul(sum,1/total);
}
// Ankle clearance from the displayed foot/toe boxes. The contact marker is on
// the surface, rather than putting the ankle origin through the ground.
function clearance(p,ankle,toe){
 return -Math.min(...solePoints(p,ankle,toe).map(v=>v[1]));
}
function solePoints(p,ankle,toe){
 const a=p.axes[ankle],b=p.axes[toe],delta=sub(p.points[toe],p.points[ankle]);
 const forward=mul(a[1],dot(a[1],delta)<0?-1:1),up=mul(a[0],a[0][1]<0?-1:1);
 const tf=mul(b[0],dot(b[0],forward)<0?-1:1),tu=mul(b[1],b[1][1]<0?-1:1);
 let ts=unit(cross(tf,tu));if(dot(ts,b[2])<0)ts=mul(ts,-1);
 let top=unit(cross(ts,tf));if(top[1]<0)top=mul(top,-1);
 const corners=(c,f,s,u,d)=>[-1,1].flatMap(x=>[-1,1].map(y=>add(add(add(c,mul(f,x*d[0]/2)),mul(s,y*d[1]/2)),mul(u,-d[2]/2))));
 return [...corners(add(add(delta,mul(forward,-.0875)),mul(up,-.006)),forward,a[2],up,[.175,.120,.051]),...corners(add(add(delta,mul(tf,.024)),mul(top,-.006)),tf,ts,top,[.048,.120,.049])];
}
function leg(p,names,side){
 const [hip,knee,foot,toe]=['thigh','calf','foot','ball'].map(n=>names.indexOf(n+'_'+side.toLowerCase()));
 const upper=length(sub(p.points[knee],p.points[hip])),lower=length(sub(p.points[foot],p.points[knee]));
 return {side,hip,knee,foot,toe,upper,lower,reach:upper+lower,clearance:clearance(p,foot,toe),footQ:p.q[foot],toeQ:p.q[toe],toeLocal:rotate(qinv(p.q[foot]),sub(p.points[toe],p.points[foot])),pole:sub(p.points[knee],p.points[hip])};
}
function orientedFoot(l,rotation){
 const points=[],axes=[];points[l.foot]=[0,0,0];points[l.toe]=rotate(rotation.footQ,l.toeLocal);
 axes[l.foot]=R.toAxes(rotation.footQ);axes[l.toe]=R.toAxes(rotation.toeQ);return {points,axes};
}
function plantRotation(p,l,normal,pitch){
 const f=unit(sub(rotate(p.q[0],[0,0,1]),mul(normal,dot(rotate(p.q[0],[0,0,1]),normal)))),right=unit(cross(normal,f)),a=pitch*Math.PI/180;
 const forward=add(mul(f,Math.cos(a)),mul(normal,Math.sin(a))),up=add(mul(normal,Math.cos(a)),mul(f,-Math.sin(a))),target=R.fromAxes([right,up,forward]);
 const align=(q,forward,up)=>qm(qm(target,qinv(R.fromAxes([unit(cross(up,forward)),up,forward]))),q);
 const footAxes=p.axes[l.foot],toeAxes=p.axes[l.toe],delta=sub(p.points[l.toe],p.points[l.foot]);
 const ff=mul(footAxes[1],dot(footAxes[1],delta)<0?-1:1),fu=mul(footAxes[0],footAxes[0][1]<0?-1:1);
 const tf=mul(toeAxes[0],dot(toeAxes[0],ff)<0?-1:1),tu=mul(toeAxes[1],toeAxes[1][1]<0?-1:1);
 return {footQ:align(l.footQ,ff,fu),toeQ:align(l.toeQ,tf,tu),right};
}
const blendRotation=(a,b,u)=>({footQ:qslerp(a.footQ,b.footQ,u),toeQ:qslerp(a.toeQ,b.toeQ,u)});
function landingTarget(requested,l,surface){
 const points=solePoints(orientedFoot(l,l.plant||l),l.foot,l.toe),height=Math.min(...points.map(p=>dot(p,surface.normal)));
 const low=points.filter(p=>dot(p,surface.normal)<height+1e-8),offset=mul(low.reduce((sum,p)=>add(sum,p),[0,0,0]),1/low.length);
 const wanted=add(requested,sub(offset,mul(surface.normal,height))),contact=surface.closest(wanted),target=sub(contact,offset);
 return {surface:contact,target,ground:sub(target,mul(surface.normal,-height)),limited:length(sub(wanted,contact))>1e-6};
}
function ideal(p,legs,surface,rootSpeed,settings){
 const n=surface.normal,tangent=v=>sub(v,mul(n,dot(v,n)));
 const center=(surface.project||surface.closest)(p.points[1]),hipAxis=sub(p.points[legs[1].hip],p.points[legs[0].hip]),halfWidth=length(hipAxis)/2,right=unit(tangent(hipAxis));
 const shift=tangent(rotate(p.q[0],[0,0,rootSpeed*settings.supportAlpha/200]));
 return legs.map(l=>{
  const raw=add(center,mul(right,l.side==='L'?-halfWidth:halfWidth));
  const requested=add(raw,shift),hit=landingTarget(requested,l,surface),base=landingTarget(raw,l,surface);
  return {requested,raw,foot:l.side,distance:length(sub(p.points[l.foot],hit.target)),...hit,shift,appliedShift:sub(hit.ground,base.ground)};
 });
}
function solve(p,l,target,parents,ratio=1,rotation=l){
 const local=R.localize(p.points,p.q,parents),hip=p.points[l.hip],a=l.upper,b=l.lower;
 local.p[l.knee]=mul(unit(local.p[l.knee]),a);local.p[l.foot]=mul(unit(local.p[l.foot]),b);
 const delta=sub(target,hip),d=clamp(length(delta),Math.abs(a-b)+1e-6,(a+b)*ratio-1e-6),axis=length(delta)>1e-8?unit(delta):[0,-1,0];
 let pole=sub(l.pole,mul(axis,dot(l.pole,axis)));
 if(length(pole)<1e-6)pole=cross(axis,[1,0,0]);if(length(pole)<1e-6)pole=cross(axis,[0,0,1]);
 const along=(a*a-b*b+d*d)/(2*d),bend=Math.sqrt(Math.max(0,a*a-along*along));
 const knee=add(hip,add(mul(axis,along),mul(unit(pole),bend))),foot=add(hip,mul(axis,d));
 const hq=qm(fromTo(sub(p.points[l.knee],hip),sub(knee,hip)),p.q[l.hip]);
 const kq=qm(fromTo(sub(p.points[l.foot],p.points[l.knee]),sub(foot,knee)),p.q[l.knee]);
 local.q[l.hip]=qm(qinv(p.q[parents[l.hip]]),hq);local.q[l.knee]=qm(qinv(hq),kq);
 local.q[l.foot]=qm(qinv(kq),rotation.footQ);local.q[l.toe]=qm(qinv(rotation.footQ),rotation.toeQ);local.p[l.toe]=l.toeLocal;
 return R.fk(local,parents);
}
function blendLeg(p,release,l,amount,parents){
 const local=R.localize(p.points,p.q,parents);
 for(const i of [l.hip,l.knee,l.foot,l.toe])local.q[i]=qslerp(release.q[i],local.q[i],amount);
 for(const i of [l.knee,l.foot])local.p[i]=R.offsetBlend(release.p[i],local.p[i],amount);
 return R.fk(local,parents);
}
function plan(end,names,parents,settings,surface,forwardSpeed,poseAt=null){
 const legs=['L','R'].map(s=>{const l=leg(end,names,s);l.plant=plantRotation(end,l,surface.normal,-(settings.plantPitch??10));l.clearance=clearance(orientedFoot(l,l.plant),l.foot,l.toe);return l;}),scores=ideal(end,legs,surface,forwardSpeed,settings);
 const selected=settings.jumpFoot==='Auto'?(scores[0].distance<=scores[1].distance?0:1):settings.jumpFoot==='L'?0:1;
 const l=legs[selected],maxReach=l.reach*settings.supportReach,dt=1/240,frames=[],footSpeed=settings.supportSpeed/100;
 const body=poseAt||(t=>({...end,points:end.points.map(p=>add(p,[0,0,forwardSpeed*t]))}));
 const toLocal=(p,v)=>rotate(qinv(p.q[0]),sub(v,p.points[0])),toWorld=(p,v)=>add(p.points[0],rotate(p.q[0],v));
 // Carry the prepared ideal and its base in the root frame, before ground clamping.
 const idealLocal=toLocal(end,scores[selected].requested),rawLocal=toLocal(end,scores[selected].raw);
 let localFoot=toLocal(end,end.points[l.foot]),jumpDelay=Infinity,abortDelay=Infinity,failureReason=null,rotationProgress=0;
 const query=p=>{const raw=toWorld(p,rawLocal),requested=toWorld(p,idealLocal),hit=landingTarget(requested,l,surface),base=landingTarget(raw,l,surface);
  return {...hit,shift:sub(requested,raw),appliedShift:sub(hit.ground,base.ground)};};
 const record=(t,p,foot,target,rotation)=>frames.push({t,rotation,root:p.points[0].slice(),advance:p.points[0][2]-end.points[0][2],foot,localFoot:toLocal(p,foot),target:target.target,surface:target.surface,distance:length(sub(foot,target.target)),reachable:length(sub(target.target,p.points[l.hip]))<=maxReach,shift:target.shift,appliedShift:target.appliedShift,limited:target.limited});
 record(0,end,end.points[l.foot].slice(),query(end),l);
 // Fixed authored substeps; no body hold and no dependency on playback history.
 const limit=Math.min(30,2+scores[selected].distance/footSpeed*2);
 for(let step=1;step<=Math.ceil(limit/dt);step++){
  const t=step*dt,p=body(t),target=query(p);
  localFoot=toward(localFoot,toLocal(p,target.target),footSpeed*dt);
  const candidate=toWorld(p,localFoot),progress=clamp(1-length(sub(candidate,target.target))/Math.max(1e-8,scores[selected].distance),0,1);
  let u=Math.max(rotationProgress,progress*progress*(3-2*progress));
  const room=dot(sub(candidate,target.surface),surface.normal),height=u=>clearance(orientedFoot(l,blendRotation(l,l.plant,u)),l.foot,l.toe);
  // Keep ankle travel speed unchanged. If interpolating the shoe would sweep
  // through the floor, advance its flattening (or delay its raising) just enough.
  if(height(u)>room+1e-8){
   if(height(1)<=room+1e-8){let lo=u,hi=1;for(let i=0;i<20;i++){const mid=(lo+hi)/2;if(height(mid)>room)lo=mid;else hi=mid;}u=hi;}
   else {let lo=rotationProgress,hi=u;for(let i=0;i<20;i++){const mid=(lo+hi)/2;if(height(mid)<=room+1e-8)lo=mid;else hi=mid;}u=lo;}
  }
  rotationProgress=u;const rotation=blendRotation(l,l.plant,u);
  const solved=solve(p,l,toWorld(p,localFoot),parents,1,rotation),foot=solved.points[l.foot];
  localFoot=toLocal(p,foot);record(t,p,foot,target,rotation);
  const current=frames.at(-1),previous=frames.at(-2);
  // Compare the actually reachable ankle each tick; 0.01 mm ignores float noise.
  if(current.distance>previous.distance+1e-5){abortDelay=t;failureReason='Distance growing';break;}
  // The distance gate alone is not contact: pinning there can freeze a sole
  // centimetres above the floor. Keep approaching at the requested speed until
  // the displayed sole reaches the surface, with an actually reachable ankle.
  const soleGap=dot(sub(foot,target.surface),surface.normal)-clearance(solved,l.foot,l.toe);
  if(current.distance<=settings.supportTrigger+1e-7&&current.reachable&&Math.abs(soleGap)<=1e-5&&rotationProgress>=1-1e-5){jumpDelay=t;break;}
 }
 if(!Number.isFinite(jumpDelay)&&!Number.isFinite(abortDelay)){abortDelay=frames.at(-1).t;failureReason='No reachable contact';}
 function sample(t){
  const f=clamp(t/dt,0,frames.length-1),i=Math.min(frames.length-1,Math.floor(f)),a=frames[i],b=frames[Math.min(i+1,frames.length-1)],u=f-i;
  const lerp=(a,b)=>add(a,mul(sub(b,a),u)),p=body(a.t+(b.t-a.t)*u),rotation=blendRotation(a.rotation,b.rotation,u),pose=solve(p,l,lerp(a.foot,b.foot),parents,1,rotation),foot=pose.points[l.foot],target=lerp(a.target,b.target);
  return {pose,foot,rotation,target,surface:lerp(a.surface,b.surface),distance:length(sub(foot,target)),advance:a.advance+(b.advance-a.advance)*u,shift:lerp(a.shift,b.shift),appliedShift:lerp(a.appliedShift,b.appliedShift),limited:b.limited};
 }
 return {leg:l,scores,jumpDelay,abortDelay,failureReason,idealLocal,frames,sample,terminal:sample(frames.at(-1).t),maxReach,rootSpeed:forwardSpeed};
}
// Roll the rigid sole over its convex lower outline. Every support-vertex
// transition is solved analytically, so arbitrary seeks cannot accumulate slip.
function roll(terminal,l,surface,angle){
 const axis=l.plant.right,points=solePoints(terminal.pose,l.foot,l.toe),end=Math.max(0,angle*Math.PI/180),cuts=[0,end],segments=[];
 const rotated=(p,a)=>rotate(R.qexp(mul(axis,a)),p);
 for(let i=0;i<points.length;i++)for(let j=0;j<i;j++){
  const d=sub(points[i],points[j]),a=dot(surface.normal,d),b=dot(surface.normal,cross(axis,d));
  if(Math.abs(a)+Math.abs(b)<1e-10)continue;
  const theta=Math.atan2(-a,b);for(let k=-1;k<=1;k++){const x=theta+k*Math.PI;if(x>1e-9&&x<end-1e-9)cuts.push(x);}
 }
 cuts.sort((a,b)=>a-b);let ankle=terminal.foot;
 for(let i=0;i<cuts.length-1;i++){
  const a=cuts[i],b=cuts[i+1];if(b-a<1e-9)continue;
  const mid=(a+b)/2,heights=points.map(p=>dot(surface.normal,rotated(p,mid))),lowest=Math.min(...heights);
  // Average the equal-height lateral corners to keep the contact marker centered.
  const active=points.filter((_,j)=>heights[j]<lowest+1e-8),pivot=mul(active.reduce((sum,p)=>add(sum,p),[0,0,0]),1/active.length),anchor=add(ankle,rotated(pivot,a));
  segments.push({a,b,pivot,anchor});ankle=sub(anchor,rotated(pivot,b));
 }
 return u=>{
  const a=end*clamp(u,0,1),s=segments.find(s=>a<s.b-1e-10)||segments.at(-1),q=R.qexp(mul(axis,a));
  const foot=s?sub(s.anchor,rotated(s.pivot,a)):terminal.foot,contact=s?s.anchor:add(foot,points.reduce((p,v)=>v[1]<p[1]?v:p));
  return {foot,contact,rotation:{footQ:qm(q,terminal.rotation.footQ),toeQ:qm(q,terminal.rotation.toeQ)},valid:length(sub(surface.closest(contact),contact))<2e-5};
 };
}
const api={ground,com,leg,ideal,solve,blendLeg,plan,toward,roll};if(typeof module!=='undefined')module.exports=api;else root.BodyflipSupport=api;
})(globalThis);
