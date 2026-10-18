// Snapshot list, restore, refresh and desktop publishing adapted from D/S app.js.
const desktopToken=new URLSearchParams(location.search).get('desktopSession');
const clientId=sessionStorage.reachClientId||(sessionStorage.reachClientId=crypto.randomUUID());
let sequence=Number(sessionStorage.reachSequence)||0,liveBusy=false,refreshing=false,workspaceReady=false;
let frameCapture=null,saveChain=Promise.resolve();
const motionReferences=new WeakMap();
const runtimeErrors=[];
function showError(e){message(e.message||String(e));}
window.addEventListener('error',e=>runtimeErrors.push(e.message));
window.addEventListener('unhandledrejection',e=>runtimeErrors.push(String(e.reason)));
async function getJSON(url){const r=await fetch(url);const v=await r.json();if(!r.ok)throw Error(v.error||r.status);return v;}
function saveSettings(){if(!desktopToken)return Promise.resolve();const saved=copy(settings);saveChain=saveChain.catch(()=>{}).then(()=>post('/state',saved));return saveChain;}
async function settled(){while(pending)await new Promise(r=>setTimeout(r,10));}
function setPlaying(value){playing=!!value;$('play').textContent=playing?'Pause':'Play';accum=0;}
function capturePNG(data,preview=false,camera=cameraState){
 frameCapture||=new LabFrameCapture(canvas,{names,parents});
 return frameCapture.png({pose:data,camera:copy(camera),rect:{width:renderer.rect.width,height:renderer.rect.height},pixelRatio:preview?Math.min(renderer.pixelRatio,640/Math.max(renderer.rect.width,renderer.rect.height)):renderer.pixelRatio});
}
async function fingerprint(value){const b=new TextEncoder().encode(JSON.stringify(value));return [...new Uint8Array(await crypto.subtle.digest('SHA-256',b))].map(x=>x.toString(16).padStart(2,'0')).join('');}
async function compactLiveState(saved){
 if(!saved.motion)return saved;
 const motion=saved.motion;
 let request=motionReferences.get(motion);
 if(!request){request=post('/motion',motion);motionReferences.set(motion,request);request.catch(()=>motionReferences.delete(motion));}
 const {id}=await request;
 const {motion:unused,...state}=saved;return {...state,motionRef:{id,startTick:motion.startTick}};
}
async function snapshotList(){const list=await getJSON('/snapshots');$('capture').textContent='Snapshot ('+list.length+')';$('snapshots').replaceChildren(new Option('Restore snapshot…',''),...list.map(n=>new Option(n.startsWith('snapshot_')?'#'+n.split('_')[1]:n,n)));}
async function saveSnapshot(){
 if(!desktopToken)throw Error('Open the desktop shortcut to save snapshots.');
 drawAll();const saved=snapshot(),data=copy(renderData());
 const image=await capturePNG(data);const r=await post('/snapshot',{...saved,displayedPose:data,image});
 await snapshotList();message('Saved '+r.name+' · PNG + exact pose and settings.');return r;
}
const vector=(v,n)=>Array.isArray(v)&&v.length===n&&v.every(Number.isFinite);
const validPose=p=>Array.isArray(p)&&p.length===26&&p.every(b=>vector(b,7));
function validateCheckpoint(s){
 if(!s||!s.settings||(!s.app&&s.schema!==1)||(s.app&&s.app!=='reach-lab'))throw Error('Not a REACH snapshot.');
 if(s.fingerSource&&s.fingerSource!==fingerData.poseSha256)throw Error('Snapshot uses a different finger pose export.');
 if(s.sourceSha256!==dataset.sourceSha256)throw Error('Snapshot uses a different source skeleton.');
 if(!validPose(s.pose)||!vector(s.solverState,20)||!Number.isInteger(s.tick)||s.tick<0)throw Error('Invalid saved pose or solver state.');
 if(s.basePose&&!validPose(s.basePose))throw Error('Invalid captured base pose.');
 if(s.motion){const m=s.motion;if(!Number.isInteger(m.startTick)||!Array.isArray(m.frames)||m.frames.length<2||m.frames.length>3600||m.frames.some(f=>!validPose(f.basePose)||!Array.isArray(f.targets)||f.targets.length!==2||f.targets.some(t=>!vector(t.center,3)||!vector(t.rotation,4)||!vector(t.normal,3))))throw Error('Invalid captured motion.');if(!m.initial||m.initial.motion)throw Error('Invalid motion start.');validateCheckpoint(m.initial);}
 if(s.handQ&&(!Array.isArray(s.handQ)||s.handQ.length!==2||!s.handQ.every(q=>vector(q,4))))throw Error('Invalid hand rotations.');
 if(s.returns&&(!Array.isArray(s.returns)||s.returns.length!==2||s.returns.some(r=>r&&(!validPose(r.from)||!Number.isFinite(r.tick)))))throw Error('Invalid arm return.');
 if(s.grabs&&(!Array.isArray(s.grabs)||s.grabs.length!==2||s.grabs.some(g=>g&&(!vector(g.curl,15)||!vector(g.ball,7)||!Number.isFinite(g.close)||(g.active&&(!vector(g.palm,3)||!vector(g.normal,3)||!vector(g.rotation,4)||!Number.isFinite(g.radius)))||(g.gripped&&!vector(g.attachment,7))))))throw Error('Invalid grab state.');
 if(s.grabs?.some(g=>{const p=g?.armPlan;return [3,4,5].includes(p?.version)&&(typeof p.key!=='string'||!vector(p.target,3)||!vector(p.shoulder,3)||!vector(p.forearm,4)||!Number.isFinite(p.reserve)||p.reserve<0||p.reserve>100||!Number.isFinite(p.residual)||!Number.isFinite(p.cos)||Math.abs(p.cos)>1||!Number.isInteger(p.evaluations)||p.evaluations<1||p.evaluations>14||(p.version===5&&(!vector(p.wrist,3)||!vector(p.rotation,4)||typeof p.jointKey!=='string')));}))throw Error('Invalid saved arm planning state.');
 if(s.grabs?.some(g=>{const c=g?.coupled;return c&&((c.guiding!==undefined&&typeof c.guiding!=='boolean')||(c.stalled!==undefined&&(!Number.isInteger(c.stalled)||c.stalled<0||c.stalled>6)));}))throw Error('Invalid saved arm guidance state.');
 if(s.wholeReturn&&(!validPose(s.wholeReturn.from)||!Number.isFinite(s.wholeReturn.tick)))throw Error('Invalid body return.');
 if(!s.phat?.wrists||s.phat.wrists.length!==2||s.phat.wrists.some(w=>!vector(w.frame1,4)||!vector(w.frame2,4)||!vector(w.modes,3)||!vector(w.limits,3)))throw Error('Invalid wrist limits.');
}
async function restoreSnapshot(s,{resume=false,save=true,restoreSettings=true}={}){
 validateCheckpoint(s);const wasRefreshing=refreshing;refreshing=true;setPlaying(false);revision++;await settled();while(liveBusy)await new Promise(r=>setTimeout(r,10));
 try{
 if(restoreSettings)settings=sanitize(s.settings);
 setBasePose(s.basePose||null);
 scenarioMotion=s.motion?copy(s.motion):null;
 pose=copy(s.pose);solverState=[...s.solverState];handQ=s.handQ?copy(s.handQ):hands.map(j=>pose[j].slice(3));
 grabs=s.grabs?copy(s.grabs):[null,null];
 returns=s.returns?copy(s.returns):[null,null];wholeReturn=s.wholeReturn?copy(s.wholeReturn):null;ticks=s.tick;phat=copy(s.phat);
 for(const k of Object.keys(cameraDefault))if(Number.isFinite(s.camera?.[k]))cameraState[k]=s.camera[k];
 const controls=s.controls||{};if([.25,.5,1].includes(controls.playSpeed))$('playSpeed').value=[...$('playSpeed').options].find(o=>Number(o.value)===controls.playSpeed).value;
 if(typeof controls.skeleton==='boolean')$('skeleton').checked=controls.skeleton;
 if(typeof controls.axes==='boolean')$('axes').checked=controls.axes;
 syncControls();setPlaying(resume&&s.playing);drawAll();
 if(save&&desktopToken){clearTimeout(saveTimer);await saveSettings();await saveSession();}
 }finally{refreshing=wasRefreshing;}
}
async function saveSession(){if(desktopToken)await post('/session',snapshot());}
async function restartCapturedScenario(){
 const motion=scenarioMotion,s=copy(motion.initial),current=copy(settings);
 const index=clamp(ticks-motion.startTick,0,motion.frames.length-1),frame=motion.frames[index];
 for(let k=0;k<2;k++){
  const h=current.hands[k],start=s.settings.hands[k],source=frame.targets[k];
  const offsetPosition=grabs[k]?.feedback?grabs[k].feedback.offset||[0,0,0]:sub(h.target,source.center);
  h.target=add(start.target,offsetPosition);
  const offset=R.qm(R.qinv(source.rotation),rotationQ(h.rotation));
  h.rotation=angle(offset,[0,0,0,1])<1e-6?copy(start.rotation):rotationDegrees(R.qm(motion.frames[0].targets[k].rotation,offset));
  s.grabs[k].ball=[...h.target,...s.grabs[k].ball.slice(3)];
  if(s.grabs[k].feedback){s.grabs[k].feedback.lastCenter=[...h.target];s.grabs[k].feedback.offset=[...offsetPosition];}
 }
 s.settings=current;s.camera=copy(cameraState);s.controls=snapshot().controls;s.motion=motion;
 await restoreSnapshot(s,{save:false});
}
async function refreshLab(){
 if(!desktopToken){location.reload();return;}
 refreshing=true;const wasPlaying=playing;setPlaying(false);
 try{await settled();while(liveBusy)await new Promise(r=>setTimeout(r,10));clearTimeout(saveTimer);await saveSettings();const saved=snapshot();saved.playing=wasPlaying;await post('/session',saved);location.reload();}
 catch(e){refreshing=false;setPlaying(wasPlaying);showError(e);}
}
async function publishLive(){
 if(!desktopToken||!workspaceReady||liveBusy||refreshing||drag)return;
 liveBusy=true;
 try{const captured=snapshot(),data=copy(renderData()),capturedAt=new Date().toISOString();
  const saved=await compactLiveState(captured),packet={...saved,state:saved,displayedPose:data,runtimeErrors:[...runtimeErrors],capturedAt,clientId};
  const [key,image]=await Promise.all([fingerprint(packet),capturePNG(data,captured.playing,captured.camera)]);
  const result=await post('/desktop-view',{...packet,fingerprint:key,sequence:++sequence,image});sessionStorage.reachSequence=sequence;
  $('sharing').textContent=result.stale?'Waiting for current view…':'Live view shared · '+clientId.slice(0,8);
 }catch(e){$('sharing').textContent='Live view: '+e.message;}finally{liveBusy=false;}
}
async function initWorkspace(){
 const saved=await getJSON('/session');
 if(saved.settings){try{await restoreSnapshot(saved,{resume:true,save:false,restoreSettings:false});}catch(e){message('Previous session not restored: '+e.message);}}
 $('capture').onclick=()=>saveSnapshot().catch(showError);$('refresh').onclick=refreshLab;
 $('snapshots').onchange=async()=>{if(!$('snapshots').value)return;try{await restoreSnapshot(await getJSON('/snapshots/'+encodeURIComponent($('snapshots').value)+'.json'));message('Snapshot restored · paused at tick '+ticks);}catch(e){showError(e);}};
 $('export').onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify(snapshot(),null,2)],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download='reach-lab-snapshot.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
 $('import').onclick=()=>$('importFile').click();$('importFile').onchange=async()=>{try{await restoreSnapshot(JSON.parse(await $('importFile').files[0].text()));message('REACH snapshot imported.');}catch(e){showError(e);}finally{$('importFile').value='';}};
 await snapshotList();workspaceReady=true;
 if(desktopToken){await saveSettings();setInterval(publishLive,1200);publishLive();}
 else{$('sharing').textContent='Inspection view · shared settings are read-only.';$('capture').disabled=true;}
 Object.assign(window.reachLab,{saveSnapshot,restore:restoreSnapshot,refresh:refreshLab,publishLive,errors:runtimeErrors});
}
load();
