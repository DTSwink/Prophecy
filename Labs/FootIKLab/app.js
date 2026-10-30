'use strict';
const $=id=>document.getElementById(id),R=Recovery,K=FootIK,S=BodyflipSupport,{add,sub,mul,dot,cross,length:norm,unit:normalize}=R;
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v)),posAt=(data,j)=>data.points[j],axisAt=(data,j,a)=>data.axes[j][a];
let names=[],parents=[],nameToIndex=new Map(),swordMesh=null,renderer=null,run=null,model=null,frame=null,settings=K.sanitize(),time=0,playing=false,raf=null,lastStamp=0,accumulator=0,revision=0,persistence=null,reloading=false,busy=false,backendVersion=0;
let sourcesUnchanged=null,platformEditor=null,prepareTask=null,preparePending=false,resumeAfterPrepare=false,trimTimer=null;
const refreshFiles=[...new Set(['index.html','data/rig.json','server.py','nn_service.py','nn_worker.py','directional_nn.py','surface_nn.py','surface_driver.cjs','directional-sources.json','run_bank.py',...Array.from(document.scripts,s=>s.getAttribute('src')).filter(Boolean),...Array.from(document.querySelectorAll('link[href]'),s=>s.getAttribute('href'))])];
const cameraDefault={yaw:1.05,pitch:.08,zoom:.8,panX:0,panY:0},cameraState={...cameraDefault},cache=new Map(),errors=[];
const loadTiming={requests:[],stages:[]};
const surfacePreparations=new Map(),viewOnly=new Set(['ghost','targets','ramp','bicolor','bones','loop','showRoot','translucency','ghostTranslucency','trimIn','trimOut','speed']);
const isSurface=s=>s.terrain==='incline'||Array.isArray(s.platformLayouts[s.terrain]);
const physicsKey=s=>JSON.stringify(Object.fromEntries(Object.entries(s).filter(([k])=>!viewOnly.has(k))));
function availableEnd(){return isSurface(settings)&&model?model.generatedThrough??model.duration:5;}
async function post(path,data){const started=performance.now();const result=await FootHTTP.json(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)},65000);loadTiming.requests.push({kind:data.kind||'continuation',ms:performance.now()-started,cache:result.cache,generatedThrough:result.generatedThrough});return result;}
function snapshot(){return {schema:'foot-ik-lab-v1',settings,camera:cameraState,playback:{time,playing}};}
function persistenceBaseline(saved){const value=snapshot();value.settings={...settings};for(const key of ['slideHandShift','slideHandShiftSpeed','slideHeadSpeed','slideCloser','slideLegBlend','slidePelvisBlend'])if(saved.settings?.[key]==null)delete value.settings[key];return value;}
function save(){persistence?.save(fail);}
function fail(e){errors.push(e.message||String(e));$('error').hidden=false;$('error').textContent=errors.at(-1);setPlaying(false);}
window.addEventListener('error',e=>fail(e.error||e.message));window.addEventListener('unhandledrejection',e=>fail(e.reason));
function seek(t){time=clamp(Math.round(t*60)/60,0,availableEnd());drawAll();}
function setPlaying(v){playing=!!v&&!!model&&!busy;if(raf!==null)cancelAnimationFrame(raf);raf=null;lastStamp=0;accumulator=0;$('play').innerHTML=(playing?'Pause':'Play')+' <kbd>Space</kbd>';if(playing&&!document.hidden)raf=requestAnimationFrame(animate);else drawAll();}
function advance(){if(time>=settings.trimOut-1e-8){if(!settings.loop){setPlaying(false);return;}time=settings.trimIn;}else if(time<settings.trimIn-1e-8)time=settings.trimIn;else time=Math.min(settings.trimOut,(Math.round(time*60)+1)/60);}
function animate(stamp){raf=null;if(!playing||document.hidden)return;if(lastStamp)accumulator+=Math.min(.05,(stamp-lastStamp)/1000)*settings.speed;lastStamp=stamp;let steps=0;while(accumulator>=1/60&&steps++<6){advance();accumulator-=1/60;}drawAll();if(playing)raf=requestAnimationFrame(animate);}
function sync(){for(const k of ['gait','terrain','height','depth','steps','clearance','pelvis','translucency','ghostTranslucency','speed','direction','slopeAngle','approach','upright','rootYawSpeed','rootYawStart','rootYawStop','footYawLimit','stepAccent','minGravityIncline','fullGravity','energyConservation','deleteFloorFrame','pinReleaseSpeed','pelvisCloser','pelvisSpeedMin','pelvisSpeedMax','pelvisCloserMax','slideSpeed','slideBlend','slideFriction','slideRecovery','slideShift','slideShiftSpeed','slideHandShift','slideHandShiftSpeed','slideHeadSpeed','slideCloser','slideLegBlend','slidePelvisBlend'])$(k).value=settings[k]??'';for(const k of ['enabled','ghost','targets','ramp','bicolor','bones','loop','showRoot','inclineGravity','slideEnabled'])$(k).checked=settings[k];$('phaseInput').value=settings.phase;$('phaseRead').textContent=Math.round(settings.phase*100)+'%';$('speedRead').textContent=settings.speed.toFixed(1)+'×';$('ghostTranslucencyRead').textContent=settings.ghostTranslucency+'%';$('uprightRead').textContent=Math.round(settings.upright*100)+'%';const surface=settings.terrain==='incline'||Array.isArray(settings.platformLayouts[settings.terrain]);$('surfaceOptions').hidden=settings.terrain!=='incline';for(const k of ['slopeAngle','approach'])$(k).disabled=Array.isArray(settings.platformLayouts[settings.terrain]);$('gravityOptions').hidden=!surface;$('slideEnabled').disabled=!surface;for(const k of ['pelvisCloser','pelvisSpeedMin','pelvisSpeedMax','pelvisCloserMax','slideSpeed','slideBlend','slideFriction','slideRecovery','slideShift','slideShiftSpeed','slideHandShift','slideHandShiftSpeed','slideHeadSpeed','slideCloser','slideLegBlend','slidePelvisBlend'])$(k).disabled=!surface;for(const k of ['fullGravity','energyConservation'])$(k).disabled=!settings.inclineGravity;$('motionMode').textContent=surface?'Gravity root':'Kinematic';$('motionMode').title=surface?'Simulated root; kinematic NN limbs and foot IK.':'';for(const k of ['height','depth','steps','pelvis','clearance','stepAccent'])$(k).disabled=surface;$('terrainHint').textContent=surface?'Gravity + foot support. Angle in More options.':'Root follows a ramp; feet see the steps.';syncTrim();}
function syncTrim(){for(const key of ['trimIn','trimOut']){const el=$(key);el.style.left=settings[key]/5*100+'%';el.dataset.time='F '+Math.round(settings[key]*60);el.setAttribute('aria-valuenow',settings[key]);el.setAttribute('aria-valuemin',0);el.setAttribute('aria-valuemax',5);el.setAttribute('aria-valuetext','Frame '+Math.round(settings[key]*60));} $('trimSelection').style.left=settings.trimIn/5*100+'%';$('trimSelection').style.width=(settings.trimOut-settings.trimIn)/5*100+'%';}
async function buildMotion(token){
 const requested=K.sanitize(settings),surface=isSurface(requested),end=requested.trimOut;
 loadTiming.requests.length=0;loadTiming.stages=loadTiming.stages.filter(s=>s.name==='renderer');
 $('status').textContent=surface?'Generating to F '+Math.round(end*60)+'…':'Preparing…';
 if(requested.direction!=='forward'&&backendVersion<6)throw Error('Restart this Foot IK server to enable directional NN.');
 if(surface&&backendVersion<7)throw Error('Restart only the Foot IK server to enable generation up to the end bracket. Your scene is saved.');
 const key=[surface?'surface-seed-v2':'run-window-v1',requested.gait,requested.direction,requested.phase,requested.rootYawSpeed,requested.rootYawStart,requested.rootYawStop].join(':');
 let decoded=cache.get(key);
 if(!decoded){decoded=K.decode(await post('/resume',{kind:'direction',policy:'run',gait:requested.gait,duration:surface?.1:5,...(surface?{seedOnly:true,totalDuration:5}:{}),phase:requested.phase,direction:requested.direction,rootYawSpeed:requested.rootYawSpeed,rootYawStart:requested.rootYawStart,rootYawStop:requested.rootYawStop}),parents);cache.set(key,decoded);while(cache.size>4)cache.delete(cache.keys().next().value);}
 if(token!==revision)return;
 const preparing=performance.now();let prepared;
 if(surface){
  const key=physicsKey(requested);let session=surfacePreparations.get(key);
  if(!session){session=FootSurfaceCoupling.createPreparation(decoded,requested,post);surfacePreparations.set(key,session);while(surfacePreparations.size>2)surfacePreparations.delete(surfacePreparations.keys().next().value);}
  // Keep completed prefixes even if a later edit supersedes this request.
  // The queue consumes only the newest desired endpoint/settings next.
  prepared=await session.extend(end);
 }else prepared=await FootHandoff.prepare(decoded,requested,request=>{$('status').textContent='Preparing NN handoff…';return post('/resume',request);},()=>token!==revision);
 loadTiming.stages.push({name:'terrain + handoff',ms:performance.now()-preparing});if(token!==revision||!prepared)return;
 run=decoded;model=prepared;time=Math.min(time,availableEnd());platformEditor?.refresh();$('error').hidden=true;$('status').textContent=run.source+' · '+model.speed.toFixed(1)+' m/s';$('status').title=surface?'Generated through F '+Math.round(availableEnd()*60)+'. Extend the end bracket to continue.':model.handoff?'Terrain exit seeds the real lower/upper NN from current and previous corrected poses (30Hz).':'Contact intent estimated from uncorrected NN sole height and foot speed.';
 sync();const drawing=performance.now();drawAll();loadTiming.stages.push({name:'draw',ms:performance.now()-drawing});console.info('[Foot IK solve] '+JSON.stringify({ms:performance.now()-preparing,through:Math.round(availableEnd()*60),request:loadTiming.requests.at(-1)}));
}
function prepare(){
 ++revision;preparePending=true;resumeAfterPrepare||=playing;
 if(prepareTask)return prepareTask;
 busy=true;setPlaying(false);$('play').disabled=$('step').disabled=$('addPlatform').disabled=true;
 prepareTask=(async()=>{try{while(preparePending){preparePending=false;const token=revision;try{await buildMotion(token);}catch(error){if(token===revision)throw error;}}}
  finally{prepareTask=null;busy=false;$('play').disabled=$('step').disabled=$('addPlatform').disabled=false;const resume=resumeAfterPrepare;resumeAfterPrepare=false;if(resume)setPlaying(true);}})();
 return prepareTask;
}
function extendTrim(){if(isSurface(settings)&&(!model||settings.trimOut>availableEnd()+1e-8||busy))prepare().catch(fail);}
class FootRenderer extends WebGLMotionRenderer{
 drawNNGhost(pose){
  const opacity=1-settings.ghostTranslucency/100;if(opacity<=0)return;
  const gl=this.gl,mesh=this.ghostMesh||=(new LabVertexStream(350000)),buffer=this.ghostBuffer||=gl.createBuffer();
  if(this.ghostPoints!==pose.points||this.ghostAxes!==pose.axes){
   mesh.length=0;this.addBody(mesh,{...pose,hideSword:true,upperOnly:false,skeleton:false,bicolor:false,tint:[.64,.45,.95]});
   this.uploadVertices(buffer,mesh);this.ghostPoints=pose.points;this.ghostAxes=pose.axes;
  }
  // X-ray comparison, using the same collider volumes as the displayed body.
  // A depth-only prepass prevents overlapping back faces accumulating opacity.
  gl.depthMask(true);gl.clear(gl.DEPTH_BUFFER_BIT);gl.depthFunc(gl.LESS);
  gl.colorMask(false,false,false,false);this.bindAndDraw(buffer,mesh,gl.TRIANGLES,false);
  gl.colorMask(true,true,true,true);gl.depthFunc(gl.EQUAL);gl.depthMask(false);
  gl.enable(gl.BLEND);gl.blendFunc(gl.SRC_ALPHA,gl.ONE_MINUS_SRC_ALPHA);gl.uniform1f(this.locations.opacity,opacity);
  this.bindAndDraw(buffer,mesh,gl.TRIANGLES,false);
  gl.uniform1f(this.locations.opacity,1);gl.disable(gl.BLEND);gl.depthMask(true);gl.depthFunc(gl.LEQUAL);
 }
 bindCamera(){const c=this.canvas;c.addEventListener('contextmenu',e=>e.preventDefault());
 c.addEventListener('pointerdown',e=>{e.preventDefault();document.activeElement?.blur?.();c.focus({preventScroll:true});c.setPointerCapture(e.pointerId);this.drag={x:e.clientX,y:e.clientY,startX:e.clientX,startY:e.clientY,button:e.button,select:e.button===0&&!e.altKey,moved:false};if(this.drag.select&&!busy)this.drag.selection=platformEditor?.previewSelection(e.clientX,e.clientY);});
 c.addEventListener('pointermove',e=>{if(!this.drag)return;const d=this.drag;if(d.select&&!d.moved){if(Math.hypot(e.clientX-d.startX,e.clientY-d.startY)<4)return;d.moved=true;if(d.selection){platformEditor?.finishSelection(d.selection,true,true);d.selection=null;}}const dx=e.clientX-d.x,dy=e.clientY-d.y;d.x=e.clientX;d.y=e.clientY;if(d.button===1||d.button===2){cameraState.panX+=dx;cameraState.panY+=dy;}else{cameraState.yaw-=dx*.008;cameraState.pitch=clamp(cameraState.pitch-dy*.006,-1.15,1.75);}drawAll();});
 const end=e=>{const d=this.drag;if(!d)return;this.drag=null;const orbit=d.moved||Math.hypot(e.clientX-d.startX,e.clientY-d.startY)>=4;if(d.selection)platformEditor?.finishSelection(d.selection,e.type!=='pointerup'||orbit,orbit);save();};for(const event of ['pointerup','pointercancel','lostpointercapture'])c.addEventListener(event,end);
 c.addEventListener('wheel',e=>{e.preventDefault();const z=Math.min(3,cameraState.zoom*Math.exp(-e.deltaY*.001));if(z>0&&Number.isFinite(3.55/z))cameraState.zoom=z;drawAll();save();},{passive:false});c.addEventListener('dblclick',()=>{Object.assign(cameraState,cameraDefault);drawAll();save();});}

