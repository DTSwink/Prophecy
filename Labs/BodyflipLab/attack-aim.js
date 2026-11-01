/* Attack aim: legal body/chain turns, calibrated against the final contact. */
(function(root){
'use strict';
const node=typeof module!=='undefined',R=node?require('./recovery.js'):root.Recovery,C=node?require('./core.js'):root.BodyflipCore,H=node?require('./attack-inertia.js'):root.BodyflipAttackInertia,J=node?require('./joint-rig.js'):root.BodyflipJointRig,W=node?require('./wrist.js'):root.BodyflipWrist;
const Work=node?require('./preparation.js'):root.BodyflipPreparation;
const {add,sub,mul,dot,cross,length,unit,rotate,qm,qinv,qexp}=R;
const direct=new Set(['KickL','KickR','jabL','jabR','pike']);
const smooth=x=>{x=Math.max(0,Math.min(1,x));return x*x*x*(10+x*(-15+6*x));};
function center(pose,rig){const total=rig.reduce((s,b)=>s+b.mass,0);return rig.reduce((p,b)=>add(p,mul(add(pose.points[b.i],rotate(pose.q[b.i],b.offset)),b.mass/total)),[0,0,0]);}
function launchCenter(packet){return packet.comOffset?add(packet.p,rotate(packet.q,packet.comOffset)):packet.p;}
// Spears aim their visible shaft. Bombs keep their arc and only aim its azimuth.
function launchAim(packet,target,worldDirection=null){
 const planar=packet.kind==='bomb',origin=packet.kind==='spear'?packet.p:launchCenter(packet),flatten=v=>planar?[v[0],0,v[2]]:v;
 return {origin,direction:flatten(packet.kind==='spear'?packet.axis:packet.v),...(worldDirection||target?{wanted:unit(flatten(worldDirection||sub(target,origin)))}:{})};
}
function between(from,to,up){
 const a=unit(from),b=unit(to),d=Math.max(-1,Math.min(1,dot(a,b)));
 if(length(from)<1e-8||length(to)<1e-8)return [0,0,0,1];
 if(d>0&&length(cross(a,b))<1e-12)return [0,0,0,1];
 let axis=cross(a,b);const sine=length(axis);
 if(length(axis)<1e-8){axis=sub(up,mul(a,dot(up,a)));if(length(axis)<1e-8)axis=cross(a,Math.abs(a[0])<.9?[1,0,0]:[0,0,1]);}
 return qexp(mul(unit(axis),Math.atan2(sine,d)));
}
function create({clip,track,names,parents,reference,sampleHit,launchAt=null,project=null,evaluateMotion=null,evaluationAmount=1,evaluationUndoRotation=true,motionSolve=null,throwAimOrigin=null}){
 if(!launchAt&&!clip?.meta.hitTarget)throw Error('Missing original hit target for '+clip?.meta.name);
 const hitTime=launchAt?(track.releaseTime??track.hitTime):track.hitTime;
 let bone,point;
 if(launchAt){bone=names.indexOf(track.handBone||'hand_r');point=pose=>launchCenter(launchAt(pose));}
 else {
  const f=clip.meta.phases.hit,i=Math.min(clip.poses.length-2,Math.floor(f)),source=C.blend(clip.poses[i],clip.poses[i+1],f-i,parents);bone=names.indexOf(C.effector(clip.meta.name));
  const offset=rotate(qinv(source.q[bone]),sub(clip.meta.hitTarget,source.points[bone]));
  point=pose=>add(pose.points[bone],rotate(pose.q[bone],offset));
 }
 const rig=H.model(names,parents,reference),hit=sampleHit(hitTime),initialLaunch=launchAt?launchAt(hit):null,initialAim=initialLaunch?launchAim(initialLaunch):null,planar=initialLaunch?.kind==='bomb',origin=initialAim?initialAim.origin:center(hit,rig),direction=initialAim?initialAim.direction:sub(point(hit),origin);
 // Frame zero of the jump establishes a world-space ray. Neither the current
 // release point nor any candidate spine rotation is allowed to retarget it.
 const aimReferenceOrigin=initialLaunch?(throwAimOrigin||sampleHit(Number.isFinite(track.aimReferenceTime)?track.aimReferenceTime:track.start??0).points[names.indexOf('pelvis')]).slice():null;
 const authoredDirection=track.throwDirection?.slice()||null;
 const throwDirectionFor=initialLaunch?target=>{const d=authoredDirection||sub(target,aimReferenceOrigin);return unit(length(d)>1e-9?d:direction);}:null;
 let carrier=null;
 const start=track.start??0,armed=track.armedTime??start+track.duration,ready=!launchAt&&direct.has(clip.meta.name)?armed:hitTime;
 const end=track.end,returnEnd=track.returnEnd,returnPolicy=track.returnPolicy||C.attackReturn({},track.returnEnd-track.end);
 const weight=(t,undoRotation=true)=>smooth((t-start)/Math.max(1e-8,ready-start))*(undoRotation?returnPolicy.factor(t-end):1);
 // Steer through the torso without rewriting the authored arm or leg stroke.
 // Static/no-spin aiming retains its approved parameterization.
 const chain=[];for(let j=bone;j>0;j=parents[j])if(/^spine_/.test(names[j])||/^thigh_/.test(names[j]))chain.unshift(j);
 const factors=names.map((_,i)=>{let n=0;for(let j=i;j>0;j=parents[j])if(chain.includes(j))n++;return chain.length?n/chain.length:0;});
 const joints=J.create(names,parents,reference),identity=[0,0,0,1],neutral={yaw:identity,offsets:joints.joints.map(c=>c.hinge?[0]:[0,0,0])};
 if(!project)project=pose=>{const out=joints.project(pose),d=sub(center(pose,rig),center(out,rig));return {...pose,...out,points:out.points.map((p,i)=>i?add(p,d):pose.points[0].slice())};};
 // Every source pose is immutable for this plan. Reuse projection for the
 // multiple endpoint probes that differ only in their additive aim delta.
 const projectionCache=new WeakMap(),projectSource=project;
 project=pose=>{if(projectionCache.has(pose))return projectionCache.get(pose);const result=projectSource(pose);projectionCache.set(pose,result);return result;};
 // During a flip, yaw follows the pelvis upright; it is not a fixed world-Y turn.
 const pelvis=names.indexOf('pelvis'),aimBasis=evaluateMotion?qm(hit.q[pelvis],qinv(reference.q[pelvis])):identity,worldTurn=q=>qm(qm(aimBasis,q),qinv(aimBasis));
 const state=p=>{
  if(initialLaunch){
   // Throws steer the upper body with heading and elevation only. There is
   // no free roll, whole-pelvis turn or sideways-tilt fallback to win the fit.
   const heading=Math.atan2(direction[0],direction[2])+p[0],pitch=planar?0:(p[1]||0),headingTurn=qm(qexp([Math.cos(heading)*pitch,0,-Math.sin(heading)*pitch]),qexp([0,p[0],0])),turn=headingTurn,log=R.qlog(turn);
   return {yaw:identity,bends:factors.map(w=>qexp(mul(log,w)))};
  }
  return {yaw:worldTurn(qm(qexp([p[3]||0,0,p[4]||0]),qexp([0,p[0],0]))),bends:factors.map(w=>worldTurn(qexp([p[1]*w,(p[5]||0)*w,p[2]*w])))};
 };
 const blendQ=(a,b,w)=>qm(qexp(mul(R.qlog(qm(b,qinv(a))),w)),a);
 function mix(a,b,w){if(Array.isArray(a))a=neutral;return {yaw:blendQ(a.yaw,b.yaw,w),offsets:a.offsets.map((v,i)=>v.map((x,j)=>x+(b.offsets[i][j]-x)*w)),...(initialLaunch?{throwTurn:blendQ(a.throwTurn||identity,b.throwTurn||identity,w)}:{})};}
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
  points[0]=pose.points[0].slice();return {...pose,points,q,axes:q.map(R.toAxes),...(initialLaunch?{attackSpineAim:true}:{})};
 }
 function coordinates(q,c){
  if(c.native)return joints.coordinates(q,c);
  if(c.hinge){const d=qm(q,qinv(c.bind)),sign=d[3]<0?-1:1;return [2*Math.atan2(dot(d.slice(0,3),c.axisLocal)*sign,d[3]*sign)];}
  const d=W.decompose(qm(qm(qinv(c.parentBasis),q),c.basis));return [d.swing[1],d.swing[2],d.angle];
 }
 function fromCoordinates(v,c){
  if(hit.attackFree){
   if(c.hinge)return qm(qexp(mul(c.axisLocal,v[0])),c.bind);
   let [y,z,angle]=v;const n=Math.hypot(y,z);if(n>1){y/=n;z/=n;}
   return qm(qm(c.parentBasis,W.compose([0,y,z,Math.sqrt(Math.max(0,1-y*y-z*z))],qexp([angle,0,0]))),qinv(c.basis));
  }
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
 function legalState(world,corrected=null){
  // Keep throws as one direction-to-direction rotation. Converting a release
  // pose into joint-limit coordinates and replaying those offsets on every
  // animation frame changes the path and introduces unintended torso roll.
  if(initialLaunch)return {...neutral,throwTurn:world.bends[bone]};
  corrected ||= project(applyWorld(legalHit,world));
  const local=R.localize(corrected.points,corrected.q,parents);
  return {yaw:world.yaw,offsets:joints.joints.map((c,i)=>coordinates(local.q[c.i],c).map((x,j)=>x-hitCoordinates[i][j]))};
 }
 const rotationBases=new WeakMap();
 function applyRotation(pose,delta){
  if(Array.isArray(delta))delta=neutral;
  if(initialLaunch){const log=R.qlog(delta.throwTurn||identity);return applyWorld(pose,{yaw:identity,bends:factors.map(w=>qexp(mul(log,w)))});}
  const base=project(pose);let prepared=rotationBases.get(base);
  if(!prepared){const pivot=center(base,rig),local=R.localize(base.points,base.q,parents);prepared={pivot,local,coordinates:joints.joints.map(c=>coordinates(local.q[c.i],c))};rotationBases.set(base,prepared);}
  const pivot=prepared.pivot,local={p:prepared.local.p,q:prepared.local.q.slice()};
  if(evaluateMotion)local.q[pelvis]=qm(local.q[pelvis],qm(qm(qinv(legalHit.q[pelvis]),delta.yaw),legalHit.q[pelvis]));
  else local.q[0]=qm(delta.yaw,local.q[0]);
  for(let i=0;i<joints.joints.length;i++){const c=joints.joints[i],v=prepared.coordinates[i];if(delta.offsets[i].some(x=>Math.abs(x)>1e-12)){const next=fromCoordinates(v.map((x,j)=>x+delta.offsets[i][j]),c);local.q[c.i]=base.attackFree?qm(qm(next,qinv(fromCoordinates(v,c))),local.q[c.i]):next;}}
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
 function timedDelta(delta,time,amount,undo,from=neutral){
  const goal=mix(neutral,delta,Math.max(0,Math.min(1,amount))),out=mix(from,goal,smooth((time-start)/Math.max(1e-8,ready-start)));
  if(!undo)return out;
  const fade=returnPolicy.factor(time-end);
  out.yaw=R.qslerp(identity,out.yaw,fade);
  if(out.throwTurn)out.throwTurn=R.qslerp(identity,out.throwTurn,fade);
  out.offsets=out.offsets.map(v=>mul(v,fade));
  return out;
 }
 const amount=Math.max(0,Math.min(1,evaluationAmount)),applyDeltaAt=(pose,time,delta)=>applyRotation(pose,timedDelta(delta,time,amount,evaluationUndoRotation));
 let neutralPrediction=null;
 const solutions=new Map(),jobs=new Map();
 function solution(target){
  const fixedDirection=throwDirectionFor?.(target),key=(fixedDirection||target).join(',');if(solutions.has(key))return solutions.get(key);
  const desired=initialLaunch?launchAim(initialLaunch,target,fixedDirection).wanted:unit(sub(target,origin));
  if(!initialLaunch&&length(sub(target,origin))<1e-8)return {state:neutral,parameters:[0,0,0],error:0};
  const azimuth=v=>Math.atan2(v[0],v[2]),wrap=a=>Math.atan2(Math.sin(a),Math.cos(a));
  const yaw=Math.hypot(desired[0],desired[2])<1e-8?0:wrap(azimuth(desired)-azimuth(direction));
  const initial=R.qlog(between(rotate(qexp([0,yaw,0]),direction),desired,[0,1,0]));
  let p=planar?[yaw]:initialLaunch?[yaw,Math.asin(unit(direction)[1])-Math.asin(desired[1])]:[yaw,initial[0],initial[2]];
  const evaluate=p=>{
   const world=state(p),posed=project(applyWorld(legalHit,world));
   if(evaluateMotion){
    // Evaluate the same full trajectory used for display, after its momentum
    // response. Candidate sources apply a supplied delta directly, never solve
    // another aim plan, so future-hit evaluation cannot recurse into itself.
    const context={applyDeltaAt,applyRotation,weight,hitTime},result=evaluateMotion(legalState(world,posed),context),actual=result.pose||result;
    const launch=result.launch||(launchAt?launchAt(actual,result.sample?(_,time=hitTime)=>result.sample(time):undefined):null);
    const aimed=launch?launchAim(launch,target,fixedDirection):null,origin=aimed?aimed.origin:center(actual,rig),direction=aimed?unit(aimed.direction):unit(sub(point(actual),origin));
    let wanted=aimed?aimed.wanted:unit(sub(target,origin));
    if(amount<1){
     neutralPrediction??=evaluateMotion(neutral,context);const base=neutralPrediction.pose||neutralPrediction,baseLaunch=neutralPrediction.launch||(launchAt?launchAt(base,neutralPrediction.sample?(_,time=hitTime)=>neutralPrediction.sample(time):undefined):null);
     const initialRay=baseLaunch?launchAim(baseLaunch).direction:sub(point(base),center(base,rig)),initial=unit(initialRay);
     wanted=rotate(R.qslerp(identity,between(initial,wanted,[0,1,0]),amount),initial);
    }
    // Rotate the authored stroke; do not fold the arm to force its tip radius.
    return add(sub(direction,wanted),desired);
   }
   if(launchAt){const delta=legalState(world,posed),launch=launchAt(posed,(other,time=hitTime)=>project(applyRotation(other,mix(neutral,delta,weight(time))))),aimed=launchAim(launch,target,fixedDirection);return add(sub(unit(aimed.direction),aimed.wanted),desired);}
   return unit(sub(point(posed),center(posed,rig)));
  };
  if(evaluateMotion&&motionSolve){
   let job=jobs.get(key);
   if(!job){
    function* search(){
     let p=initialLaunch?(planar?[yaw]:[yaw,Math.asin(unit(direction)[1])-Math.asin(desired[1])]):(motionSolve.seed||[0,0,0]).slice(),value=yield p,error=length(sub(value,desired));
     for(const stage of initialLaunch?[planar?[0]:[0,1]]:[motionSolve.indices||[0,1,2],...(motionSolve.fallbackIndices?[motionSolve.fallbackIndices]:[])]){
      const indices=stage;
      for(let iteration=0;iteration<(motionSolve.iterations??2)&&error>1e-4;iteration++){
       const h=1e-3,columns=[];
       for(const j of indices){const v=p.slice();v[j]+=h;const probe=yield v;columns.push(mul(sub(probe,value),(motionSolve.scales?.[j]??1)/h));}
       const damping=1e-6*Math.max(1,...columns.map(a=>dot(a,a))),matrix=columns.map((a,i)=>columns.map((b,j)=>dot(a,b)+(i===j?damping:0)));
       let delta=solve3(matrix,columns.map(c=>dot(c,sub(desired,value)))),size=length(delta),limit=motionSolve.maxStep??2;if(size>limit)delta=mul(delta,limit/size);
       let improved=false;
       for(let scale=1;scale>=1/64;scale*=.5){
        const candidate=p.slice();indices.forEach((j,k)=>candidate[j]+=delta[k]*scale*(motionSolve.scales?.[j]??1));const next=yield candidate,nextError=length(sub(next,desired));
        if(nextError>=error)continue;p=candidate;value=next;error=nextError;improved=true;break;
       }
       if(!improved)break;
      }
     }
     return {state:legalState(state(p)),parameters:p,error,bounded:true};
    }
    job={iterator:search(),step:null,value:undefined};jobs.set(key,job);
   }
   for(;;){job.step ||= job.iterator.next(job.value);if(job.step.done){const result=job.step.value;solutions.set(key,result);jobs.delete(key);if(solutions.size>8)solutions.delete(solutions.keys().next().value);return result;}job.value=evaluate(job.step.value);job.step=null;Work.checkpoint();}
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
  if(planar&&error>1e-6){
   // A fast carrier can make a yaw-only aim unreachable. Keep the best yaw,
   // including the unturned pose, without tilting or changing launch speed.
   for(const seed of [0,yaw-Math.PI/2,yaw+Math.PI/2,yaw+Math.PI]){const candidate=refine([seed]);if(candidate.error<error){p=candidate.p;error=candidate.error;}}
  }
  if(error>1e-6&&!initialLaunch){
   // A constrained spine cannot cover the entire sphere. Start from a rigid
   // legal turn, then transfer as much of its tilt into the chain as it permits.
   let rigid=refine([yaw,0,0,initial[0],initial[2]]);
   if(launchAt&&initialLaunch.kind!=='spear'&&rigid.error>1e-6){
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
  return timedDelta(correction(target),time,amount,undoRotation,from);
 }
 function apply(pose,time,target,amount=1,undoRotation=true){return applyRotation(pose,rotation(time,target,amount,undoRotation));}
 return {apply,applyRotation,rotation,point,weight,correction,ready,origin,direction,aimReferenceOrigin,throwDirectionFor,rig,chain,factors,solution,hitTime,deadline:launchAt?'Release':direct.has(clip.meta.name)?'Armed':'Hit'};
}
const api={create,center,between,launchCenter,launchAim};if(node)module.exports=api;else root.BodyflipAttackAim=api;
})(globalThis);
