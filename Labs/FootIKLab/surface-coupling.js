/* Causal bridge: 120Hz surface physics and a recurrent 30Hz locomotion policy. */
(function(root){
'use strict';
const R=typeof module!=='undefined'?require('./recovery.js'):root.Recovery;
const K=typeof module!=='undefined'?require('./footik.js'):root.FootIK;
const F=typeof module!=='undefined'?require('./surface.js'):root.FootSurface;
const {add,sub,mul,length,rotate,qinv,qslerp}=R;
const files=['surface.js','surface-coupling.js','surface_driver.cjs','surface_nn.py','footik.js','support.js','recovery.js'];
let version;
async function fingerprint(){
 if(!version)version=(async()=>{const parts=await Promise.all(files.map(async name=>{const response=await fetch(name);if(!response.ok)throw Error('Cannot load '+name);return new Uint8Array(await response.arrayBuffer());})),bytes=new Uint8Array(parts.reduce((n,p)=>n+p.length,0));let offset=0;for(const p of parts){bytes.set(p,offset);offset+=p.length;}return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),v=>v.toString(16).padStart(2,'0')).join('');})();
 return version;
}
function sourceData(run){return {names:run.names.slice(1),fps:run.fps,duration:run.duration,periodSeconds:run.periodSeconds,roots:run.poses.map(p=>p.points[0]),poses:run.poses.map(p=>({points:p.points.slice(1),axes:p.axes.slice(1)})),direction:run.direction,directionMeta:run.directionMeta,rootYawDegrees:run.rootYawDegrees,rootYawSpeed:run.rootYawSpeed,nnRootWindow:run.nnRootWindow,source:run.source};}
function anchored(p,position){return {...p,points:p.points.map(v=>add(position,sub(v,p.points[0])))};}
function transport(previous,current){
 const q=qslerp(previous.surfaceQ,current.surfaceQ,.5),delta=rotate(qinv(q),sub(current.base,previous.base));
 // The policy's ground frame follows the supporting plane. Upright is a
 // posture adjustment, not a reduction in the actual along-surface speed.
 // Normal motion remains in physics; it is not planar locomotion.
 return [delta[0],0,delta[2]];
}
function pair(a,b,parents){const x=R.localize(a.points,a.q,parents),y=R.localize(b.points,b.q,parents);return u=>u<=0?a:u>=1?b:R.fk({p:x.p.map((v,j)=>add(v,mul(sub(y.p[j],v),u))),q:x.q.map((v,j)=>qslerp(v,y.q[j],u))},parents);}
function pose(data){const q=data.axes.map(R.fromAxes);return {points:data.points,axes:data.axes,q};}
async function compute(run,input,infer,cancelled=()=>false){
 const s=K.sanitize(input),sim=F.simulate(run,s,{interactive:true}),speed=run.directionMeta.commandSpeed,roots=[],poses=[],contexts=[],steps=[],windows=[];
 let next=sim.next(),segment=null,segmentStart=0,active=[false,false],lastPose=null,first=true,requested=0;
 while(!next.done){
  if(cancelled())return null;
  const c=next.value,{i,time}=c;
  const virtual=i?add(roots[i-1],transport(contexts[i-1],c)):[0,0,0];roots.push(virtual);contexts.push(c);
  let p=anchored(segment?segment((i-segmentStart)/4):K.at(run,time),virtual);
  if(i>=4&&i%4===0&&time<run.duration-1e-8){
   const forecast=c.forecast(40),projected=[virtual];for(let k=1;k<forecast.length;k++)projected.push(add(projected[k-1],transport(forecast[k-1],forecast[k])));
   const path=[roots[i-4],...projected.filter((_,k)=>k%4===0)];
   const request={gait:s.gait,policy:'run',direction:run.direction,names:run.names,drawn:false,frames:2,roots:path,rootYawDegrees:path.map((_,k)=>K.commandYaw(s,time+(k-1)/30,speed))};
   if(first)request.seeds=[poses[i-4],p].map(v=>({points:v.points,axes:v.axes}));
   const result=await infer(request,requested++);first=false;
   if(!result?.pose?.points?.every(v=>v.every(Number.isFinite)))throw Error('Invalid surface NN step');
   const target=pose(result.pose);segment=pair(p,target,run.parents);segmentStart=i;
   steps.push(result);
   windows.push({frame:i/2,root:c.base,velocity:c.velocity,virtual,delta:sub(virtual,roots[i-4]),futureDelta:sub(path[2],virtual),yaw:request.rootYawDegrees[1],nextYaw:request.rootYawDegrees[2],future:path.slice(2,10),futureYaw:request.rootYawDegrees.slice(2,10)});
  }
  const legs=['L','R'].map(side=>K.stableLeg(p,run.names,side)),untilPlant=[],initial=lastPose?null:K.at(run,1/120);
  for(let side=0;side<2;side++){
   const l=legs[side],carrier=rotate(qinv(c.surfaceQ),c.velocity);carrier[1]=0;
   const velocity=lastPose?mul(sub(p.points[l.foot],lastPose.points[l.foot]),120):add(mul(sub(sub(initial.points[l.foot],initial.points[0]),sub(p.points[l.foot],p.points[0])),120),carrier);
   const intent=F.gaitIntent(p,l,velocity,speed,active[side]);active[side]=intent.stance;
   // Continuous approach estimate from the new NN motion, not the old course's
   // cached phase. Material contact/reach checks still own actual acquisition.
   untilPlant.push(active[side]?0:velocity[1]<-.05?Math.max(0,intent.clearance-.02)/-velocity[1]:Infinity);
  }
  poses.push(p);lastPose=p;next=sim.next({pose:p,legs,stance:active.slice(),untilPlant});
 }
 const model=next.value;model.coupling={policyHz:30,steps:steps.length,windows,source:'actual-root'};
 return {model,steps};
}
async function prepare(run,settings,post,cancelled){
 const physics={...K.sanitize(settings)};for(const k of ['ghost','targets','ramp','bicolor','bones','loop','showRoot','translucency','ghostTranslucency','trimIn','trimOut','speed'])delete physics[k];
 const source=sourceData(run),seed=run.poses.slice(0,2).map(p=>({points:p.points,axes:p.axes}));
 const response=await post('/resume',{kind:'surface',gait:settings.gait,policy:'run',direction:run.direction,frames:2,roots:source.roots.slice(0,12),seeds:seed,source,settings:physics,sourceVersion:await fingerprint()});
 if(cancelled())return null;
 if(response.kind!=='surface'||!Array.isArray(response.steps))throw Error('Surface NN worker is not updated yet. Refresh after its idle timeout.');
 const result=await compute(run,settings,async(_,i)=>response.steps[i],cancelled);
 if(!result)return null;
 if(result.steps.length!==response.steps.length)throw Error('Surface NN replay length differs');
 result.model.coupling.seconds=response.seconds;result.model.coupling.cache=response.cache;
 return result.model;
}
const api={files,sourceData,transport,compute,prepare};if(typeof module!=='undefined')module.exports=api;else root.FootSurfaceCoupling=api;
})(globalThis);
