// Short isolated headless smoke test. Never writes the user's saved lab settings.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),{spawn}=require('node:child_process');
const out=path.resolve(__dirname,'../../Saved/ThrowLab'),profile=path.join(out,'attack-profile'),sleep=ms=>new Promise(r=>setTimeout(r,ms));fs.mkdirSync(profile,{recursive:true});
const C=require('./core.js'),R=require('./recovery.js'),data=JSON.parse(fs.readFileSync(path.join(__dirname,'data/clips.json')));let maxError=0;
for(const raw of data.clips){const clip=C.decode(raw,data.parents);for(let i=0;i<raw.frames.length;i++){const pose=C.sample(clip,i/raw.fps,data.parents);for(let j=0;j<data.names.length;j++)for(let k=0;k<3;k++)maxError=Math.max(maxError,Math.abs(pose.points[j][k]-(raw.frames[i][j][k]-clip.offset[k])));}}assert(maxError<1e-8);
const receipt={sourceFrames:data.clips.map(c=>c.frames.length),keyframeErrorMetres:maxError,checks:[]};
const portFile=path.join(profile,'DevToolsActivePort');if(fs.existsSync(portFile))fs.unlinkSync(portFile);
const chrome=['C:/Program Files/Google/Chrome/Application/chrome.exe','C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'].find(fs.existsSync);
const browser=spawn(chrome,['--headless','--remote-debugging-port=0','--disable-background-networking','--disable-extensions','--no-first-run','--no-default-browser-check','--disable-component-update','--disable-sync','--enable-unsafe-swiftshader','--use-angle=swiftshader','--window-size=1280,900','--user-data-dir='+profile,'about:blank'],{windowsHide:true,stdio:'ignore'});
let socket,serial=0;const pending=new Map();
function send(method,params={}){return new Promise((resolve,reject)=>{const id=++serial;pending.set(id,{resolve,reject});socket.send(JSON.stringify({id,method,params}));});}
async function evaluate(expression){const r=await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value;}
async function ready(){for(let i=0;i<100;i++){if(await evaluate('!!window.ThrowLab'))return;await sleep(100);}throw Error('Lab did not initialize: '+await evaluate('document.body.innerText'));}
async function shot(name){const r=await send('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path.join(out,name+'.png'),Buffer.from(r.data,'base64'));}
(async()=>{try{
 for(let i=0;i<150&&!fs.existsSync(portFile);i++)await sleep(50);
 const port=fs.readFileSync(portFile,'utf8').split('\n')[0],targets=await(await fetch('http://127.0.0.1:'+port+'/json/list')).json();socket=new WebSocket(targets.find(t=>t.type==='page').webSocketDebuggerUrl);await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});
 socket.onmessage=e=>{const r=JSON.parse(e.data),p=pending.get(r.id);if(r.method==='Network.loadingFailed')console.error(JSON.stringify(r.params));if(r.method==='Runtime.exceptionThrown')console.error(JSON.stringify(r.params));if(p){pending.delete(r.id);r.error?p.reject(Error(JSON.stringify(r.error))):p.resolve(r.result);}};
 await send('Page.enable');await send('Runtime.enable');await send('Network.enable');await send('Emulation.setDeviceMetricsOverride',{width:1280,height:900,deviceScaleFactor:1,mobile:false});
 await send('Page.addScriptToEvaluateOnNewDocument',{source:`const originalFetch=fetch;window.fetch=(input,opts={})=>{const p=new URL(input,location.href).pathname;if(p==='/state'){if(opts.method==='POST')sessionStorage.setItem('qa-state',opts.body);return Promise.resolve(new Response(opts.method==='POST'?'{}':sessionStorage.getItem('qa-state')||'{}'));}return originalFetch(input,opts)};navigator.sendBeacon=()=>true;`});
 const approved=JSON.parse(fs.readFileSync(path.join(__dirname,'fixtures/attack-presets.json'))),tag=process.env.THROW_DYNAMICS_TAG,group=process.env.THROW_DYNAMICS_GROUP||'dynamics',original=path.join(out,group+'-before/state-snapshot.json'),seed=tag?JSON.parse(fs.readFileSync(tag==='after'&&fs.existsSync(original)?original:path.join(__dirname,'state.json'))):{settings:approved.settings,camera:approved.camera,playback:{time:0,playing:false}};seed.playback={time:0,playing:false};
 await send('Page.addScriptToEvaluateOnNewDocument',{source:"if(!sessionStorage.getItem('qa-state'))sessionStorage.setItem('qa-state',"+JSON.stringify(JSON.stringify(seed))+");"});
 await send('Page.navigate',{url:process.env.THROW_LAB_TEST_URL||'http://127.0.0.1:8893/throw-lab.html'});await ready();
 if(process.env.THROW_MOTION_AUDIT){
  await evaluate('(async()=>{(0,eval)(await (await fetch("motion-audit.js")).text())})()');
  const report=await evaluate('(()=>{const end=clip.duration*60,finish=chargeTiming().trigger+(forwardEndFrame()-controls().armed)/throwSpeed().multiplier,scan=sample=>{const r=ThrowMotionAudit.scan({sample,end,names});r.discontinuities=r.discontinuities.map(v=>{const f=v.frame,phase=chargeSourceFrame(f),sourceKey=Math.abs(f/2-Math.round(f/2))<.002,retimed=f>chargeTiming().trigger&&f<finish&&Math.abs(phase/2-Math.round(phase/2))<.002,userKey=[...controls().keys,...controls().forearmKeys].some(k=>Math.abs(k.frame-f)<.004);return {...v,origin:userKey?"user key":sourceKey?"source key":retimed?"retimed source key":"procedural"}});return r;};return {percent:controls().throwPercent,slowdown:controls().slowdownBlend,finish,before:scan(f=>motionPose(f/60,false)),after:scan(f=>authoredPose(f/60)),source:scan(f=>fullPose(f/60))}})()');
  fs.writeFileSync(path.join(out,'motion-audit-current.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));return;
 }
 if(tag){
  assert(['before','after'].includes(tag));assert(/^[a-z0-9-]+$/.test(group));const folder=path.join(out,group+'-'+tag);fs.mkdirSync(folder,{recursive:true});fs.writeFileSync(path.join(folder,'state-snapshot.json'),JSON.stringify(seed,null,2));
  await evaluate('setPlaying(false);settings.gizmosHidden=true;resetCamera();document.getElementById("cameraSide").click();');
  const trace=await evaluate('(()=>{const rows=[],basis=ThrowAttack.swingBasis(C.sample(clip,0,parents),C.sample(clip,authoredReleaseTime(),parents),attackRig||ThrowAttack.rig(names,parents));for(let f=0;f<=clip.duration*60;f+=.25){const pose=authoredPose(f/60);rows.push({frame:f,source:chargeSourceFrame(f),angle:ThrowAttack.swingAngle(ThrowAttack.armDirection(pose,attackRig),basis)*180/Math.PI,hand:pose.points[10],pelvis:pose.points[1],head:pose.points[17],headQ:pose.q[17],pelvisQ:pose.q[1]});}return {percent:controls().throwPercent,armed:controls().armed,trigger:chargeTiming().trigger,release:releaseTime()*60,rows}})()');
  fs.writeFileSync(path.join(folder,'trace.json'),JSON.stringify(trace));
  for(let f=0;f<=68;f+=2){await evaluate('ThrowLab.seek('+f+'/60)');const shot=await send('Page.captureScreenshot',{format:'png',clip:{x:950,y:270,width:300,height:470,scale:1}});fs.writeFileSync(path.join(folder,String(f/2).padStart(3,'0')+'.png'),Buffer.from(shot.data,'base64'));}
  console.log(JSON.stringify({dynamics:tag,percent:trace.percent,trigger:trace.trigger,folder}));return;
 }


 async function click(id){const p=await evaluate(`(()=>{const el=document.getElementById('${id}');el.scrollIntoView({block:'center'});const r=el.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()`);await send('Input.dispatchMouseEvent',{type:'mousePressed',...p,button:'left',clickCount:1});await send('Input.dispatchMouseEvent',{type:'mouseReleased',...p,button:'left',clickCount:1});}
 await evaluate('ThrowLab.seek(releaseTime())');const before=await evaluate('ThrowLab.state');
 assert.equal(before.settings.vanilla['big-throw'].halfAttack,false);assert.equal(before.settings.vanilla['big-throw'].aimAtTarget,false);
 await click('halfAttack');const half=await evaluate('ThrowLab.state');
 assert(R.length(R.sub(half.launch.v,before.launch.v))<1e-8);assert(Math.abs(R.dot(half.pose.q[17],before.pose.q[17]))>1-1e-10);
 assert(await evaluate('(()=>{const p=C.sample(clip,0,parents);return [0,1,18,19,20,21,22,23,24,25].every(j=>R.length(R.sub(currentPose.points[j],p.points[j]))<1e-10)})()'));
 await evaluate('undoEdit()');assert.deepEqual((await evaluate('ThrowLab.state')).settings,before.settings);assert.deepEqual((await evaluate('ThrowLab.state')).pose,before.pose);
 await click('aimAtTarget');const full=await evaluate('ThrowLab.state');
 const checkAim=async()=>{const result=await evaluate('(()=>{const s=ThrowLab.state,plan=attackPlan();return {error:R.length(R.sub(s.launch.axis,R.unit(R.sub(settings.target,s.launch.p)))),speed:R.length(s.launch.v),twist:s.launch.twist,yaw:plan.yaw,pitch:plan.pitch};})()');assert(result.error<1e-7);assert(Math.abs(result.speed-R.length(before.launch.v))<1e-8);assert.equal(result.twist,before.launch.twist);return result;};
 const fullAim=await checkAim();assert(await evaluate('R.length(R.sub(R.rotate(R.qm(currentPose.q[1],R.qinv(presetPose(time).q[1])),[0,1,0]),[0,1,0]))<1e-9'));
 await click('halfAttack');const halfAim=await checkAim();
 const beforeSnap=await evaluate('settings'),snapUndo=await evaluate('history.undoStack.length');await click('alignVelocity');assert(await evaluate('R.dot(R.unit(ThrowLab.state.launch.v),ThrowLab.state.launch.axis)>1-1e-9'));await checkAim();if(await evaluate('history.undoStack.length')>snapUndo)await evaluate('undoEdit()');assert.deepEqual(await evaluate('settings'),beforeSnap);
 const settings=await evaluate('settings');assert.deepEqual({...settings.vanilla['big-throw'],halfAttack:false,aimAtTarget:false},before.settings.vanilla['big-throw']);
 await evaluate('ThrowLab.seek(controls().armed/120)');assert.deepEqual(await evaluate('ThrowLab.state.errors'),[]);
 await evaluate('ThrowLab.seek(releaseTime());document.getElementById("targetX").value=3;document.getElementById("targetX").dispatchEvent(new Event("change"))');await checkAim();
 // Original speed and twist remain independent of the FK entry and target edits.
 const current=await evaluate('ThrowLab.state');await evaluate('ThrowLab.refresh()');await sleep(300);await ready();assert.deepEqual((await evaluate('ThrowLab.state')).settings,current.settings);assert.equal(await evaluate('document.getElementById("halfAttack").checked'),true);assert.equal(await evaluate('document.getElementById("aimAtTarget").checked'),true);await checkAim();
 await evaluate('document.getElementById("clip").value="small-throw";document.getElementById("clip").dispatchEvent(new Event("change"))');assert.equal(await evaluate('controls().aimAtTarget'),false);assert.equal(await evaluate('controls().halfAttack'),false);
 assert.equal(await evaluate('ThrowLab.state.weaponKind'),'bomb');assert.equal(await evaluate('document.getElementById("object").value'),'bomb');
 await evaluate('document.getElementById("object").value="sword";document.getElementById("object").dispatchEvent(new Event("change"))');
 assert.equal(await evaluate('ThrowLab.state.weaponKind'),'spear');await evaluate('undoEdit()');assert.equal(await evaluate('ThrowLab.state.weaponKind'),'bomb');
 const smallSettings=await evaluate('settings');await evaluate('ThrowLab.refresh()');await sleep(300);await ready();assert.deepEqual(await evaluate('settings'),smallSettings);assert.equal(await evaluate('ThrowLab.state.weaponKind'),'bomb');
 const cached=JSON.parse(fs.readFileSync(path.join(__dirname,'data/objects.json')));
 assert.deepEqual(await evaluate('objectAssets.spear.source'),cached.spear.source);assert.deepEqual(await evaluate('objectAssets.bomb.source'),cached.bomb.source);
 // Real Small Throw slider interaction; all mutations stay in isolated sessionStorage.
 assert.equal(await evaluate('document.getElementById("throwPercentSection").hidden'),false);
 assert.equal(await evaluate('controls().throwPercent'),100);
 await evaluate('controls().armed=18;settings.releases[clip.id]=34.25/60;controls().twist=7;sync();ThrowLab.seek(releaseTime());save()');
 const fullSmall=await evaluate('ThrowLab.state'),percentUndo=await evaluate('history.undoStack.length');
 await click('throwPercent');assert.equal(await evaluate('controls().throwPercent'),50);
 const halfSmall=await evaluate('ThrowLab.state');assert(Math.abs(R.length(halfSmall.launch.v)/R.length(fullSmall.launch.v)-.5)<1e-10);
 assert.equal(halfSmall.launch.twist,7);assert.equal(halfSmall.releaseTime,25.25/60);
 assert.equal(await evaluate('document.getElementById("releaseFrame").value'),'34.25');assert.equal(await evaluate('controls().armed'),18);
 assert.equal(await evaluate('history.undoStack.length'),percentUndo+1);
 const arc=await evaluate('(()=>{const peak=forwardEndFrame(),finish=chargeTiming().trigger+peak-controls().armed,basis=ThrowAttack.swingBasis(fullPose(0),fullPose(authoredReleaseTime()),attackRig),angle=p=>ThrowAttack.swingAngle(ThrowAttack.armDirection(p,attackRig),basis);return {full:angle(fullPose(peak/60)),half:angle(motionPose(finish/60)),finish}})()');assert(Math.abs(arc.half/arc.full-.5)<.001);assert(arc.half*180/Math.PI>40&&arc.half*180/Math.PI<55);
 const effort=await evaluate('(()=>{const initial=fullPose(0);let full=0,weak=0;for(let f=0;f<=clip.duration*60;f+=.25){full=Math.max(full,R.length(R.sub(fullPose(f/60).points[17],initial.points[17])));weak=Math.max(weak,R.length(R.sub(motionPose(f/60).points[17],initial.points[17])));}return {full,weak}})()');assert(effort.weak<effort.full*.9&&effort.weak>effort.full*.4);

 assert(R.length(R.sub(halfSmall.pose.points[10],fullSmall.pose.points[10]))>.01);
 await evaluate('undoEdit()');assert.deepEqual((await evaluate('ThrowLab.state')).pose,fullSmall.pose);assert.deepEqual((await evaluate('ThrowLab.state')).launch,fullSmall.launch);
 await evaluate('undoEdit(true)');assert.equal(await evaluate('controls().throwPercent'),50);
 await evaluate('ThrowLab.refresh()');await sleep(300);await ready();assert.equal(await evaluate('controls().throwPercent'),50);assert.equal(await evaluate('document.getElementById("throwPercentRead").textContent'),'50%');
 for(const half of [false,true])for(const kind of ['bomb','sword']){
  await evaluate(`controls().halfAttack=${half};controls().aimAtTarget=true;C.selectObject(settings,'${kind}');sync();ThrowLab.seek(releaseTime())`);
  const result=await evaluate('(()=>{const s=ThrowLab.state,base=projectiles.reference(baseProjectileOptions()),to=R.unit(R.sub(settings.target,settings.object==="sword"?s.launch.p:s.pose.points[6]));return {ratio:R.length(s.launch.v)/R.length(base.v),aimError:R.length(R.sub(settings.object==="sword"?s.launch.axis:R.unit(s.launch.v),to)),releaseError:R.length(R.sub(s.object.p,s.heldObject.p))}})()');
  assert(Math.abs(result.ratio-.5)<1e-10);assert(result.aimError<1e-7,JSON.stringify(result));assert(result.releaseError<1e-6);
  // No advance knowledge of charge: Aim/Half must share the exact full-strength prefix.
  const prefix=await evaluate('(()=>{let error=0;for(const percent of [25,50,75]){const trigger=18*percent/100;for(const f of [0,trigger/2,trigger]){controls().throwPercent=100;const full=authoredPose(f/60);controls().throwPercent=percent;const partial=authoredPose(f/60);for(let j=0;j<names.length;j++)error=Math.max(error,R.length(R.sub(partial.points[j],full.points[j])),1-Math.abs(R.dot(partial.q[j],full.q[j])));}}controls().throwPercent=50;return error})()');
  assert(prefix<1e-12,'Charge percentage changed the wind-up before trigger release: '+prefix);
  await evaluate('ThrowLab.seek((chargeTiming().trigger+1e-6)/60)');const afterCut=await evaluate('ThrowLab.state.pose');await evaluate('ThrowLab.seek(chargeTiming().trigger/60)');const atCut=await evaluate('ThrowLab.state.pose');assert(R.length(R.sub(afterCut.points[10],atCut.points[10]))<1e-5);
  await evaluate('ThrowLab.seek(releaseTime()-1e-7)');assert.equal(await evaluate('ThrowLab.state.object.phase'),'held');await evaluate('ThrowLab.seek(releaseTime())');assert.equal(await evaluate('ThrowLab.state.object.phase'),'released');
 }
 await evaluate('C.selectObject(settings,"bomb");controls().halfAttack=false;controls().aimAtTarget=false;document.getElementById("throwPercent").value=0;document.getElementById("throwPercent").dispatchEvent(new Event("input"));ThrowLab.seek(releaseTime())');
 assert.equal(await evaluate('R.length(ThrowLab.state.launch.v)'),0);
 await evaluate('document.getElementById("throwPercent").value=50;document.getElementById("throwPercent").dispatchEvent(new Event("input"));sync();settings.gizmosHidden=true;resetCamera();document.querySelector("aside").scrollTop=0;ThrowLab.seek(releaseTime())');await shot('small-throw-50-percent');
 await evaluate('ThrowLab.seek(20/60)');const elbowAt20=await evaluate('(()=>{const p=currentPose.points;return Math.acos(Math.max(-1,Math.min(1,R.dot(R.unit(R.sub(p[9],p[8])),R.unit(R.sub(p[10],p[9]))))))*180/Math.PI})()');const sourceElbowAt20=await evaluate('(()=>{const p=fullPose(chargeSourceFrame(20)/60).points;return Math.acos(Math.max(-1,Math.min(1,R.dot(R.unit(R.sub(p[9],p[8])),R.unit(R.sub(p[10],p[9]))))))*180/Math.PI})()');assert(Math.abs(elbowAt20-sourceElbowAt20)<1e-5);await click('cameraSide');await shot('small-throw-50-percent-frame20');await evaluate('ThrowLab.seek((chargeTiming().trigger+forwardEndFrame()-controls().armed)/60)');await shot('small-throw-50-percent-arc');
 // Regression for the user's18% palm pose: compare the entire arm orientation,
 // not just the wrist's parent-local quaternion or the hand's position.
 const palm=await evaluate('(()=>{let error=0,samples=0;for(const percent of [5,18,50,75,99]){controls().throwPercent=percent;const t=chargeTiming(),finish=t.trigger+forwardEndFrame()-controls().armed;for(let f=t.trigger+4;f<=finish;f+=.5){const pose=motionPose(f/60),source=fullPose(chargeSourceFrame(f)/60);for(const j of [8,9,10])error=Math.max(error,1-Math.abs(R.dot(pose.q[j],source.q[j])));samples++;}}controls().throwPercent=18;sync();resetCamera();Object.assign(cameraState,{yaw:0,pitch:0,zoom:1.4,panX:0,panY:0});ThrowLab.seek(26/60);return {error,samples}})()');assert(palm.error<1e-10);await shot('small-throw-18-percent-palm');
 await evaluate('ThrowLab.seek((chargeTiming().trigger+forwardEndFrame()-controls().armed)/60)');await shot('small-throw-18-percent-source-pose');
 await evaluate('const originalFrame=chargeSourceFrame(time*60);controls().throwPercent=100;sync();ThrowLab.seek(originalFrame/60)');await shot('small-throw-native-palm-reference');
 const fiveBody=await evaluate('(()=>{controls().throwPercent=5;controls().armed=18;settings.releases[clip.id]=34/60;controls().halfAttack=false;controls().aimAtTarget=false;sync();const initial=fullPose(0);let head=0,chest=0,pelvis=0,frame=0;for(let f=0;f<=clip.duration*60;f+=.25){const p=authoredPose(f/60),h=R.length(R.sub(p.points[17],initial.points[17]));if(h>head){head=h;frame=f;}chest=Math.max(chest,R.length(R.sub(p.points[6],initial.points[6])));pelvis=Math.max(pelvis,R.length(R.qlog(R.qm(p.q[1],R.qinv(initial.q[1]))))*180/Math.PI);}ThrowLab.seek(frame/60);return {head,chest,pelvis,frame}})()');assert(fiveBody.head<.02);assert(fiveBody.chest<.015);assert(fiveBody.pelvis<1);await evaluate('resetCamera()');await click('cameraSide');await shot('small-throw-5-percent-body');
 const bodySmoothness=await evaluate('(()=>{const rows=[];for(const percent of [5,25,50,76,99]){controls().throwPercent=percent;const timing=chargeTiming(),body=partialBodyPlan();for(const f of [timing.trigger,timing.trigger+body.settle,body.returnStart,timing.trigger+forwardEndFrame()-controls().armed]){const h=.0001,a=authoredPose((f-h)/60),b=authoredPose(f/60),c=authoredPose((f+h)/60),v0=R.mul(R.sub(b.points[17],a.points[17]),60/h),v1=R.mul(R.sub(c.points[17],b.points[17]),60/h);rows.push({percent,frame:f,jump:R.length(R.sub(v1,v0)),sourceBoundary:Math.abs(f/2-Math.round(f/2))<1e-6});}}controls().throwPercent=76;sync();const start=performance.now();for(let i=0;i<60;i++)authoredPose((13+i*.5)/60);return {rows,poseMilliseconds:(performance.now()-start)/60}})()');assert(bodySmoothness.rows.every(r=>r.sourceBoundary||r.jump<.001));
 const forwardProgress=await evaluate('(()=>{controls().throwPercent=33;const t=chargeTiming(),span=forwardEndFrame()-controls().armed,start=chargeSourceFrame(t.trigger),end=chargeSourceFrame(t.trigger+span),basis=ThrowAttack.swingBasis(fullPose(0),fullPose(authoredReleaseTime()),attackRig),angle=f=>ThrowAttack.swingAngle(ThrowAttack.armDirection(motionPose(f/60),attackRig),basis)*180/Math.PI;return {firstTen:(chargeSourceFrame(t.trigger+10)-start)/(end-start),expected:10/span,angle10to16:angle(16)-angle(10)}})()');assert(Math.abs(forwardProgress.firstTen-forwardProgress.expected)<1e-9);assert(forwardProgress.angle10to16>8);
 // New control interpolates source speed, not strength or playback speed.
 await evaluate('controls().throwPercent=33;controls().slowdownBlend=0;controls().halfAttack=false;controls().aimAtTarget=false;C.selectObject(settings,"bomb");sync();ThrowLab.seek(releaseTime());save()');
 const slowBefore=await evaluate('({settings:structuredClone(settings),release:releaseTime(),speed:throwSpeed(),launch:ThrowLab.state.launch,source:chargeSourceFrame(releaseTime()*60),prefix:authoredPose(chargeTiming().trigger/120)})'),slowUndo=await evaluate('history.undoStack.length');
 await click('slowdownBlend');assert.equal(await evaluate('controls().slowdownBlend'),.5);assert.equal(await evaluate('history.undoStack.length'),slowUndo+1);
 const middle=await evaluate('({release:releaseTime(),speed:throwSpeed(),launch:ThrowLab.state.launch,source:chargeSourceFrame(releaseTime()*60),prefix:authoredPose(chargeTiming().trigger/120)})');
 assert(Math.abs(middle.speed.rate-(slowBefore.speed.rate+1)/2)<1e-12);assert(middle.release<slowBefore.release);assert.deepEqual(middle.prefix,slowBefore.prefix);assert(Math.abs(middle.source-slowBefore.source)<1e-9);assert(Math.abs(R.length(middle.launch.v)-R.length(slowBefore.launch.v))<1e-8);
 await evaluate('ThrowLab.refresh()');await sleep(300);await ready();assert.equal(await evaluate('controls().slowdownBlend'),.5);assert.equal(await evaluate('document.getElementById("slowdownBlendRead").textContent'),'0.50');
 await evaluate('undoEdit()');assert.equal(await evaluate('controls().slowdownBlend'),0);assert.deepEqual(await evaluate('settings'),slowBefore.settings);
 await evaluate('undoEdit(true)');assert.equal(await evaluate('controls().slowdownBlend'),.5);
 await evaluate('document.getElementById("slowdownBlend").value=1;document.getElementById("slowdownBlend").dispatchEvent(new Event("input"));ThrowLab.seek(releaseTime())');
 const noSlow=await evaluate('({release:releaseTime(),speed:throwSpeed(),launch:ThrowLab.state.launch,source:chargeSourceFrame(releaseTime()*60),prefix:authoredPose(chargeTiming().trigger/120)})');assert.equal(noSlow.speed.rate,1);assert(noSlow.release<middle.release);assert.deepEqual(noSlow.prefix,slowBefore.prefix);assert(Math.abs(noSlow.source-slowBefore.source)<1e-9);assert(Math.abs(R.length(noSlow.launch.v)-R.length(slowBefore.launch.v))<1e-8);
 assert.equal(await evaluate('ThrowLab.state.object.phase'),'released');await evaluate('ThrowLab.seek(releaseTime()-1e-7)');assert.equal(await evaluate('ThrowLab.state.object.phase'),'held');
 await evaluate('ThrowLab.seek(releaseTime());document.getElementById("slowdownBlend").scrollIntoView({block:"center"})');assert((await evaluate('document.getElementById("slowdownBlendHint").textContent')).endsWith('1.00x.'));await shot('slowdown-blend');
 for(const half of [false,true])for(const kind of ['bomb','sword']){
  await evaluate(`controls().halfAttack=${half};controls().aimAtTarget=true;C.selectObject(settings,'${kind}');sync();ThrowLab.seek(releaseTime())`);
  const error=await evaluate('(()=>{const s=ThrowLab.state,to=R.unit(R.sub(settings.target,settings.object==="sword"?s.launch.p:s.pose.points[6]));return R.length(R.sub(settings.object==="sword"?s.launch.axis:R.unit(s.launch.v),to))})()');assert(error<1e-7);
 }
 const slowdown={baselineRate:slowBefore.speed.rate,middleRate:middle.speed.rate,fullRate:noSlow.speed.rate,releaseFrames:[slowBefore.release*60,middle.release*60,noSlow.release*60]};

 // The left Small Throw slider shares the existing per-throw velocity amplitude.
 await evaluate('controls().halfAttack=false;controls().aimAtTarget=false;controls().speedScale=1;sync();drawAll();save()');
 const velocityBefore=await evaluate('structuredClone(settings)'),velocityUndo=await evaluate('history.undoStack.length');
 await click('smallThrowVelocity');assert.equal(await evaluate('controls().speedScale'),2.5);assert.equal(await evaluate('history.undoStack.length'),velocityUndo+1);
 assert.equal(await evaluate('document.getElementById("speedScale").value'),'2.5');
 await evaluate('ThrowLab.refresh()');await sleep(300);await ready();assert.equal(await evaluate('document.getElementById("smallThrowVelocityRead").textContent'),'2.50x');
 await evaluate('undoEdit()');assert.deepEqual(await evaluate('settings'),velocityBefore);await evaluate('undoEdit(true)');assert.equal(await evaluate('controls().speedScale'),2.5);
 const velocityMultiplier=await evaluate('(()=>{const rows=[];for(const percent of [0,5,43,100]){controls().throwPercent=percent;controls().speedScale=1;const time=releaseTime(),pose=authoredPose(time),base=projectiles.preview(projectileOptions()),flight=projectiles.at(time+.1,projectileOptions());controls().speedScale=3;const boosted=projectiles.preview(projectileOptions()),fastFlight=projectiles.at(time+.1,projectileOptions());rows.push({percent,velocityError:R.length(R.sub(boosted.v,R.mul(base.v,3))),twistError:Math.abs(boosted.twist-base.twist),poseSame:JSON.stringify(pose)===JSON.stringify(authoredPose(time)),releaseSame:time===releaseTime(),flightChange:R.length(R.sub(fastFlight.p,flight.p))});}controls().throwPercent=43;controls().speedScale=3;sync();drawAll();save();return rows})()');
 for(const row of velocityMultiplier){assert(row.velocityError<1e-8);assert.equal(row.twistError,0);assert(row.poseSame&&row.releaseSame);if(row.percent)assert(row.flightChange>1e-4);else assert(row.flightChange<1e-9);}
 await evaluate('document.getElementById("smallThrowVelocity").scrollIntoView({block:"center"})');await shot('small-throw-velocity-slider');






 await evaluate('document.getElementById("clip").value="big-throw";document.getElementById("clip").dispatchEvent(new Event("change"));ThrowLab.seek(releaseTime())');assert.equal(await evaluate('controls().aimAtTarget'),true);
 assert.equal(await evaluate('document.getElementById("throwPercentSection").hidden'),true);assert.equal(await evaluate('controls().throwPercent'),100);
 await click('aimAtTarget');await click('halfAttack');assert(R.length(R.sub((await evaluate('ThrowLab.state')).launch.v,before.launch.v))<1e-8);assert.deepEqual((await evaluate('ThrowLab.state')).pose,before.pose);
 await click('aimAtTarget');await click('halfAttack');await evaluate('document.querySelector("aside").scrollTop=0;resetCamera();ThrowLab.seek(controls().armed/60)');await shot('attack-modes');assert.deepEqual(await evaluate('ThrowLab.state.errors'),[]);
 const result={success:true,fullAim,halfAim,fiveBody,bodySmoothness,forwardProgress,slowdown,velocityMultiplier,checks:'Actual checkbox clicks; default off, half fixed legs/head world rotation, full yaw-only pelvis, release spear-axis direction/speed/twist, one-step undo, exact off restore, target edit invalidation, independent throws, Small Throw bomb default/override/undo/Refresh and current asset hashes; Throw % causal identical wind-up with Aim/Half, neutral-to-full forward arc scaled to50% (about43deg from the actual neutral pose), entire source arm/palm orientation retained, including18% regression, body remaining motion reduced after the causal trigger,5% world head/chest/pelvis movement bounded; body velocity continuous across trigger/entry/peak at5/25/50/76/99%; no armed plateau at33%; direct arm return from reduced peak, earlier fractional release, exact half speed, zero drop, original 100% restore, grouped undo/redo/Refresh, half/full bomb/spear aim, Big Throw unchanged. Slowdown slider0/0.5/1, linear source rates, earlier synchronized release, preserved strength/prefix, grouped undo/redo/Refresh and fast Aim/Half tested. All state writes isolated.'};fs.writeFileSync(path.join(out,'attack-browser-verification.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 }finally{if(socket?.readyState===1){await send('Browser.close').catch(()=>{});socket.close();}else browser.kill();}
})().catch(e=>{console.error(e);process.exitCode=1;});
