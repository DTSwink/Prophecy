/* One rigid collider per spine bone. Shared by Jolt and the torso renderer. */
(function(root){
'use strict';
const R=typeof module!=='undefined'?require('./recovery.js'):root.Recovery;
const sizes=[[.210,.118],[.230,.125],[.245,.135],[.260,.143],[.270,.150]];
function create(names,parents,reference){
 return sizes.map(([width,depth],index)=>{
  const name='spine_0'+(index+1),bone=names.indexOf(name),child=names.indexOf(index===4?'neck_01':'spine_0'+(index+2));
  if(bone<0||child<0||parents[child]!==bone)throw Error('Missing spine chain: '+name);
  const inverse=R.qinv(reference.q[bone]),delta=R.rotate(inverse,R.sub(reference.points[child],reference.points[bone])),length=R.length(delta),up=R.unit(delta);
  // Fixed bone-local frame. Never infer rotation from the animated next joint.
  const side=R.unit(R.sub([0,0,1],R.mul(up,R.dot(up,[0,0,1])))),forward=R.unit(R.cross(side,up));
  return {name,bone,child,shape:'box',offset:R.mul(delta,.5),rotation:R.fromAxes([forward,side,up]),
   dims:[depth,width,Math.max(.01,length-.008)]};
 });
}
function world(pose,spec){
 const rotation=R.qm(pose.q[spec.bone],spec.rotation),center=R.add(pose.points[spec.bone],R.rotate(pose.q[spec.bone],spec.offset));
 const [forward,side,up]=R.toAxes(rotation);return {...spec,center,rotation,forward,side,up};
}
const api={create,world};if(typeof module!=='undefined')module.exports=api;else root.BodyflipTorso=api;
})(globalThis);
