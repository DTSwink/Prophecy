/* Surface locomotion experiment: NN articulation, material foot contacts, and a
 * gravity-driven root. It is intentionally separate from the accepted stair IK. */
(function(root){
'use strict';
const R=typeof module!=='undefined'?require('./recovery.js'):root.Recovery;
const S=typeof module!=='undefined'?require('./support.js'):root.BodyflipSupport;
const K=typeof module!=='undefined'?require('./footik.js'):root.FootIK;
const {add,sub,mul,dot,cross,length,unit,rotate,qm,qinv,qslerp}=R;
const up=[0,1,0],identity=[0,0,0,1],clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const smooth=x=>{x=clamp(x,0,1);return x*x*(3-2*x);};
const bounded=(v,max)=>length(v)>max?mul(unit(v),max):v;
function settings(input={}){const finite=(v,d)=>Number.isFinite(Number(v))?Number(v):d;return {...K.sanitize(input),terrain:'incline',slopeAngle:clamp(finite(input.slopeAngle??45,45),0,90),approach:input.approach==='parallel'?'parallel':'toward',upright:clamp(finite(input.upright??.55,.55),0,1)};}
function gravityActive(normal,s){
 return s.inclineGravity&&Math.acos(clamp(normal[1],-1,1))*180/Math.PI>=s.minGravityIncline-1e-8;
}
// The threshold enables full gravity; the percentage only removes vertical
// root thrust. Neither gravity nor thrust suppression ramps toward 90 degrees.
function gravityShare(normal,s){return gravityActive(normal,s)?s.fullGravity/100:0;}
// A real surface change, never the smoothed visual normal. Interpolating
// retained kinetic energy gives exact projection/preserved-speed endpoints.
function transferVelocity(velocity,fromNormal,toNormal,percent){
 const projection=sub(velocity,mul(toNormal,dot(velocity,toNormal))),p2=dot(projection,projection),v2=dot(velocity,velocity),energy=clamp(percent/100,0,1);
 if(energy===0)return projection;
 const turned=rotate(R.fromTo(fromNormal,toNormal),velocity),transported=sub(turned,mul(toNormal,dot(turned,toNormal)));
 let direction=add(mul(projection,1-energy),mul(transported,energy));
 if(length(direction)<1e-8)direction=transported;
 return length(direction)>1e-8?mul(unit(direction),Math.sqrt(p2+energy*Math.max(0,v2-p2))):projection;
}
function gravityDrive(drive,normal,share){
 return share===0?drive:[drive[0],drive[1]*(1-share),drive[2]];
}
function createTerrain(input,extent=28){
 const s=settings(input),a=s.slopeAngle*Math.PI/180,start=1.8,c=Math.cos(a),h=Math.sin(a),parallel=s.approach==='parallel';
 const slope=parallel?S.rectangle('incline',[0,0,0],[c,h,0],[0,0,1],[-extent,extent,-5,35],.2):S.rectangle('incline',[0,0,start],[1,0,0],[0,h,c],[-4,4,-extent,extent],.2);
 const floor=S.rectangle('entry',[0,0,0],[1,0,0],[0,0,1],[-12,12,-5,parallel?35:start],.2);
 const complete=parallel?[slope]:[floor,slope],withoutFloor=[slope];
 const surfacesAt=time=>s.deleteFloorFrame>=0&&time*60>=s.deleteFloorFrame-1e-8?withoutFloor:complete;
 let surfaces=surfacesAt(0);
 const pick=(p,normal=up)=>{
  let best=null;
  for(const surface of surfaces){const point=surface.closest(p),distance=length(sub(p,point));if(!best||distance<best.distance)best={surface,point,distance};}
  return best;
 };
 return {kind:'incline',start,end:30,slope,floor,get surfaces(){return surfaces;},surfacesAt,setTime:time=>{surfaces=surfacesAt(time);},tiles:[],pick,
  rootHeight:z=>parallel?0:Math.max(0,z-start)*Math.tan(Math.min(a,Math.PI/2-.001)),
  floorFor:(p,offsets)=>{const hit=pick(p);return p[1]-Math.min(...offsets.map(o=>dot(sub(add(p,o),hit.point),hit.surface.normal)));}};
}
function footRotation(p,l,normal,heading,pitch=0){
 let forward=sub(heading,mul(normal,dot(heading,normal)));if(length(forward)<1e-5)forward=cross([1,0,0],normal);forward=unit(forward);
 const right=unit(cross(normal,forward)),r=R.qexp(mul(right,-pitch)),f=rotate(r,forward),u=rotate(r,normal);
 const target=R.fromAxes([unit(cross(u,f)),u,f]),frame=S.footFrame(p,l.foot,l.toe,l.side);
 const align=(q,f,u)=>qm(qm(target,qinv(R.fromAxes([unit(cross(u,f)),u,f]))),q);
 return {footQ:align(p.q[l.foot],frame.forward,frame.up),toeQ:align(p.q[l.toe],frame.toeForward,frame.toeUp)};
}
function shoePose(p,l,target,rotation){const points=p.points.slice(),q=p.q.slice(),axes=p.axes.slice();points[l.foot]=target;points[l.toe]=add(target,rotate(rotation.footQ,l.toeLocal));q[l.foot]=rotation.footQ;q[l.toe]=rotation.toeQ;axes[l.foot]=R.toAxes(rotation.footQ);axes[l.toe]=R.toAxes(rotation.toeQ);return {points,q,axes};}
function sole(p,l,n){return S.lowestOffset(p,l,n);}
function fit(p,l,target,rotation,surface){const shaped=shoePose(p,l,target,rotation),offset=sole(shaped,l,surface.normal),point=surface.closest(add(target,offset));return {target:sub(point,offset),point,offset};}
function capture(p,l,target,rotation,surface,id){
 const fitted=fit(p,l,target,rotation,surface),pose=shoePose(p,l,fitted.target,rotation),frame=S.footFrame(pose,l.foot,l.toe,l.side),axis=unit(cross(surface.normal,frame.forward));
 const terminal={pose,foot:fitted.target,rotation},positive=S.roll(terminal,{...l,plant:{right:axis}},surface,85),negative=S.roll(terminal,{...l,plant:{right:mul(axis,-1)}},surface,45);
 return {surface,id,pose,rotation,angle:0,sample:angle=>angle>=0?positive(angle/85):negative(-angle/45)};
}
function constrain(p,l,target,rotation,surfaces,reachRatio=.985){
 const hip=p.points[l.hip],reach=l.reach*reachRatio,minimum=Math.min(l.reach*.27,length(sub(p.points[l.foot],hip)));let result=target.slice();
 for(let pass=0;pass<12;pass++){
  const before=result;
  const v=sub(result,hip),distance=length(v);if(distance>reach)result=add(hip,mul(unit(v),reach));
  else if(distance<minimum){const axis=distance>1e-8?unit(v):unit(sub(p.points[l.foot],hip));result=add(hip,mul(axis,minimum));}
  const shaped=shoePose(p,l,result,rotation),corners=S.footPoints(shaped,l.foot,l.toe,l.side);
  for(const surface of surfaces){const [x0,x1,z0,z1]=surface.bounds;let penetration=0;
   for(const o of corners){const local=surface.local(add(result,o));if(local[0]>=x0&&local[0]<=x1&&local[2]>=z0&&local[2]<=z1)penetration=Math.max(penetration,-local[1]);}
   if(penetration>0)result=add(result,mul(surface.normal,penetration+1e-5));
  }
  if(length(sub(result,before))<1e-8)break;
 }
 return result;
}
function penetration(p,l,surfaces){let result=0;const points=S.footPoints(p,l.foot,l.toe,l.side);for(const surface of surfaces){const [x0,x1,z0,z1]=surface.bounds;for(const v of points){const local=surface.local(add(p.points[l.foot],v));if(local[0]>=x0&&local[0]<=x1&&local[2]>=z0&&local[2]<=z1)result=Math.max(result,-local[1]);}}return result;}
function solvePole(p,l,target,parents,rotation,previous,state,dt){
 if(!previous)return K.solve(p,l,target,parents,rotation);
 const delta=sub(target,p.points[l.hip]),axis=unit(delta),sourceAxis=rotate(p.q[l.pelvis],l.axisLocal),sourcePole=rotate(p.q[l.pelvis],l.poleLocal);
 const illConditioned=dot(axis,sourceAxis)<-.7||length(delta)<l.reach*.4;
 if(!illConditioned&&!state.poleRecovering)return K.solve(p,l,target,parents,rotation);
 const oldAxis=unit(sub(previous.points[l.foot],previous.points[l.hip])),oldUpper=sub(previous.points[l.knee],previous.points[l.hip]);
 let oldPole=sub(oldUpper,mul(oldAxis,dot(oldUpper,oldAxis)));if(length(oldPole)<1e-6)return K.solve(p,l,target,parents,rotation);
 oldPole=rotate(R.fromTo(oldAxis,axis),unit(oldPole));
 const desired=rotate(R.fromTo(sourceAxis,axis),sourcePole),angle=Math.atan2(dot(axis,cross(oldPole,desired)),dot(oldPole,desired)),limit=720*Math.PI/180*dt;
 state.poleRecovering=Math.abs(angle)>limit;
 // Parallel transport preserves the old bend plane at the antipodal/folded
 // singularity. Only the pole recovers at a bounded rate; the ankle target,
 // material pin, bone lengths and surface constraints are untouched.
 const pole=rotate(R.qexp(mul(axis,clamp(angle,-limit,limit))),oldPole),inverse=qinv(p.q[l.pelvis]);
 return K.solve(p,{...l,axisLocal:rotate(inverse,axis),poleLocal:rotate(inverse,pole)},target,parents,rotation);
}
// Public geometry/stance helpers keep host adapters off copied solver rules.
function gaitIntent(p,l,velocity,speed,active){
 const clearance=p.points[l.foot][1]+Math.min(...S.footPoints(p,l.foot,l.toe,l.side).map(v=>v[1]))-p.points[0][1],fast=Math.hypot(velocity[0],velocity[2]);
 return {clearance,stance:active?clearance<.055&&fast<speed*.95:clearance<.035&&fast<speed*.68};
}
function bodyRotation(normal,upright){return R.fromTo(up,unit(add(mul(normal,1-upright),mul(up,upright))));}
function intent(run,raw,legs,fps,speed){
 return [0,1].map(side=>{let active=false;return raw.map((p,i)=>{const l=legs[i][side],a=raw[Math.max(0,i-1)].points[l.foot],b=raw[Math.min(raw.length-1,i+1)].points[l.foot],v=mul(sub(b,a),fps/(i===0||i===raw.length-1?1:2));
  active=gaitIntent(p,l,v,speed,active).stance;return active;});});
}
function createMetrics(){return {maxPenetration:0,maxReachError:0,maxRequestedReachExcess:0,maxContactDrift:0,maxRootAcceleration:0,maxFootSpeed:0,maxRelativeFootSpeed:0,maxKneeStep:0,maxAnkleStep:0,maxRelativeAnkleDegrees:0,ankleReleases:0,wallContactFrames:0,contactFrames:0,flightFrames:0,maxBodyTilt:0,maxGravityResidual:0,reachRollPositive:0,reachRollNegative:0,maxPinAngleStep:0};}
// Shared contact/leg solver. Call step in chronological order at120Hz.
// Root motion and the terrain query belong to the host; all foot rules live here.
function createFeet({names,parents,terrain,settings:s,metrics=createMetrics()}){
 const footState=[0,1].map(()=>({pin:null,released:null,lastTarget:null,lastRotation:null,lastVelocity:[0,0,0]})),events=[];
 let serial=0,previous=null;
 function step({baseline,terrainPose,source:p,sourceLegs,stance,untilPlant,time,frame=time*60,normal,surfaceQ,height,velocity,terrainWeight=1,enabled=s.enabled,wallExpired=false,steep=false}){
  const fps=120,dt=1/fps,feet=[],supports=[];let pose=baseline;
  for(let side=0;side<2;side++){
   const state=footState[side],l=K.stableLeg(pose,names,side===0?'L':'R'),sourceLeg=sourceLegs[side],sourceFrame=S.footFrame(p,sourceLeg.foot,sourceLeg.toe,sourceLeg.side);
   let target=add(baseline.points[l.foot],mul(sub(terrainPose.points[l.foot],baseline.points[l.foot]),terrainWeight)),rotation={footQ:qslerp(baseline.q[l.foot],terrainPose.q[l.foot],terrainWeight),toeQ:qslerp(baseline.q[l.toe],terrainPose.q[l.toe],terrainWeight)};
   // A wall step is a crouched contact near the pelvis, not a straight leg
   // ending under it with the toes folded up along the shin. Raise the intended
   // wall foothold along its plane as upright bias grows, leaving ankle limits
   // and the actual reachable/contact tests to accept or reject it.
   const alongUp=sub(up,mul(normal,dot(up,normal))),wallLift=height*.55*smooth((Math.acos(clamp(normal[1],-1,1))*180/Math.PI-50)/40)*terrainWeight;
   if(length(alongUp)>1e-5)target=add(target,mul(unit(alongUp),wallLift));
   const desired=terrain.pick(target),surface=desired.surface,tooSteep=surface.id==='incline'&&steep,canAttach=enabled&&!(tooSteep&&wallExpired);
   const sourcePitch=Math.asin(clamp(sourceFrame.forward[1],-1,1)),heading=rotate(surfaceQ,unit([sourceFrame.forward[0],0,sourceFrame.forward[2]]));
   const contactRotation=footRotation(pose,l,surface.normal,heading,0),captureFrom=state.lastTarget||target;let fitted=fit(pose,l,captureFrom,contactRotation,surface);
   fitted=fit(pose,l,constrain(pose,l,fitted.target,contactRotation,[surface],.96),contactRotation,surface);
   const surfaceRemoved=state.pin&&!terrain.surfaces.some(s=>s.id===state.pin.surface.id);
   if(state.pin&&(!stance[side]||!canAttach||surfaceRemoved)){
    state.released={time,point:state.lastTarget,rotation:state.lastRotation,velocity:state.lastVelocity};events.push({frame:frame,type:'release',side:l.side,surface:state.pin.surface.id,reason:surfaceRemoved?'surface-removed':!canAttach?'support-budget':'gait'});state.pin=null;
   }
   const d=dot(sub(target,fitted.target),surface.normal),reach=length(sub(fitted.target,pose.points[l.hip])),captureDistance=length(sub(captureFrom,fitted.target));
   const angularGap=state.lastRotation?length(R.qlog(qm(contactRotation.footQ,qinv(state.lastRotation.footQ)))):0;
   if(!state.pin&&stance[side]&&canAttach&&captureDistance<.035&&reach<l.reach*.98&&angularGap<7*Math.PI/180&&(!state.released||time-state.released.time>.12)){
    state.pin=capture(pose,l,fitted.target,contactRotation,surface,++serial);state.pin.yaw=K.createPinYaw(surface.normal,s.footYawLimit??45);state.released=null;events.push({frame:frame,type:'plant',side:l.side,surface:surface.id});
   }
   let contact=null;
   if(state.pin){
    const pin=state.pin,wanted=clamp(-sourcePitch*180/Math.PI,-20,65),previousAngle=pin.angle,maxAngleStep=300*dt;pin.angle+=clamp(wanted-pin.angle,-maxAngleStep,maxAngleStep);
    let roll=pin.sample(pin.angle),best=length(sub(roll.foot,pose.points[l.hip]));
    // The useful pivot direction depends on travel. A backward stride can
    // preserve its heel contact by rolling the opposite way. Natural rotation
    // AND this reach correction share one300deg/s budget.
    if(best>l.reach*.94){
     const natural=pin.angle,lo=Math.max(-44,previousAngle-maxAngleStep),hi=Math.min(70,previousAngle+maxAngleStep),goal=l.reach*.94,angles=[lo,hi,natural];
     for(let a=Math.ceil(lo*2)/2;a<hi;a+=.5)angles.push(a);
     const candidates=angles.map(angle=>{const r=pin.sample(angle);return {angle,r,distance:length(sub(r.foot,pose.points[l.hip]))};}).filter(c=>c.r.valid&&c.distance<best-1e-8);
     candidates.sort((a,b)=>a.distance<=goal&&b.distance<=goal?Math.abs(a.angle-natural)-Math.abs(b.angle-natural):a.distance<=goal?-1:b.distance<=goal?1:a.distance-b.distance);
     for(const candidate of candidates){
      const test=K.solve(pose,l,candidate.r.foot,parents,candidate.r.rotation),relative=qm(qinv(test.q[l.knee]),test.q[l.foot]),sourceRelative=qm(qinv(sourceLeg.kneeQ),sourceLeg.footQ);
      if(length(R.qlog(qm(relative,qinv(sourceRelative))))>65*Math.PI/180||penetration(test,l,terrain.surfaces)>1e-4)continue;
      if(candidate.angle>natural+1e-8)metrics.reachRollPositive++;else if(candidate.angle<natural-1e-8)metrics.reachRollNegative++;
      roll=candidate.r;best=candidate.distance;pin.angle=candidate.angle;break;
     }
    }
    metrics.maxPinAngleStep=Math.max(metrics.maxPinAngleStep,Math.abs(pin.angle-previousAngle));
    roll=pin.yaw(roll,pose,l,r=>penetration(shoePose(pose,l,r.foot,r.rotation),l,terrain.surfaces)<1e-5);
    best=length(sub(roll.foot,pose.points[l.hip]));
    const yawBlocked=roll.blocked&&Math.abs(roll.yawError)>(s.footYawLimit??45);
    if(!roll.valid||best>l.reach*.995||yawBlocked){state.released={time,point:state.lastTarget||roll.foot,rotation:state.lastRotation||roll.rotation,velocity:state.lastVelocity};events.push({frame:frame,type:'release',side:l.side,surface:pin.surface.id,reason:yawBlocked?'yaw-clearance':'reach'});state.pin=null;}
    else {target=roll.foot;rotation=roll.rotation;contact={surface:pin.surface.id,point:roll.contact,local:pin.surface.local(roll.contact),normal:pin.surface.normal,localPoint:rotate(qinv(rotation.footQ),sub(roll.contact,target)),stanceId:pin.id,angle:pin.angle,valid:true};if(roll.yaw)Object.assign(contact,{yaw:roll.yaw,yawError:roll.yawError,pivotKind:roll.pivotKind});supports.push({normal:pin.surface.normal,surface:pin.surface,point:roll.contact});}
   }
   if(!state.pin){
    // A free ankle follows calf-relative NN articulation; only imminent contact
    // turns its sole to the surface. No late world-rotation snap on release.
    const b=1-smooth(Math.max(0,d)/.20),natural={footQ:baseline.q[l.foot],toeQ:baseline.q[l.toe]};
    rotation={footQ:qslerp(natural.footQ,rotation.footQ,b),toeQ:qslerp(natural.toeQ,rotation.toeQ,b)};
    if(canAttach){const landing=1-smooth(untilPlant[side]/.14);rotation={footQ:qslerp(rotation.footQ,contactRotation.footQ,landing),toeQ:qslerp(rotation.toeQ,contactRotation.toeQ,landing)};}
    if(state.released&&state.released.point){const elapsed=time-state.released.time,u=clamp(elapsed/.18,0,1),w=1-smooth(u);
     if(state.released.offset===undefined){state.released.offset=sub(state.released.point,target);state.released.deltaFoot=qm(state.released.rotation.footQ,qinv(rotation.footQ));state.released.deltaToe=qm(state.released.rotation.toeQ,qinv(rotation.toeQ));}
     target=add(target,mul(state.released.offset,w));rotation={footQ:qm(qslerp(identity,state.released.deltaFoot,w),rotation.footQ),toeQ:qm(qslerp(identity,state.released.deltaToe,w),rotation.toeQ)};
     if(u===1)state.released=null;
    }
    // Collision is solved against shoe volume on the actual plane; never lift
    // along world Y on an inclined surface.
    const shaped=shoePose(pose,l,target,rotation),points=S.footPoints(shaped,l.foot,l.toe,l.side);
    const depth=Math.min(...points.map(o=>dot(sub(add(target,o),surface.closest(add(target,o))),surface.normal)));
    if(depth<0&&!wallExpired)target=add(target,mul(surface.normal,-depth+.001));
   }
   if(!enabled){target=baseline.points[l.foot];rotation={footQ:baseline.q[l.foot],toeQ:baseline.q[l.toe]};contact=null;}
   if(!contact&&state.lastRotation){for(const key of ['footQ','toeQ']){const angle=length(R.qlog(qm(rotation[key],qinv(state.lastRotation[key])))),limit=600*Math.PI/180*dt;if(angle>limit)rotation[key]=qslerp(state.lastRotation[key],rotation[key],limit/angle);}}
   metrics.maxRequestedReachExcess=Math.max(metrics.maxRequestedReachExcess,length(sub(target,pose.points[l.hip]))-l.reach*.985);
   if(!contact){
    if(state.lastTarget){
     const relative=state.lastRelativeVelocity||[0,0,0],want=bounded(mul(sub(target,add(state.lastTarget,mul(velocity,dt))),30),s.gait==='run'?8:5);
     const nextVelocity=add(relative,bounded(sub(want,relative),(s.gait==='run'?110:80)*dt));
     target=add(state.lastTarget,mul(add(velocity,nextVelocity),dt));state.lastRelativeVelocity=nextVelocity;
    }
    target=constrain(pose,l,target,rotation,terrain.surfaces);
   }else state.lastRelativeVelocity=sub(state.lastVelocity,velocity);
   const solveTarget=(point,rot)=>solvePole(pose,l,point,parents,rot,previous,state,dt);
   let solved=solveTarget(target,rotation);
   const naturalFoot=qm(solved.q[l.knee],qm(qinv(sourceLeg.kneeQ),sourceLeg.footQ)),naturalToe=qm(naturalFoot,qm(qinv(sourceLeg.footQ),sourceLeg.toeQ));
   const ankleDifference=length(R.qlog(qm(rotation.footQ,qinv(naturalFoot)))),ankleLimit=65*Math.PI/180;
   if(ankleDifference>ankleLimit){
    if(contact){supports.pop();state.pin=null;contact=null;metrics.ankleReleases++;events.push({frame:frame,type:'release',side:l.side,surface:surface.id,reason:'ankle-limit'});}
    const blend=ankleLimit/ankleDifference;rotation={footQ:qslerp(naturalFoot,rotation.footQ,blend),toeQ:qslerp(naturalToe,rotation.toeQ,blend)};
    target=constrain(pose,l,target,rotation,terrain.surfaces);solved=solveTarget(target,rotation);
   }
   if(contact&&penetration(solved,l,terrain.surfaces)>1e-4){supports.pop();state.pin=null;contact=null;events.push({frame:frame,type:'release',side:l.side,surface:surface.id,reason:'shoe-collision'});target=constrain(pose,l,target,rotation,terrain.surfaces);solved=solveTarget(target,rotation);}
   pose=solved;
   const actual=pose.points[l.foot],error=length(sub(actual,target));
   const depth=penetration(pose,l,terrain.surfaces);
   if(contact&&error>.005){supports.pop();contact=null;state.pin=null;}
   const v=state.lastTarget?mul(sub(actual,state.lastTarget),fps):[0,0,0];metrics.maxFootSpeed=Math.max(metrics.maxFootSpeed,length(v));metrics.maxRelativeFootSpeed=Math.max(metrics.maxRelativeFootSpeed,length(sub(v,velocity)));state.lastVelocity=v;state.lastTarget=actual;state.lastRotation=rotation;
   if(contact)metrics.maxContactDrift=Math.max(metrics.maxContactDrift,length(sub(add(actual,rotate(pose.q[l.foot],contact.localPoint)),contact.point)));
   metrics.maxRelativeAnkleDegrees=Math.max(metrics.maxRelativeAnkleDegrees,length(R.qlog(qm(qm(qinv(pose.q[l.knee]),pose.q[l.foot]),qinv(qm(qinv(sourceLeg.kneeQ),sourceLeg.footQ)))))*180/Math.PI);
   if(previous){const kneeStep=length(R.qlog(qm(pose.q[l.knee],qinv(previous.q[l.knee]))))*180/Math.PI,ankleStep=length(R.qlog(qm(pose.q[l.foot],qinv(previous.q[l.foot]))))*180/Math.PI;
    if(kneeStep>metrics.maxKneeStep){metrics.maxKneeStep=kneeStep;metrics.maxKneeFrame=frame;metrics.maxKneeSide=l.side;}
    if(ankleStep>metrics.maxAnkleStep){metrics.maxAnkleStep=ankleStep;metrics.maxAnkleFrame=frame;metrics.maxAnkleSide=l.side;}
   }
   metrics.maxReachError=Math.max(metrics.maxReachError,error);metrics.maxPenetration=Math.max(metrics.maxPenetration,depth);
   if(contact){metrics.contactFrames++;if(contact.surface==='incline')metrics.wallContactFrames++;}
   feet.push({side:l.side,state:contact?(Math.abs(contact.angle)>1?'ROLL':'PIN'):'SWING',target:actual,contact,error,penetration:depth,soleGap:dot(sub(actual,surface.closest(actual)),surface.normal)});
  }
  previous=pose;return {pose,feet,supports};
 }
 return {step,metrics,events};
}
function prepare(run,input={},experiment={}){
 const s=settings(input),fps=120,dt=1/fps,count=Math.round(run.duration*fps)+1,{names,parents}=run,pelvis=names.indexOf('pelvis');
 const origin=run.poses[0].points[0],raw=Array.from({length:count},(_,i)=>{const p=K.at(run,i/fps);return {...p,points:p.points.map(v=>sub(v,[origin[0],0,origin[2]]))};});
 const speed=length(sub(raw.at(-1).points[0],raw[0].points[0]))/run.duration,legs=raw.map(p=>['L','R'].map(side=>K.stableLeg(p,names,side))),flags=intent(run,raw,legs,fps,speed);
 const height=raw.reduce((sum,p)=>sum+p.points[pelvis][1]-p.points[0][1],0)/count;
 const gravity=experiment.gravity??9.81,enabled=experiment.support!==false&&s.enabled;
 // Cover the whole recorded flight in both plane directions, including a
 // five-second fall below the original floor, without another user setting.
 const terrain=createTerrain(s,Math.max(28,speed*run.duration+.5*Math.abs(gravity)*run.duration**2+2*height)),steep=terrain.slope.normal[1]<.45;
 // A level supported course needs no terrain adaptation. The NN already owns
 // its pinning and knee geometry; another contact solve changes vanilla gait.
 // Test the actual finite surfaces at each frame (including floor removal),
 // and retain simulation whenever gravity or a missing surface owns the root.
 const authoredLevel=experiment.support!==false&&!gravityActive(up,s)&&raw.every((p,i)=>{
  const surfaces=terrain.surfacesAt(i/fps);
  if(surfaces.some(x=>dot(x.normal,up)<1-1e-10))return false;
  const covered=point=>surfaces.some(x=>{const v=x.local(point),[a,b,c,d]=x.bounds;return Math.abs(v[1])<1e-6&&v[0]>=a&&v[0]<=b&&v[2]>=c&&v[2]<=d;});
  return covered(p.points[0])&&legs[i].every(l=>S.footPoints(p,l.foot,l.toe,l.side).every(o=>{const v=add(p.points[l.foot],o);return covered([v[0],p.points[0][1],v[2]]);}));
 });
 if(authoredLevel){
  const frames=raw.map((pose,i)=>{
   const lo=Math.max(0,i-1),hi=Math.min(count-1,i+1),velocity=mul(sub(raw[hi].points[0],raw[lo].points[0]),fps/Math.max(1,hi-lo));
   return {pose,raw:pose,root:pose.points[0],pelvisOffset:0,pelvisTransfer:0,influence:0,nn:true,
    feet:legs[i].map(l=>({side:l.side,state:'NN',target:pose.points[l.foot],contact:null,error:0,penetration:0})),
    surface:{normal:up,bodyUp:up,mass:add(pose.points[0],[0,height,0]),velocity,acceleration:[0,0,0],gravity:[0,-gravity,0],supportForce:[0,gravity,0],drive:[0,0,0],contacts:0,mode:'NN',authored:true,wallTime:0,wallExpired:false,gravityShare:0,gravityActive:false,collisionImpulse:[0,0,0],collisionCorrection:[0,0,0]}};
  });
  return {frames,terrain,settings:s,metrics:createMetrics(),events:[],speed,duration:run.duration,fps,surfacePrototype:true,sample:t=>frames[clamp(Math.round(t*fps),0,count-1)]};
 }
 const initialNormal=s.approach==='parallel'?terrain.slope.normal:up;
 let bodyQ=bodyRotation(initialNormal,s.upright);
 let normal=initialNormal.slice(),mass=add([0,0,0],mul(rotate(bodyQ,up),height)),velocity=[0,0,speed],wallTime=0,lastSupportTime=s.approach==='parallel'||terrain.surfaces.some(x=>x.id==='entry')?0:-Infinity;
 let motionSurface=s.approach==='parallel'?terrain.slope:terrain.floor,previousCourse=motionSurface.id,previousCollisions=new Set();
 if(s.approach==='parallel')velocity=mul(unit(sub([0,0,1],mul(normal,dot([0,0,1],normal)))),speed);
 // Parallel starts already on its surface. At Upright1 a vertical wall has
 // zero projected standing height, but the root capsule still has a radius.
 // Resolve this before frame0 instead of visibly ejecting it on the first tick.
 for(const surface of terrain.surfaces){const p=surface.local(mass),[x0,x1,z0,z1]=surface.bounds,radius=Math.max(.22,height*Math.max(0,dot(rotate(bodyQ,up),surface.normal))*.93);if(p[0]>=x0&&p[0]<=x1&&p[2]>=z0&&p[2]<=z1&&p[1]<radius)mass=add(mass,mul(surface.normal,radius-p[1]));}
 const untilPlant=flags.map(list=>{let next=Infinity;const result=[];for(let i=count-1;i>=0;i--){if(list[i])next=i;result[i]=(next-i)/fps;}return result;});
 const frames=[];
 const metrics=createMetrics(),footSolver=createFeet({names,parents,terrain,settings:s,metrics}),events=footSolver.events;
 for(let i=0;i<count;i++){
  const time=i/fps,p=raw[i],hadFloor=terrain.surfaces.some(x=>x.id==='entry');terrain.setTime(time);
  const hasFloor=terrain.surfaces.some(x=>x.id==='entry');
  if(hadFloor&&!hasFloor){lastSupportTime=-Infinity;events.push({frame:i/2,type:'surface-removed',surface:'entry'});}
  const courseSurface=s.approach==='parallel'?terrain.slope:(mass[2]>terrain.start-.55?terrain.slope:terrain.floor),nextSurface=hasFloor?courseSurface:terrain.slope;
  const desiredNormal=nextSurface.normal;
  normal=unit(add(mul(normal,1-.055),mul(desiredNormal,.055)));
  bodyQ=qslerp(bodyQ,bodyRotation(normal,s.upright),1-Math.exp(-dt/.11));
  // The NN already sees and follows the root yaw command. This transform only
  // adapts its ground frame to the simulated surface; contacts stay material.
  const rootQ=bodyQ,bodyUp=rotate(rootQ,up),surfaceQ=R.fromTo(up,normal),base=sub(mass,mul(bodyUp,height));
  const transform=q=>{const points=p.points.map(v=>add(base,rotate(q,sub(v,p.points[0])))),quats=p.q.map(v=>qm(q,v));return {points,q:quats,axes:quats.map(R.toAxes)};};
  let pose=transform(rootQ);const baseline=pose,terrainPose=transform(surfaceQ),feet=[],supports=[];
  const result=footSolver.step({baseline,terrainPose,source:p,sourceLegs:legs[i],stance:flags.map(x=>x[i]),untilPlant:untilPlant.map(x=>x[i]),time,frame:i/2,normal,surfaceQ,height,velocity,terrainWeight:1,enabled,steep});
  pose=result.pose;feet.push(...result.feet);supports.push(...result.supports);
  const hasSupport=supports.length>0;if(hasSupport)lastSupportTime=time;
  if(steep&&supports.some(x=>x.surface.id==='incline'))wallTime+=dt;
  let supportForce=[0,0,0],drive=[0,0,0];
  const forceSurface=terrain.surfaces.some(x=>x.id===motionSurface.id)?motionSurface:nextSurface;
  const actualNormal=s.inclineGravity?forceSurface.normal:(hasSupport?unit(supports.reduce((v,h)=>add(v,h.normal),[0,0,0])):normal);
  const activeGravity=gravityActive(actualNormal,s),share=gravityShare(actualNormal,s);
  if(enabled&&(hasSupport||time-lastSupportTime<.075)){
   const plane=s.inclineGravity?forceSurface:(hasSupport?supports[0].surface:nextSurface),dist=dot(sub(mass,plane.project(mass)),actualNormal),rest=height*Math.max(.35,dot(bodyUp,actualNormal));
   const elastic=clamp((rest-dist)*110-dot(velocity,actualNormal)*15+(activeGravity?0:gravity*actualNormal[1]),-8,45);
   supportForce=mul(actualNormal,elastic);
   let direction=rotate(R.fromTo(up,actualNormal),[0,0,1]);direction=unit(sub(direction,mul(actualNormal,dot(direction,actualNormal))));
   const tangentVelocity=sub(velocity,mul(actualNormal,dot(velocity,actualNormal)));let command=mul(direction,speed);
   if(s.approach==='parallel'){const contour=unit(cross(actualNormal,direction)),initial=mul(rotate(bodyRotation(initialNormal,s.upright),up),height);command=add(command,mul(contour,clamp(dot(sub(initial,mass),contour)*4,-2,2)));}
   // Bounded traction and gravity decide whether contact can sustain motion.
   // No elapsed-time expiry or latched stop: every valid support can drive again.
   const gravityTangent=sub([0,-gravity,0],mul(actualNormal,-gravity*actualNormal[1]));
   drive=bounded(sub(mul(sub(command,tangentVelocity),10),activeGravity?[0,0,0]:gravityTangent),actualNormal[1]<.45?18:28);
   // Both velocity drive and the commanded height spring are root thrust.
   // Removing only the former lets the spring secretly cancel gravity on slopes.
   drive=gravityDrive(drive,actualNormal,share);
   supportForce=gravityDrive(supportForce,actualNormal,share);
  }
  const acceleration=add([0,-gravity,0],add(supportForce,drive));
  metrics.maxRootAcceleration=Math.max(metrics.maxRootAcceleration,length(acceleration));
  metrics.maxBodyTilt=Math.max(metrics.maxBodyTilt,Math.acos(clamp(dot(bodyUp,up),-1,1))*180/Math.PI);
  if(!hasSupport)metrics.flightFrames++;
  frames.push({pose,raw:baseline,feet,root:pose.points[0],pelvisOffset:0,pelvisTransfer:0,influence:1,
   surface:{normal:actualNormal,bodyUp,mass:mass.slice(),velocity:velocity.slice(),acceleration,gravity:[0,-gravity,0],supportForce,drive,contacts:supports.length,mode:hasSupport?'SUPPORT':velocity[1]<0?'FALL':'FLIGHT',wallTime,wallExpired:false,...(s.inclineGravity?{gravityShare:share,gravityActive:activeGravity}: {})}});
  velocity=add(velocity,mul(acceleration,dt));mass=add(mass,mul(velocity,dt));
  // A finite capsule-plane collision prevents the fast approach tunnelling
  // through the wall. Gravity is integrated first; this only removes inward
  // normal motion, never creates an upward impulse or follows a prerecorded arc.
  const collisionImpulse=[0,0,0],beforeCollision=mass.slice();
  const transfer=surface=>{
   if(!s.inclineGravity||!enabled||surface.id===motionSurface.id||dot(velocity,surface.normal)>=-1e-8)return;
   const before=velocity.slice(),after=transferVelocity(before,motionSurface.normal,surface.normal,s.energyConservation),delta=sub(after,before);
   velocity=after;for(let k=0;k<3;k++)collisionImpulse[k]+=delta[k];
   events.push({frame:i/2,type:'root-transfer',from:motionSurface.id,to:surface.id,before,after,energyConservation:s.energyConservation});motionSurface=surface;
  };
  // Transfer once at the same course boundary that begins body alignment,
  // before gradual normals or capsule damping consume the incoming speed.
  if(courseSurface.id!==previousCourse&&courseSurface.id==='incline')transfer(courseSurface);previousCourse=courseSurface.id;
  const collisions=new Set();
  for(const surface of terrain.surfaces){
   const local=surface.local(mass),[x0,x1,z0,z1]=surface.bounds;
   if(local[0]<x0||local[0]>x1||local[2]<z0||local[2]>z1)continue;
   const radius=Math.max(.22,height*Math.max(0,dot(bodyUp,surface.normal))*.93);
   if(local[1]<=radius+1e-6)collisions.add(surface.id);
   if(local[1]<radius){mass=add(mass,mul(surface.normal,radius-local[1]));const inward=dot(velocity,surface.normal);if(inward<0){if(!previousCollisions.has(surface.id))transfer(surface);const remaining=dot(velocity,surface.normal);if(remaining<0){const delta=mul(surface.normal,-remaining);velocity=add(velocity,delta);for(let k=0;k<3;k++)collisionImpulse[k]+=delta[k];}}}
  }
  previousCollisions=collisions;
  frames[i].surface.collisionImpulse=collisionImpulse;
  frames[i].surface.collisionCorrection=sub(mass,beforeCollision);
 }
 return {frames,terrain,settings:s,metrics,events,speed,duration:run.duration,fps,surfacePrototype:true,sample:t=>frames[clamp(Math.round(t*fps),0,count-1)]};
}
const api={settings,createTerrain,prepare,createFeet,gaitIntent,bodyRotation,gravityActive,gravityShare,gravityDrive,transferVelocity,stableLeg:K.stableLeg,apiVersion:1};if(typeof module!=='undefined')module.exports=api;else root.FootSurface=api;
})(globalThis);
