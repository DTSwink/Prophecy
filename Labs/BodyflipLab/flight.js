(function(root){
'use strict';
const Physical=typeof module!=='undefined'?require('./physical-flight.js'):root.BodyflipPhysicalFlight,PhysicalAim=typeof module!=='undefined'?require('./physical-aim.js'):root.BodyflipPhysicalAim;
const SC=typeof module!=='undefined'?require('./spin-contact.js'):root.BodyflipSpinContact;
const R=typeof module!=='undefined'?require('./recovery.js'):root.Recovery,C=typeof module!=='undefined'?require('./core.js'):root.BodyflipCore;
const S=typeof module!=='undefined'?require('./support.js'):root.BodyflipSupport;
const H=typeof module!=='undefined'?require('./hand-support.js'):root.BodyflipHandSupport;
const N=typeof module!=='undefined'?require('./hand-inertia.js'):root.BodyflipHandInertia;
const B=typeof module!=='undefined'?require('./bounce.js'):root.BodyflipBounce;
const K=typeof module!=='undefined'?require('./capsule.js'):root.BodyflipCapsule;
const P=typeof module!=='undefined'?require('./body-contact.js'):root.BodyflipBodyContact;
const IK=typeof module!=='undefined'?require('./foot-ik.js'):root.BodyflipFootIK;
const M=typeof module!=='undefined'?require('./jump-motion.js'):root.BodyflipJumpMotion;
const D=typeof module!=='undefined'?require('./mass.js'):root.BodyflipMass,O=typeof module!=='undefined'?require('./spin.js'):root.BodyflipSpin;
const A=typeof module!=='undefined'?require('./jump-attack.js'):root.BodyflipJumpAttack,G=typeof module!=='undefined'?require('./space-gym.js'):root.BodyflipSpace;
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
// One height reference for every grounded push. Animation/foot choice must
// not change the meaning of Jump %. Space gym retains its existing impulse.
function jumpHeight(jumps){const clip=trimStart(jumps.find(c=>c.name.includes('_Start_Run_Lfoot'))||jumps.find(c=>c.name.includes('_Start_')));return Math.max(...clip.poses.map(p=>p.points[0][1]))-clip.poses[0].points[0][1];}
function jumpDirection(normal,skew){return rotate(R.qexp(mul(R.qlog(R.fromTo(normal,[0,1,0])),clamp(skew,0,1))),normal);}
// Keep only incoming motion tangent to both the contact and authored push.
// Sequential projections can reintroduce inward velocity on an inclined plane.
function carryVelocity(incoming,normal,direction){
 const line=R.cross(normal,direction),squared=R.dot(line,line);
 return squared>1e-12?mul(line,R.dot(incoming,line)/squared):sub(incoming,mul(normal,R.dot(incoming,normal)));
}
function create(run,jumps,settings,parents,reference=run.poses[0],context={}){
 C.registerRig(run.names,parents,reference);H.registerRig(reference);
 settings=C.sanitize(settings);
 const jumpScale=context.jumpScale??1,jumpTimeScale=Math.sqrt(jumpScale),launchSpeed=Math.sqrt(2*9.81*jumpHeight(jumps)*jumpScale),build=C.jumpBuild(settings,jumpScale*100),authoredBuild=build.ms>settings.loadMs;
 const supportStart=context.time??(settings.runSeconds-settings.jumpEarly),runOrigin=run.poses[0].points[0],n=run.poses.length-1;
 const speed=(run.poses[n].points[0][2]-runOrigin[2])/(n/run.fps),runDistance=speed*settings.runSeconds,edge=settings.mode==='idle'?5:runDistance-.12;
 const hand=context.hand&&context.hand!=='foot',limbBlend=hand?settings.handReturn:settings.legBlend;
 const contactBody=P.create(run.names,parents,reference),handShapes=['hand_l','hand_r'];
 const priorPose=context.poseAt||run.sample||(time=>translate(at(run,time,parents),[-runOrigin[0],0,-runOrigin[2]+Math.max(0,time-run.duration)*speed]));
 // Once a marker takes over, the previous jump's hypothetical future
 // landing must not inject a new locomotion policy into this support motion.
 const incomingFrame=p=>hand?H.reframe(localRoot(p)):localRoot(p);
 const incomingBody=context.articulationAt?C.transition(t=>incomingFrame(priorPose(supportStart+t)),t=>incomingFrame(context.articulationAt(supportStart+t)),hand?settings.handBend:settings.jumpBlend,parents,null,false,true):null;
 const incomingRootOffset=incomingBody?sub(priorPose(supportStart).points[0],context.articulationAt(supportStart).points[0]):null;
 const incomingRootVelocity=incomingBody?mul(sub(sub(priorPose(supportStart).points[0],priorPose(supportStart-C.motionStep).points[0]),sub(context.articulationAt(supportStart).points[0],context.articulationAt(supportStart-C.motionStep).points[0])),1/C.motionStep):null;
 // After this marker owns the body, an earlier segment's hypothetical landing
 // cannot rebase the root underneath the support planner. Retain its raw
 // flight curve, anchored at takeover; this jump's body carrier resolves contact.
 const rawWorldRun=time=>{const pose=incomingBody&&time>=supportStart?translate(incomingBody(time-supportStart),add(context.articulationAt(time).points[0],add(incomingRootOffset,mul(incomingRootVelocity,time-supportStart)))):priorPose(time);return hand?H.reframe(pose):pose;};
 const rawStart=rawWorldRun(supportStart);
 const surface=context.surface||S.ground(edge);
 const grounded=context.grounded??(context.surfaces?K.supported(rawStart.points[0],context.surfaces):false);
 const footBuild=!hand&&authoredBuild&&build.depth>0;
 const preparationStart=footBuild&&grounded&&context.anticipate?Math.max(0,context.notBefore??0,supportStart-(build.ms-settings.loadMs)/1000):supportStart;
 const preparationReach=footBuild?['L','R'].map(side=>S.leg(rawStart,run.names,side)).reduce((sum,l)=>sum+l.reach,0)/2:0;
 let depthStop=Infinity;
 const preparationDepth=time=>{if(!footBuild)return 0;const u=clamp((Math.min(time,depthStop)-preparationStart)/(build.ms/1000),0,1);return build.depth*preparationReach*u*u*u*(10+u*(-15+6*u));};
 const worldRun=time=>{
  const p=rawWorldRun(time),depth=footBuild?preparationDepth(time):0;if(depth<=0)return p;
  let lowered={...p,points:p.points.map((v,i)=>i===0?v:sub(v,mul(surface.normal,depth)))};
  // The root and gait keep advancing. Bend the knees under the lowered pelvis
  // while retaining the gait's foot trajectories, rather than sinking the shoes.
  if(grounded)for(const side of ['L','R']){const leg=S.leg(p,run.names,side);lowered=S.solve(lowered,leg,p.points[leg.foot],parents,1,leg);}
  return lowered;
 };
 const last=worldRun(supportStart);
 const supportVelocity=context.velocityAt?context.velocityAt(supportStart):mul(sub(worldRun(supportStart+1/240).points[0],last.points[0]),240);
 const supportSettings=hand?{...settings,handSide:context.hand==='handL'?'L':context.hand==='handR'?'R':context.hand==='handBoth'?'Both':'Auto'}:settings;
 const solver=hand?H:S;
 const approachInertia=hand?N.create(t=>{const pose=priorPose(t);return {pose,root:pose.points[0]};},{release:supportStart,cap:settings.fallCap,names:run.names,parents,reference}):null;
 const approachContext=!grounded&&approachInertia?.diagnostics.enabled?{inertia:{names:run.names,parents,reference,comAt:t=>t<0?S.com(priorPose(supportStart+t),run.names,parents,reference):approachInertia.trajectory(supportStart+t).position,resolveRoot:context.surfaces?(p,delta,posed)=>contactBody.resolve(posed,context.surfaces,handShapes):null}}:null;
 const support=solver.plan(last,run.names,parents,supportSettings,surface,context.speed??speed,t=>worldRun(supportStart+t),supportVelocity,hand?context.handChoice:null,hand?approachContext:null);
 const selectionTime=supportStart+(Number.isFinite(support.jumpDelay)?support.jumpDelay:0),velocity=mul(sub(worldRun(selectionTime+1/120).points[0],worldRun(Math.max(0,selectionTime-1/120)).points[0]),60);
 const takeoffSpeed=Math.hypot(velocity[0],velocity[2]),standingThreshold=C.walkForwardSpeed*settings.standRatio,jumpStyle=takeoffSpeed<standingThreshold?'Stand':'Run';
 const candidates=jumps.filter(c=>c.name.includes('_Start_'+jumpStyle+'_')).map(trimStart),start=candidates.find(c=>c.supportFoot===support.leg.side),loop=jumps.find(c=>c.name.endsWith('_Loop_Fall'));
 if(!start)throw Error('Missing '+jumpStyle+' jump for '+support.leg.side+' foot');
 const heights=start.poses.map(p=>p.points[0][1]),apexIndex=heights.indexOf(Math.max(...heights)),clipApex=apexIndex/start.fps;let apex=clipApex*jumpTimeScale;
 const contactTime=supportStart+support.jumpDelay;
 let jumpStart=contactTime,runEnd=localRoot(support.terminal.pose),jumpRoot=support.terminal.pose.points[0],bounce=null;
 let incoming=context.velocityAt&&Number.isFinite(jumpStart)?context.velocityAt(jumpStart):[0,0,speed];
 if(incomingBody&&Number.isFinite(jumpStart))incoming=mul(sub(rawWorldRun(jumpStart+C.motionStep).points[0],rawWorldRun(jumpStart).points[0]),1/C.motionStep);
 if(hand&&support.inertia&&Number.isFinite(contactTime)&&support.jumpDelay>0){
  const h=Math.min(.0001,support.jumpDelay/2),at=t=>support.sample(t).pose.points[0],t=support.jumpDelay;
  incoming=mul(add(sub(mul(at(t),3),mul(at(t-h),4)),at(t-2*h)),1/(2*h));
 }
 const launchV=(heights[Math.min(2,heights.length-1)]-heights[0])*start.fps/2*jumpTimeScale;
 const direction=jumpDirection(surface.normal,settings.jumpSkew);
 const tangent=context.velocityAt?carryVelocity(incoming,surface.normal,direction):[0,0,speed];
 const horizontal=context.velocityAt?add(tangent,mul(direction,launchV)):[0,0,speed];
 const pelvis=run.names.indexOf('pelvis'),l=support.leg;const solveSupport=(...args)=>hand&&support.posture.solve?support.posture.solve(...args):S.solve(...args);let launchLocal=R.localize(runEnd.points,runEnd.q,parents);
 const limbs=hand&&support.paired?support.limbs:[l];
 const supportBones=hand?limbs.flatMap(a=>[parents[a.hip],a.hip,a.knee,a.foot]):[l.hip,l.knee,l.foot,l.toe];
 const solveContacts=(p,c)=>{for(const a of c.hands||[{...c,leg:l}])p=solveSupport(p,a.leg,a.foot,parents,settings.supportReach,a.rotation);return p;};
 const clearFreeHand=p=>hand&&support.posture.freeArm?H.clearHand(p,support.posture.freeArm,surface,parents):p;
 const limitHands=p=>{for(const a of limbs)p=H.limitWrist(p,a);return p;};
 const mean=points=>mul(points.reduce((sum,p)=>add(sum,p),[0,0,0]),1/points.length);
 // Keep the pelvis on the launch-root trajectory. The animation owns the other
 // local joints; the planted leg is solved separately until its reach boundary.
 let release=Infinity,buildPelvisRest=null;
 const sourceLoopStart=Math.max(clipApex+.35,start.duration-.25),loopBlend=.25;
 let animationOffset=0,loopStart=sourceLoopStart,bodyEntry=null,legEntry=null;
 const loopEntry=C.transition(t=>localRoot(at(start,sourceLoopStart+t,parents)),t=>localRoot(at(loop,t,parents,true)),loopBlend,parents);
 const animationTime=t=>t+animationOffset;
 const handLaunch=hand&&support.posture.canCrouch?R.localize(localRoot(last).points,last.q,parents):null;
 const handClipPelvis=handLaunch?R.localize(localRoot(loop.poses[0]).points,loop.poses[0].q,parents).q[pelvis]:null;
 function jumpAnimation(t,unretimed=false){
  if(hand&&!handLaunch)return localRoot(worldRun(jumpStart+t));
  const sourceTime=hand||unretimed?t:animationTime(t);
  let pose=handLaunch?localRoot(at(loop,t,parents,true)):localRoot(at(start,sourceTime,parents));
  if(!handLaunch&&sourceTime>=sourceLoopStart)pose=loopEntry(sourceTime-sourceLoopStart);
  if(handLaunch){
   // A grounded hand launch enters the normal airborne articulation, aligned
   // to its incoming pelvis. Inverted airborne launches retain their own motion.
   const local=R.localize(pose.points,pose.q,parents);local.p[0]=[0,0,0];local.q[0]=[0,0,0,1];
   local.p[pelvis]=handLaunch.p[pelvis];local.q[pelvis]=qm(handLaunch.q[pelvis],qm(qinv(handClipPelvis),local.q[pelvis]));pose=R.fk(local,parents);
  }
  return pose;
 }
 const heightAt=t=>{const f=clamp(t*start.fps,0,heights.length-1),i=Math.min(heights.length-2,Math.floor(f));return heights[i]+(heights[i+1]-heights[i])*(f-i);};
 function airPose(t){
  let pose;
  if(hand){
   // Keep the authored support body through the pin. After release, grounded
   // launches enter the fall loop; airborne launches resume their incoming pose.
   pose=t<=release?localRoot(loadingBody((bounce?.loadDuration||0)+t)):bodyEntry?bodyEntry(t-release):jumpAnimation(t);
  }else{
  pose=bounce&&!bounce.didPush?localRoot(at(loop,t,parents,true)):jumpAnimation(t);const animationPose=pose;
  if(t<settings.jumpBlend&&bodyEntry)pose=bodyEntry(t);
  const local=R.localize(pose.points,pose.q,parents);
  for(const i of [0,pelvis]){local.p[i]=launchLocal.p[i];local.q[i]=launchLocal.q[i];}
  if(buildPelvisRest&&t>release){const u=settings.jumpBlend>0?clamp((t-release)/settings.jumpBlend,0,1):1,ease=u*u*(3-2*u);local.p[pelvis]=add(launchLocal.p[pelvis],mul(sub(buildPelvisRest,launchLocal.p[pelvis]),ease));}
  // Both use the same animation clock, but their entry blends stay independent.
  if(t>release&&t<settings.jumpBlend){const source=R.localize(animationPose.points,animationPose.q,parents);for(const i of supportBones){local.p[i]=source.p[i];local.q[i]=source.q[i];}}
  if(t<=release)for(const i of supportBones){local.p[i]=launchLocal.p[i];local.q[i]=launchLocal.q[i];}
  // The support hip socket must not translate when the leg hands back to animation.
  local.p[l.hip]=launchLocal.p[l.hip];
  pose=R.fk(local,parents);
  }
  if(bounce){const motion=bounce.sample(t+bounce.loadDuration);return {pose:translate(pose,motion.p),root:motion.p,vy:motion.v[1]};}
  let height,vy;
  if(t<=apex){height=(heightAt(t/jumpTimeScale)-heights[0])*jumpScale;const h0=heightAt(Math.max(0,t-.002)/jumpTimeScale),h1=heightAt(Math.min(apex,t+.002)/jumpTimeScale);vy=(h1-h0)/.004*jumpScale;}
  else {const f=cappedFall(t-apex,settings.fallCap);height=(heights[apexIndex]-heights[0])*jumpScale+f.y;vy=f.v;}
  if(context.velocityAt){
   if(t<=apex){height=height*direction[1]+tangent[1]*t;vy=vy*direction[1]+tangent[1];}
   else {const fall=fallFrom(t-apex,tangent[1],settings.fallCap);height=(heights[apexIndex]-heights[0])*jumpScale*direction[1]+tangent[1]*apex+fall.y;vy=fall.v;}
  }
  const rootPos=add(jumpRoot,[horizontal[0]*t,height,horizontal[2]*t]);return {pose:translate(pose,rootPos),root:rootPos,vy};
 }
 // The sole proximity gate captures a nearby cone-valid contact for the push.
 // Find the first reach boundary once during preparation; seek/loop order cannot
 // alter planting or release. Inactive playback does no planning work.
 function findRelease(contactAt){
  const excess=t=>{const c=contactAt(t),p=airPose(t).pose;return c.valid?Math.max(...(c.hands||[{...c,leg:l}]).map(a=>R.length(sub(a.foot,p.points[a.leg.hip]))-a.leg.reach*settings.supportReach)):1;};
  let lastTime=0;
  for(let i=0;i<=480;i++){const t=i/240;if(excess(t)>=0||i===480){let lo=lastTime,hi=t;for(let j=0;j<18;j++){const mid=(lo+hi)*.5;if(excess(mid)>=0)hi=mid;else lo=mid;}return lo;}lastTime=t;}
 }
 const footAxes=support.terminal.pose.axes[l.foot],toeDelta=hand?rotate(support.terminal.pose.q[l.foot],[l.side==='L'?.145:-.145,0,0]):sub(support.terminal.pose.points[l.toe],support.terminal.foot);
 const footForward=R.mul(footAxes[1],R.dot(footAxes[1],toeDelta)<0?-1:1);
 const landingPitch=-Math.asin(clamp(R.dot(footForward,surface.normal),-1,1))*180/Math.PI;
 const previousContactPose=support.jumpDelay>=C.motionStep?support.sample(support.jumpDelay-C.motionStep).pose:worldRun(contactTime-C.motionStep);
 let loadDuration=0,loadCommitted=false;
 function loadingBody(t){
  const p=hand?support.body(support.jumpDelay+t):worldRun(contactTime+t);
  if(footBuild)return p;
  if(!authoredBuild)return p;
  const age=loadCommitted?Math.min(t,loadDuration):t,u=clamp(age/(build.ms/1000),0,1),ease=u*u*u*(10+u*(-15+6*u));
  const depth=build.depth*limbs.reduce((sum,a)=>sum+a.reach,0)/limbs.length*ease;
  const height=R.dot(sub(p.points[pelvis],p.points[0]),surface.normal),startHeight=R.dot(sub(support.terminal.pose.points[pelvis],support.terminal.pose.points[0]),surface.normal),delta=mul(surface.normal,startHeight-depth-height);
  // Keep every source rotation and the root trajectory. Only the pelvis's
  // translation relative to root (and thus its descendants) is authored.
  return {...p,points:p.points.map((v,i)=>i===0?v:add(v,delta))};
 }
 // Contact planning uses the continuing turn as well as the local body pose.
 // Otherwise the displayed hip moves while the push planner sees a frozen hip.
 const contactMass=D.model(run.names,parents,reference),contactBodyPose=(t,bodyTime=t)=>{const p=loadingBody(bodyTime);return !hand&&context.contactSpinAt?D.rotateAboutCOM(p,context.contactSpinAt(contactTime+t),contactMass):p;};
 const contactMotion=solver.contactMotion(support.terminal,l,surface,settings,Number.isFinite(contactTime)?{footQ:previousContactPose.q[l.foot],toeQ:previousContactPose.q[hand?l.foot:l.toe]}:null,hand&&Number.isFinite(contactTime)?t=>loadingBody(t).points[l.hip]:null,hand?{parents,solve:solveSupport,support,bodyAt:t=>Number.isFinite(contactTime)?loadingBody(t):support.terminal.pose}:null);
 if(!(build.ms>0))contactMotion.startPush(0);
 const rollingAt=(t,root)=>contactMotion.sample(t+loadDuration,root||(hand&&Number.isFinite(contactTime)?airPose(t).root:null));
 // Loading keeps incoming momentum and gravity; its root path replaces clip height.
 function loadingPose(t){
  const p=loadingBody(t),local=R.localize(p.points,p.q,parents),motion=bounce.sample(t);
  local.p[0]=motion.p;if(!hand&&!authoredBuild)local.q[0]=support.terminal.pose.q[0];
  for(const i of authoredBuild?[]:hand?limbs.map(a=>a.hip):[pelvis,l.hip]){local.p[i]=launchLocal.p[i];if(i===pelvis)local.q[i]=launchLocal.q[i];}
  const contact=contactMotion.sample(t,motion.p);
  const posed=solveContacts(R.fk(local,parents),contact);
  return clearFreeHand(posed);
 }
 const paired=hand&&support.paired,driveReach=limbs.reduce((sum,a)=>sum+a.reach,0)/limbs.length;
 const driveContact=c=>paired?{...c,foot:mean(c.hands.map(h=>h.foot))}:c;
 const contactConstraints=paired?(root,t)=>{const p=loadingBody(t),delta=sub(root,p.points[0]),c=contactMotion.sample(t,root);return c.hands.map(h=>({hip:add(p.points[h.leg.hip],delta),foot:h.foot,maxReach:h.leg.reach*settings.supportReach,minLength:.45*h.leg.reach,valid:h.valid,normal:surface.normal,surfaceOrigin:surface.origin}));}:null;
 // A rotated airborne body can have its root anchor below the platform while
 // its physical body is clear. Only grounded locomotion may use the standing
 // capsule here; airborne loading resolves the posed body, as hand loading does.
 if(build.ms>0&&Number.isFinite(contactTime)){
  bounce=B.create({root:jumpRoot,hip:mean(limbs.map(a=>(hand?support.terminal.pose:contactBodyPose(0)).points[a.hip])),upperLength:hand?null:l.upper,lowerLength:hand?null:l.lower,foot:paired?mean(support.terminal.hands.map(h=>h.foot)):support.terminal.foot,normal:surface.normal,direction,incoming,reach:driveReach,maxReach:paired?driveReach*settings.supportReach:support.maxReach,loadMs:settings.loadMs,buildMs:footBuild?Math.max(0,build.ms-(contactTime-preparationStart)*1000):build.ms,authoredBuild,rebound:settings.rebound,launchSpeed,cap:settings.fallCap,rolling:(t,p)=>driveContact(rollingAt(t,p)),carry:carryVelocity,loading:(t,p)=>driveContact(contactMotion.sample(t,p)),constraints:contactConstraints,anchorOffset:hand||authoredBuild||context.contactSpinAt?t=>{const p=contactBodyPose(t,!hand&&loadCommitted?Math.min(t,loadDuration):t);return sub(mean(limbs.map(a=>p.points[a.hip])),p.points[0]);}:null,surfaceOrigin:hand?surface.origin:null,resolveRoot:hand&&context.surfaces||authoredBuild?(p,delta,t)=>{if(!hand&&grounded)return K.move(p,delta,context.surfaces||[surface]);const base=contactBodyPose(t),at=add(p,delta),posed={...base,points:base.points.map(v=>add(v,sub(at,base.points[0])))};return contactBody.resolve(solveContacts(posed,contactMotion.sample(t,at)),context.surfaces||[surface],hand?handShapes:['foot_'+l.side.toLowerCase(),'ball_'+l.side.toLowerCase()]);}:null,startPush:t=>{loadDuration=t;loadCommitted=true;depthStop=contactTime+t;if(hand&&authoredBuild)contactMotion.invalidate();contactMotion.startPush(t);}});
  if(hand)contactMotion.setRootAt(t=>bounce.sample(t).p);
  runEnd=localRoot(loadingPose(bounce.loadDuration));launchLocal=R.localize(runEnd.points,runEnd.q,parents);
  if(authoredBuild&&!hand){const p=rawWorldRun(contactTime+bounce.loadDuration);buildPelvisRest=R.localize(p.points,p.q,parents).p[pelvis];}
  jumpStart=contactTime+bounce.loadDuration;apex=bounce.apex-bounce.loadDuration;
 }
 release=bounce?bounce.releaseTime-bounce.loadDuration:Number.isFinite(jumpStart)?findRelease(rollingAt):0;
 if(hand&&!bounce&&Number.isFinite(contactTime))contactMotion.setRootAt(t=>airPose(t).root);
 const contactAt=t=>rollingAt(Math.min(t,release));
 const releaseContact=contactAt(release);
 const released=Number.isFinite(jumpStart)?solveContacts(airPose(release).pose,releaseContact):null;
 let matchTime=release,matchDistance=null,legRate=1;
 if(!hand&&settings.matchLeg&&(!bounce||bounce.didPush)&&released&&release<loopStart){
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
  if(hand){
   const departing=t=>{const age=release+t,c=contactAt(age);return localRoot(solveContacts(airPose(age).pose,c));};
   const target=t=>jumpAnimation(release+t);
   // Prepare both from the same displayed contact pose before assigning either.
   // The supporting arms have their own recovery clock. Leaving them in the
   // body blend makes them jump back to its unfinished pose when Limb ends
   // before Body. Unselected joints follow the target animation directly.
   const bodyBones=parents.map((_,i)=>i).filter(i=>!supportBones.includes(i));
   const body=C.transition(departing,target,settings.jumpBlend,parents,bodyBones,false,true);
   legEntry=C.transition(departing,target,limbBlend,parents,supportBones,false,true);bodyEntry=body;
  }else{
  const beforePush=t=>localRoot(t===0?runEnd:bounce&&bounce.loadDuration>0?loadingPose(bounce.loadDuration+t):support.sample(Math.max(0,support.jumpDelay+t)).pose);
  const bodyTarget=t=>bounce&&!bounce.didPush?localRoot(at(loop,t,parents,true)):jumpAnimation(t);
  bodyEntry=C.transition(beforePush,bodyTarget,settings.jumpBlend,parents);
  const legTarget=t=>{const p=jumpAnimation(release+t),local=R.localize(p.points,p.q,parents);local.p[l.hip]=launchLocal.p[l.hip];return R.fk(local,parents);};
  legEntry=C.transition(t=>{const age=release+t,c=contactAt(age);return solveSupport(airPose(age).pose,l,c.foot,parents,settings.supportReach,c.rotation);},legTarget,settings.legBlend,parents,supportBones);
  }
 }
 const abortTime=supportStart+support.abortDelay;
 // A failed plant never borrows jump height. Keep momentum, release IK, then fall off the ledge.
 const edgeTime=edge/speed,fallStart=Math.max(abortTime,edgeTime),fallRoot=Number.isFinite(fallStart)?worldRun(fallStart).points[0]:null;
 // Capture the displayed pelvis at the edge, including an unfinished abort
 // blend. Fall animation may pose the limbs but cannot lift/drop the pelvis.
 const abortRecovery=Number.isFinite(abortTime)?C.transition(t=>localRoot(support.sample(Math.max(0,support.abortDelay+t)).pose),t=>localRoot(worldRun(abortTime+t)),settings.jumpBlend,parents):null;
 const abortLeg=Number.isFinite(abortTime)&&context.continueAt?C.transition(t=>support.sample(Math.max(0,support.abortDelay+t)).pose,t=>context.continueAt(abortTime+t).pose,limbBlend,parents,supportBones):null;
 const abortBody=footBuild&&Number.isFinite(abortTime)&&context.continueAt?C.transition(t=>support.sample(Math.max(0,support.abortDelay+t)).pose,t=>context.continueAt(abortTime+t).pose,settings.jumpBlend,parents):null;
 const fallPose=Number.isFinite(fallStart)?abortRecovery(fallStart-abortTime):null;
 const fallLocal=fallPose?R.localize(fallPose.points,fallPose.q,parents):null;
 const abortFall=fallPose?C.transition(t=>abortRecovery(Math.max(0,fallStart-abortTime+t)),t=>localRoot(at(loop,t,parents,true)),settings.jumpBlend,parents):null;
 function aborted(time){
  if(context.continueAt){const frame=context.continueAt(time);let pose=abortLeg(time-abortTime);
   if(abortBody){const body=abortBody(time-abortTime),local=R.localize(body.points,body.q,parents),leg=R.localize(pose.points,pose.q,parents);for(const i of supportBones){local.p[i]=leg.p[i];local.q[i]=leg.q[i];}pose=R.fk(local,parents);}
   return {...frame,pose,phase:'MISS Â· '+frame.phase,supportState:'FAILED',failureReason:support.failureReason,distance:support.terminal.distance};}
  const elapsed=time-abortTime,fallTime=Math.max(0,time-fallStart),fall=cappedFall(fallTime,settings.fallCap);
  let pose=time>=fallStart?abortFall(fallTime):abortRecovery(elapsed);
  if(time>=fallStart){const local=R.localize(pose.points,pose.q,parents);for(const i of [0,pelvis]){local.p[i]=fallLocal.p[i];local.q[i]=fallLocal.q[i];}pose=R.fk(local,parents);}
  const root=worldRun(time).points[0].slice();if(time>=fallStart)root[1]=fallRoot[1]+fall.y;
  return {pose:translate(pose,root),root,phase:time>=fallStart?'ABORT - FALL':settings.mode==='walk'?'ABORT - WALK':'ABORT - RUN',supportState:'FAILED',failureReason:support.failureReason,distance:support.terminal.distance,speed,vy:fall.v,airTime:0};
 }
 function sample(time,flip=0,twist=0,axis=settings.axis){
  if(time<supportStart){const pose=worldRun(time);return {pose,root:pose.points[0],phase:settings.mode==='idle'?'IDLE':settings.mode==='walk'?'WALK':'RUN',speed,vy:0,airTime:0};}
  if(time>=abortTime){const frame=aborted(time);return hand?{...frame,pose:limitHands(frame.pose)}:frame;}
  if(bounce&&time>=contactTime&&time<jumpStart){const motion=bounce.sample(time-contactTime);return {pose:loadingPose(time-contactTime),root:motion.p,phase:'LOAD',supportState:'PIN',contactAge:time-contactTime,supportTarget:contactMotion.sample(time-contactTime).contact,speed,vy:motion.v[1],airTime:0};}
  if(time<jumpStart){const frame=support.sample(time-supportStart);return {...frame,root:frame.pose.points[0],phase:'SUPPORT',supportState:'APPROACH',supportAge:time-supportStart,supportTarget:frame.surface,speed,vy:0,airTime:0};}
  const t=time-jumpStart,frame=airPose(t);let pose=frame.pose;
  const airTime=Math.max(0,t-release);
  if(airTime>0&&!hand){const q=C.orientation(flip,twist,axis,pose.q[1]);pose=C.centerPose(pose,q,pose.points[1]);pose.points[0]=frame.root;}
  let supportState='FREE';
  if(t<=release){const c=contactAt(t);pose=solveContacts(pose,c);supportState='PIN';}
  else {
   if(matchDistance!==null&&t<loopStart)supportState='MATCH';
   if(t<release+limbBlend){
   const carried=legEntry(t-release),source=R.localize(carried.points,carried.q,parents),local=R.localize(pose.points,pose.q,parents);
   for(const i of supportBones){local.q[i]=source.q[i];if(!limbs.some(a=>a.hip===i))local.p[i]=source.p[i];}
   pose=R.fk(local,parents);supportState='BLEND';
   }
  }
  // A zero-angle hand release keeps its stable carrier frame. Apply a legacy
  // air flip only when requested, preserving root/body transform separation.
  if(airTime>0&&hand&&(flip||twist)){const rootQ=pose.q[0],q=C.orientation(flip,twist,axis,pose.q[1]),delta=qm(q,qinv(pose.q[1]));pose=C.centerPose(pose,q,pose.points[1]);pose.points[0]=frame.root;pose.q[0]=qm(delta,rootQ);pose.axes[0]=R.toAxes(pose.q[0]);}
  if(hand)pose=limitHands(clearFreeHand(pose));
  return {...frame,pose,phase:bounce&&!bounce.didPush?'MISS Â· FALL':t<release?'PUSH':t<apex?'RISE':t<loopStart?'FALL':'FALL LOOP',failureReason:hand&&bounce&&!bounce.didPush?'No push travel: '+bounce.limitReason:null,supportState,contactAge:time-contactTime,supportTarget:contactAt(t).contact,speed,airTime};
 }
 // Diagnostic only: raw animation leg, carried by the displayed procedural pelvis.
 // No locomotion crossfade, support IK or release blend enters this target.
 function animationLeg(time,displayed,unretimed=false,other=false){
  if(hand)return null;
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
  const targets=support.idealTargets(worldRun(supportStart+t));
  return {surface,kind:hand?'hand':'foot',targets:hand?targets.map((target,i)=>{const plan=support.hands?.find(h=>h.leg.side===target.foot)?.plan||(target.selected?support:null),at=plan?(plan.frames.filter(f=>f.t<=t+1e-9).at(-1)||plan.frames[0]):null;return {...target,selected:paired||target.selected,contact:at?.surface||support.scores[i].constrainedSurface,cone:at?.cone||support.scores[i].cone};}):targets};
 }
 // Playback-time diagnostic: no timer, so pause/seek/loop show the same three frames.
 function pushDebug(time){
  const age=(time-jumpStart)*60;
  if(bounce&&!bounce.didPush||!Number.isFinite(jumpStart)||jumpStart>=abortTime||age<-1e-7||age>=3-1e-7)return null;
  const contact=contactAt(0);return {origin:paired?mean(contact.hands.map(h=>h.contact)):contact.contact,direction};
 }
 const inertia=hand?N.create(sample,{release:jumpStart+release,cap:settings.fallCap,names:run.names,parents,reference}):null;
 if(inertia?.diagnostics.enabled)apex=release+Math.max(0,inertia.diagnostics.velocity[1])/9.81;
 return {sample:inertia?inertia.sample:sample,authoredSample:sample,inertia,solveSupport,solveContacts,animationLeg,coneDebug,idealDebug,pushDebug,contactTime,contactMotion,bounce,launchSpeed,build,preparationStart,preparationDepth,surface,surfaces:context.surfaces||[surface],direction,carriedVelocity:tangent,incomingVelocity:incoming,landingPitch,animationTime,legTime,matchTime,matchDistance,legRate,edge,speed,takeoffSpeed,standingThreshold,jumpStyle,lift:release,apex,start:start.name,sourceStart:start.sourceStart,supportFoot:paired?'Both':l.side,supportKind:hand?'hand':'foot',supportBone:l.foot,supportScores:support.scores,loopStart,sourceLoopStart,runSeconds:settings.runSeconds,supportStart,jumpStart,abortTime,failureReason:support.failureReason,airStart:jumpStart+release,support,release};
}
function fallFrom(t,v,cap){v=Math.max(-cap,v);const tc=Math.max(0,(v+cap)/9.81),a=Math.min(t,tc);return {y:v*a-.5*9.81*a*a-cap*Math.max(0,t-tc),v:Math.max(-cap,v-9.81*t)};}
function eventsFor(settings){return settings.jumpEvents??[{id:'first',time:Math.round((settings.runSeconds-settings.jumpEarly)*60)/60,surface:'floor'}];}
function handFrames(source,segment,settings){
 // Planning, capsule integration, playback and debug all ask for the same
 // 240 Hz poses. Share the solved result, including the COM/contact iteration.
 // Only merge floating-point drift at a tick; real subframe queries stay exact.
 const prepared=new Map(),recent=new Map(),variants=new Map();
 const end=Math.min(segment.airStart,segment.abortTime)+Math.max(settings.jumpBlend,segment.supportKind==='hand'?settings.handReturn+settings.handFollow:settings.legBlend+settings.legFollow);
 return (time,flip,twist,axis)=>{
  const tick=Math.round(time*240),fixed=Math.abs(time-tick/240)<1e-10,t=fixed?tick/240:time,air=Math.max(0,t-segment.airStart);
  const defaultFlip=settings.airFlip?settings.flipAngle+settings.flipSpeed*air:0,defaultTwist=settings.airFlip?settings.twistAngle+settings.twistSpeed*air:0;
  const normal=(flip===undefined||Math.abs(flip-defaultFlip)<1e-8)&&(twist===undefined||Math.abs(twist-defaultTwist)<1e-8)&&(axis===undefined||axis===settings.axis);
  const keep=normal&&fixed&&t>=segment.supportStart&&t<=end&&(prepared.has(t)||prepared.size<2400);
  const cache=keep?prepared:normal?recent:variants;
  const key=normal?t:[t,flip??defaultFlip,twist??defaultTwist,axis??settings.axis].join(':');
  if(cache.has(key))return cache.get(key);
  const frame=normal?source(t,defaultFlip,defaultTwist,settings.axis):source(t,flip,twist,axis);
  cache.set(key,frame);
  // Keep the expensive support/blend interval across loops. Long free falls
  // and arbitrary scrub/rotation requests have bounded caches instead.
  if(cache!==prepared&&cache.size>256)cache.delete(cache.keys().next().value);
  return frame;
 };
}
function sequence(run,jumps,input,parents,reference=run.poses[0],resume=null,catalog=null,options={}){
 H.registerRig(reference);
 C.registerRig(run.names,parents,reference);H.registerRig(reference);
 const settings=C.sanitize(input),schedule=eventsFor(settings);let horizon=options.horizon??Math.max(12,settings.trimOut,...schedule.map(e=>e.time+5));
 const startTurn=R.qexp([0,settings.startYaw*Math.PI/180,0]);
 const turnPose=p=>settings.startYaw?finish(p.points.map(v=>add(p.points[0],rotate(startTurn,sub(v,p.points[0])))),p.q.map(q=>qm(startTurn,q))):p;
 // Rotate motion sources, not the environment or rig's rest frames.
 if(settings.startYaw)jumps=jumps.map(c=>({...c,poses:c.poses.map(turnPose),locals:undefined,takeoff:undefined}));
 if(settings.mode==='spaceGym'){const originalRun=run;run={...run,sample:t=>turnPose(originalRun.sample?originalRun.sample(t):originalRun.poses[0])};}
 if(settings.mode==='spaceGym')return {...G.sequence(run,jumps,settings,parents,schedule.filter(e=>e.time<=horizon),catalog,reference),preparedThrough:horizon};
 const origin=run.poses[0].points[0],speed=(run.poses.at(-1).points[0][2]-origin[2])/((run.poses.length-1)/run.fps),edge=settings.mode==='idle'?5:speed*settings.runSeconds-.12;
 const surfaces=S.scene(edge,settings),events=[],segments=[],loop=jumps.find(c=>c.name.endsWith('_Loop_Fall'));
 const gait=t=>{const p=run.sample?run.sample(t):translate(at(run,t,parents),[-origin[0],0,-origin[2]+Math.max(0,t-run.duration)*speed]);return run.facingSeeded?p:turnPose(p);};
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
 const body=P.create(run.names,parents,reference),massRig=D.model(run.names,parents,reference);
 const headingAt=pose=>{
  const turn=qm(pose.q[pelvis],qinv(reference.q[pelvis])),forward=rotate(turn,[0,0,1]);
  // A vertical forward vector has no yaw; recover it from the pelvis side axis.
  const side=rotate(turn,[1,0,0]),yaw=Math.hypot(forward[0],forward[2])>1e-6?Math.atan2(forward[0],forward[2]):Math.atan2(-side[2],side[0]);
  return R.qexp([0,yaw,0]);
 };
 const carrierOptions={surfaces,speed,parents,headingAt,initialYaw:settings.startYaw*Math.PI/180,landingBlend:settings.jumpBlend,gait,fallPose,cap:settings.fallCap,phase,resume,horizon,decorate:settings.surfaceIK&&IK.available&&surfaces.some(s=>s.normal[1]>1e-5&&s.normal[1]<.99999)?(source,options)=>IK.track(source,{...options,names:run.names,parents,gait:settings.mode==='jump'?'run':'walk'}):null};
 // A single final balance sees attack articulation, aiming and released-limb follow.
 function physicalTrack(segment,source,start,seedSource=source){
  const pushed=segment.launchSpeed>0&&Number.isFinite(segment.jumpStart)&&start<segment.abortTime&&(segment.bounce?segment.bounce.didPush&&start>segment.jumpStart+1e-9:start>=segment.jumpStart-1e-9);
  // Contact decides whether a push happened. Once it did, strength is a
  // gameplay command on COM velocity, not a side effect of the departing pose.
  // Rebound remains the explicit, separately tunable returned impact energy.
  const speed=Math.sqrt((segment.launchSpeed||0)**2+2*(segment.bounce?.returnedEnergy||0));
  const releaseVelocity=pushed?(measured)=>{
   const bias=segment.carrier.state(start-1e-7).bias,world=add(measured,bias);
   return sub(add(carryVelocity(world,segment.surface.normal,segment.direction),mul(segment.direction,speed)),bias);
  }:null;
  const config={start,settings,names:run.names,parents,reference,gravity:9.81,cap:settings.fallCap,seedSource,releaseVelocity,balance:segment.spin.active};
  let track=null;
  return {sample(time){
   if(!pushed&&!segment.spin.active||!Number.isFinite(start)||time<=start)return source(time);
   track ||= segment.spin.active&&settings.aim&&segment.attack?PhysicalAim.create(source,config,{track:segment.attack,clip:catalog.get(segment.event.attack),settings}):Physical.create(source,config);
   const frame=track.sample(time);return {...frame,physicalAim:segment.spin.active};
  },get track(){return track;}};
 }
 const baselineSpin=settings.airFlip&&Number.isFinite(edgeTime)?O.create(baseline,{start:edgeTime,commandTime:edgeTime,event:{spinVersion:2},settings,names:run.names,parents,reference}):null;
 const baselineCarrier=K.track(baselineSpin?baselineSpin.sample:baseline,{...carrierOptions,body,rootMotion:run.nativeEntry?t=>gait(t).points[0]:null});
 let previous=t=>baselineCarrier.sample(t),eventIndex=0,preparedThrough=0;
 function prepareThrough(end){
 horizon=Math.max(horizon,end);carrierOptions.horizon=horizon;baselineCarrier.setHorizon(horizon);
 for(const segment of segments)segment.carrier.setHorizon?.(horizon);
 const preparationLead=e=>{const j=C.sanitizeJump(e);return j.pushWith==='foot'&&j.jumpPercent>0&&settings.buildDepth>0?Math.max(0,C.jumpBuild(settings,j.jumpPercent).ms-settings.loadMs)/1000:0;};
 for(;eventIndex<schedule.length&&schedule[eventIndex].time-preparationLead(schedule[eventIndex])<=end+1e-8;eventIndex++){
  const event=schedule[eventIndex];
  const prior=previous,frame=prior(event.time),last=segments.at(-1);
  if(last&&event.time<Math.min(last.spinReleaseTime??last.jumpStart+last.release,last.abortTime)-1e-8){events.push({...event,status:'Busy',reason:'Previous support / push still active'});continue;}
  const p=frame.pose,spinSeed=frame.spin||null,spinOrigin=spinSeed?.rotation||[0,0,0,1],unspun=t=>O.rebase(prior(t),spinOrigin,massRig);
  if(C.sanitizeJump(event).jumpPercent===0){
   const segment=G.action(event,unspun);segment.motion=M.create(event,segment,jumps,run.names,parents,settings);if(segment.motion)segment.sample=segment.motion.sample;segment.attack=A.create(event,segment,catalog,run.names,parents,settings,reference);if(segment.attack)segment.sample=segment.attack.sample;segment.spin=O.create(segment.sample,{start:event.time,commandTime:event.time,event,settings,names:run.names,parents,reference,inherited:spinSeed});segment.physical=physicalTrack(segment,segment.spin.sample,event.time,prior);segment.sample=segment.physical.sample;segment.rawSample=segment.sample;segment.carrier=K.track(segment.sample,{...carrierOptions,start:event.time,initialYaw:frame.capsule?.yaw??carrierOptions.initialYaw,body,exactSource:true,forceSource:true,bodyDuringSupport:true,supportAirborne:!frame.capsule?.grounded});segments.push(segment);previous=t=>t<(segment.preparationStart??event.time)?prior(t):segment.carrier.sample(t);events.push({...event,status:'Action',reason:'0% push',pushTime:event.time});continue;
  }
  const priorRoot=t=>C.sanitizeJump(event).pushWith!=='foot'&&t>event.time?(last?last.carrier:baselineCarrier).state(t).root:prior(t).root;
  const velocityAt=t=>mul(sub(priorRoot(t+1/240),priorRoot(Math.max(event.time,t-1/240))),1/(t+1/240-Math.max(event.time,t-1/240)));
  const velocity=velocityAt(event.time);
  const ranked=surfaces.map(surface=>{
   const gap=R.length(sub(surface.closest(p.points[pelvis]),p.points[pelvis]));
   const hand=C.sanitizeJump(event).pushWith,handSettings={...settings,handSide:hand==='handL'?'L':hand==='handR'?'R':hand==='handBoth'?'Both':'Auto'};
   const choices=hand==='foot'?S.candidates(p,run.names,settings,surface,velocity):H.candidates(p,run.names,handSettings,surface,velocity,parents),choice=choices.scores[choices.selected];
   return {surface,gap,available:choice.eligible,contactGap:choice.cone.gap,foot:choice.foot,choices};
  }).sort((a,b)=>Number(b.available)-Number(a.available)||(a.available?a.contactGap-b.contactGap:0)||a.gap-b.gap);
  const surface=event.surface==='auto'?ranked[0]?.surface:surfaces.find(s=>s.id===event.surface);
  if(!surface){events.push({...event,status:'Miss',reason:'Surface disabled'});continue;}
  const segment=create(run,jumps,settings,parents,reference,{time:event.time,anticipate:true,notBefore:Math.max(last?Math.min(last.spinReleaseTime??last.airStart,last.abortTime):0,frame.capsule?.landingTime??0),grounded:frame.capsule?.grounded,hand:C.sanitizeJump(event).pushWith,handChoice:ranked.find(r=>r.surface===surface)?.choices,jumpScale:C.sanitizeJump(event).jumpPercent/100,surface,surfaces,poseAt:t=>unspun(t).pose,continueAt:unspun,contactSpinAt:!frame.capsule?.grounded&&C.sanitizeJump(event).pushWith==='foot'&&last?t=>qm(last.spin.state(t).rotation,qinv(spinOrigin)):null,articulationAt:last&&!last.carrier.state(event.time).landed?t=>O.rebase((last.rawSample||last.sample)(t),spinOrigin,massRig).pose:null,rootAt:t=>{const f=t<=event.time?prior(t):null;return f?f.root:(last?last.carrier.state(t).root:baselineCarrier.state(t).root);},velocityAt,speed:Math.hypot(velocity[0],velocity[2])});
  segment.surfaceChoices=ranked.map(r=>({surface:r.surface.id,foot:r.foot,eligible:r.available,contactGap:r.contactGap,pelvisGap:r.gap}));
  segment.event=event;
  // Compose all articulation first; one COM correction then drives the capsule.
  segment.sample=segment.authoredSample;
  segment.motion=M.create(event,segment,jumps,run.names,parents,settings);
  if(segment.motion)segment.sample=segment.motion.sample;
  segment.attack=A.create(event,segment,catalog,run.names,parents,settings,reference);if(segment.attack)segment.sample=segment.attack.sample;
  const unturned=segment.sample;segment.unturned=unturned;
  const spinContact=SC.create(segment,settings,run.names,parents,reference),pin=spinContact.apply;segment.spinContact=spinContact;
  segment.spin=O.create(t=>unturned(t,0,0,settings.axis),{start:event.time,commandTime:segment.airStart,event,settings,names:run.names,parents,reference,inherited:spinSeed,contact:pin});
  segment.spinReleaseTime=spinContact.releaseTime;
  const earlyRelease=segment.spinReleaseTime<segment.airStart-1e-7;
  const authored=t=>{const f=segment.spin.sample(t);return earlyRelease&&t>=segment.spinReleaseTime?{...f,phase:'FALL',supportState:'FREE',airTime:t-segment.spinReleaseTime,spinRelease:true}:f;};
  if(earlyRelease){const originalPushDebug=segment.pushDebug;segment.pushDebug=t=>t>=segment.spinReleaseTime?null:originalPushDebug(t);}
  if(segment.supportKind==='hand')segment.inertia=N.create(authored,{release:spinContact.releaseTime,cap:settings.fallCap,names:run.names,parents,reference});
  const source=segment.inertia?segment.inertia.sample:authored;
  const raw=handFrames(source,segment,{...settings,airFlip:false});
  segment.rawSample=raw;
  // Complete the contact side of release before solving a free-flight tick.
  // The departure pose can then use its real collision result without borrowing
  // a future offset or estimating the past from another frame.
  // A spinning two-hand push can release either hand first. Complete each
  // departing contact before its recovery samples the displayed history.
  const departureTimes=spinContact.releases.map(release=>release.time-1e-7);
  const departureTime=Math.max(...departureTimes);
  const displayedRelease=(t,project)=>{const f=segment.carrier.sample(Math.min(t,departureTime));return project?{...f,pose:project(f.pose)}:f;};
  // Contact history is displayed in resolved carrier coordinates. The new
  // free-flight source must retain its articulation in source coordinates:
  // the carrier will add its accumulated displacement/velocity exactly once.
  // Any surface projection must run in displayed world coordinates first.
  const sourceRelease=(t,project)=>{const f=displayedRelease(t,project),original=raw(t),delta=sub(original.root,f.root);return {...f,root:original.root,pose:{...f.pose,points:f.pose.points.map(p=>add(p,delta))}};};
  const finalArticulation=t=>{const f=raw(t);return t>=segment.spinReleaseTime?{...f,pose:pin(f.pose,t,f,null,sourceRelease)}:f;};
  segment.physical=physicalTrack(segment,finalArticulation,segment.spinReleaseTime,sourceRelease);
  segment.rawSample=segment.physical.sample;
  segment.carrier=K.track(segment.physical.sample,{...carrierOptions,initialYaw:prior(segment.preparationStart).capsule?.yaw??carrierOptions.initialYaw,breakTimes:departureTimes,start:segment.preparationStart,forceSource:true,body,bodyDuringSupport:segment.supportKind==='hand'||!frame.capsule?.grounded,supportAirborne:!frame.capsule?.grounded,excludeBody:frame=>frame.spin?.active?spinContact.activeBones(frame.spin.time):['APPROACH','PIN'].includes(frame.supportState)?(segment.support.limbs||[segment.support.leg]).flatMap(l=>segment.supportKind==='hand'?['hand_'+l.side.toLowerCase()]:['foot_'+l.side.toLowerCase(),'ball_'+l.side.toLowerCase()]):[],exactSource:true,cacheResolvedPose:true,correctPose:(pose,frame)=>{if(frame.physical)return pose;if(frame.returnedToLocomotion&&segment.supportKind==='hand')return pin(pose,frame.time,frame,null,displayedRelease,pose);if(frame.spin?.active||(segment.supportKind==='hand'?settings.handFollow:settings.legFollow)>0&&frame.spin?.time>=segment.spinReleaseTime)return pin(pose,frame.spin.time,frame,null,displayedRelease);const l=segment.support.leg;if(segment.support.paired&&frame.supportState==='APPROACH'&&frame.hands?.some(h=>h.pinned))return segment.support.sample(frame.supportAge,pose.points[0]).pose;if(frame.supportState!=='PIN')return pose;const c=segment.supportKind==='hand'?segment.contactMotion.sample(frame.contactAge,pose.points[0]):{foot:frame.pose.points[l.foot],rotation:{footQ:frame.pose.q[l.foot],toeQ:frame.pose.q[l.toe]}};return segment.supportKind==='hand'?segment.solveContacts(pose,c):segment.solveSupport(pose,l,c.foot,parents,settings.supportReach,c.rotation);}});
  events.push({...event,surfaceId:surface.id,supportKind:segment.supportKind,supportSide:segment.supportFoot,status:earlyRelease&&segment.spinReleaseTime<=segment.jumpStart?'Miss':Number.isFinite(segment.jumpStart)&&(!segment.bounce||segment.bounce.didPush)?'Push':'Miss',contactTime:segment.contactTime,pushTime:segment.jumpStart,releaseTime:segment.spinReleaseTime,handReleases:spinContact.releases,reason:earlyRelease&&segment.spinReleaseTime<=segment.jumpStart?'Spin released support before push':segment.bounce&&!segment.bounce.didPush?'No push travel: '+segment.bounce.limitReason:segment.failureReason});
  segments.push(segment);previous=t=>t<(segment.preparationStart??event.time)?prior(t):segment.carrier.sample(t);
 }
 for(let i=0;i<segments.length;i++){const s=segments[i],until=Math.min(end,segments[i+1]?.preparationStart??segments[i+1]?.supportStart??end);s.carrier.setHorizon?.(until);s.carrier.prepare(until);const landing=s.carrier.landings.find(l=>l.time<=until&&l.time<s.jumpStart);if(landing){const result=events.find(e=>e.id===s.event.id);if(result&&['Push','Miss'].includes(result.status)){result.status='Miss';result.reason='Body contact before push ('+(landing.bone||landing.surfaceId)+')';result.landingTime=landing.time;}}}
 baselineCarrier.setHorizon(Math.min(end,segments[0]?.preparationStart??segments[0]?.supportStart??end));baselineCarrier.prepare(Math.min(end,segments[0]?.preparationStart??segments[0]?.supportStart??end));
 preparedThrough=Math.max(preparedThrough,end);
 }
 const activeAt=t=>{for(let i=segments.length-1;i>=0;i--)if(t>=segments[i].supportStart)return segments[i];return segments[0]||null;};
 const sample=(t,flip=0,twist=0,axis=settings.axis)=>{
  let segment=null;for(let i=segments.length-1;i>=0;i--)if(t>=(segments[i].preparationStart??segments[i].supportStart)){segment=segments[i];break;}
  const frame=segment?segment.carrier.sample(t):baselineCarrier.sample(t);
  return {...frame,supportFoot:segment?.supportFoot,supportKind:segment?.supportKind,supportBone:segment?.supportBone,surface:segment?.surface};
 };
 if(!options.defer)prepareThrough(horizon);
 return {...(segments[0]||{}),edge,speed,surfaces,events,segments,activeAt,sample,prepareThrough,get preparedThrough(){return preparedThrough;},
  capsule:{radius:K.radius,halfHeight:K.halfHeight},get landings(){return [{carrier:baselineCarrier},...segments].flatMap((s,i)=>s.carrier.landings.filter(l=>l.time<(segments[i]?.supportStart??Infinity)).map(l=>({time:l.time,root:l.root,surfaceId:l.surfaceId})));},
  airStartAt:t=>{const s=activeAt(t);return s&&t>=s.supportStart&&!s.carrier.state(t).landed?s.airStart:Infinity;},
  pushDebug:t=>{for(let i=segments.length-1;i>=0;i--){const s=segments[i];if(s.carrier.state(t).landed)continue;const push=s.pushDebug(t);if(push)return push;}return null;},
  animationLeg:(t,p,unretimed=false,other=false)=>{const s=activeAt(t);return s&&!s.carrier.state(t).landed?s.animationLeg(t,p,unretimed,other):null;},coneDebug:(t,p)=>{const s=activeAt(t);return s&&!s.carrier.state(t).landed?s.coneDebug(t,p):null;},idealDebug:t=>{const s=activeAt(t);if(!s||s.carrier.state(t).landed)return null;const debug=s.idealDebug(t);if(debug?.kind==='hand'){const releases=s.spinContact.releases;return {...debug,targets:debug.targets.map(target=>({...target,selected:target.selected&&!releases.some(r=>r.side===target.foot&&t>=r.time)}))};}return debug;}};
}
const continuationCache=new Map();
async function prepare(run,jumps,input,parents,reference,generate,cancelled=()=>false,catalog=null){
 const settings=C.sanitize(input),preparedSeeds=new Map(),originalRun=run;
 let facingSample=null;
 function resume(data){
  const seeds=data.seeds.map(p=>({points:p.points,axes:p.axes}));
  const common={gait:settings.mode==='jump'?'run':'walk',drawn:settings.attack==='pike'||settings.attack.startsWith('slash'),names:run.names};
  const key=JSON.stringify({...common,seeds});
  let stored=preparedSeeds.get(key)||continuationCache.get(key);
  // A longer root path must preserve every command that informed the old NN
  // frames, including its future window. Otherwise it is a different rollout.
  if(stored&&!stored.roots.slice(0,Math.min(stored.roots.length,data.roots.length)).every((p,i)=>p.every((v,k)=>Math.abs(v-data.roots[i][k])<1e-9)))stored=null;
  if(stored&&stored.clip.poses.length>=data.frames){preparedSeeds.set(key,stored);return time=>at(stored.clip,Math.max(0,time-data.time),parents);}
  let request={...common,frames:data.frames,roots:data.roots,seeds},append=null;
  if(stored?.continuation){
   const count=stored.clip.poses.length;
   append=stored;
   request={...common,frames:data.frames-count+1,roots:data.roots.slice(count-1),seeds:stored.clip.poses.slice(-2).map(p=>({points:p.points,axes:p.axes})),continuation:stored.continuation};
   // Even a one-frame extension needs the policy's complete command window.
   while(request.roots.length<12)request.roots.push(data.roots.at(-1));
  }
  throw {landingRequest:request,key,append,roots:data.roots};
 }
 let sequenceResult=null,work=Promise.resolve();
 async function extendTo(end){
  if(sequenceResult&&end<=sequenceResult.preparedThrough+1e-8)return sequenceResult;
  const horizon=Math.max(1/60,end);
  for(;;){
   if(cancelled())return null;
   try{
    if(settings.startYaw&&['walk','jump'].includes(settings.mode)){
     const yaw=R.qexp([0,settings.startYaw*Math.PI/180,0]),inverse=qinv(yaw),origin=originalRun.poses[0].points[0],speed=(originalRun.poses.at(-1).points[0][2]-origin[2])/((originalRun.poses.length-1)/originalRun.fps);
     const rootAt=t=>[0,origin[1],speed*t],count=Math.max(2,Math.ceil(horizon*30)+1);
     const source=t=>{const p=t<0?C.blend(originalRun.poses[0],originalRun.poses[1],t*originalRun.fps,parents):at(originalRun,t,parents);return translate(p,sub(rootAt(t),p.points[0]));};
     const transform=(p,q)=>finish(p.points.map(v=>rotate(q,v)),p.q.map(v=>qm(q,v)));
     const seeds=[-1/30,0].map(t=>{const p=source(t),facing=finish(p.points.map(v=>add(p.points[0],rotate(yaw,sub(v,p.points[0])))),p.q.map(v=>qm(yaw,v)));return transform(facing,inverse);});
     const predicted=resume({time:0,frames:count,seeds,roots:Array.from({length:Math.max(12,count+9)},(_,i)=>rotate(inverse,rootAt((i-1)/30)))});
     facingSample=t=>{const pose=transform(predicted(Math.max(0,t)),yaw);return translate(pose,sub(rootAt(t),pose.points[0]));};
     if(!run.facingSeeded)run={...originalRun,facingSeeded:true,sample:t=>facingSample(t)};
    }
    if(!sequenceResult)sequenceResult=sequence(run,jumps,settings,parents,reference,resume,catalog,{horizon,defer:true});
    else if(settings.mode==='spaceGym')Object.assign(sequenceResult,sequence(run,jumps,settings,parents,reference,resume,catalog,{horizon,defer:true}));
    sequenceResult.prepareThrough?.(horizon);
    // Keep the legacy first-jump fields for diagnostics and offline callers.
    if(sequenceResult.segments[0])for(const [key,value] of Object.entries(sequenceResult.segments[0]))if(!(key in sequenceResult))sequenceResult[key]=value;
    sequenceResult.extend=end=>{work=work.catch(()=>{}).then(()=>extendTo(end));return work;};
    return sequenceResult;
   }catch(error){
    if(!error.landingRequest)throw error;
    const result=await generate(error.landingRequest);
    if(cancelled())return null;
    let clip=decodeNN(result);
    if(error.append){const old=error.append.clip;clip={...clip,poses:[...old.poses,...clip.poses.slice(1)],roots:[...old.roots,...clip.roots.slice(1)],duration:(old.poses.length+clip.poses.length-2)/clip.fps};}
    const stored={clip,roots:error.roots,continuation:result.continuation};
    preparedSeeds.set(error.key,stored);continuationCache.set(error.key,stored);
    while(continuationCache.size>8)continuationCache.delete(continuationCache.keys().next().value);
   }
  }
 }
 work=extendTo(settings.trimOut);return work;
}
const api={carryVelocity,jumpDirection,jumpHeight,decodeNN,decodeJump,at,create,sequence,prepare,eventsFor,cappedFall,localRoot,trimStart};if(typeof module!=='undefined')module.exports=api;else root.BodyflipFlight=api;
})(globalThis);
