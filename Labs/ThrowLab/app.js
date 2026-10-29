'use strict';
const $=id=>document.getElementById(id),R=Recovery,C=ThrowCore,V=ThrowVanilla,{add,sub,mul,dot,cross,length:norm,unit:normalize}=R;
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v)),posAt=(p,j)=>p.points[j],axisAt=(p,j,a)=>p.axes[j][a];
let names=[],parents=[],nameToIndex=new Map(),swordMesh=null,clips=[],clip=null,renderer=null,currentPose=null;
let settings=C.sanitize(),time=0,playing=false,raf=null,lastStamp=0,saveTimer=null,stateWrites=Promise.resolve(),scenes=null;
let reloading=false;
let history=null,repairReceipts=[];
let objectAssets=null,projectiles=null,objectPose=null,gizmos=null;
const worldAnchor=[0,.95,1.5];
const errors=[],keys=new Set(),cameraDefault={yaw:-.65,pitch:-.08,zoom:.8,panX:0,panY:0,free:false,freeView:null,offset:null},cameraState={...cameraDefault};
function fail(e){errors.push(e.message||String(e));$('error').textContent=errors.at(-1);$('error').hidden=false;setPlaying(false);console.error(e);}
window.addEventListener('error',e=>fail(e.error||e.message));window.addEventListener('unhandledrejection',e=>fail(e.reason));
async function post(path,data){const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});if(!r.ok)throw Error((await r.json()).error);return r.json();}
function total(){return clip.duration+3;}
function authoredReleaseTime(){const value=settings.releases[clip.id];return clamp(Number.isFinite(value)?value:clip.duration*.5,0,clip.duration);}
const displayFrame=v=>Number(v.toFixed(4)).toString();
function controls(){return settings.vanilla[clip.id]||=(V.config({},clip.duration*60,authoredReleaseTime()*60));}
function presetArmPose(t){return V.pose(C.sample(clip,t,parents),parents,nameToIndex.get('lowerarm_l'),controls().forearmKeys||[],Math.min(t,clip.duration)*60,true);}
function presetPose(t){return V.pose(presetArmPose(t),parents,nameToIndex.get('hand_l'),controls().keys,Math.min(t,clip.duration)*60);}
function throwAmount(){return clip.id==='small-throw'?controls().throwPercent/100:1;}
function throwSpeed(){return clip.id==='small-throw'?ThrowAttack.chargeSpeed(chargeCurve(),throwAmount(),controls().slowdownBlend):{baseRate:1,rate:1,multiplier:1};}
function chargeTiming(){const timing=ThrowAttack.chargeTiming(controls().armed,authoredReleaseTime()*60,throwAmount()),forward=timing.forward/throwSpeed().multiplier;return {...timing,baseForward:timing.forward,forward,release:timing.trigger+forward};}
function releaseTime(){return clip?.id==='small-throw'?chargeTiming().release/60:authoredReleaseTime();}
function fullPose(t){const source=C.sample(clip,t,parents);return fullAttackPlan()?.apply(source,Math.min(t,clip.duration)*60)||source;}
let chargeCurveCache=null;
function chargeCurve(){
 attackRig||=ThrowAttack.rig(names,parents);const key=JSON.stringify([clip.id,controls().armed,authoredReleaseTime()]);
 if(chargeCurveCache?.key!==key)chargeCurveCache={key,curve:ThrowAttack.chargeCurve(f=>C.sample(clip,f/60,parents),controls().armed,authoredReleaseTime()*60,clip.duration*60,attackRig)};
 return chargeCurveCache.curve;
}
function forwardEndFrame(){return chargeCurve().peak;}
function chargeSourceFrame(frame){return ThrowAttack.chargeFrame(chargeCurve(),throwAmount(),Math.max(0,frame-chargeTiming().trigger)*throwSpeed().multiplier);}
let bodyCache=null;
function partialBodyPlan(){
 const full=fullAttackPlan(),key=JSON.stringify([clip.id,throwAmount(),controls().armed,authoredReleaseTime()]);
 if(bodyCache?.key!==key||bodyCache.full!==full)bodyCache={key,full,body:ThrowAttack.prepareBody({sample:f=>fullPose(f/60),rig:attackRig,amount:throwAmount(),trigger:chargeTiming().trigger,returnFrame:authoredReleaseTime()*60,end:clip.duration*60})};
 return bodyCache.body;
}
let armCarryCache=null;
function armCarryPlan(finish){
 const full=fullAttackPlan(),key=JSON.stringify([clip.id,throwAmount(),controls().armed,authoredReleaseTime(),controls().slowdownBlend]);
 if(armCarryCache?.key!==key||armCarryCache.full!==full){
  const base=f=>motionPose(f/60,false),timing=chargeTiming();
  armCarryCache={key,full,plan:{
   entry:ThrowAttack.prepareCarry({incoming:f=>fullPose(f/60),outgoing:base,rig:attackRig,frame:timing.trigger,duration:Math.min(4,timing.baseForward)/throwSpeed().multiplier}),
   exit:ThrowAttack.prepareCarry({incoming:base,outgoing:base,rig:attackRig,frame:finish,duration:Math.min(8,clip.duration*60-finish)})
  }};
 }
 return armCarryCache.plan;
}
function motionPose(t,carry=true){
 const amount=throwAmount();if(amount===1)return C.sample(clip,t,parents);
 const source=fullPose(t),frame=Math.min(t,clip.duration)*60,timing=chargeTiming();if(frame<=timing.trigger)return source;
 const multiplier=throwSpeed().multiplier,finish=timing.trigger+(forwardEndFrame()-controls().armed)/multiplier,entry=(frame-timing.trigger)*multiplier/Math.max(1e-9,Math.min(4,timing.baseForward));
 const u=clamp((frame-finish)/Math.max(1e-9,clip.duration*60-finish),0,1),recover=u*u*u*(10+u*(-15+6*u));
 const pose=ThrowAttack.partialPose({source,charged:fullPose(timing.trigger/60),action:fullPose(chargeSourceFrame(frame)/60),rig:attackRig,amount,recover,entry,ending:fullPose(clip.duration),anchor:frame>finish?fullPose(finish/60):source,body:partialBodyPlan(),frame,anchorFrame:Math.min(frame,finish)});
 if(!carry||amount===0)return pose;
 if(entry<1)return ThrowAttack.carryPose(pose,armCarryPlan(finish).entry,frame);
 return frame>finish&&frame<finish+8?ThrowAttack.carryPose(pose,armCarryPlan(finish).exit,frame):pose;
}
function motionPresetPose(t){
 const arm=V.pose(motionPose(t),parents,nameToIndex.get('lowerarm_l'),controls().forearmKeys||[],Math.min(t,clip.duration)*60,true);
 return V.pose(arm,parents,nameToIndex.get('hand_l'),controls().keys,Math.min(t,clip.duration)*60);
}
function weaponKind(){return settings.object==='sword'&&settings.imperialSpear?'spear':settings.object;}
function grip(){return settings.grips[clip.id][weaponKind()];}
function weaponScale(){return settings.weaponScales[clip.id][weaponKind()];}
function setWeaponScale(value){if(!Array.isArray(value)||value.length!==3||!value.every(Number.isFinite))return;settings.weaponScales[clip.id][weaponKind()]=value.map(v=>clamp(v,.1,2));drawAll();save();}
function baseProjectileOptions(){return {key:clip.id,kind:weaponKind(),scale:weaponScale(),grip:grip(),release:releaseTime(),referenceRelease:authoredReleaseTime(),sample:presetPose,hand:nameToIndex.get('hand_l'),duration:clip.duration,target:settings.target,radius:settings.radius,controls:controls()};}
let attackRig=null,attackCache=null,partialAimCache=null;
function fullAttackPlan(){
 const c=controls();if(!c.halfAttack&&!c.aimAtTarget)return null;
 const options=baseProjectileOptions(),key=JSON.stringify([options.key,options.kind,options.referenceRelease,options.target,{...options.controls,throwPercent:100},options.grip,options.scale]);
 if(attackCache?.key===key)return attackCache.plan;
 attackRig||=ThrowAttack.rig(names,parents);
 const seed=projectiles.reference(options),plan=ThrowAttack.prepare({rig:attackRig,initial:C.sample(clip,0,parents),armedPose:C.sample(clip,c.armed/60,parents),releasePose:presetPose(authoredReleaseTime()),velocity:seed.v,...(settings.object==='sword'?{aimAxis:seed.axis,aimPoint:seed.p,aimBone:options.hand}:{}),target:settings.target,half:c.halfAttack,aim:c.aimAtTarget,armed:c.armed});
 attackCache={key,plan};return plan;
}
function attackPlan(){
 const full=fullAttackPlan(),c=controls();if(throwAmount()===1||!c.aimAtTarget)return full;
 const options=baseProjectileOptions(),key=JSON.stringify([attackCache?.key,options.release,options.controls]);
 if(partialAimCache?.key===key)return partialAimCache.plan;
 const seed=projectiles.reference(options),releasePose=motionPresetPose(releaseTime()),held=projectiles.held({...options,pose:releasePose}),fullTurn=full?.rotation||[0,0,0,1];
 const partial=ThrowAttack.prepare({rig:attackRig,initial:C.sample(clip,0,parents),releasePose,velocity:R.rotate(fullTurn,seed.v),...(settings.object==='sword'?{aimAxis:R.rotate(held.q,objectAssets[weaponKind()].longAxis||[0,0,1]),aimPoint:held.p,aimBone:options.hand}:{}),target:settings.target,half:c.halfAttack,aim:true,armed:chargeTiming().forward});
 const plan={...partial,rotation:R.qm(partial.rotation,fullTurn),partial};partialAimCache={key,plan};return plan;
}
function attackPose(source,t){
 if(throwAmount()===1)return fullAttackPlan()?.apply(source,Math.min(t,clip.duration)*60)||source;
 const elapsed=Math.min(t,clip.duration)*60-chargeTiming().trigger;if(elapsed<=0)return source;
 return attackPlan()?.partial?.apply(source,elapsed)||source;
}
function authoredArmPose(t){return V.pose(attackPose(motionPose(t),t),parents,nameToIndex.get('lowerarm_l'),controls().forearmKeys||[],Math.min(t,clip.duration)*60,true);}
function authoredPose(t){return V.pose(authoredArmPose(t),parents,nameToIndex.get('hand_l'),controls().keys,Math.min(t,clip.duration)*60);}
function projectileOptions(){const plan=attackPlan(),amount=throwAmount();return {...baseProjectileOptions(),baseSample:presetPose,sample:authoredPose,pose:currentPose,preserveLaunch:!!plan||amount!==1,launchRotation:plan?.rotation,launchScale:amount};}
function editWholeFrame(){setPlaying(false);seek(Math.round(Math.min(time,clip.duration)*60)/60);}
function writeHandKey(rotation){const f=Math.round(Math.min(time,clip.duration)*60),c=controls();c.keys=c.keys.filter(k=>Math.abs(k.frame-f)>1e-7);c.keys.push({frame:f,rotation});c.keys.sort((a,b)=>a.frame-b.frame);syncVanilla();drawAll();save();}
function writeForearmKey(rotation){const f=Math.round(Math.min(time,clip.duration)*60),c=controls();c.forearmKeys=(c.forearmKeys||[]).filter(k=>Math.abs(k.frame-f)>1e-7);c.forearmKeys.push({frame:f,rotation});c.forearmKeys.sort((a,b)=>a.frame-b.frame);drawAll();save();}
function rotationResetTarget(){
 if(settings.gizmosHidden||$('vanillaTab').getAttribute('aria-selected')!=='true'||$('vanillaPanel').hidden)return null;
 if(settings.handGizmo)return {kind:'hand',label:'hand',changed:controls().keys.length>0,hint:'Restore authored hand rotation across the whole timeline of this throw'};
 if(settings.forearmGizmo)return {kind:'forearm',label:'forearm',changed:(controls().forearmKeys||[]).length>0,hint:'Restore authored forearm rotation across the whole timeline of this throw'};
 if(settings.weaponGizmo&&settings.object==='sword')return {kind:'weapon',label:'weapon',changed:grip().rotation.some(v=>v!==0),hint:'Restore the selected weapon rotation; keep its position and scale'};
 if(settings.velocityGizmo)return {kind:'velocity',label:'velocity',changed:controls().velocityRotation.some(v=>v!==0),hint:'Restore animation-derived launch direction; keep amplitude and twist'};
 return null;
}
function syncRotationReset(){const target=rotationResetTarget(),button=$('resetRotation');button.hidden=!target;if(!target)return;button.textContent='Reset '+target.label+' rotation';button.title=target.hint+(target.changed?' (Ctrl+Z to undo)':' - already at default');button.disabled=false;}
function resetRotation(){
 const target=rotationResetTarget();if(!target?.changed||gizmos?.active)return;
 document.activeElement?.blur();history?.record(settings);setPlaying(false);
 if(target.kind==='hand')controls().keys=[];
 else if(target.kind==='forearm')controls().forearmKeys=[];
 else if(target.kind==='weapon')grip().rotation=[0,0,0];
 else controls().velocityRotation=[0,0,0];
 syncVanilla();drawAll();save();
}
function drawGizmos(){
 if(!gizmos)return;syncRotationReset();const models={};
 const vanilla=$('vanillaTab').getAttribute('aria-selected')==='true'&&!$('vanillaPanel').hidden;
 for(const id of ['handGizmo','forearmGizmo','velocityGizmo','imperialSpear','weaponGizmo','scaleGizmo'])$(id).parentElement.hidden=!vanilla;
 if(!vanilla){gizmos.draw(renderer.viewCamera,models);return;}
 if(settings.forearmGizmo){const arm=nameToIndex.get('lowerarm_l');models.forearm={defaultQ:attackPose(motionPose(time),time).q[arm],currentQ:currentPose.q[arm],center:currentPose.points[arm],axes:currentPose.axes[arm],base:currentPose.q[parents[arm]],angles:V.anglesAt(controls().forearmKeys||[],Math.min(time,clip.duration)*60)};}
 if(settings.handGizmo){const hand=nameToIndex.get('hand_l'),source=authoredArmPose(time);models.hand={defaultQ:source.q[hand],currentQ:currentPose.q[hand],world:settings.handGizmoSpace==='world',center:currentPose.points[hand],base:source.q[hand],angles:V.anglesAt(controls().keys,Math.min(time,clip.duration)*60)};}
 if(settings.velocityGizmo){const seed=projectiles.preview(projectileOptions()),pose=authoredPose(releaseTime());models.velocity={center:add(seed.p,R.rotate(seed.q,seed.comOffset)),base:R.qm(attackPlan()?.rotation||[0,0,0,1],presetPose(authoredReleaseTime()).q[0]),angles:controls().velocityRotation,direction:seed.v};}
 if(settings.weaponGizmo&&settings.object==='sword'){const hand=nameToIndex.get('hand_l'),held=projectiles.held(projectileOptions()),base=R.qm(currentPose.q[hand],objectAssets[weaponKind()].bind?.rotation||[0,0,0,1]);const model={center:held.p,base,angles:grip().rotation,position:grip().position};models.weapon=model;models.move=model;}
 $('weaponGizmo').disabled=settings.object!=='sword';$('imperialSpear').disabled=settings.object!=='sword';
 $('object').options[0].textContent=settings.imperialSpear?'Imperial Spear':'Spear (sword)';
 if(settings.scaleGizmo&&settings.object==='sword')models.scale={center:projectiles.held(projectileOptions()).p,q:projectiles.held(projectileOptions()).q,scale:weaponScale()};
 $('scaleGizmo').disabled=settings.object!=='sword';
 gizmos.draw(renderer.viewCamera,settings.gizmosHidden?{}:models);
}
function trim(){const v=settings.trims[clip.id]||[0,total()],a=clamp(Number(v[0])||0,0,total()-1/60),b=clamp(Number(v[1])||total(),a+1/60,total());return [a,b];}
function snapshot(){return {schema:'throw-lab-v1',settings:structuredClone(settings),camera:structuredClone(cameraState),playback:{time,playing},history:history?.pack()||{},repairs:repairReceipts.slice()};}
function stored(){history?.record(settings);scenes=ThrowScenes.capture(scenes,snapshot());return ThrowScenes.pack(scenes);}
function persist(data){const payload=structuredClone(data);return stateWrites=stateWrites.catch(()=>{}).then(()=>post('/state',payload));}
function save(){clearTimeout(saveTimer);if(reloading)return;history?.record(settings);syncHistoryUI();saveTimer=setTimeout(()=>persist(stored()).catch(fail),250);}
function syncHistoryUI(){if(!$('undoEdit'))return;$('undoEdit').disabled=!history?.undoStack.length;$('redoEdit').disabled=!history?.redoStack.length;}
function undoEdit(redo=false){
 if(!history||gizmos?.active)return;document.activeElement?.blur();history.record(settings);
 const restored=history.move(redo);if(!restored){syncHistoryUI();return;}
 setPlaying(false);settings=C.sanitize(restored);clip=clips.find(c=>c.id===settings.clip)||clips[0];settings.clip=clip.id;time=clamp(time,0,total());sync();history.rebase(settings);drawAll();save();
}
async function refresh(){const state=stored();reloading=true;setPlaying(false);clearTimeout(saveTimer);try{await persist(state);location.reload();}catch(e){reloading=false;fail(e);}}
function seek(t){time=clamp(t,0,total());drawAll();}
function step(direction){setPlaying(false);seek((Math.round(time*60)+direction)/60);save();}
function setPlaying(value){playing=!!value;if(playing&&clip){const [a,b]=trim();if(time<a||time>=b)time=a;}lastStamp=0;drawAll();schedule();}
function schedule(){if(raf===null&&!document.hidden&&(playing||(cameraState.free&&keys.size)))raf=requestAnimationFrame(frame);}
function frame(stamp){raf=null;const dt=lastStamp?Math.min(.1,(stamp-lastStamp)/1000):0;lastStamp=stamp;
 if(cameraState.free&&keys.size)BodyflipCamera.move(cameraState,keys,dt);
 if(playing){const [a,b]=trim();time+=dt*settings.playbackSpeed;if(time>=b){if(settings.trimLoop)time=a+(time-a)%(b-a);else{time=b;playing=false;save();}}}
 drawAll();schedule();
}
function drawAll(){if(!renderer||!clip)return;currentPose=authoredPose(time);
 objectPose=projectiles.at(time,projectileOptions());
 renderer.draw({...currentPose,bicolor:settings.bicolor,skeleton:settings.skeleton,roomBrightness:settings.roomBrightness,hideSword:true},worldAnchor);
 drawGizmos();
 $('play').innerHTML=playing?'Pause <kbd>Space</kbd>':'Play <kbd>Space</kbd>';$('phase').textContent=(playing?'PLAYING':'PAUSED')+' · '+(objectPose.phase==='held'?'LEFT HAND':objectPose.phase.toUpperCase());$('scrub').value=time*60;$('frameRead').textContent='F '+displayFrame(time*60);syncHand();syncLaunchRead();
}
function sync(){
 $('clip').value=clip.id;$('clipInfo').textContent=`Animation: F 0–${Math.round(clip.duration*60)} · +180 flight frames`;
 $('scrub').max=Math.round(total()*60);['bicolor','skeleton','trimLoop','handGizmo','forearmGizmo','velocityGizmo','imperialSpear','weaponGizmo','scaleGizmo'].forEach(k=>$(k).checked=settings[k]);$('freeCamera').checked=cameraState.free;
 settings.vanilla[clip.id]=V.config(controls(),clip.duration*60,authoredReleaseTime()*60);
 $('object').value=settings.object;syncRelease();syncVanilla();
 $('roomBrightness').value=settings.roomBrightness;$('roomBrightnessRead').textContent=Math.round(settings.roomBrightness)+'%';
 $('playbackSpeed').value=settings.playbackSpeed;$('playbackSpeedRead').textContent=settings.playbackSpeed.toFixed(1)+'×';syncTarget();syncTrim();
 $('scene').replaceChildren(...scenes.items.map(s=>new Option(s.name,s.id)));$('scene').value=scenes.active;
}
function syncTarget(){['X','Y','Z'].forEach((a,i)=>$('target'+a).value=Number(settings.target[i].toFixed(3)));$('radius').value=settings.radius;}
function syncPercent(){
 const c=controls(),timing=chargeTiming();$('throwPercentSection').hidden=clip.id!=='small-throw';$('throwPercent').value=c.throwPercent;$('throwPercentRead').textContent=displayFrame(c.throwPercent)+'%';$('slowdownBlend').value=c.slowdownBlend;$('slowdownBlendRead').textContent=c.slowdownBlend.toFixed(2);$('slowdownBlendHint').textContent='0 = current slowdown / 1 = no slowdown. Throw motion: '+throwSpeed().rate.toFixed(2)+'x.';
 $('throwPercentHint').textContent='Normal-speed wind-up to F '+displayFrame(timing.trigger)+', then '+displayFrame(throwAmount()*100)+'% forward arc and '+displayFrame(throwAmount()**2*100)+'% remaining body effort. Release F '+displayFrame(releaseTime()*60)+'.';
}
function syncRelease(){
 $('releaseFrame').max=clip.duration*60;$('releaseFrame').value=displayFrame(authoredReleaseTime()*60);$('armedFrame').max=authoredReleaseTime()*60;$('armedFrame').value=displayFrame(controls().armed);
 const partial=throwAmount()!==1;for(const id of ['armedFrame','releaseFrame'])document.querySelector('label[for="'+id+'"] span').textContent=partial?'frame at 100%':'frame';
 $('releaseRead').textContent=(partial?'Trigger F '+displayFrame(chargeTiming().trigger):'Armed F '+displayFrame(controls().armed))+' · release F '+displayFrame(releaseTime()*60)+' · left hand';syncPercent();
}
function syncHand(){
 const f=Math.min(time,clip.duration)*60,c=controls(),a=V.anglesAt(c.keys,f),key=c.keys.find(k=>Math.abs(k.frame-f)<1e-7);
 if(document.activeElement!==$('keyFrame'))$('keyFrame').value=String(Math.round(f));$('keyFrame').max=clip.duration*60;
 ['X','Y','Z'].forEach((axis,i)=>{if(document.activeElement!==$('hand'+axis))$('hand'+axis).value=Number(a[i].toFixed(4));});
 $('handKeyRead').textContent=key?'Key at F '+displayFrame(key.frame):'Interpolated pose · F '+displayFrame(f);$('deleteHandKey').disabled=!key;
 $('handKeys').value=key?String(key.frame):'';
}
function syncSmallThrowVelocity(){const v=controls().speedScale;$('smallThrowVelocity').max=Math.max(5,Math.ceil(v));$('smallThrowVelocity').value=v;$('smallThrowVelocityRead').textContent=v.toFixed(2)+'x';}
function syncVanilla(){syncSmallThrowVelocity();syncAero();syncPercent();const c=controls();$('halfAttack').checked=c.halfAttack;$('aimAtTarget').checked=c.aimAtTarget;$('handKeys').replaceChildren(new Option(c.keys.length?'Jump to key…':'No rotation keys',''),...c.keys.map(k=>new Option('F '+displayFrame(k.frame),String(k.frame))));['X','Y','Z'].forEach((axis,i)=>$('velocity'+axis).value=Number(c.velocityRotation[i].toFixed(4)));$('speedScale').value=c.speedScale;$('autoTwist').checked=c.twist===null;syncHand();syncLaunchRead();}
function alignLaunchToSpear(){
 if(settings.object!=='sword'||gizmos?.active)return;
 const seed=projectiles.preview(projectileOptions()),c=controls(),pose=presetPose(authoredReleaseTime()),axis=R.rotate(R.qinv(attackPlan()?.rotation||[0,0,0,1]),seed.axis),angles=V.alignVelocity(seed.authoredVelocity,pose.q[0],axis,c.velocityRotation);
 if(!angles)return;setPlaying(false);
 if(Math.abs(R.dot(V.rotation(angles),V.rotation(c.velocityRotation)))>1-1e-12)return;
 c.velocityRotation=angles;syncVanilla();drawAll();save();
}
function syncAero(){
 const a=controls().aero;$('aeroEnabled').checked=a.enabled;
 for(const [id,value] of [['aeroStrength',a.strength],['aeroPressure',a.pressure*100],['aeroDamping',a.damping]])if(document.activeElement!==$(id))$(id).value=Number(value.toFixed(4));
}
function syncLaunchRead(){if(!projectiles)return;const plan=attackPlan();$('aimRead').textContent=controls().aimAtTarget?(plan?.valid?(settings.object==='sword'?'At Throw, the spear points directly at the target. Gravity still applies.':'Aim uses the spine_05 → target direction at Throw. Gravity still applies.'):(settings.object==='sword'?'Place the target away from the held weapon.':'Aim needs a nonzero launch velocity and a target away from the chest.')):'Aim off · your launch presets are used.';const seed=projectiles.preview(projectileOptions()),c=controls();$('alignVelocity').disabled=settings.object!=='sword'||norm(seed.authoredVelocity)<1e-8;$('aeroEnabled').disabled=settings.object!=='sword';for(const id of ['aeroStrength','aeroPressure','aeroDamping'])$(id).disabled=settings.object!=='sword'||!c.aero.enabled;if(document.activeElement!==$('twist'))$('twist').value=Number(seed.twist.toFixed(4));$('launchRead').textContent='Speed '+(norm(seed.v)/60).toFixed(3)+' m / frame · '+(c.twist===null?'animation twist':'custom twist');}
function syncTrim(){const [a,b]=trim();for(const [id,v] of [['trimIn',a],['trimOut',b]]){$(id).style.left=(100*v/total())+'%';$(id).dataset.time='F '+Math.round(v*60);} $('trimSelection').style.left=(100*a/total())+'%';$('trimSelection').style.width=(100*(b-a)/total())+'%';}
function resetCamera(){Object.assign(cameraState,structuredClone(cameraDefault));$('freeCamera').checked=false;drawAll();save();}
class ThrowRenderer extends WebGLMotionRenderer{
 bindCamera(){const c=this.canvas;c.addEventListener('contextmenu',e=>e.preventDefault());
 c.addEventListener('pointerdown',e=>{if(e.button===2)history?.begin();this.drag={x:e.clientX,y:e.clientY,button:e.button};c.setPointerCapture(e.pointerId);});
 c.addEventListener('pointermove',e=>{if(!this.drag)return;const dx=e.clientX-this.drag.x,dy=e.clientY-this.drag.y;this.drag.x=e.clientX;this.drag.y=e.clientY;
  if(this.drag.button===2){const v=this.viewCamera,scale=Math.max(.3,dot(sub(settings.target,v.eye),v.forward))/v.focalCss;settings.target=add(settings.target,e.shiftKey?mul(v.forward,-dy*scale):add(mul(v.right,dx*scale),mul(v.up,-dy*scale)));syncTarget();}
  else if(this.drag.button===1)BodyflipCamera.pan(cameraState,this.viewCamera,dx,dy);else {const precision=gizmos?.leftControl&&e.ctrlKey ? .3 : 1;BodyflipCamera.rotate(cameraState,dx*precision,dy*precision);}drawAll();});
 const end=()=>{if(this.drag?.button===2){save();history?.end();}this.drag=null;save();};c.addEventListener('pointerup',end);c.addEventListener('pointercancel',end);c.addEventListener('lostpointercapture',end);
 c.addEventListener('wheel',e=>{e.preventDefault();BodyflipCamera.wheel(cameraState,e.deltaY);drawAll();save();},{passive:false});c.addEventListener('dblclick',resetCamera);
 }
 draw(data,root){super.draw(data,root);const gl=this.gl,mesh=this.extras||(this.extras=new LabVertexStream(16000)),lines=this.extraLines||(this.extraLines=new LabVertexStream(3000));mesh.length=lines.length=0;
 const t=settings.target,r=settings.radius,col=[1,.38,.66];this.capsule(mesh,t,t,r,col,20,6);
 for(const axes of [[[1,0,0],[0,1,0]],[[0,0,1],[0,1,0]]]){let prev=null;for(let n=0;n<=64;n++){const a=n*Math.PI/32,p=add(t,add(mul(axes[0],Math.cos(a)*r*1.25),mul(axes[1],Math.sin(a)*r*1.25)));if(prev)this.line(lines,prev,p,col);prev=p;}}
 this.line(lines,t,[t[0],0,t[2]],[.5,.27,.4]);this.groundRing(mesh,[t[0],.012,t[2]],.08,.11,col);this.drawObject(mesh);this.bindAndDraw(this.meshBuffer,mesh,gl.TRIANGLES);this.bindAndDraw(this.lineBuffer,lines,gl.LINES);
 }
 drawObject(mesh){
  const asset=objectAssets[weaponKind()];this.objectCaches||={};let cache=this.objectCaches[weaponKind()];
  if(!cache){const normals=[];for(let i=0;i<asset.triangles.length;i+=3){const [a,b,c]=asset.triangles.slice(i,i+3).map(j=>asset.vertices[j]);normals.push(normalize(cross(sub(b,a),sub(c,a))));}cache=this.objectCaches[weaponKind()]={normals,world:new Float32Array(asset.vertices.length*3)};}
  const axes=R.toAxes(objectPose.q),p=objectPose.p,w=cache.world,scale=weaponScale();
  for(let i=0;i<asset.vertices.length;i++){const v=asset.vertices[i];for(let k=0;k<3;k++)w[i*3+k]=p[k]+axes[0][k]*v[0]*scale[0]+axes[1][k]*v[1]*scale[1]+axes[2][k]*v[2]*scale[2];}
  for(let i=0;i<asset.triangles.length;i+=3){const n=R.rotate(objectPose.q,normalize(cache.normals[i/3].map((v,k)=>v/scale[k]))),c=asset.colors[i/3];for(let k=0;k<3;k++){const j=asset.triangles[i+k]*3;mesh.push(w[j],w[j+1],w[j+2],...n,...c);}}
 }
}
async function changeScene(action){
 const current=scenes.items.find(s=>s.id===scenes.active),name=action==='select'?null:prompt('Scene name',action==='new'?'Throws '+(scenes.items.length+1):action==='copy'?current.name+' copy':current.name);
 if(action!=='select'&&(name===null||!name.trim()))return;
 stored();let next=action==='select'?ThrowScenes.select(scenes,$('scene').value):action==='copy'?ThrowScenes.copy(scenes,name,crypto.randomUUID()):action==='rename'?ThrowScenes.rename(scenes,name):ThrowScenes.create(scenes,name,crypto.randomUUID(),{settings:C.sanitize(),camera:cameraDefault,playback:{time:0,playing:false}});
 reloading=true;setPlaying(false);clearTimeout(saveTimer);try{await persist(ThrowScenes.pack(next));location.reload();}catch(e){reloading=false;throw e;}
}
function bind(){
 $('wholeFrame').onclick=()=>{setPlaying(false);seek(Math.round(time*60)/60);save();};
 $('resetRotation').onclick=resetRotation;
 $('undoEdit').onclick=()=>undoEdit();$('redoEdit').onclick=()=>undoEdit(true);
 // One entry per numeric edit or slider/trim gesture. Navigation never enters
 // history because it does not change settings.
 for(const el of document.querySelectorAll('input[type=number]')){el.addEventListener('focus',()=>history?.begin());el.addEventListener('blur',()=>history?.end());}
 for(const el of [$('throwPercent'),$('slowdownBlend'),$('smallThrowVelocity'),$('roomBrightness'),$('playbackSpeed'),$('trimIn'),$('trimOut')]){el.addEventListener('pointerdown',()=>history?.begin(),true);for(const event of ['pointerup','pointercancel','lostpointercapture'])el.addEventListener(event,()=>history?.end());}
 $('play').onclick=()=>{setPlaying(!playing);save();};$('reset').onclick=()=>{setPlaying(false);seek(trim()[0]);save();};$('stepBack').onclick=()=>step(-1);$('stepForward').onclick=()=>step(1);$('refresh').onclick=refresh;
 $('clip').onchange=()=>{setPlaying(false);C.selectClip(settings,$('clip').value);clip=clips.find(c=>c.id===settings.clip);time=clamp(time,0,total());sync();drawAll();save();};
 for(const id of ['halfAttack','aimAtTarget'])$(id).onchange=()=>{controls()[id]=$(id).checked;drawAll();save();};
 $('object').onchange=()=>{C.selectObject(settings,$('object').value);drawAll();save();};
 const releaseAt=value=>{settings.releases[clip.id]=clamp(value,0,clip.duration);controls().armed=Math.min(controls().armed,Math.floor(authoredReleaseTime()*60));syncRelease();drawAll();save();};
 $('releaseFrame').onchange=()=>{const v=+$('releaseFrame').value;if(Number.isFinite(v))releaseAt(v/60);};$('releaseHere').onclick=()=>releaseAt(time);
 $('scrub').oninput=()=>{const frame=Math.round(+$('scrub').value);setPlaying(false);seek(frame/60);save();};
 const update=()=>{drawAll();save();},go=f=>{setPlaying(false);seek(f/60);save();};
 const arm=f=>{controls().armed=clamp(Math.round(f),0,Math.floor(authoredReleaseTime()*60));syncRelease();drawAll();save();};
 $('armedFrame').onchange=()=>{if($('armedFrame').value!==''&&Number.isFinite(+$('armedFrame').value))arm(+$('armedFrame').value);};$('armedHere').onclick=()=>arm(time*60);
 $('goArmed').onclick=()=>go(chargeTiming().trigger);$('goThrow').onclick=()=>go(releaseTime()*60);
 $('keyFrame').onchange=()=>{const f=+$('keyFrame').value;if(Number.isFinite(f))go(clamp(Math.round(f),0,Math.round(clip.duration*60)));};
 const putKey=writeHandKey;
 ['X','Y','Z'].forEach((axis,i)=>{$('hand'+axis).onfocus=()=>{editWholeFrame();};$('hand'+axis).onchange=()=>{const input=$('hand'+axis),v=+input.value;if(input.value===''||!Number.isFinite(v))return;editWholeFrame();const a=V.anglesAt(controls().keys,Math.min(time,clip.duration)*60);a[i]=v;putKey(a);};$('velocity'+axis).onchange=()=>{const input=$('velocity'+axis),v=+input.value;if(input.value!==''&&Number.isFinite(v)){controls().velocityRotation[i]=v;update();}};});
 $('setHandKey').onclick=()=>{editWholeFrame();putKey(V.anglesAt(controls().keys,Math.round(time*60)));};
 $('deleteHandKey').onclick=()=>{editWholeFrame();const c=controls(),f=Math.min(time,clip.duration)*60;c.keys=c.keys.filter(k=>Math.abs(k.frame-f)>1e-7);syncVanilla();update();};
 $('handKeys').onchange=()=>{if($('handKeys').value!=='')go(+$('handKeys').value);};
 $('speedScale').onchange=()=>{const v=+$('speedScale').value;if(Number.isFinite(v)){controls().speedScale=Math.max(0,v);$('speedScale').value=controls().speedScale;syncSmallThrowVelocity();update();}};
 $('twist').oninput=$('twist').onchange=()=>{const input=$('twist'),v=+input.value;if(input.value!==''&&Number.isFinite(v)){controls().twist=v;$('autoTwist').checked=false;update();}};
 $('autoTwist').onchange=()=>{controls().twist=$('autoTwist').checked?null:projectiles.preview(projectileOptions()).twist;update();};
 $('alignVelocity').onclick=alignLaunchToSpear;
 $('aeroEnabled').onchange=()=>{controls().aero.enabled=$('aeroEnabled').checked;update();};
 for(const [id,key,max,scale] of [['aeroStrength','strength',10,1],['aeroPressure','pressure',.5,.01],['aeroDamping','damping',10,1]])$(id).onchange=()=>{const value=+$(id).value;if($(id).value===''||!Number.isFinite(value))return;controls().aero[key]=clamp(value*scale,0,max);$(id).value=controls().aero[key]/scale;update();};
 $('resetLaunch').onclick=()=>{Object.assign(controls(),{velocityRotation:[0,0,0],speedScale:1,twist:null});syncVanilla();update();};
 for(const k of ['bicolor','skeleton','trimLoop','handGizmo','forearmGizmo','velocityGizmo','imperialSpear','weaponGizmo','scaleGizmo'])$(k).onchange=()=>{settings[k]=$(k).checked;if(C.gizmoKeys.includes(k)&&settings[k])settings.gizmosHidden=false;if(C.gizmoKeys.includes(k)&&settings[k])for(const other of C.gizmoKeys){settings[other]=other===k;$(other).checked=settings[other];}drawAll();save();};
 $('smallThrowVelocity').oninput=()=>{controls().speedScale=+$('smallThrowVelocity').value;$('speedScale').value=controls().speedScale;syncSmallThrowVelocity();drawAll();save();};
 $('slowdownBlend').oninput=()=>{controls().slowdownBlend=clamp(+$('slowdownBlend').value,0,1);syncRelease();drawAll();save();};
 $('throwPercent').oninput=()=>{controls().throwPercent=clamp(+$('throwPercent').value,0,100);syncRelease();drawAll();save();};
 $('roomBrightness').oninput=()=>{settings.roomBrightness=clamp(+$('roomBrightness').value,0,100);$('roomBrightnessRead').textContent=Math.round(settings.roomBrightness)+'%';drawAll();save();};
 $('playbackSpeed').oninput=()=>{settings.playbackSpeed=clamp(+$('playbackSpeed').value||1,.1,1);$('playbackSpeedRead').textContent=settings.playbackSpeed.toFixed(1)+'×';save();};
 ['X','Y','Z'].forEach((a,i)=>$('target'+a).oninput=()=>{if($('target'+a).value!==''&&Number.isFinite(+$('target'+a).value)){settings.target[i]=+$('target'+a).value;drawAll();save();}});
 $('radius').onchange=()=>{settings.radius=clamp(+$('radius').value||.16,.04,1);syncTarget();drawAll();save();};$('resetTarget').onclick=()=>{settings.target=C.defaults.target.slice();syncTarget();drawAll();save();};
 $('cameraReset').onclick=resetCamera;for(const [id,yaw,pitch] of [['cameraFront',0,0],['cameraSide',Math.PI/2,0],['cameraTop',0,-8]])$(id).onclick=()=>{Object.assign(cameraState,{free:false,freeView:null,yaw,pitch,panX:0,panY:0});$('freeCamera').checked=false;drawAll();save();};
 $('freeCamera').onchange=()=>{BodyflipCamera.toggle(cameraState,$('freeCamera').checked,renderer.viewCamera,worldAnchor);drawAll();save();};
 for(const [id,i] of [['trimIn',0],['trimOut',1]]){const el=$(id);let dragging=false;const move=e=>{if(!dragging)return;const rect=$('scrub').getBoundingClientRect(),v=Math.round(clamp((e.clientX-rect.left)/rect.width,0,1)*total()*60)/60,pair=trim();pair[i]=i?clamp(v,pair[0]+1/60,total()):clamp(v,0,pair[1]-1/60);settings.trims[clip.id]=pair;settings.trimLoop=true;$('trimLoop').checked=true;setPlaying(false);seek(pair[i]);syncTrim();save();};el.onpointerdown=e=>{dragging=true;el.setPointerCapture(e.pointerId);move(e);};el.onpointermove=move;el.onpointerup=el.onpointercancel=()=>dragging=false;}
 $('scene').onchange=()=>changeScene('select').catch(fail);for(const action of ['new','copy','rename'])$(action+'Scene').onclick=()=>changeScene(action).catch(fail);
 $('snapshot').onclick=async()=>{try{drawAll();const r=await post('/snapshot',{...snapshot(),source:{name:clip.name,sha256:clip.sha256},image:$('viewport').toDataURL('image/png')});$('toast').textContent='Saved snapshot '+r.name;$('toast').hidden=false;setTimeout(()=>$('toast').hidden=true,2500);}catch(e){fail(e);}};
 const writing=e=>e.target.isContentEditable||/INPUT|SELECT|TEXTAREA/.test(e.target.tagName)&&e.target.type!=='range'&&e.target.type!=='checkbox';
 window.addEventListener('keydown',e=>{if(gizmos?.active){e.preventDefault();e.stopImmediatePropagation();}},true);
 window.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&!e.altKey&&e.key?.toLowerCase()==='z'&&$('vanillaTab').getAttribute('aria-selected')==='true'&&!$('vanillaPanel').hidden){e.preventDefault();e.stopImmediatePropagation();if(!e.repeat)undoEdit(e.shiftKey);}},true);
 window.addEventListener('keydown',e=>{if(writing(e)||e.ctrlKey||e.metaKey||e.altKey)return;if(e.key?.toLowerCase()==='s'&&!e.shiftKey&&$('vanillaTab').getAttribute('aria-selected')==='true'&&!$('vanillaPanel').hidden){e.preventDefault();keys.delete('s');if(!e.repeat){settings.gizmosHidden=!settings.gizmosHidden;drawAll();save();}return;}if(e.key?.toLowerCase()==='l'&&$('vanillaTab').getAttribute('aria-selected')==='true'&&!$('vanillaPanel').hidden){e.preventDefault();if(!e.repeat){settings.handGizmoSpace=settings.handGizmoSpace==='world'?'local':'world';drawAll();save();}return;}if(e.key?.toLowerCase()==='a'||(e.key?.toLowerCase()==='d'&&!e.shiftKey)){e.preventDefault();keys.clear();step(e.key.toLowerCase()==='a'?-1:1);return;}if(cameraState.free&&['q','z','s','d'].includes(e.key.toLowerCase())){e.preventDefault();keys.add(e.key.toLowerCase());schedule();return;}if(['Space','ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.code))e.preventDefault();if(e.code==='Space'&&!e.repeat){setPlaying(!playing);save();}if(e.code==='ArrowLeft'||e.code==='ArrowRight')step(e.code==='ArrowLeft'?-1:1);if(e.code==='KeyR')$('reset').click();},true);
 window.addEventListener('keyup',e=>{keys.delete(e.key.toLowerCase());if(cameraState.free)save();});window.addEventListener('blur',()=>keys.clear());
 document.addEventListener('visibilitychange',()=>{if(document.hidden){setPlaying(false);keys.clear();if(raf!==null)cancelAnimationFrame(raf);raf=null;save();}});
 window.addEventListener('pagehide',()=>{if(scenes&&!reloading)navigator.sendBeacon('/state',new Blob([JSON.stringify(stored())],{type:'application/json'}));});
}
async function init(){const [data,loaded,assets,repairs]=await Promise.all([fetch('data/clips.json').then(r=>r.json()),fetch('/state').then(r=>r.json()),fetch('data/objects.json').then(r=>r.json()),fetch('state-repairs.json').then(r=>r.status===404?[]:r.json())]);const repaired=ThrowHistory.repairState(loaded,repairs),s=repaired.state;repairReceipts=s.repairs||[];names=data.names;parents=data.parents;nameToIndex=new Map(names.map((n,i)=>[n,i]));clips=data.clips.map(c=>C.decode(c,parents));scenes=ThrowScenes.open(s);settings=C.sanitize(s.settings);clip=clips.find(c=>c.id===settings.clip)||clips[0];settings.clip=clip.id;time=clamp(Number(s.playback?.time)||0,0,total());BodyflipCamera.restore(cameraState,s.camera,cameraDefault);
 objectAssets=assets;const {createProjectileSystem}=await import('./projectile.js');projectiles=await createProjectileSystem(assets);
 $('clip').replaceChildren(...clips.map(c=>new Option(c.name,c.id)));renderer=new ThrowRenderer($('viewport'),{pixelRatio:Math.min(devicePixelRatio,1.5)});
 gizmos=new ThrowGizmos($('gizmoOverlay'),{begin(kind){document.activeElement?.blur();keys.clear();if(kind==='hand'||kind==='forearm')editWholeFrame();else setPlaying(false);history?.begin();},change(kind,angles){if(kind==='hand')writeHandKey(angles);else if(kind==='forearm')writeForearmKey(angles);else if(kind==='scale')setWeaponScale(angles);else if(kind==='weapon'||kind==='move'){grip()[kind==='move'?'position':'rotation']=angles;drawAll();save();}else{controls().velocityRotation=angles;syncVanilla();drawAll();save();}},end(){history?.end();drawAll();save();}});
 bind();sync();history=new ThrowHistory.History(settings,s.history);syncHistoryUI();drawAll();if(s.playback?.playing&&!document.hidden)setPlaying(true);if(repaired.changed)await persist(stored());
 window.ThrowLab={get state(){return {...snapshot(),pose:currentPose,object:structuredClone(objectPose),weaponKind:weaponKind(),heldObject:structuredClone(projectiles.held(projectileOptions())),launch:structuredClone(projectiles.preview(projectileOptions())),physics:projectiles.diagnostics,cameraView:structuredClone(renderer.viewCamera),errors:errors.slice(),frames:clip.frames.length,duration:total(),clipDuration:clip.duration,releaseTime:releaseTime()};},seek,step,setPlaying,refresh};
}
init().catch(fail);
