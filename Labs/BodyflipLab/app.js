'use strict';
const $=id=>document.getElementById(id),R=Recovery,C=BodyflipCore,{add,sub,mul,dot,cross,length:norm,unit:normalize}=R;
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v)),posAt=(data,j)=>data.points[j],axisAt=(data,j,a)=>data.axes[j][a];
let names=[],parents=[],nameToIndex=new Map(),swordMesh=null,manifest=null,idle=null,basePelvis=null,physics=null,renderer=null,clip=null;
let settings=C.sanitize(),flip=0,twist=0,attackTime=-1,playing=false,raf=null,lastStamp=0,accumulator=0,saveTimer=null,currentPose=null,desiredPose=null,previousContact=null,hit=false,bestMiss=Infinity,simTime=0,loadRevision=0;
const F=BodyflipFlight;let flight=null,jumps=[],run=null,flightFrame=null,runRevision=0,loadingRun=false;const runCache=new Map();let seekRevision=0,seeking=false,lastHUD=0;
const pivot=[0,1.5,0],cameraDefault={yaw:-.55,pitch:-.06,zoom:.95,panX:0,panY:0},cameraState={...cameraDefault},cache=new Map(),errors=[];
let playRevision=0,previewRAF=null,previewTime=0,platformEditor=null;
let sceneLibrary=null,sceneChanging=false,sceneReady=false,stateWrites=Promise.resolve();
function trimActive(){return settings.mode!=='space'&&!!flight;}
function timelineMax(){return Math.max(12,settings.trimOut,Math.ceil(simTime),...F.eventsFor(settings).map(e=>Math.ceil(e.time+1)));}
function syncTrim(){const max=timelineMax();if(jumpTrack&&jumpTrack.max!==max)jumpTrack.sync();$('trimControls').hidden=$('trimToggle').hidden=settings.mode==='space';$('trimLoop').checked=settings.trimLoop;for(const key of ['trimIn','trimOut']){const el=$(key),t=settings[key];el.style.left=(100*t/max)+'%';el.setAttribute('aria-valuenow',t);el.setAttribute('aria-valuemax',max);el.setAttribute('aria-valuetext',t.toFixed(3)+' seconds');el.dataset.time=(key==='trimIn'?'In ':'Out ')+t.toFixed(3)+' s';} $('trimSelection').style.left=(100*settings.trimIn/max)+'%';$('trimSelection').style.width=(100*(settings.trimOut-settings.trimIn)/max)+'%';}
function previewSeek(time){previewTime=time;++seekRevision;seeking=false;if(playing)setPlaying(false);else ++playRevision;if(previewRAF===null)previewRAF=requestAnimationFrame(()=>{previewRAF=null;seek(previewTime).catch(fail);});}
function stepFrame(direction){
 if(!physics||loadingRun)return;
 const current=previewRAF!==null?previewTime:settings.mode!=='space'?simTime:Math.max(0,attackTime);
 previewSeek(clamp((Math.round(current*60)+direction)/60,0,settings.mode!=='space'?600:total()));
}
function finishPreview(time){if(previewRAF!==null)cancelAnimationFrame(previewRAF);previewRAF=null;seek(time).catch(fail);}
function moveTrim(key,value){const t=Math.round(clamp(value,0,600)*60)/60;settings[key]=key==='trimIn'?Math.min(t,settings.trimOut-1/60):Math.max(t,settings.trimIn+1/60);settings.trimLoop=true;syncTrim();previewSeek(settings[key]);save();}
function placeKinematic(time){simTime=Math.round(time*60)/60;const air=flight&&settings.airFlip?Math.max(0,simTime-(flight.airStartAt?.(simTime)??flight.airStart)):0;flip=settings.flipAngle+settings.flipSpeed*air;twist=settings.twistAngle+settings.twistSpeed*air;attackTime=-1;previousContact=null;hit=false;bestMiss=Infinity;desiredPose=targetPose();physics.reset(desiredPose,[0,flightFrame?.vy||0,flight?.speed||0]);currentPose=physics.read();drawAll();}
function restartTrim(){const job=seek(settings.trimIn),revision=playRevision;job.then(()=>{if(revision===playRevision&&!document.hidden)setPlaying(true);}).catch(fail);}
function playbackStep(){if(trimActive()){
 if(simTime>=settings.trimOut-1e-8&&!settings.trimLoop){setPlaying(false);return false;}
 if(simTime<settings.trimIn-1e-8||simTime>=settings.trimOut-1e-8){if(settings.motion==='kinematic')placeKinematic(settings.trimIn);else {restartTrim();return false;}}}
 tick(trimActive()?settings.trimOut:Infinity);return true;}
