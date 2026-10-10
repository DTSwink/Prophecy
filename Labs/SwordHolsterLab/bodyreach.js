/* Additive spine twist + clavicle swing. UE component-space poses, cm/radians. */
(function(root){
'use strict';
const R=typeof module!=='undefined'?require('./recovery.js'):root.Recovery;
const {add,sub,mul,dot,cross,length:len,unit,qm,qinv,rotate,qexp}=R,I=[0,0,0,1],RAD=Math.PI/180;
function basis(axis){
 axis=unit(axis);const u=unit(cross(axis,Math.abs(axis[0])<.8?[1,0,0]:[0,1,0]));
 return [u,cross(axis,u)];
}
const swing=(b,v)=>qexp(add(mul(b[0],v[0]),mul(b[1],v[1])));
function make(data,base){
 const index=n=>data.names.indexOf(n),spine=[1,2,3,4,5].map(i=>index('spine_0'+i));
 const top=spine[4],clav=index('clavicle_r'),shoulder=index('upperarm_r');
 const axis=(a,b)=>rotate(qinv(base[a].q),sub(base[b].p,base[a].p));
 const affected=data.names.map((_,i)=>i).filter(i=>{for(let j=i;j>=0;j=data.parents[j])if(j===spine[0])return true;return false;});
 return {parents:data.parents,spine,top,clav,shoulder,head:index('head'),affected,chain:[...spine,clav,shoulder],
  spineAxis:unit(axis(top,index('neck_01'))),clavBasis:basis(axis(clav,shoulder)),weights:new Map(spine.map((j,k)=>[j,(k+1)/5]))};
}
function apply(ctx,base,v,onlyShoulder=false){
 const localSpine=qexp(mul(ctx.spineAxis,v[0])),worldSpine=unit(qm(qm(base[ctx.top].q,localSpine),qinv(base[ctx.top].q)));
 const clavSwing=swing(ctx.clavBasis,v.slice(1)),out=base.slice();
 for(const j of onlyShoulder?ctx.chain:ctx.affected){
  const p=ctx.parents[j];if(p<0)continue;
  const inherited=unit(qm(out[p].q,qinv(base[p].q)));
  let q=unit(qm(inherited,base[j].q));
  if(ctx.weights.has(j))q=unit(qm(R.qslerp(I,worldSpine,ctx.weights.get(j)),base[j].q));
  if(j===ctx.clav)q=unit(qm(q,clavSwing));
  out[j]={...base[j],p:add(out[p].p,rotate(inherited,sub(base[j].p,base[p].p))),q};
 }
 return onlyShoulder?out[ctx.shoulder].p:out;
}
function bounded(v,limit){
 v=[...v];v[0]=Math.max(-limit,Math.min(limit,v[0]));
 const n=Math.hypot(v[1],v[2]);if(n>limit){v[1]*=limit/n;v[2]*=limit/n;}return v;
}
function optimize(ctx,base,target,seed,limitDegrees){
 const limit=limitDegrees*RAD,score=v=>{const d=sub(apply(ctx,base,v,true),target);return dot(d,d);};
 let best=bounded(seed,limit),cost=score(best);
 // Include neutral so a previous gait frame cannot force a worse solution.
 if(score([0,0,0])<cost){best=[0,0,0];cost=score(best);}
 for(const degrees of [16,8,4,2,1,.5,.125,.03125]){
  for(let sweep=0;sweep<4;sweep++){
   let improved=false;
   for(let k=0;k<3;k++)for(const sign of [-1,1]){
    const trial=[...best];trial[k]+=sign*degrees*RAD;
    const v=bounded(trial,limit),s=score(v);
    if(s<cost-1e-9){best=v;cost=s;improved=true;}
   }
   if(!improved)break;
  }
 }
 return best;
}
function advance(current,desired,degreesPerSecond){
 const v=[...current],step=degreesPerSecond*RAD/60;
 v[0]+=Math.max(-step,Math.min(step,desired[0]-v[0]));
 const delta=[desired[1]-v[1],desired[2]-v[2]],n=Math.hypot(...delta),f=n>0?Math.min(1,step/n):0;v[1]+=delta[0]*f;v[2]+=delta[1]*f;
 return v;
}
const remaining=(v,target)=>Math.max(Math.abs(v[0]-target[0]),Math.hypot(v[1]-target[1],v[2]-target[2]))/RAD;
const api={make,apply,optimize,advance,remaining,swing};
if(typeof module!=='undefined')module.exports=api;else root.BodyReach=api;
})(globalThis);