 draw(data,center){super.draw(data,center);if(!data||!model)return;const gl=this.gl,mesh=this.terrainMesh||=(new LabVertexStream(50000)),lines=this.terrainLines||=(new LabVertexStream(15000)),sides=this.sides||=[];mesh.length=lines.length=sides.length=0;
  const surfaces=platformEditor?.surfaces()||sceneSurfaces();
  for(const surface of surfaces){this.platformBox(mesh,sides,surface,surface.id===platformEditor?.selected?[.38,.34,.23]:surface.id.startsWith('step')?[.19,.25,.34]:[.14,.20,.28],1-settings.translucency/100);
   if(dot(surface.normal,sub(this.viewCamera.eye,surface.origin))<=0)continue;
   const [x0,x1,z0,z1]=surface.bounds,[a,b,c,d]=[[x0,.004,z0],[x1,.004,z0],[x1,.004,z1],[x0,.004,z1]].map(surface.world);for(const [p,q] of [[a,b],[b,c],[c,d],[d,a]])this.line(lines,p,q,[.37,.45,.57]);
   if(model.terrain.surfaces){for(let x=Math.ceil(x0);x<x1;x++)this.line(lines,surface.world([x,.003,z0]),surface.world([x,.003,z1]),[.22,.29,.39]);for(let z=Math.ceil(z0);z<z1;z++)this.line(lines,surface.world([x0,.003,z]),surface.world([x1,.003,z]),[.22,.29,.39]);}
  }
  if(settings.ramp){if(model.terrain.surfaces){for(let i=1;i<model.frames.length;i+=6)this.line(lines,model.frames[i-1].root,model.frames[i].root,[1,.65,.24]);}else for(const x of [-.45,.45])for(let z=-1;z<model.terrain.end+1;z+=.12){const a=[x,model.terrain.rootHeight(z)+.012,z],b=[x,model.terrain.rootHeight(z+.065)+.012,z+.065];this.line(lines,a,b,[1,.65,.24]);}}
  gl.uniform1i(this.locations.receiveShadows,true);
  this.bindAndDraw(this.meshBuffer,mesh,gl.TRIANGLES);
  this.drawPlatformSides(sides,1-settings.translucency/100);
  gl.uniform1i(this.locations.receiveShadows,false);
  this.bindAndDraw(this.lineBuffer,lines,gl.LINES);
  const overlay=this.debugLines||=(new LabVertexStream(15000));overlay.length=0;
  if(settings.ghost)this.drawNNGhost(frame.raw);
  if(settings.showRoot){const p=data.points[0],c=[1,.86,.2],r=.075;for(let axis=0;axis<3;axis++){const a=p.slice(),b=p.slice();a[axis]-=r*1.7;b[axis]+=r*1.7;this.line(overlay,a,b,c);for(let i=0;i<24;i++){const a=p.slice(),b=p.slice(),u=(axis+1)%3,v=(axis+2)%3;a[u]+=r*Math.cos(i*Math.PI/12);a[v]+=r*Math.sin(i*Math.PI/12);b[u]+=r*Math.cos((i+1)*Math.PI/12);b[v]+=r*Math.sin((i+1)*Math.PI/12);this.line(overlay,a,b,c);}}
   const facing=rootFacing(),up=frame.surface?.bodyUp||[0,1,0],right=normalize(cross(up,facing)),tip=add(p,mul(facing,.55)),neck=add(tip,mul(facing,-.14));
   this.line(overlay,p,tip,c);for(const axis of [right,up])for(const sign of [-1,1])this.line(overlay,tip,add(neck,mul(axis,sign*.075)),c);
  }
  if(settings.targets&&frame.slide?.hand){const h=frame.slide.hand,p=data.points[nameToIndex.get('hand_'+h.side)];this.line(overlay,p,h.point,h.touching?[.25,1,.65]:[1,.55,.2]);}
  if(settings.targets){for(const f of frame.feet){const color=['PIN','ROLL','SLIDE'].includes(f.state)?[.25,1,.65]:f.state==='REACH'?[1,.55,.2]:[.6,.65,1],p=f.slideContact?.point||f.contact?.point||f.target,surface=surfaces.find(s=>s.id===(f.slideContact?.surface||f.contact?.surface)),u=surface?.u||[1,0,0],v=surface?.v||[0,0,1];for(let i=0;i<32;i++){const a=i*Math.PI/16,b=(i+1)*Math.PI/16;this.line(overlay,add(p,add(mul(u,Math.cos(a)*.06),mul(v,Math.sin(a)*.06))),add(p,add(mul(u,Math.cos(b)*.06),mul(v,Math.sin(b)*.06))),color);}this.line(overlay,data.points[nameToIndex.get('foot_'+f.side.toLowerCase())],p,color);}}
  gl.disable(gl.DEPTH_TEST);this.bindAndDraw(this.lineBuffer,overlay,gl.LINES);gl.enable(gl.DEPTH_TEST);
 }
}
function drawAll(){if(!renderer||!model)return;frame=model.sample(time);const pose=settings.enabled?frame.pose:frame.raw,data={...pose,hideSword:true,voidScene:true,upperOnly:false,bicolor:settings.bicolor,skeleton:settings.bones,tint:[.91,.49,.25]};renderer.draw(data,S.com(pose,names,parents,run.poses[0]));platformEditor?.render();const v=rootVelocity(model,time);$('rootVelocityRead').textContent='Root v '+norm(v).toFixed(2)+' m/s';$('rootVelocityRead').title=v.map((n,i)=>'XYZ'[i]+': '+n.toFixed(2)+' m/s').join(' · ');$('frameRead').textContent='F '+Math.round(time*60)+' / 300';$('rootTravelRead').textContent=K.travelAt(run,time).toFixed(2)+' m';$('scrub').value=time;$('scrub').setAttribute('aria-valuetext','Frame '+Math.round(time*60));$('phase').textContent=(playing?'':'PAUSED · ')+(settings.enabled?(frame.nn?'NN':frame.surface?'SURFACE · '+frame.surface.mode:'FOOT IK'):'RAW NN');$('leftState').textContent=settings.enabled?frame.feet[0].state:'RAW';$('rightState').textContent=settings.enabled?frame.feet[1].state:'RAW';$('pelvisRead').textContent=(settings.enabled?frame.pelvisOffset*100:0).toFixed(1)+' cm';}
function editable(el){return el?.isContentEditable||el?.tagName==='TEXTAREA'||el?.tagName==='SELECT'||el?.tagName==='INPUT'&&!['range','checkbox','button'].includes(el.type);}
function rootFacing(){if(frame.slide)return frame.slide.heading;const heading=K.rootHeading(run,time,settings,model.speed);return frame.surface?R.rotate(frame.surface.bodyRotation,heading):heading;}
function rootVelocity(model,t){const sample=model.sample(t);if(sample.surface?.velocity)return sample.surface.velocity;const a=Math.max(0,t-1/120),b=Math.min(model.duration,t+1/120);return b>a?mul(sub(model.sample(b).pose.points[0],model.sample(a).pose.points[0]),1/(b-a)):[0,0,0];}
function sceneSurfaces(){return model.terrain.surfacesAt?.(time)||model.terrain.surfaces||model.terrain.tiles.map(tile=>S.rectangle(tile.id,[0,tile.y,0],[1,0,0],[0,0,1],[tile.x0,tile.x1,tile.z0,tile.z1],Math.max(.12,tile.y+.2)));}
function defaultPlatformRecords(){return (model.terrain.original||FootSurface.createTerrain({...settings,platformLayouts:{...settings.platformLayouts,[settings.terrain]:[]}}).original).map(S.platformRecord);}
function platformRecords(){return settings.platformLayouts[settings.terrain]??defaultPlatformRecords();}
function initPlatformEditor(){platformEditor=new FootPlatforms.Editor({
 get:()=>({settings:{...settings,platforms:settings.platformLayouts[settings.terrain]??null},edge:model.terrain.end,surfaces:sceneSurfaces(),camera:renderer.viewCamera,rect:$('viewport').getBoundingClientRect(),center:frame.pose.points[nameToIndex.get('pelvis')]}),
 records:platformRecords,build:list=>list.filter(p=>!(settings.terrain==='incline'&&p.id==='entry'&&settings.deleteFloorFrame>=0&&time*60>=settings.deleteFloorFrame)).map(S.platformSurface),
 pause:()=>setPlaying(false),draw:drawAll,
 change:list=>{const layouts={...settings.platformLayouts},original=defaultPlatformRecords(),same=list&&list.length===original.length&&list.every(p=>{const q=original.find(x=>x.id===p.id);return q&&['position','rotation','size'].every(k=>p[k].every((v,i)=>Math.abs(v-q[k][i])<1e-9));});if(list===null||same)delete layouts[settings.terrain];else layouts[settings.terrain]=list;settings={...settings,platformLayouts:layouts};},
 commit:()=>{save();prepare().catch(fail);}
 });}
