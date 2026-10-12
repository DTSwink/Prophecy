/* Authored upper body cancels pelvis rotation; live local animation on the left. */
(function(root){
'use strict';
const R=typeof module!=='undefined'?require('./recovery.js'):root.Recovery;
const {add,sub,unit,qm,qinv,rotate,qexp,qslerp}=R,RAD=Math.PI/180,I=[0,0,0,1];
const defaults={clear:{pole:0,spine:[-94.051,-5.125,1.287],right:[-.124,43.499,5.962],left:[0,0,0]},seated:{pole:0,spine:[-93.854,-5.177,1.942],right:[-1.987,4.215,.045],left:[0,0,0]}};
function sanitize(input={}){return Object.fromEntries(['clear','seated'].map(e=>[e,{...Object.fromEntries(['spine','right','left'].map(b=>[b,[0,1,2].map(k=>{const v=Number(input?.[e]?.[b]?.[k]??defaults[e][b][k]);return Number.isFinite(v)?Math.max(-180,Math.min(180,v)):defaults[e][b][k];})])),pole:Number.isFinite(Number(input?.[e]?.pole))?Math.max(-180,Math.min(180,Number(input[e].pole))):0}]));}
const euler=v=>unit(qm(qm(qexp([0,0,v[2]*RAD]),qexp([0,v[1]*RAD,0])),qexp([v[0]*RAD,0,0])));
const angle=(a,b)=>2*Math.acos(Math.min(1,Math.abs(R.dot(unit(a),unit(b)))))/RAD;
function make(data,reference,entry=reference,compensation=1){
 const index=n=>data.names.indexOf(n),spine=[1,2,3,4,5].map(i=>index('spine_0'+i));
 const pelvis=index('pelvis'),top=spine[4],clav=index('clavicle_r'),left=index('clavicle_l');
 const bones=[top,clav,left],anchors=[pelvis,top,top];
 const affected=data.names.map((_,i)=>i).filter(i=>{for(let j=i;j>=0;j=data.parents[j])if(j===spine[0])return true;return false;});
 const refs=bones.map((j,k)=>unit(qm(qinv(reference[anchors[k]].q),reference[j].q)));
 const rightArm=['clavicle_r','upperarm_r','lowerarm_r','hand_r'].map(index),leftArm=['clavicle_l','upperarm_l','lowerarm_l','hand_l'].map(index);
 return {compensation,parents:data.parents,spine,pelvis,top,clav,left,shoulder:index('upperarm_r'),bones,anchors,affected,
  reference:refs,weights:new Map(spine.map((j,k)=>[j,(k+1)/5])),driven:new Set([...spine,...rightArm]),inertiaBones:[...spine,...rightArm,...leftArm],
  entryLocal:R.localize(entry.map(v=>v.p),entry.map(v=>v.q),data.parents),
  entryPelvisQ:[...entry[pelvis].q],
  entrySpine:spine.map(j=>unit(qm(qinv(entry[pelvis].q),entry[j].q))),
  entryBody:[...unit(qm(qinv(entry[pelvis].q),entry[top].q)),...unit(qm(qinv(entry[top].q),entry[clav].q)),...refs[2]]};
}
function blend(a,b,t){return [0,4,8].flatMap(k=>qslerp(a.slice(k,k+4),b.slice(k,k+4),t));}
function target(ctx,profile,insertion){
 const endpoint=key=>['spine','right','left'].flatMap((b,k)=>unit(qm(euler(profile[key][b]),ctx.reference[k])));
 return blend(endpoint('clear'),endpoint('seated'),Math.max(0,Math.min(1,insertion)));
}
const pelvisFrame=(ctx,base)=>ctx.compensation===1?ctx.entryPelvisQ:ctx.compensation===0?base[ctx.pelvis].q:qslerp(base[ctx.pelvis].q,ctx.entryPelvisQ,ctx.compensation);
function apply(ctx,base,v){
 // Cancel pelvis rotation for the whole FK chain, including its first offset.
 // Correcting only the top orientation leaves its position swaying underneath.
 // The entry orientation is stable; the live pelvis position still carries us.
 const out=base.slice(),frame=pelvisFrame(ctx,base),offset=unit(qm(v.slice(0,4),qinv(ctx.entrySpine[4])));
 for(const j of ctx.affected){
  const p=ctx.parents[j],frozen=ctx.driven.has(j);
  const localQ=frozen?ctx.entryLocal.q[j]:unit(qm(qinv(base[p].q),base[j].q));
  const localP=frozen?ctx.entryLocal.p[j]:rotate(qinv(base[p].q),sub(base[j].p,base[p].p));
  let q=unit(qm(out[p].q,localQ));
  if(ctx.weights.has(j))q=unit(qm(frame,qm(qslerp(I,offset,ctx.weights.get(j)),ctx.entrySpine[ctx.spine.indexOf(j)])));
  if(j===ctx.clav)q=unit(qm(out[ctx.top].q,v.slice(4,8)));
  if(j===ctx.left)q=unit(qm(out[ctx.top].q,qm(qm(v.slice(8,12),qinv(ctx.reference[2])),localQ)));
  out[j]={...base[j],p:add(out[p].p,rotate(p===ctx.pelvis?frame:out[p].q,localP)),q};
 }
 return out;
}
// Provisional slider edits add only the changed rotation to the displayed pose,
// retaining its arm solve and any early FK return until the worker replaces it.
function adjust(ctx,base,v){
 const out=base.slice(),offset=unit(qm(v.slice(0,4),qinv(ctx.reference[0])));
 const frame=pelvisFrame(ctx,base),delta=unit(qm(qm(frame,offset),qinv(frame)));
 for(const j of ctx.affected){
  const p=ctx.parents[j],inherited=unit(qm(out[p].q,qinv(base[p].q)));
  let q=unit(qm(inherited,base[j].q));
  if(ctx.weights.has(j))q=unit(qm(qslerp(I,delta,ctx.weights.get(j)),base[j].q));
  if(j===ctx.clav||j===ctx.left){
   const k=j===ctx.clav?1:2,offset=unit(qm(v.slice(k*4,k*4+4),qinv(ctx.reference[k])));
   const local=unit(qm(qinv(base[ctx.top].q),base[j].q));
   q=unit(qm(out[ctx.top].q,qm(offset,local)));
  }
  out[j]={...base[j],p:add(out[p].p,rotate(inherited,sub(base[j].p,base[p].p))),q};
 }
 return out;
}
const remaining=(a,b)=>Math.max(...[0,4,8].map(k=>angle(a.slice(k,k+4),b.slice(k,k+4))));
function advance(a,b,degreesPerSecond){return [0,4,8].flatMap(k=>{const x=a.slice(k,k+4),y=b.slice(k,k+4),d=angle(x,y);return qslerp(x,y,d>0?Math.min(1,degreesPerSecond/60/d):1);});}
const api={make,apply,adjust,target,blend,advance,remaining,sanitize,defaults,euler};
if(typeof module!=='undefined')module.exports=api;else root.BodyReach=api;
})(globalThis);
