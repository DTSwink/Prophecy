'use strict';
const $=id=>document.getElementById(id),R=Recovery,{add,sub,mul,dot,cross,length:norm,unit:normalize}=R;
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v)),posAt=(data,j)=>data.points[j],axisAt=(data,j,a)=>data.axes[j][a];
let names=[],parents=[],nameToIndex=new Map(),swordMesh=null,equipmentSetup=null,motionData=null,model=null,renderer=null;
let time=0,playing=false,frameHandle=null,lastTick=0,saveTimer=null,workspaceTab='motion',currentPose=null;
const loadedRevision=document.querySelector('meta[name="build-revision"]').content;
const desktopToken=new URLSearchParams(location.search).get('desktopSession')||'';
const clientId=sessionStorage.dsClientId||(sessionStorage.dsClientId=crypto.randomUUID());
let sequence=Number(sessionStorage.dsSequence)||0,liveBusy=false;
const runtimeErrors=[],published=new Map();
window.addEventListener('error',e=>runtimeErrors.push(e.message));window.addEventListener('unhandledrejection',e=>runtimeErrors.push(String(e.reason)));
const cameraDefault={yaw:-.72,pitch:-.22,zoom:1.8,panX:0,panY:65},cameraState={...cameraDefault};
const parameters=['headLookAtAlpha','headLookInExponent','headLookOutExponent','maxHeadLookInVelocity','maxHeadLookOutVelocity','drawHeadLookOutThreshold','sheatheHeadLookOutThreshold','spineClavicleAngleLimit','maxSpineClavicleAngularSpeed','motion','startTick','maxReachSpeed','maxReachRotationSpeed','slidingSpeed','shrinkPercent','unshrinkDuration','duration','holsterX','holsterY','holsterZ','holsterPitch','holsterYaw','holsterRoll'];
const views=['bicolor','upperOnly','skeleton','idleGhost','showTarget','handGizmos','lowerarmGizmos','upperarmGizmos','gizmoSide','speed'];
let committed={...Holster.defaults},sourceHash='';
const fkPanel=new FKReturnPanel($('fkReturnPanel'),profile=>{applyParameters({...committed,[(committed.sheathe?'sheathe':'draw')+'Return']:profile});model=Holster.retime(model,committed);time=Math.min(time,model.playbackDuration);fkPanel.timing(model);drawAll();save();});
function showFKReturn(open){$('fkReturnPanel').hidden=!open;$('openFKReturn').setAttribute('aria-expanded',String(open));requestAnimationFrame(drawAll);save();}
$('openFKReturn').onclick=()=>showFKReturn($('fkReturnPanel').hidden);$('closeFKReturn').onclick=()=>showFKReturn(false);
const curveKey=phase=>(committed.sheathe?'sheathe':'draw')+(phase==='slide'?'SlideCurve':'Curve');
const curveEditors=Object.fromEntries(['reach','slide'].map(phase=>[phase,new RetimeEditor($(phase+'CurveEditor'),phase==='reach'?'Reaching':'Sliding velocity',points=>{
 applyParameters({...committed,[curveKey(phase)]:points});
 // Reuse body/arm planning; refresh the independently clocked return and head.
 model=Holster.retime(model,committed);time=Math.min(time,model.playbackDuration);
 drawAll();save();
})]));
for(const [id,label,unit,step] of [['holsterX','X','cm',1],['holsterY','Y','cm',1],['holsterZ','Z','cm',1],['holsterPitch','Pitch','°',1],['holsterYaw','Yaw','°',1],['holsterRoll','Roll','°',1]]){
 const div=document.createElement('div');div.innerHTML=`<label for="${id}">${label} · ${unit}</label><input id="${id}" type="number" step="${step}" value="0">`;$('placement').append(div);
}
function notice(s){$('notice').textContent=s;}
function fail(e){runtimeErrors.push(String(e));$('error').hidden=false;$('error').textContent=e.message||String(e);console.error(e);}
async function post(url,value){const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json','X-Desktop-Session':desktopToken,'X-Client-Id':clientId},body:JSON.stringify(value),keepalive:url==='/state'});if(!r.ok)throw Error((await r.json()).error||r.status);return r.json();}
function state(){return {schema:'sword_holster_lab_v1',parameters:{...committed},time,camera:{...cameraState},workspaceTab,fkReturnPanelOpen:!$('fkReturnPanel').hidden,controls:Object.fromEntries(views.map(id=>[id,$(id).type==='checkbox'?$(id).checked:$(id).value])),sourceHash,revision:loadedRevision};}
function save(){if(!desktopToken||!model)return;clearTimeout(saveTimer);saveTimer=setTimeout(()=>post('/state',state()).catch(fail),250);}
function setWorkspaceTab(tab,persist=true){workspaceTab=tab;for(const k of ['motion','view','library']){$(k+'Controls').hidden=k!==tab;$(k+'Tab').setAttribute('aria-selected',String(k===tab));}if(persist)save();}
function applyParameters(o){committed=Holster.sanitize(o);fkPanel.set(committed.sheathe?'sheathe':'draw',committed[(committed.sheathe?'sheathe':'draw')+'Return']);for(const id of parameters)$(id).value=committed[id];$('action').value=committed.sheathe?'sheathe':'draw';$('retimeTitle').textContent=(committed.sheathe?'Sheathing':'Drawing')+' timing curves';for(const phase of ['reach','slide'])curveEditors[phase].set(committed[curveKey(phase)]);}
function rebuild(){model=Holster.prepare(motionData,equipmentSetup,committed);time=Math.min(time,model.playbackDuration);fkPanel.timing(model);drawAll();save();}
function commit(){applyParameters({...committed,...Object.fromEntries(parameters.map(id=>[id,$(id).value])),sheathe:$('action').value==='sheathe'});rebuild();}
function setPlaying(v){playing=!!v;$('play').textContent=playing?'Pause':'Play';lastTick=performance.now();if(playing&&frameHandle===null)frameHandle=requestAnimationFrame(tick);if(!playing)save();}
function seek(t){setPlaying(false);time=clamp(t,0,model.playbackDuration);drawAll();save();}
function stepFrame(d){let t=time+d/60;seek(t<0?model.playbackDuration:t>model.playbackDuration?0:t);}
function tick(now){frameHandle=null;if(!playing)return;time=(time+(now-lastTick)/1000*Number($('speed').value))%(model.playbackDuration+.35);lastTick=now;drawAll();frameHandle=requestAnimationFrame(tick);}
function resetCamera(){Object.assign(cameraState,cameraDefault);$('orbitYaw').value=String(cameraState.yaw*180/Math.PI);drawAll();save();}
function displayPoint(p,shift=[0,0,0]){const v=sub(p,shift);return [v[0]/100,v[2]/100,v[1]/100];}
// Renderer bone basis is UE local X,-Y,Z; only world coordinates swap Y/Z.
// Conjugating by the world swap would also swap local Y/Z and turn shapes sideways.
function displayAxes(q){return R.toAxes(q).map((v,k)=>[v[0],v[2],v[1]].map(x=>k===1?-x:x));}
function drawAll(){
 if(!model||!renderer)return;
 const playbackTime=Math.min(time,model.playbackDuration),sourceTime=Holster.recordedTime(model,playbackTime);
 for(const phase of ['reach','slide']){const {start,end}=model.retimeSegments[phase];curveEditors[phase].showProgress(end>start&&playbackTime>=start&&playbackTime<=end?(playbackTime-start)/(end-start):null);}
 const f=Holster.sample(model,playbackTime),root=f.pose[model.pelvis].p,shift=[root[0],root[1],0];
 const data={bicolor:$('bicolor').checked,points:f.pose.map(p=>displayPoint(p.p,shift)),axes:f.pose.map(p=>displayAxes(p.q)),upperOnly:$('upperOnly').checked,upper:names.map(n=>!(/^(root|thigh|calf|foot|ball)/.test(n))),skeleton:$('skeleton').checked,tint:f.blocked?[.96,.56,.28]:[.91,.49,.25],gizmoSide:$('gizmoSide').value,handGizmos:$('handGizmos').checked,lowerarmGizmos:$('lowerarmGizmos').checked,upperarmGizmos:$('upperarmGizmos').checked,target:$('showTarget').checked?displayPoint(f.goal.p,shift):null,equipment:{sword:f.sword,holster:f.holster},shift};
 if($('idleGhost').checked){const base=Holster.motion(motionData,committed.motion,sourceTime);data.ghost={...data,points:base.map(p=>displayPoint(p.p,shift)),axes:base.map(p=>displayAxes(p.q)),equipment:null,hideSword:true,skeleton:true,tint:[.28,.66,.86]};}
 renderer.draw(data,[0,0,0]);currentPose={...data,diagnostics:{fkReturn:f.fkReturn,headLook:f.headLook,body:f.body,phase:f.phase,blocked:f.blocked,handError:f.handError,metrics:f.metrics,scale:f.scale,insertion:f.insertion,progress:f.progress,tick:Math.floor(sourceTime*60),sourceTime,playbackTime}};
 $('caseTitle').textContent='D/S · '+(committed.sheathe?'Sheathe':'Draw / unsheathe');$('caseSubtitle').textContent=(committed.motion==='idle'?'Idle':'Walk forward')+' · starts at tick '+committed.startTick;
 $('phase').textContent=f.blocked?'Reach limited':f.phase;$('handError').textContent=f.handError.toFixed(1)+' cm';$('reachError').textContent=(f.metrics?.unreachable||0).toFixed(1)+' cm';$('retained').textContent=(f.scale*100).toFixed(1)+'%';$('insertion').textContent=(f.insertion*100).toFixed(1)+'%';
 $('status').className=f.blocked?'warning':'muted';$('status').textContent=f.blocked?'Target is beyond arm reach. Sliding is waiting for the 2 cm arrival gate.':f.phase==='Reach'&&f.body?.remainingDegrees>.25?'Turning spine / clavicle · '+f.body.remainingDegrees.toFixed(1)+'° remaining'+(committed.sheathe?'': ' before grip') :f.fkReturn?.active?'FK return to moving '+committed.motion+'.':f.headLook?.mode==='Look out'?'Head returning forward.':f.active?'D/S active · FK arm interpolation.':'Arm returned to base motion. '+(f.phase==='Holstered'?'Sword follows holster.':'Sword follows hand.');
 $('timeline').max=String(model.playbackDuration);if(!timelineDragging)$('timeline').value=String(Math.min(time,model.playbackDuration));$('time').textContent=`${Math.min(time,model.playbackDuration).toFixed(2)} / ${model.playbackDuration.toFixed(2)} s · ${Math.floor(Math.min(time,model.playbackDuration)*60)}`;
}
function canvasPNG(){return new Promise((resolve,reject)=>$('viewport').toBlob(blob=>{if(!blob)return reject(Error('Capture failed'));const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsDataURL(blob);},'image/png'));}
async function fingerprint(value){const b=new TextEncoder().encode(JSON.stringify(value));return [...new Uint8Array(await crypto.subtle.digest('SHA-256',b))].map(x=>x.toString(16).padStart(2,'0')).join('');}
async function snapshotList(){const names=await(await fetch('/snapshots')).json();$('snapshot').textContent='Snapshot ('+names.length+')';$('snapshots').replaceChildren(new Option('Restore snapshot…',''),...names.map(n=>new Option('#'+n.split('_')[1],n)));}
async function snapshot(){drawAll();const packet={...state(),displayedPose:structuredClone(currentPose)};packet.image=await canvasPNG();const r=await post('/snapshot',packet);await snapshotList();notice('Saved '+r.name+' · PNG + exact pose and settings.');}
function restore(s){if(s.schema!=='sword_holster_lab_v1')throw Error('Not a D/S lab settings file');if(s.sourceHash&&s.sourceHash!==sourceHash)throw Error('Snapshot uses different source assets');applyParameters(s.parameters||{});for(const k of views)if(s.controls?.[k]!==undefined){if($(k).type==='checkbox')$(k).checked=!!s.controls[k];else $(k).value=s.controls[k];}for(const k of Object.keys(cameraDefault))if(Number.isFinite(s.camera?.[k]))cameraState[k]=s.camera[k];setWorkspaceTab(['motion','view','library'].includes(s.workspaceTab)?s.workspaceTab:'motion',false);$('fkReturnPanel').hidden=!s.fkReturnPanelOpen;$('openFKReturn').setAttribute('aria-expanded',String(!!s.fkReturnPanelOpen));time=Number(s.time)||0;rebuild();seek(time);}
async function publishLive(){if(!desktopToken||liveBusy||!currentPose)return;liveBusy=true;try{
 const saved=state(),pose=structuredClone(currentPose),frozenModel=model,image=canvasPNG();const view={state:saved,displayedPose:pose,playing,frame:Math.floor(time*60),fps:60,phase:pose.diagnostics.phase,runtimeErrors:[...runtimeErrors]};
 const [key,png]=await Promise.all([fingerprint(view),image]);published.set(key,{model:frozenModel,state:saved});if(published.size>8)published.delete(published.keys().next().value);
 const r=await post('/desktop-view',{...view,fingerprint:key,sequence:++sequence,image:png,capturedAt:new Date().toISOString(),clientId});sessionStorage.dsSequence=sequence;$('sharing').textContent='Desktop view shared · '+clientId.slice(0,8);
 for(const c of r.commands||[]){const v=published.get(c.fingerprint);await post('/capture',v?{id:c.id,fingerprint:c.fingerprint,state:v.state,frames:v.model.frames}:{id:c.id,error:'View expired'});}
 }catch(e){$('sharing').textContent='View sharing: '+e.message;}finally{liveBusy=false;}}
let timelineDragging=false;
window.holsterLab={ready:false,state,seek,snapshot,restore,model:()=>model,pose:()=>currentPose,errors:runtimeErrors,publishLive,setPlaying};
async function init(){
 [motionData,equipmentSetup]=await Promise.all([fetch('data/motions.json').then(r=>r.json()),fetch('data/unreal-setup.json').then(r=>r.json())]);sourceHash=await fingerprint([motionData,equipmentSetup]);names=motionData.names;parents=motionData.parents;nameToIndex=new Map(names.map((n,i)=>[n,i]));renderer=new HolsterRenderer($('viewport'));
 const saved=await(await fetch('/state')).json();applyParameters(Holster.defaults);if(saved.schema)restore(saved);else rebuild();
 for(const id of [...parameters,'action'])$(id).addEventListener('change',commit);
 for(const id of views)$(id).addEventListener('change',()=>{drawAll();save();});
 for(const t of ['motion','view','library'])$(t+'Tab').onclick=()=>setWorkspaceTab(t);
 $('play').onclick=()=>setPlaying(!playing);$('start').onclick=()=>seek(0);$('end').onclick=()=>seek(model.playbackDuration);$('actionStart').onclick=()=>seek(committed.startTick/60);$('previous').onclick=()=>stepFrame(-1);$('next').onclick=()=>stepFrame(1);
 $('viewport').addEventListener('pointerup',save);$('viewport').addEventListener('wheel',save,{passive:true});
 $('timeline').oninput=()=>{timelineDragging=true;};$('timeline').onchange=()=>{timelineDragging=false;seek(Number($('timeline').value));};
 $('orbitYaw').oninput=()=>{};$('orbitYaw').onchange=()=>{cameraState.yaw=Number($('orbitYaw').value)*Math.PI/180;drawAll();save();};
 $('snapshot').onclick=()=>snapshot().catch(fail);$('resetCamera').onclick=resetCamera;$('refresh').onclick=async()=>{if(desktopToken)await post('/state',state());location.reload();};
 $('snapshots').onchange=async()=>{if($('snapshots').value)try{restore(await(await fetch('/snapshots/'+$('snapshots').value+'.json')).json());}catch(e){fail(e);}};
 $('resetPlacement').onclick=()=>{applyParameters({...committed,...Object.fromEntries(parameters.filter(k=>k.startsWith('holster')).map(k=>[k,0]))});rebuild();};
 $('resetSettings').onclick=()=>{applyParameters(Holster.defaults);time=0;rebuild();};
 $('export').onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify(state(),null,2)],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download='ds-holster-profile.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
 $('import').onclick=()=>$('importFile').click();$('importFile').onchange=async()=>{try{restore(JSON.parse(await $('importFile').files[0].text()));notice('D/S profile imported.');}catch(e){fail(e);}};
 // Reserve playback keys before focused widgets or other lab handlers see them.
 // Consume release too: Space otherwise activates a focused button on keyup.
 const playbackKey=e=>['Space','ArrowLeft','ArrowRight'].includes(e.code);
 const consumePlayback=e=>{e.preventDefault();e.stopImmediatePropagation();};
 window.addEventListener('keydown',e=>{
  if(!playbackKey(e))return;
  consumePlayback(e);
  if(e.code==='Space'){if(!e.repeat)setPlaying(!playing);}
  else stepFrame(e.code==='ArrowLeft'?-1:1);
 },{capture:true});
 window.addEventListener('keyup',e=>{if(playbackKey(e))consumePlayback(e);},{capture:true});
 window.addEventListener('keydown',e=>{if(e.key.toLowerCase()==='p'&&!['INPUT','SELECT','TEXTAREA'].includes(e.target.tagName)){e.preventDefault();snapshot().catch(fail);}});
 $('sourceInfo').textContent='Idle: '+motionData.motions.idle.asset+'\nWalk: '+motionData.motions.walk.asset+'\nBlade: '+model.bladeLength.toFixed(2)+' cm · scale from A_Sword once.\nSource fingerprint '+sourceHash.slice(0,12);$('sourceInfo').style.whiteSpace='pre-wrap';
 await snapshotList();window.holsterLab.ready=true;drawAll();notice(desktopToken?'Ready · settings saved automatically.':'Inspection view · shared settings are read-only.');if(desktopToken){setInterval(publishLive,1200);publishLive();}else $('snapshot').disabled=true;
}
init().catch(fail);
