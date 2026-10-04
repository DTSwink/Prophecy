/* Parent-local FK recovery. Stateless sampling; no per-frame history or IK. */
(function(root){
'use strict';
const add=(a,b)=>a.map((v,i)=>v+b[i]), sub=(a,b)=>a.map((v,i)=>v-b[i]);
const mul=(a,s)=>a.map(v=>v*s), dot=(a,b)=>a.reduce((s,v,i)=>s+v*b[i],0);
const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
const length=a=>Math.hypot(...a), unit=a=>mul(a,1/(length(a)||1));
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const ident=[0,0,0,1];
const qinv=q=>[-q[0],-q[1],-q[2],q[3]];
function qm(a,b){return [a[3]*b[0]+a[0]*b[3]+a[1]*b[2]-a[2]*b[1],a[3]*b[1]-a[0]*b[2]+a[1]*b[3]+a[2]*b[0],a[3]*b[2]+a[0]*b[1]-a[1]*b[0]+a[2]*b[3],a[3]*b[3]-dot(a.slice(0,3),b.slice(0,3))];}
function rotate(q,v){const t=mul(cross(q,v),2);return add(v,add(mul(t,q[3]),cross(q,t)));}
function qlog(q){if(q[3]<0)q=mul(q,-1);const n=length(q.slice(0,3));return n<1e-10?mul(q.slice(0,3),2):mul(q.slice(0,3),2*Math.atan2(n,q[3])/n);}
function qexp(v){const n=length(v);return n<1e-10?unit([...mul(v,.5),1]):[...mul(v,Math.sin(n*.5)/n),Math.cos(n*.5)];}
function qslerp(a,b,t){let c=dot(a,b);if(c<0){b=mul(b,-1);c=-c;}if(c>.9995)return unit(add(mul(a,1-t),mul(b,t)));const theta=Math.acos(clamp(c,-1,1)),s=Math.sin(theta);return add(mul(a,Math.sin((1-t)*theta)/s),mul(b,Math.sin(t*theta)/s));}
function fromTo(a,b){a=unit(a);b=unit(b);const c=dot(a,b);if(c<-.999999){let axis=cross(a,[1,0,0]);if(length(axis)<1e-5)axis=cross(a,[0,1,0]);return [...unit(axis),0];}return unit([...cross(a,b),1+c]);}
// Harness matrices store three world-space basis vectors consecutively.
function fromAxes(a){const m00=a[0][0],m01=a[1][0],m02=a[2][0],m10=a[0][1],m11=a[1][1],m12=a[2][1],m20=a[0][2],m21=a[1][2],m22=a[2][2];let q,s;const trace=m00+m11+m22;
 if(trace>0){s=Math.sqrt(trace+1)*2;q=[(m21-m12)/s,(m02-m20)/s,(m10-m01)/s,s/4];}
 else if(m00>m11&&m00>m22){s=Math.sqrt(1+m00-m11-m22)*2;q=[s/4,(m01+m10)/s,(m02+m20)/s,(m21-m12)/s];}
 else if(m11>m22){s=Math.sqrt(1+m11-m00-m22)*2;q=[(m01+m10)/s,s/4,(m12+m21)/s,(m02-m20)/s];}
 else{s=Math.sqrt(1+m22-m00-m11)*2;q=[(m02+m20)/s,(m12+m21)/s,s/4,(m10-m01)/s];}return unit(q);}
const toAxes=q=>[[1,0,0],[0,1,0],[0,0,1]].map(v=>rotate(q,v));
// Use the actual authored sampler's terminal derivative, including forearm fit
// and distributed yaw. A full-frame difference can miss those nonlinear paths.
const seedInterval=1e-6;
function worldAngularVelocity(last,previous){
 return last.q.map((q,j)=>mul(qlog(qm(q,qinv(previous.q[j]))),1/seedInterval));
}
// Angular velocities add down an FK chain: world = parent + local-in-world.
// Subtract the parent's actual return velocity, including idle easing and disabled
// joints, before converting the residual to the terminal bone frame. Cache once
// per profile; recovery remains local/stateless with no per-frame velocity solve.
function recoverySeeds(model,options,duration,easing,inertia){
 const effective=model.inertiaKeys.map((key,j)=>{const a=Number(options.boneInertia?.[key]??1);return model.inertial[j]?inertia*clamp(Number.isFinite(a)?a:1,0,1):0;});
 const key=[duration,easing,...effective].join(',');
 if(model.seedCache?.key===key)return model.seedCache;
 const last=model.locals.at(-1),end=model.poses.at(-1),world=[],velocity=[],baseWorld=[],worldCorrection=[],rate=(1-easing)/duration;
 for(let j=0;j<model.parents.length;j++){
  const parent=model.parents[j],parentWorld=parent<0?[0,0,0]:world[parent];
  if(!model.upper[j]){world[j]=baseWorld[j]=worldCorrection[j]=velocity[j]=[0,0,0];continue;}
  const idleVelocity=mul(qlog(qm(qinv(last.q[j]),model.idle.q[j])),rate);
  baseWorld[j]=add(parent<0?[0,0,0]:baseWorld[parent],rotate(end.q[j],idleVelocity));
  worldCorrection[j]=sub(model.worldVelocity[j],baseWorld[j]);
  velocity[j]=effective[j]>0?sub(rotate(qinv(end.q[j]),sub(model.worldVelocity[j],parentWorld)),idleVelocity):[0,0,0];
  world[j]=add(parentWorld,rotate(end.q[j],add(idleVelocity,velocity[j])));
 }
 return model.seedCache={key,velocity,worldCorrection,effective};
}
function localize(points,rotations,parents){return {q:rotations.map((q,j)=>parents[j]<0?q:unit(qm(qinv(rotations[parents[j]]),q))),p:points.map((p,j)=>parents[j]<0?p:rotate(qinv(rotations[parents[j]]),sub(p,points[parents[j]])))};}
function fk(local,parents){const points=[],q=[];for(let j=0;j<parents.length;j++){const p=parents[j];q[j]=p<0?local.q[j]:unit(qm(q[p],local.q[j]));points[j]=p<0?local.p[j]:add(points[p],rotate(q[p],local.p[j]));}return {points,q,axes:q.map(toAxes)};}
const ease=x=>x*x*x*(10+x*(-15+6*x));
function offsetBlend(a,b,t){const la=length(a),lb=length(b);if(la<1e-9||lb<1e-9)return add(mul(a,1-t),mul(b,t));return mul(rotate(qslerp(ident,fromTo(a,b),t),unit(a)),la+(lb-la)*t);}
// Carry the frame-0 forearm frame with its upperarm, then apply only the
// shortest swing needed to reach the wrist. Decoder roll flips are not a DOF.
function fitForearms(pose,arms){
 const q=pose.q.slice(),axes=pose.axes.slice();
 for(const arm of arms){
  const reference=unit(qm(q[arm.parent],arm.localQ));
  const direction=sub(pose.points[arm.hand],pose.points[arm.bone]);
  if(length(direction)<1e-9)continue;
  q[arm.bone]=unit(qm(fromTo(rotate(reference,arm.axis),direction),reference));
  axes[arm.bone]=toAxes(q[arm.bone]);
 }
 return {...pose,q,axes};
}
function prepare(meta,buffer,clip,names,parents){
 const count=meta.frames*names.length,values=new Float32Array(buffer),positionCount=count*3;
 if(values.length!==count*12)throw Error('Invalid motion buffer length');
 for(const x of values)if(!Number.isFinite(x))throw Error('Non-finite source motion');
 const idle=localize(clip.idle.points,clip.idle.axes.map(fromAxes),parents);
 // Authored forearm correction retains its original reference; only recovery uses common idle.
 const attackFrame0=clip.attackFrame0||clip.idle;
 const armIdle=localize(attackFrame0.points,attackFrame0.axes.map(fromAxes),parents);
 const arms=['l','r'].map(side=>{const bone=names.indexOf('lowerarm_'+side),hand=names.indexOf('hand_'+side);return {bone,hand,parent:parents[bone],localQ:armIdle.q[bone],axis:unit(armIdle.p[hand])};});
 const poses=[],locals=[];
 for(let f=0;f<meta.frames;f++){const points=[],axes=[];for(let j=0;j<names.length;j++){const i=f*names.length+j;points.push(Array.from(values.subarray(i*3,i*3+3)));axes.push([0,1,2].map(k=>Array.from(values.subarray(positionCount+i*9+k*3,positionCount+i*9+k*3+3))));}const pose=fitForearms({points,axes,q:axes.map(fromAxes)},arms);poses.push(pose);locals.push(localize(points,pose.q,parents));}
 const spine=names.indexOf('spine_01'),upper=parents.map((_,j)=>{let i=j;while(i>=0){if(i===spine)return true;i=parents[i];}return false;});
 const last=locals.at(-1),prev=locals.at(-2)||last;
 const offsetVelocity=last.p.map((p,j)=>length(p)>1e-8&&length(prev.p[j])>1e-8?mul(qlog(fromTo(prev.p[j],p)),meta.fps):[0,0,0]);
 // Lengths are fixed throughout recovery, even if source idle has tiny solver roundoff.
 const idleOffsets=idle.p.map((p,j)=>length(p)>1e-8?mul(unit(p),length(last.p[j])):last.p[j]);
 const idlePose=fk({q:last.q.map((q,j)=>upper[j]?idle.q[j]:q),p:last.p.map((p,j)=>upper[j]?idleOffsets[j]:p)},parents);
 const inertial=upper.map((enabled,j)=>enabled&&names[j]!=='hand_l'&&names[j]!=='hand_r');
 const model={meta,clip,names,parents,arms,inertiaKeys:names.map(name=>/^spine_0[1-5]$/.test(name)?'spine':name.replace(/_(l|r)$/,'')),poses,locals,idle,idleOffsets,idlePose,spine,upper,inertial,offsetVelocity,attackSeconds:(meta.frames-1)/meta.fps};
 model.worldVelocity=worldAngularVelocity(poses.at(-1),sampleBase(model,model.attackSeconds-seedInterval));
 return model;
}
function sampleBase(model,seconds,options={}){
 const {meta,parents,poses,locals}=model;const t=clamp(seconds,0,1e5),tail=model.attackSeconds;
 // Match Final Harness authored playback: global position lerp and global
 // orientation slerp. Separate parent/child arcs can add a spurious full turn.
 if(t<=tail){const f=t*meta.fps,i=Math.min(meta.frames-1,Math.floor(f+1e-10)),n=Math.min(meta.frames-1,i+1),u=clamp(f-i,0,1);if(u<1e-8||i===n)return poses[i];const q=poses[i].q.map((q,j)=>qslerp(q,poses[n].q[j],u));return fitForearms({q,axes:q.map(toAxes),points:poses[i].points.map((p,j)=>add(p,mul(sub(poses[n].points[j],p),u)))},model.arms);}
 if(options.enabled===false)return poses.at(-1);
 const duration=returnTiming(model,{...options,spineTurn:0}).duration,elapsed=t-tail,x=clamp(elapsed/duration,0,1),easing=clamp(Number(options.returnEasing??1),0,1),blend=x+(ease(x)-x)*easing,inertia=clamp(Number(options.inertia)||0,0,1);
 if(elapsed>=duration-1e-12)return model.idlePose;
 if(options.springReturn===true&&inertia>0)return sampleSpringReturn(model,elapsed,options,duration,easing,inertia);
 // Compact analytic angular momentum: outgoing velocity at t=0; exact zero
 // position and derivative at duration. Inertia controls decay, not FK length.
 const hold=clamp(Number(options.inertiaHold)||0,0,.8),decayValue=Number(options.inertiaDecay??1),decay=clamp(Number.isFinite(decayValue)?decayValue:1,0,4);
 // Delay envelope decay, not FK idle return. A squared fade phase joins the
 // optional constant-velocity hold smoothly; zero hold retains the old curve.
 const fade=clamp((x-hold)/(1-hold),0,1),momentumPhase=hold>0?fade*fade:x;
 const momentumBase=elapsed*Math.pow(1-momentumPhase,3);
 const seeds=recoverySeeds(model,options,duration,easing,inertia);
 const last=locals.at(-1),q=last.q.slice(),p=last.p.slice(),worldMode=options.worldInertia===true,momenta=worldMode?[]:null;
 for(let j=0;j<parents.length;j++){if(!model.upper[j])continue;
   q[j]=qslerp(last.q[j],model.idle.q[j],blend);
   p[j]=offsetBlend(last.p[j],model.idleOffsets[j],blend);
   const effective=seeds.effective[j];
   const momentum=model.inertial[j]&&effective>0?momentumBase*Math.exp(-decay*momentumPhase/(.025+.45*effective)):0;
   if(worldMode)momenta[j]=momentum;
   if(momentum>0){if(!worldMode)q[j]=unit(qm(q[j],qexp(mul(seeds.velocity[j],momentum))));p[j]=rotate(qexp(mul(model.offsetVelocity[j],momentum)),p[j]);}
 }
 if(worldMode){
  // Baseline uses only the parent-local idle return. Apply each active bone's
  // correction about a fixed WORLD axis, independently of parent inertia.
  // Positions still follow the actual parent, keeping the skeleton connected;
  // excluded hands and zero-weight bones retain ordinary parent inheritance.
  const base=[],world=[],points=[];
  for(let j=0;j<parents.length;j++){
   const parent=parents[j];
   base[j]=parent<0?q[j]:unit(qm(base[parent],q[j]));
   world[j]=momenta[j]>0?unit(qm(qexp(mul(seeds.worldCorrection[j],momenta[j])),base[j])):parent<0?q[j]:unit(qm(world[parent],q[j]));
   points[j]=parent<0?p[j]:add(points[parent],rotate(world[parent],p[j]));
  }
  return {points,q:world,axes:world.map(toAxes)};
 }
 return fk({q,p},parents);
}
// Continuous second-order joint springs. Inertia and idle attraction act at every
// integration step; there is no hold or pose-blend phase for active joints.
// Build once on profile changes on a deterministic grid (480 steps/second, denser near idle), then sample FK.
function sampleSpringReturn(model,elapsed,options,duration,easing,inertia){
 const seeds=recoverySeeds(model,options,duration,easing,inertia),decayValue=Number(options.inertiaDecay??1),damping=clamp(Number.isFinite(decayValue)?decayValue:1,0,4),worldMode=options.worldInertia===true;
 const key=[seeds.key,damping,worldMode].join('|');
 if(model.springCache?.key!==key){
  const count=Math.ceil(duration*480),times=Array.from({length:count+1},(_,i)=>duration*(1-Math.pow(1-i/count,2))),last=model.locals.at(-1),end=model.poses.at(-1),frames=[last],rates=seeds.velocity.map((w,j)=>add(w,mul(qlog(qm(qinv(last.q[j]),model.idle.q[j])),(1-easing)/duration))),offsetRates=model.offsetVelocity.map(w=>w.slice());
  let q=end.q.map(q=>q.slice()),localQ=last.q.map(q=>q.slice()),p=last.p.map(p=>p.slice());
  if(worldMode)for(let j=0;j<rates.length;j++)rates[j]=model.worldVelocity[j].slice();
  for(let step=1;step<=count;step++){
   const t=times[step],dt=t-times[step-1],x=t/duration,ordinary=x+(ease(x)-x)*easing,previous=q,qNext=[],parentRates=[];
   // Frequency grows continuously; the remaining-time term closes the idle
   // error smoothly near the deadline. Backward Euler keeps stiff steps stable.
   const frequency=(.15+6*Math.pow(x,1+3*easing))/Math.max(duration-t,dt);
   for(let j=0;j<model.parents.length;j++){
    const parent=model.parents[j],effective=seeds.effective[j];
    if(!model.upper[j]){qNext[j]=previous[j];parentRates[j]=[0,0,0];continue;}
    if(effective>0){
     const k=frequency*frequency/Math.max(.05,effective),c=2*Math.sqrt(k)*((.35+.65*damping)*(1-x*x)+x*x),den=1+c*dt+k*dt*dt;
     if(worldMode){
      const target=parent<0?model.idle.q[j]:unit(qm(qNext[parent],model.idle.q[j])),error=qlog(qm(target,qinv(previous[j]))),parentRate=parent<0?[0,0,0]:parentRates[parent];
      rates[j]=mul(add(rates[j],mul(add(mul(error,k),mul(parentRate,c)),dt)),1/den);
      qNext[j]=unit(qm(qexp(mul(rates[j],dt)),previous[j]));
      localQ[j]=parent<0?qNext[j]:unit(qm(qinv(qNext[parent]),qNext[j]));
     }else{
      const error=qlog(qm(qinv(localQ[j]),model.idle.q[j]));
      rates[j]=mul(add(rates[j],mul(error,k*dt)),1/den);
      localQ[j]=unit(qm(localQ[j],qexp(mul(rates[j],dt))));
      qNext[j]=parent<0?localQ[j]:unit(qm(qNext[parent],localQ[j]));
     }
     const error=qlog(fromTo(p[j],model.idleOffsets[j]));
     offsetRates[j]=mul(add(offsetRates[j],mul(error,k*dt)),1/den);
     p[j]=rotate(qexp(mul(offsetRates[j],dt)),p[j]);
    }else{
     localQ[j]=qslerp(last.q[j],model.idle.q[j],ordinary);p[j]=offsetBlend(last.p[j],model.idleOffsets[j],ordinary);
     qNext[j]=parent<0?localQ[j]:unit(qm(qNext[parent],localQ[j]));
    }
    parentRates[j]=mul(qlog(qm(qNext[j],qinv(previous[j]))),1/dt);
   }
   q=qNext;frames.push({q:localQ.slice(),p:p.slice()});
  }
  const endpointBeforeSnap=frames.at(-1);
  frames[count]={q:last.q.map((q,j)=>model.upper[j]?model.idle.q[j]:q),p:last.p.map((p,j)=>model.upper[j]?model.idleOffsets[j]:p)};
  model.springCache={key,frames,times,count,endpointBeforeSnap};
 }
 const {frames,times,count}=model.springCache,f=count*(1-Math.sqrt(Math.max(0,1-elapsed/duration))),i=Math.min(count-1,Math.floor(f)),u=clamp((elapsed-times[i])/(times[i+1]-times[i]),0,1),a=frames[i],b=frames[i+1];
 return fk({q:a.q.map((q,j)=>qslerp(q,b.q[j],u)),p:a.p.map((p,j)=>offsetBlend(p,b.p[j],u))},model.parents);
}
// Same five equal component-space increments as BuildDistributedSpines in UE.
function turnSpines(model,pose,degrees){
 if(!degrees)return pose;
 const local=localize(pose.points,pose.q,model.parents),points=pose.points.slice(),q=pose.q.slice(),axes=pose.axes.slice();
 const step=qexp([0,degrees*Math.PI/180/5,0]);
 for(let j=0;j<model.parents.length;j++){
  if(!model.upper[j])continue;
  const parent=model.parents[j];
  points[j]=add(points[parent],rotate(q[parent],local.p[j]));
  q[j]=unit(qm(q[parent],local.q[j]));
  if(/^spine_0[1-5]$/.test(model.names[j]))q[j]=unit(qm(step,q[j]));
  axes[j]=toAxes(q[j]);
 }
 return {points,q,axes};
}
function turnedRecovery(model,degrees){
 if(model.turnCache?.degrees===degrees)return model.turnCache.model;
 const poses=model.poses.slice(),locals=model.locals.slice();
 for(let i=Math.max(0,poses.length-2);i<poses.length;i++){
  poses[i]=turnSpines(model,poses[i],degrees);
  locals[i]=localize(poses[i].points,poses[i].q,model.parents);
 }
 const last=locals.at(-1),prev=locals.at(-2)||last;
 const worldVelocity=worldAngularVelocity(poses.at(-1),turnSpines(model,sampleBase(model,model.attackSeconds-seedInterval),degrees));
 const offsetVelocity=last.p.map((p,j)=>length(p)>1e-8&&length(prev.p[j])>1e-8?mul(qlog(fromTo(prev.p[j],p)),model.meta.fps):[0,0,0]);
 const turned={...model,poses,locals,worldVelocity,offsetVelocity,turnCache:null,seedCache:null,springCache:null};
 model.turnCache={degrees,model:turned};return turned;
}
// Measure once from the authored endpoint in pelvis-local space, relative to idle.
// A 90-degree departure adds the selected seconds; idle gets no extra time.
function returnTiming(model,options={}){
 const degrees=clamp(Number(options.spineTurn)||0,-179,179),source=degrees?turnedRecovery(model,degrees):model;
 const angle=length(qlog(qm(qinv(source.idle.q[source.spine]),source.locals.at(-1).q[source.spine])))*180/Math.PI;
 const base=clamp(Number(options.duration)||1,.1,5),seconds=clamp(Number(options.angleTimeSeconds)||0,0,4),addedSeconds=seconds*angle/90;
 return {angle,addedSeconds,duration:base+addedSeconds};
}
function sample(model,seconds,options={}){
 const degrees=clamp(Number(options.spineTurn)||0,-179,179);
 if(!degrees)return sampleBase(model,seconds,options);
 if(seconds<=model.attackSeconds)return turnSpines(model,sampleBase(model,seconds,options),degrees);
 return sampleBase(turnedRecovery(model,degrees),seconds,options);
}
function anchor(model,pose,target){const shift=sub(model.poses[0].points[model.spine],pose.points[model.spine]);return {...pose,points:pose.points.map(p=>add(p,shift)),target:add(target,shift)};}
const api={prepare,sample,returnTiming,anchor,fk,localize,fromAxes,toAxes,qm,qinv,qlog,qexp,rotate,qslerp,fromTo,offsetBlend,add,sub,mul,dot,cross,length,unit};
if(typeof module!=='undefined')module.exports=api;else root.Recovery=api;
})(globalThis);
