'use strict';
const $=id=>document.getElementById(id),R=Recovery,C=BodyflipCore,{add,sub,mul,dot,cross,length:norm,unit:normalize}=R;
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v)),posAt=(data,j)=>data.points[j],axisAt=(data,j,a)=>data.axes[j][a];
let names=[],parents=[],nameToIndex=new Map(),swordMesh=null,manifest=null,idle=null,basePelvis=null,physics=null,throwController=null,renderer=null,clip=null;
let settings=C.sanitize(),flip=0,twist=0,attackTime=-1,playing=false,raf=null,lastStamp=0,accumulator=0,saveTimer=null,currentPose=null,desiredPose=null,previousContact=null,hit=false,bestMiss=Infinity,simTime=0,loadRevision=0;
const F=BodyflipFlight;let flight=null,jumps=[],run=null,flightFrame=null,runRevision=0,loadingRun=false;const runCache=new Map();let seekRevision=0,seeking=false,lastHUD=0;
const pivot=[0,1.5,0],cameraDefault={yaw:-.55,pitch:-.06,zoom:.95,panX:0,panY:0,free:false,offset:null,freeView:null},cameraState={...cameraDefault},cache=new Map(),errors=[];
let idleLoop=null,manualResponse=null;
let playRevision=0,previewRAF=null,previewTime=0,platformEditor=null;
let extending=null,preparingRun=null;
let sceneLibrary=null,sceneChanging=false,sceneReady=false,stateWrites=Promise.resolve();
function trimActive(){return !!flight;}
function timelineMax(){return Math.max(12,settings.trimOut,Math.ceil(simTime),...F.eventsFor(settings).map(e=>Math.ceil(e.time+1)));}
function syncTrim(){const max=timelineMax();if(jumpTrack&&jumpTrack.max!==max)jumpTrack.sync();$('trimControls').hidden=$('trimToggle').hidden=false;$('trimLoop').checked=settings.trimLoop;for(const key of ['trimIn','trimOut']){const el=$(key),t=settings[key];el.style.left=(100*t/max)+'%';el.setAttribute('aria-valuenow',t);el.setAttribute('aria-valuemax',max);el.setAttribute('aria-valuetext',t.toFixed(3)+' seconds');el.dataset.time=(key==='trimIn'?'In ':'Out ')+t.toFixed(3)+' s';} $('trimSelection').style.left=(100*settings.trimIn/max)+'%';$('trimSelection').style.width=(100*(settings.trimOut-settings.trimIn)/max)+'%';}
function previewSeek(time){previewTime=time;++seekRevision;seeking=false;if(playing)setPlaying(false);else ++playRevision;if(previewRAF===null)previewRAF=requestAnimationFrame(()=>{previewRAF=null;seek(previewTime).catch(fail);});}
function stepFrame(direction){
 if(!physics||loadingRun)return;
 const current=previewRAF!==null?previewTime:simTime;
 const first=Math.round(settings.trimIn*60),last=Math.round(settings.trimOut*60);
 let frame=Math.round(current*60)+direction;
 if(frame>last)frame=first;else if(frame<first)frame=last;
 previewSeek(frame/60);
}
function finishPreview(time){if(previewRAF!==null)cancelAnimationFrame(previewRAF);previewRAF=null;const revision=runRevision;seek(time).catch(fail);ensurePrepared(settings.trimOut,()=>revision!==runRevision).catch(fail);}
function moveTrim(key,value){const t=Math.round(clamp(value,0,600)*60)/60;settings[key]=key==='trimIn'?Math.min(t,settings.trimOut-1/60):Math.max(t,settings.trimIn+1/60);settings.trimLoop=true;syncTrim();previewSeek(settings[key]);save();}
function placeKinematic(time){manualResponse=null;simTime=Math.round(time*60)/60;const air=flight&&settings.airFlip?Math.max(0,simTime-(flight.airStartAt?.(simTime)??flight.airStart)):0;flip=settings.flipAngle+settings.flipSpeed*air;twist=settings.twistAngle+settings.twistSpeed*air;attackTime=-1;previousContact=null;hit=false;bestMiss=Infinity;desiredPose=targetPose();physics.reset(desiredPose,flightFrame?.handInertia?.velocity||flightFrame?.velocity||[0,flightFrame?.vy||0,flight?.speed||0]);currentPose=physics.read();drawAll();}
function restartTrim(){const job=seek(settings.trimIn),revision=playRevision;job.then(()=>{if(revision===playRevision&&!document.hidden)setPlaying(true);}).catch(fail);}
function playbackStep(){if(trimActive()){
 if(simTime>=settings.trimOut-1e-8&&!settings.trimLoop){setPlaying(false);return false;}
 if(simTime<settings.trimIn-1e-8||simTime>=settings.trimOut-1e-8){if(settings.motion==='kinematic')placeKinematic(settings.trimIn);else {restartTrim();return false;}}}
 tick(trimActive()?settings.trimOut:Infinity);return true;}
