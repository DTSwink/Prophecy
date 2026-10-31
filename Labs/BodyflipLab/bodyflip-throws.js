/* Playback glue: held meshes and immutable release plans. Physics stays in Bodyflip. */
(function(root){'use strict';
const node=typeof module!=='undefined',T=node?require('./throw-attack.js'):root.BodyflipThrowAttack;
function create({physics,renderer}){
 let sequence=null,poseAt=null,revision=null,through=-Infinity,tracks=[],plans=[];
 function configure(next,sample,key=''){
  const horizon=next?.preparedThrough??Infinity;if(next===sequence&&key===revision&&horizon===through)return;
  sequence=next;poseAt=sample;revision=key;through=horizon;tracks=(sequence?.segments||[]).map(s=>s.attack).filter(t=>t?.isThrow);
  plans=tracks.filter(t=>t.releaseTime<=horizon+1e-8).map(t=>t.launchAt(poseAt(t.releaseTime),t.transportVelocity(poseAt),t.transportAngularVelocity(poseAt)));
  renderer.throwAssets=T.assets;physics.setProjectiles(T.assets,plans);
 }
 function sample(time,pose){
  if(!tracks.length)return [];
  const released=physics.projectilesAt(time,poseAt),held=tracks.filter(t=>time>=t.start&&time<t.releaseTime).map(t=>({...t.heldAt(pose),id:'held:'+t.start}));return [...released,...held];
 }
 return {configure,sample,get plans(){return plans;},get tracks(){return tracks;},invalidate(){revision=null;}};
}
const api={create};if(node)module.exports=api;else root.BodyflipThrows=api;
})(globalThis);
