'use strict';
const $=id=>document.getElementById(id), R=Recovery;
const add=R.add,sub=R.sub,mul=R.mul,dot=R.dot,cross=R.cross,norm=R.length,normalize=R.unit;
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
let names=[],parents=[],nameToIndex=new Map(),swordMesh=null,manifest=null,model=null;
let selectionPlaying=null;
let attackReturnTimes={},attackReturnEasing={},attackBoneInertia={};
let renderer=null,playing=false,time=0,loadToken=0,lastTick=0,frameHandle=null,saveTimer=null;
const loadedRevision=document.querySelector('meta[name="build-revision"]').content;
const desktopToken=new URLSearchParams(location.search).get('desktopSession')||'';
const clientId=sessionStorage.recoveryClientId||(sessionStorage.recoveryClientId=crypto.randomUUID());
let liveSequence=Number(sessionStorage.recoverySequence)||0,liveBusy=false,liveTimer=null,lastFingerprint='',lastLiveSignature='';
const publishedViews=new Map(),runtimeErrors=[];
window.addEventListener('error',e=>runtimeErrors.push(e.message));
window.addEventListener('unhandledrejection',e=>runtimeErrors.push(String(e.reason)));
const cameraDefault={yaw:-.72,pitch:-.15,zoom:1.15,panX:0,panY:0};
const cameraState={...cameraDefault}, cache=new Map();
const inertiaBones=['spine','clavicle','upperarm','lowerarm','neck_01','neck_02','head'];
const controls=[...inertiaBones.map(key=>'inertiaAlpha_'+key),'enabled','duration','returnEasing','inertia','spineTurn','phaseColors','gizmoSide','handGizmos','lowerarmGizmos','upperarmGizmos','upperOnly','skeleton','idleGhost','speed'];
const committedRanges=new Map(),draftRanges=new Set();
function rangeValue(id){return committedRanges.get(id)??$(id).value;}
function commitRanges(ids=controls){for(const id of ids)if($(id)?.type==='range'){committedRanges.set(id,$(id).value);draftRanges.delete(id);}}
const posAt=(data,j)=>data.points[j],axisAt=(data,j,a)=>data.axes[j][a];
function decodeBase64(text,Type){const raw=atob(text),bytes=Uint8Array.from(raw,c=>c.charCodeAt(0));return new Type(bytes.buffer);}
function options(){return {enabled:$('enabled').checked,duration:Number(rangeValue('duration')),returnEasing:attackReturnEasing[model?.clip.name]??1,inertia:Number(rangeValue('inertia')),spineTurn:Number(rangeValue('spineTurn')),boneInertia:Object.fromEntries(inertiaBones.map(key=>[key,Number(rangeValue('inertiaAlpha_'+key))]))};}
function endTime(){return model?model.attackSeconds+(options().enabled?options().duration:0)+.35:1;}
function state(){return {schema:'attack_recovery_view_v1',attack:$('attack').value,variant:Number($('variant').value),time,camera:{...cameraState},openPanel:!$('boneInertiaPanel').hidden?'boneInertia':!$('copyProfilePanel').hidden?'copyProfile':null,copyProfile:{source:$('profileSource').value,targets:profileTargets().map(input=>input.value)},
 attackReturnTimes:{...attackReturnTimes},attackReturnEasing:{...attackReturnEasing},attackBoneInertia:Object.fromEntries(Object.entries(attackBoneInertia).map(([name,values])=>[name,{...values}])),controls:Object.fromEntries(controls.map(id=>[id,$(id).type==='checkbox'?$(id).checked:$(id).type==='range'?rangeValue(id):$(id).value])),motionSha:model?.meta.sha256,sourceSha:manifest?.sourceReceipt.files['source.html'].sha256,revision:loadedRevision};}