function bind(){
 $('addPlatform').onclick=()=>{if(!busy)platformEditor?.add();};
 for(const k of ['gait','terrain','height','depth','steps','clearance','pelvis','direction','slopeAngle','approach','upright','rootYawSpeed','rootYawStart','rootYawStop','footYawLimit','stepAccent','minGravityIncline','fullGravity','energyConservation','deleteFloorFrame','pinReleaseSpeed','pelvisCloser','pelvisSpeedMin','pelvisSpeedMax','pelvisCloserMax','slideSpeed','slideBlend','slideFriction','slideRecovery','slideShift','slideShiftSpeed','slideHandShift','slideHandShiftSpeed','slideHeadSpeed','slideCloser','slideLegBlend','slidePelvisBlend'])$(k).onchange=()=>{settings=K.sanitize({...settings,[k]:$(k).value});if(k==='terrain'&&platformEditor){platformEditor.selected=null;platformEditor.preview=null;platformEditor.history=[];}sync();save();prepare().catch(fail);};
 $('upright').oninput=()=>{$('uprightRead').textContent=Math.round(+$('upright').value*100)+'%';};
 $('phaseInput').oninput=()=>{$('phaseRead').textContent=Math.round(+$('phaseInput').value*100)+'%';};$('phaseInput').onchange=()=>{settings=K.sanitize({...settings,phase:+$('phaseInput').value});save();prepare().catch(fail);};
 for(const k of ['ghost','targets','ramp','bicolor','bones','loop','showRoot'])$(k).onchange=()=>{settings[k]=$(k).checked;drawAll();save();};
 $('inclineGravity').onchange=()=>{settings.inclineGravity=$('inclineGravity').checked;sync();save();prepare().catch(fail);};
 $('slideEnabled').onchange=()=>{settings.slideEnabled=$('slideEnabled').checked;sync();save();prepare().catch(fail);};
 $('enabled').onchange=()=>{settings.enabled=$('enabled').checked;save();prepare().catch(fail);};
 $('translucency').onchange=()=>{settings=K.sanitize({...settings,translucency:+$('translucency').value});sync();drawAll();save();};
 $('ghostTranslucency').oninput=()=>{settings.ghostTranslucency=+$('ghostTranslucency').value;$('ghostTranslucencyRead').textContent=settings.ghostTranslucency+'%';drawAll();save();};
 $('speed').oninput=()=>{settings.speed=+$('speed').value;$('speedRead').textContent=settings.speed.toFixed(1)+'×';save();};
 $('play').onclick=()=>{if(!playing&&(time<settings.trimIn||time>=settings.trimOut))seek(settings.trimIn);setPlaying(!playing);save();};$('step').onclick=()=>{setPlaying(false);seek(time+1/60);save();};$('reset').onclick=()=>{setPlaying(false);seek(0);save();};
 // Scrubbing changes the playhead, not the Play/Pause state. Restart only the
 // frame clock so elapsed time from before the seek cannot advance it again.
 $('scrub').oninput=()=>{const t=+$('scrub').value;lastStamp=0;accumulator=0;seek(t);};$('scrub').onchange=save;
 for(const key of ['trimIn','trimOut']){const el=$(key);let drag=null;const move=e=>{const rect=$('scrub').getBoundingClientRect(),t=Math.round(clamp((e.clientX-rect.left-6)/(rect.width-12)*5,0,5)*60)/60;settings[key]=key==='trimIn'?Math.min(t,settings.trimOut-1/60):Math.max(t,settings.trimIn+1/60);settings.loop=true;$('loop').checked=true;syncTrim();seek(settings[key]);if(key==='trimOut'){clearTimeout(trimTimer);trimTimer=setTimeout(extendTrim,120);}};el.onpointerdown=e=>{e.preventDefault();setPlaying(false);resumeAfterPrepare=false;drag={time};el.setPointerCapture(e.pointerId);move(e);};el.onpointermove=e=>{if(drag)move(e);};const end=()=>{if(!drag)return;const back=drag.time;drag=null;clearTimeout(trimTimer);seek(back);save();if(key==='trimOut')extendTrim();};el.onpointerup=end;el.onpointercancel=end;el.onlostpointercapture=end;}
 window.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.isComposing&&!e.ctrlKey&&!e.metaKey&&!e.altKey&&e.target?.tagName==='INPUT'&&editable(e.target)&&!e.target.readOnly){e.preventDefault();e.stopImmediatePropagation();e.target.blur();return;}if(editable(e.target))return;if(!busy&&platformEditor&&FootPlatforms.undoShortcut(e)){e.preventDefault();e.stopImmediatePropagation();platformEditor.undo();return;}if(e.ctrlKey||e.metaKey||e.altKey)return;if(!busy&&platformEditor?.key(e)){e.preventDefault();e.stopImmediatePropagation();return;}if(['Space','ArrowLeft','ArrowRight'].includes(e.code)){e.preventDefault();e.stopImmediatePropagation();if(busy)return;if(e.code==='Space'){if(!e.repeat)$('play').click();}else{setPlaying(false);seek(time+(e.code==='ArrowLeft'?-1:1)/60);save();}}},true);
 document.addEventListener('pointerdown',e=>{const a=document.activeElement;if(a&&a!==e.target&&editable(a)&&!a.contains(e.target))a.blur();const options=$('minorOptions');if(options.open&&!options.contains(e.target))options.open=false;},true);
 for(const [id,view] of [['cameraFront',{yaw:0,pitch:0}],['cameraSide',{yaw:Math.PI/2,pitch:0}],['cameraTop',{yaw:0,pitch:-1.15}],['cameraReset',cameraDefault]])$(id).onclick=()=>{Object.assign(cameraState,view,{panX:0,panY:0});drawAll();save();};
 $('refresh').onclick=async()=>{
  if(reloading)return;
  const button=$('refresh'),started=performance.now();reloading=true;button.disabled=true;
  try{
   await persistence.flush();
   if(!sourcesUnchanged||!await sourcesUnchanged()){setPlaying(false);location.reload();return;}
   // Fetch shared saved edits without throwing away the ready renderer/gait.
   const saved=await FootHTTP.json('/state');
   const next=K.sanitize(saved.settings);
   const changed=busy||!model||!$('error').hidden||Object.keys(next).some(k=>!viewOnly.has(k)&&JSON.stringify(next[k])!==JSON.stringify(settings[k]))||(isSurface(next)&&next.trimOut>availableEnd()+1e-8);
   settings=next;
   for(const k of Object.keys(cameraDefault))if(Number.isFinite(saved.camera?.[k]))cameraState[k]=saved.camera[k];
   if(!(cameraState.zoom>0))cameraState.zoom=cameraDefault.zoom;
   time=clamp(Number(saved.playback?.time)||0,0,5);
   // The server state has now been adopted, rather than edited by this tab.
   sync();
   if(changed)await prepare();
   time=clamp(time,0,availableEnd());
   setPlaying(!!saved.playback?.playing);
   persistence.accept(persistenceBaseline(saved));save();
   console.info('[Foot IK refresh] '+JSON.stringify({ms:performance.now()-started,reprepared:changed}));
  }catch(e){fail(e);}finally{reloading=false;button.disabled=false;}
 };
 document.addEventListener('visibilitychange',()=>{if(document.hidden&&!reloading){setPlaying(false);persistence?.flush().catch(fail);}});
 window.addEventListener('pagehide',()=>{if(!reloading)persistence?.flush().catch(fail);});
}
(async()=>{const [rig,saved,health]=await Promise.all([FootHTTP.json('data/rig.json'),FootHTTP.json('/state'),FootHTTP.json('/health').then(health=>{sourcesUnchanged=FootRefresh.create(refreshFiles,Date.now()-performance.now(),FootHTTP.head);return health;})]);backendVersion=health.apiVersion;if(health.stateProtocol!==2)throw Error('Restart the Foot IK server to activate updated saving. Existing saved settings are unchanged.');names=rig.names;parents=rig.parents;nameToIndex=new Map(names.map((n,i)=>[n,i]));settings=K.sanitize(saved.settings);for(const k of Object.keys(cameraDefault))if(Number.isFinite(saved.camera?.[k]))cameraState[k]=saved.camera[k];if(!(cameraState.zoom>0))cameraState.zoom=cameraDefault.zoom;time=clamp(Number(saved.playback?.time)||0,0,5);persistence=FootPersistence.create({...persistenceBaseline(saved),playback:{time,playing:!!saved.playback?.playing}},snapshot,async data=>{await FootHTTP.json('/state',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data),keepalive:true});});save();bind();sync();const rendererStart=performance.now();renderer=new FootRenderer($('viewport'),{pixelRatio:Math.min(devicePixelRatio,1.25)});loadTiming.stages.push({name:'renderer',ms:performance.now()-rendererStart});await prepare();initPlatformEditor();drawAll();if(saved.playback?.playing&&!document.hidden)setPlaying(true);window.FootIKLab={get state(){return {...snapshot(),frame:Math.round(time*60),current:frame,metrics:model.metrics,handoff:model.handoff,errors:[...errors],busy};},seek,prepare,setPlaying};loadTiming.ready=performance.now();console.info('[Foot IK load] '+JSON.stringify(loadTiming));requestAnimationFrame(()=>console.info('[Foot IK first paint] '+performance.now().toFixed(0)+'ms'));})().catch(fail);
