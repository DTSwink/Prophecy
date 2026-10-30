/* Airborne contact uses the displayed body volumes, without a standing root envelope. */
(function(root){
'use strict';
const node=typeof module!=='undefined',R=node?require('./recovery.js'):root.Recovery,S=node?require('./support.js'):root.BodyflipSupport,T=node?require('./torso.js'):root.BodyflipTorso;
const {add,sub,mul,dot,cross,length,unit,rotate,qm,qinv,qslerp}=R,skin=1e-6,clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
function create(names,parents,reference){
 const id=Object.fromEntries(names.map((n,i)=>[n,i])),spines=T.create(names,parents,reference);
 const links=['l','r'].flatMap(s=>[[`clavicle_${s}`,`upperarm_${s}`,.055],[`upperarm_${s}`,`lowerarm_${s}`,.058],[`lowerarm_${s}`,`hand_${s}`,.048],[`thigh_${s}`,`calf_${s}`,.083],[`calf_${s}`,`foot_${s}`,.062]]);
 function shapes(p,excluded=[]){
  const out=[],axis=(i,k)=>p.axes?.[i]?.[k]||R.toAxes(p.q[i])[k],box=(name,center,axes,dims)=>out.push({name,center,axes,half:mul(dims,.5)}),capsule=(name,a,b,radius)=>out.push({name,a,b,radius});
  box('pelvis',mul(add(p.points[id.thigh_l],p.points[id.thigh_r]),.5),[axis(id.pelvis,1),axis(id.pelvis,2),axis(id.pelvis,0)],[.170,.280,.130]);
  for(const s of spines){const w=T.world(p,s);box(s.name,w.center,[w.forward,w.side,w.up],w.dims);}
  for(const [a,b,r] of links)capsule(a,p.points[id[a]],p.points[id[b]],r);
  const neck=id.neck_01,head=id.head,lower=p.points[id.neck_02],up=axis(head,0),height=Math.max(.054,length(sub(p.points[head],lower)));
  box('neck',mul(add(p.points[neck],lower),.5),[mul(axis(neck,1),-1),axis(neck,2),axis(neck,0)],[.105,.105,.105]);
  capsule('head',lower,add(lower,mul(up,height)),.1);
  for(const side of ['l','r']){
   const h=id['hand_'+side],f=mul(axis(h,0),side==='l'?1:-1),n=axis(h,1);
   box('hand_'+side,add(add(p.points[h],mul(f,.0725)),mul(n,-.0025)),[f,axis(h,2),n],[.145,.090,.045]);
   const ankle=id['foot_'+side],toe=id['ball_'+side],s=S.footFrame(p,ankle,toe,side.toUpperCase());
   box('foot_'+side,add(add(p.points[toe],mul(s.forward,-.0875)),mul(s.up,-.006)),[s.forward,s.side,s.up],[.175,.120,.051]);
   box('ball_'+side,add(add(p.points[toe],mul(s.toeForward,.024)),mul(s.toeUp,-.006)),[s.toeForward,s.toeSide,s.toeUp],[.048,.120,.049]);
  }
  return excluded.length?out.filter(s=>!excluded.includes(s.name)):out;
 }
 const contacts=(pose,surfaces,bones)=>shapes(pose).filter(s=>bones.includes(s.name)).flatMap(s=>surfaces.map(surface=>query(s,surface)));
 return {shapes,contacts,move:(a,b,surfaces,excluded=[])=>move(shapes(a,excluded),shapes(b,excluded),b.points[0],surfaces),resolve:(p,surfaces,excluded=[])=>move(shapes(p,excluded),shapes(p,excluded),p.points[0],surfaces)};
}
const translated=(s,d)=>s.radius?{...s,a:add(s.a,d),b:add(s.b,d)}:{...s,center:add(s.center,d)};
function query(s,surface){
 const b=surface.box,axes=[b.forward,b.side,b.up],half=mul(b.dims,.5);
 if(!s.radius){
  const delta=sub(s.center,b.center),test=[...axes,...s.axes,...axes.flatMap(a=>s.axes.map(v=>cross(a,v)))];let gap=-Infinity,normal;
  for(const v of test){const size=length(v);if(size<1e-9)continue;const n=mul(v,1/size),x=dot(delta,n),d=Math.abs(x)-axes.reduce((a,v,i)=>a+Math.abs(dot(v,n))*half[i],0)-s.axes.reduce((a,v,i)=>a+Math.abs(dot(v,n))*s.half[i],0);if(d>gap){gap=d;normal=mul(n,x<0?-1:1);}}
  return {gap,normal,surface,bone:s.name};
 }
 const local=p=>axes.map(v=>dot(sub(p,b.center),v)),a=local(s.a),z=local(s.b),d=sub(z,a),cuts=[0,1];
 for(let k=0;k<3;k++)if(Math.abs(d[k])>1e-12)for(const sign of [-1,1]){const t=(sign*half[k]-a[k])/d[k];if(t>0&&t<1)cuts.push(t);}
 cuts.sort((a,b)=>a-b);let best=Infinity,pa,pb;
 const visit=t=>{const p=add(a,mul(d,t)),q=p.map((v,k)=>clamp(v,-half[k],half[k])),distance=dot(sub(p,q),sub(p,q));if(distance<best){best=distance;pa=p;pb=q;}};
 for(let i=0;i<cuts.length-1;i++){const lo=cuts[i],hi=cuts[i+1],mid=(lo+hi)/2;let num=0,den=0;for(let k=0;k<3;k++){const v=a[k]+d[k]*mid;if(Math.abs(v)>half[k]){num+=d[k]*(a[k]-Math.sign(v)*half[k]);den+=d[k]*d[k];}}visit(lo);visit(hi);if(den>0)visit(clamp(-num/den,lo,hi));}
 let distance=Math.sqrt(best),normal;
 if(distance>1e-10)normal=axes.reduce((v,n,k)=>add(v,mul(n,(pa[k]-pb[k])/distance)),[0,0,0]);
 else {const center=mul(add(a,z),.5),extent=mul(d.map(Math.abs),.5),overlap=half.map((h,k)=>h+s.radius+extent[k]-Math.abs(center[k])),k=overlap.indexOf(Math.min(...overlap));normal=mul(axes[k],center[k]<0?-1:1);distance=s.radius-overlap[k];}
 return {gap:distance-s.radius,normal,surface,bone:s.name};
}
function interpolate(a,b,t){
 if(a.radius)return {...a,a:add(a.a,mul(sub(b.a,a.a),t)),b:add(a.b,mul(sub(b.b,a.b),t))};
 // Box frames may have opposite handedness; reconstruct the third axis from
 // the first two before interpolation. A box is unchanged by an axis sign.
 const rotation=s=>R.fromAxes([s.axes[0],s.axes[1],cross(s.axes[0],s.axes[1])]);
 return {...a,center:add(a.center,mul(sub(b.center,a.center),t)),axes:R.toAxes(qslerp(rotation(a),rotation(b),t))};
}
function motionBound(a,b){if(a.radius)return Math.max(length(sub(a.a,b.a)),length(sub(a.b,b.b)));const qa=R.fromAxes([a.axes[0],a.axes[1],cross(a.axes[0],a.axes[1])]),qb=R.fromAxes([b.axes[0],b.axes[1],cross(b.axes[0],b.axes[1])]);return length(sub(a.center,b.center))+length(a.half)*length(R.qlog(qm(qb,qinv(qa))));}
function bounds(s){const center=s.radius?mul(add(s.a,s.b),.5):s.center,extent=s.radius?add(mul(sub(s.b,s.a).map(Math.abs),.5),[s.radius,s.radius,s.radius]):[0,1,2].map(k=>s.axes.reduce((v,a,i)=>v+Math.abs(a[k])*s.half[i],0));return {center,extent};}
const supportMin=(s,n)=>s.radius?Math.min(dot(s.a,n),dot(s.b,n))-s.radius:dot(s.center,n)-s.axes.reduce((v,a,i)=>v+Math.abs(dot(a,n))*s.half[i],0);
function nearby(a,b,surface,bound){const box=surface.box,axes=[box.forward,box.side,box.up],extent=[0,1,2].map(k=>axes.reduce((v,n,i)=>v+Math.abs(n[k])*box.dims[i]/2,0)),x=bounds(a),y=bounds(b);return [0,1,2].every(k=>Math.max(x.center[k]+x.extent[k],y.center[k]+y.extent[k])+bound+skin>=box.center[k]-extent[k]&&Math.min(x.center[k]-x.extent[k],y.center[k]-y.extent[k])-bound-skin<=box.center[k]+extent[k]);}
function move(before,after,root,surfaces){
 let correction=[0,0,0];const contacts=[];
 for(let j=0;j<after.length;j++){
  const a=before[j],b=after[j],bound=motionBound(a,b);if(bound<1e-12)continue;
  for(const surface of surfaces){if(!nearby(a,b,surface,bound))continue;let t=0;
   for(let i=0;i<48&&t<=1;i++){
    const q=query(interpolate(a,b,t),surface);
    if(q.gap<=skin*2){const next=query(interpolate(a,b,Math.min(1,t+1e-4)),surface);if(next.gap<q.gap-1e-9||q.gap<-skin){contacts.push({...q,fraction:t});
      // Stop a crossing even through a thin slab. Several body volumes touching
      // one plane impose the same bound; do not add their corrections together.
      const required=supportMin(interpolate(a,b,t),q.normal)-supportMin(b,q.normal);
      correction=add(correction,mul(q.normal,Math.max(0,required-dot(correction,q.normal))));
     }break;}
    t+=(q.gap-skin)/bound;
   }
  }
 }
 for(let pass=0;pass<8;pass++){
  let deepest=null;for(const shape of after)for(const surface of surfaces){const s=translated(shape,correction);if(!nearby(s,s,surface,0))continue;const q=query(s,surface);if(q.gap<-skin&&(!deepest||q.gap<deepest.gap))deepest=q;}
  if(!deepest)break;correction=add(correction,mul(deepest.normal,-deepest.gap+skin));contacts.push({...deepest,fraction:1});
 }
 return {root:add(root,correction),contacts};
}
const api={create,query,move};if(node)module.exports=api;else root.BodyflipBodyContact=api;
})(globalThis);
