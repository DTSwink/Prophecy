'use strict';
const $=id=>document.getElementById(id),R=Recovery,Playback=HolsterPlayback,{add,sub,mul,dot,cross,length:norm,unit:normalize}=R;
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v)),posAt=(data,j)=>data.points[j],axisAt=(data,j,a)=>data.axes[j][a];
let upperMask=[],names=[],parents=[],nameToIndex=new Map(),swordMesh=null,equipmentSetup=null,motionData=null,model=null,renderer=null;
let time=0,playing=false,frameHandle=null,lastTick=0,saveTimer=null,workspaceTab='motion',currentPose=null;
const loadedRevision=document.querySelector('meta[name="build-revision"]').content;
const desktopToken=new URLSearchParams(location.search).get('desktopSession')||'';
const clientId=sessionStorage.dsClientId||(sessionStorage.dsClientId=crypto.randomUUID());
let sequence=Number(sessionStorage.dsSequence)||0,liveBusy=false;
const runtimeErrors=[],published=new Map();
window.addEventListener('error',e=>runtimeErrors.push(e.message));window.addEventListener('unhandledrejection',e=>runtimeErrors.push(String(e.reason)));
const cameraDefault={yaw:-.72,pitch:-.22,zoom:1.8,panX:0,panY:65},cameraState={...cameraDefault};
const parameters=['noCheat','leewayPhase','holsterRotationStabilization','holsterReturnDuration','holsterPivotPercent','pelvisRotationCompensation','swordRelativeSlidePole','entryInertia','entryInertiaDuration','maxElbowPoleAngularSpeed','gazeYaw','sheatheRotationTolerance','sheatheTipTolerance','slideRotationCorrection','sheatheHeadTargetAlpha','headLookInSpeedAlpha','headLookAtAlpha','headMaxDownAngle','headLookInExponent','headLookOutExponent','maxHeadLookInVelocity','maxHeadLookOutVelocity','maxHeadLookInVelocityAtMaxGaze','maxHeadLookOutVelocityAtMaxGaze','drawHeadLookOutThreshold','sheatheHeadLookOutThreshold','maxSpineClavicleAngularSpeed','motion','startTick','maxReachSpeed','maxReachRotationSpeed','slidingSpeed','maxAttachedSpeed','maxAttachedRotationSpeed','shrinkPercent','shrinkDuration','unshrinkDuration','duration','holsterX','holsterY','holsterZ','holsterPitch','holsterYaw','holsterRoll'];
const views=['showPelvisDistance','showLeeway','sequenceMode','bypassCurves','bicolor','upperOnly','skeleton','idleGhost','handGizmos','lowerarmGizmos','upperarmGizmos','gizmoSide','speed'];
let committed={...Holster.defaults},sourceHash='';
const bodyProfileKeys=['bodyTargets','pelvisRotationCompensation','maxSpineClavicleAngularSpeed','maxElbowPoleAngularSpeed','swordRelativeSlidePole','maxReachSpeed','maxReachRotationSpeed','slidingSpeed'];
const bodyProfile=o=>structuredClone(Object.fromEntries(bodyProfileKeys.map(k=>[k,o[k]])));
const bodyAction=sheathe=>sheathe?'sheatheBody':'drawBody';
let bodyProfiles={drawBody:bodyProfile(Holster.defaults),sheatheBody:bodyProfile(Holster.defaults)};
function restoreBodyProfiles(input){
 const {drawBody,sheatheBody,...shared}=input;
 // Old files migrate by cloning the existing shared values into both actions.
 bodyProfiles={drawBody:bodyProfile(Holster.sanitize({...shared,...drawBody})),sheatheBody:bodyProfile(Holster.sanitize({...shared,...sheatheBody}))};
 const attached=Holster.sanitize({...shared,...sheatheBody});
 return {...shared,maxAttachedSpeed:attached.maxAttachedSpeed,maxAttachedRotationSpeed:attached.maxAttachedRotationSpeed,...bodyProfiles[bodyAction(shared.sheathe??Holster.defaults.sheathe)]};
}

