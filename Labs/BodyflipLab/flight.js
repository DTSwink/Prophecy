(function(root){
'use strict';
const R=typeof module!=='undefined'?require('./recovery.js'):root.Recovery,C=typeof module!=='undefined'?require('./core.js'):root.BodyflipCore;
const S=typeof module!=='undefined'?require('./support.js'):root.BodyflipSupport;
const {add,sub,mul,rotate,qm,qinv,qslerp}=R,clamp=(x,a,b)=>Math.max(a,Math.min(b,x)),smooth=t=>t*t*(3-2*t);
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
function create(run,jumps,settings,parents,reference=run.poses[0]){
 settings=C.sanitize(settings);
 const supportStart=settings.runSeconds-settings.jumpEarly,runOrigin=run.poses[0].points[0],n=run.poses.length-1;
 const speed=(run.poses[n].points[0][2]-runOrigin[2])/(n/run.fps),runDistance=speed*settings.runSeconds,edge=runDistance-.12;
 const worldRun=time=>translate(at(run,time,parents),[-runOrigin[0],0,-runOrigin[2]+Math.max(0,time-run.duration)*speed]);
 const last=worldRun(supportStart);
 const support=S.plan(last,run.names,parents,settings,S.ground(edge),speed,t=>worldRun(supportStart+t));
 const selectionTime=supportStart+(Number.isFinite(support.jumpDelay)?support.jumpDelay:0),velocity=mul(sub(worldRun(selectionTime+1/120).points[0],worldRun(Math.max(0,selectionTime-1/120)).points[0]),60);
 const takeoffSpeed=Math.hypot(velocity[0],velocity[2]),standingThreshold=C.walkForwardSpeed*settings.standRatio,jumpStyle=takeoffSpeed<standingThreshold?'Stand':'Run';
 const candidates=jumps.filter(c=>c.name.includes('_Start_'+jumpStyle+'_')).map(trimStart),start=candidates.find(c=>c.supportFoot===support.leg.side),loop=jumps.find(c=>c.name.endsWith('_Loop_Fall'));
 if(!start)throw Error('Missing '+jumpStyle+' jump for '+support.leg.side+' foot');
 const heights=start.poses.map(p=>p.points[0][1]),apexIndex=heights.indexOf(Math.max(...heights)),apex=apexIndex/start.fps;
 const jumpStart=supportStart+support.jumpDelay,runEnd=localRoot(support.terminal.pose),jumpRoot=support.terminal.pose.points[0];
 const pelvis=run.names.indexOf('pelvis'),launchLocal=R.localize(runEnd.points,runEnd.q,parents),l=support.leg;
 const supportBones=[l.hip,l.knee,l.foot,l.toe];
 // Keep the pelvis on the launch-root trajectory. The animation owns the other
 // local joints; the planted leg is solved separately until its reach boundary.
 let release=Infinity;
 const loopStart=Math.max(apex+.35,start.duration-.25),loopBlend=.25;
 const heightAt=t=>{const f=clamp(t*start.fps,0,heights.length-1),i=Math.min(heights.length-2,Math.floor(f));return heights[i]+(heights[i+1]-heights[i])*(f-i);};
 function airPose(t){
  let pose=localRoot(at(start,t,parents));const animationPose=pose;
  if(t<settings.jumpBlend)pose=C.blend(runEnd,pose,smooth(clamp(t/Math.max(.001,settings.jumpBlend),0,1)),parents);
  if(t>=loopStart){const airborne=localRoot(at(loop,t-loopStart,parents,true));pose=C.blend(pose,airborne,smooth(clamp((t-loopStart)/loopBlend,0,1)),parents);}
  const local=R.localize(pose.points,pose.q,parents);
  for(const i of [0,pelvis]){local.p[i]=launchLocal.p[i];local.q[i]=launchLocal.q[i];}
  // The body blend must not leak into the independently timed support leg.
  if(t>release&&t<settings.jumpBlend){const source=R.localize(animationPose.points,animationPose.q,parents);for(const i of supportBones){local.p[i]=source.p[i];local.q[i]=source.q[i];}}
  if(t<=release)for(const i of supportBones){local.p[i]=launchLocal.p[i];local.q[i]=launchLocal.q[i];}
  // The support hip socket must not translate when the leg hands back to animation.
  local.p[l.hip]=launchLocal.p[l.hip];
  pose=R.fk(local,parents);
  let height,vy;
  if(t<=apex){height=heightAt(t)-heights[0];const h0=heightAt(Math.max(0,t-.002)),h1=heightAt(Math.min(apex,t+.002));vy=(h1-h0)/.004;}
  else {const f=cappedFall(t-apex,settings.fallCap);height=heights[apexIndex]-heights[0]+f.y;vy=f.v;}
  const rootPos=add(jumpRoot,[0,height,speed*t]);return {pose:translate(pose,rootPos),root:rootPos,vy};
 }
 // Plant at the reached ground contact, after both sole contact and the distance
 // gate pass. No final teleport or speed spike.
 const surface=S.ground(edge);
 // Find the first reach boundary once during preparation; seek/loop order cannot
 // alter planting or release. Inactive playback does no planning work.
 function findRelease(contactAt){
  const excess=t=>{const c=contactAt(t);return c.valid?R.length(sub(c.foot,airPose(t).pose.points[l.hip]))-support.maxReach:1;};
  let lastTime=0;
  for(let i=0;i<=480;i++){const t=i/240;if(excess(t)>=0||i===480){let lo=lastTime,hi=t;for(let j=0;j<18;j++){const mid=(lo+hi)*.5;if(excess(mid)>=0)hi=mid;else lo=mid;}return lo;}lastTime=t;}
 }
 const rollAngle=Math.max(0,settings.toeOffPitch-settings.plantPitch);
 const rollDuration=settings.footRollSpeed>0?rollAngle/settings.footRollSpeed:Infinity;
 const rolling=S.roll(support.terminal,l,surface,settings.toeOffPitch-settings.plantPitch);
 const rollingAt=t=>rolling(rollAngle>0&&settings.footRollSpeed>0?clamp(t/rollDuration,0,1):0);
 release=Number.isFinite(jumpStart)?findRelease(rollingAt):0;
 const contactAt=t=>rollingAt(Math.min(t,release));
 const releaseContact=contactAt(release);
 const released=Number.isFinite(jumpStart)?S.solve(airPose(release).pose,l,releaseContact.foot,parents,settings.supportReach,releaseContact.rotation):null;
 let matchTime=release,matchDistance=null,legRate=1;
 if(settings.matchLeg&&released&&release<loopStart){
  const wanted=rotate(qinv(released.q[pelvis]),sub(released.points[l.foot],released.points[pelvis]));
  let best=Infinity;
  // Compare ankle positions in the same pelvis frame and with the actual hip
  // socket. Search once on preparation, never per rendered frame.
  for(let i=0;i<=Math.ceil(loopStart*start.fps);i++){
   const time=Math.min(i/start.fps,loopStart),p=at(start,time,parents),local=R.localize(p.points,p.q,parents);
   const ankle=add(launchLocal.p[l.hip],add(rotate(local.q[l.hip],local.p[l.knee]),rotate(qm(local.q[l.hip],local.q[l.knee]),local.p[l.foot]))),distance=R.length(sub(ankle,wanted));
   if(distance<best-1e-9||(Math.abs(distance-best)<=1e-9&&Math.abs(time-release)<Math.abs(matchTime-release))){best=distance;matchTime=time;}
  }
  matchDistance=best;legRate=(loopStart-matchTime)/(loopStart-release);
 }
 const legTime=t=>settings.matchLeg&&t<loopStart?matchTime+Math.max(0,t-release)*legRate:t;
 const abortTime=supportStart+support.abortDelay;
 // A failed plant never borrows jump height. Keep momentum, release IK, then fall off the ledge.
 const edgeTime=edge/speed,fallStart=Math.max(abortTime,edgeTime),fallRoot=Number.isFinite(fallStart)?worldRun(fallStart).points[0]:null;
 function aborted(time){
  const elapsed=time-abortTime,fallTime=Math.max(0,time-fallStart),fall=cappedFall(fallTime,settings.fallCap);
  let pose=localRoot(worldRun(time));
  if(time>=fallStart)pose=C.blend(pose,localRoot(at(loop,fallTime,parents,true)),smooth(clamp(fallTime/Math.max(.001,settings.jumpBlend),0,1)),parents);
  pose=C.blend(runEnd,pose,smooth(clamp(elapsed/Math.max(.001,settings.jumpBlend),0,1)),parents);
  const root=worldRun(time).points[0].slice();if(time>=fallStart)root[1]=fallRoot[1]+fall.y;
  return {pose:translate(pose,root),root,phase:time>=fallStart?'ABORT - FALL':settings.mode==='walk'?'ABORT - WALK':'ABORT - RUN',supportState:'FAILED',failureReason:support.failureReason,distance:support.terminal.distance,speed,vy:fall.v,airTime:0};
 }
 function sample(time,flip=0,twist=0,axis=settings.axis){
  if(time<=supportStart){const pose=worldRun(time);return {pose,root:pose.points[0],phase:settings.mode==='walk'?'WALK':'RUN',speed,vy:0,airTime:0};}
  if(time>=abortTime)return aborted(time);
  if(time<jumpStart){const frame=support.sample(time-supportStart);return {...frame,root:frame.pose.points[0],phase:'SUPPORT',supportState:'APPROACH',supportTarget:frame.surface,speed,vy:0,airTime:0};}
  const t=time-jumpStart,frame=airPose(t);let pose=frame.pose;
  const airTime=Math.max(0,t-release);
  if(airTime>0){const q=C.orientation(flip,twist,axis,pose.q[1]);pose=C.centerPose(pose,q,pose.points[1]);pose.points[0]=frame.root;}
  let supportState='FREE';
  if(t<=release){const c=contactAt(t);pose=S.solve(pose,l,c.foot,parents,settings.supportReach,c.rotation);supportState='PIN';}
  else {
   if(settings.matchLeg&&t<loopStart){
    const target=at(start,legTime(t),parents),source=R.localize(target.points,target.q,parents),local=R.localize(pose.points,pose.q,parents);
    for(const i of supportBones){local.q[i]=source.q[i];if(i!==l.hip)local.p[i]=source.p[i];}
    pose=R.fk(local,parents);supportState='MATCH';
   }
   if(t<release+settings.legBlend){
   // Re-aim from the current hip, including any air rotation. A frozen release
   // pose would translate with the pelvis instead of continuing to reach back.
   const reaching=S.solve(pose,l,releaseContact.foot,parents,settings.supportReach,releaseContact.rotation),live=R.localize(reaching.points,reaching.q,parents);
   pose=S.blendLeg(pose,live,l,smooth((t-release)/Math.max(.001,settings.legBlend)),parents);supportState='BLEND';
   }
  }
  return {...frame,pose,phase:t<release?'PUSH':t<apex?'RISE':t<loopStart?'FALL':'FALL LOOP',supportState,supportTarget:contactAt(t).contact,speed,airTime};
 }
 // Diagnostic only: raw animation leg, carried by the displayed procedural pelvis.
 // No locomotion crossfade, support IK or release blend enters this target.
 function animationLeg(time,displayed){
  if(!displayed||!Number.isFinite(jumpStart)||time<jumpStart)return null;
  const t=time-jumpStart;let target=localRoot(at(start,legTime(t),parents));
  if(t>=loopStart)target=C.blend(target,localRoot(at(loop,t-loopStart,parents,true)),smooth(clamp((t-loopStart)/loopBlend,0,1)),parents);
  const source=R.localize(target.points,target.q,parents),local=R.localize(displayed.points,displayed.q,parents);
  for(const i of supportBones){local.q[i]=source.q[i];local.p[i]=source.p[i];}
  local.p[l.hip]=launchLocal.p[l.hip];
  const pose=R.fk(local,parents);
  return {foot:l.side,points:supportBones.map(i=>pose.points[i])};
 }
 return {sample,animationLeg,legTime,matchTime,matchDistance,legRate,edge,speed,takeoffSpeed,standingThreshold,jumpStyle,lift:release,apex,start:start.name,sourceStart:start.sourceStart,supportFoot:l.side,supportScores:support.scores,loopStart,runSeconds:settings.runSeconds,supportStart,jumpStart,abortTime,failureReason:support.failureReason,airStart:jumpStart+release,support,release};
}
const api={decodeNN,decodeJump,at,create,cappedFall,localRoot,trimStart};if(typeof module!=='undefined')module.exports=api;else root.BodyflipFlight=api;
})(globalThis);
