/* Shared anatomical constraint frames and legal target reconstruction. */
(function(root){
'use strict';
const node=typeof module!=='undefined',R=node?require('./recovery.js'):root.Recovery,W=node?require('./wrist.js'):root.BodyflipWrist;
const {add,sub,mul,dot,cross,length,unit,rotate,qm,qinv,qlog,qexp}=R,rad=Math.PI/180,basis=qexp([-Math.PI/2,0,0]),cache=new WeakMap(),profiles=new WeakMap(),P=node?require('./rig-profile.js'):root.BodyflipRigProfile;
function create(names,parents,reference){
 const profile=P?.current()||null;let existing=cache.get(reference);if(existing&&profiles.get(reference)===profile)return existing;profiles.set(reference,profile);
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
 if(profile){
  joints.length=0;
  for(const c of profile.joints){
   const i=c.i,parent=c.parent,child=parents.findIndex(p=>p===i),hinge=c.angles[0]===0&&c.angles[1]===0&&c.angles[2]>0;
   const bind=qm(c.parentFrame.q,qinv(c.childFrame.q)),axisLocal=rotate(c.parentFrame.q,[0,0,1]),u=unit(sub(reference.points[i],reference.points[parent]));
   joints.push({...c,native:true,hinge,child,bind,axisLocal,axis:rotate(reference.q[parent],axisLocal),normal:u,min:-c.angles[2],max:c.angles[2],basis:c.childFrame.q,parentBasis:c.parentFrame.q,
    limits:{plane:c.angles[1],normal:c.angles[2],twistMin:-c.angles[0],twistMax:c.angles[0]}});
   rest.p[i]=sub(c.parentFrame.p,rotate(qm(qinv(reference.q[parent]),reference.q[i]),c.childFrame.p));
  }
 }
 const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
 function coordinates(q,c){if(c.hinge){const d=qm(q,qinv(c.bind)),s=d[3]<0?-1:1;return [2*Math.atan2(dot(d.slice(0,3),c.axisLocal)*s,d[3]*s)];}const d=W.decompose(qm(qm(qinv(c.parentBasis),q),c.basis));return [d.swing[1],d.swing[2],d.angle];}
 function fromCoordinates(v,c,prepared=null){
  if(c.hinge)return qm(qexp(mul(c.axisLocal,clamp(v[0],c.min,c.max))),c.bind);
  let [y,z,angle]=v;const a=prepared?prepared.a:Math.sin(c.limits.plane/2),b=prepared?prepared.b:Math.sin(c.limits.normal/2);
  if(a===0)y=0;if(b===0)z=0;
  if(a===0||b===0){y=clamp(y,-a,a);z=clamp(z,-b,b);}else if((y/a)**2+(z/b)**2>1){const aa=a*a,bb=b*b;let lo=0,hi=Math.max(a*Math.abs(y),b*Math.abs(z));const f=t=>(a*y/(t+aa))**2+(b*z/(t+bb))**2;while(f(hi)>1)hi*=2;for(let k=0;k<40;k++){const t=(lo+hi)/2;if(f(t)>1)lo=t;else hi=t;}y=aa*y/(hi+aa);z=bb*z/(hi+bb);}
  return qm(qm(c.parentBasis,W.compose([0,y,z,Math.sqrt(Math.max(0,1-y*y-z*z))],prepared?prepared.twist:qexp([clamp(angle,c.limits.twistMin,c.limits.twistMax),0,0]))),prepared?prepared.inverse:qinv(c.basis));
 }
 function swingSweep(v,c,k){
  if(c.hinge||(k!==0&&k!==1))throw Error('A swing sweep needs one swing coordinate');
  // Palm fitting changes one swing coordinate while twist and joint frames
  // stay fixed. Retain the exact limit projection and quaternion operations,
  // including normalization, but compute their invariant inputs only once.
  const point=v.slice(),prepared={a:Math.sin(c.limits.plane/2),b:Math.sin(c.limits.normal/2),twist:qexp([clamp(v[2],c.limits.twistMin,c.limits.twistMax),0,0]),inverse:qinv(c.basis)};
  return x=>{point[k]=x;return fromCoordinates(point,c,prepared);};
 }
 function clampLocal(q,c){
  if(c.native)return fromCoordinates(coordinates(q,c),c);
  if(c.hinge){const delta=qm(q,qinv(c.bind)),twist=dot(delta.slice(0,3),c.axisLocal),sign=delta[3]<0?-1:1,angle=2*Math.atan2(twist*sign,delta[3]*sign);return qm(qexp(mul(c.axisLocal,clamp(angle,c.min,c.max))),c.bind);}
  const constraint=qm(qm(qinv(c.parentBasis),q),basis),d=W.decompose(constraint),a=Math.sin(c.limits.plane/2),b=Math.sin(c.limits.normal/2);let y=d.swing[1],z=d.swing[2];
  if((y/a)**2+(z/b)**2>1){const aa=a*a,bb=b*b;let lo=0,hi=Math.max(a*Math.abs(y),b*Math.abs(z));const value=t=>(a*y/(t+aa))**2+(b*z/(t+bb))**2;while(value(hi)>1)hi*=2;for(let i=0;i<32;i++){const mid=(lo+hi)/2;if(value(mid)>1)lo=mid;else hi=mid;}y=aa*y/(hi+aa);z=bb*z/(hi+bb);}
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
  // One FK pass enforces both native connector positions. Nonphysical toes
  // retain their animated local transform under their physical foot parent.
  if(profile)for(const c of joints)local.p[c.i]=sub(c.parentFrame.p,rotate(local.q[c.i],c.childFrame.p));
  return R.fk(local,parents);
 }
 function inspect(pose){const local=R.localize(pose.points,pose.q,parents);return joints.map(c=>({name:c.name,angularError:length(qlog(qm(clampLocal(local.q[c.i],c),qinv(local.q[c.i])))),anchorError:c.native?length(sub(add(pose.points[c.parent],rotate(pose.q[c.parent],c.parentFrame.p)),add(pose.points[c.i],rotate(pose.q[c.i],c.childFrame.p)))):length(sub(local.p[c.i],rest.p[c.i]))}));}
 existing={joints,project,inspect,clampLocal,rest,coordinates,fromCoordinates,swingSweep};cache.set(reference,existing);return existing;
}
const api={create};if(node)module.exports=api;else root.BodyflipJointRig=api;
})(globalThis);
