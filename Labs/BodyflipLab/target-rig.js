/* One constrained target for kinematic display and dynamic angular tracking. */
(function(root){
'use strict';
const node=typeof module!=='undefined',R=node?require('./recovery.js'):root.Recovery,J=node?require('./joint-rig.js'):root.BodyflipJointRig,M=node?require('./mass.js'):root.BodyflipMass,S=node?require('./support.js'):root.BodyflipSupport,P=node?require('./body-contact.js'):root.BodyflipBodyContact;
const {add,sub,mul,length,rotate,qm}=R,emptySurfaces=[],cache=new WeakMap(),profiles=new WeakMap(),Profile=node?require('./rig-profile.js'):root.BodyflipRigProfile;
function create(names,parents,reference){
 const profile=Profile?.current()||null;if(cache.has(reference)&&profiles.get(reference)===profile)return cache.get(reference);profiles.set(reference,profile);
 const prepared=new WeakMap();
 const visible=P.create(names,parents,reference),joints=J.create(names,parents,reference),rig=M.model(names,parents,reference),feet=['L','R'].map(side=>S.leg(reference,names,side));
 function shapes(p,bodies=rig){if(profile)return Profile.shapes(p,bodies.map(b=>b.name));return bodies.map(b=>{const center=add(p.points[b.i],rotate(p.q[b.i],b.offset)),axes=R.toAxes(qm(p.q[b.i],b.rotation));return b.shape==='box'?{name:b.name,center,axes,half:mul(b.dims,.5)}:{name:b.name,a:sub(center,mul(axes[1],b.halfHeight)),b:add(center,mul(axes[1],b.halfHeight)),radius:b.radius};});}
 const contactShapes=p=>profile?shapes(p):[...shapes(p),...visible.shapes(p)];
 const footBodies=new Map(feet.map(l=>[l.side,rig.filter(b=>b.name==='foot_'+l.side.toLowerCase()||b.name==='ball_'+l.side.toLowerCase())]));
 const footShapes=(p,side)=>profile?shapes(p,footBodies.get(side)):[...shapes(p,footBodies.get(side)),...visible.footShapes(p,side.toLowerCase())];
 function project(p,surfaces=emptySurfaces){
  if(prepared.get(p)===surfaces)return p;
  const center=M.center(p,rig);let pose=joints.project(p);const shift=sub(center,M.center(pose,rig));
  pose={...pose,points:pose.points.map((p,i)=>i===0?p:add(p,shift))};
  // Anatomical projection can change the shoulder's world aim. Re-aim the
  // released pushing arm from its current socket, then clamp in the same
  // shoulder constraint frame. The target remains an absolute world point.
  for(const aim of p.handFollow||[]){
   if(aim.weight<=0)continue;
   const joint=joints.joints.find(j=>j.i===aim.shoulder),original=R.localize(pose.points,pose.q,parents).q[aim.shoulder];
   for(let pass=0;pass<3;pass++){
    // During recovery preserve the already blended world direction. A second
    // pull toward the contact here delayed recovery until its last few frames.
    const wanted=aim.returning?sub(p.points[aim.wrist],p.points[aim.shoulder]):sub(aim.target,pose.points[aim.shoulder]);
    const local=R.localize(pose.points,pose.q,parents),delta=R.fromTo(sub(pose.points[aim.wrist],pose.points[aim.shoulder]),wanted);
    local.q[aim.shoulder]=joints.clampLocal(qm(R.qinv(pose.q[joint.parent]),qm(delta,pose.q[aim.shoulder])),joint);pose=R.fk(local,parents);
   }
   const local=R.localize(pose.points,pose.q,parents);local.q[aim.shoulder]=joints.clampLocal(R.qslerp(original,local.q[aim.shoulder],aim.weight),joint);pose=R.fk(local,parents);
  }
  if(p.handFollow?.length){const d=sub(center,M.center(pose,rig));pose={...pose,points:pose.points.map((v,i)=>i===0?v:add(v,d))};}
  if(!surfaces.length){prepared.set(pose,surfaces);return pose;}
  // The free foot must yield when pelvis compression carries it into ground.
  // Correct that chain first, preserving the supporting side and pelvis.
  for(let pass=0;pass<8;pass++){
   let corrected=false;
   for(const leg of feet){
    let worst=null;for(const shape of footShapes(pose,leg.side))for(const surface of surfaces){const c=P.query(shape,surface);if(c.gap<-.00005&&(!worst||c.gap<worst.gap))worst=c;}
    if(!worst)continue;
    const target=add(pose.points[leg.foot],mul(worst.normal,-worst.gap+.00005)),live=S.leg(pose,names,leg.side),rotation={footQ:pose.q[leg.foot],toeQ:pose.q[leg.toe]};
    pose=joints.project(S.solve(pose,live,target,parents,1,rotation));corrected=true;
   }
   // Foot clearance changes articulation, not the intended mass-centre path.
   // Rebalance before the next pass checks the remaining sole clearance.
   if(corrected){const d=sub(center,M.center(pose,rig));pose={...pose,points:pose.points.map((v,i)=>i===0?v:add(v,d))};}
   if(!corrected)break;
  }
  // Remaining torso/hand contact is a whole-body displacement. Both modes see
  // the same physical volumes, including the capsule end caps below a joint.
  const geometry=contactShapes(pose),resolved=P.move(geometry,geometry,pose.points[0],surfaces),d=sub(resolved.root,pose.points[0]);
  if(length(d)>0)pose={...pose,points:pose.points.map((p,i)=>i===0?p:add(p,d))};
  prepared.set(pose,surfaces);return pose;
 }
 function track(source,{start=0,surfaces=emptySurfaces}={}){
  const dt=1/240,maxLocalSpeed=30,frames=[];
  function make(time,previous,elapsed){
   const frame=source(time),wanted=project(frame.pose,surfaces);if(!previous)return {...frame,pose:wanted};
   const local=R.localize(wanted.points,wanted.q,parents),before=R.localize(previous.pose.points,previous.pose.q,parents);let limited=false;
   for(const joint of joints.joints){const i=joint.i,delta=R.qlog(qm(local.q[i],R.qinv(before.q[i]))),angle=length(delta),cap=maxLocalSpeed*elapsed;if(angle>cap+1e-9){local.q[i]=joints.clampLocal(qm(R.qexp(mul(delta,cap/angle)),before.q[i]),joint);limited=true;}}
   if(!limited)return {...frame,pose:wanted};
   let pose=R.fk(local,parents);const shift=sub(M.center(wanted,rig),M.center(pose,rig));pose={...pose,points:pose.points.map((p,i)=>i===0?p:add(p,shift))};
   return {...frame,pose:project(pose,surfaces)};
  }
  function sample(time){
   if(time<start)return source(time);
   if(!frames.length)frames.push(make(start,null,0));
   const tick=Math.floor((time-start)/dt+1e-9);
   while(frames.length<=tick){const t=start+frames.length*dt;frames.push(make(t,frames.at(-1),dt));}
   const at=start+tick*dt;return time-at<1e-9?frames[tick]:make(time,frames[tick],time-at);
  }
  return {sample,get ticks(){return frames.length;}};
 }
 const result={project,track,shapes,joints,rig,mark(p,surfaces=emptySurfaces){prepared.set(p,surfaces);return p;}};cache.set(reference,result);return result;
}
const api={create};if(node)module.exports=api;else root.BodyflipTargetRig=api;
})(globalThis);
