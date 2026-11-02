'use strict';
// Worker-only prospective course planner. This deliberately calls the accepted
// whole-trajectory K planner, never the unrelated causal createFeet solver.
const K=require('../../Labs/FootIKLab/footik.js');
const H=require('../../Labs/FootIKLab/handoff.js');
const T=require('../../Labs/FootIKLab/terrain.js');
const R=require('../../Labs/FootIKLab/recovery.js');
const Boundary=require('./stair-boundary.cjs');
const LiveTerrain=require('./live-terrain.cjs');
const {add,sub,mul,length}=R;
const clone=value=>structuredClone(value);
const encodePose=p=>({points:p.points,axes:p.axes||p.q.map(R.toAxes)});
const modelPose=(data,index)=>{
 const p=data.poses[index],q=[[0,0,0,1],...p.axes.map(R.fromAxes)];
 return {points:[data.roots[index],...p.points],q,axes:q.map(R.toAxes)};
};
function rowAt(rows,time){
 if(!rows?.length)throw Error('Live Foot IK needs actual previous/current and future root commands');
 if(time<=rows[0].time)return rows[0];
 let i=1;while(i<rows.length&&rows[i].time<time)i++;
 const a=rows[Math.min(i-1,rows.length-2)],b=rows[Math.min(i,rows.length-1)],u=(time-a.time)/(b.time-a.time);
 return {time,position:add(a.position,mul(sub(b.position,a.position),u)),yaw:a.yaw+(b.yaw-a.yaw)*u};
}
function validateRoots(rows){
 if(!Array.isArray(rows)||rows.length<2)throw Error('At least two timed root commands are required');
 for(let i=0;i<rows.length;i++){
  const r=rows[i];if(!Number.isFinite(r.time)||!Number.isFinite(r.yaw)||!Array.isArray(r.position)||r.position.length!==3||!r.position.every(Number.isFinite)||(i&&r.time<=rows[i-1].time))throw Error('Invalid live root command');
 }
}
function terrainWithSnapshot(settings,snapshot){
 const terrain=T.create(settings);if(!snapshot)return terrain;
 if(snapshot.rootRows)return LiveTerrain.create(snapshot);
 if(!Array.isArray(snapshot.tiles)||!snapshot.tiles.length)throw Error('Stair terrain snapshot must contain horizontal treads');
 const tiles=snapshot.tiles.map(t=>{
  if(typeof t.id!=='string'||!['x0','x1','z0','z1','y'].every(k=>Number.isFinite(t[k]))||t.x1<=t.x0||t.z1<=t.z0)throw Error('Invalid finite tread');
  return {...t};
 });
 // Canonical height/landing/whole-shoe clipping closures retain this array.
 terrain.tiles.splice(0,terrain.tiles.length,...tiles);
 if(!Number.isFinite(snapshot.start)||!Number.isFinite(snapshot.end)||snapshot.end<=snapshot.start)throw Error('Invalid terrain influence interval');
 terrain.start=snapshot.start;terrain.end=snapshot.end;
 const profile=snapshot.rootProfile;if(!Array.isArray(profile)||profile.length<2)throw Error('Root navigation ramp profile required');
 for(let i=0;i<profile.length;i++)if(!Number.isFinite(profile[i].z)||!Number.isFinite(profile[i].y)||(i&&profile[i].z<=profile[i-1].z))throw Error('Invalid root ramp profile');
 terrain.rootHeight=z=>{
  if(z<=profile[0].z)return profile[0].y;if(z>=profile.at(-1).z)return profile.at(-1).y;
  const i=profile.findIndex(p=>p.z>=z),a=profile[i-1],b=profile[i];return a.y+(b.y-a.y)*(z-a.z)/(b.z-a.z);
 };
 return terrain;
}
function canonicalPlan(run,settings,terrain,host){
 if(settings.terrain==='flat'||settings.height===0||host.noInfluence)return flatPlan(run,settings,terrain,host);
 // Nearby lower treads can remain in the world's broadphase after the whole
 // shoe has cleared them. Test the same per-frame influence used by K, retaining
 // the sampled poses/legs/shoes for the exact flat branch. An influencing sample
 // exits immediately and leaves the canonical terrain planner authoritative.
 const sampled=host.rootAtTime&&host.influence?zeroInfluenceInputs(run,host):null;
 if(sampled)return flatPlan(run,settings,terrain,host,sampled);
 return K.prepare(run,settings,{...host,terrain,capture:true});
}
function zeroInfluenceInputs(run,host){
 const fps=120,count=Math.round(run.duration*fps)+1,origin=host.origin||run.poses[0].points[0],raw=[],base=[],legs=[],offsets=[[],[]];
 for(let i=0;i<count;i++){
  const source=K.at(run,i/fps),p={...source,points:source.points.map(v=>add(v,[-origin[0],0,-origin[2]]))};
  const row=['L','R'].map(side=>K.stableLeg(p,run.names,side)),shoe=row.map(l=>K.geometry(p,l));
  if(host.influence(p,row,i/fps,(_pose,leg)=>shoe[leg.side==='L'?0:1])!==0)return null;
  raw.push(p);base.push({...p,points:p.points.map(v=>add(v,[0,host.rootAtTime(i/fps)[1],0]))});legs.push(row);
  offsets[0].push(shoe[0]);offsets[1].push(shoe[1]);
 }
 return {raw,base,legs,offsets};
}
// The accepted K solver explicitly returns the unmodified base pose when all
// terrain influence is disabled. Avoid constructing unused swing/contact
// optimizations in that exact branch; still retain real stance/history data.
function flatPlan(run,settings,terrain,host,sampled){
 const fps=120,count=Math.round(run.duration*fps)+1,origin=host.origin||run.poses[0].points[0];
 const moved=(p,d)=>({...p,points:p.points.map(v=>add(v,d))});
 const raw=sampled?.raw||Array.from({length:count},(_,i)=>moved(K.at(run,i/fps),[-origin[0],0,-origin[2]]));
 const base=sampled?.base||raw.map((p,i)=>moved(p,[0,host.rootAtTime?host.rootAtTime(i/fps)[1]:terrain.rootHeight(p.points[0][2]),0])),legs=sampled?.legs||raw.map(p=>['L','R'].map(s=>K.stableLeg(p,run.names,s)));
 const speed=(raw.at(-1).points[0][2]-raw[0].points[0][2])/run.duration,plans=[];
 for(let side=0;side<2;side++){
  const offsets=sampled?.offsets[side]||raw.map((p,i)=>K.geometry(p,legs[i][side])),flags=[];let stance=host.initialStance?.[side]??false;
  for(let i=0;i<count;i++){
   const l=legs[i][side],lo=Math.max(0,i-1),hi=Math.min(count-1,i+1),v=mul(sub(raw[hi].points[l.foot],raw[lo].points[l.foot]),fps/Math.max(1,hi-lo));
   const sole=raw[i].points[l.foot][1]+Math.min(...offsets[i].map(o=>o[1])),fast=Math.hypot(v[0],v[2]),s=host.speedAt?host.speedAt(i/fps):speed;
   stance=stance?sole<.045&&fast<s*.85:sole<.028&&fast<s*.58;flags.push(stance);
  }
  plans.push({targets:base.map((p,i)=>p.points[legs[i][side].foot]),contacts:new Array(count).fill(null),states:new Array(count).fill('NN'),rotations:legs.map(row=>({footQ:row[side].footQ,toeQ:row[side].toeQ})),offsets,limits:legs.map(row=>row[side].reach*.995),swings:[],flags});
 }
 const planned=base.map((p,i)=>({pelvisOffset:0,targets:legs[i].map(l=>p.points[l.foot]),planted:[false,false]}));
 const frames=base.map((pose,i)=>({pose,raw:pose,feet:legs[i].map(l=>({side:l.side,state:'NN',target:pose.points[l.foot],contact:null,error:0,penetration:0})),pelvisOffset:0,root:pose.points[0],influence:0}));
 return {frames,terrain,settings,metrics:{maxPenetration:0,maxReachError:0,maxPelvis:0,maxFlatDeviation:0,pins:[0,0]},speed,duration:run.duration,fps,checkpoint:{plans,planned,legs,base,raw},sample:t=>frames[Math.max(0,Math.min(frames.length-1,Math.round(t*fps)))]};
}
function cropSource(source,rows){
 const next={...source,roots:source.roots.slice(rows),poses:source.poses.slice(rows),rootYawDegrees:source.rootYawDegrees?.slice(rows)};
 next.duration=(next.poses.length-1)/source.fps;next.totalDuration=next.duration;next.directionMeta={...source.directionMeta,totalDuration:next.duration};return next;
}
function cropModel(model,ticks){
 if(!model)return model;const frames=model.frames.slice(ticks),c=model.checkpoint;
 const checkpoint=c?{plans:c.plans.map(plan=>Object.fromEntries(Object.entries(plan).map(([key,value])=>[key,key==='swings'?value.filter(s=>s.end>=ticks).map(s=>({...s,start:Math.max(0,s.start-ticks),end:s.end-ticks})):Array.isArray(value)?value.slice(ticks):value]))),planned:c.planned.slice(ticks),legs:c.legs.slice(ticks),base:c.base.slice(ticks),raw:c.raw.slice(ticks)}:null;
 return {...model,frames,checkpoint,duration:model.duration-ticks/model.fps,sample:t=>frames[Math.max(0,Math.min(frames.length-1,Math.round(t*model.fps)))]};
}
function boundary(previous,candidate,through,baseline){
 if(through<1)return {safe:true,positionM:0,velocityChangeMps:0,pinShiftM:0};
 const a=previous[through],p=previous[through-1],b=candidate[through],next=candidate[through+1];
 if(!a||!p||!b||!next)return {safe:false,reason:'Incomplete committed boundary'};
 let positionM=0,velocityChangeMps=0,pinShiftM=0,worstVelocityBone=-1,futureChangeM=0;
 for(let j=0;j<a.pose.points.length;j++){
  positionM=Math.max(positionM,length(sub(a.pose.points[j],b.pose.points[j])));
  const dv=length(sub(mul(sub(next.pose.points[j],a.pose.points[j]),120),mul(sub(a.pose.points[j],p.pose.points[j]),120)));
  if(dv>velocityChangeMps){velocityChangeMps=dv;worstVelocityBone=j;}
  if(baseline?.[through+1])futureChangeM=Math.max(futureChangeM,length(sub(next.pose.points[j],baseline[through+1].pose.points[j])));
 }
 for(let side=0;side<2;side++){
  const contact=a.feet[side].contact,proposed=b.feet[side].contact;
  if(contact)pinShiftM=Math.max(pinShiftM,proposed&&contact.surface===proposed.surface?length(sub(contact.point,proposed.point)):Infinity);
 }
 return {safe:positionM<=1e-8&&pinShiftM<=1e-8,positionM,velocityChangeMps,worstVelocityBone,futureChangeM,pinShiftM};
}
function create(options){
 const parents=options.parents,settings=K.sanitize(options.settings),infer=options.infer;
 if(!Array.isArray(parents)||parents.length!==26)throw Error('Complete rig parents required');
 let source=clone(options.source),terrainSnapshot=clone(options.terrain||null),model=null,pending=null,committed=[],through=-1,revision=0,cancelled=false,baseTick=options.sourceStartTick||0,initialStance,boundaryDirty=false,queuedApplied=[],initialHistoryPending=!!options.initialHistory;
 const origin=options.origin?.slice()||(options.terrain?.rootRows?[0,0,0]:source.roots[0].slice()),historySeconds=options.historySeconds??.75;
 const budget=options.maxCourseSeconds??8,lookahead=options.lookaheadSeconds??1.2;
 if(!(budget>.1&&budget<=30&&lookahead>.25&&lookahead<=budget))throw Error('Invalid bounded prediction horizon');
 const counters={plans:0,inferences:0,commits:0,planMilliseconds:0,predictionMilliseconds:0,cacheHits:0,rebases:0,appliedImports:0,initialHistoryFrames:0,actualHistoryRebases:0};
 through=baseTick-1;
 function prune(){
  const ticks=Math.max(0,Math.floor((through-baseTick-historySeconds*120)/4)*4);if(!ticks)return;
  if(model?.checkpoint)initialStance=model.checkpoint.plans.map(p=>p.flags?.[ticks-1]??false);
  source=cropSource(source,ticks/4);model=cropModel(model,ticks);committed=committed.slice(ticks);baseTick+=ticks;counters.rebases++;
 }
 function merge(incoming,startTick=0){
  if(startTick%4||startTick<0)throw Error('Source window must start on a30Hz boundary');
  let first=(startTick-baseTick)/4,next=incoming;
  if(first<0){next=cropSource(incoming,-first);first=0;}
  if(first>source.poses.length)throw Error('Predicted source window has a history gap');
  // Previously accepted raw history is retained; actual corrected history is
  // for predictor seeds, not a second terrain-corrected source to replay.
  const from=Math.max(first,Math.floor((through-baseTick)/4)+1),skip=from-first;
  if(skip>=next.poses.length)return source;
  const out={...source,...next,roots:[...source.roots.slice(0,from),...next.roots.slice(skip)],poses:[...source.poses.slice(0,from),...next.poses.slice(skip)]};
  if(source.rootYawDegrees||next.rootYawDegrees)out.rootYawDegrees=[...(source.rootYawDegrees||source.poses.map(()=>0)).slice(0,from),...(next.rootYawDegrees||next.poses.map(()=>0)).slice(skip)];
  out.duration=(out.poses.length-1)/out.fps;out.totalDuration=out.duration;out.directionMeta={...out.directionMeta,totalDuration:out.duration};return out;
 }
 // A slow worker may outlive its entire predicted tail. Rebuild the retained
 // boundary from frames the host actually displayed, not that obsolete tail.
 // Explicit checkpoints are the only permission to skip an old unacknowledged
 // prefix. Ordinary accept() still rejects even a single missing actual tick.
 function rebaseActual(update,checkpoint=false){
  const incoming=update.source,start=update.sourceStartTick??0;
  if(!incoming||incoming.fps!==30||start<0||start%4)throw Error('Actual-history rebase requires a30Hz prospective source');
  const records=new Map();
  if(!checkpoint){for(let i=0;i<committed.length;i++)if(committed[i])records.set(baseTick+i,committed[i]);for(const e of queuedApplied)records.set(e.tick,e.frame);}
  for(const e of update.acceptedFrames||[]){if(!Number.isInteger(e.tick)||records.has(e.tick)&&checkpoint)throw Error('Actual-history checkpoint ticks must be unique integers');records.set(e.tick,e.frame);}
  const ticks=[...records.keys()].sort((a,b)=>a-b),latest=ticks.at(-1);
  if(!Number.isInteger(latest))throw Error('Actual-history rebase has no displayed frames');
  if(checkpoint){
   const c=update.acceptedHistoryCheckpoint;
   if(!c||c.startTick!==ticks[0]||c.endTick!==latest)throw Error('Actual-history checkpoint bounds do not match its frames');
   for(let i=1;i<ticks.length;i++)if(ticks[i]!==ticks[i-1]+1)throw Error('Actual-history checkpoint has a gap');
  }
  const first=Math.max(0,Math.floor((latest-historySeconds*120)/4)*4);
  for(let tick=first;tick<=latest;tick++)if(!records.has(tick))throw Error('Actual-history rebase needs complete retained displayed history');
  const next={...source,...incoming,roots:[],poses:[],rootYawDegrees:[]},rows=[];
  let lastYaw;
  const unwrap=y=>lastYaw===undefined?y:lastYaw+((((y-lastYaw)+180)%360+360)%360-180);
  for(let tick=first;tick<=latest;tick+=4){
   const f=records.get(tick),raw=f?.raw,h=f?.rootHeading;
   if(!raw||raw.points?.length!==26||!raw.points.every(p=>p.length===3&&p.every(Number.isFinite))||raw.q?.length!==26||!raw.q.every(q=>q.length===4&&q.every(Number.isFinite))||!Array.isArray(h)||h.length!==3||!h.every(Number.isFinite)||Math.hypot(h[0],h[2])<1e-8)throw Error('Actual-history rebase requires exact raw30Hz poses and headings');
   const height=raw.points[0][1],flat=raw.points.map(p=>[p[0],p[1]-height,p[2]]),axes=raw.axes||raw.q.map(R.toAxes);
   next.roots.push(flat[0]);next.poses.push({points:flat.slice(1),axes:axes.slice(1)});
   lastYaw=unwrap(Math.atan2(h[0],h[2])*180/Math.PI);next.rootYawDegrees.push(lastYaw);
   rows.push({time:(tick-first)/120,position:raw.points[0].slice()});
  }
  const lastActual=first+(next.poses.length-1)*4;
  if(start>lastActual+4)throw Error('Prospective source still has a gap after actual-history rebase');
  const skip=Math.max(0,(lastActual+4-start)/4);
  for(let i=skip;i<incoming.poses.length;i++){
   next.roots.push(clone(incoming.roots[i]));next.poses.push(clone(incoming.poses[i]));
   const yaw=incoming.rootYawDegrees?.[i];if(!Number.isFinite(yaw))throw Error('Prospective source needs explicit headings after actual-history rebase');
   lastYaw=unwrap(yaw);next.rootYawDegrees.push(lastYaw);
  }
  next.duration=(next.poses.length-1)/30;next.totalDuration=next.duration;next.directionMeta={...next.directionMeta,totalDuration:next.duration};
  if(first+Math.round(next.duration*120)<=latest||next.duration>budget)throw Error('Rebased source must cover the actual boundary and a bounded prospective tail');
  const terrain=clone(update.terrain||terrainSnapshot);
  if(terrain?.rootRows){
   const rootStart=terrain.rootStartTick||0;
   for(const row of terrain.rootRows){const tick=rootStart+row.time*120;if(tick>lastActual+1e-7)rows.push({...row,time:(tick-first)/120});}
   terrain.rootStartTick=first;terrain.rootRows=rows;
  }
  // Validate the entire retained material/pose receipt before replacing state.
  // Boundary.importFrame performs the same per-pose checks during the solve.
  const actual=[];
  for(let tick=first;tick<=latest;tick++){
   const frame=records.get(tick);
   if(frame.pose?.points?.length!==26||!frame.pose.points.every(p=>p.length===3&&p.every(Number.isFinite))||frame.pose?.q?.length!==26||!frame.pose.q.every(q=>q.length===4&&q.every(Number.isFinite))||frame.feet?.length!==2||frame.feet.some(f=>!f||f.contact&&(typeof f.contact.surface!=='string'||!Array.isArray(f.contact.point)||f.contact.point.length!==3||!f.contact.point.every(Number.isFinite))))throw Error('Incomplete actual pose/contact checkpoint');
   actual.push({tick,frame:clone(frame)});
  }
  source=next;terrainSnapshot=terrain;baseTick=first;model=null;pending=null;committed=[];through=first-1;queuedApplied=actual;
  initialHistoryPending=false;initialStance=actual[0].frame.feet.map(f=>!!f.contact);boundaryDirty=true;counters.rebases++;counters.actualHistoryRebases++;
  return {...update,source:next,sourceStartTick:first,terrain,acceptedFrames:undefined,acceptedHistoryCheckpoint:undefined};
 }
 async function predict(update){
  validateRoots(update.roots);if(typeof infer!=='function')throw Error('Live replanning requires its native NN callback');
  const absoluteTime=update.time??Math.max(0,through/120),time=absoluteTime-baseTick/120,index=Math.round(time*30);
  if(Math.abs(index/30-time)>1e-8)throw Error('Recurrent source changes must begin on a30Hz boundary');
  if(index*4>through-baseTick+1)throw Error('Cannot skip actual source history');
  const end=(update.endTime??absoluteTime+lookahead)-baseTick/120;if(end>budget)throw Error('Prediction exceeds the bounded retained window');
  if(index<0||!update.seeds||update.seeds.length!==2)throw Error('Actual corrected previous/current30Hz poses are required');
  const next=clone(source),pair=update.seeds.map(encodePose),base=pair[1];
  next.roots=next.roots.slice(0,index+1);next.poses=next.poses.slice(0,index+1);next.rootYawDegrees=(next.rootYawDegrees||[]).slice(0,index+1);
  // Corrected current/history seeds enter the recurrent predictor. The prior
  // uncorrected planner source stays intact: applying terrain to an already
  // corrected source would double the pelvis/foot correction at this boundary.
  const last=Math.ceil(end*30-1e-8),begin=performance.now();let current=base;
  for(let j=index;j<last;j++){
   if(cancelled)return null;
   const rows=Array.from({length:10},(_,k)=>rowAt(update.roots,baseTick/120+(j+k-1)/30));
   const request={policy:'run',gait:settings.gait,direction:next.direction||settings.direction,names:['root',...next.names],drawn:false,frames:2,roots:rows.map(r=>r.position),rootYawDegrees:rows.map(r=>r.yaw),...(j===index?{reset:true,seeds:pair}:{})};
   const result=await infer(request);counters.inferences++;
   if(!result?.pose?.points||result.pose.points.length!==26)throw Error('Invalid predicted NN pose');
   current=result.pose;next.roots.push(current.points[0].slice());next.poses.push({points:current.points.slice(1),axes:current.axes.slice(1)});next.rootYawDegrees.push(rows[2].yaw);
  }
  next.duration=last/30;next.totalDuration=next.duration;next.directionMeta={...next.directionMeta,totalDuration:next.duration};
  counters.predictionMilliseconds+=performance.now()-begin;return next;
 }
 async function plan(update={}){
  if(cancelled)throw Error('Live Foot IK planner is disabled');
  if(update.acceptedHistoryCheckpoint)update=rebaseActual(update,true);
  else{
   if(update.acceptedFrames?.length)accept(update.acceptedFrames);
   if(update.source){
    const first=((update.sourceStartTick||0)-baseTick)/4,end=(update.sourceStartTick||0)+(update.source.poses.length-1)*4;
    const prunedBase=baseTick+Math.max(0,Math.floor((through-baseTick-historySeconds*120)/4)*4);
    if(first>source.poses.length||end-prunedBase>budget*120)update=rebaseActual(update);
   }
  }
  if(model&&!boundaryDirty&&!queuedApplied.length&&!update.source&&!update.roots&&!update.terrain&&!update.settings){counters.cacheHits++;return {ready:true,through:through,generatedThrough:baseTick/120+model.duration,cached:true};}
  if(model&&!boundaryDirty&&!queuedApplied.length&&update.source&&(update.sourceStartTick||0)===baseTick&&!update.roots&&!update.terrain&&!update.settings&&JSON.stringify(update.source)===JSON.stringify(source)){counters.cacheHits++;return {ready:true,through,generatedThrough:baseTick/120+model.duration,cached:true};}
  if(model)prune();
  const nextSettings=update.settings?K.sanitize({...settings,...update.settings}):settings;
  const nextSource=update.source?merge(update.source,update.sourceStartTick):update.roots?await predict(update):source;if(cancelled||!nextSource)return null;
  if(nextSource.duration>budget)throw Error('Source exceeds the bounded retained course');
  const nextTerrain=update.terrain?clone(update.terrain):terrainSnapshot,terrain=terrainWithSnapshot(nextSettings,nextTerrain),start=performance.now();
  // Both boundary passes read the same raw NN course. Decoding computes only
  // its immutable FK/local-pose carrier; each pass still owns fresh leg, pin,
  // trajectory and displayed-history state.
  const nextRun=K.decode(nextSource,parents);
  const host=update.boundary===false?{capture:true}:Boundary.create(model,through-baseTick);host.origin=origin;host.initialStance=initialStance;
  const decorateHost=value=>{
   if(!nextTerrain?.rootRows)return value;
   const root=LiveTerrain.rootSampler(nextTerrain.rootRows),offset=(baseTick-(nextTerrain.rootStartTick||0))/120;
   value.rootAtTime=t=>root.at(t+offset);value.travelAt=t=>root.direction(t+offset);value.speedAt=t=>root.speed(t+offset);
   value.headingAt=t=>K.rootHeading(nextRun,t,nextSettings);
   value.influence=(p,legs,t,geometry=K.geometry)=>!nextSettings.enabled||nextSettings.terrain==='flat'||nextSettings.height===0?0:terrain.influence(p,legs,value.rootAtTime(t)[1],geometry);
   value.noInfluence=!nextSettings.enabled||terrain.tiles.every(tile=>!tile.shaped||nextTerrain.rootRows.every(row=>Math.abs(tile.y-row.position[1])<=.005));
   return value;
  };
  if(model&&(update.roots||update.source)){
   const predicted=nextRun;
   const rootAt=time=>{const f=Math.max(0,Math.min(nextSource.roots.length-1,time*nextSource.fps)),i=Math.min(nextSource.roots.length-2,Math.floor(f)),u=f-i;return u<1e-9?nextSource.roots[i]:add(nextSource.roots[i],mul(sub(nextSource.roots[i+1],nextSource.roots[i]),u));};
   host.speedAt=time=>{const a=Math.max(0,time-1/120),b=Math.min(predicted.duration,time+1/120);return length(sub(rootAt(b),rootAt(a)))/(b-a);};
   host.headingAt=time=>K.rootHeading(predicted,time,nextSettings);
   host.yawAt=time=>{
    const angles=predicted.rootYawDegrees;if(!angles?.length)return K.commandYaw(nextSettings,time,predicted.directionMeta?.commandSpeed||0);
    const f=Math.max(0,Math.min(angles.length-1,time*predicted.fps)),i=Math.floor(f);return angles[i]+((angles[i+1]??angles[i])-angles[i])*(f-i);
   };
  }
  decorateHost(host);
  let checkpointSeeded=false;
  // Only discard a first-pass continuation when every retained prefix sample
  // will be replaced by actual history before the final canonical solve.
  const initialPrefix=!model&&initialHistoryPending&&options.initialHistory.previousTick===baseTick;
  let prefixThrough=initialPrefix?options.initialHistory.currentTick:through;
  let completePrefix=initialPrefix||prefixThrough<baseTick;
  if(!completePrefix&&model){completePrefix=true;for(let i=0;i<=prefixThrough-baseTick;i++)if(!committed[i]){completePrefix=false;break;}}
  for(const entry of queuedApplied)if(entry.tick>prefixThrough){if(entry.tick!==prefixThrough+1){completePrefix=false;break;}prefixThrough=entry.tick;}
  if(initialPrefix||(queuedApplied.length&&completePrefix&&prefixThrough>=baseTick)){
   host.initialCheckpoint=c=>{
    checkpointSeeded=true;
    const planned=c.base.map((p,i)=>({pelvisOffset:0,targets:c.legs[i].map(l=>p.points[l.foot]),planted:[false,false]}));
    const frames=c.base.map((pose,i)=>({pose,raw:pose,feet:c.legs[i].map(l=>({side:l.side,state:'NN',target:pose.points[l.foot],contact:null,error:0,penetration:0})),pelvisOffset:0,root:pose.points[0]}));
    return {frames,terrain:c.terrain,settings:c.settings,speed:c.speed,duration:nextRun.duration,fps:c.fps,checkpoint:{plans:c.plans,planned,legs:c.legs,base:c.base,raw:c.raw}};
   };
  }
  let candidate=canonicalPlan(nextRun,nextSettings,terrain,host),consolidatedInitial=false;counters.plans++;
  if(!model&&initialHistoryPending){
   const h=options.initialHistory;
   if(!Number.isInteger(h.previousTick)||!Number.isInteger(h.currentTick)||h.previousTick<baseTick||h.currentTick<=h.previousTick||h.currentTick-baseTick>=candidate.frames.length)throw Error('Initial actual history must fit the source window');
   model=candidate;
   for(let tick=h.previousTick;tick<=h.currentTick;tick++){
    const u=(tick-h.previousTick)/(h.currentTick-h.previousTick),q=u===0?h.previous.q:u===1?h.current.q:h.previous.q.map((v,j)=>R.qslerp(v,h.current.q[j],u));
    const pose={points:u===0?h.previous.points:u===1?h.current.points:h.previous.points.map((p,j)=>add(p,mul(sub(h.current.points[j],p),u))),q,axes:q.map(R.toAxes)};
    Boundary.importFrame(model,tick-baseTick,{pose},['root',...nextSource.names]);counters.initialHistoryFrames++;
   }
   through=h.currentTick;committed=model.frames.slice(0,through-baseTick+1);
   // These samples were already displayed by the caller. They seed a true
   // current/history boundary; they were never inferred from this new plan.
   const seeded=Boundary.create(model,through-baseTick);seeded.origin=origin;seeded.initialStance=initialStance;decorateHost(seeded);
   // Queued actual receipts are a second part of this same initial boundary.
   // Import them before solving its continuation: the intermediate plan only
   // copied these preserved past fields, then was immediately discarded.
   if(!queuedApplied.length){
    candidate=canonicalPlan(nextRun,nextSettings,terrain,seeded);counters.plans++;
    host.diagnostics=seeded.diagnostics;
   }else consolidatedInitial=true;
   initialHistoryPending=false;
  }
  if(queuedApplied.length){
   const latest=queuedApplied.at(-1).tick;
   if(latest-baseTick>=candidate.frames.length)throw Error('New live source does not cover the latest actual displayed history');
   for(let i=0;i<=through-baseTick;i++)if(committed[i])Boundary.importFrame(candidate,i,committed[i],['root',...nextSource.names]);
   model=candidate;const actual=queuedApplied;queuedApplied=[];accept(actual);
   const seeded=Boundary.create(model,through-baseTick);seeded.origin=origin;seeded.initialStance=initialStance;decorateHost(seeded);
   candidate=canonicalPlan(nextRun,nextSettings,terrain,seeded);counters.plans++;host.diagnostics=seeded.diagnostics;
  }
  if(options.handoff!==false){
   const run=nextRun,request=H.requestFor(candidate,run);
   if(request){
    if(typeof infer!=='function')throw Error('Terrain exit requires real NN continuation');
    const reply=await infer(request.request);counters.inferences+=request.request.frames-1;
    if(cancelled)return null;candidate=H.apply(candidate,run,request,reply);
   }
  }
  counters.planMilliseconds+=performance.now()-start;
  // The solver consumes actual accepted history as initial conditions. Its
  // newly calculated past is not a second account of what the player saw.
  // Keep those authoritative frames/checkpoints and evaluate the new tail.
  if(model)for(let i=0;i<=through-baseTick;i++)if(committed[i])Boundary.importFrame(candidate,i,committed[i],['root',...nextSource.names]);
  const continuity=boundary(committed,candidate.frames,through-baseTick,model?.frames);
  if(consolidatedInitial)continuity.futureChangeReference='pre-boundary candidate';
  if(checkpointSeeded)continuity.futureChangeReference='raw boundary checkpoint';
  if(host.diagnostics)continuity.constraints=host.diagnostics;
  pending={candidate,source:nextSource,terrain:nextTerrain,settings:nextSettings,continuity};
  // A changed future can move an already accepted planted target. Never hide
  // that mismatch by snapping, silently changing the committed past, or calling
  // it1:1. The native owner must retain its current safe plan while repairing
  // or deferring this boundary; diagnostics identify the exact discrepancy.
  if(!continuity.safe)return {ready:false,revision,continuity,generatedThrough:baseTick/120+candidate.duration};
  model=candidate;source=nextSource;terrainSnapshot=nextTerrain;Object.assign(settings,nextSettings);pending=null;boundaryDirty=false;revision++;
  return {ready:true,revision,continuity,generatedThrough:baseTick/120+model.duration};
 }
 function commit(index=through+1){
  if(cancelled)throw Error('Live Foot IK planner is disabled');
  if(index<baseTick)throw Error('Live Foot IK retains bounded history; use course mode for replay');
  if(index<=through)return committed[index-baseTick];
  if(index!==through+1)throw Error('Commit every120Hz frame in sequence');
  if(!model?.frames[index-baseTick])throw Error('Prospective Foot IK tail is not ready');
  const frame=model.frames[index-baseTick];committed.push(frame);through=index;counters.commits++;return frame;
 }
 function accept(entries){
  if(cancelled)throw Error('No live plan for importing applied frames');
  let last=-1;const sorted=entries.slice().sort((a,b)=>a.tick-b.tick);
  for(const entry of sorted){
   if(!Number.isInteger(entry.tick)||entry.tick===last)throw Error('Applied frame ticks must be unique integers');last=entry.tick;
   if(entry.tick<baseTick)continue;
   if(!model||entry.tick-baseTick>=model.frames.length||queuedApplied.length){
    const previous=queuedApplied.at(-1)?.tick??through;
    if(model&&entry.tick>previous+1)throw Error('Applied frame history has a gap; provide every120Hz frame between consumed samples');
    const at=queuedApplied.findIndex(value=>value.tick===entry.tick);if(at>=0)queuedApplied[at]=copyEntry(entry);else queuedApplied.push(copyEntry(entry));
    continue;
   }
   if(entry.tick>through+1)throw Error('Applied frame history has a gap; provide every120Hz frame between consumed samples');
   const index=entry.tick-baseTick;if(JSON.stringify(model.frames[index])!==JSON.stringify(entry.frame))boundaryDirty=true;
   const frame=Boundary.importFrame(model,index,entry.frame,['root',...source.names]);
   committed[index]=frame;through=Math.max(through,entry.tick);counters.appliedImports++;
  }
  return {through,imported:sorted.length};
 }
 function copyEntry(entry){return {tick:entry.tick,frame:clone(entry.frame)};}
 return {plan,commit,accept,frame:index=>index<baseTick?null:index<=through?committed[index-baseTick]:model?.frames[index-baseTick],get source(){return clone(source);},get pending(){return pending?{continuity:pending.continuity,duration:pending.candidate.duration}:null;},get status(){return {enabled:!cancelled,through,baseTick,revision,generatedThrough:model?baseTick/120+model.duration:-1,retainedFrames:committed.length,queuedAppliedFrames:queuedApplied.length,lookaheadSeconds:lookahead,maxCourseSeconds:budget,...counters};},cancel(){cancelled=true;model=null;pending=null;source=null;committed=[];queuedApplied=[];}};
}
module.exports={create,boundary,terrainWithSnapshot,rowAt,flatPlan};
