// Same swing/twist projection as ProphecyReachWristLimits.h. UE XYZW frames.
(function(root){
const R=typeof module!=='undefined'?require('../SwordHolsterLab/recovery.js'):root.Recovery;
const {qm,qinv,unit,mul}=R,pi=Math.PI;
function project(q,modes,limits){
 const bound=modes.map((m,i)=>m===0?pi:m===2?0:Math.max(0,Math.min(180,limits[i]))*pi/180);
 if(bound.every(v=>v>=pi))return q;
 let t=unit([q[0],0,0,q[3]]);if(Math.hypot(...t)<1e-9)t=[0,0,0,1];
 let s=qm(q,qinv(t));if(s[3]<0)s=mul(s,-1);if(t[3]<0)t=mul(t,-1);
 const angle=2*Math.atan2(t[0],t[3]),a=Math.max(-bound[0],Math.min(bound[0],angle));
 if(Math.abs(angle)>bound[0])t=[Math.sin(a/2),0,0,Math.cos(a/2)];
 const ry=Math.sin(bound[1]/2),rz=Math.sin(bound[2]/2);let y=ry>0?s[1]:0,z=rz>0?s[2]:0;
 const radius=(ry>0?(y/ry)**2:0)+(rz>0?(z/rz)**2:0);if(radius>1){y/=Math.sqrt(radius);z/=Math.sqrt(radius);}
 if(y!==s[1]||z!==s[2])s=[0,y,z,Math.sqrt(Math.max(0,1-y*y-z*z))];
 return unit(qm(s,t));
}
function constrain(j,forearm,hand){const q1=qm(j.handFirst?hand:forearm,j.frame1),q2=qm(j.handFirst?forearm:hand,j.frame2),limited=project(unit(qm(qinv(q2),q1)),j.modes,j.limits);return unit(j.handFirst?qm(qm(q2,limited),qinv(j.frame1)):qm(qm(q1,qinv(limited)),qinv(j.frame2)));}
const api={project,constrain};if(typeof module!=='undefined')module.exports=api;else root.ReachWrist=api;
})(globalThis);