let bodyPreview=null,bodyPreviewFrame=null,bodyPreviewTargets=null,bodyPreviewHandle=null,bodyPreviewLast=0,bodyDragging=false,bodyAutoPreview=false;
let bodyPlanWorker=null,bodyPlanVersion=0,bodyPlanBusy=false,bodyPlanDirty=false;
const bodyPanel=new BodyTargetPanel($('bodyTargetsPanel'),(profile,commit)=>{
 if(bodyPreview===null){bodyAutoPreview=true;bodyPreview=bodyPanel.endpoint;bodyPreviewTargets=BodyReach.sanitize(committed.bodyTargets);refreshBodyPreview();}
 committed={...committed,bodyTargets:profile};bodyDragging=!commit;
 bodyPlanDirty=true;bodyPlanVersion++;
 requestBodyPreview();
 if(commit){save();buildBodyPlan();}
},endpoint=>{
 setPlaying(false);bodyAutoPreview=false;bodyPreview=endpoint;bodyPreviewTargets=BodyReach.sanitize(committed.bodyTargets);time=Playback.previewTime(model,endpoint==='clear'?0:1,committed.sheathe);refreshBodyPreview();drawAll();
 save();
});
function buildBodyPlan(){
 if(bodyPlanBusy||bodyDragging||!bodyPlanDirty)return;
 if(!bodyPlanWorker){
  // The worker forwards this revision to every motion dependency it imports.
  bodyPlanWorker=new Worker('body-plan-worker.js?v='+loadedRevision);
  bodyPlanWorker.onmessage=({data})=>{
   bodyPlanBusy=false;
   if(data.version!==bodyPlanVersion){buildBodyPlan();return;}
   if(data.error){bodyPlanDirty=false;fail(Error(data.error));return;}
   bodyPlanDirty=false;model=Playback.assets(data.model,motionData,equipmentSetup);
   refreshReturnTiming();
   if(bodyPreview!==null)requestBodyPreview();
   drawAll();save();
  };
  bodyPlanWorker.onerror=e=>{bodyPlanBusy=false;bodyPlanDirty=false;bodyPlanWorker.terminate();bodyPlanWorker=null;fail(Error(e.message));};
 }
 bodyPlanBusy=true;bodyPlanWorker.postMessage({version:bodyPlanVersion,options:motionOptions()});
}
function requestBodyPreview(){if(bodyPreview!==null&&!playing&&bodyPreviewHandle===null)bodyPreviewHandle=requestAnimationFrame(animateBodyPreview);}
function animateBodyPreview(now){bodyPreviewHandle=null;updateBodyPreview(now);drawAll();if(bodyPreviewLast)requestBodyPreview();}
function updateBodyPreview(now){
 if(bodyPreview===null)return;
 if(playing&&bodyAutoPreview&&!bodyPlanDirty&&!bodyDragging){clearBodyPreview();return;}
 const dt=bodyPreviewLast?Math.min(.1,(now-bodyPreviewLast)/1000):1/60;
 bodyPreviewLast=now;bodyPreviewTargets=committed.bodyTargets;
 const next=Playback.previewBody(model,bodyPreview==='clear'?0:1,committed.bodyTargets,time,committed.sheathe);
 const result=Holster.blendPreview(bodyPreviewFrame,next,1-Math.exp(-dt/.035),model.parents);
 bodyPreviewFrame=result.frame;
 if(result.settled){bodyPreviewLast=0;if(playing&&bodyAutoPreview&&!bodyPlanDirty&&!bodyDragging)clearBodyPreview();}
}
function refreshBodyPreview(){
 bodyPreviewFrame=bodyPreview!==null&&model?Playback.previewBody(model,bodyPreview==='clear'?0:1,committed.bodyTargets,time,committed.sheathe):null;
}
function clearBodyPreview(){bodyPreview=null;bodyPreviewFrame=null;bodyPreviewTargets=null;bodyPreviewLast=0;bodyAutoPreview=false;if(bodyPreviewHandle!==null)cancelAnimationFrame(bodyPreviewHandle);bodyPreviewHandle=null;}
function showBodyTargets(open){
 $('bodyTargetsPanel').hidden=!open;$('openBodyTargets').setAttribute('aria-expanded',String(open));
 if(open){$('fkReturnPanel').hidden=true;$('openFKReturn').setAttribute('aria-expanded','false');}else clearBodyPreview();
 requestAnimationFrame(drawAll);save();
}
$('openBodyTargets').onclick=()=>showBodyTargets($('bodyTargetsPanel').hidden);$('closeBodyTargets').onclick=()=>showBodyTargets(false);
$('bodyEndpoint').addEventListener('change',save);
const fkPanel=new FKReturnPanel($('fkReturnPanel'),profile=>{applyParameters({...committed,[(committed.sheathe?'sheathe':'draw')+'Return']:profile});model=Playback.retime(model,motionOptions());time=Math.min(time,model.playbackDuration);refreshReturnTiming();drawAll();save();});
function showFKReturn(open){if(open){$('bodyTargetsPanel').hidden=true;$('openBodyTargets').setAttribute('aria-expanded','false');clearBodyPreview();}$('fkReturnPanel').hidden=!open;$('openFKReturn').setAttribute('aria-expanded',String(open));requestAnimationFrame(drawAll);save();}
$('openFKReturn').onclick=()=>showFKReturn($('fkReturnPanel').hidden);$('closeFKReturn').onclick=()=>showFKReturn(false);
function motionOptions(){
 const o={...committed,...bodyProfiles,[bodyAction(committed.sheathe)]:bodyProfile(committed),sequenceMode:$('sequenceMode').checked};
 return $('bypassCurves').checked?{...o,...Object.fromEntries(['drawCurve','drawSlideCurve','sheatheCurve','sheatheSlideCurve'].map(key=>[key,Retime.linear()]))}:o;
}
function refreshReturnTiming(){const part=Playback.edited(model,committed.sheathe);fkPanel.timing(part.model,part.offset);}

