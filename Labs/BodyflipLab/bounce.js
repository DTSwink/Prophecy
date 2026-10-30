/* Small deterministic pelvis model, prepared once; playback only samples it. */
(function(root){
'use strict';
const R=typeof module!=='undefined'?require('./recovery.js'):root.Recovery;
const {add,sub,mul,dot,length,unit}=R,clamp=(v,a,b)=>Math.max(a,Math.min(b,v)),g=[0,-9.81,0];
function create({root:origin,hip,foot,normal,direction,incoming,reach,maxReach,loadMs,buildMs=loadMs,authoredBuild=buildMs>loadMs,rebound,launchSpeed,cap,rolling,carry,loading=()=>({foot,valid:true}),startPush=()=>{},anchorOffset=null,resolveRoot=null,surfaceOrigin=null,constraints=null,upperLength=null,lowerLength=null}){
 const dt=1/480,response=Math.max(.001,loadMs/1000),offset=sub(hip,origin),rest=length(sub(hip,foot));
 const minLength=Math.max(.45*reach,rest-.25*reach),room=Math.max(.015,rest-minLength);
 const anchorVelocity=t=>anchorOffset?mul(sub(anchorOffset(t+dt/2),anchorOffset(Math.max(0,t-dt/2))),1/(t<dt/2?t+dt/2:dt)):[0,0,0];
 const impact=Math.max(0,-dot(anchorOffset?add(incoming,anchorVelocity(0)):incoming,unit(sub(hip,foot))));
 // Stiffen automatically for a hard arrival before the leg runs out of room.
 const omega=Math.min(120,Math.max(Math.PI/(2*response),impact/(room*.8))),stiffness=omega*omega,damping=.3*omega;
 const minimumHeight=Math.min(.12*reach,dot(sub(hip,surfaceOrigin||foot),normal));
 const frames=[{t:0,p:origin.slice(),v:incoming.slice()}],loadCompression=[0];let compression=0,limitReason=null,pairFailure=false;
 const geometry=(p,t,v=[0,0,0])=>{const contact=loading(t,p),h=add(p,anchorOffset?anchorOffset(t):offset),delta=sub(h,contact.foot),before=Math.min(t,dt/2),footVelocity=mul(sub(loading(t+dt/2,add(p,mul(v,dt/2))).foot,loading(t-before,sub(p,mul(v,before))).foot),1/(dt/2+before));return {h,foot:contact.foot,valid:contact.valid,footVelocity:anchorOffset?sub(footVelocity,anchorVelocity(t)):footVelocity,d:length(delta),axis:unit(delta)};};
 const acceleration=(p,v,t)=>{const a=geometry(p,t,v),x=Math.max(0,rest-a.d);return add(g,mul(a.axis,Math.max(0,stiffness*x-damping*dot(sub(v,a.footVelocity),a.axis))));};
 // A paired contact adds reach constraints, not another spring or impulse.
 // Contact coordinates are queried again after each root correction because
 // legal wrist rotation can move the wrist relative to its planted palm.
 function pairRows(p,t,withMean=false){
  const rows=constraints(p,t).map(c=>({...c,minLength:c.minLength??0,minHeight:0}));
  if(withMean){const c=loading(t,p);rows.push({hip:add(p,anchorOffset?anchorOffset(t):offset),foot:c.foot,maxReach,minLength,valid:c.valid,normal,surfaceOrigin:surfaceOrigin||c.foot,minHeight:minimumHeight});}
  return rows;
 }
 function bounds(c){
  if(c.valid===false||!c.hip?.every(Number.isFinite)||!c.foot?.every(Number.isFinite)||!(c.maxReach>0)||!Number.isFinite(c.maxReach)||!(c.minLength>=0&&c.minLength<=c.maxReach))return {valid:false};
  const delta=sub(c.hip,c.foot),d=length(delta),axis=d>1e-12?mul(delta,1/d):unit(c.normal||normal);
  const height=c.normal&&c.surfaceOrigin?dot(sub(c.hip,c.surfaceOrigin),c.normal):Infinity;
  return {valid:true,d,axis,height,error:Math.max(d-c.maxReach,c.minLength-d,c.minHeight-height,0)};
 }
 function pairValid(p,t,tolerance=1e-8){const rows=pairRows(p,t);return rows.length>0&&rows.every(c=>{const a=bounds(c);return a.valid&&a.error<=tolerance;});}
 function projectPair(from,proposed,t){
  let p=proposed.slice(),reason=null;const normals=[];
  const move=delta=>{if(resolveRoot){const hit=resolveRoot(p,delta,t);p=hit.root;normals.push(...hit.contacts.map(c=>c.normal));}else p=add(p,delta);};
  if(resolveRoot){const hit=resolveRoot(from,sub(p,from),t);p=hit.root;normals.push(...hit.contacts.map(c=>c.normal));}
  for(let pass=0;pass<32;pass++){
   const rows=pairRows(p,t,true);if(rows.length<2)return {p,valid:false,reason:'Contact lost',normals};
   let error=0;
   for(let i=0;i<rows.length;i++){
    const c=pairRows(p,t,true)[i],a=bounds(c);if(!a.valid)return {p,valid:false,reason:'Contact lost',normals};error=Math.max(error,a.error);
    if(a.height<c.minHeight-1e-9){move(mul(c.normal,c.minHeight-a.height));reason='Surface clearance';}
    else if(a.d>c.maxReach+1e-9){
     // If the capsule blocks part of an inward reach correction, solve the
     // sphere intersection along its free tangent instead of converging one
     // tiny blocked radial projection at a time.
     let tangent=a.axis;for(const n of normals)tangent=sub(tangent,mul(n,Math.max(0,dot(tangent,n))));
     const size=length(tangent);if(size>1e-8){tangent=mul(tangent,1/size);const along=dot(sub(c.hip,c.foot),tangent),disc=along*along-(a.d*a.d-c.maxReach*c.maxReach);move(disc>=0?mul(tangent,-Math.max(0,along-Math.sqrt(disc))):mul(a.axis,c.maxReach-a.d));}
     else move(mul(a.axis,c.maxReach-a.d));reason='Reach limit';
    }
    else if(a.d<c.minLength-1e-9){move(mul(a.axis,c.minLength-a.d));reason='Compression limit';}
   }
   if(error<=1e-8)return {p,valid:true,reason,normals};
  }
  return {p,valid:false,reason:'No shared reach',normals};
 }
 function pairVelocity(p,v,t,normals=[]){
  const rows=pairRows(p,t),before=Math.min(t,dt/2);
  for(let pass=0;pass<16;pass++){
   const previous=v;
   for(const n of normals)v=sub(v,mul(n,Math.min(0,dot(v,n))));
   for(let i=0;i<rows.length;i++){
    const c=rows[i],z=bounds(c);if(z.d<c.maxReach-1e-7&&z.d>c.minLength+1e-7)continue;
    // Use the already corrected velocity. Reusing the original radial rate
    // for two aligned arms would apply the same braking twice and reverse it.
    const a=pairRows(sub(p,mul(v,before)),t-before),b=pairRows(add(p,mul(v,dt/2)),t+dt/2),rate=mul(sub(sub(b[i].hip,b[i].foot),sub(a[i].hip,a[i].foot)),1/(before+dt/2)),radial=dot(rate,z.axis);
    if(z.d>=c.maxReach-1e-7&&radial>0||z.d<=c.minLength+1e-7&&radial<0){
     const direct=sub(v,mul(z.axis,radial)),blocked=normals.filter(n=>dot(direct,n)<-1e-10);
     if(!blocked.length)v=direct;
     else {let tangent=z.axis;for(const n of blocked)tangent=sub(tangent,mul(n,dot(tangent,n)));const den=dot(tangent,z.axis);if(den>1e-8)v=sub(v,mul(tangent,radial/den));}
    }
   }
   for(const n of normals)v=sub(v,mul(n,Math.min(0,dot(v,n))));
   if(length(sub(v,previous))<1e-9)break;
  }
  return v;
 }
 if(constraints&&!pairValid(origin,0)){pairFailure=true;limitReason='No shared reach';}
 if(authoredBuild)for(let i=1;!pairFailure&&i<=Math.ceil(buildMs/1000/dt);i++){
  const old=frames.at(-1),t=i*dt;
  let v=add(old.v,mul(g,dt));v[1]=Math.max(Math.min(-cap,incoming[1]),v[1]);
  let p=add(old.p,mul(add(old.v,v),dt/2));
  // Loading authors the pelvis/limb pose, never a force that brakes the root.
  // Only an actual capsule collision can remove incoming normal velocity.
  if(resolveRoot){const hit=resolveRoot(old.p,sub(p,old.p),t);p=hit.root;for(const c of hit.contacts)v=sub(v,mul(c.normal,Math.min(0,dot(v,c.normal))));}
  const a=geometry(p,t,v),height=dot(sub(a.h,surfaceOrigin||a.foot),normal);
  if(!a.valid||a.d>maxReach||a.d<minLength||height<minimumHeight||constraints&&!pairValid(p,t)){limitReason='Build travel exhausted';break;}
  compression=Math.max(compression,rest-a.d);frames.push({t,p,v});loadCompression.push(compression);
  // Existing extension margin leaves room for the push. Do not fake a longer
  // buildup by pulling the capsule backwards or slowing its tangent speed.
  if(a.d>maxReach-.025&&dot(v,a.axis)>0){limitReason='Reach limit';break;}
  if(a.d<minLength+.025&&dot(sub(v,a.footVelocity),a.axis)<0||height<minimumHeight+.025&&dot(v,normal)<0){limitReason='Compression limit';break;}
 }
 else for(let i=1;!pairFailure&&i<=Math.ceil(response*1.5/dt);i++){
  const t=i*dt,old=frames.at(-1),a=acceleration(old.p,old.v,old.t),half=add(old.v,mul(a,dt/2));
  let p=add(old.p,mul(half,dt)),v=add(half,mul(acceleration(p,half,t),dt/2)),geo=geometry(p,t,v);
  // Physical safety bounds, not a timer gate. An exhausted leg starts extending early.
  const height=dot(sub(geo.h,surfaceOrigin||geo.foot),normal);
  if(height<minimumHeight){p=add(p,mul(normal,minimumHeight-height));const vn=dot(v,normal);if(vn<0)v=sub(v,mul(normal,vn));limitReason='Surface clearance';geo=geometry(p,t,v);}
  if(geo.d<minLength){p=add(p,mul(geo.axis,minLength-geo.d));const vr=dot(v,geo.axis);if(vr<0)v=sub(v,mul(geo.axis,vr));limitReason='Compression limit';geo=geometry(p,t,v);}
  if(geo.d>maxReach){p=add(p,mul(geo.axis,maxReach-geo.d));limitReason='Reach limit';geo=geometry(p,t,v);}
  // The root capsule and the planted limb must share a trajectory. Correcting
  // the capsule only after playback moves the shoulder away from its pin and
  // seeds release from a different pose than the one actually displayed.
  if(resolveRoot){
   const hit=resolveRoot(old.p,sub(p,old.p),t);p=hit.root;const normals=hit.contacts.map(c=>c.normal);
   for(const n of normals)v=sub(v,mul(n,Math.min(0,dot(v,n))));if(normals.length)limitReason='Capsule contact';
   // Capsule projection can raise the shoulder past a taut arm. Solve the
   // remaining reach correction along the available surface tangent instead
   // of alternating an inward arm projection and an upward capsule lift.
   let tangent=null;
   for(let pass=0;pass<6;pass++){
    geo=geometry(p,t,v);if(geo.d<=maxReach+1e-9)break;
    tangent=geo.axis;for(const n of normals)tangent=sub(tangent,mul(n,Math.max(0,dot(tangent,n))));
    if(length(tangent)<1e-8)break;tangent=unit(tangent);
    const along=dot(sub(geo.h,geo.foot),tangent),disc=along*along-(geo.d*geo.d-maxReach*maxReach);if(disc<0)break;
    const correction=mul(tangent,-Math.max(0,along-Math.sqrt(disc))),resolved=resolveRoot(p,correction,t);p=resolved.root;normals.push(...resolved.contacts.map(c=>c.normal));limitReason='Reach limit';
   }
   geo=geometry(p,t,v);
   if(geo.d>=maxReach-1e-7){
    tangent=geo.axis;for(const n of normals)tangent=sub(tangent,mul(n,Math.max(0,dot(tangent,n))));
    const radial=dot(sub(v,geo.footVelocity),geo.axis),den=dot(tangent,geo.axis);if(radial>0&&den>1e-8)v=sub(v,mul(tangent,radial/den));
   }
  }
  if(!geo.valid)limitReason='Contact lost';
  if(constraints){
   const joint=projectPair(old.p,p,t);
   if(!joint.valid){pairFailure=true;limitReason=joint.reason;break;}
   p=joint.p;v=pairVelocity(p,v,t,joint.normals);geo=geometry(p,t,v);if(joint.reason)limitReason=joint.reason;
  }
  compression=Math.max(compression,rest-geo.d);frames.push({t:i*dt,p,v});loadCompression.push(compression);
  if(limitReason||(geo.d>maxReach-.025&&dot(v,geo.axis)>0))break;
  if(i*dt>=Math.min(.02,response)&&(dot(sub(v,geo.footVelocity),geo.axis)>=0&&compression>.001||impact<.05))break;
 }
 function planDrive(loadIndex){
 const loaded=frames[loadIndex],loadDuration=loaded.t,spring=authoredBuild?[0,0,0]:sub(acceleration(loaded.p,loaded.v,loaded.t),g);
 startPush(loadDuration);
 const available=Math.max(0,.5*impact*impact+9.81*(origin[1]-loaded.p[1]));
 const compression=loadCompression[loadIndex],storedEnergy=Math.min(.5*stiffness*compression*compression,available);
 // Rebound is returned impact energy, added once to the active jump's energy.
 const returnedEnergy=pairFailure?0:Math.min(storedEnergy*rebound,.5*launchSpeed*launchSpeed);
 const targetSpeed=Math.sqrt(launchSpeed*launchSpeed+2*returnedEnergy),targetVelocity=add(carry(loaded.v,normal,direction),mul(direction,targetSpeed));
 let pushDuration=clamp(response*.6,.025,.1);
 function push(t){const deltaV=sub(sub(sub(targetVelocity,loaded.v),mul(g,pushDuration)),mul(spring,pushDuration/2)),u=clamp(t/pushDuration,0,1),s=u*u*(3-2*u),integral=pushDuration*(u*u*u-.5*u*u*u*u);
  let p=add(loaded.p,add(mul(loaded.v,t),add(mul(g,.5*t*t),add(mul(spring,.5*t*t-t*t*t/(6*pushDuration)),mul(deltaV,integral))))),v=add(loaded.v,add(mul(g,t),add(mul(spring,t-t*t/(2*pushDuration)),mul(deltaV,s))));
  if(resolveRoot){const hit=resolveRoot(loaded.p,sub(p,loaded.p),loadDuration+t);p=hit.root;for(const c of hit.contacts)v=sub(v,mul(c.normal,Math.min(0,dot(v,c.normal))));}
  return {p,v};
 }
 const valid=t=>{const p=push(t),c=rolling(t,p.p),h=add(p.p,anchorOffset?anchorOffset(loadDuration+t):offset),d=length(sub(h,c.foot));return c.valid&&d<=maxReach+1e-8&&d>=minLength-1e-8&&dot(sub(h,surfaceOrigin||c.foot),normal)>=minimumHeight-1e-8&&(!constraints||pairValid(p.p,loadDuration+t));};
 // Fit the drive inside remaining leg travel; never stretch the pinned limb.
 while(!pairFailure&&pushDuration>.0081&&![.25,.5,.75,1].every(u=>valid(pushDuration*u)))pushDuration=Math.max(.008,pushDuration*.75);
 let pushTime=pairFailure?0:pushDuration;
 for(let i=0;!pairFailure&&i<=Math.ceil(pushDuration/dt);i++){const t=Math.min(pushDuration,i*dt);if(!valid(t)){let lo=Math.max(0,t-dt),hi=t;for(let j=0;j<20;j++){const mid=(lo+hi)/2;if(valid(mid))lo=mid;else hi=mid;}pushTime=lo;break;}}
 // A hand contact with no usable extension is a miss, not a tiny fraction of
 // an arbitrarily shortened drive. Keep its passive velocity and fall away.
 if(surfaceOrigin&&pushTime<=.001)pushTime=0;
 const full=pushTime>=pushDuration-1e-7&&valid(pushDuration),end=push(pushTime);return {loaded,loadDuration,spring,storedEnergy,returnedEnergy,targetSpeed,targetVelocity,pushDuration,pushTime,push,full,end};
 }
 function planExtension(loadIndex){
 const loaded=frames[loadIndex],loadDuration=loaded.t;startPush(loadDuration);
 const a=upperLength,b=lowerLength,T=clamp(response*.6,.025,.1),w=3/T,eps=1/2400;
 const compression=loadCompression[loadIndex],storedEnergy=Math.min(.5*stiffness*compression*compression,Math.max(0,.5*impact*impact+9.81*(origin[1]-loaded.p[1]))),returnedEnergy=Math.min(storedEnergy*rebound,.5*launchSpeed*launchSpeed),targetSpeed=Math.sqrt(launchSpeed*launchSpeed+2*returnedEnergy),targetVelocity=add(carry(loaded.v,normal,direction),mul(direction,targetSpeed));
 // Drive the requested change in velocity, including removal of incoming
 // surface-normal motion. Using the outgoing heading here would retain part
 // of the inward velocity when that heading is skewed away from the normal.
 const impulse=sub(targetVelocity,loaded.v),drive=length(impulse)>1e-9?unit(impulse):direction;
 const tangent=v=>sub(v,mul(drive,dot(v,drive))),vt=tangent(loaded.v),gt=tangent(g);
 const socket=t=>anchorOffset?anchorOffset(loadDuration+t):offset;
 const c0=rolling(0,loaded.p),h0=add(loaded.p,socket(0)),d0=length(sub(h0,c0.foot));
 const theta=d=>Math.acos(clamp((d*d-a*a-b*b)/(2*a*b),-1,1));
 const theta0=theta(d0),goal=theta(maxReach),branch=dot(sub(h0,c0.foot),drive)>=0?1:-1,velocityStep=1e-5,nextRoot=add(loaded.p,mul(loaded.v,velocityStep)),nextFoot=rolling(velocityStep,nextRoot).foot;
 const relativeVelocity=add(loaded.v,mul(sub(sub(socket(velocityStep),socket(0)),sub(nextFoot,c0.foot)),1/velocityStep)),radialVelocity=dot(unit(sub(h0,c0.foot)),relativeVelocity);
 const thetaDot=-d0*radialVelocity/Math.max(1e-12,a*b*Math.sin(theta0));
 const error=theta0-goal,coefficient=thetaDot+w*error;
 const bend=t=>goal+(error+coefficient*t)*Math.exp(-w*t);
 const cache=new Map();
 function position(t){
  if(t<0){const p=add(loaded.p,mul(loaded.v,t));return {p,raw:p,valid:true,geometric:true,contacts:[]};}
  const key=Math.round(t*1e10);if(cache.has(key))return cache.get(key);
  const angle=bend(t),distance=Math.sqrt(a*a+b*b+2*a*b*Math.cos(angle));
  const base=add(loaded.p,add(mul(vt,t),mul(gt,.5*t*t)));let p=add(loaded.p,mul(loaded.v,t)),valid=angle>=goal-1e-8&&angle<=Math.PI;
  for(let pass=0;pass<4;pass++){
   const contact=rolling(t,p),delta=sub(add(base,socket(t)),contact.foot),along=dot(delta,drive),disc=distance*distance-dot(delta,delta)+along*along;
   valid=valid&&contact.valid&&disc>=0;if(!valid)break;
   const next=add(base,mul(drive,-along+branch*Math.sqrt(Math.max(0,disc))));if(length(sub(next,p))<1e-9){p=next;break;}p=next;
  }
  const raw=p,geometric=valid;let contacts=[];if(resolveRoot){const hit=resolveRoot(loaded.p,sub(p,loaded.p),loadDuration+t);p=hit.root;contacts=hit.contacts;}
  const contact=rolling(t,p),h=add(p,socket(t)),d=length(sub(h,contact.foot));
  valid=valid&&contact.valid&&d<=maxReach+1e-7&&d>=minLength-1e-7&&dot(sub(h,surfaceOrigin||contact.foot),normal)>=minimumHeight-1e-7&&(!constraints||pairValid(p,loadDuration+t));
  const result={p,raw,valid,geometric,contacts};cache.set(key,result);return result;
 }
 function derivatives(t){const center=position(t);let h=eps,left,right;for(let i=0;i<12;i++){left=position(t-h);right=position(t+h);if(left.geometric&&right.geometric)break;h*=.5;}
  let v,a;if(left.geometric&&right.geometric){v=mul(sub(right.raw,left.raw),1/(2*h));a=mul(add(sub(right.raw,mul(center.raw,2)),left.raw),1/(h*h));}
  else {h=Math.min(eps,t/2);const p=position(t-h),q=position(t-2*h);v=mul(add(sub(mul(center.raw,3),mul(p.raw,4)),q.raw),1/(2*h));a=mul(add(sub(center.raw,mul(p.raw,2)),q.raw),1/(h*h));}
  const hv=Math.min(1e-5,Math.max(1e-8,t/2)),vm=position(t-hv),vp=position(t+hv);
  if(vm.geometric&&vp.geometric)v=mul(sub(vp.raw,vm.raw),1/(2*hv));
  else if(t>=2*hv){const vm2=position(t-2*hv);if(vm.geometric&&vm2.geometric)v=mul(add(sub(mul(center.raw,3),mul(vm.raw,4)),vm2.raw),1/(2*hv));}
  return {v,a};
 }
 function push(t){const p=position(t);let v=t===0?loaded.v:derivatives(t).v;for(const c of p.contacts)v=sub(v,mul(c.normal,Math.min(0,dot(v,c.normal))));return {p:p.p,v};}
 function reaction(t){return dot(sub(derivatives(t).a,g),normal);}
 const budget=t=>dot(sub(push(t).v,targetVelocity),direction)>=0;
 let pushTime=0,reason='No compressive reaction',previous=0;
 const horizon=Math.max(T*4,dt),limit=Math.ceil(horizon/dt);
 if(position(0).valid&&reaction(eps)>0&&!budget(0))for(let i=1;i<=limit;i++){
  const t=Math.min(horizon,i*dt),okay=position(t).valid&&reaction(t)>0&&!budget(t);
  if(!okay){let lo=previous,hi=t;for(let k=0;k<18;k++){const m=(lo+hi)/2;if(position(m).valid&&reaction(m)>0&&!budget(m))lo=m;else hi=m;}pushTime=lo;reason=!position(t).valid?'Reach released':budget(t)?'Requested energy reached':'Reaction released';break;}
  previous=t;pushTime=t;reason='Extension horizon';
 }
 const end=push(pushTime);
 return {loaded,loadDuration,spring:[0,0,0],storedEnergy,returnedEnergy,targetSpeed,targetVelocity,pushDuration:T,pushTime,push,full:pushTime>0,end,reason,theta0,thetaDot,releaseBend:bend(pushTime),reaction:reaction(pushTime)};
 }
 function selectExtension(){
 let loadIndex=frames.length-1,plan=planExtension(loadIndex),bestError=Infinity;
 const remaining=p=>dot(sub(p.targetVelocity,p.end.v),direction);
 // End actuation when its requested energy is delivered. Release carries that
 // velocity; it never clips velocity or accelerates a shorter drive to fit.
 for(let i=frames.length-1;i>=0;i--){const chosen=i===frames.length-1?plan:planExtension(i);
  if(chosen.pushTime>0&&remaining(chosen)>=-1e-8&&remaining(chosen)<bestError){plan=chosen;loadIndex=i;bestError=remaining(chosen);if(bestError<1e-4)break;}
 }
 startPush(plan.loadDuration);return {plan,loadIndex,reason:plan.reason};
  }

 let loadIndex=frames.length-1,plan;
 if(upperLength>0&&lowerLength>0){const selected=selectExtension();plan=selected.plan;loadIndex=selected.loadIndex;limitReason=selected.reason;}
 else {
 plan=planDrive(loadIndex);
 // A longer buildup must leave room to reverse the incoming velocity. If
 // the drive exhausts limb travel while still moving against its push direction,
 // try earlier loading endpoints. Prefer the longest complete drive; among
 // equal drives retain the latest buildup. No root braking or limb stretching.
 if(authoredBuild&&plan.pushTime<plan.pushDuration-1e-7&&dot(plan.end.v,direction)<0&&!pairFailure){
  const last=loadIndex,indices=[...new Set(Array.from({length:Math.min(last,8)},(_,k)=>Math.round(last-1-k*(last-1)/Math.max(1,Math.min(last,8)-1))))];
  for(const i of indices){const candidate=planDrive(i);if(candidate.full&&candidate.pushTime>plan.pushTime+1e-9){plan=candidate;loadIndex=i;limitReason='Push travel reserved';}}
  startPush(plan.loadDuration);
 }
 }
 const {loaded,loadDuration,spring,storedEnergy,returnedEnergy,targetSpeed,targetVelocity,pushDuration,pushTime,push}=plan;
 compression=loadCompression[loadIndex];frames.length=loadIndex+1;
 const releaseTime=loadDuration+pushTime,released=push(pushTime);
 function load(t){if(frames.length===1)return {p:frames[0].p,v:frames[0].v};const f=clamp(t/dt,0,frames.length-1),i=Math.min(frames.length-2,Math.floor(f)),a=frames[i],b=frames[i+1],u=clamp((t-a.t)/dt,0,1),u2=u*u,u3=u2*u;
  const frame={p:add(add(mul(a.p,2*u3-3*u2+1),mul(b.p,-2*u3+3*u2)),add(mul(a.v,(u3-2*u2+u)*dt),mul(b.v,(u3-u2)*dt))),v:add(add(mul(a.p,(6*u2-6*u)/dt),mul(b.p,(-6*u2+6*u)/dt)),add(mul(a.v,3*u2-4*u+1),mul(b.v,3*u2-2*u)))};
  if(constraints&&!authoredBuild){const joint=projectPair(a.p,frame.p,t);if(joint.valid){frame.p=joint.p;frame.v=pairVelocity(frame.p,frame.v,t,joint.normals);}}
  return frame;
 }
 function sample(t){if(t<loadDuration)return load(Math.max(0,t));if(t<=releaseTime)return push(t-loadDuration);
  const elapsed=t-releaseTime,vy=Math.max(-cap,released.v[1]),tc=Math.max(0,(vy+cap)/9.81),a=Math.min(elapsed,tc),y=vy*a-4.905*a*a-cap*Math.max(0,elapsed-tc);
  return {p:add(released.p,[released.v[0]*elapsed,y,released.v[2]*elapsed]),v:[released.v[0],Math.max(-cap,vy-9.81*elapsed),released.v[2]]};
 }
 return {extension:upperLength>0&&lowerLength>0?{initialBend:plan.theta0,initialBendSpeed:plan.thetaDot,releaseBend:plan.releaseBend,targetSpeed:plan.targetSpeed,speed:dot(plan.end.v,direction),reason:plan.reason}:null,sample,loadDuration,releaseTime,didPush:upperLength>0&&lowerLength>0?pushTime>1e-9:pushTime>.001,compression,storedEnergy,returnedEnergy,limitReason,frames,released,apex:releaseTime+Math.max(0,released.v[1])/9.81};
}
const api={create};if(typeof module!=='undefined')module.exports=api;else root.BodyflipBounce=api;
})(globalThis);
