/* Isolated airborne-motion experiment. Recorded articulation, no ground torque.
 * Does not replace the main lab's opposite-angle compensation controls. */
(function(root){
'use strict';
const node=typeof module!=='undefined',R=node?require('./recovery.js'):root.Recovery,C=node?require('./core.js'):root.BodyflipCore,H=node?require('./attack-inertia.js'):root.BodyflipAttackInertia;
const {add,sub,mul,dot,length,unit,rotate,qm,qinv,qlog,qexp}=R,clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
function center(bs,rig){const mass=rig.reduce((s,b)=>s+b.mass,0);return rig.reduce((p,b,i)=>add(p,mul(bs[i].center,b.mass/mass)),[0,0,0]);}
function transform(pose,rotation,origin,destination){return {points:pose.points.map(p=>add(destination,rotate(rotation,sub(p,origin)))),q:pose.q.map(q=>unit(qm(rotation,q))),axes:pose.q.map(q=>R.toAxes(qm(rotation,q)))};}
function solve(columns,b){
 const size=b.length,rows=b.map((_,i)=>[...columns.map(c=>c[i]),b[i]]);
 for(let i=0;i<size;i++){
  let p=i;for(let j=i+1;j<size;j++)if(Math.abs(rows[j][i])>Math.abs(rows[p][i]))p=j;
  if(Math.abs(rows[p][i])<1e-10)throw Error('Singular airborne inertia');
  [rows[p],rows[i]]=[rows[i],rows[p]];const d=rows[i][i];for(let k=i;k<=size;k++)rows[i][k]/=d;
  for(let j=0;j<size;j++)if(j!==i){const d=rows[j][i];for(let k=i;k<=size;k++)rows[j][k]-=d*rows[i][k];}
 }
 return rows.map(r=>r[size]);
}
// C2 interpolation: the balance solve reacts to velocity, so acceleration
// breaks at 30 Hz source keys were visible as jolts in the pelvis/knee path.
// Keep every recorded key/time, with one continuous velocity and acceleration.
const curveCache=new WeakMap();
function curve(values,f){
 const last=values.length-1,i=clamp(Math.floor(f),0,last-1),u=f-i;
 let seconds=curveCache.get(values);
 if(!seconds){seconds=values[0].map((_,axis)=>{const d=values.map(()=>0),b=values.map(()=>4),upper=values.map(()=>1),lower=values.map(()=>1),rhs=values.map((_,j)=>j>0&&j<last?6*(values[j+1][axis]-2*values[j][axis]+values[j-1][axis]):0);b[0]=values.startDerivative?2:1;upper[0]=values.startDerivative?1:0;b[last]=values.endDerivative?2:1;lower[last]=values.endDerivative?1:0;if(values.startDerivative)rhs[0]=6*(values[1][axis]-values[0][axis]-values.startDerivative[axis]);if(values.endDerivative)rhs[last]=6*(values.endDerivative[axis]-values[last][axis]+values[last-1][axis]);for(let j=1;j<=last;j++){const s=lower[j]/b[j-1];b[j]-=s*upper[j-1];rhs[j]-=s*rhs[j-1];}d[last]=rhs[last]/b[last];for(let j=last-1;j>=0;j--)d[j]=(rhs[j]-upper[j]*d[j+1])/b[j];return d;});curveCache.set(values,seconds);}
 return values[0].map((_,axis)=>{
  const d=seconds[axis];
  if(f<0)return values[0][axis]+f*(values[1][axis]-values[0][axis]-d[1]/6);
  if(f>last)return values[last][axis]+(f-last)*(values[last][axis]-values[last-1][axis]+d[last-1]/6);
  const a=1-u;return a*values[i][axis]+u*values[i+1][axis]+((a*a*a-a)*d[i]+(u*u*u-u)*d[i+1])/6;
 });
}
function recording({clip,names,parents,reference,lead=.18,tail=.45,directArmed=false}){
 // Final Harness: Armed is no earlier than its authored time; thereafter
 // source time advances at 1x. Direct mode replaces only the pre-Armed path.
 const sourceStart=directArmed?clip.meta.phases.armed:0;
 if(directArmed)lead=Math.max(lead,sourceStart/clip.meta.fps,1/60);
 const locals=clip.poses.map(p=>R.localize(p.points,p.q,parents)),rest=R.localize(reference.points,reference.q,parents),pelvis=names.indexOf('pelvis');
 const hinges=H.legHinges(names,reference),kneeCurves=[];
 // The exported clip contains shin twist (especially Kick R's chamber).
 // Reconstruct the same leg plane using hip rotation and one knee hinge.
 // Preserve ankle orientation; do not import that twist into the knee.
 for(const h of hinges){
  const ru=unit(sub(reference.points[h.knee],reference.points[h.hip])),rv=unit(sub(reference.points[h.foot],reference.points[h.knee])),rn=unit(R.cross(ru,rv));
  const frame=(u,n)=>R.fromAxes([u,n,unit(R.cross(u,n))]),inverse=qinv(frame(ru,rn)),restBend=Math.acos(clamp(dot(ru,rv),-1,1)),bends=[];
  for(let f=0;f<locals.length;f++){
   const pose=clip.poses[f],u=unit(sub(pose.points[h.knee],pose.points[h.hip])),v=unit(sub(pose.points[h.foot],pose.points[h.knee])),normal=unit(R.cross(u,v)),bend=Math.acos(clamp(dot(u,v),-1,1));
   const hip=qm(qm(frame(u,normal),inverse),reference.q[h.hip]),knee=qm(rest.q[h.knee],qexp(mul(h.kneeAxis,bend-restBend))),calf=qm(hip,knee);
   locals[f].q[h.hip]=qm(qinv(pose.q[parents[h.hip]]),hip);locals[f].q[h.knee]=knee;locals[f].q[h.foot]=qm(qinv(calf),pose.q[h.foot]);bends.push([bend]);
  }
  kneeCurves.push({h,bends,restBend});
 }
 const vectors=names.map((_,j)=>locals.map(p=>qlog(qm(p.q[j],qinv(locals[0].q[j])))));
 // Unwrap the same rotation-vector branch before interpolation.
 for(const a of vectors)for(let i=1;i<a.length;i++){const n=length(a[i]);if(n>1e-8){const axis=mul(a[i],1/n),turns=Math.round(dot(sub(a[i-1],a[i]),axis)/(2*Math.PI));a[i]=add(a[i],mul(axis,turns*2*Math.PI));}}
 function at(frame){
  const q=vectors.map((v,j)=>unit(qm(qexp(curve(v,frame)),locals[0].q[j])));
  for(const {h,bends,restBend} of kneeCurves)q[h.knee]=qm(rest.q[h.knee],qexp(mul(h.kneeAxis,curve(bends,frame)[0]-restBend)));
  q[0]=rest.q[0];q[pelvis]=qm(qm(rest.q[pelvis],qinv(locals[0].q[pelvis])),q[pelvis]);
  return R.fk({p:rest.p,q},parents);
 }
 const duration=(clip.poses.length-1)/clip.meta.fps,end=lead+duration-sourceStart/clip.meta.fps,stop=end+tail;
 const h=1e-4;
 // Interpolate in hierarchy-local rotation space, preserving hinge axes and
 // sockets. Match the target's velocity/acceleration to avoid stopping at Armed.
 const startLocal=R.localize(at(sourceStart).points,at(sourceStart).q,parents),nextLocal=R.localize(at(sourceStart+h*clip.meta.fps).points,at(sourceStart+h*clip.meta.fps).q,parents),prevLocal=R.localize(at(sourceStart-h*clip.meta.fps).points,at(sourceStart-h*clip.meta.fps).q,parents);
 const startErrors=startLocal.q.map((q,i)=>qlog(qm(q,qinv(rest.q[i])))),startNext=nextLocal.q.map((q,i)=>qlog(qm(q,qinv(rest.q[i])))),startPrev=prevLocal.q.map((q,i)=>qlog(qm(q,qinv(rest.q[i]))));
 const rawEntry=t=>{const u=clamp(t/lead,0,1);return R.fk({p:rest.p,q:rest.q.map((q,i)=>{const e=startErrors[i],v=mul(sub(startNext[i],startPrev[i]),lead/(2*h)),a=mul(add(sub(startNext[i],mul(e,2)),startPrev[i]),lead*lead/(h*h)),x=add(add(mul(e,10*u**3-15*u**4+6*u**5),mul(v,-4*u**3+7*u**4-3*u**5)),mul(a,.5*u**3-u**4+.5*u**5));return qm(qexp(x),q);})},parents);};
 // A C2 quaternion entry can overshoot straight knees when Armed has a high
 // incoming velocity. Use a bounded scalar hinge coordinate only for those
 // entry curves; existing valid entries and all recorded keys remain unchanged.
 const bounded=[],entryStep=h;
 for(const {h,restBend} of kneeCurves){
  const i=h.knee,bend=q=>restBend+dot(qlog(qm(qinv(rest.q[i]),q)),h.kneeAxis);
  let unsafe=false;
  for(let n=0;n<=64;n++){const p=rawEntry(lead*n/64),angle=bend(qm(qinv(p.q[parents[i]]),p.q[i]));if(angle<0||angle>Math.PI){unsafe=true;break;}}
  if(!unsafe)continue;
  const b=clamp(bend(startLocal.q[i]),1e-10,Math.PI-1e-10),v=(bend(nextLocal.q[i])-bend(prevLocal.q[i]))/(2*entryStep),a=(bend(nextLocal.q[i])-2*b+bend(prevLocal.q[i]))/(entryStep*entryStep);
  const logit=x=>Math.log(x/(Math.PI-x)),d=Math.PI/(b*(Math.PI-b)),dd=-Math.PI*(Math.PI-2*b)/(b*b*(Math.PI-b)*(Math.PI-b));
  bounded.push({h,restBend,from:logit(restBend),to:logit(b),v:d*v*lead,a:(d*a+dd*v*v)*lead*lead});
 }
 function entry(t){
  const pose=rawEntry(t);if(!bounded.length)return pose;
  const local=R.localize(pose.points,pose.q,parents),u=clamp(t/lead,0,1);
  for(const b of bounded){const z=b.from+(b.to-b.from)*(10*u**3-15*u**4+6*u**5)+b.v*(-4*u**3+7*u**4-3*u**5)+b.a*(.5*u**3-u**4+.5*u**5),angle=Math.PI/(1+Math.exp(-z));
   local.q[b.h.knee]=qm(rest.q[b.h.knee],qexp(mul(b.h.kneeAxis,angle-b.restBend)));
  }
  return R.fk(local,parents);
 }
 // Brake the terminal motion without carrying its sideways velocity through
 // most of the return. Critical decay preserves the initial derivative; a C2
 // end window reaches the reference pose without a hard stop or knee spread.
 const last=R.localize(at(clip.poses.length-1).points,at(clip.poses.length-1).q,parents),before=R.localize(at((duration-h)*clip.meta.fps).points,at((duration-h)*clip.meta.fps).q,parents),before2=R.localize(at((duration-2*h)*clip.meta.fps).points,at((duration-2*h)*clip.meta.fps).q,parents);
 const errors=last.q.map((q,i)=>qlog(qm(q,qinv(rest.q[i])))),prevErrors=before.q.map((q,i)=>qlog(qm(q,qinv(rest.q[i])))),prev2Errors=before2.q.map((q,i)=>qlog(qm(q,qinv(rest.q[i])))),rates=errors.map((v,i)=>mul(add(sub(mul(v,3),mul(prevErrors[i],4)),prev2Errors[i]),1/(2*h))),accelerations=errors.map((v,i)=>mul(add(sub(v,mul(prevErrors[i],2)),prev2Errors[i]),1/(h*h)));
 const exit=t=>{const x=clamp(t/tail,0,1),window=1-x*x*x*(10+x*(-15+6*x)),w=8/tail,decay=Math.exp(-w*t);return R.fk({p:rest.p,q:rest.q.map((q,i)=>{const a=errors[i],b=add(rates[i],mul(a,w)),c=mul(add(add(accelerations[i],mul(rates[i],2*w)),mul(a,w*w)),.5);return qm(qexp(mul(add(add(a,mul(b,t)),mul(c,t*t)),decay*window)),q);})},parents);};
 function sample(t){if(t<=0)return reference;if(t<lead)return entry(t);if(t<=end)return at(sourceStart+(t-lead)*clip.meta.fps);if(t<stop)return exit(t-end);return reference;}
 const strikeWeight=t=>{const x=clamp((t-end)/tail,0,1);return 1-x*x*x*(10+x*(-15+6*x));};
 return {sample,at,lead,end,stop,clip,hinges,strikeWeight,directArmed,sourceStart,armedTime:lead+(clip.meta.phases.armed-sourceStart)/clip.meta.fps,sourceFrame:t=>sourceStart+Math.max(0,t-lead)*clip.meta.fps};
}
// Treat the authored heading as a prescribed body turn, independent of the
// zero-spin balance solve for articulation. Sampling/unwrapping a scalar yaw
// preserves revolutions which a single shortest quaternion cannot represent.
function bodyTurn(track,names,reference){
 const pelvis=names.indexOf('pelvis'),forward=rotate(qinv(reference.q[pelvis]),[0,0,1]);
 const count=Math.ceil(track.stop*120),dt=track.stop/count,angles=[];
 for(let i=0;i<=count;i++){
  const p=track.sample(i*dt),f=rotate(p.q[pelvis],forward),previous=i?angles[i-1][0]:0;
  const angle=Math.hypot(f[0],f[2])<1e-7?previous:Math.atan2(f[0],f[2]);
  angles.push([previous+Math.atan2(Math.sin(angle-previous),Math.cos(angle-previous))]);
 }
 angles.startDerivative=[0];angles.endDerivative=[0];
 const angleAt=t=>curve(angles,clamp(t/dt,0,count))[0],rotationAt=t=>qexp([0,angleAt(t),0]);
 const origin=reference.points[pelvis];
 function rotateBody(pose,q,pivot){
  const result=transform(pose,q,pivot,pivot);
  // Root is the locomotion anchor, not a physical body. Changing its axes
  // would put the removed turn back into pelvis-local recovery and lose it
  // again when the main app restores the root trajectory.
  result.points[0]=pose.points[0].slice();result.q[0]=pose.q[0].slice();result.axes[0]=pose.axes[0];return result;
 }
 const remove=t=>rotateBody(track.sample(t),qinv(rotationAt(t)),origin);
 function restore(plan){
  const carry=(pose,t)=>rotateBody(pose,rotationAt(t),plan.center);
  return {...plan,sample:t=>carry(plan.sample(t),t),uncorrected:t=>carry(plan.uncorrected(t),t),samplePlanned:t=>carry(plan.samplePlanned(t),t),authoredTurn:{rotationAt,angleAt}};
 }
 return {rotationAt,remove,restore};
}
function create({source,names,parents,reference,duration,sampleRate=120,angularMomentum=[0,0,0],trajectory=null,preserve=[]}){
 const rig=H.model(names,parents,reference),dt=1/sampleRate,count=Math.ceil(duration/dt),first=source(0),origin=center(H.bodies(first,rig),rig),comAt=trajectory||(()=>origin),states=[{q:[0,0,0,1],rate:[0,0,0]}];
 const chains=preserve.map(({bone,weight=()=>1})=>{
  if(!(bone>0&&bone<names.length))throw Error('Preserved strike needs a valid limb root');
  return {bone,weight,indices:names.map((_,i)=>i).filter(i=>{for(let j=i;j>=0;j=parents[j])if(j===bone)return true;return false;})};
 });
 function poseAt(raw,q,t){
  const rawCenter=center(H.bodies(raw,rig),rig),pose=transform(raw,q,rawCenter,comAt(t));
  for(const {bone,weight,indices} of chains){
   const w=clamp(weight(t),0,1),anchor=pose.points[bone],limbQ=R.qslerp(pose.q[bone],raw.q[bone],w),turn=qm(limbQ,qinv(raw.q[bone]));
   // Keep the active chain's world direction, knee articulation and ankle
   // orientation. The hip absorbs the inverse body correction, just as
   // spine_01 does for the main lab's upper-body attacks.
   for(const i of indices){pose.points[i]=add(anchor,rotate(turn,sub(raw.points[i],raw.points[bone])));pose.q[i]=unit(qm(turn,raw.q[i]));pose.axes[i]=R.toAxes(pose.q[i]);}
  }
  // Counter-rotation of a limb changes the body's COM. Recenter the complete
  // skeleton, so preserving the strike never creates a linear impulse.
  if(chains.length){const shift=sub(comAt(t),center(H.bodies(pose,rig),rig));pose.points=pose.points.map(p=>add(p,shift));}
  return pose;
 }
 let previous=H.bodies(transform(first,states[0].q,origin,comAt(0)),rig);
 const diagnostics={ticks:0,maxResidual:0,maxCorrectionStep:0,sampleRate,angularMomentum:angularMomentum.slice()};
 function advance(){
  const n=states.length,t=n*dt,raw=source(t),last=states[n-1];
  const candidate=q=>{const pose=poseAt(raw,q,t),bs=H.bodies(pose,rig);return {q,bs,h:H.momentum(previous,bs,rig,dt)};};
  let next=candidate(unit(qm(qexp(mul(last.rate,dt)),last.q)));
  for(let pass=0;pass<5;pass++){
   const error=sub(angularMomentum,next.h);if(length(error)<1e-8)break;
   const columns=[0,1,2].map(axis=>{const v=[0,0,0];v[axis]=1e-5;return mul(sub(candidate(qm(qexp(v),next.q)).h,next.h),1e5);});
   const delta=solve(columns,error);next=candidate(unit(qm(qexp(delta),next.q)));
  }
  const step=qlog(qm(next.q,qinv(last.q))),rate=mul(step,1/dt),residual=length(sub(next.h,angularMomentum));
  if(!Number.isFinite(residual)||residual>1e-4)throw Error('Airborne momentum solve failed: '+residual);
  states.push({q:next.q,rate});previous=next.bs;diagnostics.ticks++;diagnostics.maxResidual=Math.max(diagnostics.maxResidual,residual);diagnostics.maxCorrectionStep=Math.max(diagnostics.maxCorrectionStep,length(step));
 }
 function rotationAt(t){
  const f=clamp(t/dt,0,count),i=Math.floor(f),u=f-i;
  // One neighbour on each side supplies a continuous angular velocity at
  // cache boundaries. The source animation is sampled at the actual time.
  while(states.length<=Math.min(count,i+2))advance();
  if(i===count)return states[i].q;
  const a=states[i].q,b=states[i+1].q;
  const v0=i?mul(add(states[i].rate,states[i+1].rate),.5):states[1].rate;
  const v1=i+2<=count?mul(add(states[i+1].rate,states[i+2].rate),.5):states[i+1].rate;
  // Spherical Bezier: exact keys and endpoint angular velocities. A linear
  // quaternion or rotation-vector interpolation would leave velocity jumps.
  const c=qm(qexp(mul(v0,dt/3)),a),d=qm(qexp(mul(v1,-dt/3)),b),s=R.qslerp;
  return s(s(s(a,c,u),s(c,d,u),u),s(s(c,d,u),s(d,b,u),u),u);
 }
 function sample(t){t=clamp(t,0,count*dt);return poseAt(source(t),rotationAt(t),t);}
 function uncorrected(t){const raw=source(t),com=center(H.bodies(raw,rig),rig);return transform(raw,[0,0,0,1],com,comAt(t));}
 return {sample,uncorrected,rotationAt,states,rig,diagnostics,center:origin,duration:count*dt};
}
// Keep the current striking-chain animation while distributing balance over
// the body turn, torso, free hip/knee and shoulders. Penalize pelvis rotation
// and sideways free-hip motion; allow forward/backward counter-swing. COM is
// recentered, and the three angular-momentum equations leave posture freedom.
function createBalanced({source,names,parents,reference,duration,strikeRoot,strikeWeight=()=>1,sampleRate=120,angularMomentum=[0,0,0],trajectory=null,recoveryStart=Infinity,recoveryEnd=Infinity}){
 const rig=H.model(names,parents,reference),hinges=H.legHinges(names,reference),active=hinges.find(h=>h.hip===strikeRoot),free=hinges.find(h=>h.hip!==strikeRoot);
 if(!active)throw Error('Balanced kick needs its striking thigh');
 const p=names.indexOf('pelvis'),spine=names.indexOf('spine_01'),dt=1/sampleRate,count=Math.ceil(duration/dt),first=source(0),origin=center(H.bodies(first,rig),rig),comAt=trajectory||(()=>origin);
 const shoulders=['upperarm_l','upperarm_r'].map(n=>names.indexOf(n)),penalty=[100,100,40,4,5,4,60,60,2,3,2,2,2,2,2,2],states=[{x:penalty.map(()=>0),v:penalty.map(()=>0)}],mobility=penalty.map(v=>1/v),zero=Array(3).fill(0);
 let previous=H.bodies(transform(first,[0,0,0,1],origin,comAt(0)),rig);
 const diagnostics={ticks:0,maxResidual:0,maxCOMResidual:0,maxPelvisCorrection:0,maxFreeLateral:0,sampleRate};
 function prepare(t){const raw=source(t),local=R.localize(raw.points,raw.q,parents),offset=sub(comAt(t),center(H.bodies(raw,rig),rig)),hip=add(raw.points[active.hip],offset),u=unit(sub(raw.points[free.knee],raw.points[free.hip])),v=unit(sub(raw.points[free.foot],raw.points[free.knee]));return {raw,local,hip,bend:Math.acos(clamp(dot(u,v),-1,1)),t};}
 function poseAt(data,x,recenter=false){
  const {raw,local,hip,bend,t}=data,q=local.q.slice(),frame=reference.q[p],around=v=>qm(qm(frame,qexp(v)),qinv(frame)),body=around(x.slice(0,3)),pelvis=qm(body,raw.q[p]),upper=qm(qm(body,around(x.slice(3,6))),raw.q[spine]),freeHip=qm(qm(body,around(x.slice(6,9))),raw.q[free.hip]),activeHip=R.qslerp(qm(body,raw.q[active.hip]),raw.q[active.hip],strikeWeight(t));
  q[p]=qm(qinv(raw.q[parents[p]]),pelvis);q[spine]=qm(qinv(pelvis),upper);q[active.hip]=qm(qinv(pelvis),activeHip);q[free.hip]=qm(qinv(pelvis),freeHip);
  for(let i=0;i<shoulders.length;i++){const bone=shoulders[i];q[bone]=qm(qinv(raw.q[parents[bone]]),qm(around(x.slice(10+i*3,13+i*3)),raw.q[bone]));}
  // Smoothly parameterize a hinged knee inside its available flexion range.
  const limit=150*Math.PI/180,fraction=clamp(bend/limit,1e-6,1-1e-6),goal=limit/(1+Math.exp(-(Math.log(fraction/(1-fraction))+x[9])));
  q[free.knee]=qm(local.q[free.knee],qexp(mul(free.kneeAxis,goal-bend)));
  const pose=R.fk({p:local.p,q},parents),shift=sub(hip,pose.points[active.hip]);pose.points=pose.points.map(v=>add(v,shift));
  if(recenter){const correction=sub(comAt(t),center(H.bodies(pose,rig),rig));pose.points=pose.points.map(v=>add(v,correction));}
  return pose;
 }
 function advance(){
  const n=states.length,t=n*dt,data=prepare(t),last=states[n-1],targetCOM=comAt(t);
  const candidate=x=>{const pose=poseAt(data,x),offset=sub(center(H.bodies(pose,rig),rig),targetCOM);pose.points=pose.points.map(v=>sub(v,offset));const bs=H.bodies(pose,rig),h=sub(H.momentum(previous,bs,rig,dt),angularMomentum),com=sub(center(bs,rig),targetCOM);return {x,bs,h,com,offset,error:mul(h,dt)};};
  const activeWeight=strikeWeight(t),frameMobility=mobility.map((v,i)=>i<3?v*(1+99*(1-activeWeight)):i>=6&&i<=9?v*(.2+.8*activeWeight):v);
  // During recovery, let the common body orientation carry the remaining
  // momentum while the joints return. Keeping pelvis resistance high here
  // would hold the free leg out to avoid turning the body as a whole.
  const w=10,desired=last.x.map((v,i)=>i<3?v+last.v[i]*Math.exp(-10*activeWeight*dt)*dt:v+(last.v[i]+(-w*w*v-2*w*last.v[i])*dt)*dt);
  let next=candidate(desired);
  for(let pass=0;pass<12;pass++){
   if(length(next.error)<1e-9)break;
   const columns=next.x.map((_,j)=>{const x=next.x.slice();x[j]+=1e-5;return mul(sub(candidate(x).error,next.error),1e5);});
   const gram=zero.map((_,a)=>columns.reduce((sum,c,j)=>add(sum,mul(c,c[a]*frameMobility[j])),zero));
   for(let i=0;i<3;i++)gram[i][i]+=1e-10;
   const lambda=solve(gram,mul(next.error,-1)),delta=columns.map((c,j)=>dot(c,lambda)*frameMobility[j]);
   let scale=Math.min(1,.3/Math.max(1e-10,length(delta))),trial=candidate(add(next.x,mul(delta,scale)));
   for(let k=0;k<5&&length(trial.error)>length(next.error);k++){scale*=.5;trial=candidate(add(next.x,mul(delta,scale)));}
   next=trial;
  }
  if(!Number.isFinite(length(next.error))||length(next.error)>1e-5)throw Error('Balanced kick solve failed at '+t+': '+length(next.error));
  states.push({x:next.x,v:mul(sub(next.x,last.x),1/dt)});previous=next.bs;diagnostics.ticks++;
  diagnostics.maxResidual=Math.max(diagnostics.maxResidual,length(next.h));diagnostics.maxCOMResidual=Math.max(diagnostics.maxCOMResidual,length(next.com));diagnostics.maxPelvisCorrection=Math.max(diagnostics.maxPelvisCorrection,length(next.x.slice(0,3)));diagnostics.maxFreeLateral=Math.max(diagnostics.maxFreeLateral,Math.hypot(next.x[6],next.x[7]));
 }
 function stateAt(t){
  const f=clamp(t/dt,0,count),i=Math.floor(f),u=f-i;while(states.length<=Math.min(count,i+2))advance();if(i===count)return states[i].x;
  const a=states[i],b=states[i+1],v0=i?mul(add(a.v,b.v),.5):b.v,v1=i+2<=count?mul(add(b.v,states[i+2].v),.5):b.v;
  return a.x.map((v,j)=>(2*u**3-3*u*u+1)*v+(u**3-2*u*u+u)*dt*v0[j]+(-2*u**3+3*u*u)*b.x[j]+(u**3-u*u)*dt*v1[j]);
 }
 const filtered=[{x:penalty.map(()=>0),v:penalty.map(()=>0)}],goals=[];
 function response(state,a,b,elapsed){
  if(elapsed<=0)return state;const w=24,e=Math.exp(-w*elapsed),x=[],v=[];
  for(let j=0;j<a.length;j++){const speed=(b[j]-a[j])/elapsed,offset=-2*speed/w,z=state.x[j]-a[j]-offset,d=state.v[j]-speed,c=d+w*z;x[j]=b[j]+offset+(z+c*elapsed)*e;v[j]=speed+(d-w*c*elapsed)*e;}return {x,v};
 }
 function responseAt(t){
  const f=clamp(t/dt,0,count),i=Math.floor(f),u=f-i;
  goals[0] ||= stateAt(.06);
  while(filtered.length<=Math.min(count,i+1)){const j=filtered.length;goals[j]=stateAt(j*dt+.06);filtered.push(response(filtered[j-1],goals[j-1],goals[j],dt));}
  if(i===count)return filtered[i].x;
  return response(filtered[i],goals[i],goals[i].map((v,j)=>v+(goals[i+1][j]-v)*u),u*dt).x;
 }
 // Filter the articulated response, then solve the remaining common body
 // turn again. Smoothing must not silently inject angular momentum. The
 // striking chain still uses the current, unfiltered recording.
 const displayStates=[{x:[0,0,0],v:[0,0,0]}];let displayedPrevious=H.bodies(transform(first,[0,0,0,1],origin,comAt(0)),rig),displayCurve=null;
 diagnostics.maxDisplayedResidual=0;diagnostics.maxDisplayedPelvis=0;
 function advanceDisplay(){
  const j=displayStates.length,t=j*dt,data=prepare(t),coords=responseAt(t),last=displayStates[j-1];
  const candidate=x=>{const full=[...x,...coords.slice(3)],bs=H.bodies(poseAt(data,full,true),rig);return {x,bs,h:H.momentum(displayedPrevious,bs,rig,dt)};};
  let next=candidate(add(last.x,mul(last.v,dt)));
  for(let pass=0;pass<5;pass++){const error=sub(angularMomentum,next.h);if(length(error)<1e-8)break;const columns=next.x.map((_,i)=>{const x=next.x.slice();x[i]+=1e-5;return mul(sub(candidate(x).h,next.h),1e5);});next=candidate(add(next.x,solve(columns,error)));}
  const residual=length(sub(angularMomentum,next.h));if(!Number.isFinite(residual)||residual>1e-4)throw Error('Displayed kick momentum solve failed: '+residual);
  displayStates.push({x:next.x,v:mul(sub(next.x,last.x),1/dt)});displayedPrevious=next.bs;diagnostics.maxDisplayedResidual=Math.max(diagnostics.maxDisplayedResidual,residual);diagnostics.maxDisplayedPelvis=Math.max(diagnostics.maxDisplayedPelvis,length(next.x));
 }
 function displayAt(t){
  if(!displayCurve){while(displayStates.length<=count)advanceDisplay();displayCurve=displayStates.map(s=>s.x);displayCurve.startDerivative=[0,0,0];displayCurve.endDerivative=mul(displayStates[count].v,dt);}
  return curve(displayCurve,clamp(t/dt,0,count));
 }
 // Preserve the conserved strike, then return all attack-added rotations to
 // the source pose. COM still follows its path; the requested upright return
 // deliberately relaxes angular-momentum conservation during recovery.
 function sample(t){t=clamp(t,0,count*dt);const weight=R.returnWeight(t,recoveryStart,recoveryEnd);return poseAt(prepare(t),[...displayAt(t),...responseAt(t).slice(3)].map(v=>v*weight),true);}
 function samplePlanned(t){t=clamp(t,0,count*dt);return poseAt(prepare(t),stateAt(t),true);}
 function uncorrected(t){const raw=source(t);return transform(raw,[0,0,0,1],center(H.bodies(raw,rig),rig),comAt(t));}
 return {sample,samplePlanned,uncorrected,stateAt,responseAt,displayAt,displayStates,states,rig,diagnostics,center:origin,duration:count*dt,recoveryStart,recoveryEnd};
}
// Pelvis-only post-impact return, preserving the live source follow-through.
function returnFromHit(plan,{start,end,parents,pelvis}){
 if(!(Number.isFinite(start)&&Number.isFinite(end)&&end>start&&end<=plan.duration))throw Error('Hit return needs an existing recovery interval');
 const target=plan.sample(0),targetCOM=center(H.bodies(target,plan.rig),plan.rig),returning=R.pelvisReturn({source:plan.sample,base:()=>target,parents,start,end,pelvis});
 function sample(t){
  if(t<=start)return plan.sample(t);
  const pose=returning.sample(t);
  const shift=sub(targetCOM,center(H.bodies(pose,plan.rig),plan.rig));pose.points=pose.points.map(p=>add(p,shift));
  return pose;
 }
 return {...plan,sample,returnStart:start,recoveryStart:start,recoveryEnd:end,returnMode:'pelvis-from-hit'};
}
const api={create,createBalanced,returnFromHit,recording,bodyTurn,center,transform};if(node)module.exports=api;else root.BodyflipAirborneMotion=api;
})(globalThis);
