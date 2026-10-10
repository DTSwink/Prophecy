/* Adapter for the unchanged Attack Recovery Lab FK/inertia engine. */
(function(root){
'use strict';
const R=typeof module!=='undefined'?require('./recovery.js'):root.Recovery;
const {unit,qm,qinv,qlog,rotate,fromTo,length:len,mul,sub}=R;
const bones=['spine','clavicle','upperarm','lowerarm','neck_01','neck_02','head'];
const defaults=()=>({enabled:true,duration:1,returnEasing:1,inertia:1,inertiaHold:0,inertiaDecay:1,worldInertia:false,springReturn:false,angleTimeSeconds:.29,upperArmTwistRemoval:0,boneInertia:Object.fromEntries(bones.map(k=>[k,1]))});
function sanitize(input={}){
 const o={...defaults(),...input};
 for(const [k,lo,hi] of [['duration',.1,5],['returnEasing',0,1],['inertia',0,1],['inertiaHold',0,.8],['inertiaDecay',0,4],['angleTimeSeconds',0,4],['upperArmTwistRemoval',0,1]])o[k]=Math.max(lo,Math.min(hi,Number.isFinite(Number(o[k]))?Number(o[k]):defaults()[k]));
 for(const k of ['enabled','worldInertia','springReturn'])o[k]=!!o[k];
 o.boneInertia=Object.fromEntries(bones.map(k=>[k,Math.max(0,Math.min(1,Number.isFinite(Number(input.boneInertia?.[k]))?Number(input.boneInertia[k]):1))]));return o;
}
const local=(pose,parents)=>R.localize(pose.map(p=>p.p),pose.map(p=>p.q),parents);
function prepare({names,parents,last,previous,base,previousBase,dt,profile}){
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
  inertial:upper.map((u,j)=>u&&!/^hand_[lr]$/.test(names[j])),inertiaKeys:names.map(n=>/^spine_0[1-5]$/.test(n)?'spine':n.replace(/_(l|r)$/,'')),
  worldVelocity:poses[1].q.map((q,j)=>mul(qlog(qm(q,qinv(poses[0].q[j]))),1/dt)),
  offsetVelocity:end.p.map((p,j)=>len(p)>1e-8&&len(before.p[j])>1e-8?mul(qlog(fromTo(before.p[j],p)),1/dt):[0,0,0])};
 model.idlePose=R.fk({q:end.q.map((q,j)=>upper[j]?idle.q[j]:q),p:end.p.map((p,j)=>upper[j]?idleOffsets[j]:p)},parents);
 const options=sanitize(profile),timing=R.returnTiming(model,options);
 return {model,options,timing};
}
function sample(returnModel,base,elapsed){
 const {model,options,timing}=returnModel;if(elapsed>=timing.duration-1e-12)return base;
 const fk=R.sample(model,model.attackSeconds+Math.max(0,elapsed),options),a=R.localize(fk.points,fk.q,model.parents),b=local(base,model.parents);
 const q=a.q.map((q,j)=>model.upper[j]?unit(qm(qm(b.q[j],qinv(model.idle.q[j])),q)):b.q[j]);
 const p=a.p.map((p,j)=>model.upper[j]?rotate(fromTo(model.idle.p[j],b.p[j]),p):b.p[j]);
 const result=R.fk({q,p},model.parents);
 return base.map((t,j)=>model.upper[j]?{...t,p:result.points[j],q:result.q[j]}:t);
}
const api={bones,defaults,sanitize,prepare,sample};if(typeof module!=='undefined')module.exports=api;else root.FKReturn=api;
})(globalThis);
