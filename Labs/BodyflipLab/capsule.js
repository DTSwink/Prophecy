/* Upright swept root carrier. Dimensions match AProphecyAgent::InitCapsuleSize. */
(function(root){
'use strict';
const R=typeof module!=='undefined'?require('./recovery.js'):root.Recovery;
const C=typeof module!=='undefined'?require('./core.js'):root.BodyflipCore;
const {add,sub,mul,dot,length,unit}=R,clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const radius=.30,halfHeight=.86,skin=1e-6,dt=1/240,boxes=new WeakMap();
function nearby(low,delta,surface){let bounds=boxes.get(surface);if(!bounds){const b=surface.box,axes=[b.forward,b.side,b.up],extent=[0,1,2].map(k=>axes.reduce((v,a,i)=>v+Math.abs(a[k])*b.dims[i]/2,0));bounds={min:sub(b.center,extent),max:add(b.center,extent)};boxes.set(surface,bounds);}const end=add(low,delta);return [0,1,2].every(k=>Math.max(low[k],end[k])+(k===1?2*halfHeight:radius)+skin>=bounds.min[k]&&Math.min(low[k],end[k])-(k===1?0:radius)-skin<=bounds.max[k]);}
function query(low,surface){
 const box=surface.box,axes=[box.forward,box.side,box.up],half=box.dims.map(x=>x/2);
 const local=p=>axes.map(a=>dot(sub(p,box.center),a));
 const a=local(add(low,[0,radius,0])),b=local(add(low,[0,2*halfHeight-radius,0])),d=sub(b,a),cuts=[0,1];
 for(let k=0;k<3;k++)if(Math.abs(d[k])>1e-12)for(const sign of [-1,1]){const t=(sign*half[k]-a[k])/d[k];if(t>0&&t<1)cuts.push(t);}
 cuts.sort((a,b)=>a-b);let best=Infinity,axisPoint,boxPoint;
 const visit=t=>{const p=add(a,mul(d,t)),q=p.map((v,k)=>clamp(v,-half[k],half[k])),dist=dot(sub(p,q),sub(p,q));if(dist<best){best=dist;axisPoint=p;boxPoint=q;}};
 for(let i=0;i<cuts.length-1;i++){
  const lo=cuts[i],hi=cuts[i+1],mid=(lo+hi)/2;let numerator=0,denominator=0;
  for(let k=0;k<3;k++){const v=a[k]+d[k]*mid;if(Math.abs(v)>half[k]){numerator+=d[k]*(a[k]-Math.sign(v)*half[k]);denominator+=d[k]*d[k];}}
  visit(lo);visit(hi);if(denominator>0)visit(clamp(-numerator/denominator,lo,hi));
 }
 let distance=Math.sqrt(best),normal;
 if(distance>1e-10)normal=axes.reduce((s,axis,k)=>add(s,mul(axis,(axisPoint[k]-boxPoint[k])/distance)),[0,0,0]);
 else {
  // The axis itself overlaps: minimal face separation for the full capsule.
  const center=local(add(low,[0,halfHeight,0])),overlap=half.map((h,k)=>h+radius+Math.abs(axes[k][1])*(halfHeight-radius)-Math.abs(center[k]));
  const k=overlap.indexOf(Math.min(...overlap));normal=mul(axes[k],center[k]<0?-1:1);distance=radius-overlap[k];
 }
 return {gap:distance-radius,normal,surface};
}
function sweep(low,delta,surfaces){
 let first=null;
 for(const surface of surfaces){
  if(!nearby(low,delta,surface))continue;
  let t=0;
  for(let i=0;i<32&&t<=1;i++){
   const q=query(add(low,mul(delta,t)),surface),closing=-dot(delta,q.normal);
   if(q.gap<=skin*2){if(closing>1e-10||q.gap<-skin){const hit={...q,fraction:t};if(!first||t<first.fraction)first=hit;}break;}
   if(closing<=1e-12)break;
   t+=(q.gap-skin)/closing;
   if(first&&t>first.fraction)break;
  }
 }
 return first;
}
function move(low,delta,surfaces){
 let p=low.slice(),remaining=delta.slice();const contacts=[];
 for(let i=0;i<6;i++){
  let deepest=null;for(const s of surfaces){if(!nearby(p,[0,0,0],s))continue;const q=query(p,s);if(q.gap<-skin&&(!deepest||q.gap<deepest.gap))deepest=q;}
  if(!deepest)break;p=add(p,mul(deepest.normal,-deepest.gap+skin));contacts.push({...deepest,fraction:0});
 }
 for(let i=0;i<5&&length(remaining)>1e-10;i++){
  const hit=sweep(p,remaining,surfaces);if(!hit){p=add(p,remaining);break;}
  p=add(p,mul(remaining,hit.fraction));contacts.push(hit);remaining=mul(remaining,1-hit.fraction);
  remaining=sub(remaining,mul(hit.normal,Math.min(0,dot(remaining,hit.normal))));
 }
 return {root:p,contacts};
}
const top=hit=>hit.normal[1]>1e-5&&dot(hit.normal,hit.surface.normal)>1e-5;
const locomotion=frame=>['IDLE','WALK','RUN'].includes(frame.phase);
function track(source,{start=0,surfaces,speed,gait,fallPose,cap=20,phase='RUN',correctPose=p=>p,resume=null,horizon=12,decorate=null}){
 const fallSeeds=new Map();
 function falling(motion,from,elapsed){
  let starts=fallSeeds.get(motion);if(!starts){starts=new Map();fallSeeds.set(motion,starts);}
  let seed=starts.get(from);if(!seed){seed=adapter&&state(from).normal?[sample(from).pose,sample(Math.max(start,from-C.motionStep)).pose]:[motion(from),motion(from-C.motionStep)];starts.set(from,seed);}
  return fallPose(from,elapsed,...seed);
 }
 const initial=source(start),placement=move(initial.root,[0,0,0],surfaces),initialGround=surfaces.map(s=>query(placement.root,s)).find(h=>h.gap<skin*3&&top(h));
 const frames=[{t:start,root:placement.root,mode:locomotion(initial)?'loco':'source',normal:initialGround?.normal||null,surfaceId:initialGround?.surface.id||null,vy:0,velocity:[0,initial.vy||0,speed],bias:[0,0,0],fallStart:start,landed:false}],landings=[];
 function ensure(time){
  while(frames.at(-1).t<time-1e-9){
   const prev=frames.at(-1);
   // Stationary supported idle needs no collision integration until a new marker.
   if(prev.mode==='loco'&&prev.normal&&speed===0)return;
   const t=start+frames.length*dt;let raw,delta,vy=prev.vy;
   if(prev.mode==='loco'){
    const horizontal=[0,0,speed*dt];
    if(prev.normal)horizontal[1]=-dot(prev.normal,horizontal)/prev.normal[1];
    vy=Math.max(-cap,(prev.normal?0:vy)-9.81*dt);delta=add(horizontal,[0,vy*dt,0]);
   }else {raw=source(t);delta=add(sub(raw.root,source(prev.t).root),mul(prev.bias,dt));}
   const resolved=move(prev.root,delta,surfaces),up=resolved.contacts.find(top),next={...prev,t,root:resolved.root,normal:null,surfaceId:up?.surface.id||null,vy,bias:prev.bias.slice()};
   if(prev.mode==='loco'){
    next.normal=up?.normal||null;if(up)next.vy=0;
    if(prev.normal&&!next.normal)next.fallStart=prev.t;
   }else {
    next.normal=up?.normal||null;
    const airborne=raw.airTime>0||raw.phase.includes('FALL');
    if(airborne&&delta[1]<0&&up){
     next.mode='loco';next.normal=up.normal;next.vy=0;next.bias=[0,0,0];next.landed=true;
    }else if(airborne&&resolved.contacts.length)next.bias=add(prev.bias,mul(sub(sub(next.root,prev.root),delta),1/dt));
   }
   if(up&&delta[1]<0&&((prev.mode==='source'&&next.landed)||(prev.mode==='loco'&&!prev.normal))){
    const landing={time:t,surfaceId:up.surface.id,root:next.root.slice(),beforeMode:prev.mode,fallStart:prev.fallStart,prior:prev.landing||null};
    next.landing=landing;next.landed=true;landings.push(landing);
   }
   next.velocity=next.mode==='loco'&&next.normal&&speed===0?[0,0,0]:mul(sub(next.root,prev.root),1/dt);
   frames.push(next);
  }
 }
 function state(time){ensure(time);const index=Math.max(0,Math.min(frames.length-1,Math.floor((time-start)/dt+1e-8))),a=frames[index],b=frames[Math.min(index+1,frames.length-1)];return {...a,root:add(a.root,mul(sub(b.root,a.root),clamp((time-a.t)/dt,0,1)))};}
 function resolvedPose(frame,at){const offset=sub(at,frame.root);return correctPose({...frame.pose,points:frame.pose.points.map(p=>add(p,offset))},frame);}
 function beforeLanding(landing,time){
  if(landing.beforeMode==='source')return resolvedPose(source(time),state(time).root);
  if(adapter&&time<landing.fallStart)return sample(time).pose;
  const previousGait=landing.prior?continuation(landing.prior):gait;
  const pose=time<landing.fallStart?previousGait(time):falling(previousGait,landing.fallStart,time-landing.fallStart);
  return resolvedPose({pose,root:pose.points[0]},state(time).root);
 }
 function continuation(landing){
  if(landing.motion)return landing.motion;
  const current=beforeLanding(landing,landing.time),previous=beforeLanding(landing,Math.max(start,landing.time-1/30));
  if(resume){
   const count=Math.max(2,Math.ceil((horizon-landing.time)*30)+1);
   const roots=Array.from({length:count+9},(_,i)=>state(Math.max(start,landing.time+(i-1)/30)).root);
   landing.motion=resume({time:landing.time,frames:count,seeds:[previous,current],roots});
  }else {
   // Planning-only callers can inspect collision without a policy. Production
   // prepare() always supplies a seeded continuation before exposing playback.
   landing.motion=()=>current;
  }
  return landing.motion;
 }
 function prepare(time){ensure(time);for(const landing of landings)if(landing.time<=time)continuation(landing);adapter?.prepare(time);}
 function sampleBase(time,rawOverride){
  const s=state(time),raw=rawOverride||source(time);let frame=raw;
  if(s.mode==='loco'){
   const motion=s.landing?continuation(s.landing):gait;
   const pose=s.normal?motion(time):falling(motion,s.fallStart,time-s.fallStart);
   frame={pose,root:pose.points[0],phase:s.normal?phase:'FALL',speed,vy:s.vy,airTime:s.normal?0:time-s.fallStart};
  }
  const offset=sub(s.root,frame.root),translated={...frame.pose,points:frame.pose.points.map(p=>add(p,offset))},pose=correctPose(translated,frame);
  return {...frame,pose,root:s.root,velocity:s.velocity,vy:s.velocity[1],capsule:{radius,halfHeight,grounded:!!s.normal,landed:s.landed,surfaceId:s.surfaceId,normal:s.normal,landingTime:s.landing?.time??null},returnedToLocomotion:s.mode==='loco'&&s.landed};
 }
 const adapter=decorate?.(sampleBase,{start,surfaces});
 function sample(time,rawOverride){return adapter?adapter.sample(time,rawOverride):sampleBase(time,rawOverride);}
 return {sample,ensure,prepare,state,landings};
}
const api={radius,halfHeight,query,sweep,move,track};if(typeof module!=='undefined')module.exports=api;else root.BodyflipCapsule=api;
})(globalThis);
