'use strict';
const $=id=>document.getElementById(id),R=Recovery,K=FootIK,S=BodyflipSupport,{add,sub,mul,dot,cross,length:norm,unit:normalize}=R;
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v)),posAt=(data,j)=>data.points[j],axisAt=(data,j,a)=>data.axes[j][a];
let names=[],parents=[],nameToIndex=new Map(),swordMesh=null,renderer=null,run=null,model=null,frame=null,settings=K.sanitize(),time=0,playing=false,raf=null,lastStamp=0,accumulator=0,revision=0,saveTimer=null,busy=false;
const cameraDefault={yaw:1.05,pitch:.08,zoom:.8,panX:0,panY:0},cameraState={...cameraDefault},cache=new Map(),errors=[];
async function post(path,data){const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});const result=await response.json();if(!response.ok)throw Error(result.error||'Request failed');return result;}
function snapshot(){return {schema:'foot-ik-lab-v1',settings,camera:cameraState,playback:{time,playing}};}
function save(){clearTimeout(saveTimer);saveTimer=setTimeout(()=>post('/state',snapshot()).catch(fail),200);}
function fail(e){errors.push(e.message||String(e));$('error').hidden=false;$('error').textContent=errors.at(-1);setPlaying(false);}
window.addEventListener('error',e=>fail(e.error||e.message));window.addEventListener('unhandledrejection',e=>fail(e.reason));
function seek(t){time=clamp(Math.round(t*60)/60,0,5);drawAll();}
function setPlaying(v){playing=!!v&&!!model&&!busy;if(raf!==null)cancelAnimationFrame(raf);raf=null;lastStamp=0;accumulator=0;$('play').innerHTML=(playing?'Pause':'Play')+' <kbd>Space</kbd>';if(playing&&!document.hidden)raf=requestAnimationFrame(animate);else drawAll();}
function advance(){if(time>=settings.trimOut-1e-8){if(!settings.loop){setPlaying(false);return;}time=settings.trimIn;}else if(time<settings.trimIn-1e-8)time=settings.trimIn;else time=Math.min(settings.trimOut,(Math.round(time*60)+1)/60);}
function animate(stamp){raf=null;if(!playing||document.hidden)return;if(lastStamp)accumulator+=Math.min(.05,(stamp-lastStamp)/1000)*settings.speed;lastStamp=stamp;let steps=0;while(accumulator>=1/60&&steps++<6){advance();accumulator-=1/60;}drawAll();if(playing)raf=requestAnimationFrame(animate);}
function sync(){for(const k of ['gait','terrain','height','depth','steps','clearance','pelvis','translucency','ghostTranslucency','speed'])$(k).value=settings[k];for(const k of ['enabled','ghost','targets','ramp','bicolor','bones','loop'])$(k).checked=settings[k];$('phaseInput').value=settings.phase;$('phaseRead').textContent=Math.round(settings.phase*100)+'%';$('speedRead').textContent=settings.speed.toFixed(1)+'×';$('ghostTranslucencyRead').textContent=settings.ghostTranslucency+'%';syncTrim();}
function syncTrim(){for(const key of ['trimIn','trimOut']){const el=$(key);el.style.left=settings[key]/5*100+'%';el.dataset.time='F '+Math.round(settings[key]*60);el.setAttribute('aria-valuenow',settings[key]);el.setAttribute('aria-valuemin',0);el.setAttribute('aria-valuemax',5);el.setAttribute('aria-valuetext','Frame '+Math.round(settings[key]*60));} $('trimSelection').style.left=settings.trimIn/5*100+'%';$('trimSelection').style.width=(settings.trimOut-settings.trimIn)/5*100+'%';}
async function prepare(){const token=++revision,resume=playing;busy=true;setPlaying(false);$('play').disabled=$('step').disabled=true;$('status').textContent='Preparing…';
 try{const key=settings.gait+':'+settings.phase;let decoded=cache.get(key);if(!decoded){decoded=K.decode(await post('/run',{gait:settings.gait,duration:5,phase:settings.phase}),parents);cache.set(key,decoded);while(cache.size>4)cache.delete(cache.keys().next().value);}if(token!==revision)return;
  run=decoded;model=K.prepare(run,settings);$('error').hidden=true;$('status').textContent=run.source+' · '+model.speed.toFixed(1)+' m/s';$('status').title='Contact intent estimated from uncorrected NN sole height and foot speed. Terrain IK stays outside NN recurrence.';sync();drawAll();save();
 }finally{if(token===revision){busy=false;$('play').disabled=$('step').disabled=false;if(resume)setPlaying(true);}}}
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
 bindCamera(){const c=this.canvas;c.addEventListener('contextmenu',e=>e.preventDefault());c.addEventListener('pointerdown',e=>{if(document.activeElement?.blur)document.activeElement.blur();c.focus({preventScroll:true});c.setPointerCapture(e.pointerId);this.drag={x:e.clientX,y:e.clientY,button:e.button};});
 c.addEventListener('pointermove',e=>{if(!this.drag)return;const dx=e.clientX-this.drag.x,dy=e.clientY-this.drag.y;this.drag.x=e.clientX;this.drag.y=e.clientY;if(this.drag.button===1||this.drag.button===2){cameraState.panX+=dx;cameraState.panY+=dy;}else{cameraState.yaw-=dx*.008;cameraState.pitch=clamp(cameraState.pitch-dy*.006,-1.15,1.75);}drawAll();});
 const end=()=>{if(this.drag){this.drag=null;save();}};for(const event of ['pointerup','pointercancel','lostpointercapture'])c.addEventListener(event,end);
 c.addEventListener('wheel',e=>{e.preventDefault();const z=Math.min(3,cameraState.zoom*Math.exp(-e.deltaY*.001));if(z>0&&Number.isFinite(3.55/z))cameraState.zoom=z;drawAll();save();},{passive:false});c.addEventListener('dblclick',()=>{Object.assign(cameraState,cameraDefault);drawAll();save();});}
 draw(data,center){super.draw(data,center);if(!data||!model)return;const gl=this.gl,mesh=this.terrainMesh||=(new LabVertexStream(50000)),lines=this.terrainLines||=(new LabVertexStream(15000)),sides=this.sides||=[];mesh.length=lines.length=sides.length=0;
  for(const tile of model.terrain.tiles){const y=tile.y,thickness=Math.max(.12,y+.2),surface=S.rectangle(tile.id,[0,y,0],[1,0,0],[0,0,1],[tile.x0,tile.x1,tile.z0,tile.z1],thickness);this.platformBox(mesh,sides,surface,tile.id.startsWith('step')?[.19,.25,.34]:[.14,.20,.28],1-settings.translucency/100);
   if(dot(surface.normal,sub(this.viewCamera.eye,surface.origin))<=0)continue;
   const a=[tile.x0,y+.004,tile.z0],b=[tile.x1,y+.004,tile.z0],c=[tile.x1,y+.004,tile.z1],d=[tile.x0,y+.004,tile.z1];for(const [p,q] of [[a,b],[b,c],[c,d],[d,a]])this.line(lines,p,q,[.37,.45,.57]);
  }
  if(settings.ramp){for(const x of [-.45,.45])for(let z=-1;z<model.terrain.end+1;z+=.12){const a=[x,model.terrain.rootHeight(z)+.012,z],b=[x,model.terrain.rootHeight(z+.065)+.012,z+.065];this.line(lines,a,b,[1,.65,.24]);}}
  gl.uniform1i(this.locations.receiveShadows,true);
  this.bindAndDraw(this.meshBuffer,mesh,gl.TRIANGLES);
  this.drawPlatformSides(sides,1-settings.translucency/100);
  gl.uniform1i(this.locations.receiveShadows,false);
  this.bindAndDraw(this.lineBuffer,lines,gl.LINES);
  const overlay=this.debugLines||=(new LabVertexStream(15000));overlay.length=0;
  if(settings.ghost)this.drawNNGhost(frame.raw);
  if(settings.targets){for(const f of frame.feet){const color=['PIN','ROLL'].includes(f.state)?[.25,1,.65]:f.state==='REACH'?[1,.55,.2]:[.6,.65,1],p=f.contact?.point||f.target;for(let i=0;i<32;i++){const a=i*Math.PI/16,b=(i+1)*Math.PI/16;this.line(overlay,add(p,[Math.cos(a)*.06,0,Math.sin(a)*.06]),add(p,[Math.cos(b)*.06,0,Math.sin(b)*.06]),color);}this.line(overlay,data.points[nameToIndex.get('foot_'+f.side.toLowerCase())],p,color);}}
  gl.disable(gl.DEPTH_TEST);this.bindAndDraw(this.lineBuffer,overlay,gl.LINES);gl.enable(gl.DEPTH_TEST);
 }
}
function drawAll(){if(!renderer||!model)return;frame=model.sample(time);const pose=settings.enabled?frame.pose:frame.raw,data={...pose,hideSword:true,voidScene:true,upperOnly:false,bicolor:settings.bicolor,skeleton:settings.bones,tint:[.91,.49,.25]};renderer.draw(data,S.com(pose,names,parents,run.poses[0]));$('frameRead').textContent='F '+Math.round(time*60)+' / 300';$('scrub').value=time;$('scrub').setAttribute('aria-valuetext','Frame '+Math.round(time*60));$('phase').textContent=(playing?'':'PAUSED · ')+(settings.enabled?'FOOT IK':'RAW NN');$('leftState').textContent=settings.enabled?frame.feet[0].state:'RAW';$('rightState').textContent=settings.enabled?frame.feet[1].state:'RAW';$('pelvisRead').textContent=(settings.enabled?frame.pelvisOffset*100:0).toFixed(1)+' cm';}
function editable(el){return el?.isContentEditable||el?.tagName==='TEXTAREA'||el?.tagName==='SELECT'||el?.tagName==='INPUT'&&!['range','checkbox','button'].includes(el.type);}
function bind(){
 for(const k of ['gait','terrain','height','depth','steps','clearance','pelvis'])$(k).onchange=()=>{settings=K.sanitize({...settings,[k]:$(k).value});sync();prepare().catch(fail);};
 $('phaseInput').oninput=()=>{$('phaseRead').textContent=Math.round(+$('phaseInput').value*100)+'%';};$('phaseInput').onchange=()=>{settings=K.sanitize({...settings,phase:+$('phaseInput').value});prepare().catch(fail);};
 for(const k of ['enabled','ghost','targets','ramp','bicolor','bones','loop'])$(k).onchange=()=>{settings[k]=$(k).checked;drawAll();save();};
 $('translucency').onchange=()=>{settings=K.sanitize({...settings,translucency:+$('translucency').value});sync();drawAll();save();};
 $('ghostTranslucency').oninput=()=>{settings.ghostTranslucency=+$('ghostTranslucency').value;$('ghostTranslucencyRead').textContent=settings.ghostTranslucency+'%';drawAll();save();};
 $('speed').oninput=()=>{settings.speed=+$('speed').value;$('speedRead').textContent=settings.speed.toFixed(1)+'×';save();};
 $('play').onclick=()=>{if(!playing&&(time<settings.trimIn||time>=settings.trimOut))seek(settings.trimIn);setPlaying(!playing);save();};$('step').onclick=()=>{setPlaying(false);seek(time+1/60);save();};$('reset').onclick=()=>{setPlaying(false);seek(0);save();};
 $('scrub').oninput=()=>{const t=+$('scrub').value;setPlaying(false);seek(t);};$('scrub').onchange=save;
 for(const key of ['trimIn','trimOut']){const el=$(key);let drag=null;const move=e=>{const rect=$('scrub').getBoundingClientRect(),t=Math.round(clamp((e.clientX-rect.left-6)/(rect.width-12)*5,0,5)*60)/60;settings[key]=key==='trimIn'?Math.min(t,settings.trimOut-1/60):Math.max(t,settings.trimIn+1/60);settings.loop=true;$('loop').checked=true;syncTrim();seek(settings[key]);};el.onpointerdown=e=>{e.preventDefault();setPlaying(false);drag={time};el.setPointerCapture(e.pointerId);move(e);};el.onpointermove=e=>{if(drag)move(e);};const end=()=>{if(!drag)return;const back=drag.time;drag=null;seek(back);save();};el.onpointerup=end;el.onpointercancel=end;el.onlostpointercapture=end;}
 window.addEventListener('keydown',e=>{if(editable(e.target)||e.ctrlKey||e.metaKey||e.altKey)return;if(['Space','ArrowLeft','ArrowRight'].includes(e.code)){e.preventDefault();e.stopImmediatePropagation();if(busy)return;if(e.code==='Space'){if(!e.repeat)$('play').click();}else{setPlaying(false);seek(time+(e.code==='ArrowLeft'?-1:1)/60);save();}}},true);
 document.addEventListener('pointerdown',e=>{const a=document.activeElement;if(a&&a!==e.target&&editable(a)&&!a.contains(e.target))a.blur();},true);
 for(const [id,view] of [['cameraFront',{yaw:0,pitch:0}],['cameraSide',{yaw:Math.PI/2,pitch:0}],['cameraTop',{yaw:0,pitch:-1.15}],['cameraReset',cameraDefault]])$(id).onclick=()=>{Object.assign(cameraState,view,{panX:0,panY:0});drawAll();save();};
 $('refresh').onclick=async()=>{const saved=snapshot();clearTimeout(saveTimer);setPlaying(false);await post('/state',saved);location.reload();};
 document.addEventListener('visibilitychange',()=>{if(document.hidden){save();setPlaying(false);}});
}
(async()=>{const [rig,saved]=await Promise.all([fetch('data/rig.json').then(r=>r.json()),fetch('/state').then(r=>r.json())]);names=rig.names;parents=rig.parents;nameToIndex=new Map(names.map((n,i)=>[n,i]));settings=K.sanitize(saved.settings);for(const k of Object.keys(cameraDefault))if(Number.isFinite(saved.camera?.[k]))cameraState[k]=saved.camera[k];if(!(cameraState.zoom>0))cameraState.zoom=cameraDefault.zoom;time=clamp(Number(saved.playback?.time)||0,0,5);bind();sync();renderer=new FootRenderer($('viewport'),{pixelRatio:Math.min(devicePixelRatio,1.25)});await prepare();if(saved.playback?.playing&&!document.hidden)setPlaying(true);window.FootIKLab={get state(){return {...snapshot(),frame:Math.round(time*60),current:frame,metrics:model.metrics,errors:[...errors],busy};},seek,prepare,setPlaying};})().catch(fail);
