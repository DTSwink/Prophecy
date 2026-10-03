/* Parent-local FK recovery. Stateless sampling; no per-frame history or IK. */
(function(root){
'use strict';
const add=(a,b)=>a.map((v,i)=>v+b[i]), sub=(a,b)=>a.map((v,i)=>v-b[i]);
const mul=(a,s)=>a.map(v=>v*s), dot=(a,b)=>a.reduce((s,v,i)=>s+v*b[i],0);
const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
const length=a=>Math.hypot(...a), unit=a=>mul(a,1/(length(a)||1));
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const ident=[0,0,0,1];
const qinv=q=>[-q[0],-q[1],-q[2],q[3]];
function qm(a,b){return [a[3]*b[0]+a[0]*b[3]+a[1]*b[2]-a[2]*b[1],a[3]*b[1]-a[0]*b[2]+a[1]*b[3]+a[2]*b[0],a[3]*b[2]+a[0]*b[1]-a[1]*b[0]+a[2]*b[3],a[3]*b[3]-dot(a.slice(0,3),b.slice(0,3))];}
function rotate(q,v){const t=mul(cross(q,v),2);return add(v,add(mul(t,q[3]),cross(q,t)));}
function qlog(q){if(q[3]<0)q=mul(q,-1);const n=length(q.slice(0,3));return n<1e-10?mul(q.slice(0,3),2):mul(q.slice(0,3),2*Math.atan2(n,q[3])/n);}
function qexp(v){const n=length(v);return n<1e-10?unit([...mul(v,.5),1]):[...mul(v,Math.sin(n*.5)/n),Math.cos(n*.5)];}
function qslerp(a,b,t){let c=dot(a,b);if(c<0){b=mul(b,-1);c=-c;}if(c>.9995)return unit(add(mul(a,1-t),mul(b,t)));const theta=Math.acos(clamp(c,-1,1)),s=Math.sin(theta);return add(mul(a,Math.sin((1-t)*theta)/s),mul(b,Math.sin(t*theta)/s));}
function fromTo(a,b){a=unit(a);b=unit(b);const c=dot(a,b);if(c<-.999999){let axis=cross(a,[1,0,0]);if(length(axis)<1e-5)axis=cross(a,[0,1,0]);return [...unit(axis),0];}return unit([...cross(a,b),1+c]);}
// Harness matrices store three world-space basis vectors consecutively.
function fromAxes(a){const m00=a[0][0],m01=a[1][0],m02=a[2][0],m10=a[0][1],m11=a[1][1],m12=a[2][1],m20=a[0][2],m21=a[1][2],m22=a[2][2];let q,s;const trace=m00+m11+m22;
 if(trace>0){s=Math.sqrt(trace+1)*2;q=[(m21-m12)/s,(m02-m20)/s,(m10-m01)/s,s/4];}
 else if(m00>m11&&m00>m22){s=Math.sqrt(1+m00-m11-m22)*2;q=[s/4,(m01+m10)/s,(m02+m20)/s,(m21-m12)/s];}
 else if(m11>m22){s=Math.sqrt(1+m11-m00-m22)*2;q=[(m01+m10)/s,s/4,(m12+m21)/s,(m02-m20)/s];}
 else{s=Math.sqrt(1+m22-m00-m11)*2;q=[(m02+m20)/s,(m12+m21)/s,s/4,(m10-m01)/s];}return unit(q);}
const toAxes=q=>[[1,0,0],[0,1,0],[0,0,1]].map(v=>rotate(q,v));
function localize(points,rotations,parents){return {q:rotations.map((q,j)=>parents[j]<0?q:unit(qm(qinv(rotations[parents[j]]),q))),p:points.map((p,j)=>parents[j]<0?p:rotate(qinv(rotations[parents[j]]),sub(p,points[parents[j]])))};}
function fk(local,parents){const points=[],q=[];for(let j=0;j<parents.length;j++){const p=parents[j];q[j]=p<0?local.q[j]:unit(qm(q[p],local.q[j]));points[j]=p<0?local.p[j]:add(points[p],rotate(q[p],local.p[j]));}return {points,q,axes:q.map(toAxes)};}
const ease=x=>x*x*x*(10+x*(-15+6*x));
function offsetBlend(a,b,t){const la=length(a),lb=length(b);if(la<1e-9||lb<1e-9)return add(mul(a,1-t),mul(b,t));return mul(rotate(qslerp(ident,fromTo(a,b),t),unit(a)),la+(lb-la)*t);}
function prepare(meta,buffer,clip,names,parents){
 const count=meta.frames*names.length,values=new Float32Array(buffer),positionCount=count*3;
 if(values.length!==count*12)throw Error('Invalid motion buffer length');
 for(const x of values)if(!Number.isFinite(x))throw Error('Non-finite source motion');
 const poses=[],locals=[];
 for(let f=0;f<meta.frames;f++){const points=[],axes=[];for(let j=0;j<names.length;j++){const i=f*names.length+j;points.push(Array.from(values.subarray(i*3,i*3+3)));axes.push([0,1,2].map(k=>Array.from(values.subarray(positionCount+i*9+k*3,positionCount+i*9+k*3+3))));}const q=axes.map(fromAxes);poses.push({points,axes,q});locals.push(localize(points,q,parents));}
 const idle=localize(clip.idle.points,clip.idle.axes.map(fromAxes),parents);
 const spine=names.indexOf('spine_01'),upper=parents.map((_,j)=>{let i=j;while(i>=0){if(i===spine)return true;i=parents[i];}return false;});
 const last=locals.at(-1),prev=locals.at(-2)||last;
 const velocity=last.q.map((q,j)=>mul(qlog(qm(qinv(prev.q[j]),q)),meta.fps));
 const offsetVelocity=last.p.map((p,j)=>length(p)>1e-8&&length(prev.p[j])>1e-8?mul(qlog(fromTo(prev.p[j],p)),meta.fps):[0,0,0]);
 // Lengths are fixed throughout recovery, even if source idle has tiny solver roundoff.
 const idleOffsets=idle.p.map((p,j)=>length(p)>1e-8?mul(unit(p),length(last.p[j])):last.p[j]);
 const idlePose=fk({q:last.q.map((q,j)=>upper[j]?idle.q[j]:q),p:last.p.map((p,j)=>upper[j]?idleOffsets[j]:p)},parents);
 const inertial=upper.map((enabled,j)=>enabled&&names[j]!=='hand_l'&&names[j]!=='hand_r');
 return {meta,clip,names,parents,poses,locals,idle,idleOffsets,idlePose,spine,upper,inertial,velocity,offsetVelocity,attackSeconds:(meta.frames-1)/meta.fps};
}
function sample(model,seconds,options={}){
 const {meta,parents,poses,locals}=model;const t=clamp(seconds,0,1e5),tail=model.attackSeconds;
 // Match Final Harness authored playback: global position lerp and global
 // orientation slerp. Separate parent/child arcs can add a spurious full turn.
 if(t<=tail){const f=t*meta.fps,i=Math.min(meta.frames-1,Math.floor(f+1e-10)),n=Math.min(meta.frames-1,i+1),u=clamp(f-i,0,1);if(u<1e-8||i===n)return poses[i];const q=poses[i].q.map((q,j)=>qslerp(q,poses[n].q[j],u));return {q,axes:q.map(toAxes),points:poses[i].points.map((p,j)=>add(p,mul(sub(poses[n].points[j],p),u)))};}
 if(options.enabled===false)return poses.at(-1);
 const duration=clamp(Number(options.duration)||1,.1,5),elapsed=t-tail,x=clamp(elapsed/duration,0,1),blend=ease(x),inertia=clamp(Number(options.inertia)||0,0,1);
 if(elapsed>=duration-1e-12)return model.idlePose;
 // Compact analytic angular momentum: outgoing velocity at t=0; exact zero
 // position and derivative at duration. Inertia controls decay, not FK length.
 const momentum=(x<1&&inertia>0)?elapsed*Math.pow(1-x,3)*Math.exp(-elapsed/(duration*(.025+.45*inertia))):0;
 const last=locals.at(-1),q=last.q.slice(),p=last.p.slice();
 for(let j=0;j<parents.length;j++){if(!model.upper[j])continue;
   q[j]=qslerp(last.q[j],model.idle.q[j],blend);
   p[j]=offsetBlend(last.p[j],model.idleOffsets[j],blend);
   if(momentum>0&&model.inertial[j]){q[j]=unit(qm(q[j],qexp(mul(model.velocity[j],momentum))));p[j]=rotate(qexp(mul(model.offsetVelocity[j],momentum)),p[j]);}
 }
 return fk({q,p},parents);
}
function anchor(model,pose,target){const shift=sub(model.poses[0].points[model.spine],pose.points[model.spine]);return {...pose,points:pose.points.map(p=>add(p,shift)),target:add(target,shift)};}
const api={prepare,sample,anchor,fk,localize,fromAxes,toAxes,qm,qinv,qlog,qexp,rotate,qslerp,fromTo,offsetBlend,add,sub,mul,dot,cross,length,unit};
if(typeof module!=='undefined')module.exports=api;else root.Recovery=api;
})(globalThis);