async function post(url,value){const response=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json','X-Desktop-Session':desktopToken,'X-Client-Id':clientId},body:JSON.stringify(value),keepalive:url==='/state'});if(!response.ok)throw Error((await response.json()).error||`${url}: ${response.status}`);return response.json();}
function save(){if(!desktopToken)return;clearTimeout(saveTimer);saveTimer=setTimeout(()=>{if(model&&$('attack').value===model.clip.name&&Number($('variant').value)===model.meta.id)post('/state',state()).catch(e=>notice('Settings could not be saved: '+e.message));},250);}
function notice(message){$('notice').textContent=message;}
function fail(error){console.error(error);$('error').hidden=false;$('error').textContent=error.message||String(error);notice('Could not load this motion.');}
function resetCamera(){Object.assign(cameraState,cameraDefault);drawAll();save();}
function setPlaying(value){playing=!!value;$('play').textContent=playing?'Pause':'Play';lastTick=performance.now();if(playing&&frameHandle===null)frameHandle=requestAnimationFrame(tick);if(!playing)save();}
function seek(value){setPlaying(false);time=clamp(value,0,endTime());drawAll();save();}
function stepFrame(direction){
 if(!model)return;
 const end=endTime(),next=time+direction/model.meta.fps;
 seek(next>end+1e-9?0:next< -1e-9?end:clamp(next,0,end));
}
function tick(now){frameHandle=null;if(!playing)return;const elapsed=(now-lastTick)/1000;lastTick=now;time=(time+elapsed*Number($('speed').value))%endTime();drawAll();frameHandle=requestAnimationFrame(tick);}
function textIfChanged(id,value){const element=$(id);if(element.textContent!==value)element.textContent=value;}
function updateSliderLabels(){
 textIfChanged('spineTurnValue',Number($('spineTurn').value)+'°');
 textIfChanged('returnEasingValue',Number($('returnEasing').value).toFixed(2));
 textIfChanged('durationValue',Number($('duration').value).toFixed(2)+' s');textIfChanged('inertiaValue',Math.round(Number($('inertia').value)*100)+'%');
 for(const key of inertiaBones){const alpha=Number($('inertiaAlpha_'+key).value);textIfChanged('inertiaAlpha_'+key+'Value',alpha.toFixed(2)+' · '+Math.round(alpha*Number($('inertia').value)*100)+'%');}
}
function drawAll(){
 if(!model||!renderer)return;
 textIfChanged('boneInertiaAttack','For '+model.clip.name+' · all variants');
 updateSliderLabels();
 const viewOptions=options(),stop=model.attackSeconds+(viewOptions.enabled?viewOptions.duration:0)+.35;
 let pose=R.sample(model,time,viewOptions);const upperOnly=$('upperOnly').checked;
 if(upperOnly)pose=R.anchor(model,pose,model.meta.target);
 const data={...pose,target:pose.target||model.meta.target,upperOnly,upper:model.upper,skeleton:$('skeleton').checked,
   melee:!/^(slash|pike)/i.test(model.clip.name),floorTarget:model.meta.kind==='floor',gizmoSide:$('gizmoSide').value,handGizmos:$('handGizmos').checked,lowerarmGizmos:$('lowerarmGizmos').checked,upperarmGizmos:$('upperarmGizmos').checked};
 const authored=time<=model.attackSeconds||!viewOptions.enabled;
 data.tint=$('phaseColors').checked&&authored?[.23,.73,.41]:[.91,.49,.25];
 $('motionColor').style.color=`rgb(${data.tint.map(c=>Math.round(c*255)).join(',')})`;
 textIfChanged('motionLegend',$('phaseColors').checked?(authored?'Authored':'Our return'):'Motion');
 if($('idleGhost').checked){let ghost=R.sample(model,model.attackSeconds+viewOptions.duration+1,{...viewOptions,enabled:true});if(upperOnly)ghost=R.anchor(model,ghost,model.meta.target);data.ghost={...ghost,upperOnly,upper:model.upper,skeleton:true,hideSword:true,tint:[.28,.66,.86]};}
 renderer.draw(data,model.poses[0].points[0]);
 $('timeline').max=String(stop);if(!draftRanges.has('timeline'))$('timeline').value=String(time);textIfChanged('time',`${time.toFixed(2)} / ${stop.toFixed(2)} s`);
 const phases=model.clip.phases||{};let phase='Attack';
 if(time<Number(phases.armed)/model.meta.fps)phase='Pre-arm';else if(time<Number(phases.hit)/model.meta.fps)phase='Armed';else if(time<=model.attackSeconds)phase='Hit / tail';else phase=!viewOptions.enabled?'Held end':time<model.attackSeconds+viewOptions.duration?'Returning':'Idle';
 textIfChanged('phase',phase);textIfChanged('anchorLabel',upperOnly?'spine_01 fixed · lower body hidden':'');
 window.recoveryLab.currentPose=data;
 if(!playing){clearTimeout(liveTimer);liveTimer=setTimeout(publishLive,150);}
}
function fillVariants(clip,id){$('variant').replaceChildren(...clip.variants.map(v=>{const o=document.createElement('option');o.value=v.id;o.textContent=`Variant ${String(v.id).padStart(2,'0')}${v.kind==='floor'?' · FLOOR':''}`;return o;}));$('variant').value=String(clip.variants.some(v=>v.id===id)?id:clip.variants[0].id);}
async function select(attack,variant=1,restoredTime=time,resumePlaying=selectionPlaying??playing){
 const token=++loadToken;selectionPlaying=resumePlaying;setPlaying(false);$('error').hidden=true;
 const clip=manifest.clips.find(c=>c.name===attack)||manifest.clips[0];
 if(!clip){selectionPlaying=null;model=null;$('attack').replaceChildren();$('variant').replaceChildren();$('caseTitle').textContent='No variants remaining';notice('All variants have been permanently removed.');$('removeVariant').disabled=true;renderer?.draw(null,[0,0,0]);document.querySelectorAll('.transport button,.transport input,#snapshot,#floorTarget,#attack,#variant').forEach(e=>e.disabled=true);return;}
 $('attack').value=clip.name;fillVariants(clip,variant);
 const meta=clip.variants.find(v=>v.id===Number($('variant').value));
 $('attack').disabled=false;$('variant').disabled=false;notice('Loading '+clip.name+'…');
 try{
   let prepared=cache.get(meta.file);
   if(!prepared){const response=await fetch(meta.file);if(!response.ok)throw Error('Motion file unavailable');const buffer=await response.arrayBuffer();
     const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',buffer)),b=>b.toString(16).padStart(2,'0')).join('');
     if(digest!==meta.sha256)throw Error('Motion checksum mismatch');prepared=R.prepare(meta,buffer,clip,names,parents);cache.set(meta.file,prepared);if(cache.size>12)cache.delete(cache.keys().next().value);}
   if(token!==loadToken)return;model=prepared;$('returnEasing').value=String(attackReturnEasing[clip.name]??1);$('duration').value=String(attackReturnTimes[clip.name]??1);for(const key of inertiaBones)$('inertiaAlpha_'+key).value=String(attackBoneInertia[clip.name]?.[key]??1);commitRanges(['duration','returnEasing',...inertiaBones.map(key=>'inertiaAlpha_'+key)]);time=clamp(Number(restoredTime)||0,0,endTime());
   $('targetKind').textContent=meta.kind==='floor'?'Floor':'Volume';$('targetKind').classList.toggle('floor',meta.kind==='floor');
   const floors=clip.variants.filter(v=>v.kind==='floor').length;
   $('targetInfo').textContent=`${clip.variants.length-floors} volume targets${floors?' + '+floors+' floor target.':'.'}`;
   $('floorTarget').disabled=!clip.variants.some(v=>v.kind==='floor');
   $('caseTitle').textContent=`${clip.name} · ${String(meta.id).padStart(2,'0')}`;
   $('caseSubtitle').textContent=`Easy · ${meta.kind==='floor'?'floor target':'volume target'} · ${meta.frames} attack frames · ${meta.fps} fps`;
   $('libraryCount').textContent=`${manifest.clips.reduce((n,c)=>n+c.variants.length,0)} attacks available.`;
   notice(desktopToken?'Ready · settings saved automatically.':'Inspection view · shared settings are read-only.');drawAll();setPlaying(resumePlaying);save();
 }catch(e){if(token===loadToken)fail(e);}finally{if(token===loadToken)selectionPlaying=null;}
}
async function snapshotList(){const data=await (await fetch('/snapshots')).json();$('snapshot').textContent='Snapshot ('+data.length+')';$('snapshots').replaceChildren(new Option('Restore snapshot…',''),...data.map(s=>new Option('#'+s.split('_')[1],s)));}
// toBlob freezes these pixels now and encodes PNG asynchronously.
function canvasPNG(){return new Promise((resolve,reject)=>{
 $('viewport').toBlob(blob=>{if(!blob){reject(Error('Viewport capture failed'));return;}
  const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(reader.error);reader.readAsDataURL(blob);
 },'image/png');
});}
async function snapshot(){
 if(!model)return;drawAll();const saved=state(),pose=window.recoveryLab.currentPose;
 const packet={...saved,displayedPose:{points:pose.points,axes:pose.axes,target:pose.target},target:model.meta.target,kind:model.meta.kind};
 packet.image=await canvasPNG();const result=await post('/snapshot',packet);await snapshotList();notice('Saved '+result.name+' (image + exact state).');
}

function normalizeBoneInertia(values={},legacy={}){
 return Object.fromEntries(inertiaBones.map(key=>{
  let value=values[key]??legacy['inertiaAlpha_'+key];
  if(key==='spine'&&value===undefined){
   const old=[1,2,3,4,5].map(i=>Number(values['spine_0'+i]??legacy['inertiaAlpha_spine_0'+i]??1));
   value=old.reduce((sum,v)=>sum+(Number.isFinite(v)?clamp(v,0,1):1),0)/5;
  }
  value=Number(value??1);return [key,clamp(Number.isFinite(value)?value:1,0,1)];
 }));
}
function profileTargets(){return [...$('profileTargets').querySelectorAll('input:checked:not(:disabled)')];}
function updateCopyProfile(){
 const source=$('profileSource').value;
 for(const input of $('profileTargets').querySelectorAll('input')){
  input.disabled=input.value===source;if(input.disabled)input.checked=false;
  input.parentElement.classList.toggle('profile-source',input.disabled);
 }
 const count=profileTargets().length;
 $('applyProfile').disabled=!source||!count;
 $('applyProfile').textContent=count?'Copy to '+count+' attack'+(count===1?'':'s'):'Select destination attacks';
 textIfChanged('profileSummary',(attackReturnTimes[source]??1).toFixed(2)+' s return · '+(attackReturnEasing[source]??1).toFixed(2)+' easing');
}
function copyAttackProfile(){
 const source=$('profileSource').value,targets=profileTargets().map(input=>input.value);
 if(!attackBoneInertia[source]||!targets.length)return;
 const bones={...attackBoneInertia[source]},duration=attackReturnTimes[source],easing=attackReturnEasing[source];
 for(const target of targets){attackBoneInertia[target]={...bones};attackReturnTimes[target]=duration;attackReturnEasing[target]=easing;}
 if(model&&targets.includes(model.clip.name)){
  $('duration').value=String(duration);$('returnEasing').value=String(easing);
  for(const key of inertiaBones)$('inertiaAlpha_'+key).value=String(bones[key]);
  commitRanges(['duration','returnEasing',...inertiaBones.map(key=>'inertiaAlpha_'+key)]);time=Math.min(time,endTime());drawAll();
 }
 $('profileCopyStatus').textContent='Copied '+source+' to '+targets.join(', ')+'.';
 updateCopyProfile();save();
}
function showPanel(name,persist=true){
 for(const [panel,button,key] of [['boneInertiaPanel','toggleBoneInertia','boneInertia'],['copyProfilePanel','toggleCopyProfile','copyProfile']]){
  $(panel).hidden=name!==key;$(button).setAttribute('aria-expanded',String(name===key));
 }
 if(persist)save();
}
function applyControls(saved){
 if(saved?.openPanel!==undefined)showPanel(saved.openPanel,false);
 attackBoneInertia=Object.fromEntries(manifest.clips.map(clip=>[clip.name,normalizeBoneInertia(saved?.attackBoneInertia?.[clip.name],saved?.controls)]));
 attackReturnEasing=Object.fromEntries(manifest.clips.map(clip=>{const value=Number(saved?.attackReturnEasing?.[clip.name]??1);return [clip.name,clamp(Number.isFinite(value)?value:1,0,1)];}));
 const fallback=Number(saved?.controls?.duration??1);
 attackReturnTimes=Object.fromEntries(manifest.clips.map(clip=>{const value=Number(saved?.attackReturnTimes?.[clip.name]??fallback);return [clip.name,clamp(Number.isFinite(value)?value:1,.1,3)];}));
 for(const id of controls){const value=saved?.controls?.[id];if(value===undefined)continue;if($(id).type==='checkbox')$(id).checked=!!value;else if(id==='gizmoSide'){if(value==='l'||value==='r')$(id).value=value;}else if(Number.isFinite(Number(value)))$(id).value=String(value);}
 commitRanges();
 $('profileSource').value=manifest.clips.some(c=>c.name===saved?.copyProfile?.source)?saved.copyProfile.source:(saved?.attack||manifest.clips[0]?.name||'');
 for(const input of $('profileTargets').querySelectorAll('input'))input.checked=!!saved?.copyProfile?.targets?.includes(input.value);
 updateCopyProfile();
 for(const key of Object.keys(cameraDefault))if(Number.isFinite(saved?.camera?.[key]))cameraState[key]=saved.camera[key];}
async function restore(saved){applyControls(saved);const clip=manifest.clips.find(c=>c.name===saved.attack),v=clip?.variants.find(v=>v.id===saved.variant);if(!v||v.sha256!==saved.motionSha)throw Error('Snapshot belongs to a different motion dataset');await select(saved.attack,saved.variant,saved.time,false);}
window.recoveryLab={ready:false,currentPose:null,state,select,seek,snapshot,restore,model:()=>model,options,clientId,publishLive};
async function fingerprint(value){const bytes=new TextEncoder().encode(typeof value==='string'?value:JSON.stringify(value));return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),b=>b.toString(16).padStart(2,'0')).join('');}
async function publishLive(){
 if(!desktopToken||liveBusy||!model||!window.recoveryLab.ready)return;
 liveBusy=true;
 try{
  const saved=state(),pose=window.recoveryLab.currentPose,modelForView=model,viewOptions=options(),view={state:saved,playing,frame:time*model.meta.fps,phase:$('phase').textContent,
   target:model.meta.target,frameCount:model.meta.frames,fps:model.meta.fps,viewport:{width:$('viewport').width,height:$('viewport').height},
   displayedPose:{points:pose.points,axes:pose.axes,target:pose.target,tint:pose.tint,gizmoSide:pose.gizmoSide,handGizmos:pose.handGizmos,lowerarmGizmos:pose.lowerarmGizmos,upperarmGizmos:pose.upperarmGizmos},runtimeErrors:[...runtimeErrors]};
  // Freeze pixels with their exact pose before yielding; unchanged views reuse the PNG.
  const signature=JSON.stringify(view),changed=signature!==lastLiveSignature,capturedAt=new Date().toISOString();
  const pixels=changed?canvasPNG():null;
  const [key,image]=changed?await Promise.all([fingerprint(signature),pixels]):[lastFingerprint,null];
  const packet={...view,fingerprint:key,sequence:++liveSequence,capturedAt,clientId};
  sessionStorage.recoverySequence=String(liveSequence);
  if(key!==lastFingerprint)packet.image=image;
  publishedViews.set(key,{model:modelForView,state:saved,options:viewOptions,view});if(publishedViews.size>8)publishedViews.delete(publishedViews.keys().next().value);
  const result=await post('/desktop-view',packet);lastFingerprint=key;lastLiveSignature=signature;$('sharing').textContent='Desktop view shared · '+clientId.slice(0,8);
  for(const command of result.commands||[])await captureTrajectory(command);
 }catch(e){$('sharing').textContent='View sharing: '+e.message;}finally{liveBusy=false;}
}
async function captureTrajectory(command){
 const saved=publishedViews.get(command.fingerprint);
 if(!saved)return post('/capture',{id:command.id,error:'Requested view has expired',fingerprint:command.fingerprint});
 const stop=saved.model.attackSeconds+(saved.options.enabled?saved.options.duration:0),samples=[];
 for(let frame=0;frame<=Math.ceil(stop*60);frame++){const seconds=Math.min(frame/60,stop);let pose=R.sample(saved.model,seconds,saved.options);if(saved.state.controls.upperOnly)pose=R.anchor(saved.model,pose,saved.model.meta.target);samples.push({seconds,points:pose.points,axes:pose.axes});}
 await post('/capture',{id:command.id,fingerprint:command.fingerprint,state:saved.state,view:saved.view,samples});
}
async function removeVariant(){
 if(!model||!desktopToken)return;setPlaying(false);const removed=model.meta,attack=model.clip.name;$('removeVariant').disabled=true;
 try{await post('/remove-variant',{attack,variant:removed.id,motionSha:removed.sha256});manifest=await (await fetch('data/manifest.json')).json();cache.delete(removed.file);$('attack').replaceChildren(...manifest.clips.map(c=>new Option(c.name,c.name)));const clip=manifest.clips.find(c=>c.name===attack)||manifest.clips[0];await select(clip?.name,clip?.variants.find(v=>v.id>removed.id)?.id||clip?.variants[0]?.id);notice(`Permanently removed ${attack} · variant ${removed.id}.`);}catch(e){fail(e);}finally{$('removeVariant').disabled=!model;}
}
async function init(){
 const [m,s,sword]=await Promise.all([fetch('data/manifest.json').then(r=>{if(!r.ok)throw Error('Dataset is not ready');return r.json();}),fetch('/state').then(r=>r.json()),fetch('data/sword.json').then(r=>r.json())]);
 manifest=m;names=m.names;parents=m.parents;nameToIndex=new Map(names.map((n,i)=>[n,i]));
 $('profileSource').replaceChildren(...manifest.clips.map(clip=>new Option(clip.name,clip.name)));
 for(const clip of manifest.clips){const label=document.createElement('label');label.className='check';const input=document.createElement('input');input.type='checkbox';input.value=clip.name;label.append(input,document.createTextNode(clip.name));$('profileTargets').append(label);}
 swordMesh=sword?{...sword,vertices:decodeBase64(sword.vertices_b64,Float32Array),triangles:decodeBase64(sword.triangles_b64,Int32Array),bladeMask:decodeBase64(sword.blade_mask_b64,Uint8Array)}:null;applyControls(s);
 $('attack').replaceChildren(...manifest.clips.map(c=>new Option(c.name,c.name)));
 renderer=new WebGLMotionRenderer($('viewport'));
 await select(s.attack||'slashLU',s.variant||1,s.time||0,false);
 $('attack').onchange=()=>select($('attack').value,Number($('variant').value));$('variant').onchange=()=>select($('attack').value,Number($('variant').value));
 const stepVariant=direction=>{if(!model)return;const list=model.clip.variants,index=list.findIndex(v=>v.id===model.meta.id);select(model.clip.name,list[(index+direction+list.length)%list.length].id);};
 $('prevVariant').onclick=()=>stepVariant(-1);$('nextVariant').onclick=()=>stepVariant(1);
 $('removeVariant').onclick=removeVariant;$('removeVariant').disabled=!desktopToken;$('snapshot').disabled=!desktopToken;
 $('floorTarget').onclick=()=>{const c=manifest.clips.find(c=>c.name===$('attack').value);select(c.name,c.variants.find(v=>v.kind==='floor')?.id||1);};
 // Dragging only edits the widget. Rendering and saved state read committed values.
 document.addEventListener('pointerdown',event=>{if(event.target.matches('input[type=range]'))draftRanges.add(event.target.id);},true);
 document.addEventListener('input',event=>{if(event.target.matches('input[type=range]')){draftRanges.add(event.target.id);updateSliderLabels();}},true);
 document.addEventListener('change',event=>{if(event.target.matches('input[type=range]')){committedRanges.set(event.target.id,event.target.value);draftRanges.delete(event.target.id);}},true);
 document.addEventListener('pointerup',()=>{setTimeout(()=>{draftRanges.clear();updateSliderLabels();$('timeline').value=String(time);},0);},true);
 for(const id of controls)$(id).addEventListener($(id).type==='range'?'change':'input',()=>{if(id==='returnEasing'&&model)attackReturnEasing[model.clip.name]=Number($('returnEasing').value);if(id==='duration'&&model)attackReturnTimes[model.clip.name]=Number($('duration').value);if(id.startsWith('inertiaAlpha_')&&model)attackBoneInertia[model.clip.name][id.slice('inertiaAlpha_'.length)]=Number($(id).value);time=Math.min(time,endTime());drawAll();if(!$('copyProfilePanel').hidden)updateCopyProfile();save();});
 $('toggleCopyProfile').onclick=()=>{if($('copyProfilePanel').hidden){$('profileSource').value=model?.clip.name||$('profileSource').value;updateCopyProfile();showPanel('copyProfile');}else showPanel(null);};
 $('closeCopyProfile').onclick=()=>showPanel(null);
 $('profileSource').onchange=()=>{updateCopyProfile();save();};$('profileTargets').onchange=()=>{updateCopyProfile();save();};
 $('profileSelectAll').onclick=()=>{for(const input of $('profileTargets').querySelectorAll('input'))input.checked=!input.disabled;updateCopyProfile();save();};
 $('profileSelectNone').onclick=()=>{for(const input of $('profileTargets').querySelectorAll('input'))input.checked=false;updateCopyProfile();save();};
 $('applyProfile').onclick=copyAttackProfile;
 const showBoneInertia=visible=>showPanel(visible?'boneInertia':null);
 $('toggleBoneInertia').onclick=()=>showBoneInertia($('boneInertiaPanel').hidden);$('closeBoneInertia').onclick=()=>showBoneInertia(false);
 $('resetSpineTurn').onclick=()=>{$('spineTurn').value='0';commitRanges(['spineTurn']);drawAll();save();};
 $('play').onclick=()=>setPlaying(!playing);$('start').onclick=()=>seek(0);$('previous').onclick=()=>stepFrame(-1);$('next').onclick=()=>stepFrame(1);
 $('armed').onclick=()=>seek(model.clip.phases.armed/model.meta.fps);$('hit').onclick=()=>seek(model.clip.phases.hit/model.meta.fps);$('tail').onclick=()=>seek(model.attackSeconds);$('idle').onclick=()=>seek(model.attackSeconds+options().duration);
 $('timeline').onchange=()=>seek(Number($('timeline').value));$('resetCamera').onclick=resetCamera;$('snapshot').onclick=()=>snapshot().catch(fail);
 $('snapshots').onchange=async()=>{const name=$('snapshots').value;if(!name)return;try{await restore(await (await fetch('snapshots/'+name+'.json')).json());notice('Restored '+name);}catch(e){fail(e);}};
 $('refresh').onclick=async()=>{if(desktopToken)await post('/state',state());location.reload();};
 $('viewport').addEventListener('pointerup',save);$('viewport').addEventListener('wheel',save);
 // Playback keys belong to the viewport even while a select, slider or button has focus.
 const playbackKey=event=>event.code==='Space'||event.key===' '||event.key==='ArrowLeft'||event.key==='ArrowRight';
 window.addEventListener('keydown',event=>{
  if(playbackKey(event)){
   event.preventDefault();event.stopImmediatePropagation();
   if(!model)return;
   if(event.code==='Space'||event.key===' '){if(!event.repeat)setPlaying(!playing);}
   else stepFrame(event.key==='ArrowLeft'?-1:1);
  }else if(!['INPUT','SELECT','TEXTAREA'].includes(event.target.tagName)&&event.key.toLowerCase()==='p')snapshot().catch(fail);
 },true);
 window.addEventListener('keyup',event=>{if(playbackKey(event)){event.preventDefault();event.stopImmediatePropagation();}},true);
 document.addEventListener('click',event=>{if(event.target.tagName==='BUTTON'||event.target.type==='checkbox')event.target.blur();});
 window.addEventListener('pagehide',()=>{if(model&&desktopToken)post('/state',state()).catch(()=>{});});
 await snapshotList();window.recoveryLab.ready=true;
 const poll=async()=>{try{const health=await (await fetch('/health')).json();$('revision').textContent=health.revision===loadedRevision?'Local build · '+loadedRevision.slice(0,8):'Update ready · Refresh harness';}catch(e){notice('Local server unavailable; the loaded motion remains usable.');}};
 $('sharing').textContent=desktopToken?'Connecting desktop view…':'Inspection client · not the desktop publisher';
 await poll();setInterval(poll,5000);await publishLive();setInterval(publishLive,1000);
}
init().catch(fail);
