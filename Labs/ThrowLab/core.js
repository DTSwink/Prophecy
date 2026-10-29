(function(root){
'use strict';
const R=typeof module!=='undefined'?require('./recovery.js'):root.Recovery;
const V=typeof module!=='undefined'?require('./vanilla.js'):root.ThrowVanilla;
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const defaults={clip:'big-throw',object:'sword',releases:{},vanilla:{},imperialSpear:false,weaponGizmo:false,scaleGizmo:false,weaponScales:{},grips:{},forearmGizmo:false,handGizmo:false,velocityGizmo:false,gizmosHidden:false,handGizmoSpace:'world',target:[0,1.5,3],radius:.16,bicolor:true,skeleton:false,roomBrightness:40,playbackSpeed:1,trimLoop:false,trims:{}};
const gizmoKeys=["scaleGizmo","weaponGizmo","velocityGizmo","forearmGizmo","handGizmo"];
// Object choice belongs to a throw. Legacy global selections cannot tell us
// what Small Throw last used, so it acquires the requested Bomb default once.
function weaponSelection(s={}){
 const clip=s.clip==='small-throw'||s.clip==='big-throw-2'?'small-throw':'big-throw';
 const throwObjects={'big-throw':'sword','small-throw':'bomb'};
 for(const id of Object.keys(throwObjects)){
  const choice=s.throwObjects?.[id];
  if(choice==='sword'||choice==='bomb')throwObjects[id]=choice;
  else if(id==='big-throw'&&clip===id&&(s.object==='sword'||s.object==='bomb'))throwObjects[id]=s.object;
 }
 return {clip,object:throwObjects[clip],throwObjects};
}
function selectClip(s,id){
 if(!['big-throw','small-throw'].includes(id))return;
 s.throwObjects[s.clip]=s.object;s.clip=id;s.object=s.throwObjects[id];
}
function selectObject(s,value){
 if(!['sword','bomb'].includes(value))return;
 s.object=value;s.throwObjects[s.clip]=value;
}
function sanitize(s={}){const {clip,object,throwObjects}=weaponSelection(s);const activeGizmo=gizmoKeys.find(k=>s[k]);const grips={};for(const clip of ['big-throw','small-throw']){grips[clip]={};for(const kind of ['sword','spear','bomb']){const g=s.grips?.[clip]?.[kind]||s.grips?.[kind]||{};grips[clip][kind]={};for(const key of ['position','rotation'])grips[clip][kind][key]=Array.isArray(g[key])&&g[key].length===3&&g[key].every(Number.isFinite)?g[key].slice():[0,0,0];}}const weaponScales={};for(const clip of ['big-throw','small-throw']){weaponScales[clip]={};for(const kind of ['sword','spear','bomb']){const v=s.weaponScales?.[clip]?.[kind];weaponScales[clip][kind]=[0,1,2].map(i=>{const n=Array.isArray(v)?v[i]:v;return Number.isFinite(n)?clamp(n,.1,2):1;});}}return {...defaults,gizmosHidden:!!s.gizmosHidden,scaleGizmo:activeGizmo==="scaleGizmo",weaponScales,imperialSpear:!!s.imperialSpear,weaponGizmo:activeGizmo==="weaponGizmo",grips,handGizmoSpace:s.handGizmoSpace==='local'?'local':'world',forearmGizmo:activeGizmo==="forearmGizmo",handGizmo:activeGizmo==="handGizmo",velocityGizmo:activeGizmo==="velocityGizmo",vanilla:Object.fromEntries(Object.entries(s.vanilla&&typeof s.vanilla==='object'?s.vanilla:{}).map(([id,value])=>[id,V.config(value||{})])),clip,object,throwObjects,releases:s.releases&&typeof s.releases==='object'?structuredClone(s.releases):{},target:Array.isArray(s.target)&&s.target.length===3&&s.target.every(Number.isFinite)?s.target.slice():defaults.target.slice(),radius:clamp(Number(s.radius)||.16,.04,1),bicolor:s.bicolor!==false,skeleton:!!s.skeleton,roomBrightness:Number.isFinite(s.roomBrightness)?clamp(s.roomBrightness,0,100):defaults.roomBrightness,playbackSpeed:clamp(Number(s.playbackSpeed)||1,.1,1),trimLoop:!!s.trimLoop,trims:s.trims&&typeof s.trims==='object'?structuredClone(s.trims):{}};}
function decode(data,parents){
 const poses=data.frames.map(frame=>{const q=frame.map(v=>v.slice(3)),points=frame.map(v=>v.slice(0,3));return {points,q,axes:q.map(R.toAxes)};});
 // Keep all authored root displacement; only place each clip's first root at XZ origin.
 const offset=[poses[0].points[0][0],0,poses[0].points[0][2]];
 for(const p of poses)p.points=p.points.map(v=>R.sub(v,offset));
 return {...data,poses,locals:poses.map(p=>R.localize(p.points,p.q,parents)),offset};
}
function sample(clip,t,parents){
 const f=clamp(t,0,clip.duration)*clip.fps,i=Math.min(clip.locals.length-2,Math.floor(f)),u=clamp(f-i,0,1),a=clip.locals[i],b=clip.locals[i+1];
 return R.fk({p:a.p.map((v,j)=>R.add(v,R.mul(R.sub(b.p[j],v),u))),q:a.q.map((v,j)=>R.qslerp(v,b.q[j],u))},parents);
}
const api={gizmoKeys,defaults,sanitize,selectClip,selectObject,decode,sample};if(typeof module!=='undefined')module.exports=api;else root.ThrowCore=api;
})(globalThis);
