/* Shared Foot IK owns locomotion; Bodyflip owns support/push and free flight. */
(function(root){
'use strict';
const node=typeof module!=='undefined',R=node?require('./recovery.js'):root.Recovery,C=node?require('./core.js'):root.BodyflipCore;
const K=node?require('../FootIKLab/footik.js'):root.SharedFootIK.core,Q=node?require('../FootIKLab/surface-coupling.js'):root.SharedFootIK.coupling;
function preset(){return {mode:'footIK',surfaceIK:true,footIKSettings:{gait:'run',terrain:'incline',slopeAngle:90,approach:'toward',phase:.58,upright:.55,inclineGravity:true,minGravityIncline:80,fullGravity:70,energyConservation:100,pelvisCloser:40,pelvisSpeedMin:1.5,pelvisSpeedMax:6,slideEnabled:true,slideSpeed:-2,rootYawSpeed:0,deleteFloorFrame:-1},platforms:null,runSeconds:5,runPhase:.58,startYaw:0,airFlip:true,flipSpeed:0,twistSpeed:0,flipAngle:0,twistAngle:0,trimIn:0,trimOut:2.2,trimLoop:true,playbackSpeed:.5,jumpEvents:[{...C.jumpDefaults,id:'wall-backflip',time:.65,surface:'auto',flip:320,twist:0,turnIn:.2,turnOut:.25,pose:'none'}]};}
function adapter(model,parents){
 const surfaces=model.terrain.surfaces;
 function sample(t){
  const f=Math.max(0,Math.min(t,model.generatedThrough))*model.fps,i=Math.min(model.frames.length-1,Math.floor(f)),a=model.frames[i],b=model.frames[Math.min(i+1,model.frames.length-1)],u=f-i;
  const pose=u>1e-8?C.blend(a.pose,b.pose,u,parents):a.pose,velocity=a.surface.velocity.slice(),normal=a.surface.normal,plane=surfaces.reduce((best,s)=>R.dot(s.normal,normal)>R.dot(best.normal,normal)?s:best,surfaces[0]);
  return {pose,root:pose.points[0],phase:'RUN',speed:model.speed,vy:velocity[1],velocity,airTime:0,footIK:{shared:true,surfaceId:plane.id,feet:a.feet,mode:a.surface.mode},capsule:{grounded:true,surfaceId:plane.id,landingTime:0,yaw:0},terrainOwner:true};
 }
 return {surfaces,sample,state(t){const f=sample(t);return {root:f.root,bias:[0,0,0],velocity:f.velocity,landed:false,normal:model.sample(t).surface.normal,yaw:0};},prepare(){},setHorizon(){},landings:[],model};
}
const cache=new Map();
async function prepare(settings,parents,post,cancelled=()=>false){
 const input=K.sanitize({...preset().footIKSettings,...settings.footIKSettings,enabled:settings.surfaceIK,phase:settings.runPhase,platformLayouts:settings.platforms?{incline:settings.platforms}:{}}),key=JSON.stringify(input);
 let session=cache.get(key);
 if(!session){const run=K.decode(await post('/foot-ik/resume',{kind:'direction',policy:'run',gait:'run',direction:'forward',duration:.1,totalDuration:5,seedOnly:true,phase:input.phase}),parents);if(cancelled())return null;session=Q.createPreparation(run,input,(path,data)=>post("/foot-ik"+path,data));cache.set(key,session);if(cache.size>2){const old=cache.keys().next().value;cache.get(old).close();cache.delete(old);}}
 // Support planning reads the outgoing carrier while the foot acquires a pin.
 const events=(settings.jumpEvents||[]).filter(e=>e.enabled!==false),until=Math.min(5,Math.max(settings.trimOut,...events.map(e=>e.time+1)));
 const model=await session.extend(until,cancelled);if(!model)return null;
 const result=adapter(model,parents);result.extend=async(end,stop)=>{if(end>5&&(!events.length||events[0].time>=5))throw Error('Foot IK locomotion supports five seconds. Place the jump before 5 s or shorten the timeline.');return session.extend(Math.min(5,end),stop);};return result;
}
const api={preset,prepare,adapter};if(node)module.exports=api;else root.BodyflipTerrainMode=api;
})(globalThis);
