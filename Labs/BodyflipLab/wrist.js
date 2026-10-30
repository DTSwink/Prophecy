/* Wrist limits shared by Jolt and procedural hand support.
 * Jolt constraint basis: [twist, plane x twist, plane] = [hand X, -Z, Y]. */
(function(root){
'use strict';
const R=typeof module!=='undefined'?require('./recovery.js'):root.Recovery;
const {add,sub,mul,dot,cross,length,rotate,qm,qinv,qexp}=R,clip=(x,a,b)=>Math.max(a,Math.min(b,x)),identity=[0,0,0,1],rad=Math.PI/180;
const limits=Object.freeze({normal:45*rad,plane:40*rad,twistMin:-55*rad,twistMax:55*rad});
const basis=qexp([-Math.PI/2,0,0]),basisInverse=qinv(basis),a=Math.sin(limits.plane/2),b=Math.sin(limits.normal/2);
function normalized(q){const n=length(q);return n>1e-12?mul(q,1/n):identity.slice();}
function positive(q){return q[3]<0?mul(q,-1):q;}
function decompose(q){
 q=normalized(q);const n=Math.hypot(q[0],q[3]),twist=positive(n>1e-12?[q[0]/n,0,0,q[3]/n]:identity.slice()),raw=positive(qm(q,qinv(twist)));
 const swing=normalized([0,raw[1],raw[2],raw[3]]);
 return {swing,twist,angle:2*Math.atan2(twist[0],twist[3])};
}
function compose(swing,twist){return normalized(qm(swing,twist));}
function clampConstraint(q){
 const d=decompose(q);let y=d.swing[1],z=d.swing[2];
 // Closest point on Jolt's quaternion-space ellipse, not radial scaling or
 // independently clamped Euler angles. The multiplier equation is monotonic.
 if((y/a)**2+(z/b)**2>1){
  const aa=a*a,bb=b*b;let lo=0,hi=Math.max(a*Math.abs(y),b*Math.abs(z));
  const value=t=>(a*y/(t+aa))**2+(b*z/(t+bb))**2;
  while(value(hi)>1)hi*=2;
  for(let i=0;i<48;i++){const mid=(lo+hi)/2;if(value(mid)>1)lo=mid;else hi=mid;}
  y=aa*y/(hi+aa);z=bb*z/(hi+bb);
 }
 const angle=clip(d.angle,limits.twistMin,limits.twistMax);
 return compose([0,y,z,Math.sqrt(Math.max(0,1-y*y-z*z))],qexp([angle,0,0]));
}
function inspectConstraint(q){
 const d=decompose(q),ellipse=(d.swing[1]/a)**2+(d.swing[2]/b)**2;
 return {...d,ellipse,within:ellipse<=1+1e-9&&d.angle>=limits.twistMin-1e-9&&d.angle<=limits.twistMax+1e-9};
}
function create(reference,parent,hand,side='L'){
 const rest=qm(qinv(reference.q[parent]),reference.q[hand]),constraintToParent=qm(rest,basis),palmSign=side==='R'?-1:1;
 const frame=parentQ=>qm(parentQ,constraintToParent);
 const toConstraint=(parentQ,handQ)=>normalized(qm(qinv(frame(parentQ)),qm(handQ,basis)));
 const fromConstraint=(parentQ,q)=>normalized(qm(qm(frame(parentQ),q),basisInverse));
 const clamp=(parentQ,handQ)=>fromConstraint(parentQ,clampConstraint(toConstraint(parentQ,handQ)));
 function aim(parentQ,incomingHandQ,normal,weight=1){
  const source=clampConstraint(toConstraint(parentQ,incomingHandQ)),d=decompose(source),start=d.swing[1],z=d.swing[2],end=a*Math.sqrt(Math.max(0,1-(z/b)**2));
  if(length(normal)<1e-12||weight<=0)return fromConstraint(parentQ,source);
  const target=rotate(qinv(frame(parentQ)),mul(normal,-1/length(normal))),v=rotate(d.twist,rotate(basisInverse,[0,palmSign,0])),vv=dot(v,target);
  // Expanded quaternion rotation: scalar arithmetic keeps this cheap inside
  // the support planner's contact/height solves (v.x is zero in this basis).
  const A=2*target[0]*v[2],B=-2*target[0]*v[1]*z,D=2*target[1]*v[1]-2*vv,E=2*z*(target[1]*v[2]+target[2]*v[1]),F=vv+2*z*z*(target[2]*v[2]-vv),c=1-z*z;
  const evaluate=y=>(A*y+B)*Math.sqrt(Math.max(0,c-y*y))+D*y*y+E*y+F;
  // Backward extension is +constraint Y on both mirrored hands. Keeping this
  // interval fixed avoids an arbitrary opposite pitch branch at an inverted
  // palm. Test both endpoints explicitly: the exactly opposed palm must try
  // the allowed extension instead of stalling at a zero derivative.
  let lo=start,hi=end,best=start,score=evaluate(start);const ratio=(Math.sqrt(5)-1)/2;
  const consider=y=>{const s=evaluate(y);if(s>score+1e-14){score=s;best=y;}};
  consider(end);let x=hi-(hi-lo)*ratio,y=lo+(hi-lo)*ratio,sx=evaluate(x),sy=evaluate(y);
  for(let i=0;i<20;i++){
   if(sx<sy){lo=x;x=y;sx=sy;y=lo+(hi-lo)*ratio;sy=evaluate(y);}
   else{hi=y;y=x;sy=sx;x=hi-(hi-lo)*ratio;sx=evaluate(x);}
  }
  consider((lo+hi)/2);y=start+(best-start)*clip(weight,0,1);
  return fromConstraint(parentQ,compose([0,y,z,Math.sqrt(Math.max(0,1-y*y-z*z))],d.twist));
 }
 return {parent,hand,side,rest,constraintToParent,toConstraint,fromConstraint,clamp,aim,inspect:(parentQ,handQ)=>inspectConstraint(toConstraint(parentQ,handQ))};
}
const api={limits,basis,create,decompose,compose,clampConstraint,inspectConstraint};
if(typeof module!=='undefined')module.exports=api;else root.BodyflipWrist=api;
})(globalThis);
