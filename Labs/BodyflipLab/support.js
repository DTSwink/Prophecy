/* Deterministic support planning and two-bone IK. No inference or playback history. */
(function(root){
'use strict';
const R=typeof module!=='undefined'?require('./recovery.js'):root.Recovery;
const C=typeof module!=='undefined'?require('./core.js'):root.BodyflipCore;
const {add,sub,mul,dot,cross,length,unit,rotate,qm,qinv,qslerp,fromTo}=R;
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const toward=(a,b,d)=>add(a,mul(sub(b,a),Math.min(1,d/(length(sub(b,a))||1))));
// Finite rectangles share one tangent-space query with rendering and Jolt.
function rectangle(id,origin,u,v,bounds,thickness=.12){
 const normal=unit(cross(v,u)),local=p=>{const d=sub(p,origin);return [dot(d,u),dot(d,normal),dot(d,v)];};
 const world=p=>add(origin,add(mul(u,p[0]),add(mul(normal,p[1]),mul(v,p[2]))));
 const [a,b,c,d]=bounds,center=world([(a+b)/2,-thickness/2,(c+d)/2]);
 return {id,origin,u,v,normal,bounds,local,world,project:p=>{const q=local(p);q[1]=0;return world(q);},closest:p=>{const q=local(p);return world([clamp(q[0],a,b),0,clamp(q[2],c,d)]);},box:{center,dims:[b-a,thickness,d-c],forward:u,side:normal,up:v}};
}
function ground(edge){return rectangle('floor',[0,0,0],[1,0,0],[0,0,1],[-1.8,1.8,-3,edge],.4);}
function terrain(edge,ramps=true){const k=Math.SQRT1_2;return [ground(edge),...(ramps?[
 rectangle('left',[0,0,edge],[k,-k,0],[0,0,1],[-6,0,0,18]),
 rectangle('right',[0,0,edge],[k,k,0],[0,0,1],[0,6,0,18])]:[])];}
function platformRecord(surface){const b=surface.box;return {id:surface.id,position:b.center.slice(),rotation:R.fromAxes([b.forward,b.side,b.up]),size:b.dims.slice()};}
function platformSurface(p){const u=rotate(p.rotation,[1,0,0]),v=rotate(p.rotation,[0,0,1]),normal=rotate(p.rotation,[0,1,0]);return rectangle(p.id,add(p.position,mul(normal,p.size[1]/2)),u,v,[-p.size[0]/2,p.size[0]/2,-p.size[2]/2,p.size[2]/2],p.size[1]);}
function scene(edge,settings){return settings.platforms===null||settings.platforms===undefined?terrain(edge,settings.ramps):settings.platforms.filter(p=>settings.ramps||!['left','right'].includes(p.id)).map(platformSurface);}
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
// Anatomical signs belong to the rig, not world height. They must not flip
// when a foot rotates past vertical or plants on a wall.
function footFrame(p,ankle,toe,side){
 const a=p.axes[ankle],b=p.axes[toe],delta=sub(p.points[toe],p.points[ankle]),sign=side==='L'?1:-1;
 const forward=mul(a[1],dot(a[1],delta)<0?-1:1),up=mul(a[0],sign);
 const tf=mul(b[0],dot(b[0],forward)<0?-1:1),tu=mul(b[1],sign),ts=unit(cross(tf,tu));
 return {forward,up,side:a[2],toeForward:tf,toeUp:tu,toeSide:ts};
}
function clearance(p,ankle,toe,normal=[0,1,0],side){
 return -Math.min(...footPoints(p,ankle,toe,side).map(v=>dot(v,normal)));
}
function footPoints(p,ankle,toe,side){
 const f=footFrame(p,ankle,toe,side),delta=sub(p.points[toe],p.points[ankle]);
 // Query the actual box including its top when airborne/upside down. Capture
 // below aligns an inverted foot onto its sole before beginning the push.
 const corners=(c,f,s,u,d)=>[-1,1].flatMap(x=>[-1,1].flatMap(y=>[-1,1].map(z=>add(add(add(c,mul(f,x*d[0]/2)),mul(s,y*d[1]/2)),mul(u,z*d[2]/2)))));
 return [...corners(add(add(delta,mul(f.forward,-.0875)),mul(f.up,-.006)),f.forward,f.side,f.up,[.175,.120,.051]),...corners(add(add(delta,mul(f.toeForward,.024)),mul(f.toeUp,-.006)),f.toeForward,f.toeSide,f.toeUp,[.048,.120,.049])];
}
function lowestOffset(p,l,normal){
 const points=footPoints(p,l.foot,l.toe,l.side),height=Math.min(...points.map(v=>dot(v,normal)));
 const low=points.filter(v=>dot(v,normal)<height+1e-8);
 return mul(low.reduce((s,v)=>add(s,v),[0,0,0]),1/low.length);
}
// Closest point to the ideal within the cone/finite-ground intersection.
// A cone with half-angle a cuts the plane in a disk of radius height*tan(a).
function coneTarget(apex,wanted,surface,angle){
 if(surface.local){const q=coneTarget(surface.local(apex),surface.local(wanted),{normal:[0,1,0],bounds:surface.bounds,project:p=>[p[0],0,p[2]],closest:p=>[clamp(p[0],surface.bounds[0],surface.bounds[1]),0,clamp(p[2],surface.bounds[2],surface.bounds[3])]},angle);for(const k of ['apex','center','wanted','nearest','contact'])if(q[k])q[k]=surface.world(q[k]);q.normal=surface.normal;return q;}
 const normal=surface.normal,center=surface.project(apex),height=dot(sub(apex,center),normal),radius=Math.max(0,height)*Math.tan(angle*Math.PI/180);
 // Penetration does not disqualify a foot. Below the plane, use its projected
 // point; capture still uses the existing sole-to-contact distance trigger.
 const nearest=surface.closest(center),valid=length(sub(nearest,center))<=radius+1e-8;
 const info={apex,center,normal,height,radius,wanted,nearest,gap:length(sub(apex,nearest)),valid,contact:null};
 if(!valid)return info;
 const candidates=[],inside=p=>length(sub(p,center))<=radius+1e-8;
 const offer=p=>{if(inside(p)&&length(sub(surface.closest(p),p))<1e-8)candidates.push(p);};
 offer(surface.closest(wanted));
 offer(toward(center,surface.project(wanted),radius));
 const [xmin,xmax,zmin,zmax]=surface.bounds;
 // The optimum is in the disk interior, on its arc, or on a ground edge.
 for(const x of [xmin,xmax]){const d=radius*radius-(x-center[0])**2;if(d>=-1e-12){const r=Math.sqrt(Math.max(0,d)),lo=Math.max(zmin,center[2]-r),hi=Math.min(zmax,center[2]+r);if(lo<=hi)offer([x,center[1],clamp(wanted[2],lo,hi)]);}}
 for(const z of [zmin,zmax]){const d=radius*radius-(z-center[2])**2;if(d>=-1e-12){const r=Math.sqrt(Math.max(0,d)),lo=Math.max(xmin,center[0]-r),hi=Math.min(xmax,center[0]+r);if(lo<=hi)offer([clamp(wanted[0],lo,hi),center[1],z]);}}
 offer(nearest);candidates.sort((a,b)=>length(sub(a,wanted))-length(sub(b,wanted)));
 info.contact=candidates[0];return info;
}
function leg(p,names,side){
 const [hip,knee,foot,toe]=['thigh','calf','foot','ball'].map(n=>names.indexOf(n+'_'+side.toLowerCase()));
 const upper=length(sub(p.points[knee],p.points[hip])),lower=length(sub(p.points[foot],p.points[knee]));
 const pelvis=names.indexOf('pelvis'),upperAxis=unit(sub(p.points[knee],p.points[hip])),lowerAxis=unit(sub(p.points[foot],p.points[knee])),axis=unit(sub(p.points[foot],p.points[hip]));
 let pole=sub(upperAxis,mul(axis,dot(upperAxis,axis)));
 if(length(pole)<1e-5){const forward=rotate(p.q[pelvis],[0,1,0]);pole=sub(forward,mul(axis,dot(forward,axis)));}
 if(length(pole)<1e-5)pole=cross(axis,rotate(p.q[pelvis],[0,0,1]));
 pole=unit(pole);const normal=unit(cross(axis,pole));
 return {side,hip,knee,foot,toe,pelvis,upper,lower,reach:upper+lower,clearance:clearance(p,foot,toe,[0,1,0],side),footQ:p.q[foot],toeQ:p.q[toe],toeLocal:rotate(qinv(p.q[foot]),sub(p.points[toe],p.points[foot])),pole,
  axisLocal:rotate(qinv(p.q[pelvis]),axis),poleLocal:rotate(qinv(p.q[pelvis]),pole),normal,upperAxis,lowerAxis,hipQ:p.q[hip],kneeQ:p.q[knee],
  kneeLocal:rotate(qinv(p.q[hip]),sub(p.points[knee],p.points[hip])),ankleLocal:rotate(qinv(p.q[knee]),sub(p.points[foot],p.points[knee]))};
}
function orientedFoot(l,rotation){
 const points=[],axes=[];points[l.foot]=[0,0,0];points[l.toe]=rotate(rotation.footQ,l.toeLocal);
 axes[l.foot]=R.toAxes(rotation.footQ);axes[l.toe]=R.toAxes(rotation.toeQ);return {points,axes};
}
function plantRotation(p,l,normal,pitch){
 // Imported jump roots use a different basis from locomotion roots. Character
 // forward is pelvis -Y in this rig; take its heading before fitting the slope
 // so pelvis lean/descent cannot yaw the shoe sideways on inclined ground.
 const tangent=v=>sub(v,mul(normal,dot(v,normal))),facing=rotate(p.q[l.pelvis],[0,-1,0]);
 let heading=[facing[0],0,facing[2]];
 if(length(heading)<1e-6){const right=rotate(p.q[l.pelvis],[0,0,1]);heading=cross([0,1,0],right);}
 let f=tangent(unit(heading));
 if(length(f)<1e-6)f=tangent([0,1,0]);if(length(f)<1e-6)f=tangent([1,0,0]);f=unit(f);
 const right=unit(cross(normal,f)),a=pitch*Math.PI/180;
 const forward=add(mul(f,Math.cos(a)),mul(normal,Math.sin(a))),up=add(mul(normal,Math.cos(a)),mul(f,-Math.sin(a))),target=R.fromAxes([right,up,forward]);
 const align=(q,forward,up)=>qm(qm(target,qinv(R.fromAxes([unit(cross(up,forward)),up,forward]))),q);
 const frame=footFrame(p,l.foot,l.toe,l.side);
 return {footQ:align(l.footQ,frame.forward,frame.up),toeQ:align(l.toeQ,frame.toeForward,frame.toeUp),right};
}
const blendRotation=(a,b,u)=>({footQ:qslerp(a.footQ,b.footQ,u),toeQ:qslerp(a.toeQ,b.toeQ,u)});
function landingTarget(requested,l,surface){
 const points=footPoints(orientedFoot(l,l.plant||l),l.foot,l.toe,l.side),height=Math.min(...points.map(p=>dot(p,surface.normal)));
 const low=points.filter(p=>dot(p,surface.normal)<height+1e-8),offset=mul(low.reduce((sum,p)=>add(sum,p),[0,0,0]),1/low.length);
 const wanted=add(requested,sub(offset,mul(surface.normal,height))),contact=surface.closest(wanted),target=sub(contact,offset);
 return {surface:contact,target,ground:sub(target,mul(surface.normal,-height)),limited:length(sub(wanted,contact))>1e-6};
}
function ideal(p,legs,surface,rootSpeed,settings){
 const n=surface.normal,tangent=v=>sub(v,mul(n,dot(v,n)));
 const center=(surface.project||surface.closest)(p.points[1]),hipAxis=sub(p.points[legs[1].hip],p.points[legs[0].hip]),halfWidth=length(hipAxis)/2,right=unit(tangent(hipAxis));
 // Runtime callers supply actual world velocity, including descent onto slopes.
 // Scalar callers retain the forward-gait convenience API.
 const velocity=Array.isArray(rootSpeed)?rootSpeed:rotate(p.q[0],[0,0,rootSpeed]);
 const shift=mul(tangent(velocity),settings.supportAlpha/200);
 return legs.map(l=>{
  const raw=add(center,mul(right,l.side==='L'?-halfWidth:halfWidth));
  const requested=add(raw,shift),hit=landingTarget(requested,l,surface),base=landingTarget(raw,l,surface);
  return {requested,raw,foot:l.side,distance:length(sub(p.points[l.foot],hit.target)),...hit,shift,appliedShift:sub(hit.ground,base.ground)};
 });
}
function solve(p,l,target,parents,ratio=1,rotation=l){
 const local=R.localize(p.points,p.q,parents),hip=p.points[l.hip],a=l.upper,b=l.lower;
 local.p[l.knee]=l.kneeLocal;local.p[l.foot]=l.ankleLocal;
 // Use the same reach boundary as planning. Subtracting a second epsilon here
 // locked the knee just before release, so its displayed and seeded speeds differed.
 const delta=sub(target,hip),d=clamp(length(delta),Math.abs(a-b)+1e-6,Math.min((a+b)*ratio,a+b-1e-8)),axis=length(delta)>1e-8?unit(delta):[0,-1,0];
 // Transport the actual bend direction with the pelvis and aim of the leg.
 // Projecting hip->knee onto a new aim can invert the pole near alignment.
 const referenceAxis=rotate(p.q[l.pelvis],l.axisLocal),referencePole=rotate(p.q[l.pelvis],l.poleLocal);
 const swing=dot(referenceAxis,axis)<-.999999?[...referencePole,0]:fromTo(referenceAxis,axis);
 const pole=rotate(swing,referencePole),normal=unit(cross(axis,pole));
 const along=(a*a-b*b+d*d)/(2*d),bend=Math.sqrt(Math.max(0,a*a-along*along));
 const knee=add(hip,add(mul(axis,along),mul(unit(pole),bend))),foot=add(hip,mul(axis,d));
 // Both bones share the same hinge plane: independent shortest swings leave
 // different twists on the thigh and calf, producing a broken-looking knee.
 const frame=(direction,n)=>R.fromAxes([direction,n,cross(direction,n)]);
 const align=(before,after,q)=>qm(qm(frame(unit(after),normal),qinv(frame(before,l.normal))),q);
 const hq=align(l.upperAxis,sub(knee,hip),l.hipQ),kq=align(l.lowerAxis,sub(foot,knee),l.kneeQ);
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
// Surface ranking and the actual planner must agree on the same foot/contact.
function candidates(p,names,settings,surface,velocity){
 const legs=['L','R'].map(s=>{const l=leg(p,names,s);l.plant=plantRotation(p,l,surface.normal,-(settings.plantPitch??10));l.clearance=clearance(orientedFoot(l,l.plant),l.foot,l.toe,surface.normal,l.side);return l;}),scores=ideal(p,legs,surface,velocity,settings);
 for(let i=0;i<legs.length;i++){
  const l=legs[i],score=scores[i];
  score.cone=coneTarget(add(p.points[l.foot],lowestOffset(p,l,surface.normal)),score.surface,surface,settings.supportCone??30);
  // Compare the same planted-ankle travel as the planner, after each foot's
  // cone has constrained its contact. Keep the unconstrained ideal for carry.
  score.idealDistance=score.distance;
  score.constrainedSurface=score.cone.contact||surface.closest(score.cone.apex);
  score.constrainedTarget=sub(score.constrainedSurface,lowestOffset(orientedFoot(l,l.plant),l,surface.normal));
  score.distance=length(sub(p.points[l.foot],score.constrainedTarget));
  // A cone can intersect a distant slab which the leg can never reach.
  score.inRange=length(sub(surface.closest(p.points[l.hip]),p.points[l.hip]))<=l.reach+Math.max(0,l.clearance)+1e-6;
  score.eligible=score.cone.valid&&score.inRange;
 }
 const allowed=[0,1].filter(i=>settings.jumpFoot==='Auto'||legs[i].side===settings.jumpFoot),valid=allowed.filter(i=>scores[i].eligible);
 const selected=(valid.length?valid:allowed).reduce((a,b)=>scores[a].distance<=scores[b].distance?a:b);
 return {legs,scores,selected};
}
function plan(end,names,parents,settings,surface,forwardSpeed,poseAt=null,velocity=null){
 const {legs,scores,selected}=candidates(end,names,settings,surface,velocity??forwardSpeed);
 const l=legs[selected],maxReach=l.reach*settings.supportReach,dt=1/240,frames=[],footSpeed=settings.supportSpeed/100;
 const body=poseAt||(t=>({...end,points:end.points.map(p=>add(p,[0,0,forwardSpeed*t]))}));
 const toLocal=(p,v)=>rotate(qinv(p.q[0]),sub(v,p.points[0])),toWorld=(p,v)=>add(p.points[0],rotate(p.q[0],v));
 // Carry the prepared ideal and its base in the root frame, before ground clamping.
 const idealLocal=toLocal(end,scores[selected].requested),rawLocal=toLocal(end,scores[selected].raw);
 const idealsLocal=scores.map(s=>toLocal(end,s.requested));
 const idealTargets=p=>legs.map((leg,i)=>({foot:leg.side,selected:i===selected,distance:scores[i].distance,eligible:scores[i].eligible,point:landingTarget(toWorld(p,idealsLocal[i]),leg,surface).surface}));
 let localFoot=toLocal(end,end.points[l.foot]),jumpDelay=Infinity,abortDelay=Infinity,failureReason=null,rotationProgress=0,approachSpeed=0,reachWait=0;
 const query=(p,ankle,rotation)=>{
  const raw=toWorld(p,rawLocal),requested=toWorld(p,idealLocal),idealHit=landingTarget(requested,l,surface),base=landingTarget(raw,l,surface);
  const offset=lowestOffset(orientedFoot(l,rotation),l,surface.normal),apex=add(ankle,offset),cone=coneTarget(apex,idealHit.surface,surface,settings.supportCone??30);
  const contact=cone.contact||surface.closest(apex),plantOffset=lowestOffset(orientedFoot(l,l.plant),l,surface.normal),target=sub(contact,plantOffset);
  return {target,surface:contact,cone,edgeLimited:idealHit.limited,coneLimited:length(sub(contact,idealHit.surface))>1e-6,shift:sub(requested,raw),appliedShift:sub(contact,base.surface),limited:idealHit.limited||length(sub(contact,idealHit.surface))>1e-6};
 };
 const record=(t,p,foot,target,rotation)=>frames.push({t,rotation,approachSpeed,reachWait,hipDistance:length(sub(foot,p.points[l.hip])),cone:target.cone,edgeLimited:target.edgeLimited,coneLimited:target.coneLimited,root:p.points[0].slice(),advance:p.points[0][2]-end.points[0][2],foot,localFoot:toLocal(p,foot),target:target.target,surface:target.surface,distance:length(sub(add(foot,lowestOffset(orientedFoot(l,rotation),l,surface.normal)),target.surface)),reachable:length(sub(target.target,p.points[l.hip]))<=maxReach,shift:target.shift,appliedShift:target.appliedShift,limited:target.limited});
 // Gate is sole-to-ground proximity, including at t=0. Capture that nearby
 // cone-valid contact immediately; do not wait for the ideal or Plant rotation.
 function capture(t,p,ankle,rotation,hit){
  if(!hit.cone.valid||hit.cone.gap>settings.supportTrigger+1e-7)return false;
  if(dot(footFrame(orientedFoot(l,rotation),l.foot,l.toe,l.side).up,surface.normal)<=0)rotation=l.plant;
  const offset=lowestOffset(orientedFoot(l,rotation),l,surface.normal),foot=sub(hit.surface,offset);
  if(length(sub(foot,p.points[l.hip]))>maxReach)return false;
  const pose=solve(p,l,foot,parents,settings.supportReach,rotation);
  if(length(sub(pose.points[l.foot],foot))>2e-5)return false;
  if(frames.at(-1)?.t===t)frames.pop();
  record(t,p,foot,{...hit,target:foot},rotation);jumpDelay=t;return true;
 }
 const initial=query(end,end.points[l.foot],l);
 record(0,end,end.points[l.foot].slice(),initial,l);
 if(!initial.cone.valid){abortDelay=0;failureReason='No ground in cone';}
 else capture(0,end,end.points[l.foot],l,initial);
 // Fixed authored substeps; no body hold and no dependency on playback history.
 const limit=Math.min(30,2+scores[selected].idealDistance/footSpeed*2);
 for(let step=1;!Number.isFinite(jumpDelay)&&!Number.isFinite(abortDelay)&&step<=Math.ceil(limit/dt);step++){
  const t=step*dt,p=body(t),target=query(p,toWorld(p,localFoot),blendRotation(l,l.plant,rotationProgress));
  if(!target.cone.valid){abortDelay=t;failureReason='No ground in cone';break;}
  // Spend the available extension over the predicted wait for the pelvis,
  // rather than arriving too early and letting IK clip the remaining travel.
  const carried=toWorld(p,localFoot),delta=sub(target.target,carried),distance=length(delta),direction=unit(delta),relative=sub(carried,p.points[l.hip]);
  const along=dot(relative,direction),disc=along*along+maxReach*maxReach-dot(relative,relative);
  const travelRoom=disc>=0?Math.max(0,-along+Math.sqrt(disc)):0;
  let advance=Math.min(distance,footSpeed*dt,travelRoom);reachWait=0;
  const extension=length(sub(target.target,p.points[l.hip]))-maxReach;
  if(extension>0&&advance>0){
   // One playback frame of the existing incoming motion supplies the closing
   // rate. It does not change the root path or introduce a new motion option.
   const horizon=1/60,next=body(t+horizon),nextTarget=query(next,toWorld(next,localFoot),blendRotation(l,l.plant,rotationProgress));
   const nextExtension=length(sub(nextTarget.target,next.points[l.hip]))-maxReach,closing=(extension-nextExtension)/horizon;
   if(closing>1e-6){reachWait=extension/closing;advance=Math.min(advance,travelRoom*dt/Math.max(dt,reachWait));}
  }
  approachSpeed=advance/dt;
  localFoot=toward(localFoot,toLocal(p,target.target),advance);
  const candidate=toWorld(p,localFoot),progress=clamp(1-length(sub(candidate,target.target))/Math.max(1e-8,scores[selected].idealDistance),0,1);
  let u=Math.max(rotationProgress,progress*progress*(3-2*progress));
  const room=dot(sub(candidate,target.surface),surface.normal),height=u=>clearance(orientedFoot(l,blendRotation(l,l.plant,u)),l.foot,l.toe,surface.normal,l.side);
  // Keep ankle travel speed unchanged. If interpolating the shoe would sweep
  // through the floor, advance its flattening (or delay its raising) just enough.
  if(height(u)>room+1e-8){
   if(height(1)<=room+1e-8){let lo=u,hi=1;for(let i=0;i<20;i++){const mid=(lo+hi)/2;if(height(mid)>room)lo=mid;else hi=mid;}u=hi;}
   else {let lo=rotationProgress,hi=u;for(let i=0;i<20;i++){const mid=(lo+hi)/2;if(height(mid)<=room+1e-8)lo=mid;else hi=mid;}u=lo;}
  }
  rotationProgress=u;const rotation=blendRotation(l,l.plant,u);
  const solved=solve(p,l,toWorld(p,localFoot),parents,1,rotation),foot=solved.points[l.foot];
  localFoot=toLocal(p,foot);const actual=query(p,foot,rotation);record(t,p,foot,actual,rotation);
  if(capture(t,p,foot,rotation,actual))break;
  const current=frames.at(-1),previous=frames.at(-2);
  // Compare actual sole-to-contact distance; 0.01 mm ignores float noise.
  if(current.distance>previous.distance+1e-5){abortDelay=t;failureReason='Distance growing';break;}

 }
 if(!Number.isFinite(jumpDelay)&&!Number.isFinite(abortDelay)){abortDelay=frames.at(-1).t;failureReason='No reachable contact';}
 function sample(t){
  const f=clamp(t/dt,0,frames.length-1),i=Math.min(frames.length-1,Math.floor(f)),a=frames[i],b=frames[Math.min(i+1,frames.length-1)],u=f-i;
  const lerp=(a,b)=>add(a,mul(sub(b,a),u)),p=body(a.t+(b.t-a.t)*u),rotation=blendRotation(a.rotation,b.rotation,u),pose=solve(p,l,lerp(a.foot,b.foot),parents,1,rotation),foot=pose.points[l.foot],target=lerp(a.target,b.target);
  return {pose,foot,rotation,target,cone:u<.5?a.cone:b.cone,surface:lerp(a.surface,b.surface),distance:length(sub(add(foot,lowestOffset(pose,l,surface.normal)),lerp(a.surface,b.surface))),advance:a.advance+(b.advance-a.advance)*u,shift:lerp(a.shift,b.shift),appliedShift:lerp(a.appliedShift,b.appliedShift),limited:b.limited,edgeLimited:b.edgeLimited,coneLimited:b.coneLimited};
 }
 const coneForPose=p=>query(p,p.points[l.foot],{footQ:p.q[l.foot],toeQ:p.q[l.toe]}).cone;
 return {leg:l,scores,jumpDelay,abortDelay,failureReason,idealLocal,idealTargets,frames,sample,coneForPose,terminal:sample(frames.at(-1).t),maxReach,rootSpeed:forwardSpeed};
}
// Roll the rigid sole over its convex lower outline. Every support-vertex
// transition is solved analytically, so arbitrary seeks cannot accumulate slip.
function roll(terminal,l,surface,angle){
 const axis=l.plant.right,points=footPoints(terminal.pose,l.foot,l.toe,l.side),end=Math.max(0,angle*Math.PI/180),cuts=[0,end],segments=[];
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
  const foot=s?sub(s.anchor,rotated(s.pivot,a)):terminal.foot,contact=s?s.anchor:add(foot,lowestOffset(terminal.pose,l,surface.normal));
  return {foot,contact,rotation:{footQ:qm(q,terminal.rotation.footQ),toeQ:qm(q,terminal.rotation.toeQ)},valid:length(sub(surface.closest(contact),contact))<2e-5};
 };
}
// Continue the captured shoe's orientation without freezing its bank. Integrate
// contact pivots once at preparation; playback/rewind just samples this table.
function contactMotion(terminal,l,surface,settings,previousRotation=null){
 const n=surface.normal,dt=1/480,start=terminal.rotation;
 // Retain the pitch already reached on approach: leveling the bank must not
 // rewind heel-to-toe motion back to the initial Plant pitch.
 const forward=footFrame(orientedFoot(l,start),l.foot,l.toe,l.side).forward;
 const pitch=-Math.asin(clamp(dot(forward,n),-1,1))*180/Math.PI;
 const pitchQ=R.qexp(mul(l.plant.right,(pitch-settings.plantPitch)*Math.PI/180));
 const goal={footQ:qm(pitchQ,l.plant.footQ),toeQ:qm(pitchQ,l.plant.toeQ),right:l.plant.right};
 const angle=(a,b)=>2*Math.acos(clamp(Math.abs(a.reduce((s,v,i)=>s+v*b[i],0)),0,1));
 const alignment=Math.max(angle(start.footQ,goal.footQ),angle(start.toeQ,goal.toeQ));
 const alignDuration=Math.max(.025,alignment/(1080*Math.PI/180));
 const rotationPose=r=>({points:[[0,0,0],[0,0,0]],q:[r.footQ,r.toeQ]});
 const alignmentMotion=C.transition(t=>rotationPose(t<0&&previousRotation?previousRotation:start),()=>rotationPose(goal),alignDuration,[-1,-1]);
 const rollAngle=Math.max(0,settings.toeOffPitch-pitch),rate=settings.footRollSpeed;
 let pushStart=Infinity,frames=[];
 const rotationAt=t=>{const pose=alignmentMotion(t),base={footQ:pose.q[0],toeQ:pose.q[1]};
  const a=Math.min(rollAngle,Math.max(0,t-pushStart)*rate)*Math.PI/180,q=R.qexp(mul(goal.right,a));
  return {footQ:qm(q,base.footQ),toeQ:qm(q,base.toeQ)};
 };
 const corners=r=>footPoints(orientedFoot(l,r),l.foot,l.toe,l.side);
 const average=(points,indices)=>mul(indices.reduce((s,i)=>add(s,points[i]),[0,0,0]),1/indices.length);
 function fit(foot,rotation){const points=corners(rotation),heights=points.map(p=>dot(p,n)),low=Math.min(...heights),indices=heights.flatMap((h,i)=>h<low+1e-8?[i]:[]);
  foot=sub(foot,mul(n,dot(sub(foot,surface.origin),n)+low));const contact=add(foot,average(points,indices));
  return {foot,rotation,contact,valid:length(sub(surface.closest(contact),contact))<2e-5};
 }
 function bake(){
  const end=Math.max(alignDuration,Number.isFinite(pushStart)?pushStart+Math.min(2.2,rate>0?rollAngle/rate:0):0);
  frames=[fit(terminal.foot,start)];let oldPoints=corners(start);
  for(let i=1;i<=Math.ceil(end/dt);i++){
   const t=i*dt,rotation=rotationAt(t),points=corners(rotation),mid=corners(rotationAt(t-dt/2)),h=mid.map(p=>dot(p,n)),low=Math.min(...h),active=h.flatMap((v,j)=>v<low+1e-8?[j]:[]);
   const foot=add(frames.at(-1).foot,sub(average(oldPoints,active),average(points,active)));
   frames.push(fit(foot,rotation));oldPoints=points;
  }
 }
 function sample(t){const f=clamp(t/dt,0,frames.length-1),i=Math.floor(f),a=frames[i],b=frames[Math.min(i+1,frames.length-1)],u=f-i;
  return fit(add(a.foot,mul(sub(b.foot,a.foot),u)),blendRotation(a.rotation,b.rotation,u));
 }
 bake();return {sample,alignDuration,startPush(t){pushStart=t;bake();}};
}
const api={footFrame,footPoints,ground,rectangle,terrain,scene,platformRecord,platformSurface,com,leg,ideal,solve,blendLeg,plan,candidates,toward,roll,contactMotion,coneTarget,lowestOffset};if(typeof module!=='undefined')module.exports=api;else root.BodyflipSupport=api;
})(globalThis);
