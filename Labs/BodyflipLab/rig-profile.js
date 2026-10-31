/* Optional native PHAT contract. An isolated native VM installs one immutable
 * profile before constructing a sequence. With no profile, lab behavior stays
 * unchanged. Native bone-local coordinates differ by a Y reflection. */
(function(root){
'use strict';
const R=typeof module!=='undefined'?require('./recovery.js'):root.Recovery;
const {add,sub,mul,rotate,qm,qinv}=R;let active=null;
const point=v=>[v[0]*.01,-v[1]*.01,v[2]*.01],rotation=q=>R.unit([-q[0],q[1],-q[2],q[3]]);
function install(source,names,parents){
 if(!source){active=null;return;}
 if(source.schema!=='bodyflip-native-rig-v1')throw Error('Unsupported Bodyflip rig profile');
 const frame=f=>({p:point(f.position_cm),q:rotation(f.rotation_xyzw)}),bodies=source.bodies.map(b=>{
  const i=names.indexOf(b.name);if(i<1)throw Error('Native physical bone absent: '+b.name);
  if(!(b.mass_kg>0)||b.jolt_inertia_kg_cm2.some(v=>!(v>0)))throw Error('Invalid native mass: '+b.name);
  const shapes=b.shapes.filter(s=>s.simulated!==false).map(s=>{
   if(!['box','capsule','sphere'].includes(s.kind))throw Error('Unsupported native collider: '+s.kind);
   const f=frame(s.local),shape={name:b.name,i,shape:s.kind,offset:f.p,rotation:f.q,half:s.half_extent_cm?.map(v=>v*.01),radius:s.radius_cm*.01,halfHeight:s.cylinder_length_cm*.005};
   if(b.name.startsWith('foot_')&&source.foot_front_trim_cm>0){if(s.kind!=='box'||!b.toe_direction)throw Error('Unsupported native foot trim');const d=rotate(qinv(f.q),point(b.toe_direction)),axis=d.map(Math.abs).indexOf(Math.max(...d.map(Math.abs))),trim=source.foot_front_trim_cm*.01;if(shape.half[axis]*2-trim<.001)throw Error('Invalid native foot trim');const shift=[0,0,0];shift[axis]=-Math.sign(d[axis])*trim/2;shape.half[axis]-=trim/2;shape.offset=add(shape.offset,rotate(shape.rotation,shift));}
   return shape;
  });
  if(!shapes.length)throw Error('No native physical shapes: '+b.name);
  return {native:true,name:b.name,i,mass:b.mass_kg,offset:point(b.mass_frame.position_cm),rotation:rotation(b.jolt_inertia_rotation_xyzw),inertia:b.jolt_inertia_kg_cm2.map(v=>v*.0001),shapes};
 });
 const byName=new Map(bodies.map(b=>[b.name,b])),joints=source.joints.map(j=>{
  const child=bodies[j.child],parent=bodies[j.parent];if(!child||!parent||parents[child.i]!==parent.i)throw Error('Unsupported native joint graph');
  if(j.linear_modes.some(m=>m!==2))throw Error('Native Bodyflip requires locked connector translation');
  const a=frame(j.parent_frame),b=frame(j.child_frame),modes=j.angular_modes_twist_swing2_swing1,limits=j.angular_limits_deg_twist_swing2_swing1.map((v,k)=>modes[k]===0?Math.PI:modes[k]===2?0:v*Math.PI/180);
  return {i:child.i,parent:parent.i,name:child.name,parentFrame:a,childFrame:b,modes,angles:limits};
 });
 if(joints.length!==bodies.length-1)throw Error('Native rig must be one articulated tree');
 bodies.mass=bodies.reduce((a,b)=>a+b.mass,0);active={source,bodies,byName,joints,jointByIndex:new Map(joints.map(j=>[j.i,j])),names,parents};
}
function shapes(p,bones=null){
 if(!active)return null;const wanted=bones?new Set(bones):null,out=[];
 for(const b of active.bodies){if(wanted&&!wanted.has(b.name))continue;for(const s of b.shapes){
  const q=p.q?.[b.i]||R.fromAxes(p.axes[b.i]),center=add(p.points[b.i],rotate(q,s.offset)),axes=R.toAxes(qm(q,s.rotation));
  if(s.shape==='box')out.push({name:s.name,center,axes,half:s.half});
  else {const d=mul(axes[2],s.shape==='sphere'?0:s.halfHeight);out.push({name:s.name,a:sub(center,d),b:add(center,d),radius:s.radius});}
 }}return out;
}
function points(p,bone,name){
 const b=active?.byName.get(name);if(!b)return null;
 const q=p.q?.[bone]||R.fromAxes(p.axes[bone]),out=[];
 for(const s of b.shapes){if(s.shape!=='box')throw Error('Support collider must be a native box: '+name);
  for(const x of [-1,1])for(const y of [-1,1])for(const z of [-1,1])out.push(rotate(q,add(s.offset,rotate(s.rotation,[x*s.half[0],y*s.half[1],z*s.half[2]]))));
 }return out;
}
const api={install,current:()=>active,shapes,points};if(typeof module!=='undefined')module.exports=api;else root.BodyflipRigProfile=api;
})(globalThis);