window.addEventListener('error',e=>fail(e.error||e.message));window.addEventListener('unhandledrejection',e=>fail(e.reason));
function fail(e){const msg=e?.message||String(e);errors.push(msg);$('error').hidden=false;$('error').textContent=msg;setPlaying(false);console.error(e);}
function notice(text){$('toast').textContent=text;$('toast').hidden=false;clearTimeout(notice.timer);notice.timer=setTimeout(()=>$('toast').hidden=true,2500);}
async function post(path,data){const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});if(!r.ok)throw Error((await r.json()).error||'Save failed');return r.json();}
function playbackState(){return {time:previewRAF!==null?previewTime:simTime,attackTime,flip,twist,playing,hit,bestMiss:Number.isFinite(bestMiss)?bestMiss:null};}
function stored(){const state={schema:'bodyflip-lab-v1',settings:{...settings},camera:{...cameraState},playback:playbackState()};if(!sceneLibrary)return state;sceneLibrary=BodyflipScenes.capture(sceneLibrary,state);return BodyflipScenes.pack(sceneLibrary);}
function persist(state){const payload=JSON.parse(JSON.stringify(state));const job=stateWrites.catch(()=>{}).then(()=>post('/state',payload));stateWrites=job;return job;}
function syncScenes(){$('scene').replaceChildren(...sceneLibrary.items.map(s=>new Option(s.name,s.id)));$('scene').value=sceneLibrary.active;for(const id of ['scene','copyScene','renameScene','newScene'])$(id).disabled=!sceneReady||sceneChanging;}
async function changeScene(action,id){
 if(!sceneReady||sceneChanging||loadingRun||$('strike').disabled){syncScenes();return;}
 const current=sceneLibrary.items.find(s=>s.id===sceneLibrary.active);
 const name=action==='select'?null:prompt(action==='copy'?'Name the new scene (copies this setup)':'Scene name',action==='new'?'Scene '+(sceneLibrary.items.length+1):action==='copy'?current.name+' copy':current.name);
 if(action!=='select'&&(name===null||!name.trim())){syncScenes();return;}
 const previous=stored().scenes;
 const fresh=action==='new'?{settings:C.sanitize({...BodyflipPlatforms.restoreDefaultsOnce({}),ramps:false}),camera:{...cameraDefault},playback:{time:0,attackTime:-1,flip:0,twist:0,playing:false,hit:false,bestMiss:null}}:null;
 let next=action==='new'?BodyflipScenes.create(previous,name,crypto.randomUUID(),fresh):action==='select'?BodyflipScenes.select(previous,id):action==='copy'?BodyflipScenes.copy(previous,name,crypto.randomUUID()):BodyflipScenes.rename(previous,name);
 sceneChanging=true;document.body.inert=true;syncScenes();setPlaying(false);clearTimeout(saveTimer);saveTimer=null;
 ++seekRevision;if(previewRAF!==null)cancelAnimationFrame(previewRAF);previewRAF=null;
 // Reload only after the entire library is saved. This also isolates undo and pending animation loads.
 try{await persist(BodyflipScenes.pack(next));sceneLibrary=next;location.reload();}
 catch(e){sceneLibrary=previous;sceneChanging=false;document.body.inert=false;syncScenes();fail(e);}
}
async function restorePlayback(state){
 if(!state||!Number.isFinite(state.time))return;
 const time=clamp(state.time,0,600);
 await seek(time);
 attackTime=Number.isFinite(state.attackTime)?clamp(state.attackTime,-1,total()):-1;
 if(Number.isFinite(state.flip))flip=state.flip;if(Number.isFinite(state.twist))twist=state.twist;
 if(settings.motion==='kinematic')resetPhysics();
 hit=!!state.hit;bestMiss=Number.isFinite(state.bestMiss)?state.bestMiss:Infinity;
 setPlaying(state.playing===true&&!document.hidden);drawAll();
}
async function refreshLab(){
 // Snapshot BEFORE pausing. Cancel delayed saves/seeks that could overwrite it.
 const snapshot=stored();++runRevision;setPlaying(false);clearTimeout(saveTimer);saveTimer=null;
 ++seekRevision;if(previewRAF!==null)cancelAnimationFrame(previewRAF);previewRAF=null;
 try{await persist(snapshot);location.reload();}catch(e){fail(e);}
}
function save(){clearTimeout(saveTimer);if(!sceneReady||sceneChanging)return;saveTimer=setTimeout(()=>{if(!sceneChanging)persist(stored()).catch(fail);},250);}
function wrap(x){return ((x+180)%360+360)%360-180;}
function rotation(){return C.orientation(flip,twist,settings.axis,basePelvis);}
const vanillaAttacks=new Map();let vanillaManifest=null;
async function loadVanilla(){if(F.eventsFor(settings).some(e=>BodyflipThrowAttack.accepts(e.attack))&&!BodyflipThrowAttack.data)BodyflipThrowAttack.load(await fetch('data/throws.json').then(r=>r.json()));const needed=[...new Set([settings.attack,...F.eventsFor(settings).map(e=>C.sanitizeJump(e).attack)])].filter(n=>n!=='none'&&!BodyflipThrowAttack.accepts(n)&&!vanillaAttacks.has(n));if(!needed.length)return;vanillaManifest ||= await fetch('data/vanilla.json').then(r=>r.json());for(const name of needed){const meta=vanillaManifest.clips.find(c=>c.name===name);if(!meta)throw Error('Missing vanilla attack '+name);const bytes=await fetch(meta.file).then(r=>r.arrayBuffer());vanillaAttacks.set(name,C.decode(meta,bytes,names,parents));}}
function manualPose(time,basePose,sourceClip=clip,config=settings){
 if(config.kickToArmed||BodyflipKickAttack.accepts(config.attack))return basePose;
 const raw=C.sample(sourceClip,time,idle,parents),target=BodyflipJumpAttack.carryPelvis(R.localize(raw.points,raw.q,parents),R.localize(sourceClip.poses[0].points,sourceClip.poses[0].q,parents),names.indexOf('spine_01'),parents),upper=BodyflipJumpAttack.bones(names,parents);
 const weight=Math.min(clamp(time/.15,0,1),clamp((sourceClip.duration+.6-time)/.45,0,1));
 let pose=BodyflipJumpAttack.overlay(basePose,target,upper,parents,weight*weight*(3-2*weight));
 return pose;
}
function manualSoft(pose,basePose){
 if(!manualResponse||attackTime<manualResponse.last-1e-7){
  const begun=simTime-attackTime/settings.attackRate,track=flight,sourceClip=clip,config={...settings,target:settings.target.slice()};
  const base=t=>{const time=begun+t/config.attackRate,air=config.airFlip?Math.max(0,time-(track.airStartAt?.(time)??Infinity)):0;return track.sample(time,config.flipAngle+config.flipSpeed*air,config.twistAngle+config.twistSpeed*air,config.axis).pose;};
  const ph=sourceClip.meta.phases||{},vanilla=vanillaManifest?.clips.find(c=>c.name===config.attack),phases=vanilla?.phases||ph,fps=sourceClip.meta.fps;
  if(BodyflipKickAttack.accepts(config.attack)){
   const kickClip=sourceClip; // Retain the selected variant and cache its full-body plan.
   kickClip.meta.name=config.attack;kickClip.meta.phases={...ph,...phases};
   const response=BodyflipKickAttack.create({clip:kickClip,names,parents,reference:idle,base,lead:.15,tail:.45,directArmed:config.kickToArmed});
   manualResponse={begun,name:config.attack,rate:config.attackRate,response,last:attackTime};return response.sample(attackTime);
  }
  if(config.kickToArmed){
   sourceClip.meta.name=config.attack;sourceClip.meta.phases={...ph,...phases};
   const modifyPose=null;
   const planned=BodyflipJumpAttack.create({attack:config.attack,attackIn:.15,attackOut:.45},{sample:t=>({pose:base(t)}),airStart:0,jumpStart:0,abortTime:Infinity},new Map([[config.attack,sourceClip]]),names,parents,config,idle,{modifyPose});
   const response={...planned,sample:t=>planned.sample(t).pose};manualResponse={begun,name:config.attack,rate:config.attackRate,response,last:attackTime};return response.sample(attackTime);
  }
  const hitTime=.15+(phases.hit??sourceClip.poses.length*.7)/fps,returnEnd=sourceClip.duration+.6,soft=config.softAttackLegs&&config.pelvisAttackCompensation>0;
  const choreography=soft?BodyflipAttackInertia.referenceMotion({clip:{...sourceClip,meta:{...sourceClip.meta,phases}},names,parents,reference:idle,start:0,armedTime:.15+(phases.armed??sourceClip.poses.length*.4)/fps,hitTime,end:.15+sourceClip.duration,returnEnd,amount:config.pelvisAttackCompensation}):null;
  const legal=BodyflipAttackInertia.createProjection(names,parents,idle),source=t=>manualPose(t,base(t),sourceClip,config),inertia=soft?BodyflipAttackInertia.create({amount:config.pelvisAttackCompensation,choreography,source,base,target:(t,raw,baseline)=>BodyflipJumpAttack.compensate(raw||source(t),baseline||base(t),names,parents,config.pelvisAttackCompensation),start:0,end:returnEnd,recoveryStart:sourceClip.duration+.15,recoveryEnd:returnEnd,names,parents,reference:idle}):null;
  const displayed=(t,raw=source(t))=>inertia?inertia.sample(t,raw):config.pelvisAttackCompensation>0?legal(BodyflipJumpAttack.compensate(legal(raw),legal(base(t)),names,parents,config.pelvisAttackCompensation)):raw;
  const recovery=R.pelvisReturn({source:displayed,base,parents,start:hitTime,end:returnEnd,pelvis:names.indexOf('pelvis')}),response={...inertia,start:0,armedTime:.15+(phases.armed??sourceClip.poses.length*.4)/fps,end:.15+sourceClip.duration,hitTime,returnEnd,recovery,sample:(t,raw)=>t<=hitTime?displayed(t,raw):config.pelvisAttackCompensation>0?legal(recovery.sample(t)):recovery.sample(t)};
  manualResponse={begun,name:config.attack,rate:config.attackRate,response,last:0};
 }
 manualResponse.last=attackTime;return manualResponse.response.sample(attackTime,pose);
}
const aimPlans=new WeakMap();let displayedAim=null;
function makeAimPlan(track,source,sampleHit){
 const project=p=>typeof physics!=='undefined'&&physics?physics.target(p):p;
 const launchAt=track.launchAt?(pose,transform=p=>p)=>track.launchAt(pose,track.transportVelocity(t=>transform(sampleHit(t),t))):null;
 return BodyflipAttackAim.create({clip:source,track,names,parents,reference:idle,sampleHit,launchAt,project});
}
function aimTimelinePoseAt(time,rawPose=null,display=false){
 const pose=rawPose||flight.sample(time).pose;
 if(flight.sample(time).physicalAim)return pose;
 if(!settings.aim)return pose;
 const entries=(flight.segments||[]).filter(s=>s.attack&&time>=s.attack.start).map(s=>({track:s.attack,name:s.event.attack}));
 let rotation=[0,0,0,1],last=null;
 for(let i=0;i<entries.length;i++){
  const {track,name}=entries[i];if(settings.undoRotation&&time>=track.returnEnd)continue;
  const source=vanillaAttacks.get(name);if(!source&&!track.launchAt)continue;
  let plan=aimPlans.get(track);if(!plan){plan=makeAimPlan(track,source,t=>flight.sample(t).pose);aimPlans.set(track,plan);}
  if(settings.undoRotation){if(display)displayedAim=plan;return plan.apply(pose,time,settings.target,settings.aimWeight);}
  rotation=plan.rotation(Math.min(time,entries[i+1]?.track.start??time),settings.target,settings.aimWeight,false,rotation);last=plan;
 }
 if(display)displayedAim=last;return last?last.applyRotation(pose,rotation):pose;
}
function configureThrows(){if(throwController&&flight)throwController.configure(flight,t=>physics.target(aimTimelinePoseAt(t)),[settings.target.join(','),settings.aim,settings.aimWeight,settings.undoRotation].join('|'));}
function heldAim(pose){
 const entries=(flight.segments||[]).filter(s=>s.attack&&simTime>=s.attack.start).map(s=>({track:s.attack,name:s.event.attack,start:s.attack.start,rate:1,time:simTime,sample:t=>flight.sample(t).pose}));
 if(manualResponse&&simTime>=manualResponse.begun)entries.push({track:manualResponse.response,name:manualResponse.name||settings.attack,start:manualResponse.begun,rate:manualResponse.rate,time:Math.max(0,(simTime-manualResponse.begun)*manualResponse.rate),sample:t=>manualResponse.response.sample(t)});
 entries.sort((a,b)=>a.start-b.start);let rotation=[0,0,0,1],last=null;
 for(let i=0;i<entries.length;i++){
  const e=entries[i],source=vanillaAttacks.get(e.name);if(!source&&!e.track.launchAt)continue;
  let plan=aimPlans.get(e.track);if(!plan){plan=makeAimPlan(e.track,source,e.sample);aimPlans.set(e.track,plan);}
  // The next attack starts from the orientation reached by its predecessor.
  const time=i+1<entries.length?e.time-(simTime-entries[i+1].start)*e.rate:e.time;
  rotation=plan.rotation(time,settings.target,settings.aimWeight,false,rotation);last=plan;
 }
 displayedAim=last;return settings.aim&&last?last.applyRotation(pose,rotation):pose;
}
function aimAttack(pose){
 displayedAim=null;if(!flight)return pose;if(flightFrame?.physicalAim&&!manualResponse){displayedAim=flight.activeAt(simTime)?.physical?.track?.plan||null;return pose;}if(!manualResponse)return aimTimelinePoseAt(simTime,pose,true);if(settings.undoRotation===false)return heldAim(pose);
 let track,time,name,hitSample;
 if(manualResponse){track=manualResponse.response;time=attackTime>=0?attackTime:Math.max(0,(simTime-manualResponse.begun)*manualResponse.rate);name=settings.attack;hitSample=t=>track.sample(t);}
 if(!track||time>=track.returnEnd){const segment=flight.activeAt(simTime);track=segment?.attack;time=simTime;name=segment?.event?.attack;hitSample=t=>flight.sample(t).pose;}
 if(!track||time<(track.start??0)||time>=track.returnEnd)return pose;
 const source=vanillaAttacks.get(name);if(!source&&!track.launchAt)return pose;
 let plan=aimPlans.get(track);if(!plan){plan=makeAimPlan(track,source,hitSample);aimPlans.set(track,plan);}
 displayedAim=plan;
 return settings.aim?plan.apply(pose,time,settings.target,settings.aimWeight):pose;
}
function refreshAim({preview=false}={}){
 if(flight?.segments?.some(s=>s.spin?.active)){
  if(preview){drawAll();return;}
  prepareRun({preserveTime:true}).catch(fail);return;
 }
 configureThrows();
 if(physics&&settings.motion==='kinematic'){desiredPose=targetPose();physics.reset(desiredPose,flightFrame?.handInertia?.velocity||flightFrame?.velocity||[0,0,0]);currentPose=physics.read();previousContact=null;hit=false;bestMiss=Infinity;}
 drawAll();
}
function attackContact(pose,name){return displayedAim?displayedAim.point(pose):C.contactPoint(pose,name,names,swordMesh);}
function targetPose(){if(!flight&&settings.mode==='idle'&&idleLoop){flip=twist=0;flightFrame=null;const rest=idleLoop.rawAt(simTime);let pose=idleLoop.ground(clip?C.sample(clip,attackTime,rest,parents):rest);return pose;}const raw=clip?C.sample(clip,attackTime,idle,parents):idle;let pose;
 if(flight){flightFrame=flight.sample(simTime,settings.airFlip?flip:0,settings.airFlip?twist:0,settings.axis);pose=flightFrame.pose;
  if(attackTime>=0&&clip){const basePose=pose;pose=manualSoft(manualPose(attackTime,basePose),basePose);}
  else if(manualResponse)pose=manualResponse.response.sample(Math.max(0,(simTime-manualResponse.begun)*manualResponse.rate),pose);
 }else pose=C.centerPose(raw,rotation(),pivot);
 return aimAttack(pose);}
