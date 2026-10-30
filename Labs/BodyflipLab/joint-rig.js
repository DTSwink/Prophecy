/* Shared anatomical constraint frames and legal target reconstruction. */
(function(root){
'use strict';
const node=typeof module!=='undefined',R=node?require('./recovery.js'):root.Recovery,W=node?require('./wrist.js'):root.BodyflipWrist;
const {add,sub,mul,dot,cross,length,unit,rotate,qm,qinv,qlog,qexp}=R,rad=Math.PI/180,basis=qexp([-Math.PI/2,0,0]),cache=new WeakMap();
function create(names,parents,reference){
 let existing=cache.get(reference);if(existing)return existing;
 const rest=R.localize(reference.points,reference.q,parents),joints=[];
 for(let i=2;i<names.length;i++){
  const name=names[i],parent=parents[i],hinge=/^(calf|lowerarm)_/.test(name),child=parents.findIndex(p=>p===i),bind=qm(qinv(reference.q[parent]),reference.q[i]);
  if(hinge){
   const u=unit(sub(reference.points[i],reference.points[parent])),v=unit(sub(reference.points[child],reference.points[i]));let axis=unit(cross(u,v));if(length(axis)<.1)axis=rotate(reference.q[i],[0,0,1]);
   const bend=Math.acos(Math.max(-1,Math.min(1,dot(u,v)))),max=(name.startsWith('calf')?150:155)*rad;
   joints.push({i,parent,name,hinge,child,bind,axis,axisLocal:rotate(qinv(reference.q[parent]),axis),normal:unit(sub(u,mul(axis,dot(axis,u)))),min:-bend,max:max-bend,bend,u,frame:R.fromAxes([u,axis,unit(cross(u,axis))])});
  }else{
   const degrees=name.startsWith('spine')?[22,22,22]:name.startsWith('thigh')?[105,75,65]:name.startsWith('upperarm')?[130,110,100]:name.startsWith('clavicle')?[35,35,30]:name.startsWith('foot')?[40,28,25]:name.startsWith('ball')?[35,8,8]:[45,40,55];
   const [normal,plane,twist]=degrees.map(v=>v*rad),limits=name.startsWith('hand_')?W.limits:{normal,plane,twistMin:-twist,twistMax:twist};
   joints.push({i,parent,name,hinge:false,bind,basis,parentBasis:qm(bind,basis),limits});
  }
 }
 const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
 function clampLocal(q,c){
  if(c.hinge){const delta=qm(q,qinv(c.bind)),twist=dot(delta.slice(0,3),c.axisLocal),sign=delta[3]<0?-1:1,angle=2*Math.atan2(twist*sign,delta[3]*sign);return qm(qexp(mul(c.axisLocal,clamp(angle,c.min,c.max))),c.bind);}
  const constraint=qm(qm(qinv(c.parentBasis),q),basis),d=W.decompose(constraint),a=Math.sin(c.limits.plane/2),b=Math.sin(c.limits.normal/2);let y=d.swing[1],z=d.swing[2];
  if((y/a)**2+(z/b)**2>1){const aa=a*a,bb=b*b;let lo=0,hi=Math.max(a*Math.abs(y),b*Math.abs(z));for(let i=0;i<32;i++){const mid=(lo+hi)/2;if((a*y/(mid+aa))**2+(b*z/(mid+bb))**2>1)lo=mid;else hi=mid;}y=aa*y/(hi+aa);z=bb*z/(hi+bb);}
  return qm(qm(c.parentBasis,W.compose([0,y,z,Math.sqrt(Math.max(0,1-y*y-z*z))],qexp([clamp(d.angle,c.limits.twistMin,c.limits.twistMax),0,0]))),qinv(basis));
 }
 function project(pose){
  const q=pose.q.slice(),points=pose.points.slice();
  // Keep the authored hip/shoulder twist. Inferring a complete plane from
  // three almost-collinear points flips that plane when an elbow straightens.
  // Project only the hinge, then swing the socket to preserve endpoint aim.
  for(const c of joints.filter(c=>c.hinge)){
   const relative=qm(qinv(q[c.parent]),q[c.i]),legal=clampLocal(relative,c),chain=add(rest.p[c.i],rotate(legal,rest.p[c.child])),wanted=sub(points[c.child],points[c.parent]);
   const hip=qm(R.fromTo(rotate(q[c.parent],chain),wanted),q[c.parent]);q[c.parent]=hip;q[c.i]=qm(hip,legal);
  }
  const local=R.localize(points,q,parents);for(const c of joints){local.p[c.i]=rest.p[c.i];local.q[c.i]=clampLocal(local.q[c.i],c);}
  return R.fk(local,parents);
 }
 function inspect(pose){const local=R.localize(pose.points,pose.q,parents);return joints.map(c=>({name:c.name,angularError:length(qlog(qm(clampLocal(local.q[c.i],c),qinv(local.q[c.i])))),anchorError:length(sub(local.p[c.i],rest.p[c.i]))}));}
 existing={joints,project,inspect,clampLocal,rest};cache.set(reference,existing);return existing;
}
const api={create};if(node)module.exports=api;else root.BodyflipJointRig=api;
})(globalThis);
