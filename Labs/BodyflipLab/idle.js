/* Frozen authored idle loop, facing forward and grounded without flip/twist. */
(function(root){
'use strict';
const node=typeof module!=='undefined',R=node?require('./recovery.js'):root.Recovery,C=node?require('./core.js'):root.BodyflipCore,S=node?require('./support.js'):root.BodyflipSupport;
function create(meta,buffer,manifest){
 const clip=C.decode(meta,buffer,manifest.names,manifest.parents),first=clip.poses[0];
 const forward=R.rotate(first.q[1],[0,-1,0]),rotation=R.fromTo(R.unit([forward[0],0,forward[2]]),[0,0,1]);
 const feet=['L','R'].map(side=>({side,ankle:manifest.names.indexOf('foot_'+side.toLowerCase()),toe:manifest.names.indexOf('ball_'+side.toLowerCase())}));
 function ground(raw){
  const points=raw.points.map(p=>R.rotate(rotation,R.sub(p,first.points[0]))),q=raw.q.map(q=>R.qm(rotation,q)),pose={points,q,axes:q.map(R.toAxes)};
  const bottom=Math.min(...feet.flatMap(f=>S.footPoints(pose,f.ankle,f.toe,f.side).map(v=>points[f.ankle][1]+v[1])));
  return {...pose,points:points.map(p=>R.sub(p,[0,bottom,0]))};
 }
 function rawAt(time){const frame=((time%clip.duration)+clip.duration)%clip.duration*meta.fps,i=Math.min(clip.poses.length-2,Math.floor(frame));return C.blend(clip.poses[i],clip.poses[i+1],frame-i,manifest.parents);}
 let poses=null;
 function motion(phase=0){poses ||= clip.poses.map(ground);return {names:manifest.names,fps:meta.fps,duration:clip.duration,poses,sample:time=>ground(rawAt(time+phase*clip.duration)),source:meta.asset};}
 return {duration:clip.duration,rawAt,ground,sample:time=>ground(rawAt(time)),motion};
}
const api={create};if(node)module.exports=api;else root.BodyflipIdle=api;
})(globalThis);
