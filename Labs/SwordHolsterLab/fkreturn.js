/* Adapter for the unchanged Attack Recovery Lab FK/inertia engine. */
(function(root){
'use strict';
const R=typeof module!=='undefined'?require('./recovery.js'):root.Recovery;
const T=typeof module!=='undefined'?require('./retime.js'):root.Retime;
const {unit,qm,qinv,qlog,rotate,fromTo,length:len,mul,sub}=R;
const bones=['spine','clavicle','upperarm','lowerarm','hand','neck_01','neck_02','head'];
const defaults=()=>({enabled:true,startFraction:.9,duration:1,returnEasing:1,inertia:1,inertiaHold:0,inertiaDecay:1,worldInertia:false,springReturn:false,angleTimeSeconds:.29,upperArmTwistRemoval:0,handRotationFKAlpha:1,armIKEnabled:false,armIKStart:0,armIKEnd:.25,swordPointSpeed:0,swordPointExponent:1.5,swordPointCutoff:.5,timingCurve:T.linear(),boneInertia:Object.fromEntries(bones.map(k=>[k,1]))});
function sanitize(input={}){
 const o={...defaults(),...input};delete o.handRotationExponent;
 for(const [k,lo,hi] of [['startFraction',0,1],['duration',.1,5],['returnEasing',0,1],['inertia',0,1],['inertiaHold',0,.8],['inertiaDecay',0,4],['angleTimeSeconds',0,4],['upperArmTwistRemoval',0,1],['handRotationFKAlpha',0,1],['armIKStart',0,1],['armIKEnd',0,1],['swordPointSpeed',-3600,3600],['swordPointExponent',1,8],['swordPointCutoff',0,.99]])o[k]=Math.max(lo,Math.min(hi,Number.isFinite(Number(o[k]))?Number(o[k]):defaults()[k]));
 for(const k of ['enabled','worldInertia','springReturn','armIKEnabled'])o[k]=!!o[k];
 o.armIKEnd=Math.max(o.armIKStart,o.armIKEnd);
 o.timingCurve=T.sanitize(input.timingCurve);
 o.boneInertia=Object.fromEntries(bones.map(k=>[k,Math.max(0,Math.min(1,Number.isFinite(Number(input.boneInertia?.[k]))?Number(input.boneInertia[k]):1))]));return o;
}
const local=(pose,parents)=>R.localize(pose.map(p=>p.p),pose.map(p=>p.q),parents);
function prepare({names,parents,last,previous,base,previousBase,dt,profile,handInertia=false,handRotationReturn=handInertia}){
 const idle=local(base,parents),spine=names.indexOf('spine_01');
 const upper=names.map((_,j)=>{for(let k=j;k>=0;k=parents[k])if(k===spine)return true;return false;});
 // Express the incoming residual relative to moving locomotion in a fixed
 // reference pose. The original engine can then operate unchanged.
 const reference=(pose,moving)=>{
  const a=local(pose,parents),b=local(moving,parents);
  return {q:a.q.map((q,j)=>upper[j]?unit(qm(qm(idle.q[j],qinv(b.q[j])),q)):idle.q[j]),p:a.p.map((p,j)=>upper[j]?rotate(fromTo(b.p[j],idle.p[j]),p):idle.p[j])};
 };
 const end=reference(last,base),before=reference(previous,previousBase),poses=[R.fk(before,parents),R.fk(end,parents)];
 const idleOffsets=idle.p.map((p,j)=>len(p)>1e-8?mul(unit(p),len(end.p[j])):end.p[j]);
 const model={names,parents,spine,upper,idle,idleOffsets,arms:[],meta:{fps:1/dt,frames:2},attackSeconds:dt,poses,locals:[before,end],
  inertial:upper.map((u,j)=>u&&(!/^hand_[lr]$/.test(names[j])||(handInertia&&names[j]==='hand_r'))),inertiaKeys:names.map(n=>/^spine_0[1-5]$/.test(n)?'spine':n.replace(/_(l|r)$/,'')),
  worldVelocity:poses[1].q.map((q,j)=>mul(qlog(qm(q,qinv(poses[0].q[j]))),1/dt)),
  offsetVelocity:end.p.map((p,j)=>len(p)>1e-8&&len(before.p[j])>1e-8?mul(qlog(fromTo(before.p[j],p)),1/dt):[0,0,0])};
 model.idlePose=R.fk({q:end.q.map((q,j)=>upper[j]?idle.q[j]:q),p:end.p.map((p,j)=>upper[j]?idleOffsets[j]:p)},parents);
 const options=sanitize(profile),timing=R.returnTiming(model,options);
 const handRotation=handRotationReturn&&options.handRotationFKAlpha<1?prepareHandRotation(names,last,previous,base,previousBase,dt,timing.duration):null;
 const arm=names.map((n,j)=>/^upperarm_r$|^lowerarm_r$|^hand_r$/.test(n)?j:-1).filter(j=>j>=0),root=names.indexOf('root');
 const armIK=options.armIKEnabled&&arm.length===3&&root>=0?{arm,root,previous:captureIK(last,base,arm,root,0),anchor:null}:null;
 return {model,options,timing,curve:T.prepare(options.timingCurve),handRotation,armIK};
}
// A single rotational joint in the character-root frame, using the same return
// engine and duration as the released arm. It never authors hand position.
function prepareHandRotation(names,last,previous,base,previousBase,dt,duration){
 const hand=names.indexOf('hand_r'),root=names.indexOf('root');if(hand<0||root<0)return null;
 const relative=pose=>unit(qm(qinv(pose[root].q),pose[hand].q)),target=relative(base),endQ=relative(last);
 const beforeQ=unit(qm(qm(target,qinv(relative(previousBase))),relative(previous)));
 const joint=q=>({q:[q],p:[[0,0,0]]}),idle=joint(target),end=joint(endQ),before=joint(beforeQ);
 const model={names:['hand_r'],parents:[-1],spine:0,upper:[true],idle,idleOffsets:idle.p,arms:[],meta:{fps:1/dt,frames:2},attackSeconds:dt,
  poses:[R.fk(before,[-1]),R.fk(end,[-1])],locals:[before,end],idlePose:R.fk(idle,[-1]),inertial:[true],inertiaKeys:['hand'],
  worldVelocity:[mul(qlog(qm(endQ,qinv(beforeQ))),1/dt)],offsetVelocity:[[0,0,0]],fixedReturnDuration:duration};
 return {hand,root,model};
}
function applyHandRotation(returnModel,base,elapsed,pose){
 const h=returnModel?.handRotation;if(!h||elapsed<=0)return pose;
 const {options,timing,curve}=returnModel;
 let independent=base[h.hand].q;
 if(elapsed<timing.duration-1e-12){
  const t=T.time(curve,elapsed,0,timing.duration),rotation=R.sample(h.model,h.model.attackSeconds+t,options).q[0];
  const target=unit(qm(qinv(base[h.root].q),base[h.hand].q));
  independent=unit(qm(base[h.root].q,qm(qm(target,qinv(h.model.idle.q[0])),rotation)));
 }
 const result=pose.slice();result[h.hand]={...pose[h.hand],q:R.qslerp(independent,pose[h.hand].q,options.handRotationFKAlpha)};return result;
}
function sample(returnModel,base,elapsed){
 const {model,options,timing}=returnModel;if(elapsed>=timing.duration-1e-12)return base;
 // Retime only the return residual; locomotion and head retain the current tick.
 const progressTime=T.time(returnModel.curve,Math.max(0,elapsed),0,timing.duration);
 const fk=R.sample(model,model.attackSeconds+progressTime,options),a=R.localize(fk.points,fk.q,model.parents),b=local(base,model.parents);
 const q=a.q.map((q,j)=>model.upper[j]?unit(qm(qm(b.q[j],qinv(model.idle.q[j])),q)):b.q[j]);
 const p=a.p.map((p,j)=>model.upper[j]?rotate(fromTo(model.idle.p[j],b.p[j]),p):b.p[j]);
 const result=R.fk({q,p},model.parents);
 return base.map((t,j)=>model.upper[j]?{...t,p:result.points[j],q:result.q[j]}:t);
}
// Blend the released wrist's FK path into a direct root-local return. The
// original FK pose remains the donor, so torso, left arm and wrist rotation
// retain their own controls. No future locomotion samples are needed.
// Transport bend directions onto the current shoulder-to-wrist line before
// interpolating their angle. Interpolating elbow positions can cross that line
// and abruptly choose the opposite side of the arm.
function armPole(pose,arm,root){
 const inv=qinv(pose[root].q),d=unit(rotate(inv,sub(pose[arm[2]].p,pose[arm[0]].p)));
 let p=rotate(inv,sub(pose[arm[1]].p,pose[arm[0]].p));p=sub(p,mul(d,R.dot(p,d)));
 for(const axis of [[0,1,0],[0,0,1]])if(len(p)<1e-7){p=rotate(qm(inv,pose[arm[0]].q),axis);p=sub(p,mul(d,R.dot(p,d)));}
 return {d,p:unit(p)};
}
const bendAngle=(a,b,d)=>Math.atan2(R.dot(d,R.cross(a,b)),R.dot(a,b));
const carryPole=(pole,d)=>rotate(fromTo(pole.d,d),pole.p);
function captureIK(pose,base,arm,root,elapsed){
 const relative=ps=>arm.map(j=>({p:rotate(qinv(ps[root].q),sub(ps[j].p,ps[root].p)),q:unit(qm(qinv(ps[root].q),ps[j].q))}));
 return {elapsed,pose:relative(pose),base:relative(base)};
}
function anchorIK(seed,current,start){
 const prior=seed.previous,u=current.elapsed>prior.elapsed?Math.max(0,Math.min(1,(start-prior.elapsed)/(current.elapsed-prior.elapsed))):0;
 const at=key=>current[key].map((v,j)=>({p:R.add(prior[key][j].p,mul(sub(v.p,prior[key][j].p),u)),q:R.qslerp(prior[key][j].q,v.q,u)}));
 const pose=at('pose'),base=at('base'),root={p:[0,0,0],q:[0,0,0,1]};
 seed.anchor={point:pose[2].p,pole:armPole([...pose,root],[0,1,2],3),basePole:armPole([...base,root],[0,1,2],3)};
 seed.previous=null;
}
function returnProgress(ret,elapsed){
 const x=T.time(ret.curve,elapsed,0,ret.timing.duration)/ret.timing.duration;
 return x+(x*x*x*(10+x*(-15+6*x))-x)*ret.options.returnEasing;
}
function armIKWeight(returnModel,elapsed){
 const {options,timing}=returnModel;
 if(!options.armIKEnabled||elapsed<=0||elapsed>=timing.duration)return 0;
 const x=elapsed/timing.duration;
 return options.armIKEnd>options.armIKStart?Math.max(0,Math.min(1,(x-options.armIKStart)/(options.armIKEnd-options.armIKStart))):Number(x>=options.armIKStart);
}
function applyArmIK(returnModel,base,elapsed,pose,solve){
 const seed=returnModel?.armIK;if(!seed)return pose;
 const {arm,root}=seed,{options,timing}=returnModel,start=options.armIKStart*timing.duration;
 // Capture the actual outgoing FK pose when the blend begins, not at release.
 // Preparation visits ticks chronologically; interpolate the bracketing poses
 // for a fractional Start. Once captured, playback is stateless in either order.
 if(!seed.anchor){
  const current=captureIK(pose,base,arm,root,elapsed);
  if(elapsed<start){seed.previous=current;return pose;}
  anchorIK(seed,current,start);
 }
 const weight=armIKWeight(returnModel,elapsed);if(!weight)return pose;
 const anchor=seed.anchor,p0=returnProgress(returnModel,start);
 const progress=Math.max(0,Math.min(1,(returnProgress(returnModel,elapsed)-p0)/Math.max(1e-12,1-p0)));
 const toRoot=p=>rotate(qinv(base[root].q),sub(p,base[root].p));
 const path=R.add(base[root].p,rotate(base[root].q,R.add(anchor.point,mul(sub(toRoot(base[arm[2]].p),anchor.point),progress))));
 const target=R.add(pose[arm[2]].p,mul(sub(path,pose[arm[2]].p),weight));
 const direction=unit(rotate(qinv(base[root].q),sub(target,pose[arm[0]].p)));
 const initial=carryPole(anchor.pole,direction),idle=carryPole(armPole(base,arm,root),direction);
 const reference=bendAngle(initial,carryPole(anchor.basePole,direction),direction);
 const delta=bendAngle(initial,idle,direction),angle=delta+2*Math.PI*Math.round((reference-delta)/(2*Math.PI));
 const wanted=rotate(R.qexp(mul(direction,angle*progress)),initial);
 const existing=carryPole(armPole(pose,arm,root),direction);
 const pole=rotate(base[root].q,rotate(R.qexp(mul(direction,bendAngle(existing,wanted,direction)*weight)),existing));
 const out=pose.map(p=>({...p}));
 solve(out,arm,{p:target,q:pose[arm[2]].q},pole);
 // Carry any twist/finger children with their edited parent, preserving locals.
 const changed=new Set(arm),parents=returnModel.model.parents;
 for(let j=0;j<out.length;j++)if(!changed.has(j)&&changed.has(parents[j])){
  const parent=parents[j],q=unit(qm(out[parent].q,qinv(pose[parent].q)));
  out[j]={...pose[j],p:R.add(out[parent].p,rotate(q,sub(pose[j].p,pose[parent].p))),q:unit(qm(q,pose[j].q))};changed.add(j);
 }
 return out;
}
// The integral of a symmetric sigmoid velocity. Dividing by its peak slope
// keeps the requested angular speed a ceiling; exponent 1 is constant speed.
function swordPointProgress(u,exponent){
 u=Math.max(0,Math.min(1,u));if(exponent===1)return u;
 const a=Math.pow(u,exponent),b=Math.pow(1-u,exponent);return a/(a+b)/exponent;
}
// Chronological, current-pose-only preparation shared by both planners. Only
// the released hand rotation changes; playback samples the cached correction.
function prepareSwordPoint(model,compose,grip){
 const profile=model.o.drawReturn,ret=model.armReturn||model.fkReturn,release=model.plan?.slideEnd;
 if(model.o.sheathe||!ret||!profile.swordPointSpeed||!profile.swordPointCutoff||!Number.isFinite(release)||!model.frames[release])return model;
 const hand=model.names.indexOf('hand_r'),root=model.names.indexOf('root');
 const start=release/60,duration=ret.timing.duration,window=duration*profile.swordPointCutoff,end=start+window;
 const source=model.frames.slice(),keys=[];
 const relative=p=>unit(qm(qinv(p[root].q),p[hand].q));
 let q=relative(source[release].pose),previous=source[release].pose,previousTime=start,resume=null;
 const withQ=(pose,localQ)=>{const out=pose.slice();out[hand]={...pose[hand],q:unit(qm(pose[root].q,localQ))};return out;};
 for(let i=release+1;i<source.length;i++){
  const frame=source[i],time=i/60,base=frame.pose,prior=source[i-1].pose;
  if(previousTime<end-1e-12){
   const at=Math.min(time,end),u=(at-previousTime)/(time-previousTime);
   const anchor=base.map((p,j)=>({...p,q:R.qslerp(prior[j].q,p.q,u)}));
   const budget=profile.swordPointSpeed*Math.PI/180*window*(swordPointProgress((at-start)/window,profile.swordPointExponent)-swordPointProgress((previousTime-start)/window,profile.swordPointExponent));
   // Right multiplication rotates about the hand's own X axis.
   q=unit(qm(q,R.qexp([budget,0,0])));
   const aimed=withQ(anchor,q);
   if(at>=end-1e-12){
    const remaining=duration-window,options={...profile,handRotationFKAlpha:0};
    resume={options,timing:{duration:remaining},curve:T.prepare(options.timingCurve),handRotation:prepareHandRotation(model.names,aimed,previous,anchor,prior,at-previousTime,remaining)};
   }
   previous=aimed;previousTime=at;
  }
  const pose=time<=end+1e-12?withQ(base,q):applyHandRotation(resume,base,time-end,base);
  const correction=unit(qm(relative(pose),qinv(relative(base))));keys.push({tick:i,q:correction});
  model.frames[i]={...frame,pose,sword:compose(grip(model.setup,frame.scale),pose[hand])};
 }
 model.swordPoint={start:release,end:end*60,finish:(start+duration)*60,hand,root,keys:[{tick:release,q:[0,0,0,1]},...keys]};
 if(model.tickPlayback)model.sourceLocals=model.frames.map(f=>local(f.pose,model.parents));
 return model;
}
function applySwordPoint(model,frame,time,compose,grip){
 const track=model.swordPoint,x=time*60;if(!track||x<=track.start)return frame;
 const keys=track.keys,v=Math.min(keys.length-1,x-track.start),i=Math.floor(v),q=R.qslerp(keys[i].q,keys[Math.min(i+1,keys.length-1)].q,v-i);
 const pose=frame.pose.slice(),rootQ=pose[track.root].q;
 pose[track.hand]={...pose[track.hand],q:unit(qm(qm(qm(rootQ,q),qinv(rootQ)),pose[track.hand].q))};
 return {...frame,pose,sword:compose(grip(model.setup,frame.scale),pose[track.hand])};
}
const api={bones,defaults,sanitize,prepare,sample,applyHandRotation,applyArmIK,armIKWeight,prepareSwordPoint,applySwordPoint,swordPointProgress};if(typeof module!=='undefined')module.exports=api;else root.FKReturn=api;
})(globalThis);