// Fit only forearm axial twist for a prescribed elbow/wrist direction.
// PHAT boundaries become polynomials (degree <=4) in tan(roll/2). Their
// real roots partition the exact feasible intervals; select the nearest one.
// An already-feasible twist takes the constant-cost fast path. No elbow search.
(function(root){
const R=typeof module!=='undefined'?require('../SwordHolsterLab/recovery.js'):root.Recovery,W=typeof module!=='undefined'?module.exports:root.ReachWrist,{qm,qinv,qexp,rotate,unit,fromTo,mul,dot}=R,pi=Math.PI;
const poly=(a,t)=>a.reduceRight((s,c)=>s*t+c,0),plus=(a,b,s=1)=>Array.from({length:Math.max(a.length,b.length)},(_,i)=>(a[i]||0)+s*(b[i]||0)),times=(a,b)=>{const c=Array(a.length+b.length-1).fill(0);a.forEach((x,i)=>b.forEach((y,j)=>c[i+j]+=x*y));return c;};
function roots(coeff){
 const scale=Math.max(...coeff.map(Math.abs));if(scale<1e-24)return [];
 const a=coeff.map(x=>x/scale);while(a.length>1&&Math.abs(a[a.length-1])<1e-13)a.pop();
 const n=a.length-1;if(n===0)return [];if(n===1)return [-a[0]/a[1]];
 const bound=1+Math.max(...a.slice(0,-1).map(x=>Math.abs(x/a[n]))),critical=roots(a.slice(1).map((x,i)=>x*(i+1))).filter(t=>Math.abs(t)<bound),breaks=[-bound,...critical,bound],out=[];
 for(const t of critical)if(Math.abs(poly(a,t))<1e-10)out.push(t);
 for(let i=1;i<breaks.length;i++){let lo=breaks[i-1],hi=breaks[i],f=poly(a,lo),g=poly(a,hi);if(f*g>=0)continue;for(let k=0;k<64;k++){const m=(lo+hi)/2,v=poly(a,m);if(f*v<=0){hi=m;g=v;}else{lo=m;f=v;}if(hi-lo<1e-11*(1+Math.abs(m)))break;}out.push((lo+hi)/2);}
 return out.sort((a,b)=>a-b).filter((t,i,a)=>i===0||Math.abs(t-a[i-1])>1e-8*(1+Math.abs(t)));
}
function relative(j,forearm,hand){const q1=qm(j.handFirst?hand:forearm,j.frame1),q2=qm(j.handFirst?forearm:hand,j.frame2);return unit(qm(qinv(q2),q1));}
function solve(j,desired,localLower,direction,prior=0){
 const neutral=j.handFirst?qm(qm(desired,j.frame1),qinv(j.frame2)):qm(qm(desired,j.frame2),qinv(j.frame1)),aligned=unit(qm(fromTo(rotate(neutral,localLower),direction),neutral));
 const a=relative(j,aligned,desired),b=relative(j,qm(qexp(mul(direction,pi)),aligned),desired),components=a.map((v,i)=>[v,b[i]]),[x,y,z,w]=components;
 const ref=Math.atan2(Math.sin(prior),Math.cos(prior)),valid=t=>{const c=Math.cos(t/2),s=Math.sin(t/2),q=a.map((v,i)=>v*c+b[i]*s),p=W.project(q,j.modes,j.limits);return 1-Math.abs(dot(q,p))<1e-12;};
 if(valid(ref))return {forearm:unit(qm(qexp(mul(direction,ref)),aligned)),roll:ref,feasible:true,intervalSolve:false};
 const bounds=j.modes.map((m,i)=>m===0?pi:m===2?0:Math.max(0,Math.min(180,j.limits[i]))*pi/180),cs=[];
 if(bounds[0]<pi)cs.push(plus(times(x,x).map(v=>v*Math.cos(bounds[0]/2)**2),times(w,w).map(v=>v*Math.sin(bounds[0]/2)**2),-1));
 const sy=plus(times(y,w),times(z,x),-1),sz=plus(times(z,w),times(y,x)),den=times(plus(times(x,x),times(w,w)),[1,0,1]);
 const ry=Math.sin(bounds[1]/2),rz=Math.sin(bounds[2]/2);
 // A locked swing contributes an equality; retain its roots as isolated choices.
 const equal=[];if(ry<1e-12)equal.push(sy);if(rz<1e-12)equal.push(sz);
 const ellipse=plus(plus(ry>1e-12?times(sy,sy).map(v=>v/(ry*ry)):[0],rz>1e-12?times(sz,sz).map(v=>v/(rz*rz)):[0]),den,-1);cs.push(ellipse);
 const cuts=[-pi,...cs.concat(equal).flatMap(p=>roots(p).map(t=>2*Math.atan(t))),pi].sort((a,b)=>a-b).filter((v,i,a)=>i===0||v-a[i-1]>1e-9);
 const wrap=t=>Math.atan2(Math.sin(t),Math.cos(t)),choices=[];
 for(let i=1;i<cuts.length;i++){const lo=cuts[i-1],hi=cuts[i];if(valid((lo+hi)/2))for(const r of [ref-2*pi,ref,ref+2*pi])choices.push(Math.max(lo,Math.min(hi,r)));}
 for(const t of cuts)if(valid(t))choices.push(t);
 let roll=ref;
 if(choices.length){roll=choices.reduce((best,t)=>Math.abs(wrap(t-ref))<Math.abs(wrap(best-ref))?t:best,choices[0]);}
 else {
  // No twist can satisfy this direction: choose the least violated boundary.
  // The actual hand remains projected into PHAT; no tolerance is widened.
  let best=Infinity;for(const t of [ref,0,...cuts]){const q=a.map((v,i)=>v*Math.cos(t/2)+b[i]*Math.sin(t/2)),p=W.project(q,j.modes,j.limits),e=1-Math.abs(dot(q,p));if(e<best-1e-12){best=e;roll=t;}}
 }
 const forearm=unit(qm(qexp(mul(direction,roll)),aligned));return {forearm,roll,feasible:choices.length>0,intervalSolve:true};
}
W.fitForearm=solve;
})(globalThis);
