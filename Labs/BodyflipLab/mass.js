/* The lab's physical mass distribution. Root is an anchor, never a rigid body. */
(function(root){
'use strict';
const node=typeof module!=='undefined',R=node?require('./recovery.js'):root.Recovery,T=node?require('./torso.js'):root.BodyflipTorso;
const {add,sub,mul,dot,length,unit,rotate,qm,qinv}=R,cache=new WeakMap(),profiles=new WeakMap(),P=node?require('./rig-profile.js'):root.BodyflipRigProfile;
function model(names,parents,reference){
 const profile=P?.current()||null;let rig=cache.get(reference);if(rig&&profiles.get(reference)===profile)return rig;
 profiles.set(reference,profile);if(profile){rig=profile.bodies;cache.set(reference,rig);return rig;}
 const torso=new Map(T.create(names,parents,reference).map(s=>[s.bone,s]));
 rig=names.slice(1).map((name,j)=>{
  const i=j+1,mass=name==='pelvis'?8:name.startsWith('thigh')?5:name.startsWith('spine')?2:1,box=torso.get(i);
  if(box){const [x,y,z]=box.dims;return {...box,i,mass,inertia:[mass*(y*y+z*z)/12,mass*(x*x+z*z)/12,mass*(x*x+y*y)/12]};}
  const child=parents.findIndex((p,k)=>p===i&&!names[k].startsWith('clavicle')&&!names[k].startsWith('thigh'));
  const delta=child>0?sub(reference.points[child],reference.points[i]):rotate(reference.q[i],[name==='head'?.12:.045,0,0]),l=length(delta);
  const radius=name==='pelvis'?.105:name==='head'?.09:name.startsWith('thigh')?.065:name.startsWith('calf')?.045:.032,halfHeight=Math.max(.006,l*.5-radius*.6);
  const cylinder=mass*(2*halfHeight)/(2*halfHeight+4*radius/3),sphere=mass-cylinder;
  const axial=cylinder*radius*radius/2+sphere*2*radius*radius/5;
  const transverse=cylinder*(3*radius*radius+4*halfHeight*halfHeight)/12+sphere*(2*radius*radius/5+halfHeight*halfHeight+3*halfHeight*radius/4);
  return {name,i,mass,shape:'capsule',radius,halfHeight,offset:rotate(qinv(reference.q[i]),mul(delta,.5)),rotation:R.fromTo([0,1,0],rotate(qinv(reference.q[i]),unit(delta))),inertia:[transverse,axial,transverse]};
 });
 rig.mass=rig.reduce((s,b)=>s+b.mass,0);cache.set(reference,rig);return rig;
}
function bodies(pose,rig){return rig.map(b=>({center:add(pose.points[b.i],rotate(pose.q[b.i],b.offset)),q:qm(pose.q[b.i],b.rotation)}));}
function center(pose,rig){let x=0,y=0,z=0;for(const b of rig){const p=pose.points[b.i],d=rotate(pose.q[b.i],b.offset),w=b.mass/rig.mass;x+=(p[0]+d[0])*w;y+=(p[1]+d[1])*w;z+=(p[2]+d[2])*w;}return [x,y,z];}
function tensor(pose,rig){
 // Compute each body centre once, retaining the original summation order.
 const centers=rig.map(b=>add(pose.points[b.i],rotate(pose.q[b.i],b.offset))),c=[0,0,0],I=Array.from({length:3},()=>[0,0,0]);
 for(let k=0;k<rig.length;k++){const p=centers[k],w=rig[k].mass/rig.mass;c[0]+=p[0]*w;c[1]+=p[1]*w;c[2]+=p[2]*w;}
 for(let k=0;k<rig.length;k++){
  const b=rig[k],p=centers[k],r=sub(p,c),axes=R.toAxes(qm(pose.q[b.i],b.rotation)),rr=dot(r,r);
  for(let i=0;i<3;i++)for(let j=0;j<3;j++)I[i][j]+=axes.reduce((s,a,k)=>s+a[i]*a[j]*b.inertia[k],0)+b.mass*((i===j?rr:0)-r[i]*r[j]);
 }
 return I;
}
const product=(I,v)=>I.map(row=>dot(row,v)),moment=(I,axis)=>dot(axis,product(I,axis));
function rotateAboutCOM(pose,q,rig){
 const c=center(pose,rig),points=pose.points.map((p,i)=>i===0?p.slice():add(c,rotate(q,sub(p,c)))),rotations=pose.q.map((v,i)=>i===0?v.slice():R.unit(qm(q,v)));
 return {...pose,points,q:rotations,axes:rotations.map(R.toAxes)};
}
const api={model,bodies,center,tensor,product,moment,rotateAboutCOM};if(node)module.exports=api;else root.BodyflipMass=api;
})(globalThis);
