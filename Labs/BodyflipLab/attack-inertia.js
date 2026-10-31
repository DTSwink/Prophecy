/* Three-axis airborne attack response. Deterministic bounded cache; no Jolt/NN worker. */
(function(root){
'use strict';
const node=typeof module!=='undefined',R=node?require('./recovery.js'):root.Recovery,T=node?require('./torso.js'):root.BodyflipTorso,L=node?require('./leg-response.js'):root.BodyflipLegResponse;
const {add,sub,mul,dot,cross,length,unit,rotate,qm,qinv,qexp,qlog}=R;
const J=node?require('./joint-rig.js'):root.BodyflipJointRig,M=node?require('./mass.js'):root.BodyflipMass;
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
function model(names,parents,reference){
 const profile=(node?require('./rig-profile.js'):root.BodyflipRigProfile)?.current();if(profile)return profile.bodies;
 const torso=new Map(T.create(names,parents,reference).map(s=>[s.bone,s]));
 return names.slice(1).map((name,j)=>{
  const i=j+1,mass=name==='pelvis'?8:name.startsWith('thigh')?5:name.startsWith('spine')?2:1;
  const child=parents.findIndex((p,k)=>p===i&&!names[k].startsWith('clavicle')&&!names[k].startsWith('thigh'));
  const delta=child>0?sub(reference.points[child],reference.points[i]):rotate(reference.q[i],[name==='head'?.12:.045,0,0]);
  const l=length(delta),offset=rotate(qinv(reference.q[i]),mul(delta,.5)),box=torso.get(i);
  const radius=name==='pelvis'?.105:name==='head'?.09:name.startsWith('thigh')?.065:name.startsWith('calf')?.045:.032;
  // Match the lab's body masses/centres. Capsule inertia is a cylinder+caps
  // approximation; boxes use the shared torso dimensions exactly.
  if(box){const [x,y,z]=box.dims;return {i,mass,offset:box.offset,rotation:box.rotation,inertia:[mass*(y*y+z*z)/12,mass*(x*x+z*z)/12,mass*(x*x+y*y)/12]};}
  const axis=rotate(qinv(reference.q[i]),unit(delta)),axial=mass*radius*radius*.5,transverse=mass*(l*l/12+radius*radius*.25);
  return {i,mass,offset,axis,axial,transverse};
 });
}
function bodies(pose,rig){return rig.map(b=>({center:add(pose.points[b.i],rotate(pose.q[b.i],b.offset)),q:pose.q[b.i]}));}
function momentumFrom(a,rig,dt,fixedPose=null,fixedBones=null){
 const total=rig.reduce((v,b)=>v+b.mass,0),ca=rig.reduce((v,r,i)=>add(v,mul(a[i].center,r.mass/total)),[0,0,0]),inverse=a.map(b=>qinv(b.q));
 function spinAt(i,b){
  const r=rig[i],q=R.qslerp(a[i].q,b.q,.5),omega=mul(qlog(qm(b.q,inverse[i])),1/dt);
  if(r.inertia){const frame=qm(q,r.rotation),w=rotate(qinv(frame),omega);return rotate(frame,w.map((v,j)=>v*r.inertia[j]));}
  const axis=rotate(q,r.axis);return add(mul(omega,r.transverse),mul(axis,(r.axial-r.transverse)*dot(omega,axis)));
 }
 // Counter-rotating spine_01 preserves all upper-body orientations. Their
 // spin terms are identical during every trial; only orbital terms change.
 const spins=rig.map((r,i)=>fixedBones?.[r.i]?spinAt(i,fixedPose[i]):null);
 return b=>{
  const cb=rig.reduce((v,r,i)=>add(v,mul(b[i].center,r.mass/total)),[0,0,0]);
  const com=mul(add(ca,cb),.5),velocity=mul(sub(cb,ca),1/dt);let h=[0,0,0];
  for(let i=0;i<rig.length;i++){
   const r=rig[i],spin=spins[i]||spinAt(i,b[i]);
   const v=sub(mul(sub(b[i].center,a[i].center),1/dt),velocity),arm=sub(mul(add(a[i].center,b[i].center),.5),com);
   h=add(h,add(spin,mul(cross(arm,v),r.mass)));
  }
  return h;
 };
}
function momentum(a,b,rig,dt){return momentumFrom(a,rig,dt)(b);}

function legHinges(names,reference){
 return ['l','r'].map(side=>{
  const hip=names.indexOf('thigh_'+side),knee=names.indexOf('calf_'+side),foot=names.indexOf('foot_'+side);
  const incoming=unit(sub(reference.points[knee],reference.points[hip])),outgoing=unit(sub(reference.points[foot],reference.points[knee]));
  let axis=unit(cross(incoming,outgoing));if(length(axis)<.1)axis=rotate(reference.q[knee],[0,0,-1]);
  return {hip,knee,foot,hipAxis:rotate(qinv(reference.q[hip]),axis),kneeAxis:rotate(qinv(reference.q[knee]),axis)};
 });
}
// Approximate readings of the jump-throw mean curves in Wagner et al. (2011),
// Fig.2 A-D. Degrees; time is seconds relative to ball release. These are rounded
// graph readings, NOT original motion-capture data or a captured sword attack.
// https://www.jssm.org/mobile/ShowFigure.php?FigureId=fig002&jid=jssm-10-73.xml
const humanLegCurve=[
 // time, follow hip, follow knee, lead hip, lead knee
 [-.30,76,131,4,54],[-.25,68,119,0,59],[-.20,47,94,-2,61],
 [-.15,20,56,6,60],[-.10,2,26,35,55],[-.05,-3,21,60,40],
 [0,3,32,60,29],[.05,12,42,53,22],[.075,18,45,49,21]
];
// Shape-preserving cubic: continuous joint velocity without overshoot or a
// stop at each digitized point. Endpoint velocity is zero at the held ends.
function curveAt(a,t,j){
 let i=0;while(i<a.length-2&&t>a[i+1][0])i++;
 const h=a[i+1][0]-a[i][0],u=clamp((t-a[i][0])/h,0,1);
  const sec=k=>(a[k+1][j]-a[k][j])/(a[k+1][0]-a[k][0]);
  const slope=k=>{if(k===0||k===a.length-1)return 0;const x=sec(k-1),y=sec(k),h0=a[k][0]-a[k-1][0],h1=a[k+1][0]-a[k][0],w0=2*h1+h0,w1=h1+2*h0;return x*y<=0?0:(w0+w1)/(w0/x+w1/y);};
  return (2*u**3-3*u*u+1)*a[i][j]+(u**3-2*u*u+u)*h*slope(i)+(-2*u**3+3*u*u)*a[i+1][j]+(u**3-u*u)*h*slope(i+1);
}
const humanAngles=t=>[1,2,3,4].map(j=>curveAt(humanLegCurve,t,j)*Math.PI/180);
function referenceMotion({clip,names,parents,reference,start,armedTime,hitTime,end,returnEnd,amount}){
 const hinges=legHinges(names,reference),p=names.indexOf('pelvis'),spine=names.indexOf('spine_01');
 const at=f=>clip.poses[clamp(Math.round(f),0,clip.poses.length-1)],ph=clip.meta.phases||{};
 const a=at(ph.armed??clip.poses.length*.4),b=at(ph.hit??clip.poses.length*.7);
 // Blend coordination by measured upper-body rotation, never by attack ID.
 const upper=names.map((_,i)=>i).filter(i=>{for(let j=i;j>0;j=parents[j])if(j===spine)return true;return false;});
 let total=0,turn=[0,0,0];for(const i of upper){const mass=names[i].startsWith('spine')?2:1;total+=mass;turn=add(turn,mul(rotate(qinv(a.q[p]),qlog(qm(b.q[i],qinv(a.q[i])))),mass));}turn=mul(turn,1/total);
 const magnitude=length(turn),swing=Math.hypot(turn[1],turn[2]),twistShare=turn[0]**2/Math.max(1e-12,magnitude*magnitude),swingShare=1-twistShare;
 const tempoScale=clamp(Math.min((armedTime-start)/.14,(hitTime-armedTime)/.16),0,1);
 const follow=turn[0]>=0?1:0,strength=clamp(amount,0,1)*clamp(magnitude/(Math.PI/3),0,1)*tempoScale;
 // Qualitative heading reference (Kristensen 2002/2004): folded backswing,
 // opposing forward leg swing and near extension at impact. These angles are
 // authored coordination targets, not digitized experimental measurements.
 const swingCurve=[[-.30,0,35],[-.16,-20,85],[0,30,25],[.075,35,30]];
 const ease=x=>{x=clamp(x,0,1);return x*x*x*(10+x*(-15+6*x));};
 const clock=[[start,-.30],[armedTime,-.16],[hitTime,0],[hitTime+(hitTime-armedTime)*.075/.16,.075]];
 function sample(t,pose){
  if(t<=start||t>=returnEnd||strength===0)return pose;
  const weight=strength*ease((t-start)/Math.max(1/60,armedTime-start))*(1-ease((t-end)/Math.max(1/60,returnEnd-end)));
  // Armed = late cocking (-160ms); Hit = release. A monotone cubic clock
  // carries velocity through those boundaries and eases into follow-through.
  const phase=curveAt(clock,t,1);
  const values=humanAngles(phase),swingHip=curveAt(swingCurve,phase,1)*Math.PI/180,swingKnee=curveAt(swingCurve,phase,2)*Math.PI/180,local=R.localize(pose.points,pose.q,parents),up=rotate(pose.q[p],[1,0,0]),forward=rotate(pose.q[p],[0,-1,0]);
  for(let k=0;k<2;k++){
   const h=hinges[k],v=unit(sub(pose.points[h.knee],pose.points[h.hip])),w=unit(sub(pose.points[h.foot],pose.points[h.knee]));
   const hip=Math.atan2(dot(v,forward),-dot(v,up)),knee=Math.acos(clamp(dot(v,w),-1,1)),j=k===follow?0:2;
   const pitch=swing>1e-8?-turn[2]/swing:0,side=swing>1e-8?-turn[1]/swing:0;
   const hipTarget=twistShare*values[j]+swingShare*pitch*swingHip,kneeTarget=twistShare*values[j+1]+swingShare*swingKnee;
   const hipDelta=(hipTarget-hip)*weight,kneeDelta=(clamp(kneeTarget,5*Math.PI/180,150*Math.PI/180)-knee)*weight;
   // Flex in the pelvis sagittal plane; using the thigh's existing bend axis
   // here would turn a splayed leg sideways instead of bringing it forward.
   local.q[h.hip]=qm(qexp([0,swingShare*side*swingHip*weight,hipDelta]),local.q[h.hip]);
   local.q[h.knee]=qm(local.q[h.knee],qexp(mul(h.kneeAxis,kneeDelta)));
  }
  return R.fk(local,parents);
 }
 return {sample,follow,strength,tempoScale,armedTime,hitTime,rotation:turn,twistShare,swingShare,source:'Wagner 2011 jump throw; Kristensen 2002/2004 heading coordination'};
}
function apply(pose,names,parents,state,hinges){
 const local=R.localize(pose.points,pose.q,parents),p=names.indexOf('pelvis'),s=names.indexOf('spine_01'),counter=qexp([state.pelvis,0,0]);
 local.q[p]=qm(local.q[p],counter);local.q[s]=qm(qinv(counter),local.q[s]);
 for(let k=0;k<2;k++){
  const hip=names.indexOf('thigh_'+['l','r'][k]);local.q[hip]=qm(qexp([state.legs[k]-state.pelvis,0,0]),local.q[hip]);

 }
 return R.fk(local,parents);
}
// Critical angular spring, integrated exactly against a linearly moving target.
// Velocity is retained, rather than recomputed from an imposed angle. The same
// response on pelvis and legs smooths their relative yaw without a hard clamp.
// 32 rad/s gives roughly 63ms low-frequency lag; this intentionally relaxes the
// planner's instantaneous momentum equality while preserving its settled turn.
function respond(state,from,to,dt,frequency=32){
 if(dt<=0)return state;
 const decay=Math.exp(-frequency*dt);
 function joint(x,v,a,b){
  const speed=(b-a)/dt,offset=-2*speed/frequency,z=x-a-offset,d=v-speed,c=d+frequency*z;
  return [b+offset+(z+c*dt)*decay,speed+(d-frequency*c*dt)*decay];
 }
 const pelvis=joint(state.pelvis,state.pelvisRate,from.pelvis,to.pelvis),legs=state.legs.map((x,k)=>joint(x,state.rates[k],from.legs[k],to.legs[k]));
 return {pelvis:pelvis[0],pelvisRate:pelvis[1],legs:legs.map(v=>v[0]),rates:legs.map(v=>v[1])};
}
function createYaw({source,base,target,start,end,names,parents,reference,choreography=null,wholeLeg=false}){
 const rig=model(names,parents,reference),hinges=legHinges(names,reference),dt=1/120,stop=end+.8,count=Math.ceil((stop-start)/dt),p=names.indexOf('pelvis');
 const states=[{pelvis:0,pelvisRate:0,legs:[0,0],rates:[0,0]}],plans=[states[0]],initial=source(start),first={bodies:bodies(initial,rig),target:bodies(target(start,initial,base(start)),rig)};let history=first;
 const diagnostics={ticks:0,maxPlannedResidual:0,maxLag:0,maxStep:0,maxAcceleration:0,maxPlannedAcceleration:0};
 function advance(){
  const n=states.length,t=start+n*dt,prev=plans[n-1],plain=source(t),raw=choreography?choreography.sample(t,plain):plain,baseline=base(t),rawBodies=bodies(raw,rig),targetBodies=bodies(target(t,plain,baseline),rig),axis=rotate(baseline.q[p],[1,0,0]);
  const targetH=dot(momentum(history.target,targetBodies,rig,dt),axis);
  // Independent hip springs. A bent/extended leg has a different yaw inertia,
  // so its response comes from its current geometry rather than a left/right delay.
  const desired=prev.legs.map((angle,k)=>{
   const hip=names.indexOf('thigh_'+['l','r'][k]),origin=raw.points[hip];let inertia=0;
   for(let j=0;j<rig.length;j++){let bone=rig[j].i;while(bone>0&&bone!==hip)bone=parents[bone];if(bone!==hip)continue;
    const arm=sub(rawBodies[j].center,origin),b=rig[j],spin=b.native?R.toAxes(qm(raw.q[b.i],b.rotation)).reduce((v,a,k)=>v+dot(a,axis)**2*b.inertia[k],0):(b.transverse||.001);inertia+=b.mass*Math.max(0,dot(arm,arm)-dot(arm,axis)**2)+spin;
   }
   const frequency=clamp(24*Math.sqrt(.09/Math.max(.015,inertia)),18,32),acceleration=frequency*frequency*(prev.pelvis-angle)-2*frequency*prev.rates[k];
   return angle+(prev.rates[k]+acceleration*dt)*dt;
  });
  function candidate(pelvis){const legs=desired.map(a=>pelvis+clamp(a-pelvis,-Math.PI/10,Math.PI/10)),pose=apply(raw,names,parents,{pelvis,legs},hinges),bs=bodies(pose,rig);return {pelvis,legs,pose,bs,h:dot(momentum(history.bodies,bs,rig,dt),axis)};}
  let next=candidate(prev.pelvis);
  for(let j=0;j<3;j++){
   if(Math.abs(targetH-next.h)<1e-7)break;
   const derivative=(candidate(next.pelvis+1e-4).h-next.h)/1e-4;if(Math.abs(derivative)<1e-6)break;
   next=candidate(next.pelvis+clamp((targetH-next.h)/derivative,-.2,.2));
  }
  const plan={pelvis:next.pelvis,pelvisRate:(next.pelvis-prev.pelvis)/dt,legs:next.legs,rates:next.legs.map((a,k)=>(a-prev.legs[k])/dt)},previous=states[n-1],state=respond(previous,prev,plan,dt);
  plans.push(plan);states.push(state);history={bodies:next.bs,target:targetBodies};
  diagnostics.ticks++;diagnostics.maxPlannedResidual=Math.max(diagnostics.maxPlannedResidual,Math.abs(next.h-targetH));diagnostics.maxLag=Math.max(diagnostics.maxLag,...state.legs.map(a=>Math.abs(a-state.pelvis)));diagnostics.maxStep=Math.max(diagnostics.maxStep,Math.abs(state.pelvis-previous.pelvis));
  diagnostics.maxAcceleration=Math.max(diagnostics.maxAcceleration,Math.abs(state.pelvisRate-previous.pelvisRate)/dt);diagnostics.maxPlannedAcceleration=Math.max(diagnostics.maxPlannedAcceleration,Math.abs(plan.pelvisRate-prev.pelvisRate)/dt);
 }
 function stateAt(t){
  if(t<=start)return states[0];
  const frame=clamp((t-start)/dt,0,count),i=Math.floor(frame),u=frame-i;
  while(states.length<=Math.min(count,i+1))advance();
  // Past the finite cache, continue settling analytically. Never freeze a
  // nonzero velocity at the cache endpoint or grow a replay history forever.
  if(i===count)return respond(states[i],plans[i],plans[i],Math.max(0,t-(start+count*dt)));
  const a=plans[i],b=plans[i+1],goal={pelvis:a.pelvis+(b.pelvis-a.pelvis)*u,legs:a.legs.map((v,k)=>v+(b.legs[k]-v)*u)};
  return respond(states[i],a,goal,u*dt);
 }
 function sample(t,pose=source(t)){
  if(t<=start)return pose;
  const state=stateAt(t);
  return apply(choreography?choreography.sample(t,pose):pose,names,parents,state,hinges);
 }
 // Read-only A/B diagnostic of the previous immediate correction.
 function samplePlanned(t,pose=source(t)){
  if(t<=start)return pose;stateAt(t);
  const frame=clamp((t-start)/dt,0,count),i=Math.floor(frame),u=frame-i,a=plans[i],b=plans[Math.min(count,i+1)],state={pelvis:a.pelvis+(b.pelvis-a.pelvis)*u,legs:a.legs.map((v,k)=>v+(b.legs[k]-v)*u)};
  return apply(choreography?choreography.sample(t,pose):pose,names,parents,state,hinges);
 }
 const legResponse=wholeLeg?L.create({source:samplePlanned,base,start,stop:end+1,names,parents,reference,hinges}):null;
 return {sample:legResponse?(t,pose)=>legResponse.sample(t,pose===undefined?source(t):pose):sample,samplePlanned,stateAt,diagnostics,states,plannedStates:plans,rig,stop:legResponse?.stop??stop,choreography,legResponse};
}
function solve3(columns,b){
 const a=[0,1,2].map(i=>[...columns.map(c=>c[i]),b[i]]);
 for(let i=0;i<3;i++){
  let pivot=i;for(let j=i+1;j<3;j++)if(Math.abs(a[j][i])>Math.abs(a[pivot][i]))pivot=j;
  if(Math.abs(a[pivot][i])<1e-9)return [0,0,0];[a[i],a[pivot]]=[a[pivot],a[i]];
  const scale=a[i][i];for(let k=i;k<4;k++)a[i][k]/=scale;
  for(let j=0;j<3;j++)if(j!==i){const v=a[j][i];for(let k=i;k<4;k++)a[j][k]-=v*a[i][k];}
 }
 return a.map(r=>r[3]);
}
function applySpatial(pose,names,parents,state){
 const local=R.localize(pose.points,pose.q,parents),p=names.indexOf('pelvis'),s=names.indexOf('spine_01'),counter=qexp(state.pelvis);
 local.q[p]=qm(local.q[p],counter);local.q[s]=qm(qinv(counter),local.q[s]);
 for(let k=0;k<2;k++){const hip=names.indexOf('thigh_'+['l','r'][k]);local.q[hip]=qm(qm(qinv(counter),qexp(state.legs[k])),local.q[hip]);}
 return R.fk(local,parents);
}
// Plan against the same anatomical pose used for display, preserving its COM.
// In particular, a discarded spine rotation must not drive a pelvis response.
function createProjection(names,parents,reference){
 const joints=J.create(names,parents,reference),massRig=M.model(names,parents,reference),cache=new WeakMap();
 return pose=>{
  if(cache.has(pose))return cache.get(pose);
  const center=M.center(pose,massRig),p=joints.project(pose),shift=sub(center,M.center(p,massRig));
  const result={...pose,...p,points:p.points.map((v,i)=>i?add(v,shift):pose.points[0])};
  cache.set(pose,result);cache.set(result,result);return result;
 };
}
function createSpatial({source,base,target,start,end,names,parents,reference,choreography=null,amount=1,anticipation=.06,recoveryStart=Infinity,recoveryEnd=end}){
 if(typeof target!=='function')throw Error('Attack compensation requires an opposite-angle target');
 const rig=model(names,parents,reference),hinges=legHinges(names,reference),dt=1/60,stop=end+.8,count=Math.ceil((stop-start)/dt),p=names.indexOf('pelvis'),spine=names.indexOf('spine_01'),hips=hinges.map(h=>h.hip);
 const legal=createProjection(names,parents,reference);
 const rawSource=source,rawBase=base;source=t=>legal(rawSource(t));base=t=>legal(rawBase(t));
 const zero=()=>[0,0,0],plans=[{pelvis:zero(),pelvisRate:zero(),legs:[zero(),zero()],rates:[zero(),zero()],x:Array(9).fill(0),xrates:Array(9).fill(0)}],initial=source(start),rest=base(start);
 let history={bodies:bodies(initial,rig),target:bodies(legal(target(start,initial,rest)),rig)},jacobian=null;
 const diagnostics={axes:3,targetMode:'opposite-angle',jointConstrained:true,ticks:0,maxPlannedResidual:0,maxLag:0,maxStep:0,maxPlannedAcceleration:0,amount:clamp(amount,0,1)};
 function advance(){
  const n=plans.length,t=start+n*dt,prev=plans[n-1],plain=source(t),raw=legal(choreography?choreography.sample(t,plain):plain),baseline=base(t),targetBodies=bodies(legal(target(t,plain,baseline)),rig),rawLocal=R.localize(raw.points,raw.q,parents),measure=momentumFrom(history.bodies,rig,dt);
  // Preserve the original Amount meaning: the target pose counter-rotates
  // the pelvis by that fraction of the attack-added spine rotation. Match its
  // three-axis momentum while distributing motion over the soft lower body;
  // Amount is not a fraction of angular momentum to cancel.
  const targetH=momentum(history.target,targetBodies,rig,dt);
  // The three momentum equations leave posture freedom. Prefer a damped
  // return toward the base pose, then distribute the required correction over
  // pelvis and both hips with a local inertia-weighted least-squares solve.
  const previous=prev.x,rates=prev.xrates,w=24;
  const desired=previous.map((v,i)=>v+(rates[i]+(-w*w*v-2*w*rates[i])*dt)*dt);
  function candidate(x){
   const pelvis=x.slice(0,3),legs=[x.slice(3,6),x.slice(6,9)].map(v=>add(pelvis,mul(v,1/Math.sqrt(1+dot(v,v)/(Math.PI/10)**2)))),counter=qexp(pelvis),inverse=qinv(counter),q=rawLocal.q.slice();
   q[p]=qm(rawLocal.q[p],counter);q[spine]=qm(inverse,rawLocal.q[spine]);
   for(let k=0;k<2;k++)q[hips[k]]=qm(qm(inverse,qexp(legs[k])),rawLocal.q[hips[k]]);
   const points=[],world=[];for(let i=0;i<parents.length;i++){const parent=parents[i];world[i]=parent<0?q[i]:unit(qm(world[parent],q[i]));points[i]=parent<0?rawLocal.p[i]:add(points[parent],rotate(world[parent],rawLocal.p[i]));}
   const bs=bodies(legal({points,q:world}),rig);return {x,pelvis,legs,bs,h:measure(bs)};
  }
  // Reuse the local Jacobian for nearby ticks; refresh if iteration needs it.
  let next=candidate(desired),columns=jacobian?.columns,inverseMass=jacobian?.inverseMass,gram=jacobian?.gram;
  for(let pass=0;pass<6;pass++){
   const error=sub(targetH,next.h);if(length(error)<1e-5)break;
   if(!columns||(pass===0&&n%4===0)||pass===4){
    columns=next.x.map((_,a)=>{const v=next.x.slice();v[a]+=1e-4;return mul(sub(candidate(v).h,next.h),1e4);});
    inverseMass=columns.map(v=>1/Math.max(.001,length(v)*dt));
    gram=[0,1,2].map(a=>columns.reduce((sum,v,i)=>add(sum,mul(v,v[a]*inverseMass[i])),[0,0,0]));
    jacobian={columns,inverseMass,gram};
   }
   const multiplier=solve3(gram,error),delta=columns.map((v,i)=>dot(v,multiplier)*inverseMass[i]),norm=Math.hypot(...delta),scale=Math.min(1,.3/Math.max(1e-9,norm));
   let trial=candidate(next.x.map((v,i)=>v+delta[i]*scale));
   if(length(sub(targetH,trial.h))>length(error))trial=candidate(next.x.map((v,i)=>v+delta[i]*scale*.5));
   next=trial;
  }
  const plan={x:next.x,xrates:next.x.map((v,i)=>(v-prev.x[i])/dt),pelvis:next.pelvis,pelvisRate:mul(sub(next.pelvis,prev.pelvis),1/dt),legs:next.legs,rates:next.legs.map((v,k)=>mul(sub(v,prev.legs[k]),1/dt))};
  plans.push(plan);history={bodies:next.bs,target:targetBodies};diagnostics.ticks++;
  diagnostics.maxPlannedResidual=Math.max(diagnostics.maxPlannedResidual,length(sub(next.h,targetH)));diagnostics.maxLag=Math.max(diagnostics.maxLag,...next.legs.map(v=>length(sub(v,next.pelvis))));
  diagnostics.maxStep=Math.max(diagnostics.maxStep,length(sub(plan.pelvis,prev.pelvis)));diagnostics.maxPlannedAcceleration=Math.max(diagnostics.maxPlannedAcceleration,length(sub(plan.pelvisRate,prev.pelvisRate))/dt);
 }
 function stateAt(t){
  const frame=clamp((t-start)/dt,0,count),i=Math.floor(frame),u=frame-i;while(plans.length<=Math.min(count,i+1))advance();
  const a=plans[i],b=plans[Math.min(count,i+1)],mix=(v,w)=>add(v,mul(sub(w,v),u));
  return {pelvis:mix(a.pelvis,b.pelvis),legs:a.legs.map((v,k)=>mix(v,b.legs[k]))};
 }
 function samplePlanned(t,pose=source(t)){if(t<=start)return pose;return legal(applySpatial(legal(choreography?choreography.sample(t,legal(pose)):legal(pose)),names,parents,stateAt(t)));}
 // The clip is known in advance. Lead the damped response by 60 ms so its
 // opposing swing occurs during impact rather than after it; state/velocity
 // still start continuously at the marker. This is not an instantaneous solve.
 const legResponse=L.create({source:samplePlanned,base,start,stop:end+1,names,parents,reference,hinges,anticipation,sampleRate:60,recoveryStart,recoveryEnd});
 return {sample:(t,pose)=>legal(legResponse.sample(t,pose===undefined?source(t):legal(pose))),samplePlanned,stateAt,diagnostics,states:plans,plannedStates:plans,rig,stop:legResponse.stop,choreography,legResponse};
}
function create(options){return options.wholeLeg===false?createYaw(options):createSpatial(options);}
const api={createProjection,model,bodies,momentum,legHinges,humanAngles,referenceMotion,apply,applySpatial,respond,create};if(node)module.exports=api;else root.BodyflipAttackInertia=api;
})(globalThis);