const curveKey=phase=>(committed.sheathe?'sheathe':'draw')+(phase==='slide'?'SlideCurve':'Curve');
function commitCurves(values){
 applyParameters({...committed,...values});
 // Reuse body/arm planning; refresh the independently clocked return and head.
 model=Playback.retime(model,motionOptions());time=Math.min(time,model.playbackDuration);
 refreshReturnTiming();drawAll();save();
}
const curveEditors=Object.fromEntries(['reach','slide'].map(phase=>[phase,new RetimeEditor($(phase+'CurveEditor'),phase==='reach'?'Reaching':'Sliding velocity',points=>{
 commitCurves({[curveKey(phase)]:points});
})]));
for(const [id,label,unit,step] of [['holsterX','X','cm',1],['holsterY','Y','cm',1],['holsterZ','Z','cm',1],['holsterPitch','Pitch','°',1],['holsterYaw','Yaw','°',1],['holsterRoll','Roll','°',1]]){
 const div=document.createElement('div');div.innerHTML=`<label for="${id}">${label} · ${unit}</label><input id="${id}" type="number" step="${step}" value="0">`;$('placement').append(div);
}
function notice(s){$('notice').textContent=s;}
function fail(e){runtimeErrors.push(String(e));$('error').hidden=false;$('error').textContent=e.message||String(e);console.error(e);}
async function post(url,value){const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json','X-Desktop-Session':desktopToken,'X-Client-Id':clientId},body:JSON.stringify(value),keepalive:url==='/state'});if(!r.ok)throw Error((await r.json()).error||r.status);return r.json();}
function state(){return {schema:'sword_holster_lab_v1',parameters:{...committed,...bodyProfiles,[bodyAction(committed.sheathe)]:bodyProfile(committed)},time,camera:{...cameraState},workspaceTab,bodyTargetsPanelOpen:!$('bodyTargetsPanel').hidden,bodyPoseEndpoint:bodyPanel.endpoint,fkReturnPanelOpen:!$('fkReturnPanel').hidden,controls:Object.fromEntries(views.map(id=>[id,$(id).type==='checkbox'?$(id).checked:$(id).value])),sourceHash,revision:loadedRevision};}
function save(){if(!desktopToken||!model)return;clearTimeout(saveTimer);saveTimer=setTimeout(()=>post('/state',state()).catch(fail),250);}
function setWorkspaceTab(tab,persist=true){workspaceTab=tab;for(const k of ['motion','view','library']){$(k+'Controls').hidden=k!==tab;$(k+'Tab').setAttribute('aria-selected',String(k===tab));}if(persist)save();}
function applyParameters(o){if(bodyPlanDirty)bodyPlanVersion++;committed=Holster.sanitize(o);$('speedTitle').textContent=(committed.sheathe?'Sheathing':'Drawing')+' speeds';bodyPanel.set(committed.bodyTargets);$('bodyTargetsTitle').textContent='Body poses · '+(committed.sheathe?'Sheathing':'Drawing');fkPanel.set(committed.sheathe?'sheathe':'draw',committed[(committed.sheathe?'sheathe':'draw')+'Return']);for(const id of parameters)$(id)[$(id).type==='checkbox'?'checked':'value']=committed[id];for(const id of ['pelvisRotationCompensation','holsterRotationStabilization','holsterPivotPercent'])$(id+'Value').textContent=committed[id].toFixed(2);$('action').value=committed.sheathe?'sheathe':'draw';$('sheatheEntryControls').hidden=!committed.sheathe;$('sheatheHeadTargetControl').hidden=!committed.sheathe;$('sheatheHeadTargetAlphaValue').textContent=committed.sheatheHeadTargetAlpha.toFixed(2);$('headLookInSpeedAlphaValue').textContent=committed.headLookInSpeedAlpha.toFixed(2);$('gazeYawValue').textContent=committed.gazeYaw+'°';$('retimeTitle').textContent=(committed.sheathe?'Sheathing':'Drawing')+' timing curves';for(const phase of ['reach','slide'])curveEditors[phase].set(committed[curveKey(phase)]);}
function rebuild(){bodyPlanVersion++;bodyPlanDirty=false;model=Playback.prepare(motionData,equipmentSetup,motionOptions());refreshBodyPreview();time=Math.min(time,model.playbackDuration);refreshReturnTiming();drawAll();save();}
function commit(event){if(event?.target.id==='action'){bodyProfiles[bodyAction(committed.sheathe)]=bodyProfile(committed);const sheathe=$('action').value==='sheathe';clearBodyPreview();bodyDragging=false;applyParameters({...committed,...bodyProfiles[bodyAction(sheathe)],sheathe});rebuild();return;}if(['pelvisRotationCompensation','holsterRotationStabilization','holsterPivotPercent'].includes(event?.target.id)){commitPlanSlider(event.target.id);return;}applyParameters({...committed,...Object.fromEntries(parameters.map(id=>[id,$(id).type==='checkbox'?$(id).checked:$(id).value])),sheathe:$('action').value==='sheathe'});if(['swordRelativeSlidePole','entryInertia','entryInertiaDuration','sheatheHeadTargetAlpha','headLookInSpeedAlpha','headLookAtAlpha','headMaxDownAngle','headLookInExponent','headLookOutExponent','maxHeadLookInVelocity','maxHeadLookOutVelocity','maxHeadLookInVelocityAtMaxGaze','maxHeadLookOutVelocityAtMaxGaze','drawHeadLookOutThreshold','sheatheHeadLookOutThreshold'].includes(event?.target.id)){model=Playback.retime(model,motionOptions());time=Math.min(time,model.playbackDuration);refreshReturnTiming();drawAll();save();}else rebuild();}
function commitPlanSlider(id){
 const value=Number($(id).value);
 $(id+'Value').textContent=value.toFixed(2);
 if(value===committed[id])return;
 committed={...committed,[id]:value};
 bodyPlanDirty=true;bodyPlanVersion++;save();buildBodyPlan();
}
function setPlaying(v){if(v){if(bodyPreview!==null)bodyAutoPreview=true;if(bodyPlanDirty)buildBodyPlan();}playing=!!v;$('play').textContent=playing?'Pause':'Play';lastTick=performance.now();if(playing&&frameHandle===null)frameHandle=requestAnimationFrame(tick);if(!playing){requestBodyPreview();save();}}
function seek(t){clearBodyPreview();if(bodyPlanDirty)buildBodyPlan();setPlaying(false);time=clamp(t,0,model.playbackDuration);drawAll();save();}
function stepFrame(d){let t=time+d/60;seek(t<0?model.playbackDuration:t>model.playbackDuration?0:t);}
function tick(now){frameHandle=null;if(!playing)return;time=(time+(now-lastTick)/1000*Number($('speed').value))%(model.playbackDuration+.35);lastTick=now;if(bodyPreview!==null)updateBodyPreview(now);drawAll();frameHandle=requestAnimationFrame(tick);}
function resetCamera(){Object.assign(cameraState,cameraDefault);$('orbitYaw').value=String(cameraState.yaw*180/Math.PI);drawAll();save();}
function displayPoint(p,shift=[0,0,0]){const v=sub(p,shift);return [v[0]/100,v[2]/100,v[1]/100];}
// Renderer bone basis is UE local X,-Y,Z; only world coordinates swap Y/Z.
// Conjugating by the world swap would also swap local Y/Z and turn shapes sideways.
function displayAxes(q){return R.toAxes(q).map((v,k)=>[v[0],v[2],v[1]].map(x=>k===1?-x:x));}
function textIfChanged(id,value){const el=$(id);if(el.textContent!==value)el.textContent=value;}
let handSpeedCache=null;
function handSpeeds(playbackTime){
 // Fixed authored-time interval: pause, scrubbing and playback speed do not
 // change the measurement. Cache per tick; camera redraws do no pose work.
 if(bodyPreview!==null)return null;
 const tick=Math.max(1,Math.ceil(playbackTime*60-1e-7));
 if(handSpeedCache?.model===model&&handSpeedCache.tick===tick)return handSpeedCache.value;
 const start=(tick-1)/60,end=Math.min(tick/60,model.playbackDuration),dt=end-start;
 const hand=nameToIndex.get('hand_r');
 const local=t=>{const f=Playback.sample(model,t),h=f.pose[hand],q=R.qinv(f.holster.q);return {p:R.rotate(q,sub(h.p,f.holster.p)),q:R.qm(q,h.q)};};
 const a=local(start),b=local(end);
 const value={linear:dt>0?norm(sub(b.p,a.p))/dt:0,angular:dt>0?Holster.angle(a.q,b.q)/dt:0};
 handSpeedCache={model,tick,value};return value;
}
function drawAll(){
 if(!model||!renderer)return;
 textIfChanged('actionLabel',model.sequence?'First action':'Action');textIfChanged('sequenceLabel',(committed.sheathe?'S → D':'D → S')+' · after full return');textIfChanged('durationLabel',model.sequence?'Time budget per action · s':'Timeline length · s');
 const playbackTime=Math.min(time,model.playbackDuration),sourceTime=Playback.recordedTime(model,playbackTime);
 const edit=Playback.edited(model,committed.sheathe),part=Playback.segment(model,playbackTime);
 for(const phase of ['reach','slide']){const segment=edit.model?.retimeSegments[phase],start=(segment?.start??0)+edit.offset,end=(segment?.end??0)+edit.offset;curveEditors[phase].showProgress(end>start&&playbackTime>=start&&playbackTime<=end?(playbackTime-start)/(end-start):null);}
 const f=bodyPreviewFrame||Playback.sample(model,playbackTime),root=f.pose[model.pelvis].p,shift=[root[0],root[1],0];
 const data={bicolor:$('bicolor').checked,points:f.pose.map(p=>displayPoint(p.p,shift)),axes:f.pose.map(p=>displayAxes(p.q)),upperOnly:$('upperOnly').checked,upper:upperMask,skeleton:$('skeleton').checked,tint:f.blocked?[.96,.56,.28]:[.91,.49,.25],gizmoSide:$('gizmoSide').value,handGizmos:$('handGizmos').checked,lowerarmGizmos:$('lowerarmGizmos').checked,upperarmGizmos:$('upperarmGizmos').checked,equipment:{sword:f.sword,holster:f.holster},shift};
 if($('idleGhost').checked){const base=Holster.motion(motionData,committed.motion,playbackTime,committed.gazeYaw);data.ghost={...data,points:base.map(p=>displayPoint(p.p,shift)),axes:base.map(p=>displayAxes(p.q)),equipment:null,hideSword:true,skeleton:true,tint:[.28,.66,.86]};}
 data.leeway=$('showLeeway').checked?HolsterLeeway.sample(part.model,f):null;
 data.pelvisDistance=null;
 if($('showPelvisDistance').checked){
  const pivot=part.model.holsterPivot
   ?add(f.holster.p,R.rotate(f.holster.q,part.model.holsterPivot))
   :Holster.point(f.holster,Holster.holsterPivot(equipmentSetup,part.model.o.holsterPivotPercent));
  data.pelvisDistance={holster:pivot,pelvis:[...root],cm:norm(sub(pivot,root))};
 }
 const leeway=data.leeway;$('leewayReadout').hidden=!leeway;
 if(leeway){
  const row=(id,text,color)=>{textIfChanged(id,text);$(id).style.color='rgb('+color.join(',')+')';},c=HolsterLeeway.colors;
  row('leewayRotation',`Rotation ${leeway.error.toFixed(1)} / ${leeway.limit.toFixed(1)}° · includes roll`,leeway.rotationOK?c.green:c.red);
  row('leewayRoll',`Roll ${leeway.roll.toFixed(1)} / ±${leeway.rollBudget.toFixed(1)}°`,leeway.rotationOK?c.green:c.red);
  row('leewayTip',`Tip ${leeway.tipError.toFixed(1)} / ${leeway.tipLimit.toFixed(1)} cm · body ${leeway.bodyOK?'ready':'waiting'}`,leeway.tipOK?c.green:c.amber);
  row('leewayGates',f.phase==='Align tip'?'Attached · aligning tip':!part.model.o.leewayPhase?(leeway.rotationOK&&leeway.tipOK?'Tip and rotation ready · attach and slide':'Waiting for tip at entrance and rotation tolerance'):leeway.rotationOK?'Rotation ready · attach to holster':'Waiting for rotation tolerance',leeway.rotationOK?c.green:c.amber);
 }
 const handVelocity=handSpeeds(playbackTime);
 textIfChanged('handLinearSpeed',handVelocity?handVelocity.linear.toFixed(1)+' cm/s':'—');
 textIfChanged('handAngularSpeed',handVelocity?handVelocity.angular.toFixed(1)+' °/s':'—');
 textIfChanged('swordShrinkReadout',((1-f.scale)*100).toFixed(1)+'%');
 textIfChanged('swordSlideReadout',(f.insertion*100).toFixed(1)+'%');
 renderer.draw(data,[0,0,0]);currentPose={...data,diagnostics:{handVelocity,sequenceAction:f.sequenceAction,fkReturn:f.fkReturn,headLook:f.headLook,body:f.body,phase:f.phase,blocked:f.blocked,handError:f.handError,metrics:f.metrics,scale:f.scale,insertion:f.insertion,progress:f.progress,tick:Math.floor(sourceTime*60),sourceTime,playbackTime}};
 const distanceLabel=$('pelvisDistanceLabel');distanceLabel.hidden=!data.pelvisDistance;
 if(data.pelvisDistance){
  const p=displayPoint(mul(add(data.pelvisDistance.holster,root),.5),shift),m=renderer.viewProjection,w=m[3]*p[0]+m[7]*p[1]+m[11]*p[2]+m[15];
  distanceLabel.hidden=w<=0;
  if(w>0){const x=(m[0]*p[0]+m[4]*p[1]+m[8]*p[2]+m[12])/w,y=(m[1]*p[0]+m[5]*p[1]+m[9]*p[2]+m[13])/w;
   distanceLabel.style.left=((x+1)*.5*renderer.rect.width)+'px';distanceLabel.style.top=((1-y)*.5*renderer.rect.height)+'px';
   textIfChanged('pelvisDistanceLabel',data.pelvisDistance.cm.toFixed(3)+' cm');
  }
 }
 textIfChanged('caseTitle',model.sequence?(committed.sheathe?'S → D · Sheathe then draw':'D → S · Draw then sheathe'):'D/S · '+(committed.sheathe?'Sheathe':'Draw / unsheathe'));textIfChanged('caseSubtitle',({idle:'Idle',walk:'Walk forward',run:'Run forward'}[committed.motion])+' · starts at tick '+committed.startTick);
 textIfChanged('phase',(f.sequenceAction?f.sequenceAction+' · ':'')+(f.blocked?'Reach limited':f.phase));textIfChanged('handError',f.handError.toFixed(1)+' cm');textIfChanged('reachError',(f.metrics?.unreachable||0).toFixed(1)+' cm');textIfChanged('retained',(f.scale*100).toFixed(1)+'%');textIfChanged('insertion',(f.insertion*100).toFixed(1)+'%');
 const statusClass=f.blocked?'warning':'muted';if($('status').className!==statusClass)$('status').className=statusClass;textIfChanged('status',model.sequence?.reason|| (bodyPreview!==null?'Editing '+(bodyPreview==='clear'?'0':'100')+'% insertion · '+(bodyPlanDirty?'updating motion…':'playback pose, including early FK return.'):f.phase==='Align tip'?(f.handError>.01?'Sword attached to holster · hand is '+f.handError.toFixed(2)+' cm from its grip target.':'Sword attached to holster · aligning at the current depth.'):f.blocked?(part.model.o.leewayPhase?'Reach is waiting for the rotation tolerance.':'Reach is waiting for the tip at the entrance within rotation tolerance.'):f.phase==='Reach'&&f.body?.remainingDegrees>.25?'Turning spine / clavicle · '+f.body.remainingDegrees.toFixed(1)+'° remaining'+(part.model.o.sheathe?'': ' before grip') :f.fkReturn?.active?'FK return to moving '+committed.motion+'.':f.headLook?.mode==='Look out'?'Head returning to gaze.':f.active?'D/S active · FK arm interpolation.':'Arm returned to base motion. '+(f.phase==='Holstered'?'Sword follows holster.':'Sword follows hand.')));
 if($('timeline').max!==String(model.playbackDuration))$('timeline').max=String(model.playbackDuration);if(!timelineDragging)$('timeline').value=String(Math.min(time,model.playbackDuration));textIfChanged('time',`${Math.min(time,model.playbackDuration).toFixed(2)} / ${model.playbackDuration.toFixed(2)} s · ${Math.floor(Math.min(time,model.playbackDuration)*60)}`);
}
let frameCapture=null;
function canvasPNG({preview=false}={}){return (frameCapture||(frameCapture=new LabFrameCapture($('viewport'),{names,parents,equipment:equipmentSetup}))).png({pose:currentPose,camera:{...cameraState},rect:{width:renderer.rect.width,height:renderer.rect.height},pixelRatio:preview?Math.min(window.devicePixelRatio||1,640/Math.max(renderer.rect.width,renderer.rect.height)):window.devicePixelRatio||1});}
async function fingerprint(value){const b=new TextEncoder().encode(JSON.stringify(value));return [...new Uint8Array(await crypto.subtle.digest('SHA-256',b))].map(x=>x.toString(16).padStart(2,'0')).join('');}
async function snapshotList(){const names=await(await fetch('/snapshots')).json();$('snapshot').textContent='Snapshot ('+names.length+')';$('snapshots').replaceChildren(new Option('Restore snapshot…',''),...names.map(n=>new Option('#'+n.split('_')[1],n)));}
async function snapshot(){drawAll();const packet={...state(),displayedPose:structuredClone(currentPose)};packet.image=await canvasPNG();const r=await post('/snapshot',packet);await snapshotList();notice('Saved '+r.name+' · PNG + exact pose and settings.');}
function restore(s){if(s.schema!=='sword_holster_lab_v1')throw Error('Not a D/S lab settings file');if(s.sourceHash&&s.sourceHash!==sourceHash)throw Error('Snapshot uses different source assets');applyParameters(restoreBodyProfiles(s.parameters||{}));$('bypassCurves').checked=!!s.controls?.bypassCurves;for(const k of views)if(s.controls?.[k]!==undefined){if($(k).type==='checkbox')$(k).checked=!!s.controls[k];else $(k).value=s.controls[k];}for(const k of Object.keys(cameraDefault))if(Number.isFinite(s.camera?.[k]))cameraState[k]=s.camera[k];setWorkspaceTab(['motion','view','library'].includes(s.workspaceTab)?s.workspaceTab:'motion',false);clearBodyPreview();bodyPanel.endpoint=s.bodyPoseEndpoint==='seated'?'seated':'clear';bodyPanel.set(committed.bodyTargets);$('bodyTargetsPanel').hidden=!s.bodyTargetsPanelOpen;$('openBodyTargets').setAttribute('aria-expanded',String(!!s.bodyTargetsPanelOpen));$('fkReturnPanel').hidden=!!s.bodyTargetsPanelOpen||!s.fkReturnPanelOpen;$('openFKReturn').setAttribute('aria-expanded',String(!$('fkReturnPanel').hidden));time=Number(s.time)||0;rebuild();seek(time);}
async function publishLive(){if(!desktopToken||liveBusy||!currentPose||bodyDragging||bodyPreviewLast)return;liveBusy=true;try{
 const saved=state(),pose=structuredClone(currentPose),frozenModel=model,image=canvasPNG({preview:playing});const view={state:saved,displayedPose:pose,playing,frame:Math.floor(time*60),fps:60,phase:pose.diagnostics.phase,runtimeErrors:[...runtimeErrors]};
 const [key,png]=await Promise.all([fingerprint(view),image]);published.set(key,{model:frozenModel,state:saved});if(published.size>8)published.delete(published.keys().next().value);
 const r=await post('/desktop-view',{...view,fingerprint:key,sequence:++sequence,image:png,capturedAt:new Date().toISOString(),clientId});sessionStorage.dsSequence=sequence;$('sharing').textContent='Desktop view shared · '+clientId.slice(0,8);
 for(const c of r.commands||[]){const v=published.get(c.fingerprint);await post('/capture',v?{id:c.id,fingerprint:c.fingerprint,state:v.state,frames:v.model.frames}:{id:c.id,error:'View expired'});}
 }catch(e){$('sharing').textContent='View sharing: '+e.message;}finally{liveBusy=false;}}
let timelineDragging=false;
window.holsterLab={ready:false,state,seek,snapshot,restore,model:()=>model,pose:()=>currentPose,errors:runtimeErrors,publishLive,setPlaying};
async function init(){
 [motionData,equipmentSetup]=await Promise.all([fetch('data/motions.json').then(r=>r.json()),fetch('data/unreal-setup.json').then(r=>r.json())]);sourceHash=await fingerprint([motionData,equipmentSetup]);names=motionData.names;upperMask=names.map(n=>!(/^(root|thigh|calf|foot|ball)/.test(n)));parents=motionData.parents;nameToIndex=new Map(names.map((n,i)=>[n,i]));renderer=new HolsterRenderer($('viewport'));
 const saved=await(await fetch('/state')).json();applyParameters(Holster.defaults);if(saved.schema){const updatedSource=saved.sourceHash&&saved.sourceHash!==sourceHash&&[...(motionData.previousSourceHashes||[]),...(equipmentSetup.previousSourceHashes||[])].includes(saved.sourceHash);restore(updatedSource?{...saved,sourceHash}:saved);}else rebuild();
 for(const id of ['sheatheHeadTargetAlpha','headLookInSpeedAlpha'])$(id).addEventListener('input',()=>{$(id+'Value').textContent=Number($(id).value).toFixed(2);});
 $('gazeYaw').addEventListener('input',()=>{$('gazeYawValue').textContent=$('gazeYaw').value+'°';});
 for(const id of ['pelvisRotationCompensation','holsterRotationStabilization','holsterPivotPercent'])$(id).addEventListener('input',()=>commitPlanSlider(id));
 for(const id of [...parameters,'action'])$(id).addEventListener('change',commit);
 for(const id of views)$(id).addEventListener('change',()=>{drawAll();save();});
 for(const t of ['motion','view','library'])$(t+'Tab').onclick=()=>setWorkspaceTab(t);
 $('play').onclick=()=>setPlaying(!playing);$('start').onclick=()=>seek(0);$('end').onclick=()=>seek(model.playbackDuration);$('actionStart').onclick=()=>{const part=Playback.edited(model,committed.sheathe);seek(part.offset+(part.model?.o.startTick||0)/60);};$('previous').onclick=()=>stepFrame(-1);$('next').onclick=()=>stepFrame(1);
 $('viewport').addEventListener('pointerup',save);$('viewport').addEventListener('wheel',save,{passive:true});
 $('timeline').oninput=()=>{timelineDragging=true;seek(Number($('timeline').value));};$('timeline').onchange=()=>{timelineDragging=false;seek(Number($('timeline').value));};
 $('orbitYaw').oninput=()=>{};$('orbitYaw').onchange=()=>{cameraState.yaw=Number($('orbitYaw').value)*Math.PI/180;drawAll();save();};
 $('snapshot').onclick=()=>snapshot().catch(fail);$('resetCamera').onclick=resetCamera;$('refresh').onclick=async()=>{if(desktopToken)await post('/state',state());location.reload();};
 $('snapshots').onchange=async()=>{if($('snapshots').value)try{restore(await(await fetch('/snapshots/'+$('snapshots').value+'.json')).json());}catch(e){fail(e);}};
 $('resetPlacement').onclick=()=>{applyParameters({...committed,...Object.fromEntries(['holsterX','holsterY','holsterZ','holsterPitch','holsterYaw','holsterRoll'].map(k=>[k,0]))});rebuild();};
 $('resetSettings').onclick=()=>{applyParameters(restoreBodyProfiles(Holster.defaults));time=0;rebuild();};
 $('sequenceMode').onchange=()=>{clearBodyPreview();bodyDragging=false;rebuild();};
 $('bypassCurves').onchange=()=>{if(bodyPlanDirty)bodyPlanVersion++;model=Playback.retime(model,motionOptions());refreshBodyPreview();refreshReturnTiming();drawAll();save();if(bodyPlanDirty)buildBodyPlan();};
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
 $('sourceInfo').textContent='Idle: '+motionData.motions.idle.asset+'\nWalk: '+motionData.motions.walk.asset+'\nRun: '+motionData.motions.run.asset+'\nBlade: '+model.bladeLength.toFixed(2)+' cm · scale from A_Sword once.\nSource fingerprint '+sourceHash.slice(0,12);$('sourceInfo').style.whiteSpace='pre-wrap';
 await snapshotList();window.holsterLab.ready=true;drawAll();notice(desktopToken?'Ready · settings saved automatically.':'Inspection view · shared settings are read-only.');if(desktopToken){setInterval(publishLive,1200);publishLive();}else $('snapshot').disabled=true;
}
init().catch(fail);