window.addEventListener('error',e=>fail(e.error||e.message));window.addEventListener('unhandledrejection',e=>fail(e.reason));
function fail(e){const msg=e?.message||String(e);errors.push(msg);$('error').hidden=false;$('error').textContent=msg;setPlaying(false);console.error(e);}
function notice(text){$('toast').textContent=text;$('toast').hidden=false;clearTimeout(notice.timer);notice.timer=setTimeout(()=>$('toast').hidden=true,2500);}
async function post(path,data){const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});if(!r.ok)throw Error((await r.json()).error||'Save failed');return r.json();}
function playbackState(){return {time:previewRAF!==null&&settings.mode!=='space'?previewTime:simTime,attackTime:previewRAF!==null&&settings.mode==='space'?previewTime:attackTime,flip,twist,playing,hit,bestMiss:Number.isFinite(bestMiss)?bestMiss:null};}
function stored(){const state={schema:'bodyflip-lab-v1',settings:{...settings},camera:{...cameraState},playback:playbackState()};if(!sceneLibrary)return state;sceneLibrary=BodyflipScenes.capture(sceneLibrary,state);return BodyflipScenes.pack(sceneLibrary);}
function persist(state){const payload=JSON.parse(JSON.stringify(state));const job=stateWrites.catch(()=>{}).then(()=>post('/state',payload));stateWrites=job;return job;}
function syncScenes(){$('scene').replaceChildren(...sceneLibrary.items.map(s=>new Option(s.name,s.id)));$('scene').value=sceneLibrary.active;for(const id of ['scene','copyScene','renameScene'])$(id).disabled=!sceneReady||sceneChanging;}
async function changeScene(action,id){
 if(!sceneReady||sceneChanging||loadingRun||$('strike').disabled){syncScenes();return;}
 const current=sceneLibrary.items.find(s=>s.id===sceneLibrary.active);
 const name=action==='select'?null:prompt(action==='copy'?'Name the new scene (copies this setup)':'Scene name',action==='copy'?current.name+' copy':current.name);
 if(action!=='select'&&(name===null||!name.trim())){syncScenes();return;}
 const previous=stored().scenes;
 let next=action==='select'?BodyflipScenes.select(previous,id):action==='copy'?BodyflipScenes.copy(previous,name,crypto.randomUUID()):BodyflipScenes.rename(previous,name);
 sceneChanging=true;document.body.inert=true;syncScenes();setPlaying(false);clearTimeout(saveTimer);saveTimer=null;
 ++seekRevision;if(previewRAF!==null)cancelAnimationFrame(previewRAF);previewRAF=null;
 // Reload only after the entire library is saved. This also isolates undo and pending animation loads.
 try{await persist(BodyflipScenes.pack(next));sceneLibrary=next;location.reload();}
 catch(e){sceneLibrary=previous;sceneChanging=false;document.body.inert=false;syncScenes();fail(e);}
}
async function restorePlayback(state){
 if(!state||!Number.isFinite(state.time))return;
 const time=clamp(state.time,0,600);
 if(settings.mode!=='space')await seek(time);else simTime=time;
 attackTime=Number.isFinite(state.attackTime)?clamp(state.attackTime,-1,total()):-1;
 if(Number.isFinite(state.flip))flip=state.flip;if(Number.isFinite(state.twist))twist=state.twist;
 if(settings.mode==='space'||settings.motion==='kinematic')resetPhysics();
 hit=!!state.hit;bestMiss=Number.isFinite(state.bestMiss)?state.bestMiss:Infinity;
 setPlaying(state.playing===true&&!document.hidden);drawAll();
}
async function refreshLab(){
 // Snapshot BEFORE pausing. Cancel delayed saves/seeks that could overwrite it.
 const snapshot=stored();setPlaying(false);clearTimeout(saveTimer);saveTimer=null;
 ++seekRevision;if(previewRAF!==null)cancelAnimationFrame(previewRAF);previewRAF=null;
 try{await persist(snapshot);location.reload();}catch(e){fail(e);}
}
function save(){clearTimeout(saveTimer);if(!sceneReady||sceneChanging)return;saveTimer=setTimeout(()=>{if(!sceneChanging)persist(stored()).catch(fail);},250);}
function wrap(x){return ((x+180)%360+360)%360-180;}
function rotation(){return C.orientation(flip,twist,settings.axis,basePelvis);}
function targetPose(){const raw=clip?C.sample(clip,attackTime,idle,parents):idle;let pose;
 if(settings.mode!=='space'&&flight){flightFrame=flight.sample(simTime,settings.airFlip?flip:0,settings.airFlip?twist:0,settings.axis);pose=flightFrame.pose;
  if(attackTime>=0&&clip){const attack=C.centerPose(raw,pose.q[1],pose.points[1]),weight=Math.min(clamp(attackTime/.15,0,1),clamp((total()-attackTime)/.45,0,1));pose=C.blend(pose,attack,weight,parents);}
 }else pose=C.centerPose(raw,rotation(),pivot);
 if(settings.aim&&attackTime>=0&&clip){const progress=clamp((attackTime-.10)/Math.max(.1,clip.duration+.12),0,1),weight=settings.aimWeight*Math.sin(Math.PI*progress);pose=C.aimPose(pose,settings.target,settings.attack,names,parents,swordMesh,weight);}return pose;}
