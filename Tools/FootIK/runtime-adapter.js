/* Native host protocol. Lab algorithms own all foot/slide mathematics. */
(function(root){
'use strict';
const R=FootIKRequire('recovery.js'),K=FootIKRequire('footik.js'),H=FootIKRequire('handoff.js'),F=FootIKRequire('surface.js'),C=FootIKRequire('surface-coupling.js'),S=FootIKRequire('support.js');
const {add,sub,mul,dot,length,unit,rotate,qm,qinv,qslerp}=R,up=[0,1,0],identity=[0,0,0,1];
const LivePlanner=FootIKRequire('live-stair-planner.cjs');
const LiveExit=FootIKRequire('live-exit.cjs');
const LiveJoin=FootIKRequire('live-join.cjs');
let state=null;
// Array-shaped chronological ring: absolute length preserves canonical frame
// clocks, while only the last requested entries occupy memory during gameplay.
function history(capacity){let size=0;const rows=new Array(capacity);return {get length(){return size;},push(value){rows[size++%capacity]=value;return size;},at(index){const i=index<0?size+index:index;return i<Math.max(0,size-capacity)||i>=size?undefined:rows[i%capacity];},slice(start=0,end=size){const out=[];for(let i=Math.max(0,size-capacity,start);i<Math.min(end,size);i++)out.push(rows[i%capacity]);return out;},toJSON(){return this.slice();}};}
function finite(x,label){if(!Number.isFinite(+x))throw Error('Invalid '+label);return +x;}
function vector(v,label,n=3){if(!Array.isArray(v)||v.length!==n||!v.every(Number.isFinite))throw Error('Invalid '+label);return v.slice();}
function pose(value,names){
 if(!value||!Array.isArray(value.points)||value.points.length!==names.length)throw Error('Foot IK requires all '+names.length+' pose points');
 const points=value.points.map((v,i)=>vector(v,'pose point '+i));
 const q=value.q?value.q.map((v,i)=>vector(v,'pose rotation '+i,4)):value.axes?.map(R.fromAxes);
 if(!q||q.length!==names.length||q.some(v=>v.some(x=>!Number.isFinite(x))))throw Error('Foot IK requires complete pose rotations');
 const axes=value.axes?value.axes.map((basis,i)=>{if(!Array.isArray(basis)||basis.length!==3)throw Error('Invalid pose basis '+i);return basis.map((axis,j)=>vector(axis,'pose axis '+i+':'+j));}):q.map(R.toAxes);
 return {points,q,axes};
}
function runOf(a){
 if(a.source){const parents=a.parents||a.source.parents;if(!Array.isArray(parents))throw Error('Foot IK source parents required');return K.decode(a.source,parents);}
 const {names,parents}=a;if(!Array.isArray(names)||names.length!==26||names[0]!=='root'||!Array.isArray(parents)||parents.length!==names.length)throw Error('Foot IK requires the complete 26-bone rig');
 const seeds=a.seeds;if(!Array.isArray(seeds)||seeds.length!==2)throw Error('Foot IK needs previous/current source poses');
 const previous=pose(seeds[0],names),current=pose(seeds[1],names),speed=a.speed==null?length(sub(current.points[0],previous.points[0]))*30:finite(a.speed,'command speed');
 const duration=1/30,run={names:names.slice(),parents:parents.slice(),fps:30,duration,totalDuration:duration,periodSeconds:1,direction:a.settings?.direction||'forward',directionMeta:{commandSpeed:speed,facingDegrees:0,totalDuration:duration},referenceHeight:a.height==null?current.points[names.indexOf('pelvis')][1]-current.points[0][1]:finite(a.height,'reference height'),poses:[previous,current]};
 run.locals=run.poses.map(p=>R.localize(p.points,p.q,parents));run.travel=[0,speed/30];return run;
}
function describe(model){return {frames:model.frames.length,generatedThrough:model.generatedThrough??(model.frames.length-1)/120,fps:model.fps||120,duration:model.duration,metrics:model.metrics,events:model.events||[],coupling:model.coupling||null};}
function dispose(){if(state?.session)state.session.close();if(state?.generator)state.generator.return();if(state?.planner)state.planner.cancel();state=null;return {enabled:false};}
function nn(request,index){
 if(state?.policySteps){const result=state.policySteps[index];if(!result)throw Error('Missing Foot IK policy reply '+index);return result;}
 if(typeof root.__footikNN!=='function')throw Error('Foot IK requires native NN callback for coupled mode');
 const result=JSON.parse(root.__footikNN(JSON.stringify(request)));return result;
}
function prepare(a){
 dispose();const run=runOf(a),settings=K.sanitize(a.settings||{});state={kind:'fixture',run,settings,policySteps:a.policySteps||null};
 if(a.policySteps||a.coupled){state.session=C.createSession(run,settings,nn);state.model=state.session.model;state.session.extend(a.endTime??state.model.duration);}
 else state.model=settings.terrain==='incline'||Array.isArray(settings.platformLayouts[settings.terrain])?F.prepare(run,settings):a.handoff?H.prepare(run,settings,request=>a.handoffReply||nn(request,0)):K.prepare(run,settings);
 return describe(state.model);
}
function plane(record){
 if(record.position&&record.rotation&&record.size){const p=S.platformSurface(record);p.finiteSlab=true;return p;}
 const origin=vector(record.origin,'surface origin'),normal=unit(vector(record.normal,'surface normal'));
 if(length(normal)<.9)throw Error('Surface normal is zero');
 let right=record.tangent?vector(record.tangent,'surface tangent'):(Math.abs(normal[0])<.8?[1,0,0]:[0,0,1]);right=unit(sub(right,mul(normal,dot(right,normal))));
 if(length(right)<.9)throw Error('Surface tangent is parallel to normal');
 const forward=unit(R.cross(right,normal)),bounds=vector(record.bounds||[-1000,1000,-1000,1000],'surface bounds',4);
 const p=S.rectangle(String(record.id),origin,right,forward,bounds,record.thickness==null?.2:Math.max(.001,finite(record.thickness,'surface thickness')));p.finiteSlab=true;return p;
}
function worldTerrain(records,rootRecords,includeNavigation=false){
 let surfaces=[],navigation=[],revision=null,removed=new Map(),rootReference=null;const fallback=S.rectangle('__empty',[0,-10000,0],[1,0,0],[0,0,1],[-1,1,-1,1],.2);
 const combined=()=>includeNavigation?[...new Map([...surfaces,...navigation].map(p=>[p.id,p])).values()]:surfaces;
 const t={kind:'world',hostWorld:true,custom:true,editedRoute:true,start:0,end:Infinity,original:[],tiles:[],get allSurfaces(){return [...new Map([...surfaces,...navigation].map(p=>[p.id,p])).values()];},get surfaces(){return combined();},resolveRootSurface(id){const p=removed.get(id)||(rootReference?.id===id?rootReference:null);if(p)rootReference=p;return p;},get floor(){return surfaces.find(x=>x.normal[1]>.7)||surfaces[0]||fallback;},get slope(){return surfaces.find(x=>x.normal[1]<.7)||surfaces[0]||fallback;},setTime(){},surfacesAt(){return surfaces;},rootSurfaces(){return navigation;},rootHeight(){return 0;},pick(p){let best=null;for(const surface of surfaces){const point=surface.closest(p),distance=length(sub(p,point));if(!best||distance<best.distance)best={surface,point,distance};}return best;},pickRoot(mass,bodyUp,height){let best=null;for(const surface of navigation){const p=surface.local(mass),radius=Math.max(.22,height*Math.max(0,dot(bodyUp,surface.normal))*.93);if(p[1]<-surface.box.dims[1]-.05)continue;const tangent=length(sub(surface.project(mass),surface.closest(mass))),distance=Math.hypot(p[1]-radius,tangent);if(!best||distance<best.distance)best={surface,distance};}return best?.surface||null;},floorFor(p,offsets){const hit=this.pick(p);return hit?p[1]-Math.min(...offsets.map(o=>dot(sub(add(p,o),hit.point),hit.surface.normal))):p[1];},update(next,roots,tag){if(tag!=null&&tag===revision)return;const update=(old,list)=>list.map(record=>{if(!record||record.id==null)throw Error('Surface has no stable id');const value=plane(record),before=old.find(x=>x.id===value.id);if(before){Object.assign(before,value);return before;}return value;});const prior=[...surfaces,...navigation];surfaces=update(surfaces,next||[]);navigation=roots?update(navigation,roots):surfaces;const ids=new Set([...surfaces,...navigation].map(p=>p.id));removed=new Map(prior.filter(p=>!ids.has(p.id)).map(p=>[p.id,p]));revision=tag;}};
 t.update(records,rootRecords);return t;
}
function sampleWindow(input,time,start){
 const rows=input.futureRoots;
 if(!Array.isArray(rows)||!rows.length)return null;
 const dt=input.rootInterval||1/30,first=rows[0].time??start-dt,index=(time-first)/dt,i=Math.max(0,Math.min(rows.length-1,Math.floor(index))),u=Math.max(0,Math.min(1,index-i)),a=rows[i],b=rows[Math.min(i+1,rows.length-1)];
 let yawA=a.yaw??a.yawDegrees,yawB=b.yaw??b.yawDegrees;
 if(yawA==null&&a.heading)yawA=Math.atan2(a.heading[0],a.heading[2])*180/Math.PI;if(yawB==null&&b.heading)yawB=Math.atan2(b.heading[0],b.heading[2])*180/Math.PI;
 let yaw=yawA;if(yawA!=null&&yawB!=null){let d=(yawB-yawA)%360;if(d>180)d-=360;if(d<-180)d+=360;yaw=yawA+d*u;}
 const position=a.position&&b.position?add(a.position,mul(sub(b.position,a.position),u)):null;
 return {yaw,position,a,b,dt};
}
function rootInit(a){
 dispose();const settings=F.settings(a.settings||{}),height=finite(a.height??.9,'root calibration height'),speed=finite(a.speed??0,'root speed'),gravity=finite(a.gravity??9.81,'gravity');
 if(height<=0||gravity<0)throw Error('Invalid root calibration');
 const terrain=a.canonicalTerrain?F.createTerrain(settings,a.extent??100):worldTerrain(a.surfaces||[],a.rootSurfaces,true);
 const s={kind:'root',settings,terrain,height,speed,gravity,input:a,tick:Math.round((a.time||0)*120),contexts:[],events:[],metrics:F.createMetrics(),supports:[],lastReceipt:null};state=s;s.headingTime=s.tick/120;
 const controller=a.canonicalTerrain&&!a.travelVelocity?undefined:(time,normal)=>{
  let velocity=s.input.travelVelocity||[0,0,s.speed];
  if(s.input.futureDrive?.length){const rows=s.input.futureDrive;let i=0;while(i+1<rows.length&&rows[i+1].time<=time)i++;const x=rows[i],y=rows[Math.min(i+1,rows.length-1)],u=y.time>x.time?Math.max(0,Math.min(1,(time-x.time)/(y.time-x.time))):0;velocity=add(x.velocity,mul(sub(y.velocity,x.velocity),u));}
  const horizontal=[velocity[0],0,velocity[2]],magnitude=length(horizontal);if(magnitude<1e-12)return [0,0,0];
  const mapped=rotate(R.fromTo(up,normal),mul(horizontal,1/magnitude)),direction=unit(sub(mapped,mul(normal,dot(mapped,normal))));return mul(direction,magnitude);
 };
 let saved=a.snapshot||null;
 if(a.root){
  const value=a.root,position=vector(value.position,'root position'),velocity=vector(value.velocity||[0,0,0],'root velocity'),normal=unit(vector(value.normal||up,'root normal'));
  const bodyQ=value.bodyRotation?vector(value.bodyRotation,'root body rotation',4):F.bodyRotation(normal,settings.upright),bodyUp=rotate(bodyQ,up),mass=add(position,mul(normal,Math.max(.22,height*Math.max(0,dot(bodyUp,normal)))));
  const surface=(value.surface&&terrain.allSurfaces.find(x=>x.id===value.surface))||terrain.pickRoot?.(mass,bodyUp,height)||terrain.floor;
  saved={bodyQ,normal,mass,velocity,wallTime:0,lastSupportTime:a.lastSupportTime??s.tick/120,motionSurface:surface.id,previousCourse:surface.id,previousCollisions:[],slide:null,previousVerticalSpeed:null,...saved};
 }
 s.parameters={s:settings,terrain,height,speed,gravity,enabled:settings.enabled,metrics:s.metrics,events:s.events,controller};
 s.motion=F.createRootMotion(s.parameters,saved);s.beforeBegin=s.motion.snapshot();s.beforeBeginEvents=s.events.length;
 s.context=s.motion.begin(s.tick/120);s.virtualRoot=vector(a.virtualRoot||[0,0,0],'virtual root');s.contexts.push({tick:s.tick,context:s.context,virtualRoot:s.virtualRoot});
 s.previousRoot=a.previousRoot?vector(a.previousRoot,'previous root'):sub(s.context.base,mul(s.context.velocity,1/30));
 s.previousVirtualRoot=a.previousVirtualRoot?vector(a.previousVirtualRoot,'previous virtual root'):sub(s.virtualRoot,C.transport({...s.context,base:s.previousRoot},s.context));
 return rootStatus();
}
function rootInput(a){
 if(state?.kind!=='root')throw Error('Root solver is disabled');const s=state;
 let invalidated=false;
 if(a.settings){const next=F.settings({...s.settings,...a.settings});invalidated=JSON.stringify(next)!==JSON.stringify(s.settings);Object.assign(s.settings,next);s.parameters.enabled=s.settings.enabled;}
 if(a.surfaces){if(!s.terrain.update)throw Error('Canonical terrain fixture cannot accept world geometry updates');if(a.surfaceRevision==null||a.surfaceRevision!==s.surfaceRevision){s.terrain.update(a.surfaces,a.rootSurfaces,a.surfaceRevision);s.surfaceRevision=a.surfaceRevision;invalidated=true;}}
 if(a.travelVelocity)vector(a.travelVelocity,'root controller velocity');
 if(a.rootYawDegrees){if(a.rootYawDegrees.length!==10||!a.rootYawDegrees.every(Number.isFinite))throw Error('Root heading window needs previous/current plus8future angles');s.headingTime=s.tick/120;}
 if(a.futureDrive){for(let i=0;i<a.futureDrive.length;i++){const row=a.futureDrive[i];finite(row.time,'future root command time');vector(row.velocity,'future root drive');if(i&&row.time<=a.futureDrive[i-1].time)throw Error('Root drive times must increase');}}
 s.input={...s.input,...a};
 if(a.supports)s.supports=rootSupports(a.supports,s);
 if(invalidated){s.events.length=s.beforeBeginEvents;s.motion=F.createRootMotion(s.parameters,s.beforeBegin);s.context=s.motion.begin(s.tick/120);const previous=s.contexts.at(-2);if(previous)s.virtualRoot=add(previous.virtualRoot,C.transport(previous.context,s.context));s.contexts[s.contexts.length-1]={tick:s.tick,context:s.context,virtualRoot:s.virtualRoot};}
 return s;
}
function rootSupports(values,s){
 if(!Array.isArray(values))throw Error('Root support contacts must be an array');
 return values.map(value=>{const id=typeof value.surface==='string'?value.surface:value.surface?.id,surface=s.terrain.allSurfaces.find(p=>p.id===id);if(!surface)throw Error('Unknown root support material '+id);return {surface,point:vector(value.point,'root support point'),normal:value.normal?vector(value.normal,'root support normal'):surface.normal};});
}
function rootRow(c){return {time:c.time,position:c.base,velocity:c.velocity,normal:c.normal,bodyRotation:c.rootQ,bodyUp:c.bodyUp,gaitRotation:c.surfaceQ,mass:c.mass,pinNormal:c.pinNormal,surface:c.nextSurface.id,courseSurface:c.courseSurface.id,hasFloor:c.hasFloor,useEdited:c.useEdited,...(c.slide?{slide:c.slide}:{})};}
function rootYaw(s,time){
 const angles=s.input.rootYawDegrees;if(!angles)return s.input.yaw??0;
 const f=Math.max(0,Math.min(angles.length-1,(time-s.headingTime)*30+1)),nearest=Math.round(f);if(Math.abs(f-nearest)<1e-9)return angles[nearest];const i=Math.floor(f);return angles[i]+((angles[i+1]??angles[i])-angles[i])*(f-i);
}
function rootStatus(){
 if(state?.kind!=='root')return {enabled:false};const s=state;
 return {enabled:true,kind:'root',tick:s.tick,time:s.tick/120,root:{...rootRow(s.context),virtualRoot:s.virtualRoot,yaw:rootYaw(s,s.tick/120)},virtualRoot:s.virtualRoot,receipt:s.lastReceipt,snapshot:s.motion.snapshot(),metrics:s.metrics,events:s.events};
}
function rootForecast(a){
 const s=rootInput(a),ticks=a.ticks==null?32:Math.round(finite(a.ticks,'root forecast ticks'));if(ticks<0||ticks>360)throw Error('Root forecast must contain0..360ticks');
 const contexts=s.motion.forecast(s.context,s.supports,ticks),prior=s.contexts.find(row=>row.tick===s.tick-4),virtual=[s.virtualRoot];
 for(let i=1;i<contexts.length;i++)virtual.push(add(virtual[i-1],C.transport(contexts[i-1],contexts[i])));
 const result=contexts.map((c,i)=>({...rootRow(c),virtualRoot:virtual[i],yaw:rootYaw(s,c.time)}));
 const roots=[prior?.context.base||s.previousRoot,s.context.base],virtualRoots=[prior?.virtualRoot||s.previousVirtualRoot,s.virtualRoot],rootYawDegrees=[rootYaw(s,s.tick/120-1/30),rootYaw(s,s.tick/120)];
 for(let i=4;i<=ticks;i+=4){roots.push(result[i].position);virtualRoots.push(virtual[i]);rootYawDegrees.push(result[i].yaw);}
 return {tick:s.tick,time:s.tick/120,roots,virtualRoots,rootYawDegrees,frames:result,virtualRoot:s.virtualRoot,snapshot:s.motion.snapshot()};
}
function rootStep(a){
 const s=rootInput(a),ticks=a.ticks==null?2:Math.round(finite(a.ticks,'root step ticks'));if(ticks<1||ticks>120)throw Error('Root step must contain1..120ticks');const receipts=[],frames=[{...rootRow(s.context),virtualRoot:s.virtualRoot,yaw:rootYaw(s,s.tick/120)}];
 for(let i=0;i<ticks;i++){
  const supports=a.supportsByTick?rootSupports(a.supportsByTick[i]||[],s):s.supports;
  const receipt=s.motion.finish(s.context,supports);receipts.push(receipt);s.lastReceipt=receipt;
  const previous=s.context;s.tick++;s.beforeBegin=s.motion.snapshot();s.beforeBeginEvents=s.events.length;s.context=s.motion.begin(s.tick/120);s.virtualRoot=add(s.virtualRoot,C.transport(previous,s.context));s.contexts.push({tick:s.tick,context:s.context,virtualRoot:s.virtualRoot});if(s.contexts.length>5)s.contexts.shift();
  frames.push({...rootRow(s.context),virtualRoot:s.virtualRoot,yaw:rootYaw(s,s.tick/120)});
 }
 if(s.events.length>128){const removed=s.events.length-128;s.events.splice(0,removed);s.beforeBeginEvents=Math.max(0,s.beforeBeginEvents-removed);}
 return {...rootStatus(),receipts,frames};
}
function externalSurfaceContext(s,time){
 const rows=s.input.rootFrames;if(!Array.isArray(rows)||!rows.length)throw Error('External surface pose requires real root contexts and their forecast');
 const tick=Math.round(time*120),row=rows.find(x=>Math.round(x.time*120)===tick);if(!row)throw Error('Missing external root context at tick'+tick);
 const navigation=s.terrain.rootSurfaces(),surface=navigation.find(p=>p.id===row.surface)||s.terrain.allSurfaces.find(p=>p.id===row.surface)||s.terrain.resolveRootSurface?.(row.surface),course=navigation.find(p=>p.id===row.courseSurface)||s.terrain.allSurfaces.find(p=>p.id===row.courseSurface)||surface;
 if(!surface)throw Error('Unknown external root surface '+row.surface);
 const normal=vector(row.normal,'external root normal'),rootQ=vector(row.bodyRotation,'external root body rotation',4),bodyUp=row.bodyUp||rotate(rootQ,up),surfaceQ=row.gaitRotation||R.fromTo(up,normal);
 return {time,hasFloor:row.hasFloor??s.terrain.surfaces.some(x=>x.id==='entry'),useEdited:row.useEdited??true,nextSurface:surface,courseSurface:course,pinNormal:row.pinNormal||normal,normal,rootQ,bodyUp,surfaceQ,base:vector(row.position,'external root position'),mass:vector(row.mass,'external root mass'),velocity:vector(row.velocity,'external root velocity'),...(row.slide?{slide:row.slide}:{})};
}
function liveSurfaceInit(a){
 dispose();const run=runOf(a),settings=F.settings(a.settings||{}),height=finite(a.height??run.referenceHeight??run.directionMeta?.referenceHeight??.9,'surface rig height');
 run.referenceHeight=height;run.directionMeta={...run.directionMeta,commandSpeed:a.speed??run.directionMeta?.commandSpeed??2};run.totalDuration=1e9;
 const terrain=a.canonicalTerrain?F.createTerrain(settings,a.extent??100):worldTerrain(a.surfaces||[],a.rootSurfaces);
 const s={kind:'externalSurface',run,sourceRun:run,settings,terrain,height,input:a,tick:Math.round(a.currentTick||0),sourceStartTick:a.sourceStartTick||0,active:[false,false],supports:[],lastFrame:null,next:null,previousSource:null};state=s;
 s.previousSourceDt=a.previousPoseDt??1/120;if(!(s.previousSourceDt>0))throw Error('Previous source sample interval must be positive');
 if(a.previousPose)s.previousSource=pose(a.previousPose,run.names);
 else if(s.tick>s.sourceStartTick)s.previousSource=K.at(run,(s.tick-s.sourceStartTick-1)/120);
 const headingAt=time=>{if(s.input.canonicalTerrain&&!s.input.futureRoots)return K.rootHeading(s.run,time,s.settings,s.run.directionMeta.commandSpeed);const w=sampleWindow(s.input,time,s.tick/120),yaw=w?.yaw??s.input.rootYaw??0;return [Math.sin(yaw*Math.PI/180),0,Math.cos(yaw*Math.PI/180)];};
 const motion=()=>({begin:time=>{s.terrain.setTime(time);return externalSurfaceContext(s,time);},finish(context,supports){
  s.supports=supports.map(v=>({surface:v.surface.id,point:v.point,normal:v.normal}));
  const rows=s.input.rootReceipts||[],given=rows.find(x=>Math.round(x.time*120)===Math.round(context.time*120))?.receipt||s.input.rootReceipt;
  return given||{externalRoot:true,normal:context.normal,bodyUp:context.bodyUp,bodyRotation:context.rootQ,gaitRotation:context.surfaceQ,mass:context.mass,velocity:context.velocity,contacts:supports.length,mode:context.slide?'SLIDE':supports.length?'SUPPORT':context.velocity[1]<0?'FALL':'FLIGHT',pinNormal:context.pinNormal,...(context.slide?{slide:context.slide}:{})};
 },forecast(context,_supports,ticks){return Array.from({length:ticks+1},(_,i)=>externalSurfaceContext(s,context.time+i/120));},snapshot(){return null;}});
 s.generator=F.simulate(run,settings,{live:true,terrain,motion,frames:history(8),interactive:true,checkpoints:true,startTime:s.tick/120,headingAt,onModel:m=>{s.model=m;}});
 return {enabled:true,kind:s.kind,tick:s.tick,height,externalRoot:true};
}
function liveSurfaceStep(a){
 if(state?.kind!=='externalSurface')throw Error('External-root surface solver is disabled');const s=state;
 if(a.currentTick!=null&&a.currentTick!==s.tick)throw Error('External surface ticks must be consecutive');
 if(a.settings){Object.assign(s.settings,F.settings({...s.settings,...a.settings}));if(s.model)Object.assign(s.model.settings,s.settings);}
 if(a.surfaces){if(!s.terrain.update)throw Error('Canonical terrain fixture cannot change geometry');s.terrain.update(a.surfaces,a.rootSurfaces,a.surfaceRevision);}
 if(a.source){s.sourceRun=K.decode(a.source,s.run.parents);s.sourceStartTick=a.sourceStartTick??s.sourceStartTick;}
 s.input={...s.input,...a};const ticks=Math.round(a.ticks??1);if(ticks<1||ticks>120)throw Error('Surface step requires1..120ticks');const frames=[];
 for(let i=0;i<ticks;i++){
  if(!s.next||s.next.value?.checkpoint)s.next=s.generator.next();const context=s.next.value;
  if(!context||context.checkpoint)throw Error('Missing external root surface context');
  let p;
  if(a.commands?.[i]?.pose)p=pose(a.commands[i].pose,s.run.names);
  else if(a.poses?.[i])p=pose(a.poses[i],s.run.names);
  else if(a.pose&&ticks===1)p=pose(a.pose,s.run.names);
  else{const time=(s.tick-s.sourceStartTick)/120;if(time<0||time>s.sourceRun.duration+1e-8)throw Error('NN source does not cover external surface tick');p=K.at(s.sourceRun,time);}
  const legs=['L','R'].map(side=>K.stableLeg(p,s.run.names,side)),untilPlant=[];
  const initial=s.previousSource?null:K.at(s.sourceRun,(s.tick-s.sourceStartTick+1)/120),carrier=rotate(qinv(context.surfaceQ),context.velocity);carrier[1]=0;
  for(let side=0;side<2;side++){const l=legs[side],v=s.previousSource?mul(sub(p.points[l.foot],s.previousSource.points[l.foot]),1/s.previousSourceDt):add(mul(sub(sub(initial.points[l.foot],initial.points[0]),sub(p.points[l.foot],p.points[0])),120),carrier),intent=F.gaitIntent(p,l,v,a.commandSpeed??s.run.directionMeta.commandSpeed,s.active[side]);s.active[side]=intent.stance;untilPlant.push(intent.stance?0:v[1]<-.05?Math.max(0,intent.clearance-.02)/-v[1]:Infinity);}
  const supplied=a.commands?.[i],command={pose:p,legs,stance:supplied?.stance||a.stance||s.active.slice(),untilPlant:(supplied?.untilPlant||a.untilPlant||untilPlant).map(x=>x==null?Infinity:x)};s.active=command.stance.slice();
  s.next=s.generator.next(command);s.previousSource=p;s.previousSourceDt=1/120;s.lastFrame=s.model.frames.at(-1);frames.push(s.lastFrame);s.tick++;
 }
 if(s.model.events.length>256)s.model.events.splice(0,s.model.events.length-256);
 return {enabled:true,kind:s.kind,tick:s.tick,frame:s.lastFrame,frames,supports:s.supports,externalRoot:true};
}
function init(a){
 dispose();const run=runOf(a),settings=K.sanitize(a.settings||{}),terrain=a.canonicalTerrain?F.createTerrain(settings,a.extent??100):worldTerrain(a.surfaces||[],a.rootSurfaces);
 const height=run.referenceHeight??run.directionMeta?.referenceHeight??a.height??.9;run.referenceHeight=height;run.directionMeta=run.directionMeta||{};run.directionMeta.commandSpeed=run.directionMeta.commandSpeed??a.speed??2;run.totalDuration=1e9;
 const live={kind:'live',settings,run,terrain,input:a,rootRevision:0,inputTime:0,rootState:null,rootContext:null,nextTime:0,lastFrame:null,previousFrame:null,policySteps:a.policySteps||null,ownsPolicy:a.policy!==false,outputs:[],lastSupports:[]};state=live;
 const yawAt=time=>{if(a.canonicalTerrain&&!live.input.futureRoots)return K.commandYaw(live.settings,time,run.directionMeta.commandSpeed);const w=sampleWindow(live.input,time,live.inputTime);return w?.yaw??live.input.rootYaw??live.input.root?.yaw??0;};
 const headingAt=time=>{const yaw=yawAt(time);return [Math.sin(yaw*Math.PI/180),0,Math.cos(yaw*Math.PI/180)];};
 const controller=a.canonicalTerrain&&!a.travelVelocity?undefined:(time,normal)=>{const w=sampleWindow(live.input,time,live.inputTime);let velocity=live.input.travelVelocity;if(!velocity&&w?.a.position&&w?.b.position&&w.a!==w.b)velocity=mul(sub(w.b.position,w.a.position),1/w.dt);velocity=velocity||[0,0,run.directionMeta.commandSpeed];const horizontal=[velocity[0],0,velocity[2]],magnitude=length(horizontal);if(magnitude<1e-12)return [0,0,0];const mapped=rotate(R.fromTo(up,normal),mul(horizontal,1/magnitude));return mul(unit(sub(mapped,mul(normal,dot(mapped,normal)))),magnitude);};
 const motion=params=>{
  let active=null,observed=-1,saved=null;
  function observedState(time){
   const input=live.input.root;if(!input)return saved;
   const position=vector(input.position,'actual root position'),velocity=vector(input.velocity||[0,0,0],'actual root velocity'),normal=unit(vector(input.normal||saved?.normal||[0,1,0],'actual surface normal'));
   const bodyQ=input.bodyRotation?vector(input.bodyRotation,'body rotation',4):saved?.bodyQ||F.bodyRotation(normal,settings.upright),bodyUp=rotate(bodyQ,up),mass=add(position,mul(normal,Math.max(.22,height*Math.max(0,dot(bodyUp,normal)))));
   const surface=terrain.rootSurfaces?.().find(p=>p.id===input.surface)||terrain.pickRoot?.(mass,bodyUp,height)||terrain.floor;
   return {...(saved||{}),bodyQ,normal,mass,velocity,wallTime:saved?.wallTime||0,lastSupportTime:saved?.lastSupportTime??time,motionSurface:saved?.motionSurface||surface.id,previousCourse:saved?.previousCourse||surface.id,previousCollisions:saved?.previousCollisions||[],slide:saved?.slide||null,previousVerticalSpeed:saved?.previousVerticalSpeed??null};
  }
  return {begin(time){if(observed!==live.rootRevision){saved=observedState(time);observed=live.rootRevision;active=F.createRootMotion({...params,s:settings,controller},saved);}const c=active.begin(time);live.rootContext=c;return c;},finish(context,supports){const receipt=active.finish(context,supports);saved=active.snapshot();live.rootState=saved;live.lastSupports=supports.map(v=>({surface:v.surface.id,point:v.point,normal:v.normal}));return receipt;},forecast(context,supports,ticks){return active.forecast(context,supports,ticks);},snapshot(){return saved;}};
 };
 const initialPair=a.initialPair?{previous:pose(a.initialPair.previous,run.names),current:pose(a.initialPair.current,run.names)}:a.seeds?{previous:pose(a.seeds[0],run.names),current:pose(a.seeds[1],run.names)}:null;
 const host={live:true,terrain,motion,frames:history(8),steps:history(2),windows:history(10),headingAt,gaitAt:()=>live.settings.gait,speedAt:()=>live.input.commandSpeed??run.directionMeta.commandSpeed,yawAt,...(initialPair?{initialPair}:{}),initialPreviousRoot:a.previousRoot,onFrame:value=>{live.outputs.push({tick:value.i,root:{...rootRow(value.context),virtualRoot:value.virtual,yaw:yawAt(value.time)},frame:value.frame,source:value.source,supports:live.lastSupports});}};
 if(a.policy===false){let model;live.generator=F.simulate(run,settings,{...host,interactive:true,checkpoints:true,onModel:m=>{model=m;}});live.next=live.generator.next();live.model=model;live.active=[false,false];}
 else{live.session=C.createSession(run,settings,nn,host);live.model=live.session.model;}
 return {enabled:true,policy:live.ownsPolicy,fps:120,settings,height,causalSurface:true,measuredSeed:!!initialPair};
}
function tick(a){
 if(!state||state.kind!=='live')throw Error('Foot IK live session is not enabled');const s=state;
 if(a.currentTick!=null&&a.currentTick!==Math.round(s.nextTime*120))throw Error('Causal surface ticks must be consecutive');
 const count=a.ticks==null?1:Math.round(finite(a.ticks,'120Hz tick count'));if(count<1||count>120)throw Error('Foot IK tick count must be1..120');
 if(a.settings){Object.assign(s.settings,K.sanitize({...s.settings,...a.settings}));Object.assign(s.model.settings,s.settings);}
 if(a.surfaces){if(!s.terrain.update)throw Error('Canonical fixture cannot change world geometry');s.terrain.update(a.surfaces,a.rootSurfaces,a.surfaceRevision);}
 if(a.root&&!a.teleport)throw Error('Causal surface owns its root; external replacement requires explicit teleport');
 s.input={...s.input,...a};s.inputTime=s.nextTime;if(a.root)s.rootRevision++;s.outputs=[];const frames=[];
 for(let n=0;n<count;n++){
  const time=s.nextTime;
  if(s.session)s.session.extend(time);
  else{
   if(s.next.value?.checkpoint)s.next=s.generator.next();const c=s.next.value;if(!c||c.checkpoint)throw Error('Missing Foot IK root context');
   const p=pose(a.pose||a.currentPose||s.run.poses[1],s.run.names),previous=a.previousPose?pose(a.previousPose,s.run.names):s.sourcePrevious;
   const legs=['L','R'].map(side=>K.stableLeg(p,s.run.names,side)),untilPlant=[];
   for(let side=0;side<2;side++){const l=legs[side],v=previous?mul(sub(p.points[l.foot],previous.points[l.foot]),a.previousPose?30:120):c.velocity,intent=F.gaitIntent(p,l,v,s.run.directionMeta.commandSpeed,s.active[side]);s.active[side]=intent.stance;untilPlant.push(s.active[side]?0:v[1]<-.05?Math.max(0,intent.clearance-.02)/-v[1]:Infinity);}
   s.next=s.generator.next({pose:p,legs,stance:a.stance||s.active.slice(),untilPlant:a.untilPlant||untilPlant});s.sourcePrevious=p;
  }
  s.previousFrame=s.lastFrame;s.lastFrame=s.model.frames.at(-1);frames.push(s.lastFrame);s.nextTime+=1/120;
 }
 if(s.model.events.length>256)s.model.events.splice(0,s.model.events.length-256);
 // Source histories remain inside the canonical session. Results returned here
 // are one120Hz frame; the Unreal owner publishes each second frame at60Hz.
 const rootState=s.rootState,normal=rootState?.normal,bodyUp=rootState?rotate(rootState.bodyQ,up):null;
 const nextRoot=rootState?{position:sub(rootState.mass,mul(normal,Math.max(.22,(s.run.referenceHeight||.9)*Math.max(0,dot(bodyUp,normal))))),velocity:rootState.velocity,normal,bodyRotation:rootState.bodyQ}:null;
 return {enabled:true,time:s.nextTime-1/120,nextTime:s.nextTime,tick:Math.round(s.nextTime*120),frame:s.lastFrame,frames,outputs:s.outputs,previousFrame:s.previousFrame,nextRoot,supports:s.lastSupports,policySteps:s.model.coupling?.steps||0};
}
function command(input){
 const a=typeof input==='string'?JSON.parse(input):input;if(!a||typeof a.op!=='string')throw Error('Foot IK command requires op');
 let result;
 switch(a.op){
 case 'policyHandoff':if(state?.kind!=='live'||!state.session)throw Error('Causal policy owner is disabled');result=state.session.policyHandoff();break;
 case 'liveSurfaceInit':result=liveSurfaceInit(a);break;
 case 'liveSurfaceStep':result=liveSurfaceStep(a);break;
 case 'liveSurfaceStatus':result=state?.kind==='externalSurface'?{enabled:true,tick:state.tick,frame:state.lastFrame,supports:state.supports}:{enabled:false};break;
 case 'liveSurfaceClose':result=dispose();break;
 case 'liveJoin':result=LiveJoin.join(a);break;
 case 'liveIdentity':result=LiveJoin.identity(a);break;
 case 'liveExitReady':result=LiveExit.evaluate(a);break;
 case 'rootInit':result=rootInit(a);break;
 case 'rootStep':result=rootStep(a);break;
 case 'rootForecast':result=rootForecast(a);break;
 case 'rootStatus':result=rootStatus();break;
 case 'rootClose':result=dispose();break;
 case 'liveEvaluate':{
  if(!state||state.kind!=='prospective'||state.epoch!==a.epoch){dispose();state={kind:'prospective',epoch:a.epoch,planner:LivePlanner.create({...a,handoff:false,infer:request=>nn(request,0)})};}
  const current=Math.max(0,Math.round(a.currentTick||0)),p=state.planner;
   if(!a.acceptedFrames?.length&&Number.isInteger(a.acceptedThrough))for(let i=p.status.through+1;i<=a.acceptedThrough;i++)p.commit(i);
  const update=p.status.revision?{source:a.source,sourceStartTick:a.sourceStartTick,terrain:a.terrain,settings:a.settings}:{};
  if(a.acceptedFrames?.length)update.acceptedFrames=a.acceptedFrames;
  if(a.acceptedHistoryCheckpoint){update.acceptedHistoryCheckpoint=a.acceptedHistoryCheckpoint;update.source=a.source;update.sourceStartTick=a.sourceStartTick;update.terrain=a.terrain;}
  const planned=p.plan(update);
  if(!planned?.ready){result={...planned,diagnostics:p.status};break;}
  if(current/120>p.status.generatedThrough+1e-8)throw Error('Live Foot IK source does not cover the current game tick');
  result={...planned,frame:p.frame(current),currentTick:current,throughTick:Math.round(p.status.generatedThrough*120),diagnostics:p.status};break;
 }
 case 'liveCommit':{
  if(state?.kind!=='prospective')throw Error('No prospective Foot IK plan');const through=Math.max(0,Math.round(a.through));
   if(a.acceptedFrames?.length)state.planner.accept(a.acceptedFrames);
   else for(let i=state.planner.status.through+1;i<=through;i++)state.planner.commit(i);result=state.planner.status;break;
 }
 case 'liveFrames':{
  if(state?.kind!=='prospective')throw Error('No prospective Foot IK plan');const start=Math.max(0,Math.round(a.start||0)),count=Math.max(0,Math.min(240,Math.round(a.count||1)));result=[];
  for(let i=start;i<start+count;i++){const frame=state.planner.frame(i);if(!frame)break;result.push(frame);}break;
 }
 case 'liveFrameTexts':{
  if(state?.kind!=='prospective')throw Error('No prospective Foot IK plan');const start=Math.max(0,Math.round(a.start||0)),count=Math.max(0,Math.min(240,Math.round(a.count||1)));result=[];
  // Preserve the exact existing JSON wire representation. Native callers can
  // retain each immutable frame without parsing and rebuilding its850numbers.
  for(let i=start;i<start+count;i++){const frame=state.planner.frame(i);if(!frame)break;result.push(JSON.stringify(frame));}break;
 }
 case 'prepare':result=prepare(a);break;
 case 'init':result=init(a);break;
 case 'tick':case 'step':result=tick(a);break;
 case 'extend':{const end=finite(a.endTime,'end time');if(!state?.model)throw Error('No Foot IK course');if(state.session)state.session.extend(end);else if(end>state.model.duration+1e-8)throw Error('Foot IK course extension requires a longer NN source');result=describe(state.model);break;}
 case 'frames':{if(!state?.model)throw Error('No Foot IK result');const start=Math.max(0,Math.round(a.start||0)),count=Math.max(0,Math.min(12001,Math.round(a.count??state.model.frames.length)));result=state.model.frames.slice(start,start+count).map((frame,i)=>state.kind==='fixture'?{...frame,rootHeading:K.rootHeading(state.run,(start+i)/(state.model.fps||120),state.settings,state.run.directionMeta?.commandSpeed||0)}:frame);break;}
 case 'windows':result=state?.model?.coupling?.windows||[];break;
 case 'status':result=state?.kind==='root'?rootStatus():state?.kind==='externalSurface'?{enabled:true,kind:state.kind,tick:state.tick,frame:state.lastFrame,supports:state.supports}:state?.kind==='prospective'?{kind:state.kind,...state.planner.status}:state?{enabled:true,kind:state.kind,...describe(state.model)}:{enabled:false};break;
 case 'close':case 'reset':result=dispose();break;
 default:throw Error('Unknown Foot IK command '+a.op);
 }
 return JSON.stringify(result);
}
root.FootIKNative={command,apiVersion:1};
})(globalThis);
