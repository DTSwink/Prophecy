(function(root){
'use strict';
const R=typeof module!=='undefined'?require('./recovery.js'):root.Recovery,C=typeof module!=='undefined'?require('./core.js'):root.BodyflipCore;
const S=typeof module!=='undefined'?require('./support.js'):root.BodyflipSupport;
const B=typeof module!=='undefined'?require('./bounce.js'):root.BodyflipBounce;
const K=typeof module!=='undefined'?require('./capsule.js'):root.BodyflipCapsule;
const {add,sub,mul,rotate,qm,qinv,qslerp}=R,clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const finish=(points,q)=>({points,q,axes:q.map(R.toAxes)});
function translate(p,delta){return finish(p.points.map(v=>add(v,delta)),p.q);}
function decodeNN(data){return {names:['root',...data.names],fps:data.fps,duration:data.duration,poses:data.poses.map((p,i)=>{const q=[[0,0,0,1],...p.axes.map(R.fromAxes)];return finish([data.roots[i],...p.points],q);}),roots:data.roots,source:data.source};}
function decodeJump(data){return {name:data.name,fps:data.fps,duration:data.duration,poses:data.frames.map(frame=>{const points=frame.map(v=>[v[0]*.01,v[2]*.01,v[1]*.01]),q=frame.map(v=>R.fromAxes([[1,0,0],[0,1,0],[0,0,1]].map((axis,k)=>{const a=rotate(v.slice(3),axis);return [a[0],a[2],a[1]].map(x=>k===1?-x:x);})));return finish(points,q);})};}
function at(clip,t,parents,loop=false){clip.locals ||= clip.poses.map(p=>R.localize(p.points,p.q,parents));t=loop?((t%clip.duration)+clip.duration)%clip.duration:clamp(t,0,clip.duration);const f=t*clip.fps,i=Math.min(clip.poses.length-2,Math.floor(f));const a=clip.locals[i],b=clip.locals[i+1],u=clamp(f-i,0,1);return R.fk({p:a.p.map((v,j)=>add(v,mul(sub(b.p[j],v),u))),q:a.q.map((v,j)=>qslerp(v,b.q[j],u))},parents);}
function localRoot(p){return translate(p,mul(p.points[0],-1));}
function cappedFall(t,cap,g=9.81){const tc=cap/g;if(t<=tc)return {y:-.5*g*t*t,v:-g*t};return {y:-.5*g*tc*tc-cap*(t-tc),v:-cap};}
function trimStart(clip){
 if(clip.takeoff)return clip.takeoff;
 // Keep the sample immediately before meaningful root ascent; ignore sub-mm export noise.
 const base=clip.poses[0].points[0][1],rise=clip.poses.findIndex(p=>p.points[0][1]>base+.005),first=Math.max(0,rise-1);
 if(rise<1)throw Error('Jump start has no root ascent: '+clip.name);
 const sourceStart=first/clip.fps;
 return clip.takeoff={name:clip.name,fps:clip.fps,sourceStart,duration:clip.duration-sourceStart,poses:clip.poses.slice(first),supportFoot:clip.name.endsWith('Lfoot')?'L':'R'};
}
function jumpDirection(normal,skew){return rotate(R.qexp(mul(R.qlog(R.fromTo(normal,[0,1,0])),clamp(skew,0,1))),normal);}
// Keep only incoming motion tangent to both the contact and authored push.
// Sequential projections can reintroduce inward velocity on an inclined plane.
function carryVelocity(incoming,normal,direction){
 const line=R.cross(normal,direction),squared=R.dot(line,line);
 return squared>1e-12?mul(line,R.dot(incoming,line)/squared):sub(incoming,mul(normal,R.dot(incoming,normal)));
}
function create(run,jumps,settings,parents,reference=run.poses[0],context={}){
 C.registerRig(run.names,parents,reference);
 settings=C.sanitize(settings);
 const supportStart=context.time??(settings.runSeconds-settings.jumpEarly),runOrigin=run.poses[0].points[0],n=run.poses.length-1;
 const speed=(run.poses[n].points[0][2]-runOrigin[2])/(n/run.fps),runDistance=speed*settings.runSeconds,edge=settings.mode==='idle'?5:runDistance-.12;
 const worldRun=context.poseAt||run.sample||(time=>translate(at(run,time,parents),[-runOrigin[0],0,-runOrigin[2]+Math.max(0,time-run.duration)*speed]));
 const last=worldRun(supportStart);
 const surface=context.surface||S.ground(edge);
 const supportVelocity=context.velocityAt?context.velocityAt(supportStart):mul(sub(worldRun(supportStart+1/240).points[0],last.points[0]),240);
 const support=S.plan(last,run.names,parents,settings,surface,context.speed??speed,t=>worldRun(supportStart+t),supportVelocity);
 const selectionTime=supportStart+(Number.isFinite(support.jumpDelay)?support.jumpDelay:0),velocity=mul(sub(worldRun(selectionTime+1/120).points[0],worldRun(Math.max(0,selectionTime-1/120)).points[0]),60);
 const takeoffSpeed=Math.hypot(velocity[0],velocity[2]),standingThreshold=C.walkForwardSpeed*settings.standRatio,jumpStyle=takeoffSpeed<standingThreshold?'Stand':'Run';
 const candidates=jumps.filter(c=>c.name.includes('_Start_'+jumpStyle+'_')).map(trimStart),start=candidates.find(c=>c.supportFoot===support.leg.side),loop=jumps.find(c=>c.name.endsWith('_Loop_Fall'));
 if(!start)throw Error('Missing '+jumpStyle+' jump for '+support.leg.side+' foot');
 const heights=start.poses.map(p=>p.points[0][1]),apexIndex=heights.indexOf(Math.max(...heights)),clipApex=apexIndex/start.fps;let apex=clipApex;
 const contactTime=supportStart+support.jumpDelay;
 let jumpStart=contactTime,runEnd=localRoot(support.terminal.pose),jumpRoot=support.terminal.pose.points[0],bounce=null;
 const incoming=context.velocityAt&&Number.isFinite(jumpStart)?context.velocityAt(jumpStart):[0,0,speed];
 const launchV=(heights[Math.min(2,heights.length-1)]-heights[0])*start.fps/2;
 const direction=jumpDirection(surface.normal,settings.jumpSkew);
 const tangent=context.velocityAt?carryVelocity(incoming,surface.normal,direction):[0,0,speed];
 const horizontal=context.velocityAt?add(tangent,mul(direction,launchV)):[0,0,speed];
 const pelvis=run.names.indexOf('pelvis'),l=support.leg;let launchLocal=R.localize(runEnd.points,runEnd.q,parents);
 const supportBones=[l.hip,l.knee,l.foot,l.toe];
 // Keep the pelvis on the launch-root trajectory. The animation owns the other
 // local joints; the planted leg is solved separately until its reach boundary.
 let release=Infinity;
 const sourceLoopStart=Math.max(apex+.35,start.duration-.25),loopBlend=.25;
 let animationOffset=0,loopStart=sourceLoopStart,bodyEntry=null,legEntry=null;
 const loopEntry=C.transition(t=>localRoot(at(start,sourceLoopStart+t,parents)),t=>localRoot(at(loop,t,parents,true)),loopBlend,parents);
 const animationTime=t=>t+animationOffset;
 function jumpAnimation(t,unretimed=false){
  const sourceTime=unretimed?t:animationTime(t);
  let pose=localRoot(at(start,sourceTime,parents));
  if(sourceTime>=sourceLoopStart)pose=loopEntry(sourceTime-sourceLoopStart);
  return pose;
 }
 const heightAt=t=>{const f=clamp(t*start.fps,0,heights.length-1),i=Math.min(heights.length-2,Math.floor(f));return heights[i]+(heights[i+1]-heights[i])*(f-i);};
 function airPose(t){
  let pose=bounce&&!bounce.didPush?localRoot(at(loop,t,parents,true)):jumpAnimation(t);const animationPose=pose;
  if(t<settings.jumpBlend&&bodyEntry)pose=bodyEntry(t);
  const local=R.localize(pose.points,pose.q,parents);
  for(const i of [0,pelvis]){local.p[i]=launchLocal.p[i];local.q[i]=launchLocal.q[i];}
  // Both use the same animation clock, but their entry blends stay independent.
  if(t>release&&t<settings.jumpBlend){const source=R.localize(animationPose.points,animationPose.q,parents);for(const i of supportBones){local.p[i]=source.p[i];local.q[i]=source.q[i];}}
  if(t<=release)for(const i of supportBones){local.p[i]=launchLocal.p[i];local.q[i]=launchLocal.q[i];}
  // The support hip socket must not translate when the leg hands back to animation.
  local.p[l.hip]=launchLocal.p[l.hip];
  pose=R.fk(local,parents);
  if(bounce){const motion=bounce.sample(t+bounce.loadDuration);return {pose:translate(pose,motion.p),root:motion.p,vy:motion.v[1]};}
  let height,vy;
  if(t<=apex){height=heightAt(t)-heights[0];const h0=heightAt(Math.max(0,t-.002)),h1=heightAt(Math.min(apex,t+.002));vy=(h1-h0)/.004;}
  else {const f=cappedFall(t-apex,settings.fallCap);height=heights[apexIndex]-heights[0]+f.y;vy=f.v;}
  if(context.velocityAt){
   if(t<=apex){height=height*direction[1]+tangent[1]*t;vy=vy*direction[1]+tangent[1];}
   else {const fall=fallFrom(t-apex,tangent[1],settings.fallCap);height=(heights[apexIndex]-heights[0])*direction[1]+tangent[1]*apex+fall.y;vy=fall.v;}
  }
  const rootPos=add(jumpRoot,[horizontal[0]*t,height,horizontal[2]*t]);return {pose:translate(pose,rootPos),root:rootPos,vy};
 }
 // The sole proximity gate captures a nearby cone-valid contact for the push.
 // Find the first reach boundary once during preparation; seek/loop order cannot
 // alter planting or release. Inactive playback does no planning work.
 function findRelease(contactAt){
  const excess=t=>{const c=contactAt(t);return c.valid?R.length(sub(c.foot,airPose(t).pose.points[l.hip]))-support.maxReach:1;};
  let lastTime=0;
  for(let i=0;i<=480;i++){const t=i/240;if(excess(t)>=0||i===480){let lo=lastTime,hi=t;for(let j=0;j<18;j++){const mid=(lo+hi)*.5;if(excess(mid)>=0)hi=mid;else lo=mid;}return lo;}lastTime=t;}
 }
 const footAxes=support.terminal.pose.axes[l.foot],toeDelta=sub(support.terminal.pose.points[l.toe],support.terminal.foot);
 const footForward=R.mul(footAxes[1],R.dot(footAxes[1],toeDelta)<0?-1:1);
 const landingPitch=-Math.asin(clamp(R.dot(footForward,surface.normal),-1,1))*180/Math.PI;
 const previousContactPose=support.jumpDelay>=C.motionStep?support.sample(support.jumpDelay-C.motionStep).pose:worldRun(contactTime-C.motionStep);
 const contactMotion=S.contactMotion(support.terminal,l,surface,settings,Number.isFinite(contactTime)?{footQ:previousContactPose.q[l.foot],toeQ:previousContactPose.q[l.toe]}:null);
 let loadDuration=0;
 if(!(settings.loadMs>0))contactMotion.startPush(0);
 const rollingAt=t=>contactMotion.sample(t+loadDuration);
 // Loading keeps incoming momentum and gravity; its root path replaces clip height.
 function loadingPose(t){
  const p=worldRun(contactTime+t),local=R.localize(p.points,p.q,parents),motion=bounce.sample(t);
  local.p[0]=motion.p;local.q[0]=support.terminal.pose.q[0];
  for(const i of [pelvis,l.hip]){local.p[i]=launchLocal.p[i];if(i===pelvis)local.q[i]=launchLocal.q[i];}
  const contact=contactMotion.sample(t);
  return S.solve(R.fk(local,parents),l,contact.foot,parents,settings.supportReach,contact.rotation);
 }
 if(settings.loadMs>0&&Number.isFinite(contactTime)){
  bounce=B.create({root:jumpRoot,hip:support.terminal.pose.points[l.hip],foot:support.terminal.foot,normal:surface.normal,direction,incoming,reach:l.reach,maxReach:support.maxReach,loadMs:settings.loadMs,rebound:settings.rebound,launchSpeed:Math.sqrt(2*9.81*(heights[apexIndex]-heights[0])),cap:settings.fallCap,rolling:rollingAt,carry:carryVelocity,loading:contactMotion.sample,startPush:t=>{loadDuration=t;contactMotion.startPush(t);}});
  runEnd=localRoot(loadingPose(bounce.loadDuration));launchLocal=R.localize(runEnd.points,runEnd.q,parents);
  jumpStart=contactTime+bounce.loadDuration;apex=bounce.apex-bounce.loadDuration;
 }
 release=bounce?bounce.releaseTime-bounce.loadDuration:Number.isFinite(jumpStart)?findRelease(rollingAt):0;
 const contactAt=t=>rollingAt(Math.min(t,release));
 const releaseContact=contactAt(release);
 const released=Number.isFinite(jumpStart)?S.solve(airPose(release).pose,l,releaseContact.foot,parents,settings.supportReach,releaseContact.rotation):null;
 let matchTime=release,matchDistance=null,legRate=1;
 if(settings.matchLeg&&(!bounce||bounce.didPush)&&released&&release<loopStart){
  const wanted=rotate(qinv(released.q[pelvis]),sub(released.points[l.foot],released.points[pelvis]));
  let best=Infinity;
  // Compare ankle positions in the same pelvis frame and with the actual hip
  // socket. Search once on preparation, never per rendered frame.
  for(let i=0;i<=Math.ceil(loopStart*start.fps);i++){
   const time=Math.min(i/start.fps,loopStart),p=at(start,time,parents),local=R.localize(p.points,p.q,parents);
   const ankle=add(launchLocal.p[l.hip],add(rotate(local.q[l.hip],local.p[l.knee]),rotate(qm(local.q[l.hip],local.q[l.knee]),local.p[l.foot]))),distance=R.length(sub(ankle,wanted));
   if(distance<best-1e-9||(Math.abs(distance-best)<=1e-9&&Math.abs(time-release)<Math.abs(matchTime-release))){best=distance;matchTime=time;}
  }
  matchDistance=best;
  // Start every animated joint at the matched pose on push. Root motion and
  // contact timing remain procedural; no limb waits for the others to catch up.
  animationOffset=matchTime;loopStart=Math.max(0,sourceLoopStart-animationOffset);
 }
 const legTime=animationTime;
 // Seed from the actual moving pose immediately before each handoff. Body
 // starts on push; the support chain starts independently when its pin releases.
 if(Number.isFinite(jumpStart)){
  const beforePush=t=>localRoot(t===0?runEnd:bounce&&bounce.loadDuration>0?loadingPose(bounce.loadDuration+t):support.sample(Math.max(0,support.jumpDelay+t)).pose);
  const bodyTarget=t=>bounce&&!bounce.didPush?localRoot(at(loop,t,parents,true)):jumpAnimation(t);
  bodyEntry=C.transition(beforePush,bodyTarget,settings.jumpBlend,parents);
  const legTarget=t=>{const p=jumpAnimation(release+t),local=R.localize(p.points,p.q,parents);local.p[l.hip]=launchLocal.p[l.hip];return R.fk(local,parents);};
  legEntry=C.transition(t=>{const age=release+t,c=contactAt(age);return S.solve(airPose(age).pose,l,c.foot,parents,settings.supportReach,c.rotation);},legTarget,settings.legBlend,parents,supportBones);
 }
 const abortTime=supportStart+support.abortDelay;
 // A failed plant never borrows jump height. Keep momentum, release IK, then fall off the ledge.
 const edgeTime=edge/speed,fallStart=Math.max(abortTime,edgeTime),fallRoot=Number.isFinite(fallStart)?worldRun(fallStart).points[0]:null;
 // Capture the displayed pelvis at the edge, including an unfinished abort
 // blend. Fall animation may pose the limbs but cannot lift/drop the pelvis.
 const abortRecovery=Number.isFinite(abortTime)?C.transition(t=>localRoot(support.sample(Math.max(0,support.abortDelay+t)).pose),t=>localRoot(worldRun(abortTime+t)),settings.jumpBlend,parents):null;
 const abortLeg=Number.isFinite(abortTime)&&context.continueAt?C.transition(t=>support.sample(Math.max(0,support.abortDelay+t)).pose,t=>context.continueAt(abortTime+t).pose,settings.legBlend,parents,supportBones):null;
 const fallPose=Number.isFinite(fallStart)?abortRecovery(fallStart-abortTime):null;
 const fallLocal=fallPose?R.localize(fallPose.points,fallPose.q,parents):null;
 const abortFall=fallPose?C.transition(t=>abortRecovery(Math.max(0,fallStart-abortTime+t)),t=>localRoot(at(loop,t,parents,true)),settings.jumpBlend,parents):null;
 function aborted(time){
  if(context.continueAt){const frame=context.continueAt(time),pose=abortLeg(time-abortTime);return {...frame,pose,phase:'MISS · '+frame.phase,supportState:'FAILED',failureReason:support.failureReason,distance:support.terminal.distance};}
  const elapsed=time-abortTime,fallTime=Math.max(0,time-fallStart),fall=cappedFall(fallTime,settings.fallCap);
  let pose=time>=fallStart?abortFall(fallTime):abortRecovery(elapsed);
  if(time>=fallStart){const local=R.localize(pose.points,pose.q,parents);for(const i of [0,pelvis]){local.p[i]=fallLocal.p[i];local.q[i]=fallLocal.q[i];}pose=R.fk(local,parents);}
  const root=worldRun(time).points[0].slice();if(time>=fallStart)root[1]=fallRoot[1]+fall.y;
  return {pose:translate(pose,root),root,phase:time>=fallStart?'ABORT - FALL':settings.mode==='walk'?'ABORT - WALK':'ABORT - RUN',supportState:'FAILED',failureReason:support.failureReason,distance:support.terminal.distance,speed,vy:fall.v,airTime:0};
 }
 function sample(time,flip=0,twist=0,axis=settings.axis){
  if(time<supportStart){const pose=worldRun(time);return {pose,root:pose.points[0],phase:settings.mode==='idle'?'IDLE':settings.mode==='walk'?'WALK':'RUN',speed,vy:0,airTime:0};}
  if(time>=abortTime)return aborted(time);
  if(bounce&&time>=contactTime&&time<jumpStart){const motion=bounce.sample(time-contactTime);return {pose:loadingPose(time-contactTime),root:motion.p,phase:'LOAD',supportState:'PIN',supportTarget:contactMotion.sample(time-contactTime).contact,speed,vy:motion.v[1],airTime:0};}
  if(time<jumpStart){const frame=support.sample(time-supportStart);return {...frame,root:frame.pose.points[0],phase:'SUPPORT',supportState:'APPROACH',supportTarget:frame.surface,speed,vy:0,airTime:0};}
  const t=time-jumpStart,frame=airPose(t);let pose=frame.pose;
  const airTime=Math.max(0,t-release);
  if(airTime>0){const q=C.orientation(flip,twist,axis,pose.q[1]);pose=C.centerPose(pose,q,pose.points[1]);pose.points[0]=frame.root;}
  let supportState='FREE';
  if(t<=release){const c=contactAt(t);pose=S.solve(pose,l,c.foot,parents,settings.supportReach,c.rotation);supportState='PIN';}
  else {
   if(matchDistance!==null&&t<loopStart)supportState='MATCH';
   if(t<release+settings.legBlend){
   const carried=legEntry(t-release),source=R.localize(carried.points,carried.q,parents),local=R.localize(pose.points,pose.q,parents);
   for(const i of supportBones){local.q[i]=source.q[i];if(i!==l.hip)local.p[i]=source.p[i];}
   pose=R.fk(local,parents);supportState='BLEND';
   }
  }
  return {...frame,pose,phase:bounce&&!bounce.didPush?'MISS · FALL':t<release?'PUSH':t<apex?'RISE':t<loopStart?'FALL':'FALL LOOP',supportState,supportTarget:contactAt(t).contact,speed,airTime};
 }
 // Diagnostic only: raw animation leg, carried by the displayed procedural pelvis.
 // No locomotion crossfade, support IK or release blend enters this target.
 function animationLeg(time,displayed,unretimed=false,other=false){
  if(!displayed||bounce&&!bounce.didPush||!Number.isFinite(jumpStart)||time<jumpStart)return null;
  const side=other?(l.side==='L'?'R':'L'):l.side;
  const bones=other?['thigh','calf','foot','ball'].map(name=>run.names.indexOf(name+'_'+side.toLowerCase())):supportBones;
  const t=time-jumpStart,target=jumpAnimation(t,unretimed);
  const source=R.localize(target.points,target.q,parents),local=R.localize(displayed.points,displayed.q,parents);
  for(const i of bones){local.q[i]=source.q[i];local.p[i]=source.p[i];}
  local.p[bones[0]]=launchLocal.p[bones[0]];
  const pose=R.fk(local,parents);
  return {foot:side,pose,points:bones.map(i=>pose.points[i])};
 }
 function coneDebug(time,displayed){
  if(!displayed||time>jumpStart+release||time>abortTime)return null;
  return support.coneForPose(displayed);
 }
 // Both ideal markers use the same root-local candidates as foot selection.
 // After approach, hold them at capture/abort so they do not chase the air pose.
 function idealDebug(time){
  if(time<supportStart)return null;
  const t=Math.min(time-supportStart,support.jumpDelay,support.abortDelay);
  return {surface,targets:support.idealTargets(worldRun(supportStart+t))};
 }
 // Playback-time diagnostic: no timer, so pause/seek/loop show the same three frames.
 function pushDebug(time){
  const age=(time-jumpStart)*60;
  if(bounce&&!bounce.didPush||!Number.isFinite(jumpStart)||jumpStart>=abortTime||age<-1e-7||age>=3-1e-7)return null;
  return {origin:contactAt(0).contact,direction};
 }
 return {sample,animationLeg,coneDebug,idealDebug,pushDebug,contactTime,contactMotion,bounce,surface,direction,carriedVelocity:tangent,incomingVelocity:incoming,landingPitch,animationTime,legTime,matchTime,matchDistance,legRate,edge,speed,takeoffSpeed,standingThreshold,jumpStyle,lift:release,apex,start:start.name,sourceStart:start.sourceStart,supportFoot:l.side,supportScores:support.scores,loopStart,sourceLoopStart,runSeconds:settings.runSeconds,supportStart,jumpStart,abortTime,failureReason:support.failureReason,airStart:jumpStart+release,support,release};
}
function fallFrom(t,v,cap){v=Math.max(-cap,v);const tc=Math.max(0,(v+cap)/9.81),a=Math.min(t,tc);return {y:v*a-.5*9.81*a*a-cap*Math.max(0,t-tc),v:Math.max(-cap,v-9.81*t)};}
function eventsFor(settings){return settings.jumpEvents??[{id:'first',time:Math.round((settings.runSeconds-settings.jumpEarly)*60)/60,surface:'floor'}];}
function sequence(run,jumps,input,parents,reference=run.poses[0],resume=null){
 C.registerRig(run.names,parents,reference);
 const settings=C.sanitize(input),origin=run.poses[0].points[0],speed=(run.poses.at(-1).points[0][2]-origin[2])/((run.poses.length-1)/run.fps),edge=settings.mode==='idle'?5:speed*settings.runSeconds-.12;
 const surfaces=S.scene(edge,settings),events=[],segments=[],loop=jumps.find(c=>c.name.endsWith('_Loop_Fall'));
 const gait=run.sample||(t=>translate(at(run,t,parents),[-origin[0],0,-origin[2]+Math.max(0,t-run.duration)*speed]));
 const edgeTime=settings.mode==='idle'?Infinity:edge/speed,edgePose=gait(Number.isFinite(edgeTime)?edgeTime:0),edgeLocal=R.localize(edgePose.points,edgePose.q,parents),pelvis=run.names.indexOf('pelvis');
 const edgeFall=Number.isFinite(edgeTime)?C.transition(t=>localRoot(gait(edgeTime+t)),t=>localRoot(at(loop,t,parents,true)),settings.jumpBlend,parents):null;
 const baseline=t=>{
  if(t<=edgeTime){const pose=gait(t);return {pose,root:pose.points[0],phase:settings.mode==='idle'?'IDLE':settings.mode==='walk'?'WALK':'RUN',speed,vy:0,airTime:0};}
  const elapsed=t-edgeTime,fall=cappedFall(elapsed,settings.fallCap),root=add(edgePose.points[0],[0,fall.y,speed*elapsed]);
  const p=edgeFall(elapsed),local=R.localize(p.points,p.q,parents);
  for(const i of [0,pelvis]){local.p[i]=i===0?[0,0,0]:edgeLocal.p[i];local.q[i]=edgeLocal.q[i];}
  return {pose:translate(R.fk(local,parents),root),root,phase:'FALL',speed,vy:fall.v,airTime:elapsed};
 };
 const phase=settings.mode==='idle'?'IDLE':settings.mode==='walk'?'WALK':'RUN';
 const fallTransitions=new WeakMap();
 const fallPose=(from,elapsed,fromPose=gait(from),previousPose=gait(from-C.motionStep))=>{
  let transition=fallTransitions.get(fromPose);
  if(!transition){transition=C.transition(t=>localRoot(t<0?previousPose:fromPose),t=>localRoot(at(loop,t,parents,true)),settings.jumpBlend,parents);fallTransitions.set(fromPose,transition);}
  const rest=localRoot(fromPose),p=transition(elapsed),local=R.localize(p.points,p.q,parents),base=R.localize(rest.points,rest.q,parents);
  for(const i of [0,pelvis]){local.p[i]=base.p[i];local.q[i]=base.q[i];}return R.fk(local,parents);
 };
 const horizon=Math.max(12,settings.trimOut,...eventsFor(settings).map(e=>e.time+5));
 const carrierOptions={surfaces,speed,gait,fallPose,cap:settings.fallCap,phase,resume,horizon};
 const baselineCarrier=K.track(baseline,carrierOptions);
 let previous=t=>baselineCarrier.sample(t);
 for(const event of eventsFor(settings)){
  const prior=previous,frame=prior(event.time),last=segments.at(-1);
  if(last&&event.time<Math.min(last.jumpStart+last.release,last.abortTime)-1e-8){events.push({...event,status:'Busy',reason:'Previous support / push still active'});continue;}
  const p=frame.pose;
  const velocityAt=t=>mul(sub(prior(t+1/240).root,prior(Math.max(event.time,t-1/240)).root),1/(t+1/240-Math.max(event.time,t-1/240)));
  const velocity=velocityAt(event.time);
  const ranked=surfaces.map(surface=>{
   const gap=R.length(sub(surface.closest(p.points[pelvis]),p.points[pelvis]));
   const choices=S.candidates(p,run.names,settings,surface,velocity),choice=choices.scores[choices.selected];
   return {surface,gap,available:choice.eligible,contactGap:choice.cone.gap,foot:choice.foot};
  }).sort((a,b)=>Number(b.available)-Number(a.available)||(a.available?a.contactGap-b.contactGap:0)||a.gap-b.gap);
  const surface=event.surface==='auto'?ranked[0]?.surface:surfaces.find(s=>s.id===event.surface);
  if(!surface){events.push({...event,status:'Miss',reason:'Surface disabled'});continue;}
  const segment=create(run,jumps,settings,parents,reference,{time:event.time,surface,poseAt:t=>prior(t).pose,continueAt:prior,velocityAt,speed:Math.hypot(velocity[0],velocity[2])});
  segment.surfaceChoices=ranked.map(r=>({surface:r.surface.id,foot:r.foot,eligible:r.available,contactGap:r.contactGap,pelvisGap:r.gap}));
  segment.event=event;segments.push(segment);
  events.push({...event,surfaceId:surface.id,status:Number.isFinite(segment.jumpStart)&&(!segment.bounce||segment.bounce.didPush)?'Push':'Miss',contactTime:segment.contactTime,pushTime:segment.jumpStart,releaseTime:segment.airStart,reason:segment.bounce&&!segment.bounce.didPush?'Contact ended before push':segment.failureReason});
  const raw=t=>{const air=Math.max(0,t-segment.airStart);return segment.sample(t,settings.airFlip?settings.flipAngle+settings.flipSpeed*air:0,settings.airFlip?settings.twistAngle+settings.twistSpeed*air:0,settings.axis);};
  segment.carrier=K.track(raw,{...carrierOptions,start:event.time,correctPose:(pose,frame)=>{const l=segment.support.leg;return frame.supportState==='PIN'?S.solve(pose,l,frame.pose.points[l.foot],parents,settings.supportReach,{footQ:frame.pose.q[l.foot],toeQ:frame.pose.q[l.toe]}):pose;}});
  previous=t=>t<event.time?prior(t):segment.carrier.sample(t);
 }
 const activeAt=t=>{for(let i=segments.length-1;i>=0;i--)if(t>=segments[i].supportStart)return segments[i];return segments[0]||null;};
 const sample=(t,flip=0,twist=0,axis=settings.axis)=>{
  let segment=null;for(let i=segments.length-1;i>=0;i--)if(t>=segments[i].supportStart){segment=segments[i];break;}
  const frame=segment?segment.carrier.sample(t,segment.sample(t,flip,twist,axis)):baselineCarrier.sample(t);
  return {...frame,supportFoot:segment?.supportFoot,surface:segment?.surface};
 };
 for(let i=0;i<segments.length;i++)segments[i].carrier.prepare(segments[i+1]?.supportStart??horizon);
 baselineCarrier.prepare(segments[0]?.supportStart??horizon);
 return {...(segments[0]||{}),edge,speed,surfaces,events,segments,activeAt,sample,
  capsule:{radius:K.radius,halfHeight:K.halfHeight},get landings(){return [{carrier:baselineCarrier},...segments].flatMap((s,i)=>s.carrier.landings.filter(l=>l.time<(segments[i]?.supportStart??Infinity)).map(l=>({time:l.time,root:l.root,surfaceId:l.surfaceId})));},
  airStartAt:t=>{const s=activeAt(t);return s&&t>=s.supportStart&&!s.carrier.state(t).landed?s.airStart:Infinity;},
  pushDebug:t=>{for(let i=segments.length-1;i>=0;i--){const push=segments[i].pushDebug(t);if(push)return push;}return null;},
  animationLeg:(t,p,unretimed=false,other=false)=>{const s=activeAt(t);return s&&!s.carrier.state(t).landed?s.animationLeg(t,p,unretimed,other):null;},coneDebug:(t,p)=>{const s=activeAt(t);return s&&!s.carrier.state(t).landed?s.coneDebug(t,p):null;},idealDebug:t=>{const s=activeAt(t);return s&&!s.carrier.state(t).landed?s.idealDebug(t):null;}};
}
const continuationCache=new Map();
async function prepare(run,jumps,input,parents,reference,generate,cancelled=()=>false){
 const settings=C.sanitize(input),preparedSeeds=new Map();
 function resume(data){
  const request={gait:settings.mode==='jump'?'run':'walk',drawn:settings.attack==='pike'||settings.attack.startsWith('slash'),names:run.names,frames:data.frames,roots:data.roots,seeds:data.seeds.map(p=>({points:p.points,axes:p.axes}))};
  const key=JSON.stringify(request);let clip=preparedSeeds.get(key)||continuationCache.get(key);
  if(!clip)throw {landingRequest:request,key};
  preparedSeeds.set(key,clip);
  return time=>at(clip,Math.max(0,time-data.time),parents);
 }
 for(;;){
  if(cancelled())return null;
  try{return sequence(run,jumps,settings,parents,reference,resume);}
  catch(error){
   if(!error.landingRequest)throw error;
   const result=await generate(error.landingRequest);
   if(cancelled())return null;
   const clip=decodeNN(result);preparedSeeds.set(error.key,clip);continuationCache.set(error.key,clip);
   while(continuationCache.size>8)continuationCache.delete(continuationCache.keys().next().value);
  }
 }
}
const api={carryVelocity,jumpDirection,decodeNN,decodeJump,at,create,sequence,prepare,eventsFor,cappedFall,localRoot,trimStart};if(typeof module!=='undefined')module.exports=api;else root.BodyflipFlight=api;
})(globalThis);