function resetPhysics(){if(!physics)return;const dynamic=settings.mode!=='space'&&!!flight;physics.configure({dynamic,kinematic:settings.motion==='kinematic',edge:flight?.edge||5,surfaces:flight?.surfaces,cap:settings.fallCap});desiredPose=targetPose();if(dynamic||settings.motion==='kinematic')physics.reset(desiredPose,[0,flightFrame?.vy||0,flight?.speed||0]);else {const rest=C.centerPose(idle,rotation(),pivot);physics.reset(rest);for(let i=0;i<60;i++)physics.step(desiredPose,1/240);}currentPose=physics.read();previousContact=null;drawAll();}
async function prepareRun({preserveTime=false}={}){
 const savedTime=preserveTime?simTime:0,savedAttack=preserveTime?attackTime:-1,resume=preserveTime&&playing;
 const rev=++runRevision,editSeek=++seekRevision;seeking=false;setPlaying(false);const pausedRevision=playRevision;
 loadingRun=true;$('play').disabled=true;$('step').disabled=true;$('strike').disabled=true;$('runInfo').textContent='Loading '+(settings.mode==='walk'?'walk':'run')+'…';let resumeAfter=false;
 try {const request={gait:settings.mode==='walk'?'walk':'run',duration:5,phase:settings.runPhase,drawn:settings.attack==='pike'||settings.attack.startsWith('slash')},key=JSON.stringify(request);let decoded=runCache.get(key);if(!decoded){decoded=F.decodeNN(await post('/run',request));runCache.set(key,decoded);while(runCache.size>4)runCache.delete(runCache.keys().next().value);}if(rev!==runRevision)return;
  const restoreTime=preserveTime?(seekRevision===editSeek?savedTime:simTime):0;
  resumeAfter=resume&&playRevision===pausedRevision&&seekRevision===editSeek;
  run=decoded;flight=F.sequence(run,jumps,settings,parents,idle);platformEditor?.refresh();simTime=restoreTime;attackTime=savedAttack;
  const air=settings.airFlip?Math.max(0,simTime-(flight.airStartAt?.(simTime)??flight.airStart)):0;flip=settings.flipAngle+settings.flipSpeed*air;twist=settings.twistAngle+settings.twistSpeed*air;hit=false;bestMiss=Infinity;flightFrame=null;
  const first=flight.segments[0],support=first?.support.terminal;
  $('legMatchInfo').textContent=first&&settings.matchLeg&&first.matchDistance!==null?'Leg '+first.matchTime.toFixed(3)+' s · '+first.legRate.toFixed(3)+'×':'Normal leg timing';
  $('runInfo').textContent=(settings.mode==='walk'?'Walk':'Run')+' NN · '+flight.speed.toFixed(1)+' m/s · '+flight.events.length+' jumps';
  $('runInfo').title='Run duration places the ledge. Each timeline marker starts support; contact starts loading, then the push. Drag a marker or edit its time.';
  jumpTrack?.sync();
  if(preserveTime&&settings.motion!=='kinematic'&&restoreTime>0){simTime=0;resetPhysics();const job=seek(restoreTime),seekPlayRevision=playRevision;await job;resumeAfter&&=playRevision===seekPlayRevision;}else resetPhysics();
  if(rev===runRevision)save();
 }finally{if(rev===runRevision){loadingRun=false;$('play').disabled=false;$('step').disabled=false;$('strike').disabled=false;if(resumeAfter&&!document.hidden)setPlaying(true);}}
}
function total(){return clip?clip.duration+.6:1;}
function strike(){if(!clip||loadingRun)return;attackTime=0;hit=false;bestMiss=Infinity;previousContact=null;setPlaying(true);}
function cancelAttack(){attackTime=-1;previousContact=null;hit=false;bestMiss=Infinity;if(!playing)resetPhysics();}
function tick(endTime=Infinity){for(let i=0;i<4&&simTime<endTime-1e-8;i++){
 if(settings.mode==='space'){flip+=settings.flipSpeed/240;twist+=settings.twistSpeed/240;}simTime+=1/240;
 if(settings.mode!=='space'&&flight&&settings.airFlip){const air=Math.max(0,simTime-flight.airStartAt(simTime));flip=settings.flipAngle+settings.flipSpeed*air;twist=settings.twistAngle+settings.twistSpeed*air;}
 if(attackTime>=0){attackTime+=settings.attackRate/240;if(attackTime>total()){if(settings.loop){attackTime=0;hit=false;bestMiss=Infinity;previousContact=null;}else attackTime=-1;}}
 desiredPose=targetPose();physics.step(desiredPose,1/240);currentPose=physics.read();
 if(attackTime>=.15&&attackTime<=.15+clip.duration){const point=C.contactPoint(currentPose,settings.attack,names,swordMesh);let d=norm(sub(point,settings.target));if(previousContact)d=Math.min(d,C.segmentDistance(settings.target,previousContact,point));if(settings.attack.startsWith('slash')||settings.attack==='pike'){const hand=currentPose.points[nameToIndex.get('hand_r')];d=Math.min(d,C.segmentDistance(settings.target,hand,point));}bestMiss=Math.min(bestMiss,Math.max(0,d-settings.radius));hit||=d<=settings.radius+.025;previousContact=point;}else previousContact=null;
 }}
