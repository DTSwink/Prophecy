/* Causal bridge: 120Hz surface physics and a recurrent 30Hz locomotion policy. */
(function(root){
'use strict';
const R=typeof module!=='undefined'?require('./recovery.js'):root.Recovery;
const K=typeof module!=='undefined'?require('./footik.js'):root.FootIK;
const F=typeof module!=='undefined'?require('./surface.js'):root.FootSurface;
const {add,sub,mul,length,rotate,qinv,qslerp}=R;
const files=['surface.js','surface-coupling.js','surface_driver.cjs','surface_nn.py','footik.js','support.js','recovery.js','slide-joints.js','slide-entry.js','slide-arms.js'];
let version;
async function fingerprint(){
 if(!version)version=(async()=>{const parts=await Promise.all(files.map(async name=>{if(root.FootHTTP)return new Uint8Array(await root.FootHTTP.request(name,{},'arrayBuffer',8000));const response=await fetch(name);if(!response.ok)throw Error('Cannot load '+name);return new Uint8Array(await response.arrayBuffer());})),bytes=new Uint8Array(parts.reduce((n,p)=>n+p.length,0));let offset=0;for(const p of parts){bytes.set(p,offset);offset+=p.length;}return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),v=>v.toString(16).padStart(2,'0')).join('');})().catch(error=>{version=null;throw error;});
 return version;
}
function sourceData(run){return {names:run.names.slice(1),fps:run.fps,duration:run.duration,totalDuration:run.totalDuration??run.directionMeta?.totalDuration??run.duration,referenceHeight:run.referenceHeight??run.directionMeta?.referenceHeight,periodSeconds:run.periodSeconds,roots:run.poses.map(p=>p.points[0]),poses:run.poses.map(p=>({points:p.points.slice(1),axes:p.axes.slice(1)})),direction:run.direction,directionMeta:run.directionMeta,rootYawDegrees:run.rootYawDegrees,rootYawSpeed:run.rootYawSpeed,nnRootWindow:run.nnRootWindow,source:run.source};}
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
function createSession(run,input,infer){
 let model;
 const s=K.sanitize(input),sim=F.simulate(run,s,{interactive:true,checkpoints:true,onModel:value=>{model=value;}}),speed=run.directionMeta.commandSpeed,roots=[],poses=[],contexts=[],steps=[],windows=[];
 let next=sim.next(),segment=null,segmentStart=0,active=[false,false],lastPose=null,first=true,slideSource=null,resumeSource=null,pendingPolicy=null,lastPolicyIndex=-1,queue=Promise.resolve();
 function resumePose(source,at,originalTime,position){
  const turn=R.qexp([0,(K.commandYaw(s,at,speed)-K.commandYaw(s,originalTime,speed))*Math.PI/180,0]);
  const q=source.q.map(v=>R.qm(turn,v));return {points:source.points.map(v=>add(position,rotate(turn,sub(v,source.points[0])))),q,axes:q.map(R.toAxes)};
 }
 model.coupling={policyHz:30,steps:0,windows,source:'actual-root'};
 async function consumePolicy(){
  if(!pendingPolicy)return;
  const {request,p,i,window}=pendingPolicy,result=await infer(request,steps.length);
  if(!result?.pose?.points?.every(v=>v.every(Number.isFinite)))throw Error('Invalid surface NN step');
  const target=pose(result.pose);segment=pair(p,target,run.parents);segmentStart=i;
  steps.push(result);windows.push(window);first=false;pendingPolicy=null;model.coupling.steps=steps.length;
 }
 async function advance(endTime,cancelled){
  if(!Number.isFinite(+endTime))throw Error('Invalid surface preparation end');
  const last=Math.min(Math.round(model.duration*120),Math.max(0,Math.ceil(+endTime*120-1e-8)));
  if(cancelled())return null;
  if(model.frames.length>last)return {model,steps};
  // A policy boundary exactly at the old trim end did not need its next
  // pose yet. Its root window was captured then; consume it before resuming.
  await consumePolicy();
  while(!next.done&&model.frames.length<=last){
   if(cancelled())return null;
   if(next.value.checkpoint){next=sim.next();if(next.done)break;}
   const c=next.value,{i,time}=c;
   const virtual=i?add(roots[i-1],transport(contexts[i-1],c)):[0,0,0];roots[i]=virtual;contexts[i]=c;
  let p=anchored(segment?segment((i-segmentStart)/4):K.at(run,time),virtual);
  if(c.slide){slideSource||={pose:p,previous:poses[Math.max(0,i-4)]||p,time};p=anchored(slideSource.pose,virtual);}
  else if(slideSource){resumeSource=slideSource;slideSource=null;segment=null;active=[false,false];}
  if(resumeSource)p=resumePose(resumeSource.pose,time,resumeSource.time,virtual);
  if(!c.slide&&i>=4&&i%4===0&&time<model.duration-1e-8&&lastPolicyIndex!==i){
   const forecast=c.forecast(40),projected=[virtual];for(let k=1;k<forecast.length;k++)projected.push(add(projected[k-1],transport(forecast[k-1],forecast[k])));
   const path=[roots[i-4],...projected.filter((_,k)=>k%4===0)];
   const request={gait:s.gait,policy:'run',direction:run.direction,names:run.names,drawn:false,frames:2,roots:path,rootYawDegrees:path.map((_,k)=>K.commandYaw(s,time+(k-1)/30,speed))};
   if(resumeSource){
    // Rebase the paused native gait and its30Hz history onto today's root
    // window, not the old pre-slide root. The displayed slide blends out in
    // surface.js; its deliberately non-locomotion pose is not NN feedback.
    const previous=resumePose(resumeSource.previous,time-1/30,resumeSource.time-1/30,roots[i-4]);
    request.reset=true;request.seeds=[previous,p].map(v=>({points:v.points,axes:v.axes}));resumeSource=null;
   }else if(first)request.seeds=[poses[i-4],p].map(v=>({points:v.points,axes:v.axes}));
   pendingPolicy={request,p,i,window:{frame:i/2,root:c.base,velocity:c.velocity,virtual,delta:sub(virtual,roots[i-4]),futureDelta:sub(path[2],virtual),yaw:request.rootYawDegrees[1],nextYaw:request.rootYawDegrees[2],future:path.slice(2,10),futureYaw:request.rootYawDegrees.slice(2,10),...(request.reset?{resumed:true}:{})}};lastPolicyIndex=i;
   // Only the next30Hz endpoint needed to interpolate this visible interval
   // is allowed beyond the end. At an exact boundary even that is deferred.
   if(i<last)await consumePolicy();
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
   poses[i]=p;lastPose=p;next=sim.next({pose:p,legs,stance:active.slice(),untilPlant});
   if(!next.done&&!next.value.checkpoint)throw Error('Missing surface frame checkpoint');
  }
  return {model,steps};
 }
 return {model,steps,get generatedThrough(){return model.generatedThrough;},extend(endTime,cancelled=()=>false){const task=queue.then(()=>advance(endTime,cancelled));queue=task.catch(()=>{});return task;},close(){sim.return();}};
}
async function compute(run,input,infer,cancelled=()=>false){const session=createSession(run,input,infer);return session.extend(session.model.duration,cancelled);}
async function decodeFrameBatch(batch){
 if(typeof module!=='undefined')return JSON.parse(require('node:zlib').gunzipSync(Buffer.from(batch.data,'base64')));
 const bytes=Uint8Array.from(atob(batch.data),c=>c.charCodeAt(0));
 const stream=new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'));
 return JSON.parse(await new Response(stream).text());
}
function createPreparation(run,settings,post){
 const physics={...K.sanitize(settings)};for(const k of ['ghost','targets','ramp','bicolor','bones','loop','showRoot','translucency','ghostTranslucency','trimIn','trimOut','speed'])delete physics[k];
 const source=sourceData(run),seed=run.poses.slice(0,2).map(p=>({points:p.points,axes:p.axes}));
 let responses=[],sessionId,available=-1/120,queue=Promise.resolve(),preparedResponse=null;
 const session=createSession(run,settings,async(_,i)=>responses[i]);
 async function extend(endTime,cancelled){
  const end=Math.min(session.model.duration,Math.max(0,Math.ceil(+endTime*120-1e-8)/120));
  if(!Number.isFinite(end))throw Error('Invalid surface preparation end');
  if(cancelled())return null;
  if(end>available+1e-8){
   const response=await post('/resume',{kind:'surface',gait:settings.gait,policy:'run',direction:run.direction,frames:2,roots:source.roots.slice(0,12),seeds:seed,source,settings:physics,sourceVersion:await fingerprint(),totalDuration:session.model.duration,endTime:end,...(sessionId?{sessionId}:{})});
   if(response.kind!=='surface'||!Array.isArray(response.steps))throw Error('Surface NN worker is not updated yet. Refresh after its idle timeout.');
   if(!Number.isFinite(response.generatedThrough)||response.generatedThrough+1e-8<end)throw Error('Surface server did not prepare the requested tail');
   if(response.steps.length<responses.length)throw Error('Surface server lost its policy prefix');
   responses=response.steps;available=response.generatedThrough;sessionId=response.sessionId;
   preparedResponse=response;
   session.model.coupling.seconds=response.seconds;session.model.coupling.cache=response.cache;
  }
  if(cancelled())return null;
  if(preparedResponse?.frameEncoding==='gzip-json-v1'){
   const model=session.model,last=Math.ceil(end*120-1e-8)+1;
   for(const batch of preparedResponse.frameBatches){
    if(model.frames.length>=last)break;
    if(batch.start+batch.count<=model.frames.length)continue;
    if(batch.start>model.frames.length)throw Error('Surface pose prefix has a gap');
    const frames=await decodeFrameBatch(batch);
    if(frames.length!==batch.count)throw Error('Invalid surface pose batch');
    model.frames.push(...frames.slice(model.frames.length-batch.start,last-batch.start));
   }
   if(model.frames.length<last)throw Error('Surface response is missing solved poses');
   model.generatedThrough=(model.frames.length-1)/120;
   Object.assign(model.metrics,preparedResponse.diagnostics.metrics);
   model.events.splice(0,model.events.length,...(preparedResponse.diagnostics.events||[]));
   Object.assign(model.coupling,preparedResponse.diagnostics.coupling);
   return model;
  }
  // Compatibility with older offline recordings. Current workers send the
  // already-solved pose batches; no IK or collision work runs in the viewer.
  const result=await session.extend(end,cancelled);return result?.model||null;
 }
 return {get model(){return session.model;},get generatedThrough(){return session.generatedThrough;},extend(endTime,cancelled=()=>false){const task=queue.then(()=>extend(endTime,cancelled));queue=task.catch(()=>{});return task;},close(){session.close();}};
}
async function prepare(run,settings,post,cancelled=()=>false,endTime=run.totalDuration??run.directionMeta?.totalDuration??run.duration){return createPreparation(run,settings,post).extend(endTime,cancelled);}
const api={files,sourceData,transport,createSession,compute,createPreparation,prepare,decodeFrameBatch};if(typeof module!=='undefined')module.exports=api;else root.FootSurfaceCoupling=api;
})(globalThis);
