/* Small deterministic pelvis model, prepared once; playback only samples it. */
(function(root){
'use strict';
const R=typeof module!=='undefined'?require('./recovery.js'):root.Recovery;
const {add,sub,mul,dot,length,unit}=R,clamp=(v,a,b)=>Math.max(a,Math.min(b,v)),g=[0,-9.81,0];
function create({root:origin,hip,foot,normal,direction,incoming,reach,maxReach,loadMs,rebound,launchSpeed,cap,rolling,carry,loading=()=>({foot,valid:true}),startPush=()=>{}}){
 const dt=1/480,response=Math.max(.001,loadMs/1000),offset=sub(hip,origin),rest=length(sub(hip,foot));
 const minLength=Math.max(.45*reach,rest-.25*reach),room=Math.max(.015,rest-minLength);
 const impact=Math.max(0,-dot(incoming,unit(sub(hip,foot))));
 // Stiffen automatically for a hard arrival before the leg runs out of room.
 const omega=Math.min(120,Math.max(Math.PI/(2*response),impact/(room*.8))),stiffness=omega*omega,damping=.3*omega;
 const minimumHeight=Math.min(.12*reach,dot(sub(hip,foot),normal));
 const frames=[{t:0,p:origin.slice(),v:incoming.slice()}];let compression=0,limitReason=null;
 const geometry=(p,t)=>{const contact=loading(t),h=add(p,offset),delta=sub(h,contact.foot),footVelocity=mul(sub(loading(t+dt/2).foot,loading(Math.max(0,t-dt/2)).foot),1/(t<dt/2?t+dt/2:dt));return {h,foot:contact.foot,valid:contact.valid,footVelocity,d:length(delta),axis:unit(delta)};};
 const acceleration=(p,v,t)=>{const a=geometry(p,t),x=Math.max(0,rest-a.d);return add(g,mul(a.axis,Math.max(0,stiffness*x-damping*dot(sub(v,a.footVelocity),a.axis))));};
 for(let i=1;i<=Math.ceil(response*1.5/dt);i++){
  const t=i*dt,old=frames.at(-1),a=acceleration(old.p,old.v,old.t),half=add(old.v,mul(a,dt/2));
  let p=add(old.p,mul(half,dt)),v=add(half,mul(acceleration(p,half,t),dt/2)),geo=geometry(p,t);
  // Physical safety bounds, not a timer gate. An exhausted leg starts extending early.
  const height=dot(sub(geo.h,geo.foot),normal);
  if(height<minimumHeight){p=add(p,mul(normal,minimumHeight-height));const vn=dot(v,normal);if(vn<0)v=sub(v,mul(normal,vn));limitReason='Surface clearance';geo=geometry(p,t);}
  if(geo.d<minLength){p=add(p,mul(geo.axis,minLength-geo.d));const vr=dot(v,geo.axis);if(vr<0)v=sub(v,mul(geo.axis,vr));limitReason='Compression limit';geo=geometry(p,t);}
  if(geo.d>maxReach){p=add(p,mul(geo.axis,maxReach-geo.d));limitReason='Reach limit';geo=geometry(p,t);}
  if(!geo.valid)limitReason='Contact lost';
  compression=Math.max(compression,rest-geo.d);frames.push({t:i*dt,p,v});
  if(limitReason||(geo.d>maxReach-.025&&dot(v,geo.axis)>0))break;
  if(i*dt>=Math.min(.02,response)&&(dot(sub(v,geo.footVelocity),geo.axis)>=0&&compression>.001||impact<.05))break;
 }
 const loaded=frames.at(-1),loadDuration=loaded.t,spring=sub(acceleration(loaded.p,loaded.v,loaded.t),g);
 startPush(loadDuration);
 const available=Math.max(0,.5*impact*impact+9.81*(origin[1]-loaded.p[1]));
 const storedEnergy=Math.min(.5*stiffness*compression*compression,available);
 // Rebound is returned impact energy, added once to the active jump's energy.
 const returnedEnergy=Math.min(storedEnergy*rebound,.5*launchSpeed*launchSpeed);
 const targetSpeed=Math.sqrt(launchSpeed*launchSpeed+2*returnedEnergy),targetVelocity=add(carry(loaded.v,normal,direction),mul(direction,targetSpeed));
 let pushDuration=clamp(response*.6,.025,.1);
 function push(t){const deltaV=sub(sub(sub(targetVelocity,loaded.v),mul(g,pushDuration)),mul(spring,pushDuration/2)),u=clamp(t/pushDuration,0,1),s=u*u*(3-2*u),integral=pushDuration*(u*u*u-.5*u*u*u*u);
  return {p:add(loaded.p,add(mul(loaded.v,t),add(mul(g,.5*t*t),add(mul(spring,.5*t*t-t*t*t/(6*pushDuration)),mul(deltaV,integral))))),v:add(loaded.v,add(mul(g,t),add(mul(spring,t-t*t/(2*pushDuration)),mul(deltaV,s))))};
 }
 const valid=t=>{const c=rolling(t),p=push(t),h=add(p.p,offset),d=length(sub(h,c.foot));return c.valid&&d<=maxReach+1e-8&&d>=minLength-1e-8&&dot(sub(h,c.foot),normal)>=minimumHeight-1e-8;};
 // Fit the drive inside remaining leg travel; never stretch the pinned limb.
 while(pushDuration>.0081&&![.25,.5,.75,1].every(u=>valid(pushDuration*u)))pushDuration=Math.max(.008,pushDuration*.75);
 let pushTime=pushDuration;
 for(let i=0;i<=Math.ceil(pushDuration/dt);i++){const t=Math.min(pushDuration,i*dt);if(!valid(t)){let lo=Math.max(0,t-dt),hi=t;for(let j=0;j<20;j++){const mid=(lo+hi)/2;if(valid(mid))lo=mid;else hi=mid;}pushTime=lo;break;}}
 const releaseTime=loadDuration+pushTime,released=push(pushTime);
 function load(t){const f=clamp(t/dt,0,frames.length-1),i=Math.min(frames.length-2,Math.floor(f)),a=frames[i],b=frames[i+1],u=clamp((t-a.t)/dt,0,1),u2=u*u,u3=u2*u;
  return {p:add(add(mul(a.p,2*u3-3*u2+1),mul(b.p,-2*u3+3*u2)),add(mul(a.v,(u3-2*u2+u)*dt),mul(b.v,(u3-u2)*dt))),v:add(add(mul(a.p,(6*u2-6*u)/dt),mul(b.p,(-6*u2+6*u)/dt)),add(mul(a.v,3*u2-4*u+1),mul(b.v,3*u2-2*u)))};
 }
 function sample(t){if(t<loadDuration)return load(Math.max(0,t));if(t<=releaseTime)return push(t-loadDuration);
  const elapsed=t-releaseTime,vy=Math.max(-cap,released.v[1]),tc=Math.max(0,(vy+cap)/9.81),a=Math.min(elapsed,tc),y=vy*a-4.905*a*a-cap*Math.max(0,elapsed-tc);
  return {p:add(released.p,[released.v[0]*elapsed,y,released.v[2]*elapsed]),v:[released.v[0],Math.max(-cap,vy-9.81*elapsed),released.v[2]]};
 }
 return {sample,loadDuration,releaseTime,didPush:pushTime>.001,compression,storedEnergy,returnedEnergy,limitReason,frames,released,apex:releaseTime+Math.max(0,released.v[1])/9.81};
}
const api={create};if(typeof module!=='undefined')module.exports=api;else root.BodyflipBounce=api;
})(globalThis);
