/* Palm support uses the same finite-surface cone, reach pacing and contact gate
 * as foot support. Prepared torso/arm motion is deterministic under seeks. */
(function(root){
'use strict';
const node=typeof module!=='undefined',R=node?require('./recovery.js'):root.Recovery,C=node?require('./core.js'):root.BodyflipCore,S=node?require('./support.js'):root.BodyflipSupport,W=node?require('./wrist.js'):root.BodyflipWrist,N=node?require('./hand-inertia.js'):root.BodyflipHandInertia;
const {add,sub,mul,dot,cross,length,unit,rotate,qm,qinv,qexp,qslerp}=R,clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const smooth=x=>{x=clamp(x,0,1);return x*x*x*(10+x*(-15+6*x));};
// Root orientation in the rendered jump can contain the preceding body flip.
// Hand targets travel with the carrier, not with that presentation rotation.
// Reframe the root only: every physical bone keeps its world transform.
function reframe(p){const q=p.q.slice();q[0]=[0,0,0,1];return {...p,q,axes:q.map(R.toAxes)};}
let wristReference=null;
function registerRig(reference){wristReference=reference;}
function arm(p,names,side){
 // Keep the elbow bend plane in the root frame during the authored torso fold.
 // Transporting it with the chest lifts the elbow over the head as the chest
 // pitches through horizontal, even though the hand is reaching down.
 const [hip,knee,foot]=['upperarm','lowerarm','hand'].map(n=>names.indexOf(n+'_'+side.toLowerCase())),pelvis=0;
 const wrist=W.create(wristReference||p,knee,foot,side),wristStart=wrist.toConstraint(p.q[knee],p.q[foot]);
 const upperAxis=unit(sub(p.points[knee],p.points[hip])),lowerAxis=unit(sub(p.points[foot],p.points[knee])),axis=unit(sub(p.points[foot],p.points[hip]));
 let pole=sub(upperAxis,mul(axis,dot(upperAxis,axis)));
 if(length(pole)<1e-6){const back=rotate(p.q[pelvis],[0,1,0]);pole=sub(back,mul(axis,dot(back,axis)));}pole=unit(pole);
 const normal=unit(cross(axis,pole)),upper=length(sub(p.points[knee],p.points[hip])),lower=length(sub(p.points[foot],p.points[knee]));
 return {kind:'hand',wrist,wristStart,side,hip,knee,foot,toe:-1,pelvis,upper,lower,reach:upper+lower,footQ:p.q[foot],toeQ:p.q[foot],pole,normal,upperAxis,lowerAxis,hipQ:p.q[hip],kneeQ:p.q[knee],axisLocal:rotate(qinv(p.q[pelvis]),axis),poleLocal:rotate(qinv(p.q[pelvis]),pole),kneeLocal:rotate(qinv(p.q[hip]),sub(p.points[knee],p.points[hip])),ankleLocal:rotate(qinv(p.q[knee]),sub(p.points[foot],p.points[knee]))};
}
// Exact dimensions/offset/signs of renderer.handBox. Palm is the yellow face.
function corners(p,hand,side){
 const a=p.axes[hand],f=mul(a[0],side==='L'?1:-1),n=a[1],s=a[2],center=add(mul(f,.0725),mul(n,-.0025));
 return [-1,1].flatMap(x=>[-1,1].flatMap(y=>[-1,1].map(z=>add(center,add(mul(f,x*.0725),add(mul(s,y*.045),mul(n,z*.0225)))))));
}
function oriented(l,r){const axes=[],points=[];axes[l.foot]=R.toAxes(r.footQ);points[l.foot]=[0,0,0];return {axes,points};}
function lowestOffset(p,l,n){const points=corners(p,l.foot,l.side),h=Math.min(...points.map(v=>dot(v,n))),low=points.filter(v=>dot(v,n)<h+1e-8);return mul(low.reduce((a,b)=>add(a,b),[0,0,0]),1/low.length);}
const clearance=(p,hand,toe,n,side)=>-Math.min(...corners(p,hand,side).map(v=>dot(v,n)));
function palmClearance(q,n,side){
 const v=rotate(qinv(q),n),sign=side==='R'?-1:1;
 return .0725*(Math.abs(v[0])-sign*v[0])+.0025*v[1]+.0225*Math.abs(v[1])+.045*Math.abs(v[2]);
}
function clearPalmPitch(l,parent,q,n){
 // The palm box is narrower than the forearm's rounded wrist end. Flattening
 // until the palm touches can otherwise place that 4.8 cm capsule in the floor.
 // Keep the closest allowed wrist pitch that leaves room for the real capsule.
 const radius=.048;if(palmClearance(q,n,l.side)>=radius-1e-9)return q;
 const d=W.decompose(l.wrist.toConstraint(parent,q)),initial=W.decompose(W.clampConstraint(l.wristStart)),z=d.swing[2],y=d.swing[1],a=Math.sin(W.limits.plane/2),b=Math.sin(W.limits.normal/2),end=a*Math.sqrt(Math.max(0,1-(z/b)**2)),start=Math.min(initial.swing[1],end);
 const at=v=>l.wrist.fromConstraint(parent,W.compose([0,v,z,Math.sqrt(Math.max(0,1-v*v-z*z))],d.twist));
 let best=null,distance=Infinity;
 for(let i=0;i<=16;i++){const v=start+(end-start)*i/16;if(palmClearance(at(v),n,l.side)>=radius&&Math.abs(v-y)<distance){best=v;distance=Math.abs(v-y);}}
 if(best===null)return q;
 let invalid=y,valid=best;for(let i=0;i<18;i++){const mid=(invalid+valid)/2;if(palmClearance(at(mid),n,l.side)>=radius)valid=mid;else invalid=mid;}
 return at(valid);
}
function aimedPalm(l,parent,source,n,weight=1,contact=false){
 const input=l.wrist.fromConstraint(parent,source),goal=clearPalmPitch(l,parent,l.wrist.aim(parent,input,n),n);
 const a=W.decompose(W.clampConstraint(source)),b=W.decompose(l.wrist.toConstraint(parent,goal)),y=a.swing[1]+(b.swing[1]-a.swing[1])*clamp(weight,0,1),z=a.swing[2];
 const q=l.wrist.fromConstraint(parent,W.compose([0,y,z,Math.sqrt(Math.max(0,1-y*y-z*z))],a.twist));
 return contact?clearPalmPitch(l,parent,q,n):q;
}
function palmRotation(p,l,n){
 const q=aimedPalm(l,p.q[l.knee],l.wristStart,n);
 return {footQ:q,toeQ:q};
}
function limitWrist(p,l){
 const q=p.q.slice();q[l.foot]=l.wrist.clamp(p.q[l.knee],p.q[l.foot]);return {...p,q,axes:q.map(R.toAxes)};
}
function approachRotation(p,l,point,parents,n,weight){
 const posed=l.posture?.solve?l.posture.solve(p,l,point,parents,1,l):S.solve(p,l,point,parents,1,l),forearm=posed.q[l.knee];
 const q=aimedPalm(l,forearm,l.wristStart,n,weight);return {footQ:q,toeQ:q};
}
function landingTarget(requested,l,surface){const offset=lowestOffset(oriented(l,l.plant||l),l,surface.normal),contact=surface.closest(requested);return {surface:contact,target:sub(contact,offset),ground:contact,limited:length(sub(contact,requested))>1e-6};}
function clearHand(p,l,surface,parents){
 const low=add(p.points[l.foot],lowestOffset(p,l,surface.normal)),gap=dot(sub(low,surface.origin),surface.normal),contact=surface.project(low);
 if(gap>=0||length(sub(surface.closest(contact),contact))>1e-5)return p;
 return S.solve(p,l,sub(p.points[l.foot],mul(surface.normal,gap)),parents,1,{footQ:p.q[l.foot],toeQ:p.q[l.foot]});
}
function posture(p,names,parents,l,target,surface,settings,pairedTargets=null){
 const pelvis=names.indexOf('pelvis'),spines=names.map((n,i)=>n.startsWith('spine_')?i:-1).filter(i=>i>=0),limbRoots=names.map((n,i)=>/^(thigh|upperarm)_[lr]$/.test(n)?i:-1).filter(i=>i>=0),rest=R.localize(p.points,p.q,parents);
 const freeArm=arm(p,names,l.side==='L'?'R':'L'),feet=['L','R'].map(s=>S.leg(p,names,s)),anchored=feet.filter(f=>{const point=add(p.points[f.foot],S.lowestOffset(p,f,surface.normal));return length(sub(point,surface.closest(point)))<.15;});
 const canCrouch=surface.normal[1]>.5&&anchored.length>0;
 const shoulder=mul(add(p.points[names.indexOf('upperarm_l')],p.points[names.indexOf('upperarm_r')]),.5),up=unit(sub(shoulder,p.points[pelvis])),wanted=unit(sub(target,p.points[pelvis]));
 let toward=rotate(p.q[pelvis],[0,-1,0]);toward[1]=0;toward=unit(toward);
 // With feet supporting a crouch, shoulder spacing is handled by the arm.
 // Folding toward that lateral offset made the entire torso fall sideways.
 // In the air, use the actual torso/contact directions, including inversion.
 let axis=canCrouch?cross([0,1,0],toward):cross(up,wanted);if(length(axis)<1e-6)axis=rotate(p.q[pelvis],[0,0,1]);axis=unit(axis);
 const axisLocal=rotate(qinv(p.q[0]),axis),maxBend=canCrouch?145*Math.PI/180:Math.min(110*Math.PI/180,Math.acos(clamp(dot(up,wanted),-1,1)));
 const torso=length(sub(mul(add(p.points[names.indexOf('upperarm_l')],p.points[names.indexOf('upperarm_r')]),.5),p.points[pelvis]));
 const drop=Math.min(Math.min(...feet.map(f=>f.reach))*.35,Math.max(0,p.points[pelvis][1]-Math.min(...feet.map(f=>p.points[f.foot][1]))-.2));
 const spineSet=new Set(spines),stanceLegs=canCrouch?S.candidates(p,names,{...settings,jumpFoot:'Auto',plantPitch:0},surface,0).legs:[];
 let capture=null,crouchGoal=null;
 function apply(base,u,limbs=true,time=0){
  if(u<=0)return base;
  const local=R.localize(base.points,base.q,parents),worldAxis=rotate(base.q[0],axisLocal),angle=maxBend*u,hipShare=canCrouch?.9:.75;
  if(canCrouch)for(const i of [pelvis,...spines]){
   const v=capture?.rates[i],carry=capture?capture.tau*(-Math.expm1(-time/capture.tau))*(1-smooth(time/capture.duration)):0;
   local.p[i]=v?add(rest.p[i],mul(v.linear,carry)):rest.p[i];local.q[i]=v?qm(qexp(mul(v.angular,carry)),rest.q[i]):rest.q[i];
  }
  // Add the fold to the continuing motion. Capturing the torso at the marker
  // erased its velocity on the first tick, especially during an earlier flip.
  local.q[pelvis]=qm(qexp(mul(axisLocal,angle*hipShare)),local.q[pelvis]);
  // Hips move back as the chest folds forward; lowering vertically alone
  // puts the shoulder beyond the palm and makes an ordinary floor unreachable.
  if(canCrouch){const back=rotate(base.q[0],rotate(qinv(p.q[0]),toward));local.p[pelvis]=add(local.p[pelvis],rotate(qinv(base.q[0]),mul(add(mul(back,-torso*.7),[0,-drop,0]),u)));}
  const worldQ=[],bend=qexp(mul(worldAxis,angle*(1-hipShare)/spines.length));
  for(let i=0;i<parents.length;i++){const parent=parents[i];let q=parent<0?local.q[i]:qm(worldQ[parent],local.q[i]);if(spineSet.has(i)){q=qm(bend,q);local.q[i]=qm(qinv(worldQ[parent]),q);}worldQ[i]=q;}
  if(!limbs)return R.fk(local,parents);
  // Folding the torso must not carry a swinging leg over the back or raise the
  // free arm behind the head. Keep each limb's incoming world articulation at
  // its moving socket; contact IK below then owns only the grounded limbs.
  for(const i of limbRoots)local.q[i]=qm(qinv(worldQ[parents[i]]),base.q[i]);
  let posed=R.fk(local,parents);
  // A forward hip hinge leaves room for the thighs below the trunk. The feet
  // trail the hips, rather than forcing a deep squat with knees in the chest.
  if(canCrouch){
   // Blend joint rotations into the crouch. Blending ankle positions made the
   // foot take a shortcut past the hip, briefly folding the knee almost shut.
   const weight=clamp(u/Math.max(amount,1e-8),0,1);
   if(!crouchGoal){let final=apply(p,amount,false,0);
   for(const f of feet){
   const moving=f,stance=stanceLegs.find(s=>s.side===f.side),other=feet.find(s=>s.side!==f.side);
   const outward=unit(sub(final.points[f.hip],final.points[other.hip])),ground=surface.closest(add(final.points[f.hip],add(mul(toward,-f.reach*.67),mul(outward,.1))));
   const footQ=stance.plant.footQ,toeQ=stance.plant.toeQ,oriented={points:[],q:[],axes:[]};
   oriented.points[f.foot]=[0,0,0];oriented.points[f.toe]=rotate(footQ,f.toeLocal);oriented.q[f.foot]=footQ;oriented.q[f.toe]=toeQ;oriented.axes[f.foot]=R.toAxes(footQ);oriented.axes[f.toe]=R.toAxes(toeQ);
   const planted=sub(ground,S.lowestOffset(oriented,f,surface.normal));
   let target=planted;
   const sole=add(target,S.lowestOffset(oriented,f,surface.normal)),gap=dot(sub(sole,surface.origin),surface.normal),contact=surface.project(sole);
   if(gap<0&&length(sub(surface.closest(contact),contact))<1e-5)target=sub(target,mul(surface.normal,gap));
   const axis=unit(sub(target,final.points[f.hip])),open=add(toward,mul(outward,.55)),pole=unit(sub(open,mul(axis,dot(open,axis))));
   const fixed={...moving,pelvis:0,axisLocal:rotate(qinv(p.q[0]),axis),poleLocal:rotate(qinv(p.q[0]),pole)};
   final=S.solve(final,fixed,target,parents,1,{footQ,toeQ});
   }
   crouchGoal=R.localize(final.points,final.q,parents);}
   const goal=crouchGoal,now=R.localize(posed.points,posed.q,parents);
   const carry=capture?capture.tau*(-Math.expm1(-time/capture.tau))*(1-smooth(time/capture.duration)):0;
   for(const f of feet)for(const i of [f.hip,f.knee,f.foot,f.toe]){const v=capture?.rates[i],start=v?qm(qexp(mul(v.angular,carry)),rest.q[i]):rest.q[i];now.q[i]=qslerp(start,goal.q[i],weight);}
   posed=R.fk(now,parents);
   for(const f of feet){
    const low=add(posed.points[f.foot],S.lowestOffset(posed,f,surface.normal)),gap=dot(sub(low,surface.origin),surface.normal),contact=surface.project(low);
    if(gap<0&&length(sub(surface.closest(contact),contact))<1e-5){const leg=S.leg(posed,names,f.side);posed=S.solve(posed,leg,sub(posed.points[f.foot],mul(surface.normal,gap)),parents,1,{footQ:posed.q[f.foot],toeQ:posed.q[f.toe]});}
   }
  }
  return pairedTargets?posed:clearHand(posed,freeArm,surface,parents);
 }
 const limit=l.reach*settings.supportReach*.8;
 const reachError=pose=>pairedTargets?Math.max(...pairedTargets.map(c=>Math.max(0,length(sub(pose.points[c.leg.hip],c.target))-c.leg.reach*settings.supportReach*.8))):Math.max(0,length(sub(pose.points[l.hip],target))-limit);
 let best=0,bestError=Infinity;
 for(let i=0;i<=40;i++){const u=i/40,pose=apply(p,u,false),error=reachError(pose)+u*.002;if(error<bestError){best=i;bestError=error;}}
 let lo=Math.max(0,(best-1)/40),hi=Math.min(1,(best+1)/40);
 for(let i=0;i<18;i++){const a=lo+(hi-lo)/3,b=hi-(hi-lo)/3,score=u=>reachError(apply(p,u,false))+u*.002;if(score(a)<score(b))hi=b;else lo=a;}
 const amount=(lo+hi)/2,goal=apply(p,amount),duration=Math.max(1/60,settings.handBend??.35);
 function solve(pose,limb,point,tree,reach,rotation){
  if(!canCrouch)return limitWrist(S.solve(pose,limb,point,tree,reach,rotation),limb);
  // Move the elbow around the shoulder-to-wrist axis as the torso folds. This
  // retains the exact pin and hinge lengths while keeping the arm off the knee.
  const now=R.localize(pose.points,pose.q,parents),weight=clamp((rest.p[pelvis][1]-now.p[pelvis][1])/Math.max(1e-8,drop*amount),0,1),other=names.indexOf('upperarm_'+(limb.side==='L'?'r':'l'));
  const axis=unit(sub(point,pose.points[limb.hip])),outward=unit(sub(pose.points[limb.hip],pose.points[other]));
  const desired=unit(sub(outward,mul(axis,dot(outward,axis)))),original=rotate(R.fromTo(rotate(pose.q[limb.pelvis],limb.axisLocal),axis),rotate(pose.q[limb.pelvis],limb.poleLocal)),pole=rotate(qslerp([0,0,0,1],R.fromTo(original,desired),weight),original);
  const fixed={...limb,pelvis:0,axisLocal:rotate(qinv(pose.q[0]),axis),poleLocal:rotate(qinv(pose.q[0]),pole)};
  return limitWrist(S.solve(pose,fixed,point,tree,reach,rotation),limb);
 }
 return {amount,duration,canCrouch,freeArm:pairedTargets?null:freeArm,goal,solve,reachable:pairedTargets?pairedTargets.every(c=>length(sub(goal.points[c.leg.hip],c.target))<=c.leg.reach*settings.supportReach+1e-6):length(sub(goal.points[l.hip],target))<=l.reach*settings.supportReach+1e-6,seed(previous,dt){
  const old=R.localize(previous.points,previous.q,parents),speed=length(sub(sub(p.points[l.hip],p.points[0]),sub(previous.points[l.hip],previous.points[0])))/dt,room=Math.max(.001,l.reach-length(sub(p.points[l.foot],p.points[l.hip])));
  capture={duration,tau:Math.min(duration/4,room/(Math.max(.01,speed)*2)),rates:rest.p.map((v,i)=>({linear:mul(sub(v,old.p[i]),1/dt),angular:mul(R.qlog(qm(rest.q[i],qinv(old.q[i]))),1/dt)}))};
 },apply:(base,t)=>apply(base,amount*smooth(t/duration),true,Math.max(0,t)),bones:[pelvis,...spines]};
}
function candidates(p,names,settings,surface,velocity,parents){
 settings={...settings,supportCone:settings.handCone??settings.supportCone??30};
 p=reframe(p);
 const legs=['L','R'].map(side=>{const l=arm(p,names,side);l.plant=palmRotation(p,l,surface.normal);l.clearance=clearance(oriented(l,l.plant),l.foot,-1,surface.normal,side);return l;});
 const center=surface.project(p.points[1]),across=sub(p.points[legs[1].hip],p.points[legs[0].hip]),half=length(across)/2,n=surface.normal,tangent=v=>sub(v,mul(n,dot(v,n))),right=unit(tangent(across));
 const shift=mul(tangent(Array.isArray(velocity)?velocity:[0,0,velocity]),settings.supportAlpha/200);
 const scores=legs.map(l=>{
  const raw=add(center,mul(right,l.side==='L'?-half:half)),requested=add(raw,shift),hit=landingTarget(requested,l,surface),apex=add(p.points[l.foot],lowestOffset(p,l,n)),cone=S.coneTarget(apex,hit.surface,surface,settings.supportCone),contact=cone.contact||surface.closest(apex),target=sub(contact,lowestOffset(oriented(l,l.plant),l,n));
  l.posture=posture(p,names,parents,l,target,surface,settings);
  return {...hit,foot:l.side,raw,requested,shift,appliedShift:shift,cone,constrainedSurface:contact,constrainedTarget:target,idealDistance:length(sub(p.points[l.foot],hit.target)),distance:length(sub(p.points[l.foot],target)),inRange:l.posture.reachable,eligible:cone.valid&&l.posture.reachable};
 });
 const choice=settings.handSide||'Auto',allowed=[0,1].filter(i=>choice==='Auto'||choice==='Both'||legs[i].side===choice),valid=allowed.filter(i=>scores[i].eligible),selected=(valid.length?valid:allowed).reduce((a,b)=>scores[a].distance<=scores[b].distance?a:b);
 return {legs,scores,selected};
}
function plan(p,names,parents,settings,surface,speed,poseAt,velocity,prepared=null,context=null){
 settings={...settings,supportCone:settings.handCone??settings.supportCone??30};
 p=reframe(p);const incoming=poseAt;poseAt=t=>reframe(incoming(t));
 const choice=prepared||candidates(p,names,settings,surface,velocity??speed,parents);
 if(settings.handSide==='Both'){
  const pair=pairedPlan(p,names,parents,settings,surface,speed,poseAt,velocity,choice,context);
  if(pair)return pair;
 }
 const l=choice.legs[choice.selected],cache=new Map();
 const inertia=!l.posture.canCrouch?context?.inertia:null;
 const fit=(pose,t,solve=q=>q)=>inertia&&t>=0?N.fitApproach(pose,t,solve,inertia).pose:solve(pose);
 l.posture.seed(poseAt(-C.motionStep),C.motionStep);
 const body=t=>{const key=Math.round(t*1e9);if(cache.has(key))return cache.get(key);const pose=fit(l.posture.apply(poseAt(t),t),t);cache.set(key,pose);if(cache.size>256)cache.delete(cache.keys().next().value);return pose;};
 // Compare translation using the same wrist-clearance offset on both frames.
 // Each retains its real cone/edge contact, so moving past an edge still fails;
 // merely rotating the hand's lowest corner cannot manufacture a retreat.
 const receding=(now,before)=>{const offset=sub(now.surface,now.target),oldTarget=sub(before.surface,offset);return length(sub(now.foot,now.target))>length(sub(before.foot,oldTarget))+1e-5;};
 const adapter={candidates:()=>choice,receding,rotationAt:(p,limb,point,u)=>approachRotation(p,limb,point,parents,surface.normal,u),landingTarget,lowestOffset,orientedFoot:oriented,clearance,captureRotation:r=>r,solve:(pose,limb,point,tree,reach,rotation,t,u)=>fit(pose,t,q=>{const r=inertia?approachRotation(q,limb,point,tree,surface.normal,u):rotation;return l.posture.solve?l.posture.solve(q,limb,point,tree,reach,r):S.solve(q,limb,point,tree,reach,r);}),movesRoot:!!inertia,rotationByTravel:true};
 const result=S.plan(p,names,parents,settings,surface,speed,body,velocity,adapter);
 return {...result,body,kind:'hand',posture:l.posture,inertia};
}
function pairedPlan(p,names,parents,settings,surface,speed,poseAt,velocity,choice,context=null){
 // Both hands share one body trajectory. Do not average two independently
 // folded torsos, which would move an already planted shoulder discontinuously.
 const legs=choice.legs.map(l=>({...l})),primary=choice.selected,targets=legs.map((leg,i)=>({leg,target:choice.scores[i].constrainedTarget}));
 const target=mul(add(targets[0].target,targets[1].target),.5),shared=posture(p,names,parents,legs[primary],target,surface,settings,targets);
 // The continuing root can bring a currently distant target into reach. Let
 // the ordinary reach-aware approaches decide; the fold's initial reach score
 // alone must not reject a later feasible pair.
 if(choice.scores.some(s=>!s.cone.valid))return null;
 for(const l of legs)l.posture=shared;
 shared.seed(poseAt(-C.motionStep),C.motionStep);
 const inertia=!shared.canCrouch?context?.inertia:null,fit=(q,t,solve=p=>p)=>inertia&&t>=0?N.fitApproach(q,t,solve,inertia).pose:solve(q);
 const cache=new Map(),body=t=>{const key=Math.round(t*1e9);if(cache.has(key))return cache.get(key);const q=fit(shared.apply(poseAt(t),t),t);cache.set(key,q);if(cache.size>256)cache.delete(cache.keys().next().value);return q;};
 const receding=(now,before)=>{const offset=sub(now.surface,now.target),oldTarget=sub(before.surface,offset);return length(sub(now.foot,now.target))>length(sub(before.foot,oldTarget))+1e-5;};
 const hands=legs.map((leg,i)=>{
  const selected={...choice,legs,selected:i},adapter={candidates:()=>selected,receding,rotationAt:(p,l,point,u)=>approachRotation(p,l,point,parents,surface.normal,u),landingTarget,lowestOffset,orientedFoot:oriented,clearance,captureRotation:r=>r,solve:shared.solve,rotationByTravel:true};
  const plan=S.plan(p,names,parents,settings,surface,speed,body,velocity,adapter);
  return {leg,plan,contactDelay:plan.jumpDelay};
 });
 if(hands.some(h=>!Number.isFinite(h.contactDelay)))return null;
 const jumpDelay=Math.max(...hands.map(h=>h.contactDelay));
 for(const h of hands){
  h.wait=jumpDelay-h.contactDelay;
  h.contactMotion=contactMotion(h.plan.terminal,h.leg,surface,settings,null,null,{parents,solve:shared.solve,bodyAt:t=>body(h.contactDelay+t)});
 }
 const solveContacts=(pose,contacts)=>{for(const c of Array.isArray(contacts)?contacts:contacts.hands){const r=inertia&&c.pinned===false?approachRotation(pose,c.leg,c.foot,parents,surface.normal,c.rotationProgress):c.rotation;pose=shared.solve(pose,c.leg,c.foot,parents,c.pinned===false?1:settings.supportReach,r);}return pose;};
 const firstContact=Math.min(...hands.map(h=>h.contactDelay));let contactShift=null;
 function freeFit(t){const q=body(t),targets=hands.map(h=>({...h.plan.sample(Math.min(t,h.contactDelay)),leg:h.leg,pinned:false}));return fit(q,t,p=>solveContacts(p,targets));}
 if(inertia)contactShift=sub(freeFit(firstContact).points[0],body(firstContact).points[0]);
 function sample(time,rootOverride=null,pending=null){
  const t=clamp(time,0,jumpDelay),base=body(t),delta=rootOverride?sub(rootOverride,base.points[0]):inertia&&t>=firstContact?contactShift:[0,0,0],pose={...base,points:base.points.map(v=>add(v,delta))};
  const samples=hands.map(h=>{
   if(t>=h.contactDelay&&!pending?.includes(h)){const c=h.contactMotion.sample(t-h.contactDelay,pose.points[0]);return {...c,leg:h.leg,pinned:true,target:c.foot,surface:c.contact};}
   const f=h.plan.sample(t),carry=rootOverride?sub(rootOverride,add(base.points[0],inertia&&t>=firstContact?contactShift:[0,0,0])):inertia?[0,0,0]:delta;return {...f,foot:add(f.foot,carry),rotation:{footQ:f.pose.q[h.leg.foot],toeQ:f.pose.q[h.leg.foot]},leg:h.leg,pinned:false};
  });
  const result=inertia&&!rootOverride&&t<firstContact?fit(pose,t,p=>solveContacts(p,samples)):solveContacts(pose,samples),main=samples[primary];
  return {...hands[primary].plan.sample(Math.min(t,hands[primary].contactDelay)),...main,pose:result,foot:result.points[legs[primary].foot],rotation:{footQ:result.q[legs[primary].foot],toeQ:result.q[legs[primary].foot]},hands:samples};
 }
 if(inertia)for(const at of [...new Set(hands.map(h=>h.contactDelay))].sort((a,b)=>a-b)){
  const arriving=hands.filter(h=>h.contactDelay===at);let posed;
  // Update the already prepared terminal wrist positions, so interpolation
  // into capture and the contact's material pivot use the same composite rig.
  for(let pass=0;pass<48;pass++){
   posed=at===firstContact?freeFit(at):sample(at,null,arriving).pose;let error=0;
   for(const h of arriving){const low=add(posed.points[h.leg.foot],lowestOffset(posed,h.leg,surface.normal)),gap=dot(sub(low,surface.origin),surface.normal);error=Math.max(error,Math.abs(gap));if(Math.abs(gap)>1e-8){const frame=h.plan.frames.at(-1);frame.foot=sub(frame.foot,mul(surface.normal,gap*.7));}}
   if(error<1e-8)break;
  }
  posed=at===firstContact?freeFit(at):sample(at,null,arriving).pose;
  if(at===firstContact)contactShift=sub(posed.points[0],body(at).points[0]);
  for(const h of arriving){const terminal={...h.plan.sample(at),pose:posed,foot:posed.points[h.leg.foot],rotation:{footQ:posed.q[h.leg.foot],toeQ:posed.q[h.leg.foot]}};h.contactMotion=contactMotion(terminal,h.leg,surface,settings,null,null,{parents,solve:shared.solve,bodyAt:t=>body(h.contactDelay+t)});}
 }
 // The first hand waits only for the second hand's real arrival. A pair is
 // usable only while that early contact stays on the finite surface and within
 // arm reach throughout the intervening root/body motion.
 for(const h of hands)for(let t=h.contactDelay;t<=jumpDelay+1e-9;t=Math.min(jumpDelay,t+1/240)){
  const q=inertia?sample(t).pose:body(t),c=h.contactMotion.sample(t-h.contactDelay,q.points[0]),distance=length(sub(q.points[h.leg.hip],c.foot));
  if(!c.valid||distance>h.plan.maxReach+1e-8||distance<Math.abs(h.leg.upper-h.leg.lower)+1e-6)return null;
  if(t===jumpDelay)break;
 }
 const original=hands[primary].plan,frames=original.frames.slice();
 for(let t=(frames.at(-1).t+1/240);t<jumpDelay-1e-9;t+=1/240){const f=sample(t);frames.push({...frames.at(-1),...f,t});}
 const terminal=sample(jumpDelay);if(frames.at(-1).t<jumpDelay)frames.push({...frames.at(-1),...terminal,t:jumpDelay});
 return {...original,paired:true,limbs:legs,hands,sample,terminal,frames,jumpDelay,body,kind:'hand',posture:shared,solveContacts,inertia};
}
function contactMotion(terminal,l,surface,settings,previous=null,shoulderAt=null,context=null){
 if(context?.support?.paired){
  const support=context.support,primary=support.limbs.indexOf(l);let rootAt=null;
  return {alignDuration:Math.max(...support.hands.map(h=>h.contactMotion.alignDuration)),sample(t,rootOverride=null){
   const body=context?.bodyAt?.(t),root=rootOverride||rootAt?.(t)||body?.points[0]||support.body(support.jumpDelay+t).points[0];
   const hands=support.hands.map(h=>({...h.contactMotion.sample(t+h.wait,root,body),leg:h.leg})),main=hands[Math.max(0,primary)];
   return {...main,hands,valid:hands.every(h=>h.valid),residual:Math.max(...hands.map(h=>h.residual||0))};
  },startPush(t){for(const h of support.hands)h.contactMotion.startPush(t+h.wait);},setRootAt(fn){rootAt=fn;},invalidate(){for(const h of support.hands)h.contactMotion.invalidate();}};
 }
 const n=surface.normal,start=terminal.rotation,startPose=terminal.pose,startCS=l.wrist.toConstraint(startPose.q[l.knee],start.footQ);
 const initialOffset=lowestOffset(oriented(l,start),l,n),anchorLocal=rotate(qinv(start.footQ),initialOffset),anchor=add(terminal.foot,initialOffset);
 const goal=palmRotation(startPose,l,n),angle=length(R.qlog(qm(goal.footQ,qinv(start.footQ)))),alignDuration=Math.max(.025,angle/(1080*Math.PI/180));
 let rootAt=null;const cache=new Map();
 function fit(q){
  const r={footQ:q,toeQ:q},offset=rotate(q,anchorLocal);let foot=sub(anchor,offset);
  const gap=Math.min(...corners(oriented(l,r),l.foot,l.side).map(v=>dot(sub(add(foot,v),surface.origin),n)));
  // Rock about the captured material point. If another corner becomes lower,
  // raise the old pivot; min-height stays continuous through feature changes.
  foot=sub(foot,mul(n,gap));const contact=add(foot,lowestOffset(oriented(l,r),l,n));
  return {foot,rotation:r,contact,valid:length(sub(surface.closest(contact),contact))<2e-5};
 }
 function sample(time,rootOverride=null,bodyOverride=null){
  const t=Math.max(0,time),body=bodyOverride||(context?.bodyAt?context.bodyAt(t):startPose),root=rootOverride||rootAt?.(t)||body.points[0];
  const key=[bodyOverride?1:0,t,...root,...(bodyOverride?body.q[l.knee]:[]),...(bodyOverride?body.points[l.hip]:[])].map(v=>Math.round(v*1e9)).join(':');if(cache.has(key))return cache.get(key);
  const delta=sub(root,body.points[0]),p={...body,points:body.points.map(v=>add(v,delta))},u=smooth(t/alignDuration);
  const solve=context?.solve||((p,l,foot,parents,reach,r)=>S.solve(p,l,foot,parents,reach,r)),parents=context?.parents;
  let frame={foot:terminal.foot,rotation:start},residual=Infinity;
  for(let i=0;i<40;i++){
   const posed=solve(p,l,frame.foot,parents,1,frame.rotation),forearm=posed.q[l.knee],incoming=l.wrist.fromConstraint(forearm,startCS);
   const q=aimedPalm(l,forearm,startCS,n,u,true),next=fit(q);residual=length(sub(next.foot,frame.foot));if(residual<1e-8||i===39){frame=next;break;}frame={...next,foot:add(frame.foot,mul(sub(next.foot,frame.foot),.5))};
  }
  frame.residual=residual;cache.set(key,frame);if(cache.size>512)cache.delete(cache.keys().next().value);return frame;
 }
 return {sample,alignDuration,startPush(){},setRootAt(fn){rootAt=fn;cache.clear();},invalidate(){cache.clear();}};
}

const api={registerRig,limitWrist,reframe,arm,corners,lowestOffset,palmRotation,posture,candidates,plan,contactMotion,clearHand,solve:S.solve};if(node)module.exports=api;else root.BodyflipHandSupport=api;
})(globalThis);
