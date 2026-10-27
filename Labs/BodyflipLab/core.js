/* Full-body sampling and orientation. Recovery math is an independent D/S copy. */
(function(root){
'use strict';
const R=typeof module!=='undefined'?require('./recovery.js'):root.Recovery;
const {add,sub,mul,dot,cross,length,unit,qm,qinv,rotate,qexp,qslerp,fromTo,fk,localize}=R;
const rad=Math.PI/180,clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const dirs=['Back','B-R 30','B-R 60','Right','F-R 60','F-R 30','Front','F-L 30','F-L 60','Left','B-L 60','B-L 30'];
// supportSpeed is stored/displayed in cm/s; world positions and physics use metres.
// kickToArmed is the legacy saved key for the all-attack Direct to Armed mode.
const defaults={kickToArmed:false,softAttackLegs:true,pelvisAttackCompensation:.5,surfaceIK:true,loadMs:100,rebound:.5,platformTranslucency:.8,platforms:null,jumpSkew:.5,ramps:true,jumpEvents:null,mode:'jump',motion:'kinematic',runSeconds:1,jumpEarly:.1,runPhase:0,jumpBlend:.2,legBlend:.2,fallCap:20,jumpFoot:'Auto',standRatio:.5,plantPitch:10,toeOffPitch:35,footRollSpeed:720,matchLeg:true,supportCone:30,supportReach:.99,supportTrigger:.05,supportAlpha:1,supportSpeed:800,airFlip:false,playbackSpeed:1,trimLoop:false,trimIn:0,trimOut:3,axis:0,flipSpeed:120,flipAngle:0,twistAngle:0,twistSpeed:0,attack:'slashLD',variant:1,aim:true,aimWeight:.8,loop:false,attackRate:1,ghost:false,animLeg:false,animOtherLeg:false,rawLeg:false,showCone:false,showJump:false,bicolor:true,skeleton:false,target:[.4,1.55,.8],radius:.12};
// Per-jump angles are totals, independent of the legacy continuous Air flip.
const jumpDefaults={jumpPercent:100,attack:'none',attackDelay:0,attackIn:.2,attackOut:.25,flip:0,twist:0,turnDelay:0,turnDuration:.8,turnIn:.4,turnOut:.4,turnAxis:null,pose:'none',poseIn:.2,poseHold:.3,poseOut:.25};
function sanitizeJump(e={}){
 const o={...jumpDefaults};
 for(const [key,min,max] of [['jumpPercent',0,400],['attackDelay',0,30],['attackIn',1/60,3],['attackOut',1/60,3],['flip',-3600,3600],['twist',-3600,3600],['turnDelay',0,30],['turnDuration',1/60,30],['poseIn',1/60,5],['poseHold',0,30],['poseOut',1/60,5]])o[key]=clamp(Number.isFinite(e[key])?e[key]:jumpDefaults[key],min,max);
 // Half/half reproduces the previous quintic turn for all existing durations.
 for(const key of ['turnIn','turnOut'])o[key]=clamp(Number.isFinite(e[key])?e[key]:o.turnDuration/2,0,30);
 o.turnAxis=Number.isInteger(e.turnAxis)&&e.turnAxis>=0&&e.turnAxis<12?e.turnAxis:null;
 o.attack=['none','headbutt','hookL','hookR','jabL','jabR','KickL','KickR','overL','overR','pike','slashL','slashLD','slashLU','slashR','slashRD','slashRU'].includes(e.attack)?e.attack:'none';
 o.pose=['none','pose1','pose2','pose3','pose4'].includes(e.pose)?e.pose:'none';
 return o;
}
function sanitize(s={}){const o={...defaults,...s};delete o.endLeg;delete o.jumpGap;if(s.legBlend===undefined)o.legBlend=s.jumpBlend??defaults.legBlend;for(const [k,a,b] of [['pelvisAttackCompensation',0,1],['loadMs',0,300],['rebound',0,1],['platformTranslucency',0,1],['jumpSkew',0,1],['supportCone',0,85],['footRollSpeed',0,3600],['plantPitch',-25,35],['toeOffPitch',0,60],['standRatio',0,5],['jumpEarly',0,5],['playbackSpeed',.1,2],['supportReach',.5,1],['supportTrigger',0,.3],['supportAlpha',0,Infinity],['supportSpeed',.1,2000],['trimIn',0,599.98],['trimOut',1/60,600],['runSeconds',.1,5],['runPhase',0,1],['jumpBlend',0,1],['legBlend',0,1],['fallCap',2,50],['axis',0,11],['flipSpeed',-720,720],['flipAngle',-360,360],['twistAngle',-360,360],['twistSpeed',-720,720],['aimWeight',0,1],['attackRate',.25,2],['radius',.04,.35]])o[k]=clamp(Number.isFinite(+o[k])?+o[k]:defaults[k],a,b);o.jumpEarly=Math.min(o.jumpEarly,Math.max(0,o.runSeconds-1/60));o.trimIn=Math.round(o.trimIn*60)/60;o.trimOut=Math.max(o.trimIn+1/60,Math.round(o.trimOut*60)/60);o.axis=Math.round(o.axis);o.target=Array.isArray(s.target)&&s.target.length===3&&s.target.every(Number.isFinite)?s.target.map(x=>clamp(x,-1000000,1000000)):[...defaults.target];for(const k of ['kickToArmed','softAttackLegs','surfaceIK','ramps','aim','loop','ghost','animLeg','animOtherLeg','rawLeg','showCone','showJump','bicolor','skeleton','airFlip','trimLoop','matchLeg'])o[k]=!!o[k];o.motion=o.motion==='kinematic'?'kinematic':'sim';if(o.mode==='space')o.mode='idle';o.mode=['idle','walk','jump','spaceGym'].includes(o.mode)?o.mode:'jump';o.jumpFoot=['Auto','L','R'].includes(o.jumpFoot)?o.jumpFoot:'Auto';o.jumpEvents=Array.isArray(o.jumpEvents)?o.jumpEvents.slice(0,32).filter(e=>e&&Number.isFinite(+e.time)).map((e,i)=>({id:typeof e.id==='string'&&/^[a-zA-Z0-9_-]{1,48}$/.test(e.id)?e.id:'jump'+i,time:Math.round(clamp(+e.time,0,600)*60)/60,surface:['auto','floor','left','right'].includes(e.surface)?e.surface:'auto',...sanitizeJump(e)})).sort((a,b)=>a.time-b.time):null;o.platforms=Array.isArray(o.platforms)?o.platforms.slice(0,128).filter(p=>p&&Array.isArray(p.position)&&p.position.length===3&&p.position.every(Number.isFinite)&&Array.isArray(p.size)&&p.size.length===3&&p.size.every(Number.isFinite)&&Array.isArray(p.rotation)&&p.rotation.length===4&&p.rotation.every(Number.isFinite)).map((p,i)=>{const n=Math.hypot(...p.rotation);return {id:typeof p.id==='string'&&/^[a-zA-Z0-9_-]{1,48}$/.test(p.id)?p.id:'platform'+i,position:p.position.map(v=>clamp(v,-1e6,1e6)),size:p.size.map(v=>clamp(v,.02,1000)),rotation:n>1e-9?p.rotation.map(v=>v/n):[0,0,0,1]};}):null;return o;}
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
 for(const side of ['l','r']){
  const chain=['thigh','calf','foot','ball'].map(n=>names.indexOf(n+'_'+side));if(chain.some(i=>i<0))continue;
  const [,knee,foot]=chain,u=unit(local.p[knee]),v=unit(rotate(local.q[knee],local.p[foot]));
  const normal=length(cross(u,v))>1e-5?unit(cross(u,v)):[0,0,-1];
  legs.push({chain,knee,foot,normal});
 }
 motionRigs.set(parents,legs);
}
function kneeBend(local,leg){const u=unit(local.p[leg.knee]),v=unit(rotate(local.q[leg.knee],local.p[leg.foot]));return Math.atan2(dot(leg.normal,cross(u,v)),dot(u,v));}
function transition(outgoing,incoming,duration,parents,indices=null,rotationOnly=false){
 if(!(duration>0))return incoming;
 const h=motionStep,a=outgoing(0),prev=outgoing(-h),b=incoming(0),next=incoming(h);
 const la=localize(a.points,a.q,parents),lp=localize(prev.points,prev.q,parents),lb=localize(b.points,b.q,parents),ln=localize(next.points,next.q,parents);
 const bones=indices||parents.map((_,i)=>i),seeds=bones.map(i=>{
  const velocity=mul(R.qlog(qm(la.q[i],qinv(lp.q[i]))),1/h),error=R.qlog(qm(la.q[i],qinv(lb.q[i])));
  let future=R.qlog(qm(qm(qexp(mul(velocity,h)),la.q[i]),qinv(ln.q[i])));
  // Keep the logarithm on the same branch when the offset crosses 180 degrees.
  if(length(sub(future,error))>Math.PI)future=sub(future,mul(unit(future),Math.PI*2));
  return {i,error,rate:mul(sub(future,error),1/h),offset:sub(la.p[i],lb.p[i]),speed:mul(sub(sub(la.p[i],lp.p[i]),sub(ln.p[i],lb.p[i])),1/h),length:length(la.p[i])-length(lb.p[i]),lengthRate:(length(la.p[i])-length(lp.p[i])-length(ln.p[i])+length(lb.p[i]))/h};
 });
 const momentumTimes=new Map();
 function blendedLocal(target,t,selected=seeds,prepared=null){
  const local=prepared?{p:prepared.p.slice(),q:prepared.q.slice()}:localize(target.points,target.q,parents),x=clamp(t/duration,0,1),position=1-3*x*x+2*x*x*x,velocity=duration*x*(1-x)*(1-x);
  for(const s of selected){const i=s.i,tau=momentumTimes.get(i),carried=tau===undefined?velocity:tau>0?tau*(-Math.expm1(-Math.max(0,t)/tau))*position:0;local.q[i]=unit(qm(qexp(add(mul(s.error,position),mul(s.rate,carried))),local.q[i]));
   if(!rotationOnly){const original=local.p[i],p=add(original,add(mul(s.offset,position),mul(s.speed,carried)));
    // Preserve skeletal lengths; root translations are unconstrained.
    local.p[i]=parents[i]>=0&&length(p)>1e-9?mul(unit(p),Math.max(0,length(original)+s.length*position+s.lengthRate*carried)):p;
   }
  }
  return local;
 }
 // Plan braking before a knee reaches its hinge boundary. Shorten only the
 // carried velocity, not the pose blend or its deadline. The whole leg shares
 // that decay so the thigh/ankle cannot keep swinging against its knee. Integrate
 // an exponential braking curve; ease its remaining displacement out over the
 // full blend instead of immediately recoiling from the straight-leg boundary.
 const legs=(motionRigs.get(parents)||[]).filter(l=>bones.includes(l.knee));
 if(legs.length){
  const count=Math.max(48,Math.ceil(duration*480)),cache=new Map();
  const targetAt=t=>{let entry=cache.get(t);if(!entry){const pose=incoming(t);entry={t,local:localize(pose.points,pose.q,parents)};cache.set(t,entry);}return entry;};
  const targets=Array.from({length:count+1},(_,i)=>targetAt(duration*i/count));
  for(const leg of legs){
   const selected=seeds.filter(s=>s.i===leg.knee||s.i===leg.foot);
   const valid=sample=>{const angle=kneeBend(blendedLocal(null,sample.t,selected,sample.local),leg);return angle>=-1e-6&&angle<=150*rad+1e-6;};
   if(targets.every(valid))continue;
   const fits=tau=>{for(const i of leg.chain)momentumTimes.set(i,tau);return targets.every(valid)&&Array.from({length:33},(_,i)=>valid(targetAt(Math.min(duration,4*tau)*i/32))).every(Boolean);};
   let lo=0,hi=duration;
   // Zero momentum leaves the ordinary moving-pose blend. Do not mask an
   // invalid source/target by clamping the rendered joint after sampling.
   if(fits(0)){for(let i=0;i<18;i++){const mid=(lo+hi)*.5;if(fits(mid))lo=mid;else hi=mid;}fits(lo*.8);}
  }
 }
 return t=>{
  const target=incoming(Math.max(0,t));if(t>=duration)return target;
  return fk(blendedLocal(target,t),parents);
 };
}
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
function effector(attack){if(attack==='headbutt')return 'head';if(attack==='KickL')return 'foot_l';if(attack==='KickR')return 'foot_r';return /L$/.test(attack)&&!attack.startsWith('slash')?'hand_l':'hand_r';}
function swordPoint(sword,z){const m=sword.local_to_hand;return [z*m[8]+m[12],z*m[9]+m[13],z*m[10]+m[14]];}
function contactPoint(p,attack,names,sword){const j=names.indexOf(effector(attack));let off=[0,0,0];if(attack==='pike'||attack.startsWith('slash'))off=swordPoint(sword,sword.blade_tip_m);else if(attack==='headbutt')off=[.1,-.08,0];else if(attack.startsWith('Kick'))off=[.07,-.06,0];else off=[.07,0,0];return add(p.points[j],rotate(p.q[j],off));}
function aimPose(p,target,attack,names,parents,sword,weight){if(weight<=0)return p;const local=localize(p.points,p.q,parents),base=local.q.map(q=>q.slice()),end=names.indexOf(effector(attack));let chain=[],j=parents[end];while(j>1){chain.push(j);j=parents[j];}if(attack.startsWith('Kick'))chain=[names.indexOf(attack==='KickL'?'thigh_l':'thigh_r')];let out=p;for(let pass=0;pass<3;pass++)for(const joint of chain){if(names[joint].startsWith('lowerarm'))continue;const a=sub(contactPoint(out,attack,names,sword),out.points[joint]),b=sub(target,out.points[joint]);if(length(a)<1e-5||length(b)<1e-5)continue;let delta=R.qlog(fromTo(a,b)),amount=length(delta),cap=(names[joint].startsWith('spine')?10:40)*rad*weight;if(amount>cap)delta=mul(delta,cap/amount);const parent=parents[joint],world=qm(qexp(mul(delta,.45)),out.q[joint]);local.q[joint]=qm(qinv(out.q[parent]),world);let total=R.qlog(qm(qinv(base[joint]),local.q[joint])),angle=length(total);if(angle>cap)local.q[joint]=qm(base[joint],qexp(mul(total,cap/angle)));out=fk(local,parents);}return out;}
function segmentDistance(point,a,b){const d=sub(b,a),u=clamp(dot(sub(point,a),d)/(dot(d,d)||1),0,1);return length(sub(point,add(a,mul(d,u))));}
const api={walkForwardSpeed:2,defaults,jumpDefaults,sanitizeJump,dirs,sanitize,flipAxis,orientation,poseFromShared,centerPose,decode,sample,blend,transition,motionStep,registerRig,kneeBend,effector,swordPoint,contactPoint,aimPose,segmentDistance};
if(typeof module!=='undefined')module.exports=api;else root.BodyflipCore=api;
})(globalThis);