function resetPhysics(){if(!physics)return;const dynamic=!!flight;physics.configure({dynamic,kinematic:settings.motion==='kinematic',edge:flight?.edge||5,surfaces:flight?.surfaces,cap:settings.fallCap,zeroGravity:settings.mode==='spaceGym'});configureThrows();desiredPose=targetPose();if(dynamic||settings.motion==='kinematic')physics.reset(desiredPose,flightFrame?.handInertia?.velocity||flightFrame?.velocity||[0,flightFrame?.vy||0,flight?.speed||0]);else {const rest=settings.mode==='idle'?desiredPose:C.centerPose(idle,rotation(),pivot);physics.reset(rest);for(let i=0;i<60;i++)physics.step(desiredPose,dt);}currentPose=physics.read();previousContact=null;drawAll();}
async function prepareRun({preserveTime=false}={}){manualResponse=null;
 const savedTime=preserveTime?simTime:0,savedAttack=preserveTime?attackTime:-1,resume=preserveTime&&playing;
 const rev=++runRevision,editSeek=++seekRevision;const ready={};ready.promise=new Promise(resolve=>{ready.resolve=resolve;});preparingRun=ready;seeking=false;setPlaying(false);const pausedRevision=playRevision;
 loadingRun=true;$('play').disabled=true;$('step').disabled=true;$('strike').disabled=true;$('runInfo').textContent='Loading '+(settings.mode==='spaceGym'?'space':settings.mode==='idle'?'idle':settings.mode==='walk'?'walk':'run')+'…';let resumeAfter=false;
 try {await loadVanilla();let decoded;if(settings.mode==='idle'||settings.mode==='spaceGym')decoded=idleLoop.motion(settings.runPhase);else {const request={gait:settings.mode==='walk'?'walk':'run',duration:5,phase:settings.runPhase,drawn:settings.attack==='pike'||settings.attack.startsWith('slash')},key=JSON.stringify(request);decoded=runCache.get(key);if(!decoded){decoded=F.decodeNN(await post('/run',request));runCache.set(key,decoded);while(runCache.size>4)runCache.delete(runCache.keys().next().value);}}if(rev!==runRevision)return;
  const prepared=await F.prepare(decoded,jumps,settings,parents,idle,request=>{ $('runInfo').textContent='Preparing landing NN…';return post('/resume',request);},()=>rev!==runRevision,vanillaAttacks);
  if(rev!==runRevision||!prepared)return;
  const restoreTime=preserveTime?Math.min(prepared.preparedThrough,seekRevision===editSeek?savedTime:simTime):0;
  resumeAfter=resume&&playRevision===pausedRevision&&seekRevision===editSeek;
  run=decoded;flight=prepared;ready.resolve();if(preparingRun===ready)preparingRun=null;platformEditor?.refresh();simTime=restoreTime;attackTime=savedAttack;
  const air=settings.airFlip?Math.max(0,simTime-(flight.airStartAt?.(simTime)??flight.airStart)):0;flip=settings.flipAngle+settings.flipSpeed*air;twist=settings.twistAngle+settings.twistSpeed*air;hit=false;bestMiss=Infinity;flightFrame=null;
  const first=flight.segments[0],support=first?.support?.terminal;
  $('legMatchInfo').textContent=first&&settings.matchLeg&&first.matchDistance!=null?'Body '+first.matchTime.toFixed(3)+' s · '+first.legRate.toFixed(3)+'×':'Normal animation timing';
  $('runInfo').textContent=(settings.mode==='spaceGym'?'Space gym':settings.mode==='idle'?'Idle':(settings.mode==='walk'?'Walk':'Run')+' NN')+' · '+flight.speed.toFixed(1)+' m/s · '+F.eventsFor(settings).length+' jumps';
  $('runInfo').title='Duration sets the default jump time. Run/Walk duration also places the ledge. Each marker starts support, then contact, loading and push. Drag a marker or edit its time.';
  jumpTrack?.sync();
  if(preserveTime&&settings.motion!=='kinematic'&&restoreTime>0){simTime=0;resetPhysics();const job=seek(restoreTime),seekPlayRevision=playRevision;await job;resumeAfter&&=playRevision===seekPlayRevision;}else resetPhysics();
  if(rev===runRevision)save();
 }finally{ready.resolve();if(preparingRun===ready)preparingRun=null;if(rev===runRevision){loadingRun=false;$('play').disabled=false;$('step').disabled=false;$('strike').disabled=false;if(resumeAfter&&!document.hidden)setPlaying(true);}}
}
function total(){
 if(!clip)return 1;
 if(settings.kickToArmed){
  const armed=(clip.meta.phases?.armed??vanillaManifest?.clips.find(c=>c.name===settings.attack)?.phases.armed??0)/clip.meta.fps;
  return Math.max(.15,armed)+clip.duration-armed+.45;
 }
 return clip.duration+.6;
}
function strike(){if(!clip||loadingRun)return;manualResponse=null;attackTime=0;hit=false;bestMiss=Infinity;previousContact=null;setPlaying(true);}
function cancelAttack(){manualResponse=null;attackTime=-1;previousContact=null;hit=false;bestMiss=Infinity;if(!playing)resetPhysics();}
let contactAttackKey=null;
function displayedAttack(){return attackTime>=0?settings.attack:flightFrame?.attack?.name||settings.attack;}
function measureAttackContact(){
 if(attackTime<0){
  const latest=(flight?.segments||[]).map(s=>s.attack).filter(a=>a&&a.start<=simTime).at(-1);
  if(latest?.isThrow){
   if(simTime<latest.releaseTime){previousContact=null;return;}
   configureThrows();
   const plan=throwController?.plans.find(p=>Math.abs(p.releaseTime-latest.releaseTime)<1e-8);
   const body=plan&&throwController.sample(simTime,currentPose).find(p=>p.id===plan.id);
   if(!body){previousContact=null;return;}
   const key='projectile:'+plan.id;
   if(key!==contactAttackKey){contactAttackKey=key;previousContact=null;hit=false;bestMiss=Infinity;}
   const point=BodyflipAttackAim.launchCenter(body);let d=norm(sub(point,settings.target));
   if(previousContact)d=Math.min(d,C.segmentDistance(settings.target,previousContact,point));
   bestMiss=Math.min(bestMiss,Math.max(0,d-settings.radius));hit||=d<=settings.radius+.025;previousContact=point;return;
  }
 }
 const scheduled=attackTime<0?flightFrame?.attack:null,name=displayedAttack();
 const active=scheduled?scheduled.phase==='ATTACK':attackTime>=.15&&attackTime<=.15+clip.duration;
 if(!active){previousContact=null;return;}
 const key=scheduled?name+':'+scheduled.start:'manual';
 if(key!==contactAttackKey){contactAttackKey=key;previousContact=null;hit=false;bestMiss=Infinity;}
 const point=attackContact(currentPose,name);let d=norm(sub(point,settings.target));
 if(previousContact)d=Math.min(d,C.segmentDistance(settings.target,previousContact,point));
 if(name.startsWith('slash')||name==='pike')d=Math.min(d,C.segmentDistance(settings.target,currentPose.points[nameToIndex.get('hand_r')],point));
 bestMiss=Math.min(bestMiss,Math.max(0,d-settings.radius));hit||=d<=settings.radius+.025;previousContact=point;
}
function tick(endTime=Infinity){const count=settings.motion==='kinematic'?1:4,dt=1/(60*count);for(let i=0;i<count&&simTime<endTime-1e-8;i++){
 simTime+=dt;
 if(flight&&settings.airFlip){const air=Math.max(0,simTime-flight.airStartAt(simTime));flip=settings.flipAngle+settings.flipSpeed*air;twist=settings.twistAngle+settings.twistSpeed*air;}
 if(attackTime>=0){attackTime+=settings.attackRate*dt;if(attackTime>total()){if(settings.loop){attackTime=0;hit=false;bestMiss=Infinity;previousContact=null;}else attackTime=-1;}}
 desiredPose=targetPose();physics.step(desiredPose,1/240,simTime);currentPose=physics.read();
 measureAttackContact();
 }}
