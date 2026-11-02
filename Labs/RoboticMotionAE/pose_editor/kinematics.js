import * as T from '../../MimicKitUEFN/vendor/three.module.js';
const V=a=>new T.Vector3().fromArray(a),Q=a=>new T.Quaternion().fromArray(a),wrap=a=>Math.atan2(Math.sin(a),Math.cos(a));
export function rotvec(a){const v=V(a),n=v.length();return n>1e-12?new T.Quaternion().setFromAxisAngle(v.multiplyScalar(1/n),n):new T.Quaternion()}
export function toRotvec(q){q=q.clone().normalize();if(q.w<0)q.set(-q.x,-q.y,-q.z,-q.w);const s=Math.hypot(q.x,q.y,q.z),a=2*Math.atan2(s,q.w);return s>1e-12?[q.x*a/s,q.y*a/s,q.z*a/s]:[0,0,0]}
export function fk(m,f){
 const p=[V(f.slice(0,3))],q=[rotvec(f.slice(3,6))];
 for(let i=1;i<m.names.length;i++){const j=m.joints[i-1],parent=m.parents[i];p[i]=V(m.local_p[i]).applyQuaternion(q[parent]).add(p[parent]);const delta=j.size===3?rotvec(f.slice(j.index,j.index+3)):new T.Quaternion().setFromAxisAngle(V(j.axis),f[j.index]);q[i]=q[parent].clone().multiply(Q(m.local_q[i])).multiply(delta).normalize()}
 return {p,q};
}
export function setWorldRotation(m,f,body,world,limit=false){
 if(body===0){f.splice(3,3,...toRotvec(world));return}
 const pose=fk(m,f),j=m.joints[body-1];let local=Q(m.local_q[body]).invert().multiply(pose.q[m.parents[body]].clone().invert()).multiply(world).normalize();
 if(j.size===1){let angle=wrap(2*Math.atan2(new T.Vector3(local.x,local.y,local.z).dot(V(j.axis)),local.w));if(limit)angle=T.MathUtils.clamp(angle,...j.limits.range_rad);f[j.index]=angle}
 else {if(limit)local=clampBall(local,j.limits);f.splice(j.index,3,...toRotvec(local))}
}
function clampBall(delta,meta){
 const ref=Q([meta.reference_wxyz[1],meta.reference_wxyz[2],meta.reference_wxyz[3],meta.reference_wxyz[0]]),q=ref.clone().multiply(delta),n=Math.hypot(q.w,q.x);
 let twist=wrap(2*Math.atan2(q.x,q.w)),y=(q.w*q.y-q.x*q.z)/Math.max(n,1e-9),z=(q.x*q.y+q.w*q.z)/Math.max(n,1e-9);
 const lim=meta.limits_rad;twist=T.MathUtils.clamp(twist,-lim[0],lim[0]);const mag=Math.hypot(y/Math.sin(lim[1]/2),z/Math.sin(lim[2]/2));if(mag>1){y/=mag;z/=mag}
 const s=Math.sqrt(Math.max(0,1-y*y-z*z)),c=Math.cos(twist/2),sn=Math.sin(twist/2);
 return ref.invert().multiply(new T.Quaternion(s*sn,y*c+z*sn,z*c-y*sn,s*c)).normalize();
}
export const chains=[[3,4,5],[6,7,8],[9,10,11],[12,13,14]];
export function solveIK(m,f,end,requested,poleTarget=null,limit=false,orientationTarget=null){
 const chain=chains.find(c=>c[2]===end);if(!chain)throw Error('No IK chain for this joint');
 const [upper,hinge,tip]=chain,pose=fk(m,f),origin=pose.p[upper],j=m.joints[hinge-1],u=V(m.local_p[hinge]),l=V(m.local_p[tip]),rest=Q(m.local_q[hinge]),axis=V(j.axis).normalize();
 const axial=axis.clone().multiplyScalar(axis.dot(l)),perp=l.clone().sub(axial);
 const c=u.lengthSq()+l.lengthSq()+2*u.dot(axial.clone().applyQuaternion(rest)),a=2*u.dot(perp.clone().applyQuaternion(rest)),b=2*u.dot(new T.Vector3().crossVectors(axis,l).applyQuaternion(rest));
 const radius=Math.hypot(a,b),phi=Math.atan2(b,a),target=requested.clone(),direction=target.clone().sub(origin);let distance=direction.length();
 if(distance<1e-8)direction.copy(pose.p[tip]).sub(origin).normalize();else direction.multiplyScalar(1/distance);
 const min=Math.sqrt(Math.max(0,c-radius))+1e-5,max=Math.sqrt(c+radius)-1e-5;distance=T.MathUtils.clamp(distance,min,max);target.copy(origin).addScaledVector(direction,distance);
 const alpha=Math.acos(T.MathUtils.clamp((distance*distance-c)/radius,-1,1)),current=f[j.index];let candidates=[phi+alpha,phi-alpha].map(x=>current+wrap(x-current));
 if(limit){const [lo,hi]=j.limits.range_rad;candidates=candidates.map(x=>T.MathUtils.clamp(x,lo,hi))}
 const angle=candidates.sort((a,b)=>Math.abs(a-current)-Math.abs(b-current))[0];
 let pole=(poleTarget?poleTarget.clone():pose.p[hinge].clone()).sub(origin);pole.addScaledVector(direction,-pole.dot(direction));
 if(pole.lengthSq()<1e-10)pole.crossVectors(direction,new T.Vector3(0,0,1));if(pole.lengthSq()<1e-10)pole.crossVectors(direction,new T.Vector3(0,1,0));pole.normalize();
 const hrot=rest.clone().multiply(new T.Quaternion().setFromAxisAngle(axis,angle)),total=u.clone().add(l.clone().applyQuaternion(hrot)),ld=total.clone().normalize(),lp=u.clone().addScaledVector(ld,-u.dot(ld)).normalize();
 const src=new T.Matrix4().makeBasis(ld,lp,new T.Vector3().crossVectors(ld,lp)),dst=new T.Matrix4().makeBasis(direction,pole,new T.Vector3().crossVectors(direction,pole));
 const upperQ=new T.Quaternion().setFromRotationMatrix(dst.multiply(src.transpose())).normalize(),handQ=(orientationTarget||pose.q[tip]).clone();
 setWorldRotation(m,f,upper,upperQ,limit);f[j.index]=angle;setWorldRotation(m,f,tip,handQ,limit);
 return fk(m,f).p[tip].distanceTo(requested);
}
export function rotatePelvisKeepingFeet(m,f,requested,limit=false){
 const original=f.slice(),before=fk(m,original),feet=chains.filter(c=>c[2]===11||c[2]===14);
 function attempt(alpha){
  const candidate=original.slice(),rotation=before.q[0].clone().slerp(requested,alpha);
  setWorldRotation(m,candidate,0,rotation);
  for(const [,knee,foot] of feet)solveIK(m,candidate,foot,before.p[foot],before.p[knee],limit,before.q[foot]);
  const after=fk(m,candidate);let positionError=0,rotationError=0;
  for(const [,,foot] of feet){positionError=Math.max(positionError,after.p[foot].distanceTo(before.p[foot]));rotationError=Math.max(rotationError,after.q[foot].angleTo(before.q[foot]))}
  return {candidate,valid:positionError<1e-7&&rotationError<1e-7,positionError,rotationError};
 }
 let result=attempt(1),fraction=1;
 if(!result.valid){
  // Stop the pelvis at the reachable boundary instead of dragging a foot.
  let low=0,high=1;result={candidate:original,positionError:0,rotationError:0};
  for(let i=0;i<24;i++){const mid=(low+high)/2,test=attempt(mid);if(test.valid){low=mid;result=test}else high=mid}
  fraction=low;
 }
 f.splice(0,f.length,...result.candidate);
 return {fraction,positionError:result.positionError,rotationError:result.rotationError};
}
