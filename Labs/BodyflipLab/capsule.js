/* Root carrier: upright in locomotion; optional posed volumes during jump flight.
 * Standing dimensions match AProphecyAgent::InitCapsuleSize. */
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
function supported(low,surfaces){return surfaces.some(surface=>{const hit=query(low,surface);return hit.gap<skin*3&&top(hit);});}
const locomotion=frame=>['IDLE','WALK','RUN'].includes(frame.phase);
const copyPose=pose=>({...pose,points:pose.points.map(v=>Array.from(v)),q:pose.q.map(v=>Array.from(v)),...(pose.axes?{axes:pose.axes.map(a=>a.map(v=>Array.from(v)))}:{})});
// Per-hand planner payloads contain their own pose and contact arrays. Keep
// those private too, while retaining the shared rig/surface-query objects.
const copyHand=hand=>Object.fromEntries(Object.entries(hand).map(([key,value])=>[key,key==='pose'&&value?copyPose(value):key==='rotation'&&value?Object.fromEntries(Object.entries(value).map(([k,v])=>[k,Array.isArray(v)?v.slice():v])):Array.isArray(value)?value.slice():value]));
function track(source,{start=0,surfaces,speed,gait,fallPose,cap=20,phase='RUN',correctPose=p=>p,resume=null,horizon=12,decorate=null,exactSource=false,cacheResolvedPose=false,body=null,landingBlend=0,parents=null,bodyDuringSupport=false,supportAirborne=false,forceSource=false,excludeBody=()=>[],breakTimes=[],initialYaw=0,headingAt=()=>[0,0,0,1],rootMotion=null}){
 // Retain the source curve between collision ticks. Interpolating its absolute
 // root instead can move a pinned wrist just before its release handoff.
 breakTimes=breakTimes.filter(t=>Number.isFinite(t)&&t>start).sort((a,b)=>a-b);
 const sourceCache=new Map(),sampleSource=t=>{const key=Math.round(t*1e9);if(sourceCache.has(key))return sourceCache.get(key);const frame=source(t);sourceCache.set(key,frame);if(sourceCache.size>2048)sourceCache.delete(sourceCache.keys().next().value);return frame;};
 const fallSeeds=new WeakMap(),resolvedPoses=cacheResolvedPose?new WeakMap():null;
 function falling(motion,from,elapsed){
  let starts=fallSeeds.get(motion);if(!starts){starts=new Map();fallSeeds.set(motion,starts);}
  let seed=starts.get(from);if(!seed){seed=adapter&&state(from).normal?[sample(from).pose,sample(Math.max(start,from-C.motionStep)).pose]:[motion(from),motion(from-C.motionStep)];starts.set(from,seed);}
  return fallPose(from,elapsed,...seed);
 }
 const useBody=f=>body&&(bodyDuringSupport||f.airTime>0||f.phase.includes('FALL'));
 const translatedPose=(frame,at)=>correctPose({...frame.pose,points:frame.pose.points.map(p=>add(p,sub(at,frame.root)))},frame);
 const initial=sampleSource(start),placement=useBody(initial)?{root:initial.root,contacts:[]}:move(initial.root,[0,0,0],surfaces),initialGround=useBody(initial)?null:surfaces.map(s=>query(placement.root,s)).find(h=>h.gap<skin*3&&top(h));
 // A released support stays the same contact until its shape lifts clear.
 // It still collides, but cannot turn its own push into a new locomotion landing.
 const supportContacts=new Map(),contactKey=c=>c.bone+'@'+c.surface.id;
 const frames=[{t:start,root:placement.root,mode:!forceSource&&locomotion(initial)?'loco':'source',normal:initialGround?.normal||null,surfaceId:initialGround?.surface.id||null,vy:0,velocity:[0,initial.vy||0,speed],bias:[0,0,0],fallStart:start,landed:false}],landings=[];
 function ensure(time){
  while(frames.at(-1).t<time-1e-9){
   const prev=frames.at(-1);
   // Stationary supported idle needs no collision integration until a new marker.
   if(prev.mode==='loco'&&prev.normal&&speed===0)return;
   // Replace the nearest ordinary tick with the contact boundary. Keeping
   // both a boundary and a nearly coincident tick would divide contact skin
   // corrections by a microscopic interval and invent a velocity spike.
   const merge=breakTimes.length?dt/2:0,tick=start+(breakTimes.length?Math.floor((prev.t-start+merge)/dt+1e-8)+1:frames.length)*dt;
   const t=breakTimes.find(v=>v>prev.t+1e-9&&v<=tick+merge)??tick,h=t-prev.t;let raw,delta,vy=prev.vy;
   if(prev.mode==='loco'){
    const horizontal=rootMotion&&!prev.landing?sub(rootMotion(t),rootMotion(prev.t)):[0,0,speed*h];horizontal[1]=0;
    if(prev.normal)horizontal[1]=-dot(prev.normal,horizontal)/prev.normal[1];
    vy=Math.max(-cap,(prev.normal?0:vy)-9.81*h);delta=add(horizontal,[0,vy*h,0]);
   }else {raw=sampleSource(t);delta=add(sub(raw.root,sampleSource(prev.t).root),mul(prev.bias,h));}
   const posed=prev.mode==='source'&&useBody(raw),proposed=add(prev.root,delta);
   const previousRaw=posed?sampleSource(prev.t):null,previousPose=posed?translatedPose(previousRaw,prev.root):null,excluded=posed?excludeBody(raw):[];
   if(posed&&body.contacts){
    const names=excludeBody(previousRaw).filter(name=>!excluded.includes(name));
    if(names.length)for(const c of body.contacts(previousPose,surfaces,names))if(c.gap<=skin*4)supportContacts.set(contactKey(c),c);
   }
   let resolved=posed?body.move(previousPose,translatedPose(raw,proposed),surfaces,excluded):move(prev.root,delta,surfaces);
   if(posed&&body.resolve)for(let pass=0;pass<4;pass++){const contactPose=translatedPose(raw,resolved.root),fix=body.resolve(contactPose,surfaces,excluded),shift=sub(fix.root,contactPose.points[0]);if(length(shift)<skin)break;resolved={root:add(resolved.root,shift),contacts:[...resolved.contacts,...fix.contacts]};}
   // Once a push has planted, another hand/foot touching down is additional
   // support, not a new fall landing that cancels the pending push. Keep the
   // collision response and retain ownership until that contact lifts clear.
   if(posed&&raw.supportState==='PIN')for(const c of resolved.contacts)if(top(c)&&/^(foot|ball|hand)_[lr]$/.test(c.bone||''))supportContacts.set(contactKey(c),c);
   const up=resolved.contacts.find(c=>top(c)&&!supportContacts.has(contactKey(c))),next={...prev,t,root:resolved.root,normal:null,surfaceId:up?.surface.id||null,vy,bias:prev.bias.slice()};
   if(posed&&body.contacts&&supportContacts.size){
    const names=[...new Set([...supportContacts.values()].map(c=>c.bone))];
    for(const c of body.contacts(translatedPose(raw,resolved.root),surfaces,names))if(c.gap>skin*4)supportContacts.delete(contactKey(c));
   }
   delete next.bodyRoot;
   if(prev.mode==='loco'){
    next.normal=up?.normal||null;if(up)next.vy=0;
    if(prev.normal&&!next.normal)next.fallStart=prev.t;
   }else {
    next.normal=up?.normal||null;
    const airborne=raw.airTime>0||raw.phase.includes('FALL')||bodyDuringSupport&&supportAirborne;
    if(airborne&&delta[1]<0&&up){
     next.mode='loco';next.normal=up.normal;next.vy=0;next.bias=[0,0,0];next.landed=true;
     if(posed){next.bodyRoot=next.root.slice();next.root=move(next.root,[0,0,0],surfaces).root;}
    }else if(airborne&&resolved.contacts.length){
     if(posed){let velocity=mul(delta,1/h);for(const c of resolved.contacts)velocity=sub(velocity,mul(c.normal,Math.min(0,dot(velocity,c.normal))));next.bias=add(prev.bias,sub(velocity,mul(delta,1/h)));}
     else next.bias=add(prev.bias,mul(sub(sub(next.root,prev.root),delta),1/h));
    }
   }
   if(up&&delta[1]<0&&((prev.mode==='source'&&next.landed)||(prev.mode==='loco'&&!prev.normal))){
    const landing={time:t,surfaceId:up.surface.id,root:next.root.slice(),bodyRoot:next.bodyRoot?.slice(),rebase:next.bodyRoot?sub(next.root,next.bodyRoot):null,bone:up.bone||null,beforeMode:prev.mode,fallStart:prev.fallStart,prior:prev.landing||null};
    next.landing=landing;next.landed=true;landings.push(landing);
   }
   next.velocity=next.mode==='loco'&&next.normal&&speed===0?[0,0,0]:mul(sub(next.bodyRoot||next.root,prev.root),1/h);
   frames.push(next);
  }
 }
 function frameIndex(time){if(!breakTimes.length)return Math.max(0,Math.min(frames.length-1,Math.floor((time-start)/dt+1e-8)));let lo=0,hi=frames.length-1;while(lo<hi){const mid=Math.ceil((lo+hi)/2);if(frames[mid].t<=time+1e-10)lo=mid;else hi=mid-1;}return lo;}
 function state(time){ensure(time);const index=frameIndex(time),a=frames[index],b=frames[Math.min(index+1,frames.length-1)],u=clamp((time-a.t)/(b.t-a.t||dt),0,1);
  let root=add(a.root,mul(sub(a===b?b.root:b.bodyRoot||b.root,a.root),u));
  if(exactSource&&a.mode==='source'&&b.mode==='source'){
   const original=add(sampleSource(a.t).root,mul(sub(sampleSource(b.t).root,sampleSource(a.t).root),u));
   root=add(root,sub(sampleSource(time).root,original));
   if(!useBody(sampleSource(time)))root=move(root,[0,0,0],surfaces).root;
  }
  return {...a,root};
 }
 function resolvedPose(frame,at,cache=false){
  // Hand source frames are immutable within this track. The same frame and
  // exact capsule root have the same contact solve; retain only that pose,
  // never landing/velocity metadata or a result from a different source frame.
  const previous=cache?resolvedPoses.get(frame):null;
  if(previous&&at.every((v,i)=>Math.abs(v-previous.root[i])<1e-10))return copyPose(previous.pose);
  const offset=sub(at,frame.root),pose=correctPose({...frame.pose,points:frame.pose.points.map(p=>add(p,offset))},frame);
  if(cache)resolvedPoses.set(frame,{root:at.slice(),pose});
  // Rendering/API callers may edit their pose; never expose cached arrays.
  return cache?copyPose(pose):pose;
 }
 function beforeLanding(landing,time){
  if(landing.beforeMode==='source'){const s=state(time);let pose=resolvedPose(sampleSource(time),s.bodyRoot||s.root,cacheResolvedPose);if(s.bodyRoot)pose.points[0]=s.root.slice();if(time>=landing.time-1e-9&&body?.resolve){const fix=body.resolve(pose,surfaces),shift=sub(fix.root,pose.points[0]);pose={...pose,points:pose.points.map((p,i)=>i===0?p:add(p,shift))};}return pose;}
  if(adapter&&time<landing.fallStart)return sample(time).pose;
  const previousGait=landing.prior?continuation(landing.prior):gait;
  const pose=time<landing.fallStart?previousGait(time):falling(previousGait,landing.fallStart,time-landing.fallStart);
  return resolvedPose({pose,root:pose.points[0]},state(time).root);
 }
 function continuation(landing,sampleTime=null){
  const count=Math.max(2,Math.ceil(Math.max(horizon-landing.time,landingBlend)*30)+1);
  if(landing.motion&&(landing.motionFrames>=count||(sampleTime!==null&&sampleTime<=landing.time+(landing.motionFrames-1)/30+1e-8)))return landing.motion;
  const current=beforeLanding(landing,landing.time),previous=beforeLanding(landing,Math.max(start,landing.time-1/30));
  if(landing.rebase)previous.points[0]=add(previous.points[0],landing.rebase);
  const heading=landing.heading||(landing.heading=headingAt(current)),inverse=R.qinv(heading),origin=landing.root;
  const transform=(pose,q,pivot)=>{const rotations=pose.q.map(v=>R.qm(q,v));return {...pose,points:pose.points.map(v=>add(pivot,R.rotate(q,sub(v,pivot)))),q:rotations,axes:rotations.map(R.toAxes)};};
  // The airborne source rotates its virtual root; the locomotion codec uses
  // an identity root frame. Rebase that reference only, keeping every physical
  // bone in world space. Blending both reference frames would orbit the pelvis.
  for(const pose of [previous,current]){
   pose.q=pose.q.slice();pose.q[0]=heading.slice();
   pose.axes=pose.q.map(R.toAxes);
  }
  if(resume){
   const roots=Array.from({length:Math.max(12,count+9)},(_,i)=>state(Math.max(start,landing.time+(i-1)/30)).root);
   if(landing.rebase)roots[0]=add(roots[0],landing.rebase);
   // Run the unchanged policy in the landing pelvis's horizontal frame. Transform
   // the complete history and root commands together, then return world poses.
   const localPrediction=resume({time:landing.time,frames:count,seeds:[previous,current].map(p=>transform(p,inverse,origin)),roots:roots.map(p=>add(origin,R.rotate(inverse,sub(p,origin))))});
   // Retain the pushing limb's release clock in the incoming trajectory. Do
   // this before the handoff blend so its first pose/velocity stays continuous.
   const predicted=time=>correctPose(transform(localPrediction(time),heading,origin),{returnedToLocomotion:true,time});
   // Follow the actual seeded rollout. Back-extrapolating a future policy pose
   // across the whole blend invents rotations/translations the NN never made.
   if(landingBlend>0&&parents){
    const outgoing=t=>C.blend(previous,current,1+t*30,parents);
    const blend=C.transition(outgoing,t=>predicted(landing.time+t),landingBlend,parents,null,false,true);
    landing.motion=time=>blend(Math.max(0,time-landing.time));
   }else landing.motion=predicted;
  }else {
   // Planning-only callers can inspect collision without a policy. Production
   // prepare() always supplies a seeded continuation before exposing playback.
   landing.motion=()=>current;
  }
  landing.motionFrames=count;return landing.motion;
 }
 function prepare(time){ensure(time);for(const landing of landings)if(landing.time<=time)continuation(landing);adapter?.prepare(time);}
 function sampleBase(time,rawOverride){
  const s=state(time),raw=rawOverride||sampleSource(time);let frame=raw;
  if(s.mode==='loco'){
   const motion=s.landing?continuation(s.landing,time):gait;
   const pose=s.normal?motion(time):falling(motion,s.fallStart,time-s.fallStart);
   frame={pose,root:pose.points[0],phase:s.normal?phase:'FALL',speed,vy:s.vy,airTime:s.normal?0:time-s.fallStart};
  }
  const offset=sub(s.root,frame.root);let pose=resolvedPose(frame,s.root,cacheResolvedPose&&s.mode==='source');
  if(s.mode==='loco'&&s.landing&&body?.resolve){
   // The recurrent policy can pass a knee/torso through the floor while
   // recovering from a low landing pose. Keep the standing root reference,
   // and resolve the posed body above it without changing joint rotations.
   const contact=body.resolve(pose,surfaces),shift=sub(contact.root,pose.points[0]);
   if(length(shift)>0)pose={...pose,points:pose.points.map((p,i)=>i===0?p:add(p,shift))};
  }
  const handInertia=frame.handInertia?{...frame.handInertia,com:add(frame.handInertia.com,offset),velocity:add(frame.handInertia.velocity,s.bias)}:null;
  const physical=frame.physical?{...frame.physical,com:add(frame.physical.com,offset),velocity:add(frame.physical.velocity,s.bias)}:null;
  if(physical&&['RISE','FALL','FALL LOOP'].includes(frame.phase))frame={...frame,phase:physical.velocity[1]>0?'RISE':frame.phase==='RISE'?'FALL':frame.phase};
  // Carrier yaw is independent of the authored FBX root and airborne spin.
  // Only an actual landing adopts the heading used to seed locomotion.
  const forward=s.landing?.heading?R.rotate(s.landing.heading,[0,0,1]):null,yaw=forward?Math.atan2(forward[0],forward[2]):initialYaw;
  return {...frame,...(cacheResolvedPose&&frame.hands?{hands:frame.hands.map(copyHand)}:{}),...(handInertia?{handInertia}:{}),...(physical?{physical}:{}),pose,root:s.root,velocity:s.velocity,vy:s.velocity[1],capsule:{radius,halfHeight,yaw,poseContact:s.mode==='source'&&!!useBody(raw),grounded:!!s.normal,landed:s.landed,surfaceId:s.surfaceId,normal:s.normal,landingTime:s.landing?.time??null,landingBone:s.landing?.bone||null},returnedToLocomotion:s.mode==='loco'&&s.landed};
 }
 const adapter=decorate?.(sampleBase,{start,surfaces});
 function sample(time,rawOverride){return adapter?adapter.sample(time,rawOverride):sampleBase(time,rawOverride);}
 return {sample,ensure,prepare,state,landings,setHorizon:time=>{horizon=time;},get preparedRootThrough(){return frames.at(-1).t;}};
}
const api={radius,halfHeight,query,sweep,move,track,supported};if(typeof module!=='undefined')module.exports=api;else root.BodyflipCapsule=api;
})(globalThis);