async function ensurePrepared(time,cancelled=()=>false){
 if(cancelled())return;
 while(preparingRun){await preparingRun.promise;if(cancelled())return;}
 if(!flight?.extend||time<=flight.preparedThrough+1e-8)return;
 const source=flight,revision=runRevision;
 if(extending?.source===source){extending.target=Math.max(extending.target,time);return extending.promise;}
 const task={source,target:time,promise:null};extending=task;
 loadingRun=true;$('play').disabled=true;$('step').disabled=true;$('strike').disabled=true;
 task.promise=(async()=>{
  try{
   while(revision===runRevision&&task.target>source.preparedThrough+1e-8){
    $('runInfo').textContent='Preparing to '+task.target.toFixed(2)+' s...';
    const ready=await source.extend(task.target);
    if(revision!==runRevision||!ready)return;
    flight=ready;
    if(source!==ready){task.source=ready;break;}
   }
   if(revision===runRevision){$('runInfo').textContent=(settings.mode==='spaceGym'?'Space gym':settings.mode==='idle'?'Idle':(settings.mode==='walk'?'Walk':'Run')+' NN')+' '+flight.speed.toFixed(1)+' m/s '+F.eventsFor(settings).length+' jumps';jumpTrack?.sync();}
  }finally{if(extending===task)extending=null;if(revision===runRevision){loadingRun=false;$('play').disabled=false;$('step').disabled=false;$('strike').disabled=false;}}
 })();return task.promise;
}
async function seek(time){const rev=++seekRevision;setPlaying(false);seeking=true;try{await ensurePrepared(time,()=>rev!==seekRevision);if(rev!==seekRevision)return;hit=false;bestMiss=Infinity;if(settings.motion==='kinematic'){placeKinematic(time);return;}simTime=0;attackTime=-1;flip=settings.flipAngle;twist=settings.twistAngle;resetPhysics();const ticks=Math.round(time*60);for(let n=0;n<ticks;){const start=performance.now();do{tick();n++;}while(n<ticks&&performance.now()-start<6);if(n<ticks){await new Promise(r=>setTimeout(r,0));if(rev!==seekRevision)return;}}drawAll();}finally{if(rev===seekRevision)seeking=false;}}
function animate(stamp){raf=null;if(!playing||document.hidden)return;if(lastStamp)accumulator=Math.min(.05,accumulator+Math.min((stamp-lastStamp)/1000,.05)*settings.playbackSpeed);lastStamp=stamp;let count=0;while(accumulator>=1/60&&count++<3){if(!playbackStep())return;accumulator-=1/60;}drawAll();if(playing)raf=requestAnimationFrame(animate);}
function setPlaying(value){++playRevision;if(value&&physics&&!loadingRun&&!seeking&&trimActive()&&(simTime<settings.trimIn-1e-8||simTime>=settings.trimOut-1e-8)){if(settings.motion==='kinematic')placeKinematic(settings.trimIn);else {restartTrim();return;}}playing=!!value&&!!physics&&!loadingRun&&!seeking;if(raf!==null)cancelAnimationFrame(raf);raf=null;lastStamp=0;accumulator=0;$('play').innerHTML=playing?'Pause <kbd>Space</kbd>':'Play <kbd>Space</kbd>';if(playing)raf=requestAnimationFrame(animate);else if(physics)drawAll();}
const cameraKeys=new Set();let cameraRAF=null,cameraStamp=0;
function syncCameraUI(){
 $('followCamera').checked=!cameraState.free;
 const hint=cameraState.free?'QZDS: move � Drag: look � Wheel: zoom � Middle: pan':'Click: select � Drag: orbit � Wheel: zoom � Middle: pan';if($('cameraHint').textContent!==hint)$('cameraHint').textContent=hint;
 const note=document.querySelector('.footer-note'),text=note.textContent.replace(/COM follow|Free camera/,cameraState.free?'Free camera':'COM follow');if(note.textContent!==text)note.textContent=text;
}
function stopCameraMovement(){cameraKeys.clear();if(cameraRAF!==null)cancelAnimationFrame(cameraRAF);cameraRAF=null;cameraStamp=0;save();}
function moveCamera(stamp){
 cameraRAF=null;if(!cameraState.free||document.hidden||!cameraKeys.size){cameraStamp=0;return;}
 const seconds=cameraStamp?Math.min(.05,(stamp-cameraStamp)/1000):0;cameraStamp=stamp;
 BodyflipCamera.move(cameraState,cameraKeys,seconds);if(!playing)drawAll();
 cameraRAF=requestAnimationFrame(moveCamera);
}
function cameraKey(e,down){
 const key=e.key?.toLowerCase();if(!['q','z','d','s'].includes(key))return false;
 if(!down){if(!cameraKeys.delete(key))return false;if(!cameraKeys.size)stopCameraMovement();}
 else {
  const el=e.target;if(!cameraState.free||e.ctrlKey||e.altKey||e.metaKey||el?.isContentEditable||el?.tagName==='SELECT'||el?.tagName==='TEXTAREA'||(el?.tagName==='INPUT'&&!['checkbox','range','button'].includes(el.type)))return false;
  cameraKeys.add(key);if(cameraRAF===null)cameraRAF=requestAnimationFrame(moveCamera);
 }
 e.preventDefault();e.stopImmediatePropagation();return true;
}
function resetCamera(){stopCameraMovement();Object.assign(cameraState,cameraDefault);drawAll();save();}
class BodyflipRenderer extends WebGLMotionRenderer{
 bindCamera(){
  const c=this.canvas;c.addEventListener('contextmenu',e=>e.preventDefault());
  c.addEventListener('pointerdown',e=>{e.preventDefault();c.setPointerCapture(e.pointerId);this.drag={x:e.clientX,y:e.clientY,startX:e.clientX,startY:e.clientY,button:e.button,select:e.button===0&&!e.altKey,moved:false};if(this.drag.select)this.drag.selection=platformEditor?.previewSelection(e.clientX,e.clientY);});
  c.addEventListener('pointermove',e=>{if(!this.drag)return;if(this.drag.select&&!this.drag.moved){if(Math.hypot(e.clientX-this.drag.startX,e.clientY-this.drag.startY)<4)return;this.drag.moved=true;if(this.drag.selection){platformEditor?.finishSelection(this.drag.selection,true,true);this.drag.selection=null;}}const dx=e.clientX-this.drag.x,dy=e.clientY-this.drag.y;this.drag.x=e.clientX;this.drag.y=e.clientY;
   if(this.drag.button===2&&this.viewCamera){const v=this.viewCamera,depth=Math.max(.3,dot(sub(settings.target,v.eye),v.forward)),scale=depth/v.focalCss;settings.target=add(settings.target,e.shiftKey?mul(v.forward,-dy*scale):add(mul(v.right,dx*scale),mul(v.up,-dy*scale)));syncTarget();refreshAim({preview:true});}
   else if(this.drag.button===1){BodyflipCamera.pan(cameraState,this.viewCamera,dx,dy);}else{if(e.altKey&&platformEditor?.selected){platformEditor.selected=null;platformEditor.render();}BodyflipCamera.rotate(cameraState,dx,dy);}drawAll();});
  // Show the gizmo on press; only a completed click pauses playback. Orbit cancels the preview.
  const end=e=>{const d=this.drag;if(!d)return;this.drag=null;if(d.button===2)refreshAim();const orbit=d.moved||Math.hypot(e.clientX-d.startX,e.clientY-d.startY)>=4;if(d.selection)platformEditor?.finishSelection(d.selection,e.type!=='pointerup'||orbit,orbit);save();};c.addEventListener('pointerup',end);c.addEventListener('pointercancel',end);c.addEventListener('lostpointercapture',end);
  c.addEventListener('wheel',e=>{e.preventDefault();BodyflipCamera.wheel(cameraState,e.deltaY);drawAll();save();},{passive:false});c.addEventListener('dblclick',resetCamera);
 }
 draw(data,root){super.draw(data,root);if(!data)return;const gl=this.gl,mesh=this.extras||(this.extras=new LabVertexStream(40000)),lines=this.extraLines||(this.extraLines=new LabVertexStream(10000));mesh.length=0;lines.length=0;
  const translucent=this.platformSideFaces||(this.platformSideFaces=[]);translucent.length=0;const sideOpacity=1-settings.platformTranslucency;
  const target=settings.target,color=hit?[.3,1,.72]:[1,.38,.66];this.capsule(mesh,target,target,settings.radius,color,22,8);
  const ring=(center,a,b,r,col)=>{let prev=null;for(let n=0;n<=72;n++){const t=n*Math.PI/36,p=add(center,add(mul(a,Math.cos(t)*r),mul(b,Math.sin(t)*r)));if(prev)this.line(lines,prev,p,col);prev=p;}};
  ring(target,[1,0,0],[0,1,0],settings.radius*1.18,color);ring(target,[0,0,1],[0,1,0],settings.radius*1.18,color);
  const center=physics.com();this.capsule(mesh,center,center,.018,[.8,.7,1],10,3);const axis=flightFrame?.jumpMotion?.axis||C.flipAxis(settings.axis);this.line(lines,add(center,mul(axis,-.3)),add(center,mul(axis,.3)),[.7,.55,1]);
  {
   for(const surface of platformEditor?.surfaces()||flight?.surfaces||BodyflipSupport.scene(5,settings)){
    const [a,b,c,d]=surface.bounds,point=(x,z)=>surface.world([x,.008,z]);
    this.platformBox(mesh,translucent,surface,surface.id===platformEditor?.selected?[.38,.34,.23]:surface.id==='floor'?[.11,.19,.30]:surface.id==='left'?[.17,.24,.29]:[.22,.20,.30],sideOpacity);
    if(dot(surface.normal,sub(this.viewCamera.eye,surface.origin))<=0)continue;
    for(let x=Math.ceil(a*2)/2;x<b;x+=Math.max(.5,(b-a)/80))this.line(lines,point(x,c),point(x,d),[.24,.33,.42]);
    for(let z=Math.ceil(c*2)/2;z<d;z+=Math.max(.5,(d-c)/80))this.line(lines,point(a,z),point(b,z),[.24,.33,.42]);
    const corners=[point(a,c),point(b,c),point(b,d),point(a,d)];for(let i=0;i<4;i++)this.line(lines,corners[i],corners[(i+1)%4],[.85,.59,.32]);
   }
   const showTargets=flightFrame?.supportKind==='hand'?settings.handTargets:settings.footTargets;
   if(showTargets&&flightFrame?.supportTarget&&flightFrame.supportState!=='FREE'){
    const surface=flightFrame.surface||flight.surfaces[0],p=add(flightFrame.supportTarget,mul(surface.normal,.008));ring(p,surface.u,surface.v,.025,[.3,1,.72]);this.line(lines,data.points[flightFrame.supportBone??nameToIndex.get('foot_'+(flightFrame.supportFoot||flight.supportFoot).toLowerCase())],p,[.3,1,.72]);
   }
   const ideals=showTargets?flight?.idealDebug(simTime):null;
   if(ideals){const surface=ideals.surface;
    for(const ideal of ideals.targets){const p=add(ideal.point,mul(surface.normal,.012));ring(p,surface.u,surface.v,.075,ideal.selected?[.3,1,.72]:[1,.22,.20]);if(ideal.contact){const c=add(ideal.contact,mul(surface.normal,.014));for(const axis of [surface.u,surface.v])this.line(lines,add(c,mul(axis,-.035)),add(c,mul(axis,.035)),[1,.85,.2]);this.line(lines,p,c,[.6,.5,.25]);}}
   }
   // Sparse world-height ticks provide descent cues without a floor below the ledge.
   const cy=physics.com()[1],cz=physics.com()[2];for(let y=Math.floor(cy/2)*2-8;y<cy+8;y+=2){this.line(lines,[-2.6,y,cz-1],[-2.3,y,cz-1],[.24,.29,.4]);this.line(lines,[2.3,y,cz-1],[2.6,y,cz-1],[.24,.29,.4]);}
  }
  const contact=attackContact(data,displayedAttack());if(attackTime>=0||flightFrame?.attack){this.capsule(mesh,contact,contact,.022,[1,.9,.45],10,3);this.line(lines,contact,target,[.43,.38,.51]);}
  if(settings.ghost&&desiredPose){const ghost={...desiredPose,upperOnly:false,skeleton:true,hideSword:true,tint:[.35,.68,.87]};this.addBody(mesh,ghost);}
  // Render animation volumes with the same opaque depth pass as the scene.
  for(const kind of [0,1,2]){const unretimed=kind===2,other=kind===1;if(!(unretimed?settings.rawLeg:other?settings.animOtherLeg:settings.animLeg)||!flight)continue;const ghost=flight.animationLeg(simTime,data,unretimed,other);if(ghost){
   const col=unretimed||other?[1,.15,.15]:[.15,1,.3];
   this.addLeg(mesh,ghost.pose,ghost.foot,col);
  }}
  this.addProjectiles(mesh,data.projectiles);
  this.bindAndDraw(this.meshBuffer,mesh,gl.TRIANGLES);this.bindAndDraw(this.lineBuffer,lines,gl.LINES);
  this.drawPlatformSides(translucent,sideOpacity);
  const coneList=flightFrame?.supportKind==='hand'?(settings.showHandCones?flight.idealDebug(simTime)?.targets.map(t=>t.cone).filter(Boolean)||[]:[]):settings.showCone?[flight?.coneDebug(simTime,data)].filter(Boolean):[];
  for(const cone of coneList){if(cone){
   const overlay=this.coneLines||(this.coneLines=new LabVertexStream(1000));overlay.length=0;
   const n=cone.normal,a=normalize(cross(n,Math.abs(n[0])<.9?[1,0,0]:[0,0,1])),b=cross(n,a),col=cone.valid?[.2,1,.55]:[1,.3,.25];
   let prev=null;
   for(let i=0;i<=32;i++){const theta=i*Math.PI/16,p=add(cone.center,add(mul(a,Math.cos(theta)*cone.radius),mul(b,Math.sin(theta)*cone.radius)));if(prev)this.line(overlay,prev,p,col);if(i%4===0)this.line(overlay,cone.apex,p,col);prev=p;}
   const mark=(p,r,c)=>{for(const axis of [a,b])this.line(overlay,add(p,mul(axis,-r)),add(p,mul(axis,r)),c);};
   this.line(overlay,cone.apex,cone.center,col);mark(cone.apex,.018,col);mark(cone.wanted,.035,[1,.3,.75]);
   if(cone.contact){mark(cone.contact,.035,col);this.line(overlay,cone.wanted,cone.contact,[.65,.35,.6]);}
   gl.disable(gl.DEPTH_TEST);this.bindAndDraw(this.lineBuffer,overlay,gl.LINES);gl.enable(gl.DEPTH_TEST);
  }}
  if(settings.showJump&&flight){const push=flight.pushDebug(simTime);if(push){
   const overlay=this.jumpArrowMesh||(this.jumpArrowMesh=new LabVertexStream(7000));overlay.length=0;
   const n=normalize(push.direction),origin=push.origin,tip=add(origin,mul(n,1.4)),base=add(tip,mul(n,-.32)),col=[1,.88,.12];
   const a=normalize(cross(n,Math.abs(n[1])<.9?[0,1,0]:[1,0,0])),b=cross(n,a);
   this.capsule(overlay,origin,base,.04,col,10,3);
   for(let i=0;i<12;i++){
    const point=angle=>add(base,add(mul(a,Math.cos(angle)*.16),mul(b,Math.sin(angle)*.16)));
    const p=point(i*Math.PI/6),q=point((i+1)*Math.PI/6);
    this.triangle(overlay,tip,p,q,normalize(cross(sub(p,tip),sub(q,tip))),col);
    this.triangle(overlay,base,q,p,mul(n,-1),col);
   }
   gl.disable(gl.DEPTH_TEST);this.bindAndDraw(this.meshBuffer,overlay,gl.TRIANGLES);gl.enable(gl.DEPTH_TEST);
  }}
 }
}
function syncPlaybackReadout(time){$('timeRead').textContent=time.toFixed(2)+' s';$('frameRead').textContent='F '+Math.round(time*60);$('scrub').value=time;}
function supportHint(){
 const active=flight?.activeAt(simTime),reason=flightFrame?.failureReason;
 if(!active||!active.supportScores?.length||simTime<active.supportStart)return reason||'';
 const scores=active.supportScores.map(s=>s.foot+' '+((s.contactDistance??s.distance)*100).toFixed(1)+' cm'+(Number.isFinite(s.cost)?', score '+(s.cost*100).toFixed(1):'')+(s.eligible?'':' (unavailable)')).join(' / ');
 return (reason?reason+' · ':'')+'Selected '+active.supportFoot+(active.supportKind==='hand'?' hand':' foot')+' · At selection, after cone: '+scores+(active.supportKind==='hand'?'':'. Score = contact distance minus forward preference; lower wins')+'. Ideal rings: green selected, red other; small green ring: contact.';
}
function drawAll(){if(!renderer||!currentPose)return;configureThrows();syncCameraUI();const data={...currentPose,projectiles:throwController?.sample(simTime,currentPose)||[],bicolor:settings.bicolor,skeleton:settings.skeleton,upperOnly:false,hideSword:!(displayedAttack()==='pike'||displayedAttack().startsWith('slash')),tint:[.91,.49,.25],voidScene:true};renderer.draw(data,physics.com());platformEditor?.render();syncPlaybackReadout(simTime);const now=performance.now();if(playing&&now-lastHUD<100)return;lastHUD=now;$('fallRead').textContent=Math.max(0,-physics.com(true)[1]).toFixed(1);$('flipRead').textContent=(flightFrame?.spin?.flipRate??0).toFixed(0)+'°';$('twistRead').textContent=(flightFrame?.spin?.twistRate??0).toFixed(0)+'°';$('missRead').textContent=Number.isFinite(bestMiss)?(bestMiss*100).toFixed(1)+' cm':'—';$('hitRead').textContent=hit?'HIT':(attackTime>=0||flightFrame?.attack)?'…':'—';$('hitRead').style.color=hit?'#68e1ad':'';$('phase').textContent=(playing?'':'PAUSED · ')+(flightFrame?.phase||(settings.mode==='idle'?'IDLE':'RUN'));$('phase').title=supportHint();$('scrub').max=timelineMax();syncTrim();$('scrub').setAttribute('aria-label','Sequence timeline');}
function syncTarget(){['X','Y','Z'].forEach((k,i)=>$('target'+k).value=settings.target[i].toFixed(2));}
function syncPlaybackSpeed(){$('playbackSpeed').value=settings.playbackSpeed;$('playbackSpeedRead').value=settings.playbackSpeed.toFixed(1)+'×';$('playbackSpeed').setAttribute('aria-valuetext',settings.playbackSpeed.toFixed(1)+' times');}
function syncControls(){$('momentum3D').checked=settings.momentum3D;$('kickToArmed').checked=settings.kickToArmed;$('softAttackLegs').checked=settings.softAttackLegs;$('platformTranslucency').value=Math.round(settings.platformTranslucency*100);$('platformTools').hidden=false;jumpTrack?.sync();$('ramps').checked=settings.ramps;syncTrim();syncPlaybackSpeed();for(const k of ['startYaw','legFollow','spinLag','handCone','handFollow','spinInertia','handBend','pelvisAttackCompensation','loadMs','rebound','jumpSkew','supportCone','supportReach','supportTrigger','supportAlpha','supportSpeed','jumpEarly','standRatio','plantPitch','toeOffPitch','footRollSpeed','jumpBuildX','jumpBuildY','loadYMs','loadFullMs','buildDepth'])$(k).value=['spinLag','spinInertia','pelvisAttackCompensation','supportTrigger','jumpSkew','rebound','buildDepth'].includes(k)?+(settings[k]*100).toFixed(4):settings[k]; $('mode').value=settings.mode;$('gaitLabel').textContent=settings.mode==='spaceGym'?'Start':settings.mode==='idle'?'Idle':settings.mode==='walk'?'Walk':'Run';$('runSeconds').setAttribute('aria-label',settings.mode==='idle'?'Idle duration':settings.mode==='walk'?'Walk duration':'Run duration');$('motion').value=settings.motion;$('engine').textContent=settings.motion==='kinematic'?(settings.mode==='idle'?'Kinematic \u00b7 Idle':'Kinematic \u00b7 NN target'):'Jolt · 25 bodies';document.querySelector('.footer-note').textContent=settings.motion==='kinematic'?'Kinematic · COM follow':settings.mode!=='idle'?'Sim · Local 0 · COM follow':'Idle \u00b7 COM follow';$('runControls').hidden=$('minorOptions').hidden=false;$('airFlip').checked=settings.airFlip;$('matchLeg').checked=settings.matchLeg;$('surfaceIK').checked=settings.surfaceIK;$('surfaceIK').disabled=!BodyflipFootIK.available;$('footIKStatus').textContent=BodyflipFootIK.available?'':' (server restart needed)';$('jumpFoot').value=settings.jumpFoot;for(const k of ['runSeconds','runPhase','jumpBlend','legBlend','handReturn','fallCap']){$(k).value=settings[k];$(k+'Read').textContent=k==='runPhase'?Math.round(settings[k]*100)+'%':settings[k].toFixed(k==='fallCap'?0:2);}for(const k of ['flipSpeed','flipAngle','twistAngle','twistSpeed','attackRate','aimWeight','radius']){if($(k))$(k).value=settings[k];if($(k+'Range'))$(k+'Range').value=settings[k];}for(const k of ['showHandCones','footTargets','handTargets','undoRotation','aim','loop','ghost','animLeg','animOtherLeg','rawLeg','showCone','showJump','bicolor','skeleton'])$(k).checked=settings[k];$('aimAmount').value=Math.round(settings.aimWeight*100)+'%';$('axisLabel').textContent=C.dirs[settings.axis];for(const b of document.querySelectorAll('#axisGrid [data-axis]')){b.classList.toggle('active',+b.dataset.axis===settings.axis);b.setAttribute('aria-pressed',String(+b.dataset.axis===settings.axis));}syncTarget();}
async function loadAttack(name,id){const rev=++loadRevision;vanillaManifest ||= await fetch('data/vanilla.json').then(r=>r.json());const wasPlaying=playing,wasDrawn=settings.attack==='pike'||settings.attack.startsWith('slash');setPlaying(false);$('strike').disabled=true;const family=manifest.clips.find(c=>c.name===name)||manifest.clips[0],meta=family.variants.find(v=>v.id===+id)||family.variants[0];let decoded=cache.get(meta.file);if(!decoded){const r=await fetch(meta.file);if(!r.ok)throw Error('Attack unavailable');decoded=C.decode(meta,await r.arrayBuffer(),names,parents);cache.set(meta.file,decoded);}if(rev!==loadRevision)return;settings.attack=family.name;settings.variant=meta.id;clip=decoded;await loadVanilla();if(rev!==loadRevision)return;$('attack').value=family.name;$('variant').replaceChildren(...family.variants.map(v=>new Option(String(v.id).padStart(2,'0'),v.id)));$('variant').value=meta.id;$('scrub').max=total();attackTime=-1;manualResponse=null;hit=false;bestMiss=Infinity;if(flight&&wasDrawn!==(settings.attack==='pike'||settings.attack.startsWith('slash')))await prepareRun({preserveTime:true});else resetPhysics();$('strike').disabled=false;if(wasPlaying)setPlaying(true);save();}
let jumpTrack=null;
function buildUI(){
 syncScenes();$('scene').onchange=()=>changeScene('select',$('scene').value).catch(fail);$('copyScene').onclick=()=>changeScene('copy').catch(fail);$('renameScene').onclick=()=>changeScene('rename').catch(fail);$('newScene').onclick=()=>changeScene('new').catch(fail);
 platformEditor=new BodyflipPlatforms.Editor({get:()=>({settings,edge:flight?.edge??5,surfaces:flight?.surfaces||BodyflipSupport.scene(5,settings),camera:renderer?.viewCamera,rect:$('viewport').getBoundingClientRect(),center:physics?.com()||pivot}),pause:()=>setPlaying(false),draw:drawAll,change:list=>{settings=C.sanitize({...settings,platforms:list});},commit:()=>prepareRun({preserveTime:true}).catch(fail)});
 $('addPlatform').onclick=()=>{if(!loadingRun&&renderer?.viewCamera)platformEditor.add();};
 jumpTrack=new JumpTrack({get:()=>({settings,events:F.eventsFor(settings),results:flight?.events||[],time:simTime,max:timelineMax()}),edit:events=>{settings=C.sanitize({...settings,jumpEvents:events});prepareRun({preserveTime:true}).catch(fail);},seek:previewSeek});
 $('platformTranslucency').onchange=()=>{settings=C.sanitize({...settings,platformTranslucency:+$('platformTranslucency').value/100});$('platformTranslucency').value=Math.round(settings.platformTranslucency*100);drawAll();save();};
 $('ramps').onchange=()=>{settings.ramps=$('ramps').checked;prepareRun({preserveTime:true}).catch(fail);};
 // Pointer handlers prevent native focus transfer; viewport clicks must leave editors.
 $('viewport').tabIndex=-1;
 document.addEventListener('pointerdown',e=>{const active=document.activeElement;if(active?.matches('input[type="number"]')&&e.target!==active)active.blur();if(e.target===$('viewport')||$('platformGizmo').contains(e.target))$('viewport').focus({preventScroll:true});},true);
 document.addEventListener('keydown',e=>{if(e.code==='Enter'&&e.target.matches?.('input[type="number"]')){e.preventDefault();e.target.blur();}},true);
 $('playbackSpeed').oninput=()=>{settings.playbackSpeed=C.sanitize({playbackSpeed:+$('playbackSpeed').value}).playbackSpeed;lastStamp=0;accumulator=0;syncPlaybackSpeed();save();};
 for(const key of ['trimIn','trimOut']){
  const el=$(key);let drag=null;
  el.onpointerdown=e=>{if(e.button!==0)return;e.preventDefault();e.stopPropagation();el.focus();el.setPointerCapture(e.pointerId);drag={x:e.clientX,time:settings[key],returnTime:previewRAF!==null?previewTime:simTime,width:$('trimControls').getBoundingClientRect().width,max:+el.getAttribute('aria-valuemax')};el.classList.add('dragging');};
  el.onpointermove=e=>{if(drag)moveTrim(key,drag.time+(e.clientX-drag.x)*drag.max/drag.width);};
  const end=()=>{if(!drag)return;const returnTime=drag.returnTime;drag=null;el.classList.remove('dragging');finishPreview(returnTime);};el.onpointerup=end;el.onpointercancel=end;el.onlostpointercapture=end;
  el.onkeydown=e=>{let value=settings[key];if(e.code==='Home')value=key==='trimIn'?0:settings.trimIn+1/60;else if(e.code==='End')value=key==='trimIn'?settings.trimOut-1/60:+el.getAttribute('aria-valuemax');else return;e.preventDefault();e.stopPropagation();moveTrim(key,value);};
 }
 $('trimLoop').onchange=()=>{const enabled=$('trimLoop').checked;setPlaying(false);settings.trimLoop=enabled;syncTrim();save();if(trimActive()&&(simTime<settings.trimIn||simTime>=settings.trimOut))seek(settings.trimIn).catch(fail);};

 $('motion').onchange=()=>{++seekRevision;seeking=false;setPlaying(false);settings.motion=$('motion').value;simTime=0;attackTime=-1;flip=settings.flipAngle;twist=settings.twistAngle;syncControls();resetPhysics();save();};
 $('mode').onchange=()=>{settings.mode=$('mode').value;simTime=0;attackTime=-1;flip=twist=0;setPlaying(false);syncControls();prepareRun().catch(fail);save();};
 for(const k of ['runSeconds','runPhase','jumpBlend','legBlend','handReturn','fallCap']){$(k).oninput=()=>{settings=C.sanitize({...settings,[k]:+$(k).value});setPlaying(false);syncControls();};$(k).onchange=()=>prepareRun({preserveTime:true}).catch(fail);}
 $('kickToArmed').onchange=()=>{settings.kickToArmed=$('kickToArmed').checked;prepareRun({preserveTime:true}).catch(fail);};
 $('softAttackLegs').onchange=()=>{settings.softAttackLegs=$('softAttackLegs').checked;prepareRun({preserveTime:true}).catch(fail);};
 $('momentum3D').onchange=()=>{settings.momentum3D=$('momentum3D').checked;prepareRun({preserveTime:true}).catch(fail);};

 $('surfaceIK').onchange=()=>{settings.surfaceIK=$('surfaceIK').checked;prepareRun({preserveTime:true}).catch(fail);};
 $('matchLeg').onchange=()=>{settings.matchLeg=$('matchLeg').checked;prepareRun({preserveTime:true}).catch(fail);};
 for(const k of ['startYaw','legFollow','spinLag','handCone','handFollow','spinInertia','handBend','pelvisAttackCompensation','loadMs','rebound','jumpSkew','supportCone','supportReach','supportTrigger','supportAlpha','supportSpeed','jumpEarly','standRatio','plantPitch','toeOffPitch','footRollSpeed','jumpBuildX','jumpBuildY','loadYMs','loadFullMs','buildDepth'])$(k).onchange=()=>{settings=C.sanitize({...settings,[k]:+$(k).value/(['spinLag','spinInertia','pelvisAttackCompensation','supportTrigger','jumpSkew','rebound','buildDepth'].includes(k)?100:1)});syncControls();prepareRun({preserveTime:true}).catch(fail);};
 $('jumpFoot').onchange=()=>{settings.jumpFoot=$('jumpFoot').value;prepareRun({preserveTime:true}).catch(fail);};
 $('airFlip').onchange=()=>{settings.airFlip=$('airFlip').checked;prepareRun({preserveTime:true}).catch(fail);};

 for(const k of ['flipSpeed','flipAngle','twistAngle','twistSpeed']){const field=$(k),range=$(k+'Range');field.parentElement.classList.add('compact');field.parentElement.insertBefore(range,field);}
 const slots=[[3,1],[4,1],[5,2],[5,3],[5,4],[4,5],[3,5],[2,5],[1,4],[1,3],[1,2],[2,1]];
 C.dirs.forEach((name,i)=>{const b=document.createElement('button');b.textContent=name;b.dataset.axis=i;b.style.gridColumn=slots[i][0];b.style.gridRow=slots[i][1];b.title=`${name} · ${i*30}° axis heading`;b.onclick=()=>{settings.axis=i;flip=0;settings.flipAngle=0;syncControls();if(settings.airFlip||F.eventsFor(settings).some(e=>e.flip&&(e.turnAxis===null||e.turnAxis===undefined)))prepareRun({preserveTime:true}).catch(fail);else {resetPhysics();save();}};$('axisGrid').append(b);});
 const labels={headbutt:'Headbutt',hookL:'Hook L',hookR:'Hook R',jabL:'Jab L',jabR:'Jab R',KickL:'Kick L',KickR:'Kick R',overL:'Over L',overR:'Over R',pike:'Pike',slashL:'Slash L',slashLD:'Slash LD',slashLU:'Slash LU',slashR:'Slash R',slashRD:'Slash RD',slashRU:'Slash RU',sweepKick:'Sweep kick'};
 $('attack').replaceChildren(...manifest.clips.map(c=>new Option(labels[c.name]||c.name,c.name)));$('attack').onchange=()=>loadAttack($('attack').value,settings.variant).catch(fail);$('variant').onchange=()=>loadAttack(settings.attack,+$('variant').value).catch(fail);
 for(const k of ['flipSpeed','flipAngle','twistAngle','twistSpeed','attackRate','aimWeight','radius'])for(const id of [k,k+'Range'])if($(id))$(id).oninput=()=>{const v=Number($(id).value);if(!Number.isFinite(v))return;settings=C.sanitize({...settings,[k]:v});if(k==='flipAngle')flip=settings[k];if(k==='twistAngle')twist=settings[k];if(id!==k)$(k).value=settings[k];if($(k+'Range')&&id!==k+'Range')$(k+'Range').value=settings[k];$('aimAmount').value=Math.round(settings.aimWeight*100)+'%';if(k==='flipAngle'||k==='twistAngle')resetPhysics();else if(k==='aimWeight')refreshAim();else drawAll();save();};
 for(const k of ['flipSpeed','flipAngle','twistAngle','twistSpeed'])for(const id of [k,k+'Range'])if($(id))$(id).onchange=()=>{if(settings.airFlip)prepareRun({preserveTime:true}).catch(fail);};
 for(const k of ['showHandCones','footTargets','handTargets','undoRotation','aim','loop','ghost','animLeg','animOtherLeg','rawLeg','showCone','showJump','bicolor','skeleton'])$(k).onchange=()=>{settings[k]=$(k).checked;if(k==='aim'||k==='undoRotation')refreshAim();else drawAll();save();};
 ['X','Y','Z'].forEach((k,i)=>$('target'+k).oninput=()=>{if(Number.isFinite(+$('target'+k).value)){settings.target[i]=clamp(+$('target'+k).value,-1000000,1000000);refreshAim();save();}});
 $('zeroTwist').onclick=()=>{settings.twistAngle=twist=0;settings.twistSpeed=0;syncControls();if(settings.airFlip)prepareRun({preserveTime:true}).catch(fail);else {resetPhysics();save();}};$('resetTarget').onclick=()=>{settings.target=currentPose?add(currentPose.points[1],[.4,.15,.8]):[...C.defaults.target];syncTarget();refreshAim();save();};
 $('play').onclick=()=>setPlaying(!playing);$('strike').onclick=strike;$('stopAttack').onclick=cancelAttack;$('step').onclick=()=>stepFrame(1);$('reset').onclick=()=>{setPlaying(false);flip=settings.flipAngle=0;twist=settings.twistAngle=0;simTime=0;attackTime=-1;hit=false;bestMiss=Infinity;syncControls();prepareRun().catch(fail);save();};
 $('scrub').oninput=()=>{const time=+$('scrub').value;previewSeek(time);syncPlaybackReadout(time);};$('scrub').onchange=()=>finishPreview(+$('scrub').value);
 $('followCamera').onchange=()=>{if(!renderer?.viewCamera)return;stopCameraMovement();BodyflipCamera.toggle(cameraState,!$('followCamera').checked,renderer.viewCamera,physics?.com()||pivot);drawAll();save();};
 $('cameraReset').onclick=resetCamera;$('cameraFront').onclick=()=>{Object.assign(cameraState,cameraDefault,{yaw:0,pitch:0});drawAll();save();};$('cameraSide').onclick=()=>{Object.assign(cameraState,cameraDefault,{yaw:Math.PI/2,pitch:0});drawAll();save();};$('cameraTop').onclick=()=>{Object.assign(cameraState,cameraDefault,{yaw:0,pitch:-5});drawAll();save();};
 $('save').onclick=()=>persist(stored()).then(()=>notice('Saved')).catch(fail);$('refresh').onclick=refreshLab;$('snapshot').onclick=async()=>{setPlaying(false);try{const r=await post('/snapshot',{...stored(),pose:currentPose,target:settings.target,attackTime,diagnostics:physics.diagnostics(),image:$('viewport').toDataURL('image/png')});notice('Snapshot '+r.name);}catch(e){fail(e);}};
 const writing=el=>el?.isContentEditable||(!el?.readOnly&&!el?.disabled&&(el?.tagName==='TEXTAREA'||(el?.tagName==='INPUT'&&!['range','checkbox','radio','button','submit','reset','file','image','color','hidden'].includes(el.type))));
 const arrows=(e,down=false)=>{if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.code)||writing(e.target))return false;e.preventDefault();e.stopImmediatePropagation();if(down&&(e.code==='ArrowLeft'||e.code==='ArrowRight'))stepFrame(e.code==='ArrowLeft'?-1:1);return true;};
 const space=e=>{if(e.code!=='Space'||e.altKey||e.ctrlKey||e.metaKey||e.target.isContentEditable||e.target.tagName==='TEXTAREA'||(e.target.tagName==='INPUT'&&['text','search','password','email','url'].includes(e.target.type)))return false;e.preventDefault();e.stopImmediatePropagation();return true;};
 window.addEventListener('keydown',e=>{if(e.code==='Escape'&&jumpTrack?.open){e.preventDefault();e.stopImmediatePropagation();jumpTrack.close();return;}if(cameraKey(e,true))return;if(BodyflipPlatforms.undoShortcut(e)){e.preventDefault();e.stopImmediatePropagation();if(!e.repeat)platformEditor?.undo();return;}if(!writing(e.target)&&e.target.tagName!=='SELECT'&&!e.ctrlKey&&!e.altKey&&!e.metaKey&&platformEditor?.key(e)){e.preventDefault();e.stopImmediatePropagation();return;}if(arrows(e,true))return;if(space(e)){if(!e.repeat)setPlaying(!playing);return;}if(e.target.classList?.contains('trim-bracket'))return;if(e.repeat||/INPUT|SELECT|TEXTAREA/.test(e.target.tagName))return;if(e.code==='KeyA'){e.preventDefault();strike();}if(e.code==='KeyR')$('reset').click();},true);
 window.addEventListener('keyup',e=>{if(cameraKey(e,false))return;if(!arrows(e))space(e);},true);
 window.addEventListener('blur',stopCameraMovement);
 document.addEventListener('focusin',e=>{if(writing(e.target)||e.target.tagName==='SELECT')stopCameraMovement();});
 document.addEventListener('visibilitychange',()=>{if(document.hidden){stopCameraMovement();if(previewRAF!==null)cancelAnimationFrame(previewRAF);previewRAF=null;setPlaying(false);}});
}
function decodeB64(raw,Type){const b=Uint8Array.from(atob(raw),c=>c.charCodeAt(0));return new Type(b.buffer);}
async function init(){const [m,s,sw,jumpData,standingData,idleMeta,idleBytes]=await Promise.all([fetch('data/manifest.json').then(r=>r.json()),fetch('/state').then(r=>r.json()),fetch('data/sword.json').then(r=>r.json()),fetch('data/jumps.json').then(r=>r.json()),fetch('data/jumps-standing.json').then(r=>r.json()),fetch('data/idle.json').then(r=>r.json()),fetch('data/idle.bin').then(r=>r.arrayBuffer())]);sceneLibrary=BodyflipScenes.open(s);jumps=[...jumpData.clips,...standingData.clips].map(F.decodeJump);manifest=m;names=m.names;parents=m.parents;nameToIndex=new Map(names.map((n,i)=>[n,i]));settings=C.sanitize(BodyflipPlatforms.restoreDefaultsOnce(s.settings));flip=settings.flipAngle;twist=settings.twistAngle;BodyflipCamera.restore(cameraState,s.camera,cameraDefault);
 swordMesh={...sw,vertices:decodeB64(sw.vertices_b64,Float32Array),triangles:decodeB64(sw.triangles_b64,Int32Array),bladeMask:decodeB64(sw.blade_mask_b64,Uint8Array)};idle=C.poseFromShared(m);idleLoop=BodyflipIdle.create(idleMeta,idleBytes,m);const f=R.rotate(idle.q[1],[0,-1,0]);basePelvis=R.qm(R.fromTo(normalize([f[0],0,f[2]]),[0,0,1]),idle.q[1]);
 buildUI();syncControls();renderer=new BodyflipRenderer($('viewport'),{pixelRatio:Math.min(devicePixelRatio,1.5)});
 const {createPhysics}=await import('./physics.mjs');physics=await createPhysics(manifest,C.centerPose(idle,rotation(),pivot));renderer.torsoColliders=physics.torso;throwController=BodyflipThrows.create({physics,renderer});$('engine').textContent='Jolt · 25 bodies';await loadAttack(settings.attack,settings.variant);await prepareRun();await restorePlayback(s.playback);syncControls();sceneReady=true;syncScenes();save();
 window.BodyflipLab={get state(){const active=flight?.activeAt(simTime);return {settings:{...settings},flip,twist,attackTime,simTime,frame:Math.round(simTime*60),playing,hit,bestMiss,errors:[...errors],pose:currentPose,diagnostics:physics.diagnostics(),torso:physics.torsoWorld(),torsoGeometry:physics.torsoGeometry(),flight:flight?{preparedThrough:flight.preparedThrough,footIK:flightFrame?.footIK||null,footIKSource:window.SharedFootIK?.sourceHash,footIKAvailable:BodyflipFootIK.available,capsule:flight.capsule,landings:flight.landings,edge:flight.edge,phase:flightFrame?.phase,spin:flightFrame?.spin||null,jumpMotion:flightFrame?.jumpMotion||null,attack:flightFrame?.attack||null,root:flightFrame?.root,events:flight.events,surfaces:flight.surfaces.map(s=>({id:s.id,normal:s.normal,bounds:s.bounds})),...(active?{airStart:active.airStart,apex:active.apex,sourceStart:active.sourceStart,jumpStyle:active.jumpStyle,takeoffSpeed:active.takeoffSpeed,standingThreshold:active.standingThreshold,matchLeg:settings.matchLeg,legMatchTime:active.matchTime,legRate:active.legRate,legMatchDistance:active.matchDistance,legArrival:active.jumpStart+active.loopStart,jumpStart:active.jumpStart,contactTime:active.contactTime,loadDuration:active.bounce?.loadDuration,compression:active.bounce?.compression,returnedEnergy:active.bounce?.returnedEnergy,supportStart:active.supportStart,abortTime:active.abortTime,failureReason:flightFrame?.failureReason||null,supportDistance:flightFrame?.distance,supportHistory:(active.support?.frames||[]).map(f=>({time:active.supportStart+f.t,distance:f.distance,reachable:f.reachable,approachSpeedCmS:f.approachSpeed*100,reachWait:f.reachWait,hipDistance:f.hipDistance})),supportIdealRoot:active.support?.idealLocal,release:active.release,supportState:flightFrame?.supportState,supportTarget:flightFrame?.supportTarget,supportCone:settings.showCone?flight.coneDebug(simTime,currentPose):null,supportFoot:active.supportFoot,supportKind:active.supportKind,supportBone:active.supportBone,supportScores:active.supportScores,surfaceChoices:active.surfaceChoices,supportIdeals:flight.idealDebug(simTime),supportLead:active.support?.terminal?.appliedShift,supportLimited:active.support?.terminal?.limited}:{})}:null,com:physics.com(),velocity:physics.com(true),cameraCenter:renderer.viewCamera?.target,loadingRun};},prepareRun,seek,playbackStep,step(count=1){setPlaying(false);for(let i=0;i<count;i++)tick();drawAll();return this.state;},strike,loadAttack,setPlaying,reset:()=> $('reset').click(),targetPose,project(p){const m=renderer.viewProjection,r=$('viewport').getBoundingClientRect(),w=m[3]*p[0]+m[7]*p[1]+m[11]*p[2]+m[15];return {x:r.left+(1+(m[0]*p[0]+m[4]*p[1]+m[8]*p[2]+m[12])/w)*r.width/2,y:r.top+(1-(m[1]*p[0]+m[5]*p[1]+m[9]*p[2]+m[13])/w)*r.height/2};}};
 $('play').disabled=false;$('step').disabled=false;$('engine').title='25 rigid bodies · 24 joints · knee/elbow hinges · local lab profile';
}
init().catch(fail);
