/* Full-body sampling and orientation. Recovery math is an independent D/S copy. */
(function(root){
'use strict';
const R=typeof module!=='undefined'?require('./recovery.js'):root.Recovery;
const {add,sub,mul,dot,cross,length,unit,qm,qinv,rotate,qexp,qslerp,fromTo,fk,localize}=R;
const rad=Math.PI/180,clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const dirs=['Back','B-R 30','B-R 60','Right','F-R 60','F-R 30','Front','F-L 30','F-L 60','Left','B-L 60','B-L 30'];
// supportSpeed is stored/displayed in cm/s; world positions and physics use metres.
// kickToArmed is the legacy saved key for the all-attack Direct to Armed mode.
const poseNames={pose1:'Lara',pose2:'Snatch',pose3:'Ball',pose4:'Ninja'},poseDefaults={blendIn:.2,blendDistance:1,responseTime:.15,responseSpeed:360,wobbleSpeed:1,wobbleAmplitude:.1};
const defaults={pikeSpineAbsorb:false,attackEndFrames:{},sweepKickEndFrame:35,poseEaseIn:.15,poseExponent:2,poseEaseOut:.5,poseBlendIn:.2,poseBlendDistance:1,poseResponseTime:.15,poseResponseSpeed:360,invertPoseVariants:false,poseEdit:'pose1',poseTuning:Object.fromEntries(Object.keys(poseNames).map(id=>[id,{wobbleSpeed:1,wobbleAmplitude:.1}])),spaceFallAnimation:false,attackReturnDuration:null,attackReturnDistance:0,attackReturnLerp:.1,attackReturnExponent:1,attackReturnSnap:.5,bigThrowReturnFrames:16,smallThrowReturnFrames:34,distributePelvisTurn:false,motionCompensation:true,vanillaOnly:false,momentum3D:true,startYaw:0,legFollow:.08,spinLag:.6,handReturn:.4,handCone:30,showHandCones:false,footTargets:true,handTargets:true,handFollow:.25,spinInertia:1,jumpBuildX:35,jumpBuildY:70,loadYMs:200,loadFullMs:300,buildDepth:.15,handBend:.35,undoRotation:true,kickToArmed:false,softAttackLegs:true,pelvisAttackCompensation:.5,surfaceIK:true,loadMs:100,rebound:.5,platformTranslucency:.8,platforms:null,jumpSkew:.5,ramps:true,jumpEvents:null,mode:'jump',motion:'kinematic',runSeconds:1,jumpEarly:.1,runPhase:0,jumpBlend:.2,legBlend:.2,fallCap:20,jumpFoot:'Auto',standRatio:.5,plantPitch:10,toeOffPitch:35,footRollSpeed:720,matchLeg:true,supportCone:30,supportReach:.99,supportTrigger:.05,supportAlpha:1,supportSpeed:800,airFlip:false,playbackSpeed:1,trimLoop:false,trimIn:0,trimOut:3,axis:0,flipSpeed:120,flipAngle:0,twistAngle:0,twistSpeed:0,attack:'slashLD',variant:1,aim:true,aimWeight:1,loop:false,attackRate:1,ghost:false,animLeg:false,animOtherLeg:false,rawLeg:false,showCone:false,showJump:false,bicolor:true,skeleton:false,target:[.4,1.55,.8],radius:.12};
// Blank per-jump speeds inherit the preceding command; explicit zero stops it.
// Version 1 totals migrate to their former mean speed, then continue rotating.
const jumpDefaults={enabled:true,instantSpin:false,spinVersion:2,pushWith:'foot',jumpPercent:100,attack:'none',throwCharge:100,throwSpeed:1,throwDirection:null,attackDelay:0,attackIn:.2,attackOut:.25,flip:null,twist:null,turnDelay:0,turnDuration:.8,turnIn:.4,turnOut:.4,turnAxis:null,pose:'none',poseIn:.2,poseHold:.3,poseOut:.25};
function sanitizeJump(e={}){
 const o={...jumpDefaults};o.enabled=e.enabled!==false;o.instantSpin=!!e.instantSpin;o.pushWith=['foot','hand','handL','handR','handBoth'].includes(e.pushWith)?e.pushWith:'foot';
 o.throwDirection=Array.isArray(e.throwDirection)&&e.throwDirection.length===3&&e.throwDirection.every(Number.isFinite)&&length(e.throwDirection)>1e-9?unit(e.throwDirection):null;
 for(const [key,min,max] of [['throwCharge',0,100],['throwSpeed',0,5],['jumpPercent',0,400],['attackDelay',0,30],['attackIn',1/60,3],['attackOut',1/60,3],['turnDelay',0,30],['turnDuration',1/60,30],['poseIn',1/60,5],['poseHold',0,30],['poseOut',1/60,5]])o[key]=clamp(Number.isFinite(e[key])?e[key]:jumpDefaults[key],min,max);
 for(const key of ['flip','twist'])o[key]=Number.isFinite(e[key])?(e.spinVersion===2?clamp(e[key],-3600,3600):e[key]===0?null:clamp(e[key]/o.turnDuration,-3600,3600)):null;
 // Preserve existing ramp settings while dropping the finite-angle deadline.
 for(const key of ['turnIn','turnOut'])o[key]=clamp(Number.isFinite(e[key])?e[key]:o.turnDuration/2,0,30);
 o.turnAxis=Number.isInteger(e.turnAxis)&&e.turnAxis>=0&&e.turnAxis<12?e.turnAxis:null;
 o.attack=['none','headbutt','hookL','hookR','jabL','jabR','KickL','KickR','overL','overR','pike','slashL','slashLD','slashLU','slashR','slashRD','slashRU','sweepKick','big-throw','small-throw'].includes(e.attack)?e.attack:'none';
 o.pose=['none','keep','pose1','pose2','pose3','pose4'].includes(e.pose)?e.pose:'none';
 return o;
}
function sanitize(s={}){const o={...defaults,...s,aimWeight:1};o.poseEdit=poseNames[o.poseEdit]?o.poseEdit:'pose1';for(const [key,lo,hi] of [['blendIn',1/60,5],['blendDistance',0,1],['responseTime',.05,1],['responseSpeed',1,3600]]){const id='pose'+key[0].toUpperCase()+key.slice(1),legacy=s.poseTuning?.[o.poseEdit]?.[key]??(key==='blendIn'?s.jumpEvents?.find(e=>e.pose===o.poseEdit)?.poseIn:undefined),value=s[id]??legacy;o[id]=clamp(value!=null&&Number.isFinite(+value)?+value:poseDefaults[key],lo,hi);}o.poseTuning=Object.fromEntries(Object.keys(poseNames).map(id=>[id,Object.fromEntries([['wobbleSpeed',0,4],['wobbleAmplitude',0,1]].map(([key,lo,hi])=>{const value=s.poseTuning?.[id]?.[key];return [key,clamp(value!=null&&Number.isFinite(+value)?+value:poseDefaults[key],lo,hi)];}))]));o.attackReturnDuration=s.attackReturnDuration!=null&&Number.isFinite(+s.attackReturnDuration)?clamp(+s.attackReturnDuration,1/60,3):null;if(s.handCone===undefined)o.handCone=s.supportCone??defaults.handCone;delete o.modifiedRotations;delete o.instantSpin;delete o.endLeg;delete o.jumpGap;if(s.legBlend===undefined)o.legBlend=s.jumpBlend??defaults.legBlend;for(const [k,a,b] of [['sweepKickEndFrame',17,35],['poseEaseIn',0,1],['poseExponent',1,3],['poseEaseOut',0,1],['attackReturnDistance',0,1],['attackReturnLerp',.01,1],['attackReturnExponent',0,1],['attackReturnSnap',.1,10],['bigThrowReturnFrames',0,96],['smallThrowReturnFrames',0,34],['startYaw',-180,180],['legFollow',0,1],['spinLag',0,1],['handReturn',0,1],['handCone',0,85],['handFollow',0,1],['spinInertia',0,1],['jumpBuildX',1,98],['jumpBuildY',2,99],['loadYMs',0,1500],['loadFullMs',0,1500],['buildDepth',0,.25],['handBend',.05,2],['pelvisAttackCompensation',0,1],['loadMs',0,300],['rebound',0,1],['platformTranslucency',0,1],['jumpSkew',0,1],['supportCone',0,85],['footRollSpeed',0,3600],['plantPitch',-25,35],['toeOffPitch',0,60],['standRatio',0,5],['jumpEarly',0,5],['playbackSpeed',.1,2],['supportReach',.5,1],['supportTrigger',0,.3],['supportAlpha',0,Infinity],['supportSpeed',.1,2000],['trimIn',0,599.98],['trimOut',1/60,600],['runSeconds',.1,5],['runPhase',0,1],['jumpBlend',0,1],['legBlend',0,1],['fallCap',2,50],['axis',0,11],['flipSpeed',-720,720],['flipAngle',-360,360],['twistAngle',-360,360],['twistSpeed',-720,720],['attackRate',.25,2],['radius',.04,.35]])o[k]=clamp(Number.isFinite(+o[k])?+o[k]:defaults[k],a,b);o.sweepKickEndFrame=Math.round(o.sweepKickEndFrame);o.attackEndFrames=Object.fromEntries(Object.entries(s.attackEndFrames||{}).filter(([k,v])=>/^[a-zA-Z0-9_-]{1,48}$/.test(k)&&v!=null&&v!==''&&Number.isFinite(+v)).slice(0,64).map(([k,v])=>[k,Math.round(clamp(+v,0,10000))]));if(o.attackEndFrames.sweepKick===undefined&&s.sweepKickEndFrame!=null)o.attackEndFrames.sweepKick=o.sweepKickEndFrame;o.bigThrowReturnFrames=Math.round(o.bigThrowReturnFrames);o.smallThrowReturnFrames=Math.round(o.smallThrowReturnFrames);o.jumpBuildX=Math.round(o.jumpBuildX);o.jumpBuildY=Math.max(o.jumpBuildX+1,Math.round(o.jumpBuildY));o.loadYMs=Math.max(o.loadMs,s.loadYMs===undefined?Math.min(1500,o.loadMs*2):o.loadYMs);o.loadFullMs=Math.max(o.loadYMs,s.loadFullMs===undefined?Math.min(1500,o.loadMs*3):o.loadFullMs);o.jumpEarly=Math.min(o.jumpEarly,Math.max(0,o.runSeconds-1/60));o.trimIn=Math.round(o.trimIn*60)/60;o.trimOut=Math.max(o.trimIn+1/60,Math.round(o.trimOut*60)/60);o.axis=Math.round(o.axis);o.target=Array.isArray(s.target)&&s.target.length===3&&s.target.every(Number.isFinite)?s.target.map(x=>clamp(x,-1000000,1000000)):[...defaults.target];for(const k of ['pikeSpineAbsorb','invertPoseVariants','spaceFallAnimation','distributePelvisTurn','motionCompensation','vanillaOnly','momentum3D','showHandCones','footTargets','handTargets','undoRotation','kickToArmed','softAttackLegs','surfaceIK','ramps','aim','loop','ghost','animLeg','animOtherLeg','rawLeg','showCone','showJump','bicolor','skeleton','airFlip','trimLoop','matchLeg'])o[k]=!!o[k];o.motion=o.motion==='kinematic'?'kinematic':'sim';if(o.mode==='space')o.mode='idle';o.mode=['idle','walk','jump','spaceGym'].includes(o.mode)?o.mode:'jump';o.jumpFoot=['Auto','L','R'].includes(o.jumpFoot)?o.jumpFoot:'Auto';if(s.instantSpin===true&&o.jumpEvents==null)o.jumpEvents=[{id:'first',time:Math.round((o.runSeconds-o.jumpEarly)*60)/60,surface:'floor'}];o.jumpEvents=Array.isArray(o.jumpEvents)?o.jumpEvents.slice(0,32).filter(e=>e&&Number.isFinite(+e.time)).map((e,i)=>({id:typeof e.id==='string'&&/^[a-zA-Z0-9_-]{1,48}$/.test(e.id)?e.id:'jump'+i,time:Math.round(clamp(+e.time,0,600)*60)/60,surface:['auto','floor','left','right'].includes(e.surface)?e.surface:'auto',...sanitizeJump({...e,instantSpin:e.instantSpin??s.instantSpin})})).sort((a,b)=>a.time-b.time):null;o.platforms=Array.isArray(o.platforms)?o.platforms.slice(0,128).filter(p=>p&&Array.isArray(p.position)&&p.position.length===3&&p.position.every(Number.isFinite)&&Array.isArray(p.size)&&p.size.length===3&&p.size.every(Number.isFinite)&&Array.isArray(p.rotation)&&p.rotation.length===4&&p.rotation.every(Number.isFinite)).map((p,i)=>{const n=Math.hypot(...p.rotation);return {id:typeof p.id==='string'&&/^[a-zA-Z0-9_-]{1,48}$/.test(p.id)?p.id:'platform'+i,position:p.position.map(v=>clamp(v,-1e6,1e6)),size:p.size.map(v=>clamp(v,.02,1000)),rotation:n>1e-9?p.rotation.map(v=>v/n):[0,0,0,1]};}):null;return o;}
function jumpBuild(settings,percent){const s=sanitize(settings),tier=percent<=s.jumpBuildX?'X':percent<=s.jumpBuildY?'Y':'100';return {tier,ms:tier==='X'?s.loadMs:tier==='Y'?s.loadYMs:s.loadFullMs,depth:s.buildDepth};}
function flipAxis(index){const a=index*Math.PI/6;return [-Math.cos(a),0,Math.sin(a)];}
function orientation(flip,twist,index,pelvis=null){const f=qexp(mul(flipAxis(index),flip*rad));return pelvis?qm(qm(f,pelvis),qexp([twist*rad,0,0])):qm(f,qexp([0,twist*rad,0]));}
function poseFromShared(m){const q=m.sharedIdle.axes.map(R.fromAxes),pose={points:m.sharedIdle.points.map(p=>p.slice()),q,axes:q.map(R.toAxes)};registerRig(m.names,m.parents,pose);return pose;}
function centerPose(p,rotation,pivot=[0,1.5,0]){const a=qm(rotation,qinv(p.q[1])),points=p.points.map(v=>add(pivot,rotate(a,sub(v,p.points[1])))),q=p.q.map(v=>qm(a,v));points[0]=pivot.slice();q[0]=rotation;return {points,q,axes:q.map(R.toAxes)};}
function decode(meta,buffer,names,parents){const f=new Float32Array(buffer),n=names.length,pn=meta.frames*n*3;if(f.length!==meta.frames*n*12)throw Error('Invalid attack data');const poses=[];for(let t=0;t<meta.frames;t++){const points=[],q=[];for(let j=0;j<n;j++){const i=t*n+j;points.push(Array.from(f.subarray(i*3,i*3+3)));q.push(R.fromAxes([0,1,2].map(k=>Array.from(f.subarray(pn+i*9+k*3,pn+i*9+k*3+3)))));}poses.push({points,q,axes:q.map(R.toAxes)});}registerRig(names,parents,poses[0]);return {meta,poses,duration:(meta.frames-1)/meta.fps};}
function blend(a,b,t,parents){const la=localize(a.points,a.q,parents),lb=localize(b.points,b.q,parents);return fk({p:la.p.map((p,j)=>add(p,mul(sub(lb.p[j],p),t))),q:la.q.map((q,j)=>qslerp(q,lb.q[j],t))},parents);}
// Carry outgoing local motion while a pose/velocity offset decays onto a moving
// target. Seed once; sampling is stateless and joins the target with zero offset
// and zero offset velocity. Root/contact constraints remain the caller's job.
const motionStep=1e-5;
const motionRigs=new WeakMap();
function registerRig(names,parents,reference){
 if(motionRigs.has(parents))return;
 const local=localize(reference.points,reference.q,parents),legs=[];
 for(const side of ['l','r'])for(const parts of [['thigh','calf','foot','ball'],['upperarm','lowerarm','hand']]){
  const chain=parts.map(n=>names.indexOf(n+'_'+side));if(chain.some(i=>i<0))continue;
  const [,knee,foot]=chain,u=unit(local.p[knee]),v=unit(rotate(local.q[knee],local.p[foot]));
  const normal=length(cross(u,v))>1e-5?unit(cross(u,v)):[0,0,-1];
  legs.push({chain,knee,foot,normal,arm:parts[0]==='upperarm'});
 }
 motionRigs.set(parents,legs);
}
function kneeBend(local,leg){const u=unit(local.p[leg.knee]),v=unit(rotate(local.q[leg.knee],local.p[leg.foot]));return Math.atan2(dot(leg.normal,cross(u,v)),dot(u,v));}
function transition(outgoing,incoming,duration,parents,indices=null,rotationOnly=false,includeArms=false,coupledHand=-1,protectedElbow=-1){
 if(!(duration>0))return incoming;
 const h=motionStep,a=outgoing(0),prev=outgoing(-h),b=incoming(0),next=incoming(h);
 const la=localize(a.points,a.q,parents),lp=localize(prev.points,prev.q,parents),lb=localize(b.points,b.q,parents),ln=localize(next.points,next.q,parents);
 const bones=indices||parents.map((_,i)=>i),protectedElbows=Array.isArray(protectedElbow)?protectedElbow:[protectedElbow];
 // Forearm/wrist counter-roll is an internal cancellation, not two separate
 // inertial spins. Remove only equal opposing axial rates from the return seed.
 // Keep net hand velocity, all swing rates, and the existing return envelope.
 if(coupledHand>=0)for(const arm of motionRigs.get(parents)||[]){
  if(!arm.arm||arm.foot!==coupledHand||!bones.includes(arm.knee)||!bones.includes(arm.foot))continue;
  const f=arm.knee,hand=arm.foot,axis=unit(sub(a.points[hand],a.points[f])),forearmRate=mul(R.qlog(qm(a.q[f],qinv(prev.q[f]))),1/h),handRate=mul(R.qlog(qm(a.q[hand],qinv(prev.q[hand]))),1/h);
  const parentRate=mul(R.qlog(qm(a.q[parents[f]],qinv(prev.q[parents[f]]))),1/h),roll=dot(sub(forearmRate,parentRate),axis),counter=dot(sub(handRate,forearmRate),axis);
  if(roll*counter>=0)continue;
  const cancelled=Math.sign(roll)*Math.min(Math.abs(roll),Math.abs(counter)),rate=sub(forearmRate,mul(axis,cancelled)),previous=qm(qexp(mul(rate,-h)),a.q[f]);
  lp.q[f]=qm(qinv(prev.q[parents[f]]),previous);lp.q[hand]=qm(qinv(previous),prev.q[hand]);
 }
 const seeds=bones.map(i=>{
  const velocity=mul(R.qlog(qm(la.q[i],qinv(lp.q[i]))),1/h),error=R.qlog(qm(la.q[i],qinv(lb.q[i])));
  let future=R.qlog(qm(qm(qexp(mul(velocity,h)),la.q[i]),qinv(ln.q[i])));
  // Keep the logarithm on the same branch when the offset crosses 180 degrees.
  if(length(sub(future,error))>Math.PI)future=sub(future,mul(unit(future),Math.PI*2));
  return {i,error,rate:mul(sub(future,error),1/h),offset:sub(la.p[i],lb.p[i]),speed:mul(sub(sub(la.p[i],lp.p[i]),sub(ln.p[i],lb.p[i])),1/h),length:length(la.p[i])-length(lb.p[i]),lengthRate:(length(la.p[i])-length(lp.p[i])-length(ln.p[i])+length(lb.p[i]))/h};
 });
 const momentumTimes=new Map(),hingeTimes=new Map();
 function blendedLocal(target,t,selected=seeds,prepared=null){
  const local=prepared?{p:prepared.p.slice(),q:prepared.q.slice()}:localize(target.points,target.q,parents),x=clamp(t/duration,0,1),position=1-3*x*x+2*x*x*x,velocity=duration*x*(1-x)*(1-x),armTransfers=[];
  for(const s of selected){const i=s.i,tau=momentumTimes.get(i),carried=tau===undefined?velocity:tau>0?tau*(-Math.expm1(-Math.max(0,t)/tau))*position:0;let motion=mul(s.rate,carried);
   const hinge=hingeTimes.get(i),unbounded=hinge?unit(qm(qexp(add(mul(s.error,position),motion)),local.q[i])):null;if(hinge){const bounded=hinge.tau>0?hinge.tau*(-Math.expm1(-Math.max(0,t)/hinge.tau))*position:0;motion=add(motion,mul(hinge.axis,dot(s.rate,hinge.axis)*(bounded-carried)));}
   local.q[i]=unit(qm(qexp(add(mul(s.error,position),motion)),local.q[i]));
   if(hinge&&selected.some(s=>s.i===parents[i]))armTransfers.push({parent:parents[i],turn:qm(unbounded,qinv(local.q[i]))});
   if(!rotationOnly){const original=local.p[i],p=add(original,add(mul(s.offset,position),mul(s.speed,carried)));
    // Preserve skeletal lengths; root translations are unconstrained.
    local.p[i]=parents[i]>=0&&length(p)>1e-9?mul(unit(p),Math.max(0,length(original)+s.length*position+s.lengthRate*carried)):p;
   }
  }
  // An elbow-only brake changes the orientation of everything below it.
  // Move that lost relative turn into the shoulder: upper * forearm remains
  // the original return, so the wrist stays local and the sword keeps its
  // original orientation/momentum while the elbow remains on its bending side.
  for(const transfer of armTransfers)local.q[transfer.parent]=unit(qm(local.q[transfer.parent],transfer.turn));
  return local;
 }
 // Plan braking before a knee reaches its hinge boundary. Shorten only the
 // carried velocity, not the pose blend or its deadline. The whole leg shares
 // that decay so the thigh/ankle cannot keep swinging against its knee. Integrate
 // an exponential braking curve; ease its remaining displacement out over the
 // full blend instead of immediately recoiling from the straight-leg boundary.
 const legs=(motionRigs.get(parents)||[]).filter(l=>bones.includes(l.knee)&&(!l.arm||includeArms||protectedElbows.includes(l.knee)));
 if(legs.length){
  const count=Math.max(48,Math.ceil(duration*480)),cache=new Map();
  const targetAt=t=>{let entry=cache.get(t);if(!entry){const pose=incoming(t);entry={t,local:localize(pose.points,pose.q,parents)};cache.set(t,entry);}return entry;};
  const targets=Array.from({length:count+1},(_,i)=>targetAt(duration*i/count));
  for(const leg of legs){
   // Either Pike arm may still be extending at the cut. Brake only its
   // hinge component, carrying the blocked turn through the shoulder instead
   // of redirecting the sword. Preserve forearm roll and local wrist inertia.
   // The exponential integral starts with the original velocity; no joint
   // clamp or pose snap is applied after sampling.
   const hingeOnly=protectedElbows.includes(leg.knee);
   const selected=seeds.filter(s=>s.i===leg.knee||s.i===leg.foot);
   const valid=sample=>{const angle=kneeBend(blendedLocal(null,sample.t,selected,sample.local),leg);return angle>=-1e-6&&angle<=(hingeOnly?155:150)*rad+1e-6;};
   if(targets.every(valid))continue;
   const fits=tau=>{if(hingeOnly)hingeTimes.set(leg.knee,{tau,axis:leg.normal});else for(const i of leg.chain)momentumTimes.set(i,tau);return targets.every(valid)&&Array.from({length:33},(_,i)=>valid(targetAt(Math.min(duration,4*tau)*i/32))).every(Boolean);};
   let lo=0,hi=duration;
   // Zero momentum leaves the ordinary moving-pose blend. Do not mask an
   // invalid source/target by clamping the rendered joint after sampling.
   if(fits(0)){for(let i=0;i<18;i++){const mid=(lo+hi)*.5;if(fits(mid))lo=mid;else hi=mid;}fits(lo*.8);}
   else if(hingeOnly)hingeTimes.delete(leg.knee);else for(const i of leg.chain)momentumTimes.delete(i);
  }
 }
 const apply=(target,t)=>t>=duration?target:fk(blendedLocal(target,t),parents);
 const sample=t=>apply(incoming(Math.max(0,t)),t);
 sample.apply=apply;return sample;
}
// Original duration-based body transition and shared smooth aim envelope.
// Lerp/snap/exponent controls remain serialized but do not drive the return.
function attackReturn(settings={},duration=jumpDefaults.attackOut){
 const horizon=clamp(Number.isFinite(settings.attackReturnDuration)?settings.attackReturnDuration:duration,1/60,6);
 const factor=time=>{const x=clamp(time/horizon,0,1);return 1-x*x*x*(10+x*(-15+6*x));};
 return {horizon,factor,transition:(outgoing,incoming,parents,indices=null,coupledHand=-1,protectedElbow=-1)=>transition(outgoing,incoming,horizon,parents,indices,true,false,coupledHand,protectedElbow)};
}
// Select one duration from the pose at return start; never chase a moving error.
function returnDuration(duration,angle,weight=0){return Math.max(1/60,duration*(1-clamp(weight,0,1)+clamp(weight,0,1)*angle/(Math.PI/2)));}
const attackTransitions=new WeakMap();
function sample(clip,time,idle,parents){
 if(time<0)return idle;
 const lead=.15,tail=.45,at=t=>{const f=clamp(t,0,clip.duration)*clip.meta.fps,i=Math.min(clip.poses.length-2,Math.floor(f));return blend(clip.poses[i],clip.poses[i+1],clamp(f-i,0,1),parents);};
 let byIdle=attackTransitions.get(clip);if(!byIdle){byIdle=new WeakMap();attackTransitions.set(clip,byIdle);}
 let motion=byIdle.get(idle);
 if(!motion){
  const first=localize(clip.poses[0].points,clip.poses[0].q,parents),next=localize(clip.poses[1].points,clip.poses[1].q,parents),fps=clip.meta.fps;
  const angular=first.q.map((q,i)=>mul(R.qlog(qm(next.q[i],qinv(q))),fps)),linear=first.p.map((p,i)=>mul(sub(next.p[i],p),fps));
  // Meet frame zero with its authored velocity, preserving the existing lead
  // duration and hit window instead of holding that frame during entry.
  const leadTarget=t=>{const elapsed=t-lead;if(elapsed>=0)return at(elapsed);return fk({q:first.q.map((q,i)=>unit(qm(qexp(mul(angular[i],elapsed)),q))),p:first.p.map((p,i)=>{const v=add(p,mul(linear[i],elapsed));return parents[i]>=0?mul(unit(v),length(p)):v;})},parents);};
  motion={entry:transition(()=>idle,leadTarget,lead,parents),exit:transition(t=>at(clip.duration+t),()=>idle,tail,parents)};byIdle.set(idle,motion);
 }
 if(time<lead)return motion.entry(time);
 if(time<lead+clip.duration)return at(time-lead);
 return motion.exit(time-lead-clip.duration);
}
function effector(attack){if(attack==='headbutt')return 'head';if(attack==='KickL')return 'foot_l';if(attack==='KickR'||attack==='sweepKick')return 'foot_r';return /L$/.test(attack)&&!attack.startsWith('slash')?'hand_l':'hand_r';}
function swordPoint(sword,z){const m=sword.local_to_hand;return [z*m[8]+m[12],z*m[9]+m[13],z*m[10]+m[14]];}
function contactPoint(p,attack,names,sword){const j=names.indexOf(effector(attack));let off=[0,0,0];if(attack==='pike'||attack.startsWith('slash'))off=swordPoint(sword,sword.blade_tip_m);else if(attack==='headbutt')off=[.1,-.08,0];else if(effector(attack).startsWith('foot_'))off=[.07,-.06,0];else off=[.07,0,0];return add(p.points[j],rotate(p.q[j],off));}
function aimPose(p,target,attack,names,parents,sword,weight){if(weight<=0)return p;const local=localize(p.points,p.q,parents),base=local.q.map(q=>q.slice()),end=names.indexOf(effector(attack));let chain=[],j=parents[end];while(j>1){chain.push(j);j=parents[j];}if(effector(attack).startsWith('foot_'))chain=[names.indexOf('thigh_'+effector(attack).slice(-1))];let out=p;for(let pass=0;pass<3;pass++)for(const joint of chain){if(names[joint].startsWith('lowerarm'))continue;const a=sub(contactPoint(out,attack,names,sword),out.points[joint]),b=sub(target,out.points[joint]);if(length(a)<1e-5||length(b)<1e-5)continue;let delta=R.qlog(fromTo(a,b)),amount=length(delta),cap=(names[joint].startsWith('spine')?10:40)*rad*weight;if(amount>cap)delta=mul(delta,cap/amount);const parent=parents[joint],world=qm(qexp(mul(delta,.45)),out.q[joint]);local.q[joint]=qm(qinv(out.q[parent]),world);let total=R.qlog(qm(qinv(base[joint]),local.q[joint])),angle=length(total);if(angle>cap)local.q[joint]=qm(base[joint],qexp(mul(total,cap/angle)));out=fk(local,parents);}return out;}
function segmentDistance(point,a,b){const d=sub(b,a),u=clamp(dot(sub(point,a),d)/(dot(d,d)||1),0,1);return length(sub(point,add(a,mul(d,u))));}
function poseSettings(settings,id){return {...poseDefaults,...settings.poseTuning?.[id],blendIn:settings.poseBlendIn??poseDefaults.blendIn,blendDistance:settings.poseBlendDistance??poseDefaults.blendDistance,responseSpeed:settings.poseResponseSpeed??poseDefaults.responseSpeed,responseTime:settings.poseResponseTime??poseDefaults.responseTime};}
function attackEndFrame(settings,name,hit,last,fallback=last){const requested=settings.attackEndFrames?.[name]??(name==='sweepKick'?settings.sweepKickEndFrame:undefined);return clamp(requested==null?fallback:Math.round(requested),Math.ceil(hit),last);}
const api={attackEndFrame,poseNames,poseDefaults,poseSettings,returnDuration,attackReturn,jumpBuild,walkForwardSpeed:2,defaults,jumpDefaults,sanitizeJump,dirs,sanitize,flipAxis,orientation,poseFromShared,centerPose,decode,sample,blend,transition,motionStep,registerRig,kneeBend,effector,swordPoint,contactPoint,aimPose,segmentDistance};
if(typeof module!=='undefined')module.exports=api;else root.BodyflipCore=api;
})(globalThis);
