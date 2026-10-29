// Short isolated headless smoke test. Never writes the user's saved lab settings.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),{spawn}=require('node:child_process');
const out=path.resolve(__dirname,'../../Saved/ThrowLab'),profile=path.join(out,'flat-flight-profile'),sleep=ms=>new Promise(r=>setTimeout(r,ms));fs.mkdirSync(profile,{recursive:true});
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
 await send('Page.enable');await send('Runtime.enable');await send('Network.enable');await send('Emulation.setDeviceMetricsOverride',{width:1920,height:900,deviceScaleFactor:1,mobile:false});
 await send('Page.addScriptToEvaluateOnNewDocument',{source:`const originalFetch=fetch;window.fetch=(input,opts={})=>{const p=new URL(input,location.href).pathname;if(p==='/state'){if(opts.method==='POST')sessionStorage.setItem('qa-state',opts.body);return Promise.resolve(new Response(opts.method==='POST'?'{}':sessionStorage.getItem('qa-state')||'{}'));}return originalFetch(input,opts)};navigator.sendBeacon=()=>true;`});
 const seed=JSON.parse(fs.readFileSync(path.join(__dirname,'fixtures/flat-spear-flight.json')));
 await send('Page.addScriptToEvaluateOnNewDocument',{source:"if(!sessionStorage.getItem('qa-state'))sessionStorage.setItem('qa-state',"+JSON.stringify(JSON.stringify(seed))+");"});
 await send('Page.navigate',{url:'http://127.0.0.1:8893/throw-lab.html'});await ready();
 assert.equal(await evaluate('ThrowLab.state.playback.time'),.9);
 const actual=await evaluate('ThrowLab.state'),axis=R.rotate(actual.object.q,[0,0,1]),pitch=Math.asin(axis[1])*180/Math.PI;
 assert(pitch<-8);assert.equal(actual.physics.airSteps,40);assert.deepEqual(actual.settings,C.sanitize(seed.settings));assert.deepEqual(actual.camera,seed.camera);
 await shot('spear-air-response-fixed');await evaluate('ThrowLab.refresh()');await sleep(300);await ready();assert.deepEqual(await evaluate('ThrowLab.state.object'),actual.object);assert.deepEqual(await evaluate('ThrowLab.state.errors'),[]);
 console.log(JSON.stringify({success:true,frame:54,pitch,airSteps:actual.physics.airSteps,exactSettingsPreserved:true}));
 }finally{if(socket?.readyState===1){await send('Browser.close').catch(()=>{});socket.close();}else browser.kill();}
})().catch(e=>{console.error(e);process.exitCode=1;});
