/* Static aim: pelvis yaw and distributed contact-chain bend, calibrated at Hit. */
(function(root){
'use strict';
const node=typeof module!=='undefined',R=node?require('./recovery.js'):root.Recovery,C=node?require('./core.js'):root.BodyflipCore,H=node?require('./attack-inertia.js'):root.BodyflipAttackInertia,J=node?require('./joint-rig.js'):root.BodyflipJointRig,W=node?require('./wrist.js'):root.BodyflipWrist;
const {add,sub,mul,dot,cross,length,unit,rotate,qm,qinv,qexp}=R;
const direct=new Set(['KickL','KickR','jabL','jabR','pike']);
const smooth=x=>{x=Math.max(0,Math.min(1,x));return x*x*x*(10+x*(-15+6*x));};
function center(pose,rig){const total=rig.reduce((s,b)=>s+b.mass,0);return rig.reduce((p,b)=>add(p,mul(add(pose.points[b.i],rotate(pose.q[b.i],b.offset)),b.mass/total)),[0,0,0]);}
function launchCenter(packet){return packet.comOffset?add(packet.p,rotate(packet.q,packet.comOffset)):packet.p;}
function between(from,to,up){
 const a=unit(from),b=unit(to),d=Math.max(-1,Math.min(1,dot(a,b)));
 if(length(from)<1e-8||length(to)<1e-8)return [0,0,0,1];
 if(d>0&&length(cross(a,b))<1e-12)return [0,0,0,1];
 let axis=cross(a,b);const sine=length(axis);
 if(length(axis)<1e-8){axis=sub(up,mul(a,dot(up,a)));if(length(axis)<1e-8)axis=cross(a,Math.abs(a[0])<.9?[1,0,0]:[0,0,1]);}
 return qexp(mul(unit(axis),Math.atan2(sine,d)));
}
function create({clip,track,names,parents,reference,sampleHit,launchAt=null,project=null,evaluateMotion=null,evaluationAmount=1,evaluationUndoRotation=true,motionSolve=null}){
 if(!launchAt&&!clip?.meta.hitTarget)throw Error('Missing original hit target for '+clip?.meta.name);
 const hitTime=launchAt?(track.releaseTime??track.hitTime):track.hitTime;
 let bone,point;
 if(launchAt){bone=names.indexOf(track.handBone||'hand_r');point=pose=>launchCenter(launchAt(pose));}
 else {
  const f=clip.meta.phases.hit,i=Math.min(clip.poses.length-2,Math.floor(f)),source=C.blend(clip.poses[i],clip.poses[i+1],f-i,parents);bone=names.indexOf(C.effector(clip.meta.name));
  const offset=rotate(qinv(source.q[bone]),sub(clip.meta.hitTarget,source.points[bone]));
  point=pose=>add(pose.points[bone],rotate(pose.q[bone],offset));
 }
 const rig=H.model(names,parents,reference),hit=sampleHit(hitTime),initialLaunch=launchAt?launchAt(hit):null,origin=initialLaunch?launchCenter(initialLaunch):center(hit,rig),direction=initialLaunch?initialLaunch.v:sub(point(hit),origin);
 let carrier=null;
 const start=track.start??0,armed=track.armedTime??start+track.duration,ready=!launchAt&&direct.has(clip.meta.name)?armed:hitTime;
 const end=track.end,returnEnd=track.returnEnd;
 const weight=(t,undoRotation=true)=>smooth((t-start)/Math.max(1e-8,ready-start))*(undoRotation?1-smooth((t-end)/Math.max(1e-8,returnEnd-end)):1);
 // Only bones on the contact path receive bend: five spines for hand/head
 // contacts, the hip for foot contacts. Descendants inherit the cumulative bend.
 const chain=[];for(let j=bone;j>0;j=parents[j])if(/^spine_/.test(names[j])||/^thigh_/.test(names[j]))chain.unshift(j);
 const factors=names.map((_,i)=>{let n=0;for(let j=i;j>0;j=parents[j])if(chain.includes(j))n++;return chain.length?n/chain.length:0;});
 const joints=J.create(names,parents,reference),identity=[0,0,0,1],neutral={yaw:identity,offsets:joints.joints.map(c=>c.hinge?[0]:[0,0,0])};
 if(!project)project=pose=>{const out=joints.project(pose),d=sub(center(pose,rig),center(out,rig));return {...pose,...out,points:out.points.map((p,i)=>i?add(p,d):pose.points[0].slice())};};
 // Every source pose is immutable for this plan. Reuse projection for the
 // multiple endpoint probes that differ only in their additive aim delta.
 const projectionCache=new WeakMap(),projectSource=project;
 project=pose=>{if(projectionCache.has(pose))return projectionCache.get(pose);const result=projectSource(pose);projectionCache.set(pose,result);return result;};
 const state=p=>({yaw:qm(qexp([p[3]||0,0,p[4]||0]),qexp([0,p[0],0])),bends:factors.map(w=>qexp([p[1]*w,0,p[2]*w]))});
 const blendQ=(a,b,w)=>qm(qexp(mul(R.qlog(qm(b,qinv(a))),w)),a);
 function mix(a,b,w){if(Array.isArray(a))a=neutral;return {yaw:blendQ(a.yaw,b.yaw,w),offsets:a.offsets.map((v,i)=>v.map((x,j)=>x+(b.offsets[i][j]-x)*w))};}
 // Search in world correction coordinates, but never interpolate those
 // cumulative rotations: adjacent spines can choose opposite quaternion
 // branches. The animation path uses additive legal joint coordinates below.
 function applyWorld(pose,delta){
  const pivot=center(pose,rig),world=delta.bends.map(q=>qm(q,delta.yaw)),points=[],q=[];
  for(let i=0;i<names.length;i++){
   q[i]=qm(world[i],pose.q[i]);const parent=parents[i];
   points[i]=parent<0?add(pivot,rotate(delta.yaw,sub(pose.points[i],pivot))):add(points[parent],rotate(world[parent],sub(pose.points[i],pose.points[parent])));
  }
  const shift=sub(pivot,center({points,q},rig));for(let i=1;i<points.length;i++)points[i]=add(points[i],shift);
  points[0]=pose.points[0].slice();return {...pose,points,q,axes:q.map(R.toAxes)};
 }
 function coordinates(q,c){
  if(c.native)return joints.coordinates(q,c);
  if(c.hinge){const d=qm(q,qinv(c.bind)),sign=d[3]<0?-1:1;return [2*Math.atan2(dot(d.slice(0,3),c.axisLocal)*sign,d[3]*sign)];}
  const d=W.decompose(qm(qm(qinv(c.parentBasis),q),c.basis));return [d.swing[1],d.swing[2],d.angle];
 }
 function fromCoordinates(v,c){
  if(c.native)return joints.fromCoordinates(v,c);
  const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
  if(c.hinge)return qm(qexp(mul(c.axisLocal,clamp(v[0],c.min,c.max))),c.bind);
  let [y,z,angle]=v;const a=Math.sin(c.limits.plane/2),b=Math.sin(c.limits.normal/2);
  // Euclidean projection onto the convex Jolt swing ellipse is continuous.
  // Clamp before reconstructing its quaternion, avoiding the +/-pi branch.
  if((y/a)**2+(z/b)**2>1){const aa=a*a,bb=b*b;let lo=0,hi=Math.max(a*Math.abs(y),b*Math.abs(z));const value=t=>(a*y/(t+aa))**2+(b*z/(t+bb))**2;while(value(hi)>1)hi*=2;for(let i=0;i<32;i++){const mid=(lo+hi)/2;if(value(mid)>1)lo=mid;else hi=mid;}y=aa*y/(hi+aa);z=bb*z/(hi+bb);}
  return qm(qm(c.parentBasis,W.compose([0,y,z,Math.sqrt(Math.max(0,1-y*y-z*z))],qexp([clamp(angle,c.limits.twistMin,c.limits.twistMax),0,0]))),qinv(c.basis));
 }
 const legalHit=project(hit),hitLocal=R.localize(legalHit.points,legalHit.q,parents),hitCoordinates=joints.joints.map(c=>coordinates(hitLocal.q[c.i],c));
 function legalState(world,corrected=project(applyWorld(legalHit,world))){
  const local=R.localize(corrected.points,corrected.q,parents);
  return {yaw:world.yaw,offsets:joints.joints.map((c,i)=>coordinates(local.q[c.i],c).map((x,j)=>x-hitCoordinates[i][j]))};
 }
 const rotationBases=new WeakMap();
 function applyRotation(pose,delta){
  if(Array.isArray(delta))delta=neutral;
  const base=project(pose);let prepared=rotationBases.get(base);
  if(!prepared){const pivot=center(base,rig),local=R.localize(base.points,base.q,parents);prepared={pivot,local,coordinates:joints.joints.map(c=>coordinates(local.q[c.i],c))};rotationBases.set(base,prepared);}
  const pivot=prepared.pivot,local={p:prepared.local.p,q:prepared.local.q.slice()};
  local.q[0]=qm(delta.yaw,local.q[0]);
  for(let i=0;i<joints.joints.length;i++){const c=joints.joints[i],v=prepared.coordinates[i];local.q[c.i]=fromCoordinates(v.map((x,j)=>x+delta.offsets[i][j]),c);}
  const posed=R.fk(local,parents),shift=sub(pivot,center(posed,rig));
  for(let i=1;i<posed.points.length;i++)posed.points[i]=add(posed.points[i],shift);
  posed.points[0]=pose.points[0].slice();return {...pose,...posed};
 }
 function solve3(matrix,rhs){
  const a=matrix.map((row,i)=>[...row,rhs[i]]);
  for(let i=0;i<rhs.length;i++){
   let k=i;for(let j=i+1;j<rhs.length;j++)if(Math.abs(a[j][i])>Math.abs(a[k][i]))k=j;
   [a[i],a[k]]=[a[k],a[i]];const d=a[i][i];if(Math.abs(d)<1e-15)return rhs.map(()=>0);
   for(let j=i;j<=rhs.length;j++)a[i][j]/=d;
   for(let k=0;k<rhs.length;k++)if(k!==i){const d=a[k][i];for(let j=i;j<=rhs.length;j++)a[k][j]-=d*a[i][j];}
  }
  return a.map(row=>row[rhs.length]);
 }
 const amount=Math.max(0,Math.min(1,evaluationAmount)),applyDeltaAt=(pose,time,delta)=>applyRotation(pose,mix(neutral,delta,amount*weight(time,evaluationUndoRotation)));
 let neutralPrediction=null;
 const solutions=new Map();
 function solution(target){
  const key=target.join(',');if(solutions.has(key))return solutions.get(key);
  const desired=unit(sub(target,origin));
  if(length(sub(target,origin))<1e-8)return {state:neutral,parameters:[0,0,0],error:0};
  const azimuth=v=>Math.atan2(v[0],v[2]),wrap=a=>Math.atan2(Math.sin(a),Math.cos(a));
  const yaw=Math.hypot(desired[0],desired[2])<1e-8?0:wrap(azimuth(desired)-azimuth(direction));
  const initial=R.qlog(between(rotate(qexp([0,yaw,0]),direction),desired,[0,1,0]));
  let p=[yaw,initial[0],initial[2]];
  const evaluate=p=>{
   const world=state(p),posed=project(applyWorld(legalHit,world));
   if(evaluateMotion){
    // Evaluate the same full trajectory used for display, after its momentum
    // response. Candidate sources apply a supplied delta directly, never solve
    // another aim plan, so future-hit evaluation cannot recurse into itself.
    const context={applyDeltaAt,applyRotation,weight,hitTime},result=evaluateMotion(legalState(world,posed),context),actual=result.pose||result;
    const launch=result.launch||(launchAt?launchAt(actual,result.sample?(_,time=hitTime)=>result.sample(time):undefined):null);
    const origin=launch?launchCenter(launch):center(actual,rig),direction=launch?unit(launch.v):unit(sub(point(actual),origin));
    let wanted=unit(sub(target,origin));
    if(amount<1){
     neutralPrediction??=evaluateMotion(neutral,context);const base=neutralPrediction.pose||neutralPrediction,baseLaunch=neutralPrediction.launch||(launchAt?launchAt(base,neutralPrediction.sample?(_,time=hitTime)=>neutralPrediction.sample(time):undefined):null);
     const initial=baseLaunch?unit(baseLaunch.v):unit(sub(point(base),center(base,rig)));
     wanted=rotate(R.qslerp(identity,between(initial,wanted,[0,1,0]),amount),initial);
    }
    return add(sub(direction,wanted),desired);
   }
   if(launchAt){const delta=legalState(world,posed),launch=launchAt(posed,(other,time=hitTime)=>project(applyRotation(other,mix(neutral,delta,weight(time))))),wanted=unit(sub(target,launchCenter(launch)));return add(sub(unit(launch.v),wanted),desired);}
   return unit(sub(point(posed),center(posed,rig)));
  };
  if(evaluateMotion&&motionSolve){
   // At most two endpoint Jacobians and bounded updates. Full-trajectory aim must
   // have a fixed preparation cost rather than an unbounded nested search.
   p=(motionSolve.seed||p).slice();let value=evaluate(p),error=length(sub(value,desired));
   for(let iteration=0;iteration<2&&error>1e-6;iteration++){
    const h=1e-3,indices=motionSolve.indices||[0,1,2],columns=indices.map(j=>{const v=p.slice();v[j]+=h;return mul(sub(evaluate(v),value),1/h);});
    const damping=1e-6*Math.max(1,...columns.map(a=>dot(a,a))),matrix=columns.map((a,i)=>columns.map((b,j)=>dot(a,b)+(i===j?damping:0)));
    let delta=solve3(matrix,columns.map(c=>dot(c,sub(desired,value)))),size=length(delta),limit=motionSolve.maxStep??2;if(size>limit)delta=mul(delta,limit/size);
    let improved=false;for(const scale of [1,.5]){
     const candidate=p.slice();indices.forEach((j,k)=>candidate[j]+=delta[k]*scale);const next=evaluate(candidate),nextError=length(sub(next,desired));if(nextError>=error)continue;
     p=candidate;value=next;error=nextError;improved=true;break;
    }
    if(!improved)break;
   }
   const result={state:legalState(state(p)),parameters:p,error,bounded:true};solutions.set(key,result);if(solutions.size>8)solutions.delete(solutions.keys().next().value);return result;
  }
  function refine(seed,free=seed.length){
   let p=seed.slice(),value=evaluate(p),error=length(sub(value,desired));
   for(let n=0;n<40&&error>1e-8;n++){
    const h=1e-4,columns=Array.from({length:free},(_,j)=>{const v=p.slice();v[j]+=h;return mul(sub(evaluate(v),value),1/h);});
    // Short release windows can make the angular-to-velocity Jacobian large.
    // Scale its regularizer with sensitivity to keep the normal system stable
    // across JS engines, including its unconstrained correction direction.
    const residual=sub(desired,value),damping=1e-6*Math.max(1,...columns.map(a=>dot(a,a))),matrix=columns.map((a,i)=>columns.map((b,j)=>dot(a,b)+(i===j?damping:0))),rhs=columns.map(a=>dot(a,residual));
    let step=solve3(matrix,rhs),size=length(step);if(size>.4)step=mul(step,.4/size);
    let improved=false;
    for(let scale=1;scale>=1/64;scale*=.5){const candidate=p.map((v,i)=>v+(step[i]||0)*scale),v=evaluate(candidate),e=length(sub(v,desired));if(e<error){p=candidate;value=v;error=e;improved=true;break;}}
    if(!improved)break;
   }return {p,error};
  }
  let solved=refine(p),error=solved.error;p=solved.p;
  if(error>1e-6){
   // A constrained spine cannot cover the entire sphere. Start from a rigid
   // legal turn, then transfer as much of its tilt into the chain as it permits.
   let rigid=refine([yaw,0,0,initial[0],initial[2]]);
   if(launchAt&&rigid.error>1e-6){
    // Drift stays in world space when the body turns. Aiming the combined
    // velocity can seed the opposite branch, particularly for weak throws.
    // Intersect the desired ray with the sphere of rotatable relative velocity
    // to obtain another rigid starting estimate; the exact launch still decides.
    carrier??=mul(sub(center(sampleHit(hitTime+1/240),rig),center(sampleHit(hitTime-1/240),rig)),120);
    const relative=sub(direction,carrier),along=dot(desired,carrier),discriminant=along*along+dot(relative,relative)-dot(carrier,carrier);
    if(discriminant>=0){const speed=along+Math.sqrt(discriminant);if(speed>1e-8){
     const required=sub(mul(desired,speed),carrier),turn=wrap(azimuth(required)-azimuth(relative)),bend=R.qlog(between(rotate(qexp([0,turn,0]),relative),required,[0,1,0])),candidate=refine([turn,0,0,bend[0],bend[2]]);
     if(candidate.error<rigid.error)rigid=candidate;
    }}
   }
   if(rigid.error<error){p=rigid.p;error=rigid.error;
    const full=p.slice();let lo=0,hi=1,best=p;
    for(let k=0;k<12;k++){const fraction=(lo+hi)/2,seed=best.slice();seed[3]=full[3]*fraction;seed[4]=full[4]*fraction;const fit=refine(seed,3);if(fit.error<1e-6){hi=fraction;best=fit.p;error=fit.error;}else lo=fraction;}
    p=best;
   }
  }
  const result={state:legalState(state(p)),parameters:p,error};solutions.set(key,result);if(solutions.size>8)solutions.delete(solutions.keys().next().value);return result;
 }
 function correction(target){return solution(target).state;}
 function rotation(time,target,amount=1,undoRotation=true,from=neutral){
  const goal=mix(neutral,correction(target),Math.max(0,Math.min(1,amount)));
  return mix(from,goal,weight(time,undoRotation));
 }
 function apply(pose,time,target,amount=1,undoRotation=true){return applyRotation(pose,rotation(time,target,amount,undoRotation));}
 return {apply,applyRotation,rotation,point,weight,correction,ready,origin,direction,rig,chain,factors,solution,hitTime,deadline:launchAt?'Release':direct.has(clip.meta.name)?'Armed':'Hit'};
}
const api={create,center,between,launchCenter};if(node)module.exports=api;else root.BodyflipAttackAim=api;
})(globalThis);