async function seek(time){const rev=++seekRevision;setPlaying(false);seeking=true;try{hit=false;bestMiss=Infinity;if(settings.mode==='space'){attackTime=time;resetPhysics();return;}if(settings.motion==='kinematic'){placeKinematic(time);return;}simTime=0;attackTime=-1;flip=settings.flipAngle;twist=settings.twistAngle;resetPhysics();const ticks=Math.round(time*60);for(let n=0;n<ticks;){const start=performance.now();do{tick();n++;}while(n<ticks&&performance.now()-start<6);if(n<ticks){await new Promise(r=>setTimeout(r,0));if(rev!==seekRevision)return;}}drawAll();}finally{if(rev===seekRevision)seeking=false;}}
function animate(stamp){raf=null;if(!playing||document.hidden)return;if(lastStamp)accumulator=Math.min(.05,accumulator+Math.min((stamp-lastStamp)/1000,.05)*settings.playbackSpeed);lastStamp=stamp;let count=0;while(accumulator>=1/60&&count++<3){if(!playbackStep())return;accumulator-=1/60;}drawAll();if(playing)raf=requestAnimationFrame(animate);}
function setPlaying(value){++playRevision;if(value&&physics&&!loadingRun&&!seeking&&trimActive()&&(simTime<settings.trimIn-1e-8||simTime>=settings.trimOut-1e-8)){if(settings.motion==='kinematic')placeKinematic(settings.trimIn);else {restartTrim();return;}}playing=!!value&&!!physics&&!loadingRun&&!seeking;if(raf!==null)cancelAnimationFrame(raf);raf=null;lastStamp=0;accumulator=0;$('play').innerHTML=playing?'Pause <kbd>Space</kbd>':'Play <kbd>Space</kbd>';if(playing)raf=requestAnimationFrame(animate);else if(physics)drawAll();}
function resetCamera(){Object.assign(cameraState,cameraDefault);drawAll();save();}
class BodyflipRenderer extends WebGLMotionRenderer{
 bindCamera(){
  const c=this.canvas;c.addEventListener('contextmenu',e=>e.preventDefault());
  c.addEventListener('pointerdown',e=>{e.preventDefault();c.setPointerCapture(e.pointerId);this.drag={x:e.clientX,y:e.clientY,startX:e.clientX,startY:e.clientY,button:e.button,select:e.button===0&&!e.altKey&&settings.mode!=='space',moved:false};if(this.drag.select)this.drag.selection=platformEditor?.previewSelection(e.clientX,e.clientY);});
  c.addEventListener('pointermove',e=>{if(!this.drag)return;if(this.drag.select&&!this.drag.moved){if(Math.hypot(e.clientX-this.drag.startX,e.clientY-this.drag.startY)<4)return;this.drag.moved=true;if(this.drag.selection){platformEditor?.finishSelection(this.drag.selection,true,true);this.drag.selection=null;}}const dx=e.clientX-this.drag.x,dy=e.clientY-this.drag.y;this.drag.x=e.clientX;this.drag.y=e.clientY;
   if(this.drag.button===2&&this.viewCamera){const v=this.viewCamera,depth=Math.max(.3,dot(sub(settings.target,v.eye),v.forward)),scale=depth/v.focalCss;settings.target=add(settings.target,e.shiftKey?mul(v.forward,-dy*scale):add(mul(v.right,dx*scale),mul(v.up,-dy*scale)));syncTarget();}
   else if(this.drag.button===1){cameraState.panX+=dx;cameraState.panY+=dy;}else{if(e.altKey&&platformEditor?.selected){platformEditor.selected=null;platformEditor.render();}cameraState.yaw-=dx*.008;cameraState.pitch=clamp(cameraState.pitch-dy*.006,-1.15,1.75);}drawAll();});
  // Show the gizmo on press; only a completed click pauses playback. Orbit cancels the preview.
  const end=e=>{const d=this.drag;if(!d)return;this.drag=null;const orbit=d.moved||Math.hypot(e.clientX-d.startX,e.clientY-d.startY)>=4;if(d.selection)platformEditor?.finishSelection(d.selection,e.type!=='pointerup'||orbit||settings.mode==='space',orbit);save();};c.addEventListener('pointerup',end);c.addEventListener('pointercancel',end);c.addEventListener('lostpointercapture',end);
  c.addEventListener('wheel',e=>{e.preventDefault();const zoom=Math.min(3,cameraState.zoom*Math.exp(-e.deltaY*.001));if(zoom>0&&Number.isFinite(3.55/zoom))cameraState.zoom=zoom;drawAll();save();},{passive:false});c.addEventListener('dblclick',resetCamera);
 }
 draw(data,root){super.draw(data,root);if(!data)return;const gl=this.gl,mesh=this.extras||(this.extras=new LabVertexStream(40000)),lines=this.extraLines||(this.extraLines=new LabVertexStream(10000));mesh.length=0;lines.length=0;
  const translucent=this.platformSideFaces||(this.platformSideFaces=[]);translucent.length=0;const sideOpacity=1-settings.platformTranslucency;
  const target=settings.target,color=hit?[.3,1,.72]:[1,.38,.66];this.capsule(mesh,target,target,settings.radius,color,22,8);
  const ring=(center,a,b,r,col)=>{let prev=null;for(let n=0;n<=72;n++){const t=n*Math.PI/36,p=add(center,add(mul(a,Math.cos(t)*r),mul(b,Math.sin(t)*r)));if(prev)this.line(lines,prev,p,col);prev=p;}};
  ring(target,[1,0,0],[0,1,0],settings.radius*1.18,color);ring(target,[0,0,1],[0,1,0],settings.radius*1.18,color);
  const center=data.points[1];this.capsule(mesh,center,center,.018,[.8,.7,1],10,3);const axis=C.flipAxis(settings.axis);this.line(lines,add(center,mul(axis,-.3)),add(center,mul(axis,.3)),[.7,.55,1]);
  if(settings.mode!=='space'&&flight){
   for(const surface of platformEditor?.surfaces()||flight.surfaces){
    const [a,b,c,d]=surface.bounds,point=(x,z)=>surface.world([x,.008,z]);
    this.platformBox(mesh,translucent,surface,surface.id===platformEditor?.selected?[.38,.34,.23]:surface.id==='floor'?[.11,.19,.30]:surface.id==='left'?[.17,.24,.29]:[.22,.20,.30],sideOpacity);
    if(dot(surface.normal,sub(this.viewCamera.eye,surface.origin))<=0)continue;
    for(let x=Math.ceil(a*2)/2;x<b;x+=Math.max(.5,(b-a)/80))this.line(lines,point(x,c),point(x,d),[.24,.33,.42]);
    for(let z=Math.ceil(c*2)/2;z<d;z+=Math.max(.5,(d-c)/80))this.line(lines,point(a,z),point(b,z),[.24,.33,.42]);
    const corners=[point(a,c),point(b,c),point(b,d),point(a,d)];for(let i=0;i<4;i++)this.line(lines,corners[i],corners[(i+1)%4],[.85,.59,.32]);
   }
   if(flightFrame?.supportTarget&&flightFrame.supportState!=='FREE'){
    const surface=flightFrame.surface||flight.surfaces[0],p=add(flightFrame.supportTarget,mul(surface.normal,.008));ring(p,surface.u,surface.v,.025,[.3,1,.72]);this.line(lines,data.points[nameToIndex.get('foot_'+(flightFrame.supportFoot||flight.supportFoot).toLowerCase())],p,[.3,1,.72]);
   }
   const ideals=flight.idealDebug(simTime);
   if(ideals){const surface=ideals.surface;
    for(const ideal of ideals.targets){const p=add(ideal.point,mul(surface.normal,.012));ring(p,surface.u,surface.v,.075,ideal.selected?[.3,1,.72]:[1,.22,.20]);}
   }
   // Sparse world-height ticks provide descent cues without a floor below the ledge.
   const cy=physics.com()[1],cz=physics.com()[2];for(let y=Math.floor(cy/2)*2-8;y<cy+8;y+=2){this.line(lines,[-2.6,y,cz-1],[-2.3,y,cz-1],[.24,.29,.4]);this.line(lines,[2.3,y,cz-1],[2.6,y,cz-1],[.24,.29,.4]);}
  }
  const contact=C.contactPoint(data,settings.attack,names,swordMesh);if(attackTime>=0){this.capsule(mesh,contact,contact,.022,[1,.9,.45],10,3);this.line(lines,contact,target,[.43,.38,.51]);}
  if(settings.ghost&&desiredPose){const ghost={...desiredPose,upperOnly:false,skeleton:true,hideSword:true,tint:[.35,.68,.87]};this.addBody(mesh,ghost);}
  this.bindAndDraw(this.meshBuffer,mesh,gl.TRIANGLES);this.bindAndDraw(this.lineBuffer,lines,gl.LINES);
  this.drawPlatformSides(translucent,sideOpacity);
  if(settings.showCone&&settings.mode!=='space'&&flight){const cone=flight.coneDebug(simTime,data);if(cone){
   const overlay=this.coneLines||(this.coneLines=new LabVertexStream(1000));overlay.length=0;
   const n=cone.normal,a=normalize(cross(n,Math.abs(n[0])<.9?[1,0,0]:[0,0,1])),b=cross(n,a),col=cone.valid?[.2,1,.55]:[1,.3,.25];
   let prev=null;
   for(let i=0;i<=32;i++){const theta=i*Math.PI/16,p=add(cone.center,add(mul(a,Math.cos(theta)*cone.radius),mul(b,Math.sin(theta)*cone.radius)));if(prev)this.line(overlay,prev,p,col);if(i%4===0)this.line(overlay,cone.apex,p,col);prev=p;}
   const mark=(p,r,c)=>{for(const axis of [a,b])this.line(overlay,add(p,mul(axis,-r)),add(p,mul(axis,r)),c);};
   this.line(overlay,cone.apex,cone.center,col);mark(cone.apex,.018,col);mark(cone.wanted,.035,[1,.3,.75]);
   if(cone.contact){mark(cone.contact,.035,col);this.line(overlay,cone.wanted,cone.contact,[.65,.35,.6]);}
   gl.disable(gl.DEPTH_TEST);this.bindAndDraw(this.lineBuffer,overlay,gl.LINES);gl.enable(gl.DEPTH_TEST);
  }}
  if(settings.showJump&&settings.mode!=='space'&&flight){const push=flight.pushDebug(simTime);if(push){
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
  if(settings.animLeg&&settings.mode!=='space'&&flight){const ghost=flight.animationLeg(simTime,data);if(ghost){
   const overlay=this.animLegMesh||(this.animLegMesh=new LabVertexStream(5000));overlay.length=0;
   const col=[.75,.55,1],points=ghost.points;
   for(let i=1;i<points.length;i++)this.capsule(overlay,points[i-1],points[i],.012,col,8,3);
   for(const p of points)this.capsule(overlay,p,p,.022,col,8,3);
   // X-ray overlay stays readable when the target overlaps the displayed leg.
   gl.disable(gl.DEPTH_TEST);this.bindAndDraw(this.meshBuffer,overlay,gl.TRIANGLES);gl.enable(gl.DEPTH_TEST);
  }}
 }
}
function syncPlaybackReadout(time){$('timeRead').textContent=time.toFixed(2)+' s';$('frameRead').textContent='F '+Math.round(time*60);$('scrub').value=time;}
function supportHint(){
 const active=flight?.activeAt(simTime),reason=flightFrame?.failureReason;
 if(settings.mode==='space'||!active||simTime<active.supportStart)return reason||'';
 const scores=active.supportScores.map(s=>s.foot+' '+(s.distance*100).toFixed(1)+' cm'+(s.eligible?'':' (unavailable)')).join(' / ');
 return (reason?reason+' · ':'')+'Selected '+active.supportFoot+' · At selection, after cone: '+scores+'. Ideal rings: green selected, red other; small green ring: contact.';
}
function drawAll(){if(!renderer||!currentPose)return;const data={...currentPose,bicolor:settings.bicolor,skeleton:settings.skeleton,upperOnly:false,hideSword:!(settings.attack==='pike'||settings.attack.startsWith('slash')),tint:[.91,.49,.25],voidScene:settings.mode!=='space'};renderer.draw(data,settings.mode!=='space'?physics.com():pivot);platformEditor?.render();syncPlaybackReadout(settings.mode!=='space'?simTime:Math.max(0,attackTime));const now=performance.now();if(playing&&now-lastHUD<100)return;lastHUD=now;$('fallRead').textContent=Math.max(0,-physics.com(true)[1]).toFixed(1);$('flipRead').textContent=wrap(flip).toFixed(0)+'°';$('twistRead').textContent=wrap(twist).toFixed(0)+'°';$('missRead').textContent=Number.isFinite(bestMiss)?(bestMiss*100).toFixed(1)+' cm':'—';$('hitRead').textContent=hit?'HIT':attackTime>=0?'…':'—';$('hitRead').style.color=hit?'#68e1ad':'';$('phase').textContent=(playing?'':'PAUSED · ')+(settings.mode!=='space'?(flightFrame?.phase||'RUN'):(attackTime>=0?'ATTACK':'FLIPPING'));$('phase').title=supportHint();$('scrub').max=settings.mode!=='space'?timelineMax():total();syncTrim();$('scrub').setAttribute('aria-label',settings.mode!=='space'?'Sequence timeline':'Attack timeline');}
function syncTarget(){['X','Y','Z'].forEach((k,i)=>$('target'+k).value=settings.target[i].toFixed(2));}
function syncPlaybackSpeed(){$('playbackSpeed').value=settings.playbackSpeed;$('playbackSpeedRead').value=settings.playbackSpeed.toFixed(1)+'×';$('playbackSpeed').setAttribute('aria-valuetext',settings.playbackSpeed.toFixed(1)+' times');}
function syncControls(){$('platformTranslucency').value=Math.round(settings.platformTranslucency*100);$('platformTools').hidden=settings.mode==='space';jumpTrack?.sync();$('ramps').checked=settings.ramps;syncTrim();syncPlaybackSpeed();for(const k of ['loadMs','rebound','jumpSkew','supportCone','supportReach','supportTrigger','supportAlpha','supportSpeed','jumpEarly','standRatio','plantPitch','toeOffPitch','footRollSpeed'])$(k).value=['supportTrigger','jumpSkew','rebound'].includes(k)?+(settings[k]*100).toFixed(4):settings[k]; $('mode').value=settings.mode;$('gaitLabel').textContent=settings.mode==='walk'?'Walk':'Run';$('runSeconds').setAttribute('aria-label',settings.mode==='walk'?'Walk duration':'Run duration');$('motion').value=settings.motion;$('engine').textContent=settings.motion==='kinematic'?'Kinematic · NN target':'Jolt · 25 bodies';document.querySelector('.footer-note').textContent=settings.motion==='kinematic'?'Kinematic · COM follow':settings.mode!=='space'?'Sim · Local 0 · COM follow':'Zero gravity · 240 Hz · Hinge knees';$('runControls').hidden=$('minorOptions').hidden=settings.mode==='space';$('airFlip').checked=settings.airFlip;$('matchLeg').checked=settings.matchLeg;$('jumpFoot').value=settings.jumpFoot;for(const k of ['runSeconds','runPhase','jumpBlend','legBlend','fallCap']){$(k).value=settings[k];$(k+'Read').textContent=k==='runPhase'?Math.round(settings[k]*100)+'%':settings[k].toFixed(k==='fallCap'?0:2);}for(const k of ['flipSpeed','flipAngle','twistAngle','twistSpeed','attackRate','aimWeight','radius']){if($(k))$(k).value=settings[k];if($(k+'Range'))$(k+'Range').value=settings[k];}for(const k of ['aim','loop','ghost','animLeg','showCone','showJump','bicolor','skeleton'])$(k).checked=settings[k];$('aimAmount').value=Math.round(settings.aimWeight*100)+'%';$('axisLabel').textContent=C.dirs[settings.axis];for(const b of document.querySelectorAll('#axisGrid [data-axis]')){b.classList.toggle('active',+b.dataset.axis===settings.axis);b.setAttribute('aria-pressed',String(+b.dataset.axis===settings.axis));}syncTarget();}
async function loadAttack(name,id){const rev=++loadRevision;const wasPlaying=playing,wasDrawn=settings.attack==='pike'||settings.attack.startsWith('slash');setPlaying(false);$('strike').disabled=true;const family=manifest.clips.find(c=>c.name===name)||manifest.clips[0],meta=family.variants.find(v=>v.id===+id)||family.variants[0];let decoded=cache.get(meta.file);if(!decoded){const r=await fetch(meta.file);if(!r.ok)throw Error('Attack unavailable');decoded=C.decode(meta,await r.arrayBuffer(),names,parents);cache.set(meta.file,decoded);}if(rev!==loadRevision)return;settings.attack=family.name;settings.variant=meta.id;clip=decoded;$('attack').value=family.name;$('variant').replaceChildren(...family.variants.map(v=>new Option(String(v.id).padStart(2,'0'),v.id)));$('variant').value=meta.id;$('scrub').max=total();attackTime=-1;hit=false;bestMiss=Infinity;if(flight&&settings.mode!=='space'&&wasDrawn!==(settings.attack==='pike'||settings.attack.startsWith('slash')))await prepareRun({preserveTime:true});else resetPhysics();$('strike').disabled=false;if(wasPlaying)setPlaying(true);save();}
let jumpTrack=null;
function buildUI(){
 syncScenes();$('scene').onchange=()=>changeScene('select',$('scene').value).catch(fail);$('copyScene').onclick=()=>changeScene('copy').catch(fail);$('renameScene').onclick=()=>changeScene('rename').catch(fail);
 platformEditor=new BodyflipPlatforms.Editor({get:()=>({settings,edge:flight?.edge??5,surfaces:flight?.surfaces||[],camera:renderer?.viewCamera,rect:$('viewport').getBoundingClientRect(),center:physics?.com()||pivot}),pause:()=>setPlaying(false),draw:drawAll,change:list=>{settings=C.sanitize({...settings,platforms:list});},commit:()=>prepareRun({preserveTime:true}).catch(fail)});
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
 $('mode').onchange=()=>{settings.mode=$('mode').value;simTime=0;setPlaying(false);syncControls();if(settings.mode!=='space')prepareRun().catch(fail);else resetPhysics();save();};
 for(const k of ['runSeconds','runPhase','jumpBlend','legBlend','fallCap']){$(k).oninput=()=>{settings=C.sanitize({...settings,[k]:+$(k).value});setPlaying(false);syncControls();};$(k).onchange=()=>prepareRun({preserveTime:true}).catch(fail);}
 $('matchLeg').onchange=()=>{settings.matchLeg=$('matchLeg').checked;prepareRun({preserveTime:true}).catch(fail);};
 for(const k of ['loadMs','rebound','jumpSkew','supportCone','supportReach','supportTrigger','supportAlpha','supportSpeed','jumpEarly','standRatio','plantPitch','toeOffPitch','footRollSpeed'])$(k).onchange=()=>{settings=C.sanitize({...settings,[k]:+$(k).value/(['supportTrigger','jumpSkew','rebound'].includes(k)?100:1)});syncControls();prepareRun({preserveTime:true}).catch(fail);};
 $('jumpFoot').onchange=()=>{settings.jumpFoot=$('jumpFoot').value;prepareRun({preserveTime:true}).catch(fail);};
 $('airFlip').onchange=()=>{settings.airFlip=$('airFlip').checked;flip=twist=0;save();drawAll();};

 for(const k of ['flipSpeed','flipAngle','twistAngle','twistSpeed']){const field=$(k),range=$(k+'Range');field.parentElement.classList.add('compact');field.parentElement.insertBefore(range,field);}
 const slots=[[3,1],[4,1],[5,2],[5,3],[5,4],[4,5],[3,5],[2,5],[1,4],[1,3],[1,2],[2,1]];
 C.dirs.forEach((name,i)=>{const b=document.createElement('button');b.textContent=name;b.dataset.axis=i;b.style.gridColumn=slots[i][0];b.style.gridRow=slots[i][1];b.title=`${name} · ${i*30}° axis heading`;b.onclick=()=>{settings.axis=i;flip=0;settings.flipAngle=0;syncControls();resetPhysics();save();};$('axisGrid').append(b);});
 const labels={headbutt:'Headbutt',hookL:'Hook L',hookR:'Hook R',jabL:'Jab L',jabR:'Jab R',KickL:'Kick L',KickR:'Kick R',overL:'Over L',overR:'Over R',pike:'Pike',slashL:'Slash L',slashLD:'Slash LD',slashLU:'Slash LU',slashR:'Slash R',slashRD:'Slash RD',slashRU:'Slash RU'};
 $('attack').replaceChildren(...manifest.clips.map(c=>new Option(labels[c.name]||c.name,c.name)));$('attack').onchange=()=>loadAttack($('attack').value,settings.variant).catch(fail);$('variant').onchange=()=>loadAttack(settings.attack,+$('variant').value).catch(fail);
 for(const k of ['flipSpeed','flipAngle','twistAngle','twistSpeed','attackRate','aimWeight','radius'])for(const id of [k,k+'Range'])if($(id))$(id).oninput=()=>{const v=Number($(id).value);if(!Number.isFinite(v))return;settings=C.sanitize({...settings,[k]:v});if(k==='flipAngle')flip=settings[k];if(k==='twistAngle')twist=settings[k];if(id!==k)$(k).value=settings[k];if($(k+'Range')&&id!==k+'Range')$(k+'Range').value=settings[k];$('aimAmount').value=Math.round(settings.aimWeight*100)+'%';if(k==='flipAngle'||k==='twistAngle')resetPhysics();else drawAll();save();};
 for(const k of ['aim','loop','ghost','animLeg','showCone','showJump','bicolor','skeleton'])$(k).onchange=()=>{settings[k]=$(k).checked;drawAll();save();};
 ['X','Y','Z'].forEach((k,i)=>$('target'+k).oninput=()=>{if(Number.isFinite(+$('target'+k).value)){settings.target[i]=clamp(+$('target'+k).value,-1000000,1000000);drawAll();save();}});
 $('zeroTwist').onclick=()=>{settings.twistAngle=twist=0;settings.twistSpeed=0;syncControls();resetPhysics();save();};$('resetTarget').onclick=()=>{settings.target=settings.mode!=='space'&&currentPose?add(currentPose.points[1],[.4,.15,.8]):[...C.defaults.target];syncTarget();drawAll();save();};
 $('play').onclick=()=>setPlaying(!playing);$('strike').onclick=strike;$('stopAttack').onclick=cancelAttack;$('step').onclick=()=>{setPlaying(false);playbackStep();drawAll();};$('reset').onclick=()=>{setPlaying(false);flip=settings.flipAngle=0;twist=settings.twistAngle=0;simTime=0;attackTime=-1;hit=false;bestMiss=Infinity;syncControls();if(settings.mode!=='space')prepareRun().catch(fail);else resetPhysics();save();};
 $('scrub').oninput=()=>{const time=+$('scrub').value;previewSeek(time);syncPlaybackReadout(time);};$('scrub').onchange=()=>finishPreview(+$('scrub').value);
 $('cameraReset').onclick=resetCamera;$('cameraFront').onclick=()=>{Object.assign(cameraState,cameraDefault,{yaw:0,pitch:0});drawAll();save();};$('cameraSide').onclick=()=>{Object.assign(cameraState,cameraDefault,{yaw:Math.PI/2,pitch:0});drawAll();save();};$('cameraTop').onclick=()=>{Object.assign(cameraState,cameraDefault,{yaw:0,pitch:-5});drawAll();save();};
 $('save').onclick=()=>persist(stored()).then(()=>notice('Saved')).catch(fail);$('refresh').onclick=refreshLab;$('snapshot').onclick=async()=>{setPlaying(false);try{const r=await post('/snapshot',{...stored(),pose:currentPose,target:settings.target,attackTime,diagnostics:physics.diagnostics(),image:$('viewport').toDataURL('image/png')});notice('Snapshot '+r.name);}catch(e){fail(e);}};
 const writing=el=>el?.isContentEditable||(!el?.readOnly&&!el?.disabled&&(el?.tagName==='TEXTAREA'||(el?.tagName==='INPUT'&&!['range','checkbox','radio','button','submit','reset','file','image','color','hidden'].includes(el.type))));
 const arrows=(e,down=false)=>{if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.code)||writing(e.target))return false;e.preventDefault();e.stopImmediatePropagation();if(down&&(e.code==='ArrowLeft'||e.code==='ArrowRight'))stepFrame(e.code==='ArrowLeft'?-1:1);return true;};
 const space=e=>{if(e.code!=='Space'||e.altKey||e.ctrlKey||e.metaKey||e.target.isContentEditable||e.target.tagName==='TEXTAREA'||(e.target.tagName==='INPUT'&&['text','search','password','email','url'].includes(e.target.type)))return false;e.preventDefault();e.stopImmediatePropagation();return true;};
 window.addEventListener('keydown',e=>{if(settings.mode!=='space'&&BodyflipPlatforms.undoShortcut(e)){e.preventDefault();e.stopImmediatePropagation();if(!e.repeat)platformEditor?.undo();return;}if(settings.mode!=='space'&&!writing(e.target)&&e.target.tagName!=='SELECT'&&!e.ctrlKey&&!e.altKey&&!e.metaKey&&platformEditor?.key(e)){e.preventDefault();e.stopImmediatePropagation();return;}if(arrows(e,true))return;if(space(e)){if(!e.repeat)setPlaying(!playing);return;}if(e.target.classList?.contains('trim-bracket'))return;if(e.repeat||/INPUT|SELECT|TEXTAREA/.test(e.target.tagName))return;if(e.code==='KeyA'){e.preventDefault();strike();}if(e.code==='KeyR')$('reset').click();},true);
 window.addEventListener('keyup',e=>{if(!arrows(e))space(e);},true);
 document.addEventListener('visibilitychange',()=>{if(document.hidden){if(previewRAF!==null)cancelAnimationFrame(previewRAF);previewRAF=null;setPlaying(false);}});
}
function decodeB64(raw,Type){const b=Uint8Array.from(atob(raw),c=>c.charCodeAt(0));return new Type(b.buffer);}
async function init(){const [m,s,sw,jumpData,standingData]=await Promise.all([fetch('data/manifest.json').then(r=>r.json()),fetch('/state').then(r=>r.json()),fetch('data/sword.json').then(r=>r.json()),fetch('data/jumps.json').then(r=>r.json()),fetch('data/jumps-standing.json').then(r=>r.json())]);sceneLibrary=BodyflipScenes.open(s);jumps=[...jumpData.clips,...standingData.clips].map(F.decodeJump);manifest=m;names=m.names;parents=m.parents;nameToIndex=new Map(names.map((n,i)=>[n,i]));settings=C.sanitize(BodyflipPlatforms.restoreDefaultsOnce(s.settings));flip=settings.flipAngle;twist=settings.twistAngle;if(s.camera)for(const k of Object.keys(cameraDefault))if(Number.isFinite(s.camera[k]))cameraState[k]=s.camera[k];
 swordMesh={...sw,vertices:decodeB64(sw.vertices_b64,Float32Array),triangles:decodeB64(sw.triangles_b64,Int32Array),bladeMask:decodeB64(sw.blade_mask_b64,Uint8Array)};idle=C.poseFromShared(m);const f=R.rotate(idle.q[1],[0,-1,0]);basePelvis=R.qm(R.fromTo(normalize([f[0],0,f[2]]),[0,0,1]),idle.q[1]);
 buildUI();syncControls();renderer=new BodyflipRenderer($('viewport'),{pixelRatio:Math.min(devicePixelRatio,1.5)});
 const {createPhysics}=await import('./physics.mjs');physics=await createPhysics(manifest,C.centerPose(idle,rotation(),pivot));$('engine').textContent='Jolt · 25 bodies';await loadAttack(settings.attack,settings.variant);if(settings.mode!=='space')await prepareRun();await restorePlayback(s.playback);syncControls();sceneReady=true;syncScenes();save();
 window.BodyflipLab={get state(){const active=flight?.activeAt(simTime);return {settings:{...settings},flip,twist,attackTime,simTime,frame:Math.round(simTime*60),playing,hit,bestMiss,errors:[...errors],pose:currentPose,diagnostics:physics.diagnostics(),flight:flight?{edge:flight.edge,phase:flightFrame?.phase,root:flightFrame?.root,events:flight.events,surfaces:flight.surfaces.map(s=>({id:s.id,normal:s.normal,bounds:s.bounds})),...(active?{airStart:active.airStart,apex:active.apex,sourceStart:active.sourceStart,jumpStyle:active.jumpStyle,takeoffSpeed:active.takeoffSpeed,standingThreshold:active.standingThreshold,matchLeg:settings.matchLeg,legMatchTime:active.matchTime,legRate:active.legRate,legMatchDistance:active.matchDistance,legArrival:active.jumpStart+active.loopStart,jumpStart:active.jumpStart,contactTime:active.contactTime,loadDuration:active.bounce?.loadDuration,compression:active.bounce?.compression,returnedEnergy:active.bounce?.returnedEnergy,supportStart:active.supportStart,abortTime:active.abortTime,failureReason:flightFrame?.failureReason||null,supportDistance:flightFrame?.distance,supportHistory:active.support.frames.map(f=>({time:active.supportStart+f.t,distance:f.distance,reachable:f.reachable,approachSpeedCmS:f.approachSpeed*100,reachWait:f.reachWait,hipDistance:f.hipDistance})),supportIdealRoot:active.support.idealLocal,release:active.release,supportState:flightFrame?.supportState,supportTarget:flightFrame?.supportTarget,supportCone:settings.showCone?flight.coneDebug(simTime,currentPose):null,supportFoot:active.supportFoot,supportScores:active.supportScores,surfaceChoices:active.surfaceChoices,supportIdeals:flight.idealDebug(simTime),supportLead:active.support.terminal.appliedShift,supportLimited:active.support.terminal.limited}:{})}:null,com:physics.com(),velocity:physics.com(true),cameraCenter:renderer.viewCamera?.target,loadingRun};},prepareRun,seek,playbackStep,step(count=1){setPlaying(false);for(let i=0;i<count;i++)tick();drawAll();return this.state;},strike,loadAttack,setPlaying,reset:()=> $('reset').click(),targetPose,project(p){const m=renderer.viewProjection,r=$('viewport').getBoundingClientRect(),w=m[3]*p[0]+m[7]*p[1]+m[11]*p[2]+m[15];return {x:r.left+(1+(m[0]*p[0]+m[4]*p[1]+m[8]*p[2]+m[12])/w)*r.width/2,y:r.top+(1-(m[1]*p[0]+m[5]*p[1]+m[9]*p[2]+m[13])/w)*r.height/2};}};
 $('play').disabled=false;$('step').disabled=false;$('engine').title='25 rigid bodies · 24 joints · knee/elbow hinges · local lab profile';
}
init().catch(fail);
