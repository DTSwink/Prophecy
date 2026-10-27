/* Reduced airborne yaw response. Deterministic 120 Hz cache; no Jolt/NN worker. */
(function(root){
'use strict';
const node=typeof module!=='undefined',R=node?require('./recovery.js'):root.Recovery,T=node?require('./torso.js'):root.BodyflipTorso;
const {add,sub,mul,dot,cross,length,unit,rotate,qm,qinv,qexp,qlog}=R;
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
function model(names,parents,reference){
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
function momentum(a,b,rig,dt){
 const total=rig.reduce((v,b)=>v+b.mass,0),ca=rig.reduce((v,r,i)=>add(v,mul(a[i].center,r.mass/total)),[0,0,0]),cb=rig.reduce((v,r,i)=>add(v,mul(b[i].center,r.mass/total)),[0,0,0]);
 const com=mul(add(ca,cb),.5),velocity=mul(sub(cb,ca),1/dt);let h=[0,0,0];
 for(let i=0;i<rig.length;i++){
  const r=rig[i],q=R.qslerp(a[i].q,b[i].q,.5),omega=mul(qlog(qm(b[i].q,qinv(a[i].q))),1/dt);
  const v=sub(mul(sub(b[i].center,a[i].center),1/dt),velocity),arm=sub(mul(add(a[i].center,b[i].center),.5),com);
  let spin;
  if(r.inertia){const frame=qm(q,r.rotation),w=rotate(qinv(frame),omega);spin=rotate(frame,w.map((v,j)=>v*r.inertia[j]));}
  else {const axis=rotate(q,r.axis);spin=add(mul(omega,r.transverse),mul(axis,(r.axial-r.transverse)*dot(omega,axis)));}
  h=add(h,add(spin,mul(cross(arm,v),r.mass)));
 }
 return h;
}
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
 const up=rotate(a.q[p],[1,0,0]),turn=dot(qlog(qm(b.q[spine],qinv(a.q[spine]))),up);
 // Mirror the reference with the attack's actual turn, not the attack's name.
 // Small/no yaw attacks get proportionally little/no rotational leg gesture.
 // Compressing the human 160ms acceleration phase scales the excursion too,
 // so a very short strike does not demand an entire throwing gesture at speed.
 const tempoScale=clamp(Math.min((armedTime-start)/.14,(hitTime-armedTime)/.16),0,1);
 const follow=turn>=0?1:0,strength=clamp(amount,0,1)*clamp(Math.abs(turn)/(Math.PI/3),0,1)*tempoScale;
 const ease=x=>{x=clamp(x,0,1);return x*x*x*(10+x*(-15+6*x));};
 const clock=[[start,-.30],[armedTime,-.16],[hitTime,0],[hitTime+(hitTime-armedTime)*.075/.16,.075]];
 function sample(t,pose){
  if(t<=start||t>=returnEnd||strength===0)return pose;
  const weight=strength*ease((t-start)/Math.max(1/60,armedTime-start))*(1-ease((t-end)/Math.max(1/60,returnEnd-end)));
  // Armed = late cocking (-160ms); Hit = release. A monotone cubic clock
  // carries velocity through those boundaries and eases into follow-through.
  const phase=curveAt(clock,t,1);
  const values=humanAngles(phase),local=R.localize(pose.points,pose.q,parents),up=rotate(pose.q[p],[1,0,0]),forward=rotate(pose.q[p],[0,-1,0]);
  for(let k=0;k<2;k++){
   const h=hinges[k],v=unit(sub(pose.points[h.knee],pose.points[h.hip])),w=unit(sub(pose.points[h.foot],pose.points[h.knee]));
   const hip=Math.atan2(dot(v,forward),-dot(v,up)),knee=Math.acos(clamp(dot(v,w),-1,1)),j=k===follow?0:2;
   const hipDelta=(values[j]-hip)*weight,kneeDelta=(clamp(values[j+1],5*Math.PI/180,150*Math.PI/180)-knee)*weight;
   // Flex in the pelvis sagittal plane; using the thigh's existing bend axis
   // here would turn a splayed leg sideways instead of bringing it forward.
   local.q[h.hip]=qm(qexp([0,0,hipDelta]),local.q[h.hip]);
   local.q[h.knee]=qm(local.q[h.knee],qexp(mul(h.kneeAxis,kneeDelta)));
  }
  return R.fk(local,parents);
 }
 return {sample,follow,strength,tempoScale,armedTime,hitTime,source:'Wagner 2011 Fig.2 jump throw (approximate readings)'};
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
function create({source,base,target,start,end,names,parents,reference,choreography=null}){
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
    const arm=sub(rawBodies[j].center,origin);inertia+=rig[j].mass*Math.max(0,dot(arm,arm)-dot(arm,axis)**2)+(rig[j].transverse||.001);
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
 return {sample,samplePlanned,stateAt,diagnostics,states,plannedStates:plans,rig,stop,choreography};
}
const api={model,bodies,momentum,legHinges,humanAngles,referenceMotion,apply,respond,create};if(node)module.exports=api;else root.BodyflipAttackInertia=api;
})(globalThis);
