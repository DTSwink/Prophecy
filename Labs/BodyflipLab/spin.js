/* Persistent angular-velocity commands, integrated independently of jump height.
 * Velocity is specified for the reference pose; changing inertia scales it. */
(function(root){
'use strict';
const node=typeof module!=='undefined',R=node?require('./recovery.js'):root.Recovery,M=node?require('./mass.js'):root.BodyflipMass,C=node?require('./core.js'):root.BodyflipCore;
const Target=node?require('./target-rig.js'):root.BodyflipTargetRig;
const Response=node?require('./spin-response.js'):root.BodyflipSpinResponse;
const {add,sub,mul,dot,length,rotate,qm,qinv,qexp,qlog,unit}=R,rad=Math.PI/180,dt=1/240,identity=[0,0,0,1];
const ease=x=>{x=Math.max(0,Math.min(1,x));return x*x*x*(10+x*(-15+6*x));};
function rebase(frame,rotation,rig){
 if(!frame.spin)return frame;
 const q=qm(rotation,qinv(frame.spin.rotation));
 return {...frame,pose:M.rotateAboutCOM(frame.pose,q,rig)};
}
function create(source,{start=0,commandTime=start,event={},settings,names,parents,reference,inherited=null,contact=null}={}){

 const rig=M.model(names,parents,reference),e=C.sanitizeJump(event),seed=inherited?.rotation||identity,initial=source(start),referenceI=M.tensor(reference,rig);
 const headingDirection=rotate(initial.pose.q[0],[0,0,1]),heading=Math.atan2(headingDirection[0],headingDirection[2]);
 const axis=e.turnAxis===null&&inherited?.axis?inherited.axis:rotate(qexp([0,heading,0]),C.flipAxis(e.turnAxis??inherited?.axisIndex??settings.axis));
 const fallback={flip:settings.airFlip?settings.flipSpeed:0,twist:settings.airFlip?settings.twistSpeed:0};
 const begin=commandTime+e.turnDelay,axisIndex=e.turnAxis??inherited?.axisIndex??settings.axis;
 const at=(curve,t)=>curve.from+(curve.to-curve.from)*(t<curve.begin?0:curve.duration>0?ease((t-curve.begin)/curve.duration):1);
 const value=(curve,t)=>t<curve.begin&&curve.prior?value(curve.prior,t):at(curve,t);
 const commands={},previousCommands={};
 for(const key of ['flip','twist']){
  const prior=inherited?.commands?.[key]||{from:inherited?.target?.[key]||0,to:inherited?.command?.[key]??inherited?.target?.[key]??0,begin:start,duration:0};
  previousCommands[key]=prior;
  if(e[key]===null&&inherited){commands[key]=prior;continue;}
  const goal=e[key]??fallback[key],from=value(prior,begin),duration=e.instantSpin?0:Math.abs(goal)>Math.abs(from)?e.turnIn:e.turnOut;
  commands[key]={from,to:goal,begin,duration,prior};
 }
 const ratesAt=t=>({flip:value(commands.flip,t),twist:value(commands.twist,t)}),target={flip:commands.flip.to,twist:commands.twist.to};
 const active=!!(inherited?.active||target.flip||target.twist);
 const targetRig=Target.create(names,parents,reference),sourceLegal=active||e.attack!=='none'||e.pose!=='none';
 if(sourceLegal){const legal=targetRig.track(source,{start});source=legal.sample;}
 const sourceCache=new Map(),originalSource=source;source=time=>{const key=Math.round(time*1e9);if(sourceCache.has(key))return sourceCache.get(key);const f=originalSource(time);sourceCache.set(key,f);if(sourceCache.size>512)sourceCache.delete(sourceCache.keys().next().value);return f;};
 const seedAxis=inherited?.axis||axis,ramp=e.instantSpin?0:e.turnIn,axisCommand=e.turnAxis===null&&inherited?.axisCommand?inherited.axisCommand:{from:seedAxis,to:axis,begin,duration:ramp};
 const curveAxis=(curve,t)=>rotate(R.qslerp(identity,R.fromTo(curve.from,curve.to),t<curve.begin?0:curve.duration>0?ease((t-curve.begin)/curve.duration):1),curve.from);
 const axisAt=t=>curveAxis(axisCommand,t),oldAxis=inherited?.axisCommand||{from:seedAxis,to:seedAxis,begin:start,duration:0};
 const response=settings.spinLag>0&&active&&!(inherited&&e.flip===null&&e.twist===null&&e.turnAxis===null)?Response.create(names,parents,reference,settings.spinLag):null;
 // Each segment adds only the change from the inherited command. Prior recoil
 // remains in its source animation, including across Keep/action markers.
 const drive=t=>({flip:sub(mul(axisAt(t),value(commands.flip,t)),mul(curveAxis(oldAxis,t),value(previousCommands.flip,t))),twist:value(commands.twist,t)-value(previousCommands.twist,t)});
 const boundaries=new Set();function collect(c){if(c.duration===0&&Number.isFinite(c.begin))boundaries.add(c.begin);if(c.prior)collect(c.prior);}
 Object.values(commands).forEach(collect);Object.values(previousCommands).forEach(collect);collect(axisCommand);collect(oldAxis);
 const breaks=[...boundaries].sort((a,b)=>a-b);
 const states=[{q:identity,omega:inherited?.omega||[0,0,0],flip:0,twist:0,lag:response?.zero()}],neutralFlip=M.moment(referenceI,C.flipAxis(axisIndex)),neutralTwist=M.moment(referenceI,[0,1,0]);
 function velocity(time,q,lag=null){
  const base=source(time).pose,p=response&&lag?response.apply(base,lag):base,I=M.tensor(p,rig),axisNow=axisAt(time);
  const flipAxis=length(axisNow)>.5?axisNow:axis,twistBase=rotate(p.q[1],[1,0,0]),twistAxis=rotate(q,twistBase),localFlip=rotate(qinv(q),flipAxis);
  const gain=settings.spinInertia??1,flipScale=1+gain*(neutralFlip/Math.max(1e-8,M.moment(I,localFlip))-1),twistScale=1+gain*(neutralTwist/Math.max(1e-8,M.moment(I,twistBase))-1),rates=ratesAt(time);
  return {omega:add(mul(flipAxis,rates.flip*rad*flipScale),mul(twistAxis,rates.twist*rad*twistScale)),flipRate:rates.flip*flipScale,twistRate:rates.twist*twistScale,rates,flipScale,twistScale,axis:flipAxis};
 }
 if(active)states[0].omega=velocity(start,identity).omega;
 function recoil(lag,from,to,time,q){
  if(!response)return lag;
  const a=drive(from),b=drive(to),change=sub(b.flip,a.flip),twistChange=b.twist-a.twist;
  if(length(change)+Math.abs(twistChange)<1e-9)return lag;
  const p=source(time).pose,v=velocity(time,q,lag);
  const delta=add(mul(rotate(qinv(q),change),rad*v.flipScale),mul(rotate(p.q[1],[1,0,0]),twistChange*rad*v.twistScale));
  return response.impulse(lag,p,delta);
 }
 if(response)states[0].lag=recoil(states[0].lag,start-1e-9,start,start,identity);
 function integrate(a,lo,hi){
  let s=a;
  for(const endTime of [...breaks.filter(t=>t>lo+1e-10&&t<=hi+1e-10),hi].filter((t,i,all)=>i===0||t-all[i-1]>1e-10)){
   const h=endTime-lo;if(h<=1e-12)continue;
   let lag=s.lag;
   if(response)lag=response.drift(recoil(lag,lo,lo+h/2,lo+h/2,s.q),h/2);
   const half=velocity(lo+h/2,qm(qexp(mul(s.omega,h/2)),s.q),lag),q=unit(qm(qexp(mul(half.omega,h)),s.q));
   if(response){lag=response.drift(lag,h/2);lag=recoil(lag,lo+h/2,endTime-1e-10,endTime,q);lag=recoil(lag,endTime-1e-10,endTime,endTime,q);}
   s={q,omega:velocity(endTime,q,lag).omega,flip:s.flip+half.flipRate*h,twist:s.twist+half.twistRate*h,lag};lo=endTime;
  }
  return s;
 }
 function advance(){
  const i=states.length-1,a=states[i],time=start+i*dt;
  if(response||breaks.some(t=>t>time+1e-10&&t<=time+dt+1e-10)){states.push(integrate(a,time,time+dt));return;}
  const half=velocity(time+dt/2,qm(qexp(mul(a.omega,dt/2)),a.q)),q=unit(qm(qexp(mul(half.omega,dt)),a.q)),end=velocity(time+dt,q);
  states.push({q,omega:end.omega,flip:a.flip+half.flipRate*dt,twist:a.twist+half.twistRate*dt});
 }
 function computeState(time){
  if(time<=start){const v=velocity(start,identity);return {...states[0],...v,rotation:seed,target:v.rates,axis:seedAxis,axisIndex};}
  const f=(time-start)/dt,i=Math.floor(f+1e-9),u=Math.max(0,Math.min(1,f-i));
  while(states.length<=i+1)advance();
  const lo=start+i*dt;
  if(response||breaks.some(t=>t>lo+1e-10&&t<=lo+dt+1e-10)){
   const s=integrate(states[i],lo,time),v=velocity(time,s.q,s.lag);return {...s,rotation:unit(qm(s.q,seed)),...v,target:v.rates,axisIndex};
  }
  const a=states[i],b=states[i+1],delta=qlog(qm(b.q,qinv(a.q))),u2=u*u,u3=u2*u;
  const vector=add(add(mul(delta,-2*u3+3*u2),mul(a.omega,dt*(u3-2*u2+u))),mul(b.omega,dt*(u3-u2))),q=unit(qm(qexp(vector),a.q)),v=velocity(time,q);
  return {q,rotation:unit(qm(q,seed)),omega:v.omega,target:v.rates,axis:v.axis,axisIndex,flip:a.flip+(b.flip-a.flip)*u,twist:a.twist+(b.twist-a.twist)*u,flipRate:v.flipRate,twistRate:v.twistRate,flipScale:v.flipScale,twistScale:v.twistScale};
 }
 const stateCache=new Map();function state(time){const key=Math.round(time*1e9);if(stateCache.has(key))return stateCache.get(key);const s=computeState(time);stateCache.set(key,s);if(stateCache.size>512)stateCache.delete(stateCache.keys().next().value);return s;}
 function sample(time,applyContact=true){
  const frame=source(time);if(time<start||frame.returnedToLocomotion&&frame.capsule?.landingTime>start)return frame;
  const s=active?state(time):{q:identity,rotation:seed,omega:[0,0,0],target,axis,axisIndex,flip:0,twist:0,flipRate:0,twistRate:0,flipScale:1,twistScale:1};
  const articulated=response?response.apply(frame.pose,s.lag):frame.pose;
  let pose=active?targetRig.mark(M.rotateAboutCOM(articulated,s.q,rig)):articulated;
  if(contact&&applyContact)pose=contact(pose,time,frame,s);
  return {...frame,pose,spin:{...s,time,active,command:target,commands,axisCommand},jumpMotion:{...frame.jumpMotion,flip:s.flip,twist:s.twist,flipRate:s.flipRate,twistRate:s.twistRate,axis:s.axis}};
 }
 const orientationCache=new Map();function atOrientation(time,rotation){const key=[Math.round(time*1e9),...rotation].join(',');if(orientationCache.has(key))return orientationCache.get(key);const f=source(time),p=response&&time>=start?response.apply(f.pose,state(time).lag):f.pose,out={...f,pose:M.rotateAboutCOM(p,qm(rotation,qinv(seed)),rig)};if(sourceLegal)targetRig.mark(out.pose);orientationCache.set(key,out);if(orientationCache.size>512)orientationCache.delete(orientationCache.keys().next().value);return out;}
 return {sample,atOrientation,state,ratesAt,active,start,begin,target,rig,get ticks(){return states.length-1;}};
}
const api={create,rebase};if(node)module.exports=api;else root.BodyflipSpin=api;
})(globalThis);
