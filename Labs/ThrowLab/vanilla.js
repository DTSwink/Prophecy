(function(root){
'use strict';
const R=typeof module!=='undefined'?require('./recovery.js'):root.Recovery;
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v)),finite=(v,d=0)=>Number.isFinite(v)?v:d;
const triple=v=>Array.from({length:3},(_,i)=>finite(v?.[i]));
function wholeFrameKeys(input,end=Infinity){
 const keys=new Map();
 for(const key of Array.isArray(input)?input:[]){
  if(!Number.isFinite(key.frame))continue;
  const frame=clamp(Math.round(key.frame),0,Math.floor(end)),distance=Math.abs(key.frame-frame),old=keys.get(frame);
  // Preserve explicit whole-frame poses over accidental subframe targets.
  // Otherwise use the closest sample; equal-distance duplicates use the last.
  if(!old||distance<=old.distance)keys.set(frame,{frame,rotation:triple(key.rotation),distance});
 }
 return [...keys.values()].sort((a,b)=>a.frame-b.frame).map(({frame,rotation})=>({frame,rotation}));
}
function config(value={},end=Infinity,release=end){
 return {armed:clamp(Math.round(finite(value.armed)),0,Math.floor(release)),keys:wholeFrameKeys(value.keys,end),forearmKeys:wholeFrameKeys(value.forearmKeys,end),velocityRotation:triple(value.velocityRotation),speedScale:Math.max(0,finite(value.speedScale,1)),twist:Number.isFinite(value.twist)?value.twist:null};
}
function anglesAt(keys,frame){
 if(!keys.length)return [0,0,0];
 // Only whole frames are authorable. Playback blends adjacent frame rotations
 // along the shortest quaternion arc, never visiting extra subframe targets.
 if(Math.abs(frame-Math.round(frame))<1e-7)frame=Math.round(frame);
 const exact=Number.isInteger(frame)&&keys.find(k=>k.frame===frame);if(exact)return exact.rotation.slice();
 if(Number.isInteger(frame))return [0,0,0];
 let a={frame:Math.floor(frame),rotation:[0,0,0]},b={frame:Math.ceil(frame),rotation:[0,0,0]};
 for(const k of keys){if(k.frame===a.frame)a=k;if(k.frame===b.frame)b=k;}
 const u=frame-a.frame;
 return anglesFromRotation(R.qslerp(rotation(a.rotation),rotation(b.rotation),u),a.rotation);
}
// Local intrinsic X/Y/Z offsets, expressed in degrees at authored whole frames.
function rotation(degrees){const a=degrees.map(v=>v*Math.PI/180);return R.qm(R.qm(R.qexp([a[0],0,0]),R.qexp([0,a[1],0])),R.qexp([0,0,a[2]]));}
// Convert a world-space gizmo edit back to the existing local key format.
function anglesFromRotation(q,reference){
 const m=R.toAxes(R.unit(q)),sy=clamp(m[2][0],-1,1),y=Math.asin(sy)*180/Math.PI;
 let x,z;
 if(Math.abs(sy)<1-1e-12){x=Math.atan2(-m[2][1],m[2][2])*180/Math.PI;z=Math.atan2(-m[1][0],m[0][0])*180/Math.PI;}
 else {z=reference[2];x=Math.atan2(m[1][2],m[1][1])*180/Math.PI-Math.sign(sy)*z;}
 const near=a=>a.map((v,i)=>v+360*Math.round((reference[i]-v)/360)),a=near([x,y,z]),b=near([x+180,180-y,z+180]),distance=v=>v.reduce((s,n,i)=>s+(n-reference[i])**2,0);
 return distance(a)<=distance(b)?a:b;
}
function rotateWorld(base,angles,axis,radians,reference=angles){
 const normal=[0,0,0];normal[axis]=1;return rotateAxis(base,angles,normal,radians,reference);
}
function rotateAxis(base,angles,normal,radians,reference=angles){
 const world=R.qm(R.qexp(R.mul(R.unit(normal),radians)),R.qm(base,rotation(angles)));
 return anglesFromRotation(R.qm(R.qinv(base),world),reference);
}
// Signed twist of the edited orientation away from its authored default about
// the displayed world-space ring axis. Unlike stored Euler channels, this also
// matches forearm-local rings and the hand's absolute/world mode.
function axisOffsetDegrees(defaultQ,currentQ,axis){
 const q=R.unit(R.qm(currentQ,R.qinv(defaultQ))),along=R.dot(q.slice(0,3),R.unit(axis));
 if(Math.hypot(along,q[3])<1e-9)return null; // A perpendicular half-turn has no unique twist.
 const degrees=2*Math.atan2(along,q[3])*180/Math.PI;
 return ((degrees+180)%360+360)%360-180;
}
function pose(source,parents,hand,keys,frame,parentSpace=false){
 const angles=anglesAt(keys,frame);if(angles.every(v=>v===0))return source;
 const points=source.points.map(p=>p.slice()),q=source.q.map(v=>v.slice()),parent=q[parents[hand]],turn=rotation(angles),next=R.unit(parentSpace?R.qm(R.qm(R.qm(parent,turn),R.qinv(parent)),q[hand]):R.qm(q[hand],turn)),delta=R.qm(next,R.qinv(q[hand]));
 for(let j=0;j<q.length;j++){let ancestor=j;while(ancestor>=0&&ancestor!==hand)ancestor=parents[ancestor];if(ancestor!==hand)continue;
  points[j]=R.add(points[hand],R.rotate(delta,R.sub(source.points[j],source.points[hand])));q[j]=j===hand?next:R.unit(R.qm(delta,source.q[j]));
 }
 return {...source,points,q,axes:q.map(R.toAxes)};
}
function launch(velocity,omega,handQ,rootQ,longAxis,controls){
 const direction=R.qm(R.qm(rootQ,rotation(controls.velocityRotation)),R.qinv(rootQ));
 const axis=R.unit(R.rotate(handQ,longAxis)),authoredTwist=R.dot(omega,axis)/(60*Math.PI/180),twist=controls.twist??authoredTwist;
 return {velocity:R.mul(R.rotate(direction,velocity),controls.speedScale),omega:R.mul(axis,twist*60*Math.PI/180),axis,authoredTwist,twist};
}
const api={config,wholeFrameKeys,anglesAt,rotation,anglesFromRotation,rotateWorld,rotateAxis,axisOffsetDegrees,pose,launch};if(typeof module!=='undefined')module.exports=api;else root.ThrowVanilla=api;
})(globalThis);
