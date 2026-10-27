// Short isolated headless smoke test. Never writes the user's saved lab settings.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),{spawn}=require('node:child_process');
const out=path.resolve(__dirname,'../../Saved/ThrowLab'),profile=path.join(out,'whole-frame-profile'),sleep=ms=>new Promise(r=>setTimeout(r,ms));fs.mkdirSync(profile,{recursive:true});
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
 const seed={settings:{clip:'big-throw',forearmGizmo:true,releases:{'big-throw':33.25/60},vanilla:{'big-throw':{forearmKeys:JSON.parse(fs.readFileSync(path.join(__dirname,'fixtures/whole-frame-forearm-keys.json')))}}},playback:{time:20.27544/60,playing:false}};
 await send('Page.addScriptToEvaluateOnNewDocument',{source:"if(!sessionStorage.getItem('qa-state'))sessionStorage.setItem('qa-state',"+JSON.stringify(JSON.stringify(seed))+");"});
 await send('Page.navigate',{url:'http://127.0.0.1:8893/throw-lab.html'});await ready();
 const migrated=await evaluate('ThrowLab.state');
 assert.equal(migrated.settings.vanilla['big-throw'].forearmKeys.length,14);
 assert(migrated.settings.vanilla['big-throw'].forearmKeys.every(k=>Number.isInteger(k.frame)));
 assert.equal(migrated.releaseTime,33.25/60,JSON.stringify({settings:migrated.settings.releases,stored:await evaluate('JSON.parse(sessionStorage.getItem("qa-state")).settings.releases'),fn:await evaluate('releaseTime.toString()')}));
 const camera=migrated.camera;
 async function dragRing(kind,axis,overlap=false){
  const points=await evaluate(`(()=>{const el=document.querySelector('.gizmo-hit[data-kind="${kind}"][data-axis="${axis}"]'),r=document.getElementById('gizmoOverlay').getBoundingClientRect(),length=el.getTotalLength();for(let f=${overlap?.005:.05};f<.9;f+=${overlap?.005:.05}){const a=el.getPointAtLength(length*f),b=el.getPointAtLength(length*(f+.07));const hit=document.elementFromPoint(r.left+a.x,r.top+a.y);if(${overlap}?hit!==el&&hit?.classList.contains('gizmo-hit'):hit===el)return {a:{x:r.left+a.x,y:r.top+a.y},b:{x:r.left+b.x,y:r.top+b.y}};}return null;})()`);

  assert(points,'No reachable '+kind+' ring '+axis);
  await send('Input.dispatchMouseEvent',{type:'mouseMoved',...points.a});
  if(kind==='hand'||kind==='forearm'){
   const shown=await evaluate("({display:getComputedStyle(document.getElementById('rotationReadout')).display,...document.getElementById('rotationReadout').dataset,text:gizmos.readout.text.textContent})");assert.notEqual(shown.display,'none');assert.equal(shown.kind,kind);assert.equal(+shown.axis,axis);assert.match(shown.text,/[XYZ]/);assert.equal(await evaluate("document.querySelectorAll('.gizmo-hit title').length"),0);assert.equal(await evaluate("document.getElementById('rotationReadout').parentElement.classList.contains('gizmo-label')"),true);
  }else assert.equal(await evaluate("getComputedStyle(document.getElementById('rotationReadout')).display"),'none');
await send('Input.dispatchMouseEvent',{type:'mousePressed',...points.a,button:'left',buttons:1,clickCount:1});assert.equal(await evaluate('gizmos.active?.kind'),kind,'Gizmo drag must capture pointer');assert.equal(await evaluate('gizmos.active?.axis'),axis,'Nearest visible ring must win over SVG stacking');
  await evaluate('window.dragStart={pose:structuredClone(currentPose),normal:gizmos.active.ring.normal.slice(),frame:time*60}');
  for(let i=1;i<=5;i++)await send('Input.dispatchMouseEvent',{type:'mouseMoved',x:points.a.x+(points.b.x-points.a.x)*i/5,y:points.a.y+(points.b.y-points.a.y)*i/5,button:'left',buttons:1});

  if(kind==='hand'||kind==='forearm'){
   const read=await evaluate("(()=>{const t=document.getElementById('rotationReadout'),a=gizmos.active,m=gizmos.models[a.kind];return {display:getComputedStyle(t).display,...t.dataset,text:gizmos.readout.text.textContent,expected:ThrowVanilla.axisOffsetDegrees(m.defaultQ,m.currentQ,a.ring.normal)};})()");assert.notEqual(read.display,'none');assert.equal(read.kind,kind);assert.equal(+read.axis,axis);assert(Math.abs(+read.degrees-read.expected)<1e-7);assert.match(read.text,/[XYZ]/);if(kind==='forearm'&&axis===1)await shot('rotation-label-readout');

  }
  assert(Math.abs(await evaluate('gizmos.active?.total||0'))>.001,JSON.stringify({kind,axis,points,drag:await evaluate('gizmos.active&&({total:gizmos.active.total,point:gizmos.active.point,pointer:gizmos.active.pointer})')}));await send('Input.dispatchMouseEvent',{type:'mouseReleased',...points.b,button:'left',clickCount:1});
 }

 for(const [kind,id,bone,keyName] of [['forearm','forearmGizmo','lowerarm_l','forearmKeys'],['hand','handGizmo','hand_l','keys']]){
  await evaluate(`if(!document.getElementById('${id}').checked)document.getElementById('${id}').click();ThrowLab.seek(20.27544/60)`);
  for(let axis=0;axis<3;axis++){
   await dragRing(kind,axis);
   const result=await evaluate('({state:ThrowLab.state,start:window.dragStart})'),index=data.names.indexOf(bone);
   assert.equal(result.start.frame,20);assert.equal(result.state.playback.time,20/60);
   assert(result.state.settings.vanilla['big-throw'][keyName].every(k=>Number.isInteger(k.frame)));
   const delta=R.qlog(R.qm(result.state.pose.q[index],R.qinv(result.start.pose.q[index])));
   assert(R.length(delta)>.001);assert(R.length(R.cross(delta,result.start.normal))<1e-6);
   assert.deepEqual(result.state.camera,camera);
  }
 }
 // Numeric edits and Key here also snap, even without focusing the field first.
 await evaluate("ThrowLab.seek(22.6/60);document.getElementById('handX').value='35';document.getElementById('handX').dispatchEvent(new Event('change'))");
 assert.equal(await evaluate('ThrowLab.state.playback.time'),23/60);
 assert.equal(await evaluate("controls().keys.find(k=>k.frame===23).rotation[0]"),35);
 await evaluate("ThrowLab.seek(24.6/60);document.getElementById('setHandKey').click()");
 assert.equal(await evaluate('ThrowLab.state.playback.time'),25/60);
 await evaluate("document.getElementById('armedFrame').value='12.5';document.getElementById('armedFrame').dispatchEvent(new Event('change'));document.getElementById('goThrow').click()");
 assert.equal(await evaluate('controls().armed'),13);assert.equal(await evaluate('ThrowLab.state.playback.time'),33.25/60);
 await send('Input.dispatchKeyEvent',{type:'keyDown',key:'d',code:'KeyD'});await send('Input.dispatchKeyEvent',{type:'keyUp',key:'d',code:'KeyD'});
 assert.equal(await evaluate('ThrowLab.state.playback.time'),34/60);
 assert.equal(await evaluate("document.getElementById('scrub').step"),'1');
 const before=await evaluate('ThrowLab.state');await evaluate('ThrowLab.refresh()');await sleep(300);await ready();
 const after=await evaluate('ThrowLab.state');assert.deepEqual(after.settings,before.settings);assert.deepEqual(after.camera,before.camera);assert.deepEqual(after.playback,before.playback);
 await evaluate('undoEdit()');assert((await evaluate("controls().keys.concat(controls().forearmKeys)")).every(k=>Number.isInteger(k.frame)));
 assert.deepEqual(await evaluate('ThrowLab.state.errors'),[]);
 receipt.checks.push('Legacy fractional keys consolidate on load; actual hand/forearm axis drags snap before capturing their rotation basis; integer numeric/Key here/armed/step controls; fractional Throw preserved; camera unchanged; Refresh and undo preserve integer keys');
 receipt.success=true;fs.writeFileSync(path.join(out,'whole-frame-verification.json'),JSON.stringify(receipt,null,2));console.log(JSON.stringify(receipt,null,2));
 }finally{if(socket?.readyState===1){await send('Browser.close').catch(()=>{});socket.close();}else browser.kill();}
})().catch(e=>{console.error(e);process.exitCode=1;});
