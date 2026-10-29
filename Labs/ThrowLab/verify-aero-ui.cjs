// Short isolated headless smoke test. Never writes the user's saved lab settings.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),{spawn}=require('node:child_process');
const out=path.resolve(__dirname,'../../Saved/ThrowLab'),profile=path.join(out,'aerodynamics-profile'),sleep=ms=>new Promise(r=>setTimeout(r,ms));fs.mkdirSync(profile,{recursive:true});
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
 const approved=JSON.parse(fs.readFileSync(path.join(__dirname,'approved/2026-10-27/saved-profile.json'))),seed={settings:approved.settings,camera:approved.camera,playback:{time:0,playing:false}};
 await send('Page.addScriptToEvaluateOnNewDocument',{source:"if(!sessionStorage.getItem('qa-state'))sessionStorage.setItem('qa-state',"+JSON.stringify(JSON.stringify(seed))+");"});
 await send('Page.navigate',{url:'http://127.0.0.1:8893/throw-lab.html'});await ready();
 const before=await evaluate('ThrowLab.state');assert.equal(before.settings.vanilla['big-throw'].aero.enabled,true);
 async function click(id){const p=await evaluate(`(()=>{const el=document.getElementById('${id}');el.scrollIntoView({block:'center'});const r=el.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()`);await send('Input.dispatchMouseEvent',{type:'mousePressed',...p,button:'left',clickCount:1});await send('Input.dispatchMouseEvent',{type:'mouseReleased',...p,button:'left',clickCount:1});}
 await click('alignVelocity');const after=await evaluate('ThrowLab.state');
 assert(R.dot(R.unit(after.launch.v),after.launch.axis)>1-1e-10);assert(Math.abs(R.length(after.launch.v)-R.length(before.launch.v))<1e-8);assert.equal(after.launch.twist,before.launch.twist);assert.deepEqual(after.camera,before.camera);assert.deepEqual(after.playback,before.playback);
 const expected=structuredClone(before.settings);expected.vanilla['big-throw'].velocityRotation=after.settings.vanilla['big-throw'].velocityRotation;assert.deepEqual(after.settings,expected);assert.equal(after.history.undo.length,before.history.undo.length+1);
 await evaluate('undoEdit()');assert.deepEqual(await evaluate('ThrowLab.state.settings'),before.settings);await evaluate('undoEdit(true)');assert.deepEqual(await evaluate('ThrowLab.state.settings'),after.settings);
 await click('alignVelocity');assert.equal(await evaluate('ThrowLab.state.history.undo.length'),after.history.undo.length);
 // Real text input switches auto twist to manual before blur; a focus session
 // remains one undo group. Angular velocity is local shaft spin at release.
 const beforeTwist=await evaluate('ThrowLab.state.settings');
 for(const value of ['6','-6','0']){
  await evaluate("document.getElementById('twist').scrollIntoView({block:'center'});document.getElementById('twist').focus();document.getElementById('twist').select()");
  await send('Input.insertText',{text:value});const state=await evaluate('ThrowLab.state');assert.equal(state.settings.vanilla['big-throw'].twist,+value);assert.equal(await evaluate("document.getElementById('autoTwist').checked"),false);
  const expected=R.mul(state.launch.axis,+value*60*Math.PI/180);assert(R.length(R.sub(state.launch.omega,expected))<1e-8);assert.equal(state.settings.vanilla['big-throw'].speedScale,beforeTwist.vanilla['big-throw'].speedScale);
 }
 await evaluate("document.getElementById('twist').value='';document.getElementById('twist').dispatchEvent(new Event('input'))");assert.equal(await evaluate('controls().twist'),0);
 await evaluate('document.activeElement.blur();undoEdit()');assert.deepEqual(await evaluate('ThrowLab.state.settings'),beforeTwist);
 await evaluate("document.getElementById('aeroOptions').open=true");
 for(const [id,value,key,expected] of [['aeroStrength','2.5','strength',2.5],['aeroPressure','35','pressure',.35],['aeroDamping','1.8','damping',1.8]]){
  const prior=await evaluate('ThrowLab.state.settings');await evaluate(`document.getElementById('${id}').value='${value}';document.getElementById('${id}').dispatchEvent(new Event('change'))`);assert(Math.abs((await evaluate(`controls().aero.${key}`))-expected)<1e-12);const edited=await evaluate('ThrowLab.state.settings');await evaluate('undoEdit()');assert.deepEqual(await evaluate('ThrowLab.state.settings'),prior);await evaluate('undoEdit(true)');assert.deepEqual(await evaluate('ThrowLab.state.settings'),edited);
 }
 await click('aeroEnabled');await evaluate('ThrowLab.seek(100/60)');assert.equal(await evaluate('ThrowLab.state.physics.airSteps'),0);assert.equal(await evaluate("document.getElementById('aeroStrength').disabled"),true);
 await click('aeroEnabled');assert((await evaluate('ThrowLab.state.physics.airSteps'))>0);
 await evaluate("document.getElementById('object').value='bomb';document.getElementById('object').dispatchEvent(new Event('change'))");assert.equal(await evaluate("document.getElementById('alignVelocity').disabled"),true);assert.equal(await evaluate("document.getElementById('aeroEnabled').disabled"),true);assert.equal(await evaluate('ThrowLab.state.physics.airSteps'),0);
 await evaluate("document.getElementById('object').value='sword';document.getElementById('object').dispatchEvent(new Event('change'))");
 const settings=await evaluate('ThrowLab.state.settings'),camera=await evaluate('ThrowLab.state.camera');await evaluate('ThrowLab.refresh()');await sleep(300);await ready();assert.deepEqual(await evaluate('ThrowLab.state.settings'),settings);assert.deepEqual(await evaluate('ThrowLab.state.camera'),camera);
 await evaluate("document.getElementById('clip').value='small-throw';document.getElementById('clip').dispatchEvent(new Event('change'))");assert.equal(await evaluate('controls().aero.strength'),1);
 await evaluate("document.getElementById('clip').value='big-throw';document.getElementById('clip').dispatchEvent(new Event('change'));document.getElementById('aeroOptions').open=true;document.getElementById('alignVelocity').scrollIntoView({block:'center'});ThrowLab.seek(34/60)");assert.equal(await evaluate('controls().aero.strength'),2.5);assert.deepEqual(await evaluate('ThrowLab.state.errors'),[]);await evaluate("document.getElementById('twist').scrollIntoView({block:'center'})");await shot('spear-aerodynamics-controls');
 receipt.checks.push('Manual signed twist responds to real text input before blur, zero/negative rates and grouped undo; actual snap-button click uses held pose at Throw, preserves speed/twist/keys/grip/camera/playhead, one-step undo/redo and duplicate no-op; aero controls/disable/bomb exclusion/cache refresh/independent throws/Refresh verified');receipt.success=true;fs.writeFileSync(path.join(out,'aerodynamics-browser-verification.json'),JSON.stringify(receipt,null,2));console.log(JSON.stringify(receipt,null,2));
 }finally{if(socket?.readyState===1){await send('Browser.close').catch(()=>{});socket.close();}else browser.kill();}
})().catch(e=>{console.error(e);process.exitCode=1;});
