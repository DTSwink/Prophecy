/* Surface locomotion experiment: NN articulation, material foot contacts, and a
 * gravity-driven root. It is intentionally separate from the accepted stair IK. */
(function(root){
'use strict';
const R=typeof module!=='undefined'?require('./recovery.js'):root.Recovery;
const S=typeof module!=='undefined'?require('./support.js'):root.BodyflipSupport;
const K=typeof module!=='undefined'?require('./footik.js'):root.FootIK;
const T=typeof module!=='undefined'?require('./terrain.js'):root.FootTerrain;
const {add,sub,mul,dot,cross,length,unit,rotate,qm,qinv,qslerp}=R;
const up=[0,1,0],identity=[0,0,0,1],clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const smooth=x=>{x=clamp(x,0,1);return x*x*(3-2*x);};
const bounded=(v,max)=>length(v)>max?mul(unit(v),max):v;
function settings(input={}){const finite=(v,d)=>Number.isFinite(Number(v))?Number(v):d;return {...K.sanitize(input),terrain:Array.isArray(input.platformLayouts?.[input.terrain])?input.terrain:'incline',slopeAngle:clamp(finite(input.slopeAngle??45,45),0,90),approach:input.approach==='parallel'?'parallel':'toward',upright:clamp(finite(input.upright??.55,.55),0,1)};}
function pinsAllowed(normal,velocity,s){return !(Math.acos(clamp(normal[1],-1,1))*180/Math.PI>s.minGravityIncline+1e-8&&length(velocity)<(s.pinReleaseSpeed??.2));}
function gravityActive(normal,s){
 return s.inclineGravity&&Math.acos(clamp(normal[1],-1,1))*180/Math.PI>=s.minGravityIncline-1e-8;
}
// The threshold enables full gravity; the percentage only removes vertical
// root thrust. Neither gravity nor thrust suppression ramps toward 90 degrees.
function gravityShare(normal,s){return gravityActive(normal,s)?s.fullGravity/100:0;}
function pelvisCloser(normal,s,velocity=[0,0,0]){
 const angle=Math.acos(clamp(normal[1],-1,1))*180/Math.PI,minimum=s.minGravityIncline;
 if(!s.enabled||minimum>=90||angle<=minimum)return 0;
 const speed=length(velocity),lo=s.pelvisSpeedMin??0,hi=s.pelvisSpeedMax??3.5;
 const blend=hi>lo?clamp((speed-lo)/(hi-lo),0,1):(speed>lo?1:0);
 const low=s.pelvisCloser??0,high=s.pelvisCloserMax??low;
 return (low+(high-low)*blend)/100*clamp((angle-minimum)/(90-minimum),0,1);
}
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
 const procedural=s.terrain==='incline'?null:T.create(s);
 const original=procedural?procedural.tiles.map(tile=>S.rectangle(tile.id,[0,tile.y,0],[1,0,0],[0,0,1],[tile.x0,tile.x1,tile.z0,tile.z1],Math.max(.12,tile.y+.2))):(parallel?[slope]:[floor,slope]);
 const records=s.platformLayouts[s.terrain],custom=Array.isArray(records);
 const complete=custom?records.map(S.platformSurface):original,withoutFloor=complete.filter(p=>p.id!=='entry');
 const same=(a,b)=>a&&b&&['position','size','rotation'].every(k=>a[k].every((v,i)=>Math.abs(v-b[k][i])<1e-8));
 const editedRoute=custom&&(s.terrain!=='incline'||original.some(p=>!same(S.platformRecord(p),records.find(x=>x.id===p.id))));
 if(custom)for(const surface of complete)surface.finiteSlab=true;
 // Root navigation retains each untouched stair's ramp segment. Feet query
 // actual treads. An edited tread or an added platform uses its edited plane.
 const navigation=complete.map(p=>{
  const tile=procedural?.tiles.find(t=>t.id===p.id),before=original.find(x=>x.id===p.id);
  if(!tile||!p.id.startsWith('step')||!['stairs','down'].includes(s.terrain)||!before)return p;
  const x=S.platformRecord(p),y=S.platformRecord(before);
  if(['position','size','rotation'].some(k=>x[k].some((v,i)=>Math.abs(v-y[k][i])>1e-8)))return p;
  const y0=procedural.rootHeight(tile.z0),y1=procedural.rootHeight(tile.z1),v=[0,y1-y0,tile.z1-tile.z0];
  return S.rectangle(p.id,[0,y0,tile.z0],[1,0,0],unit(v),[tile.x0,tile.x1,0,length(v)],.2);
 });
 const surfacesAt=time=>s.terrain==='incline'&&s.deleteFloorFrame>=0&&time*60>=s.deleteFloorFrame-1e-8?withoutFloor:complete;
 let surfaces=surfacesAt(0);
 const pick=(p,normal=up)=>{
  let best=null;
  for(const surface of surfaces){const point=surface.closest(p),distance=length(sub(p,point));if(!best||distance<best.distance)best={surface,point,distance};}
  return best;
 };
 const rootSurfaces=()=>navigation.filter(p=>surfaces.some(x=>x.id===p.id));
 const pickRoot=(mass,bodyUp,height)=>{let best=null;for(const surface of rootSurfaces()){
  const p=surface.local(mass),radius=Math.max(.22,height*Math.max(0,dot(bodyUp,surface.normal))*.93);
  // Do not pull a root underneath a finite slab up through its underside.
  if(p[1]<-surface.box.dims[1]-.05)continue;
  const tangent=length(sub(surface.project(mass),surface.closest(mass))),distance=Math.hypot(p[1]-radius,tangent);
  if(!best||distance<best.distance)best={surface,distance};
 }return best?.surface||null;};
 return {kind:s.terrain,custom,editedRoute,start,end:procedural?.end??30,slope,floor,allSurfaces:complete,original,rootSurfaces,pickRoot,get surfaces(){return surfaces;},surfacesAt,setTime:time=>{surfaces=surfacesAt(time);},tiles:[],pick,
  rootHeight:z=>procedural?procedural.rootHeight(z):parallel?0:Math.max(0,z-start)*Math.tan(Math.min(a,Math.PI/2-.001)),
  floorFor:(p,offsets)=>{const hit=pick(p);return hit?p[1]-Math.min(...offsets.map(o=>dot(sub(add(p,o),hit.point),hit.surface.normal))):p[1];}};
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
 const pitch=Math.atan2(dot(frame.forward,surface.normal),dot(frame.up,surface.normal))*180/Math.PI;
 return {surface,id,pose,rotation,pitch,angle:0,sample:angle=>angle>=0?positive(angle/85):negative(-angle/45)};
}
function constrain(p,l,target,rotation,surfaces,reachRatio=.985,fixedCorners=null){
 const hip=p.points[l.hip],reach=l.reach*reachRatio,minimum=Math.min(l.reach*.27,length(sub(p.points[l.foot],hip)));let result=target.slice();
 // Rotation is fixed for this projection loop. Plane-space corner offsets
 // therefore stay fixed too; only the ankle's translation changes each pass.
 const projected=fixedCorners?surfaces.map(surface=>({surface,corners:fixedCorners.map(o=>[dot(o,surface.u),dot(o,surface.normal),dot(o,surface.v)])})):null;
 for(let pass=0;pass<12;pass++){
  const before=result;
  const v=sub(result,hip),distance=length(v);if(distance>reach)result=add(hip,mul(unit(v),reach));
  else if(distance<minimum){const axis=distance>1e-8?unit(v):unit(sub(p.points[l.foot],hip));result=add(hip,mul(axis,minimum));}
  if(projected){for(const {surface,corners} of projected){
   const origin=surface.local(result),[x0,x1,z0,z1]=surface.bounds;let penetration=0;
   for(const o of corners){const x=origin[0]+o[0],y=origin[1]+o[1],z=origin[2]+o[2];if(surface.finiteSlab&&y<-surface.box.dims[1]-.04)continue;if(x>=x0&&x<=x1&&z>=z0&&z<=z1)penetration=Math.max(penetration,-y);}
   if(penetration>0)result=add(result,mul(surface.normal,penetration+1e-5));
  }}else{
  const corners=S.footPoints(shoePose(p,l,result,rotation),l.foot,l.toe,l.side);
  for(const surface of surfaces){const [x0,x1,z0,z1]=surface.bounds;let penetration=0;
   for(const o of corners){const local=surface.local(add(result,o));if(surface.finiteSlab&&local[1]<-surface.box.dims[1]-.04)continue;if(local[0]>=x0&&local[0]<=x1&&local[2]>=z0&&local[2]<=z1)penetration=Math.max(penetration,-local[1]);}
   if(penetration>0)result=add(result,mul(surface.normal,penetration+1e-5));
  }
  }
  if(length(sub(result,before))<1e-8)break;
 }
 return result;
}
function penetration(p,l,surfaces){let result=0;const points=S.footPoints(p,l.foot,l.toe,l.side);for(const surface of surfaces){const [x0,x1,z0,z1]=surface.bounds;for(const v of points){const local=surface.local(add(p.points[l.foot],v));if(surface.finiteSlab&&local[1]<-surface.box.dims[1]-.04)continue;if(local[0]>=x0&&local[0]<=x1&&local[2]>=z0&&local[2]<=z1)result=Math.max(result,-local[1]);}}return result;}
function solvePole(p,l,target,parents,rotation,previous,state,dt,surfaces){
 const axis=unit(sub(target,p.points[l.hip]));
 // Preserve the signed NN knee hinge; obstacles cannot pick its other side.
 let normal=sub(l.normal,mul(axis,dot(l.normal,axis)));
 if(length(normal)<1e-5)normal=rotate(R.fromTo(rotate(p.q[l.pelvis],l.axisLocal),axis),l.normal);
 normal=unit(normal);
 const pole=unit(cross(normal,axis)),inverse=qinv(p.q[l.pelvis]);
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
 const fresh=()=>({pin:null,released:null,lastTarget:null,lastRotation:null,lastVelocity:[0,0,0]});
 const footState=[fresh(),fresh()],events=[];
 let serial=0,previous=null;
 function step({baseline,terrainPose,source:p,sourceLegs,stance,untilPlant,time,frame=time*60,normal,surfaceQ,height,velocity,terrainWeight=1,enabled=s.enabled,wallExpired=false,steep=false,allowPins=true,pelvisShift=null}){
  const fps=120,dt=1/fps,feet=[],supports=[];let pose=baseline;
  if(!terrain.surfaces.length){for(let side=0;side<2;side++){const state=footState[side],l=sourceLegs[side];if(state.pin)events.push({frame,type:'release',side:l.side,surface:state.pin.surface.id,reason:'surface-removed'});state.pin=null;state.released=null;state.lastTarget=null;state.lastRotation=null;feet.push({side:l.side,state:'SWING',target:baseline.points[l.foot],contact:null,error:0,penetration:0,soleGap:Infinity});}previous=baseline;return {pose:baseline,feet,supports};}
  // Move hip anchors and torso before solving the legs. Targets/carrier remain
  // the original NN feet, so this posture edit cannot translate material pins.
  if(enabled&&pelvisShift&&length(pelvisShift)>0)pose={...baseline,points:baseline.points.map((v,i)=>i?add(v,pelvisShift):v)};
  for(let side=0;side<2;side++){
   const supportCount=supports.length;
   const state=footState[side],l=S.leg(pose,names,side===0?'L':'R'),sourceLeg=sourceLegs[side],sourceFrame=S.footFrame(p,sourceLeg.foot,sourceLeg.toe,sourceLeg.side);
   // Carry the source's stabilized anatomical hinge with its thigh. Rebuilding
   // it from the tilted pelvis reverses knees; a straight leg's geometric
   // cross-product alone is undefined and can flip at the next bent sample.
   l.normal=unit(rotate(qm(pose.q[l.hip],qinv(sourceLeg.hipQ)),sourceLeg.normal));
   l.poleLocal=rotate(qinv(pose.q[l.pelvis]),unit(cross(l.normal,unit(sub(pose.points[l.foot],pose.points[l.hip])))));
   // Filter the terrain residual in the moving NN foot frame. Root velocity
   // here used to low-pass the gait itself and leave the ankle behind.
   const carrier=state.lastBaseline?mul(sub(baseline.points[l.foot],state.lastBaseline),fps):velocity;
   let target=add(baseline.points[l.foot],mul(sub(terrainPose.points[l.foot],baseline.points[l.foot]),terrainWeight)),rotation={footQ:qslerp(baseline.q[l.foot],terrainPose.q[l.foot],terrainWeight),toeQ:qslerp(baseline.q[l.toe],terrainPose.q[l.toe],terrainWeight)};
   const desired=terrain.pick(target),surface=desired.surface,tooSteep=surface.id==='incline'&&steep,canAttach=enabled&&allowPins&&!(tooSteep&&wallExpired);
   const sourcePitch=Math.asin(clamp(sourceFrame.forward[1],-1,1)),heading=rotate(surfaceQ,unit([sourceFrame.forward[0],0,sourceFrame.forward[2]]));
   const contactRotation=footRotation(pose,l,surface.normal,heading,0),captureFrom=state.lastTarget||target,captureRotation=state.lastRotation||rotation;
   const fitted=fit(pose,l,captureFrom,captureRotation,surface);
   let surfaceRemoved=state.pin&&!terrain.surfaces.some(s=>s.id===state.pin.surface.id);
   if(surfaceRemoved&&state.lastContact){
    const old=state.pin.surface,point=state.lastContact.point;
    const replacement=terrain.surfaces.find(s=>dot(s.normal,old.normal)>1-1e-8&&length(sub(s.closest(point),point))<2e-5);
    if(replacement){
     const sample=state.pin.sample;
     state.pin.sample=angle=>{const r=sample(angle);return {...r,valid:length(sub(replacement.closest(r.contact),r.contact))<2e-5};};
     state.pin.surface=replacement;surfaceRemoved=false;
     events.push({frame,type:'support-transfer',side:l.side,from:old.id,to:replacement.id});
    }
   }
   if(state.pin&&(!stance[side]||!canAttach||surfaceRemoved)){
    state.released={time,point:state.lastTarget,rotation:state.lastRotation,velocity:state.lastVelocity};events.push({frame:frame,type:'release',side:l.side,surface:state.pin.surface.id,reason:!allowPins?'root-speed':surfaceRemoved?'surface-removed':!canAttach?'support-budget':'gait'});state.pin=null;
   }
   const d=dot(sub(target,fitted.target),surface.normal),reach=length(sub(fitted.target,pose.points[l.hip])),captureDistance=length(sub(captureFrom,fitted.target));
   // With no requested surface correction, acquire the NN's actual contact
   // rather than pulling a still-airborne shoe several centimetres down. The
   // acquisition envelope grows continuously with the requested terrain delta.
   const captureRadius=.005+Math.min(.03,length(sub(terrainPose.points[l.foot],baseline.points[l.foot]))*terrainWeight);
   if(!state.pin&&stance[side]&&canAttach&&captureDistance<captureRadius&&reach<l.reach*.9999&&(!state.released||time-state.released.time>.12)){
    state.pin=capture(pose,l,fitted.target,captureRotation,surface,++serial);state.pin.yaw=K.createPinYaw(surface.normal,s.footYawLimit??45);state.released=null;events.push({frame:frame,type:'plant',side:l.side,surface:surface.id});
   }
   let contact=null;
   if(state.pin){
    const pin=state.pin,wanted=clamp(pin.pitch-sourcePitch*180/Math.PI,-44,70),previousAngle=pin.angle,maxAngleStep=300*dt;pin.angle+=clamp(wanted-pin.angle,-maxAngleStep,maxAngleStep);
    let roll=pin.sample(pin.angle),best=length(sub(roll.foot,pose.points[l.hip]));
    // The useful pivot direction depends on travel. A backward stride can
    // preserve its heel contact by rolling the opposite way. Natural rotation
    // AND this reach correction share one300deg/s budget.
    // The former94% target forced roughly40 degrees of knee bend even when
    // the NN was legitimately extended. Preserve its extension allowance.
    const preferredReach=Math.max(l.reach*.985,length(sub(baseline.points[l.foot],baseline.points[l.hip])));
    if(best>preferredReach){
     const natural=pin.angle,lo=Math.max(-44,previousAngle-maxAngleStep),hi=Math.min(70,previousAngle+maxAngleStep),goal=preferredReach,angles=[lo,hi,natural];
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
    if(state.released&&state.released.point){
     if(state.released.deltaFoot===undefined){state.released.deltaFoot=qm(state.released.rotation.footQ,qinv(rotation.footQ));state.released.deltaToe=qm(state.released.rotation.toeQ,qinv(rotation.toeQ));}
     const elapsed=time-state.released.time,u=clamp(elapsed/.18,0,1),w=1-smooth(u);
     // Position already has a velocity-continuous swing filter below. A
     // second .18s blend toward the old world pin delayed departure again.
     rotation={footQ:qm(qslerp(identity,state.released.deltaFoot,w),rotation.footQ),toeQ:qm(qslerp(identity,state.released.deltaToe,w),rotation.toeQ)};
     if(u===1)state.released=null;
    }
    // Collision is solved against shoe volume on the actual plane; never lift
    // along world Y on an inclined surface.
    const shaped=shoePose(pose,l,target,rotation),points=S.footPoints(shaped,l.foot,l.toe,l.side);
    const depth=Math.min(...points.map(o=>dot(sub(add(target,o),surface.closest(add(target,o))),surface.normal)));
    if(depth<0&&!wallExpired&&(!surface.finiteSlab||surface.local(target)[1]>=-surface.box.dims[1]))target=add(target,mul(surface.normal,-depth+.001));
   }
   if(!enabled){target=baseline.points[l.foot];rotation={footQ:baseline.q[l.foot],toeQ:baseline.q[l.toe]};contact=null;}
   if(!contact&&state.lastRotation){for(const key of ['footQ','toeQ']){const angle=length(R.qlog(qm(rotation[key],qinv(state.lastRotation[key])))),limit=600*Math.PI/180*dt;if(angle>limit)rotation[key]=qslerp(state.lastRotation[key],rotation[key],limit/angle);}}
   metrics.maxRequestedReachExcess=Math.max(metrics.maxRequestedReachExcess,length(sub(target,pose.points[l.hip]))-l.reach*.985);
   if(!contact){
    if(state.lastTarget){
     const relative=state.lastRelativeVelocity||[0,0,0],want=bounded(mul(sub(target,add(state.lastTarget,mul(carrier,dt))),30),s.gait==='run'?8:5);
     const nextVelocity=add(relative,bounded(sub(want,relative),(s.gait==='run'?110:80)*dt));
     target=add(state.lastTarget,mul(add(carrier,nextVelocity),dt));state.lastRelativeVelocity=nextVelocity;
    }
    target=constrain(pose,l,target,rotation,terrain.surfaces,Math.max(.985,length(sub(baseline.points[l.foot],baseline.points[l.hip]))/l.reach));
   }else state.lastRelativeVelocity=sub(state.lastVelocity,carrier);
   const solveTarget=(point,rot)=>solvePole(pose,l,point,parents,rot,previous,state,dt);
   let solved=solveTarget(target,rotation);
   const naturalFoot=qm(solved.q[l.knee],qm(qinv(sourceLeg.kneeQ),sourceLeg.footQ)),naturalToe=qm(naturalFoot,qm(qinv(sourceLeg.footQ),sourceLeg.toeQ));
   const ankleDifference=length(R.qlog(qm(rotation.footQ,qinv(naturalFoot)))),ankleLimit=65*Math.PI/180;
   if(ankleDifference>ankleLimit){
    if(contact){supports.pop();state.pin=null;contact=null;metrics.ankleReleases++;events.push({frame:frame,type:'release',side:l.side,surface:surface.id,reason:'ankle-limit'});}
    const blend=ankleLimit/ankleDifference;rotation={footQ:qslerp(naturalFoot,rotation.footQ,blend),toeQ:qslerp(naturalToe,rotation.toeQ,blend)};
    target=constrain(pose,l,target,rotation,terrain.surfaces,Math.max(.985,length(sub(baseline.points[l.foot],baseline.points[l.hip]))/l.reach));solved=solveTarget(target,rotation);
   }
   if(contact&&penetration(solved,l,terrain.surfaces)>1e-4){supports.pop();state.pin=null;contact=null;events.push({frame:frame,type:'release',side:l.side,surface:surface.id,reason:'shoe-collision'});target=constrain(pose,l,target,rotation,terrain.surfaces,Math.max(.985,length(sub(baseline.points[l.foot],baseline.points[l.hip]))/l.reach));solved=solveTarget(target,rotation);}
   pose=solved;
   const actual=pose.points[l.foot],error=length(sub(actual,target));
   const depth=penetration(pose,l,terrain.surfaces);
   if(contact&&error>.005){supports.pop();contact=null;state.pin=null;}
   // A shoe touching the surface supports the root even while its animation
   // pin is acquiring/releasing. Tangential locking is not a contact sensor.
   if(enabled&&supports.length===supportCount){
    const corners=S.footPoints(pose,l.foot,l.toe,l.side).map(o=>add(actual,o));
    for(const plane of terrain.surfaces){
     const [x0,x1,z0,z1]=plane.bounds,points=corners.filter(v=>{const a=plane.local(v);return a[0]>=x0&&a[0]<=x1&&a[2]>=z0&&a[2]<=z1;});
     if(!points.length)continue;
     const point=points.reduce((a,b)=>dot(a,plane.normal)<dot(b,plane.normal)?a:b),gap=dot(sub(point,plane.closest(point)),plane.normal);
     if(gap>=-1e-4&&gap<=.002){supports.push({normal:plane.normal,surface:plane,point:plane.closest(point)});break;}
    }
   }
   const v=state.lastTarget?mul(sub(actual,state.lastTarget),fps):[0,0,0];metrics.maxFootSpeed=Math.max(metrics.maxFootSpeed,length(v));metrics.maxRelativeFootSpeed=Math.max(metrics.maxRelativeFootSpeed,length(sub(v,velocity)));state.lastVelocity=v;state.lastTarget=actual;state.lastRotation=rotation;state.lastBaseline=baseline.points[l.foot];
   // Constraint projection is not swing momentum; only a held pin supplies
   // the relative velocity to carry into departure.
   if(contact)state.lastRelativeVelocity=sub(v,carrier);
   if(contact)metrics.maxContactDrift=Math.max(metrics.maxContactDrift,length(sub(add(actual,rotate(pose.q[l.foot],contact.localPoint)),contact.point)));
   metrics.maxRelativeAnkleDegrees=Math.max(metrics.maxRelativeAnkleDegrees,length(R.qlog(qm(qm(qinv(pose.q[l.knee]),pose.q[l.foot]),qinv(qm(qinv(sourceLeg.kneeQ),sourceLeg.footQ)))))*180/Math.PI);
   if(previous){const kneeStep=length(R.qlog(qm(pose.q[l.knee],qinv(previous.q[l.knee]))))*180/Math.PI,ankleStep=length(R.qlog(qm(pose.q[l.foot],qinv(previous.q[l.foot]))))*180/Math.PI;
    if(kneeStep>metrics.maxKneeStep){metrics.maxKneeStep=kneeStep;metrics.maxKneeFrame=frame;metrics.maxKneeSide=l.side;}
    if(ankleStep>metrics.maxAnkleStep){metrics.maxAnkleStep=ankleStep;metrics.maxAnkleFrame=frame;metrics.maxAnkleSide=l.side;}
   }
   metrics.maxReachError=Math.max(metrics.maxReachError,error);metrics.maxPenetration=Math.max(metrics.maxPenetration,depth);
   if(contact){metrics.contactFrames++;if(contact.surface==='incline')metrics.wallContactFrames++;}
   state.lastContact=contact;
   feet.push({side:l.side,state:contact?(Math.abs(contact.angle)>1?'ROLL':'PIN'):'SWING',target:actual,contact,error,penetration:depth,soleGap:dot(sub(actual,surface.closest(actual)),surface.normal)});
  }
  previous=pose;return {pose,feet,supports};
 }
 return {step,metrics,events,reset(){footState.splice(0,2,fresh(),fresh());previous=null;}};
}
function createRootMotion({s,terrain,height,speed,gravity=9.81,enabled=true,metrics=createMetrics(),events=[]},saved=null){
 const dt=1/120,steep=terrain.slope.normal[1]<.45;
 const initialSurface=terrain.editedRoute?terrain.pickRoot([0,terrain.rootHeight(0)+height,0],up,height):null;
 const initialNormal=terrain.editedRoute?(initialSurface?.normal||up):s.approach==='parallel'?terrain.slope.normal:up;
 let bodyQ=bodyRotation(initialNormal,s.upright);
 let normal=initialNormal.slice(),mass=add([0,terrain.editedRoute?terrain.rootHeight(0):0,0],mul(rotate(bodyQ,up),height)),velocity=[0,0,speed],wallTime=0,lastSupportTime=terrain.editedRoute?(initialSurface?0:-Infinity):s.approach==='parallel'||terrain.surfaces.some(x=>x.id==='entry')?0:-Infinity;
 let motionSurface=terrain.editedRoute?(initialSurface||terrain.floor):s.approach==='parallel'?terrain.slope:terrain.floor,previousCourse=motionSurface.id,previousCollisions=new Set(),slide=null,previousVerticalSpeed=null;
 if(s.approach==='parallel'||terrain.editedRoute)velocity=mul(unit(sub([0,0,1],mul(normal,dot([0,0,1],normal)))),speed);
 // Parallel starts already on its surface. At Upright1 a vertical wall has
 // zero projected standing height, but the root capsule still has a radius.
 // Resolve this before frame0 instead of visibly ejecting it on the first tick.
 for(const surface of terrain.custom?terrain.rootSurfaces():terrain.surfaces){const p=surface.local(mass),[x0,x1,z0,z1]=surface.bounds,radius=Math.max(.22,height*Math.max(0,dot(rotate(bodyQ,up),surface.normal))*.93);if(p[0]>=x0&&p[0]<=x1&&p[2]>=z0&&p[2]<=z1&&p[1]<radius&&(!terrain.custom||p[1]>=-surface.box.dims[1]))mass=add(mass,mul(surface.normal,radius-p[1]));}

 if(saved){bodyQ=saved.bodyQ;normal=saved.normal;mass=saved.mass;velocity=saved.velocity;wallTime=saved.wallTime;lastSupportTime=saved.lastSupportTime;motionSurface=terrain.allSurfaces.find(x=>x.id===saved.motionSurface)||terrain.floor;previousCourse=saved.previousCourse;previousCollisions=new Set(saved.previousCollisions);slide=saved.slide||null;}
 if(saved)previousVerticalSpeed=saved.previousVerticalSpeed??null;
 function snapshot(){return {bodyQ:bodyQ.slice(),normal:normal.slice(),mass:mass.slice(),velocity:velocity.slice(),wallTime,lastSupportTime,motionSurface:motionSurface.id,previousCourse,previousCollisions:[...previousCollisions],slide,previousVerticalSpeed};}
 function begin(time){
  // Negative fall thresholds allow entry before the apex. Keep that initial
  // ascent through freefall; after reaching the apex, any new ascent exits.
  const slowingAscent=previousVerticalSpeed===null||velocity[1]<previousVerticalSpeed;
  previousVerticalSpeed=velocity[1];let exited=false;
  if(slide&&velocity[1]<=0&&!slide.descended)slide={...slide,descended:true};
  const exitSpeed=slide?.descended?0:Math.max(0,-s.slideSpeed);
  if(slide&&velocity[1]>exitSpeed){events.push({frame:time*60,type:'slide-exit',time,velocity:velocity.slice(),reason:'ascending'});slide=null;lastSupportTime=-Infinity;exited=true;}
  const hadFloor=terrain.surfaces.some(x=>x.id==='entry');terrain.setTime(time);
  const hasFloor=terrain.surfaces.some(x=>x.id==='entry');
  if(hadFloor&&!hasFloor){lastSupportTime=-Infinity;events.push({frame:time*60,type:'surface-removed',surface:'entry'});}
  const candidate=terrain.custom?terrain.pickRoot(mass,rotate(bodyQ,up),height):null;
  const editedContact=candidate&&!terrain.original.some(p=>p.id===candidate.id)&&length(sub(mass,candidate.closest(mass)))<height+.2;
  const useEdited=terrain.editedRoute||editedContact;
  const courseSurface=useEdited?(candidate||motionSurface):s.approach==='parallel'?terrain.slope:(mass[2]>terrain.start-.55?terrain.slope:terrain.floor),nextSurface=useEdited?courseSurface:hasFloor?courseSurface:terrain.slope;
  const desiredNormal=nextSurface.normal;
  if(!slide){normal=unit(add(mul(normal,1-.055),mul(desiredNormal,.055)));
  bodyQ=qslerp(bodyQ,bodyRotation(normal,s.upright),1-Math.exp(-dt/.11));}
  // The NN already sees and follows the root yaw command. This transform only
  // adapts its ground frame to the simulated surface; contacts stay material.
  // The capsule retains the physical controller's extent. Its mesh origin is
  // the ground reference along the surface normal, not the tilted torso's up.
  const rootQ=bodyQ,bodyUp=rotate(rootQ,up),surfaceQ=R.fromTo(up,normal),base=sub(mass,mul(normal,Math.max(.22,height*Math.max(0,dot(bodyUp,normal)))));

  const pinNormal=!useEdited&&s.inclineGravity&&terrain.surfaces.some(x=>x.id===motionSurface.id)?motionSurface.normal:nextSurface.normal;
  if(!slide&&!exited&&enabled&&s.slideEnabled&&Math.acos(clamp(pinNormal[1],-1,1))*180/Math.PI>s.minGravityIncline+1e-8&&(velocity[1]<0||(s.slideSpeed<0&&slowingAscent))&&velocity[1]<=-s.slideSpeed){
   const plane=terrain.surfaces.find(p=>dot(p.normal,pinNormal)>1-1e-6&&length(sub(mass,p.closest(mass)))<height+.25);
   if(plane){
    // Enter a surface slide without retaining the locomotion spring's outward
    // rebound. Preserve tangential inertia; no attraction or ongoing thrust.
    const outward=Math.max(0,dot(velocity,plane.normal));
    velocity=sub(velocity,mul(plane.normal,outward));
    slide={time,surface:plane.id,velocity:velocity.slice(),descended:velocity[1]<=0};events.push({frame:time*60,type:'slide',...slide});
   }
  }
  return {time,hasFloor,useEdited,nextSurface,courseSurface,pinNormal,normal:normal.slice(),rootQ,bodyUp,surfaceQ,base,mass:mass.slice(),velocity:velocity.slice(),...(slide?{slide}: {})};
 }
 function finish(context,supports){
  const {time,hasFloor,useEdited,nextSurface,courseSurface,normal,rootQ,bodyUp,surfaceQ,base}=context;
  const hasSupport=!slide&&supports.length>0;if(hasSupport)lastSupportTime=time;
  if(steep&&supports.some(x=>x.surface.id==='incline'))wallTime+=dt;
  let supportForce=[0,0,0],drive=[0,0,0];
  const forceSurface=useEdited?nextSurface:terrain.surfaces.some(x=>x.id===motionSurface.id)?motionSurface:nextSurface;
  const actualNormal=s.inclineGravity||useEdited?forceSurface.normal:(hasSupport?unit(supports.reduce((v,h)=>add(v,h.normal),[0,0,0])):normal);
  const activeGravity=gravityActive(actualNormal,s),share=gravityShare(actualNormal,s);
  if(!slide&&enabled&&(hasSupport||time-lastSupportTime<.075)){
   const plane=s.inclineGravity||useEdited?forceSurface:(hasSupport?supports[0].surface:nextSurface),dist=dot(sub(mass,plane.project(mass)),actualNormal),rest=height*Math.max(.35,dot(bodyUp,actualNormal));
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
  const receipt={normal:actualNormal,bodyUp,bodyRotation:rootQ,gaitRotation:surfaceQ,mass:mass.slice(),velocity:velocity.slice(),acceleration,gravity:[0,-gravity,0],supportForce,drive,contacts:slide?0:supports.length,mode:slide?'SLIDE':hasSupport?'SUPPORT':velocity[1]<0?'FALL':'FLIGHT',wallTime,wallExpired:false,pinsAllowed:!slide&&pinsAllowed(context.pinNormal,velocity,s),pinNormal:context.pinNormal,...(s.inclineGravity?{gravityShare:share,gravityActive:activeGravity}: {}),...(slide?{slide}: {})};
  velocity=add(velocity,mul(acceleration,dt));mass=add(mass,mul(velocity,dt));
  // A finite capsule-plane collision prevents the fast approach tunnelling
  // through the wall. Gravity is integrated first; this only removes inward
  // normal motion, never creates an upward impulse or follows a prerecorded arc.
  const collisionImpulse=[0,0,0],beforeCollision=mass.slice();
  const transfer=surface=>{
   if(slide||(!s.inclineGravity&&!terrain.custom)||!enabled||surface.id===motionSurface.id||dot(velocity,surface.normal)>=-1e-8)return;
   const before=velocity.slice(),after=transferVelocity(before,motionSurface.normal,surface.normal,s.energyConservation),delta=sub(after,before);
   velocity=after;for(let k=0;k<3;k++)collisionImpulse[k]+=delta[k];
   events.push({frame:time*60,type:'root-transfer',from:motionSurface.id,to:surface.id,before,after,energyConservation:s.energyConservation});motionSurface=surface;
  };
  // Transfer once at the same course boundary that begins body alignment,
  // before gradual normals or capsule damping consume the incoming speed.
  if(courseSurface.id!==previousCourse&&(useEdited||courseSurface.id==='incline')&&terrain.surfaces.some(p=>p.id===courseSurface.id))transfer(courseSurface);previousCourse=courseSurface.id;
  const collisions=new Set();
  for(const surface of terrain.custom?terrain.rootSurfaces():terrain.surfaces){
   const local=surface.local(mass),[x0,x1,z0,z1]=surface.bounds;
   if(local[0]<x0||local[0]>x1||local[2]<z0||local[2]>z1)continue;
   if(terrain.custom&&local[1]<-surface.box.dims[1]-.05)continue;
   const radius=Math.max(.22,height*Math.max(0,dot(bodyUp,surface.normal))*.93);
   if(local[1]<=radius+1e-6)collisions.add(surface.id);
   if(local[1]<radius){mass=add(mass,mul(surface.normal,radius-local[1]));const inward=dot(velocity,surface.normal);if(inward<0){if(!previousCollisions.has(surface.id))transfer(surface);const remaining=dot(velocity,surface.normal);if(remaining<0){const delta=mul(surface.normal,-remaining);velocity=add(velocity,delta);for(let k=0;k<3;k++)collisionImpulse[k]+=delta[k];}}}
  }
  previousCollisions=collisions;
  receipt.collisionImpulse=collisionImpulse;
  receipt.collisionCorrection=sub(mass,beforeCollision);
  return receipt;
 }
 function forecast(context,supports,ticks){
  const copy=createRootMotion({s,terrain,height,speed,gravity,enabled},snapshot()),result=[context];let c=context;
  try{for(let k=1;k<=ticks;k++){
   // Predictions retain observed support only while it remains reachable.
   // New contacts are discovered by the actual foot solve on the next tick.
   const held=supports.filter(h=>terrain.surfaces.some(x=>x.id===h.surface.id)&&length(sub(c.mass,h.point))<height*1.2);
   copy.finish(c,held);c=copy.begin(context.time+k/120);result.push(c);
  }}finally{terrain.setTime(context.time);}
  return result;
 }
 return {begin,finish,forecast,snapshot};
}
// Host-owned slide posture. Its contacts are sliding visual constraints, never
// material pins or root forces. Once a limb cannot reach, it leaves the wall.
function slideTargetShift(normal,velocity,s,part='feet'){
 const tangentUp=sub(up,mul(normal,dot(up,normal)));
 if(length(tangentUp)<1e-8)return [0,0,0];
 const maximum=part==='hand'?s.slideHandShift??s.slideShift:s.slideShift,speed=part==='hand'?s.slideHandShiftSpeed??s.slideShiftSpeed:s.slideShiftSpeed;
 return mul(unit(tangentUp),(maximum??20)/100*clamp(length(velocity)/(speed??10),0,1));
}
function slideBalanceTime(time){
 // Integrate speed bursts, rather than multiplying absolute time by a changing
 // speed (which would jump phase or run backwards as the burst subsides).
 // The idle gaps run at exactly 1x; accumulated extra phase is never discarded.
 const clock=time-.7;if(clock<=0)return time;
 const hash=x=>{const v=Math.sin(x*127.1+311.7)*43758.5453;return v-Math.floor(v);};
 const integral=x=>{x=clamp(x,0,1);return x*x*x*x*(2.5+x*(-3+x));};
 let extra=0;
 for(let event=0;event<=Math.floor(clock/1.25);event++){
  const age=clock-event*1.25-(.04+.24*hash(event+93));if(age<=0)continue;
  const attack=.10+.07*hash(event+121),release=.4+.24*hash(event+157),boost=1.2+1.2*hash(event+307);
  const tail=clamp(age-attack,0,release);
  const area=age<attack?attack*integral(age/attack):attack*.5+tail-release*integral(tail/release);
  extra+=boost*area;
 }
 return time+extra;
}
function createSlidePose(names,parents,terrain,s){
 const J=typeof module!=='undefined'?require('./slide-joints.js'):root.SlideJoints,joints=J.build(undefined,names,parents);
 const E=typeof module!=='undefined'?require('./slide-entry.js'):root.SlideEntry;
 const A=typeof module!=='undefined'?require('./slide-arms.js'):root.SlideArms;
 const slideArms=A.create({names,parents,joints});
 const pelvis=names.indexOf('pelvis'),arms=['l','r'].map(side=>({side,a:names.indexOf('upperarm_'+side),b:names.indexOf('lowerarm_'+side),c:names.indexOf('hand_'+side)}));
 const referenceLocal=R.localize(joints.reference.points,joints.reference.q,parents);
 const spine=names.map((name,i)=>name.startsWith('spine_')?i:-1).filter(i=>i>=0),neck=['neck_01','neck_02','head'].map(name=>names.indexOf(name));
 const descendants=names.map((_,joint)=>names.map((_,i)=>{let p=i;while(p>=0&&p!==joint)p=parents[p];return p===joint?i:-1;}).filter(i=>i>=0));
 const turnBranch=(pose,joint,turn)=>{
  const q=joints.project(joint,pose.q[parents[joint]],qm(turn,pose.q[joint]),false).q,delta=qm(q,qinv(pose.q[joint])),pivot=pose.points[joint];
  for(const i of descendants[joint]){if(i!==joint)pose.points[i]=add(pivot,rotate(delta,sub(pose.points[i],pivot)));pose.q[i]=qm(delta,pose.q[i]);pose.axes[i]=R.toAxes(pose.q[i]);}
 };
 let entry=null;
 // The slide solver repeatedly queries the same two shoe boxes. Construct
 // their corners without map/flatMap and temporary vectors at each corner;
 // dimensions and arithmetic order match support.js:footPoints.
 const shoeCorners=(p,l,rotation)=>{
  const shaped=shoePose(p,l,p.points[l.foot],rotation),f=S.footFrame(shaped,l.foot,l.toe,l.side),delta=sub(shaped.points[l.toe],shaped.points[l.foot]),out=[];
  const box=(c,forward,side,up,size)=>{for(const x of [-1,1])for(const y of [-1,1])for(const z of [-1,1]){
   const a=x*size[0]/2,b=y*size[1]/2,d=z*size[2]/2;
   out.push([((c[0]+forward[0]*a)+side[0]*b)+up[0]*d,((c[1]+forward[1]*a)+side[1]*b)+up[1]*d,((c[2]+forward[2]*a)+side[2]*b)+up[2]*d]);
  }};
  box(add(add(delta,mul(f.forward,-.0875)),mul(f.up,-.006)),f.forward,f.side,f.up,[.175,.120,.051]);
  box(add(add(delta,mul(f.toeForward,.024)),mul(f.toeUp,-.006)),f.toeForward,f.toeSide,f.toeUp,[.048,.120,.049]);
  return out;
 };
 const lowestCorner=(corners,n)=>{let height=Infinity;for(const c of corners)height=Math.min(height,dot(c,n));let total=[0,0,0],count=0;for(const c of corners)if(dot(c,n)<height+1e-8){total=add(total,c);count++;}return mul(total,1/count);};
 const tangent=(v,n)=>sub(v,mul(n,dot(v,n)));
 const kneeSolve=(p,l,target,rotation,n,weight)=>{
  const axis=unit(sub(target,p.points[l.hip])),pole=unit(tangent(n,axis)),inverse=qinv(p.q[pelvis]);
  p=K.solve(p,{...l,axisLocal:rotate(inverse,axis),poleLocal:rotate(inverse,pole)},target,parents,rotation,true);
  // A catch changes hip flexion. Accommodate it with the nearest legal knee
  // swivel around the hip-to-ankle axis, retaining the signed hinge and the
  // actual wall target. Projecting the thigh alone would dislocate the ankle.
  const swivel=weight?joints.feasibleSwivel(l.hip,p.q[parents[l.hip]],p.q[l.hip],axis,pole,pole)*weight:0;
  if(Math.abs(swivel)>1e-10){const turn=R.qexp(mul(axis,swivel));p.points[l.knee]=add(p.points[l.hip],rotate(turn,sub(p.points[l.knee],p.points[l.hip])));for(const j of [l.hip,l.knee]){p.q[j]=qm(turn,p.q[j]);p.axes[j]=R.toAxes(p.q[j]);}}
  return p;
 };
 const spring=(state,target,frequency,damping,dt)=>{state.v=add(state.v,mul(sub(mul(sub(target,state.x),frequency*frequency),mul(state.v,2*damping*frequency)),dt));state.x=add(state.x,mul(state.v,dt));return state.x;};
 // Three compliant contact particles, in the surface tangent plane. Coulomb
 // drag opposes their absolute slip, while the limb's tether recovers toward
 // its nominal pose. Independent rough patches produce catches and recovery,
 // not position noise or a synchronized loop. This is visual compliance only:
 // no reaction force is fed into the deliberately ballistic root.
 const hash=x=>{const v=Math.sin(x*127.1+311.7)*43758.5453;return v-Math.floor(v);};
 const upperNoise=(time,seed)=>{const cell=Math.floor(time),x=time-cell,w=x*x*x*(10+x*(-15+6*x));return (hash(cell+seed)*(1-w)+hash(cell+seed+1)*w)*2-1;};
 const contactState=seed=>({x:[0,0,0],v:[0,0,0],phase:seed,grip:0,force:[0,0,0]});
 function dragContact(state,velocity,normal,dt,active,amount=1){
  if(dt<=0)return state.x;
  const carrier=tangent(velocity,normal),speed=length(carrier);
  // Spatial variation is band-limited: high fall speed must not turn wall
  // texture into frame-to-frame jitter. At rest there is no clock-driven dance.
  state.phase+=Math.min(speed,5)*dt/(3.1*(.7+.6*hash(Math.floor(state.phase)+71)));
  const cell=Math.floor(state.phase),f=state.phase-cell;
  // Rough patches have a smooth leading edge AND an exit. Unbounded runs of
  // similar random values would hold a displaced foot motionless for seconds.
  const release=.40+.18*hash(cell+19),rough=(.55+.45*hash(cell))*smooth(f/.22)*(1-smooth((f-release)/(.94-release)));
  const requested=active?rough:0;
  state.grip+=(requested-state.grip)*(1-Math.exp(-dt*18));
  // Match damping to the progressive spring's actual stiffness. Large catches
  // previously stored a much stiffer spring with unchanged damping, then
  // snapped back in roughly a tenth of a second when the patch released.
  const frequency=9,recovery=(s.slideRecovery??100)/100;
  const stiffnessAt=()=>1+3*(length(state.x)/.20)**4;
  // Keep pull proportional to displacement (with a progressive stretch guard).
  // Slow recovery adds damping, rather than softening the spring and storing a
  // larger catch that would then paradoxically return faster. The 100% default
  // is the existing integration. Substeps keep high damping stable at 10%.
  const stiffness=stiffnessAt(),damping=2*1.05*frequency*Math.sqrt(stiffness)/recovery;
  const steps=Math.max(1,Math.ceil(damping*dt/.35),Math.ceil(frequency*Math.sqrt(stiffness)*dt/.2)),h=dt/steps;
  const friction=active?amount*(s.slideFriction??100)/100*(1.2+31*state.grip)*smooth(speed/.25):0;
  for(let step=0;step<steps;step++){
  const stiffness=stiffnessAt(),elastic=mul(state.x,-frequency*frequency*stiffness);
  const acceleration=sub(elastic,mul(state.v,2*1.05*frequency*Math.sqrt(stiffness)/recovery));
  const freeVelocity=add(carrier,add(state.v,mul(acceleration,h)));
  // The impulse cannot reverse absolute slip by itself (static friction at
  // low speed). Spring release can overshoot, giving a small natural recoil.
  state.force=mul(unit(freeVelocity),-Math.min(friction,length(freeVelocity)/h));
  state.v=tangent(add(state.v,mul(add(acceleration,state.force),h)),normal);
  state.x=tangent(add(state.x,mul(state.v,h)),normal);
  }
  return state.x;
 }
 const limitedRotation=(p,l,desired)=>{
  // A sliding foot need not lie flush against the wall. Prefer the relaxed
  // calf-relative ankle and only modestly bias toward the surface; the sole
  // clearance fit can use its heel/toe/edge without rearranging the knee pole.
  const relaxed=qm(p.q[l.knee],joints.joints[l.foot].refRelative);
  // Follow the calf's neutral ankle; a projected 180-degree absolute shoe
  // rotation has two branches and used to flip even for tiny hip changes.
  const toe=qm(relaxed,joints.joints[l.toe].refRelative);
  return {footQ:relaxed,toeQ:toe};
 };
 const copyPose=p=>({...p,points:p.points.slice(),q:p.q.slice(),axes:p.axes.slice()});
 // A maximum offset is a target request, not permission to violate a joint.
 // Retain the original bend branch while finding the reachable portion of it.
 function reachableShift(targetShift,build,valid){
  const distance=length(targetShift);if(distance<1e-10)return build(0);
  const margin=.03/distance,base=build(0,true),end=1+2*margin,steps=Math.ceil((distance+.06)/.04);
  const feasible=t=>valid(build(t,true),base)||valid(build(t),base);
  let lo=0,hi=end;
  // Stay in the connected reachable interval starting at the original pose;
  // a much higher target can become feasible again across an inverted branch.
  for(let i=1;i<=steps;i++){const t=end*i/steps;if(!feasible(t)){hi=t;break;}lo=t;}
  if(lo===end){const result=build(1);if(valid(result,base))return result;lo=0;}
  for(let i=0;i<9;i++){const t=(lo+hi)*.5;if(feasible(t))lo=t;else hi=t;}
  // Ease into the anatomical boundary instead of sitting exactly on its
  // swivel singularity. This soft minimum is continuous as speed changes.
  const allowed=Math.max(0,lo-margin),h=Math.max(margin-Math.abs(1-allowed),0)/margin;
  let amount=Math.max(0,Math.min(1,allowed)-h*h*margin/4);
  const exact=build(amount);if(valid(exact,base))return exact;
  // The probe uses fewer contact iterations. If its final candidate fails the
  // exact solve, find the boundary rather than dropping the requested shift
  // by half in one frame. Only this uncommon fallback incurs exact refinement.
  let left=0,right=amount,best=build(0);
  if(!valid(best,base))return best;
  for(let i=0;i<10;i++){const mid=(left+right)*.5,p=build(mid);if(valid(p,base)){left=mid;best=p;}else right=mid;}
  return best;
 }
 function legReference(u){
  const local={p:entry.local.p.slice(),q:entry.local.q.slice()};
  for(const l of entry.legs){
   local.q[l.knee]=qslerp(local.q[l.knee],referenceLocal.q[l.knee],u);
   for(const j of [l.knee,l.foot,l.toe])local.p[j]=mul(unit(add(mul(unit(local.p[j]),1-u),mul(unit(referenceLocal.p[j]),u))),length(local.p[j]));
  }
  return R.fk(local,parents);
 }
 // Alternate reach and joint-space limits. Contact is the lowest actual shoe
 // point, so an ankle at its limit may use its heel/toe instead of being forced flat.
 function contactLeg(p,l,wanted,desired,pole,plane,contactWeight=1,reachRatio=.985,localRotation=null,limitHip=true,iterations=14){
  let rotation=desired,target=wanted;
  const initialAxis=unit(sub(wanted,p.points[l.hip])),initialPole=unit(tangent(pole,initialAxis));
  const solve=()=>kneeSolve(p,l,target,rotation,rotate(R.fromTo(initialAxis,unit(sub(target,p.points[l.hip]))),initialPole),limitHip?contactWeight:0);
  const ankle=()=>{
   if(!localRotation)return limitedRotation(p,l,desired);
   const requested=qm(p.q[l.knee],localRotation.footQ),footQ=qslerp(requested,joints.project(l.foot,p.q[l.knee],requested,false).q,contactWeight);
   const toe=qm(footQ,localRotation.toeQ);
   return {footQ,toeQ:qslerp(toe,joints.project(l.toe,footQ,toe,false).q,contactWeight)};
  };
  for(let k=0;k<iterations;k++){
   p=solve();
   rotation=ankle();
   const corners=shoeCorners(p,l,rotation),offset=lowestCorner(corners,plane.normal),fitted=sub(plane.closest(add(wanted,offset)),offset);
   const gap=dot(sub(wanted,fitted),plane.normal),capture=contactWeight*(1-smooth(Math.max(0,gap)/.06));
   // Contact fitting owns only normal clearance. Tangential placement belongs
   // to the limb/friction trajectory, not to a demand for a flat shoe.
   const candidate=add(wanted,mul(plane.normal,dot(sub(fitted,wanted),plane.normal)*capture));
   const safe=constrain(p,l,candidate,rotation,terrain.surfaces,reachRatio,corners);
   const error=length(sub(safe,target));target=safe;
   if(k>1&&error<1e-7)break;
  }
  p=solve();rotation=ankle();
  return shoePose(p,l,p.points[l.foot],rotation);
 }
 function step(context,initial,previous){
  if(!entry){
   const surface=terrain.allSurfaces.find(p=>p.id===context.slide.surface),n=surface.normal,w=unit(tangent(up,n)),side=unit(cross(w,n));
   const near=arms.reduce((a,b)=>length(sub(initial.points[a.c],surface.closest(initial.points[a.c])))<=length(sub(initial.points[b.c],surface.closest(initial.points[b.c])))?a:b),sign=near.side==='l'?1:-1;
   const bodyUp=unit(add(w,mul(n,-.16*dot(context.heading,n)**2))),forward=unit(tangent(context.heading,bodyUp));
   const desired=R.fromAxes([bodyUp,mul(forward,-1),cross(bodyUp,mul(forward,-1))]),turn=qm(desired,qinv(initial.q[pelvis]));
   // Explicit slide-only closeness, blended by the same local pose transition.
   // Keep a torso clearance; root inertia and gravity remain unchanged.
   const origin=initial.points[pelvis],distance=dot(sub(origin,surface.closest(origin)),n);
   const shift=mul(n,-Math.min((s.slideCloser||0)/100,Math.max(0,distance-.15)));
   const points=initial.points.map((v,i)=>i?add(add(origin,shift),rotate(turn,sub(v,origin))):v),q=initial.q.map((v,i)=>i?qm(turn,v):v);
   const local=R.localize(points,q,parents);for(let i=0;i<names.length;i++)if(/^(spine_|clavicle_|neck_|head)/.test(names[i]))local.q[i]=referenceLocal.q[i];
   const far=arms.find(a=>a!==near),handVelocity=previous?mul(sub(sub(initial.points[far.c],initial.points[far.a]),sub(previous.points[far.c],previous.points[far.a])),120):[0,0,0];
   const angularVelocity=previous?mul(R.qlog(qm(initial.q[pelvis],qinv(previous.q[pelvis]))),120):[0,0,0];
   entry={pose:initial,local:R.localize(initial.points,initial.q,parents),legs:['L','R'].map(side=>S.leg(initial,names,side)),root:context.base.slice(),goal:R.fk(local,parents),surface,n,w,side,near,far,sign,forward,initialForward:forward,desiredQ:desired,
    lastTime:context.time,body:{x:[0,0,0],v:bounded(angularVelocity,.5)},torso:{x:[0,0,0],v:[0,0,0]},free:{x:[0,0,0],v:bounded(mul(handVelocity,.4),.5)},
    drag:{L:contactState(2.21),R:contactState(17.63),hand:contactState(39.08)}};
   entry.legReference=legReference(1);
  }
  const e=entry,delta=sub(context.base,e.root),carry=p=>({...p,points:p.points.map(v=>add(v,delta))});
  const elapsed=context.time-context.slide.time,dt=context.time-e.lastTime;e.lastTime=context.time;
  const wall=terrain.surfaces.find(p=>p.id===e.surface.id),plane=e.surface,targets=[];
  // A very low speed threshold can otherwise move the target its entire
  // range in one tick when vertical velocity passes through zero at the apex.
  function advanceShift(part){
   const requested=slideTargetShift(e.n,context.velocity,s,part);e.shifts||={};
   const motion=e.shifts[part]||={x:requested,v:[0,0,0],previous:null};
   const target=spring(motion,requested,10,1,dt),velocity=dt>0&&motion.previous?mul(sub(target,motion.previous),1/dt):[0,0,0];
   motion.previous=target;return {target,velocity};
  }
  const feetShift=advanceShift('feet'),handShift=advanceShift('hand'),targetShift=feetShift.target;
  // Friction sees the moving neutral target as well as the ballistic carrier.
  // Do not turn the first offset into an impulse; the pose's entry blend owns it.
  for(const [key,state] of Object.entries(e.drag))dragContact(state,add(context.velocity,(key==='hand'?handShift:feetShift).velocity),e.n,dt,!!wall&&(state.touching??true),key==='hand'?.8:1);
  const mean=mul(add(e.drag.L.x,e.drag.R.x),.5),difference=dot(sub(e.drag.L.x,e.drag.R.x),e.w),palmLag=dot(e.drag.hand.x,e.w);
  // Differential contact tension rocks the torso. The free arm trails that
  // acceleration rather than being the only independently animated limb.
  const balance=add(mul(e.side,clamp(dot(mean,e.w)*.55-palmLag*.3,-.10,.10)),mul(e.n,clamp(difference*.8,-.10,.10)));
  const oldBodyVelocity=e.body.v.slice(),body=spring(e.body,balance,9,.6,dt);
  const bodyAcceleration=dt>0?mul(sub(e.body.v,oldBodyVelocity),1/dt):[0,0,0];
  if(dt>0)e.free.v=add(e.free.v,mul(cross(bodyAcceleration,mul(up,.4)),dt*.35));
  const free=spring(e.free,mul(add(mean,e.drag.hand.x),-.18),6,.3,dt);
  const start=carry(e.pose);let goal=carry(e.goal);
  const slideUp=unit(add(e.w,mul(e.n,-.16*dot(context.heading,e.n)**2))),forward=unit(tangent(context.heading,slideUp));
  e.forward=forward;
  const facingQ=R.fromAxes([slideUp,mul(forward,-1),cross(slideUp,mul(forward,-1))]);
  const pivot=goal.points[pelvis],turn=qm(R.qexp(body),qm(facingQ,qinv(e.desiredQ)));
  goal={...goal,points:goal.points.map((v,i)=>i?add(pivot,rotate(turn,sub(v,pivot))):v),q:goal.q.map((v,i)=>i?qm(turn,v):v)};goal.axes=goal.q.map(R.toAxes);
  // The entry corridor ends under the future pelvis heading. Author its fixed
  // local leg destination there, rather than turning an initial-facing contact
  // away from the wall for the entire blend and repairing it afterwards.
  let legForward=forward,legUp=slideUp,entryTurn=null;
  if(!e.entryLegLocal){
   const command=context.headingAt(context.time+s.slideLegBlend);
   legUp=unit(add(e.w,mul(e.n,-.16*dot(command,e.n)**2)));legForward=unit(tangent(command,legUp));
   const futureQ=R.fromAxes([legUp,mul(legForward,-1),cross(legUp,mul(legForward,-1))]);
   entryTurn=qm(futureQ,qinv(facingQ));
   goal={...goal,points:goal.points.map((v,i)=>i?add(pivot,rotate(entryTurn,sub(v,pivot))):v),q:goal.q.map((v,i)=>i?qm(entryTurn,v):v)};goal.axes=goal.q.map(R.toAxes);
  }
  for(const side of ['L','R']){
   const l=S.leg(e.legReference,names,side),front=(1-dot(legForward,e.n))*.5;
   const right=unit(cross(legUp,legForward)),nearAmount=(1+(side==='R'?1:-1)*dot(right,mul(e.n,-1)))*.5;
   const drop=(.70-.25*nearAmount)*(1-front)+(.82-.12*nearAmount)*front;
   const heading=unit(add(mul(e.side,dot(legForward,e.side)*.35),e.w));
   const point=add(add(plane.project(goal.points[l.hip]),mul(e.w,-l.reach*drop)),e.drag[side].x),rotation=footRotation(goal,l,e.n,heading);
   const bend=p=>{const axis=unit(sub(p.points[l.foot],p.points[l.hip]));return unit(tangent(sub(p.points[l.knee],p.points[l.hip]),axis));};
   const wantedAxis=unit(sub(point,goal.points[l.hip]));e.poles||={};const previousPole=e.poles[side];
   let wantedPole=unit(tangent(legForward,wantedAxis));
   if(previousPole){const transported=rotate(R.fromTo(previousPole.axis,wantedAxis),previousPole.pole),angle=Math.acos(clamp(dot(transported,wantedPole),-1,1));
    wantedPole=rotate(qslerp([0,0,0,1],R.fromTo(transported,wantedPole),angle>1e-8?Math.min(1,dt*4/angle):1),transported);}
   // A sole can touch while its knee capsule intersects the wall. Find the
   // nearest lower contact in that case, instead of letting clearance later
   // pull the whole shoe away from an otherwise reachable surface.
   const contactValid=p=>{
    const kneeGap=dot(sub(p.points[l.knee],plane.project(p.points[l.knee])),e.n);
    const shoe=add(p.points[l.foot],sole(p,l,e.n)),gap=dot(sub(shoe,plane.project(shoe)),e.n);
    if(kneeGap<.086||Math.abs(gap)>=.003||penetration(p,l,terrain.surfaces)>.001)return false;
    if(previousPole){const axis=unit(sub(p.points[l.foot],p.points[l.hip])),transported=rotate(R.fromTo(previousPole.axis,axis),previousPole.pole);
     if(dot(bend(p),transported)<.98)return false;
    }
    for(const surface of terrain.surfaces){const at=surface.local(p.points[l.knee]),[x0,x1,z0,z1]=surface.bounds;
     if(surface.finiteSlab&&at[1]<-surface.box.dims[1]-.04)continue;
     if(at[0]>=x0&&at[0]<=x1&&at[2]>=z0&&at[2]<=z1&&at[1]<.086)return false;
    }
    return [l.hip,l.knee,l.foot,l.toe].every(j=>joints.diagnose(j,p.q[parents[j]],p.q[j]).withinLimits);
   };
   const lowered=amount=>{
    const wanted=sub(point,mul(e.w,amount)),axis=unit(sub(wanted,goal.points[l.hip]));
    return contactLeg(copyPose(goal),l,wanted,rotation,rotate(R.fromTo(wantedAxis,axis),wantedPole),plane);
   };
   let neutral=lowered(0),lower=0;e.contactDrop||={};const previousDrop=e.contactDrop[side];
   if(!contactValid(neutral)){
    let lo=0,hi=0,best=null;
    if(previousDrop){const candidate=lowered(previousDrop);if(contactValid(candidate)){hi=previousDrop;best=candidate;}}
    if(!best)for(let i=1;i<=16;i++){
     const amount=l.reach*i/24;
     // Prefer lowering for knee clearance; the opposite direction remains
     // available at a wall/floor corner where the shoe cannot descend.
     for(const sign of[1,-1]){const candidate=lowered(amount*sign);if(contactValid(candidate)){hi=amount*sign;lo=l.reach*(i-1)/24*sign;best=candidate;break;}}
     if(best)break;
    }
    if(best){for(let i=0;i<5;i++){const mid=(lo+hi)*.5,candidate=lowered(mid);if(contactValid(candidate)){hi=mid;best=candidate;}else lo=mid;}
     neutral=best;lower=hi;}
   }
   // Retire an extra clearance offset gradually when it becomes unnecessary.
   // Feasibility always wins over smoothing, so this cannot reinsert a knee
   // into the wall while the character turns or crosses a floor edge.
   if(Number.isFinite(previousDrop)&&dt>0&&contactValid(neutral)){
    const eased=previousDrop+clamp(lower-previousDrop,-dt*.45,dt*.45),candidate=lowered(eased);
    if(contactValid(candidate)){neutral=candidate;lower=eased;}
   }
   e.contactDrop[side]=lower;
   const contactPoint=sub(point,mul(e.w,lower)),neutralAxis=unit(sub(neutral.points[l.foot],neutral.points[l.hip])),neutralPole=bend(neutral);
   goal=reachableShift(targetShift,(t,probe)=>{
    if(t===0)return neutral;
    const wanted=add(contactPoint,mul(targetShift,t)),pole=rotate(R.fromTo(neutralAxis,unit(sub(wanted,neutral.points[l.hip]))),neutralPole);
    return contactLeg(copyPose(neutral),l,wanted,rotation,pole,plane,1,.985,null,true,probe?3:14);
   },(p,base)=>
    contactValid(p)&&dot(bend(p),bend(base))>.1);
   // The feasible amount of an upward speed/friction shift can change as a
   // knee swivels. Continue the material contact along the wall instead of
   // handing a suddenly reachable high target to a joint-space chase.
   e.contactTravel||={};const wantedTravel=dot(sub(goal.points[l.foot],goal.points[l.hip]),e.w),lastTravel=e.contactTravel[side];
   if(Number.isFinite(lastTravel)&&dt>0&&contactValid(goal)){
    const travel=lastTravel+clamp(wantedTravel-lastTravel,-dt*.8,dt*.8);
    if(Math.abs(travel-wantedTravel)>1e-8){
     const target=add(goal.points[l.foot],mul(e.w,travel-wantedTravel)),axis=unit(sub(target,neutral.points[l.hip]));
     const candidate=contactLeg(copyPose(neutral),l,target,rotation,rotate(R.fromTo(neutralAxis,axis),neutralPole),plane);
     if(contactValid(candidate))goal=candidate;
     else{
      const heldTarget=add(goal.points[l.foot],mul(e.w,lastTravel-wantedTravel)),heldAxis=unit(sub(heldTarget,neutral.points[l.hip]));
      const held=contactLeg(copyPose(neutral),l,heldTarget,rotation,rotate(R.fromTo(neutralAxis,heldAxis),neutralPole),plane);
      if(contactValid(held))goal=held;
      else if(contactValid(neutral))goal=neutral;
     }
    }
   }
   e.contactTravel[side]=dot(sub(goal.points[l.foot],goal.points[l.hip]),e.w);
   e.poles[side]={axis:unit(sub(goal.points[l.foot],goal.points[l.hip])),pole:bend(goal)};
   targets.push({side,l,target:goal.points[l.foot],rotation:{footQ:goal.q[l.foot],toeQ:goal.q[l.toe]}});
  }
  if(entryTurn){
   const undo=qinv(entryTurn);goal={...goal,points:goal.points.map((v,i)=>i?add(pivot,rotate(undo,sub(v,pivot))):v),q:goal.q.map((v,i)=>i?qm(undo,v):v)};goal.axes=goal.q.map(R.toAxes);
   for(const target of targets){const l=target.l;target.target=goal.points[l.foot];target.rotation={footQ:goal.q[l.foot],toeQ:goal.q[l.toe]};}
  }
  // Keep pelvis/legs and the material brace target out of the torso gesture.
  // Irregular, band-limited corrections bend the spine, with a damped response
  // instead of independent frame noise. Axes are authored in the pelvis frame.
  const requestedTorso=mul([upperNoise(elapsed*.9,401)*.08,upperNoise(elapsed*1.35,457)*.12,upperNoise(elapsed*1.1,503)*.14],smooth(elapsed/.5));
  const torso=spring(e.torso,requestedTorso,12,.85,dt),torsoWorld=rotate(goal.q[pelvis],torso);
  const spineWeights=[.12,.17,.22,.25,.24];
  for(let i=0;i<spine.length;i++)turnBranch(goal,spine[i],R.qexp(mul(torsoWorld,spineWeights[i])));
  // Speed-based gaze begins at the slide's entry speed and reaches 70% toward
  // absolute down at the chosen head speed, independently of the feet shift.
  // Distribute it through
  // both neck joints and the head, retaining their actual joint limits.
  const entrySpeed=length(context.slide.velocity),maxSpeed=s.slideHeadSpeed??30,speed=length(context.velocity);
  const gaze=.7*smooth(maxSpeed>entrySpeed?(speed-entrySpeed)/(maxSpeed-entrySpeed):speed/maxSpeed)*smooth(elapsed/.65);
  const look=mul(R.qlog(R.fromTo(rotate(goal.q[neck[2]],[0,-1,0]),mul(up,-1))),gaze);
  for(let i=0;i<neck.length;i++)turnBranch(goal,neck[i],R.qexp(mul(look,[.3,.35,.35][i])));
  const armResult=slideArms.step({pose:goal,normal:e.n,up,side:e.side,forward,plane,elapsed,dt,velocity:context.velocity,handShift:handShift.target,frictionOffset:e.drag.hand.x,freeOffset:free,balanceTime:slideBalanceTime});
  goal=armResult.pose;
  const a=R.localize(start.points,start.q,parents),b=R.localize(goal.points,goal.q,parents);
  for(const {l} of targets)for(const j of [l.hip,l.knee,l.foot,l.toe])b.q[j]=joints.project(j,[0,0,0,1],b.q[j],false).q;
  // Keep a moving contact target from switching IK swivel branches in one tick.
  // This is a bounded joint-space pursuit; the clearance solver follows below.
  e.legGoalQ||=b.q.map(q=>q.slice());
  for(const {l} of targets)for(const j of [l.hip,l.knee,l.foot,l.toe]){
   const angle=length(R.qlog(qm(b.q[j],qinv(e.legGoalQ[j])))),amount=dt>0?Math.min(1,dt*4/Math.max(angle,1e-8)):1;
   b.q[j]=joints.blendLocal(j,e.legGoalQ[j],b.q[j],amount);e.legGoalQ[j]=b.q[j];}
  const legDuration=s.slideLegBlend,bodyU=smooth(elapsed/s.slideBlend),pelvisU=smooth(elapsed/s.slidePelvisBlend);
  // Keep the entry corridor's destination in joint space stable while the
  // pelvis turns. Moving friction/shift targets take over smoothly afterwards.
  e.entryLegLocal||={p:b.p.map(v=>v.slice()),q:b.q.map(v=>v.slice())};
  const follow=smooth((elapsed-legDuration)/.3);
  for(const {l} of targets){for(const j of [l.hip,l.knee,l.foot,l.toe])b.q[j]=joints.blendLocal(j,e.entryLegLocal.q[j],b.q[j],follow);
   for(const j of [l.knee,l.foot,l.toe])b.p[j]=R.offsetBlend(e.entryLegLocal.p[j],b.p[j],follow);}
  if(!e.legPlans){
   const forecast=context.forecast(Math.ceil(legDuration*120));
   const inverseSmooth=y=>{let lo=0,hi=1;for(let k=0;k<24;k++){const mid=(lo+hi)*.5;if(smooth(mid)<y)lo=mid;else hi=mid;}return(lo+hi)*.5;};
   const poseAt=(progress,local)=>{local={p:local.p.slice(),q:local.q.slice()};
    const futureCommand=context.headingAt(context.time+inverseSmooth(progress)*legDuration),futureUp=unit(add(e.w,mul(e.n,-.16*dot(futureCommand,e.n)**2))),futureHeading=unit(tangent(futureCommand,futureUp));
    const futureQ=R.fromAxes([futureUp,mul(futureHeading,-1),cross(futureUp,mul(futureHeading,-1))]);
    const parent=R.fk(local,parents).q[parents[pelvis]],residual=qm(qinv(e.desiredQ),e.pose.q[pelvis]);
    local.q[pelvis]=qm(qinv(parent),qm(futureQ,qslerp(residual,[0,0,0,1],smooth(inverseSmooth(progress)*legDuration/s.slidePelvisBlend))));
    const pose=R.fk(local,parents),tick=inverseSmooth(progress)*legDuration*120,i=Math.min(forecast.length-2,Math.floor(tick)),t=tick-i;
    const future=add(forecast[i].base,mul(sub(forecast[i+1].base,forecast[i].base),t)),delta=sub(future,context.base);
    pose.points=pose.points.map(v=>add(v,delta));return pose;};
   const bodyProgress=progress=>smooth(inverseSmooth(progress)*legDuration/s.slideBlend),pelvisProgress=progress=>smooth(inverseSmooth(progress)*legDuration/s.slidePelvisBlend);
   const surfacesAt=(progress,live)=>live?terrain.surfaces:terrain.surfacesAt(context.time+inverseSmooth(progress)*legDuration);
   e.legPlans=targets.map(({l})=>E.create({a,b,leg:l,parents,joints,surfaces:surfacesAt,poseAt,bodyProgress,pelvis,pelvisProgress}));
   const score=plans=>Math.max(...plans.map(p=>{const d=p.diagnostics;return d.worst&&d.worst.u<.95?d.maxPenetration:0;}));
   if(score(e.legPlans)>.008){const leading=targets.map(({l})=>E.create({a,b,leg:l,parents,joints,surfaces:surfacesAt,poseAt,bodyProgress,pelvis,pelvisProgress,bodyExponent:4}));if(score(leading)<score(e.legPlans)){e.legPlans=leading;e.bodyExponent=4;}}

  }
  const u=smooth(elapsed/legDuration);
  const local={p:a.p.map((v,i)=>add(v,mul(sub(b.p[i],v),bodyU))),q:a.q.map((v,i)=>qslerp(v,b.q[i],1-(1-bodyU)**(e.bodyExponent||1)))};
  local.p[pelvis]=add(a.p[pelvis],mul(sub(b.p[pelvis],a.p[pelvis]),pelvisU));
  const parentQ=start.q[parents[pelvis]],residual=qm(qinv(e.desiredQ),e.pose.q[pelvis]);
  local.q[pelvis]=qm(qinv(parentQ),qm(goal.q[pelvis],qslerp(residual,[0,0,0,1],pelvisU)));
  for(const {l} of targets){
   for(const j of [l.hip,l.knee,l.foot,l.toe])local.q[j]=joints.blendLocal(j,a.q[j],b.q[j],u);
   for(const j of [l.knee,l.foot,l.toe])local.p[j]=R.offsetBlend(a.p[j],b.p[j],u);
  }
  for(const plan of e.legPlans)plan.sample(u,local);
  let pose=R.fk(local,parents);const feet=[];
  // The free leg follows the constrained FK path until entry is complete;
  // only then does wall contact own its ankle target again.
  for(const target of targets){
   const l={...target.l};
   const actual=pose.points[l.foot],contactPoint=plane.closest(add(actual,sole(pose,l,e.n))),gap=dot(sub(add(actual,sole(pose,l,e.n)),contactPoint),e.n);
   const touching=!!wall&&Math.abs(gap)<.004;
   e.drag[target.side].touching=touching;
   feet.push({side:target.side,state:touching?'SLIDE':'REACH',target:actual,contact:null,slideContact:touching?{point:contactPoint,surface:plane.id,normal:e.n}:null,error:length(sub(actual,target.target)),penetration:penetration(pose,l,terrain.surfaces),soleGap:gap});
  }
  // Blend the incoming NN's local joints into the hinge-valid goal. Some source
  // poses already have off-axis elbow rotation; hard-projecting the first
  // transition frame would snap instead of respecting the chosen blend time.
  if(wall)pose=slideArms.clear(pose,plane,dt);
  const hands=armResult.hands.map(h=>{const {point,gap}=slideArms.contact(pose,h.side,plane);
   return {...h,point,gap,touching:!!wall&&h.weight>.9&&gap<.004};});
  const hand=hands.reduce((a,b)=>a.weight>=b.weight?a:b);e.drag.hand.touching=hands.some(h=>h.touching);
  return {pose,feet,hand,hands,blend:bodyU,legBlend:u,pelvisBlend:pelvisU,commandedHeading:context.heading,heading:unit(rotate(pose.q[pelvis],[0,-1,0]))};
 }
 return {step};
}
function* simulate(run,input={},experiment={}){
 const s=settings(input),fps=120,dt=1/fps,duration=run.totalDuration??run.directionMeta?.totalDuration??run.duration,count=Math.round(duration*fps)+1,{names,parents}=run,pelvis=names.indexOf('pelvis');
 const origin=run.poses[0].points[0],rawAt=i=>{const p=K.at(run,i/fps);return {...p,points:p.points.map(v=>sub(v,[origin[0],0,origin[2]]))};};
 // Interactive policy steps provide their own pose/contact intent. Do not
 // pre-solve a five-second limb trajectory merely to initialize this generator.
 // A bounded NN seed supplies fixed calibration independent of the trim end.
 const referenceHeight=run.referenceHeight??run.directionMeta?.referenceHeight;
 const speed=Number.isFinite(referenceHeight)?run.directionMeta.commandSpeed:length(sub(rawAt(Math.round(run.duration*fps)).points[0],rawAt(0).points[0]))/run.duration;
 const raw=experiment.interactive?null:Array.from({length:count},(_,i)=>rawAt(i));
 const legs=raw?.map(p=>['L','R'].map(side=>K.stableLeg(p,names,side))),flags=raw?intent(run,raw,legs,fps,speed):null;
 // Legacy full clips retain their previous exact calibration. New bounded
 // sources never visit poses past the seed to calculate it.
 const height=Number.isFinite(referenceHeight)?referenceHeight:(raw||Array.from({length:count},(_,i)=>rawAt(i))).reduce((sum,p)=>sum+p.points[pelvis][1]-p.points[0][1],0)/count;
 const gravity=experiment.gravity??9.81,enabled=experiment.support!==false&&s.enabled;
 // Cover the whole recorded flight in both plane directions, including a
 // five-second fall below the original floor, without another user setting.
 const terrain=createTerrain(s,Math.max(28,speed*duration+.5*Math.abs(gravity)*duration**2+2*height)),steep=terrain.slope.normal[1]<.45;
 const untilPlant=flags?.map(list=>{let next=Infinity;const result=[];for(let i=count-1;i>=0;i--){if(list[i])next=i;result[i]=(next-i)/fps;}return result;});
 const frames=[];let lastSupports=[];
 const metrics=createMetrics(),footSolver=createFeet({names,parents,terrain,settings:s,metrics}),events=footSolver.events;
 const motion=createRootMotion({s,terrain,height,speed,gravity,enabled,metrics,events});let slidePose=null,returnPose=null,pelvisPull=null;
 const model={frames,terrain,settings:s,metrics,events,speed,duration,fps,surfacePrototype:true,generatedThrough:-1/fps,sample:t=>frames[clamp(Math.round(t*fps),0,frames.length-1)]};
 experiment.onModel?.(model);
 for(let i=0;i<count;i++){
  const time=i/fps,context=motion.begin(time),{base,rootQ,bodyUp,surfaceQ,normal,velocity,useEdited,nextSurface}=context;
  const command=experiment.interactive?yield {i,time,...context,forecast:ticks=>motion.forecast(context,lastSupports,ticks)}:null;
  const p=command?.pose||raw?.[i]||rawAt(i);
  const transform=q=>{const points=p.points.map(v=>add(base,rotate(q,sub(v,p.points[0])))),quats=p.q.map(v=>qm(q,v));return {points,q:quats,axes:quats.map(R.toAxes)};};
  const terrainPose=transform(surfaceQ),pelvisPosition=terrainPose.points[pelvis];
  // NN translations and lower articulation share the surface's ground frame.
  // Upright changes body posture about the pelvis, not the standing height.
  const points=p.points.map(v=>add(pelvisPosition,rotate(rootQ,sub(v,p.points[pelvis])))),quats=p.q.map(v=>qm(rootQ,v));
  points[0]=base;
  for(const side of ['L','R']){const l=K.stableLeg(p,names,side),hip=points[l.hip];
   for(const j of [l.hip,l.knee,l.foot,l.toe]){if(j!==l.hip)points[j]=add(hip,sub(terrainPose.points[j],terrainPose.points[l.hip]));quats[j]=terrainPose.q[j];}
  }
  let pose={points,q:quats,axes:quats.map(R.toAxes)};const baseline=pose,feet=[],supports=[];
  const pinNormal=context.pinNormal,allowPins=pinsAllowed(pinNormal,velocity,s);
  const requestedCloser=enabled?pelvisCloser(normal,s,velocity):0;
  // Retain the authored approach, but release a close-wall pelvis smoothly.
  // Crossing the narrow dangerous-incline band must not withdraw the hip
  // thirteen centimetres in one tick while a foot still supports the body.
  const requestedPull=mul(normal,-requestedCloser);
  if(!pelvisPull||requestedCloser>=length(pelvisPull.x))pelvisPull={x:requestedPull,v:[0,0,0]};
  else{
   // Retain its world direction too: a wall pull must not become a downward
   // crouch just because the root has switched to the horizontal floor.
   const omega=20,decay=Math.exp(-omega*dt),offset=sub(pelvisPull.x,requestedPull),rate=add(pelvisPull.v,mul(offset,omega));
   pelvisPull.x=add(requestedPull,mul(add(offset,mul(rate,dt)),decay));pelvisPull.v=mul(sub(pelvisPull.v,mul(rate,omega*dt)),decay);
  }
  const closer=length(pelvisPull.x);
  let slideResult=null;
  if(slidePose&&!context.slide){
   const previous=frames.at(-1);returnPose={pose:previous.pose,root:previous.root,rotation:previous.surface.bodyRotation,time};
   slidePose=null;footSolver.reset();
  }
  if(!slidePose){const result=footSolver.step({baseline,terrainPose,source:p,sourceLegs:command?.legs||legs[i],stance:command?.stance||flags.map(x=>x[i]),untilPlant:command?.untilPlant||untilPlant.map(x=>x[i]),time,frame:i/2,normal,surfaceQ,height,velocity,terrainWeight:0,enabled,steep,allowPins:allowPins&&!returnPose,pelvisShift:closer>0?pelvisPull.x:null});pose=result.pose;feet.push(...result.feet);supports.push(...result.supports);}
  if(context.slide){
   let previousSlidePose=frames.at(-1)?.pose;
   if(!slidePose){
    slidePose=createSlidePose(names,parents,terrain,s);footSolver.reset();returnPose=null;
    // Releasing locomotion contacts must not author a different first slide
    // pose. Carry the last displayed articulation with this tick's root.
    const last=frames.at(-1);
    if(last){const delta=sub(base,last.root);pose={...last.pose,points:last.pose.points.map(v=>add(v,delta))};previousSlidePose=frames.at(-2)?.pose;}
   }
   slideResult=slidePose.step({...context,heading:K.rootHeading(run,time,s,speed),headingAt:t=>K.rootHeading(run,t,s,speed),forecast:ticks=>motion.forecast(context,[],ticks)},pose,previousSlidePose);pose=slideResult.pose;feet.splice(0,feet.length,...slideResult.feet);supports.length=0;
   metrics.slideFrames=(metrics.slideFrames||0)+1;metrics.slideHandFrames=(metrics.slideHandFrames||0)+(slideResult.hands.some(hand=>hand.touching)?1:0);
   const before=frames.at(-1)?.pose;
   for(const foot of feet){const l=S.leg(pose,names,foot.side);metrics.maxPenetration=Math.max(metrics.maxPenetration,foot.penetration);metrics.slideContactFrames=(metrics.slideContactFrames||0)+(foot.slideContact?1:0);
    if(before){const v=mul(sub(pose.points[l.foot],before.points[l.foot]),fps);metrics.maxFootSpeed=Math.max(metrics.maxFootSpeed,length(v));metrics.maxRelativeFootSpeed=Math.max(metrics.maxRelativeFootSpeed,length(sub(v,velocity)));
     for(const [j,key] of [[l.knee,'Knee'],[l.foot,'Ankle']]){const angle=length(R.qlog(qm(pose.q[j],qinv(before.q[j]))))*180/Math.PI;if(angle>metrics['max'+key+'Step']){metrics['max'+key+'Step']=angle;metrics['max'+key+'Frame']=i/2;metrics['max'+key+'Side']=foot.side;}}
    }
   }
  }

  if(returnPose&&!context.slide){
   // Blend out the slide after the gait solve, so its anatomical knee poles
   // cannot instantly replace the slide's different bend plane. Fresh pins
   // and traction wait until the displayed feet have completed this transition.
   const u=smooth((time-returnPose.time)/s.slideBlend),turn=qm(rootQ,qinv(returnPose.rotation));
   const from={points:returnPose.pose.points.map((v,j)=>j?add(base,rotate(turn,sub(v,returnPose.root))):base),q:returnPose.pose.q.map((q,j)=>j?qm(turn,q):pose.q[0])};
   const a=R.localize(from.points,from.q,parents),b=R.localize(pose.points,pose.q,parents);
   pose=R.fk({p:a.p.map((v,j)=>j?R.offsetBlend(v,b.p[j],u):base),q:a.q.map((q,j)=>R.qslerp(q,b.q[j],u))},parents);
   supports.length=0;
   for(const foot of feet){foot.contact=null;foot.state='SWING';foot.error=length(sub(pose.points[names.indexOf('foot_'+foot.side.toLowerCase())],foot.target));}
   if(u===1){returnPose=null;footSolver.reset();}
  }
  const surface=motion.finish(context,supports);lastSupports=supports;
  frames.push({pose,raw:baseline,feet,root:pose.points[0],pelvisOffset:slideResult?dot(sub(pose.points[pelvis],baseline.points[pelvis]),normal):dot(pelvisPull.x,normal),pelvisTransfer:0,influence:1,surface,...(slideResult?{slide:{...context.slide,blend:slideResult.blend,legBlend:slideResult.legBlend,pelvisBlend:slideResult.pelvisBlend,hand:slideResult.hand,hands:slideResult.hands,heading:slideResult.heading,commandedHeading:slideResult.commandedHeading}}: {})});
  model.generatedThrough=time;
  // Pause after committing this frame, before beginning another root/limb
  // tick. The generator retains contacts, slide springs and collision state.
  if(experiment.checkpoints)yield {checkpoint:true,model,index:i,time};
 }
 return model;
}
function prepare(run,input={},experiment={}){return simulate(run,input,experiment).next().value;}

const api={settings,createTerrain,prepare,simulate,createFeet,gaitIntent,bodyRotation,gravityActive,gravityShare,gravityDrive,transferVelocity,pinsAllowed,pelvisCloser,slideTargetShift,slideBalanceTime,stableLeg:K.stableLeg,apiVersion:1};if(typeof module!=='undefined')module.exports=api;else root.FootSurface=api;
})(globalThis);
