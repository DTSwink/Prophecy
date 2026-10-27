const fs=require('node:fs'),path=require('node:path');
const lab=__dirname;
const state={schema:'bodyflip-lab-v1',settings:{mode:'jump',motion:'kinematic',ramps:false,platformResetVersion:1,platforms:[{id:'floor',position:[0,-.2,-1.56],size:[5,.4,12.88],rotation:[0,0,0,1]}],airFlip:false,flipAngle:0,twistAngle:0,jumpEvents:[{id:'first',time:.9,surface:'floor',flip:360,twist:180,turnDelay:.1,turnDuration:.8,pose:'pose1'}]},playback:{time:0,playing:false},camera:{yaw:-.7,pitch:-.1,zoom:1,panX:0,panY:0}};
state.settings.platformResetVersion=require(path.join(lab,'platforms.js')).restoreDefaultsOnce({}).platformResetVersion;
const guard=`<script>
window.qa={errors:[],writes:0,requests:[]};window.addEventListener('error',e=>qa.errors.push(e.message));window.addEventListener('unhandledrejection',e=>qa.errors.push(String(e.reason)));
const fixture=${JSON.stringify(state)},realFetch=window.fetch.bind(window);
window.fetch=(input,options={})=>{const url=new URL(typeof input==='string'?input:input.url,location.href);if(url.pathname==='/state'){if(options.method==='POST'){qa.writes++;return Promise.resolve(new Response('{}',{headers:{'Content-Type':'application/json'}}));}return Promise.resolve(new Response(JSON.stringify(fixture),{headers:{'Content-Type':'application/json'}}));}if(['/resume','/snapshot'].includes(url.pathname))throw Error('Unexpected write/inference route in isolated preview');const request={path:url.pathname,start:performance.now()};qa.requests.push(request);return realFetch(input,options).then(r=>{request.status=r.status;request.end=performance.now();return r;});};
</script>`;
const test=`<script>
(async()=>{const wait=ms=>new Promise(r=>setTimeout(r,ms));for(let i=0;i<1000&&!window.BodyflipLab;i++)await wait(50);if(!window.BodyflipLab)throw Error('Lab did not initialize');for(let i=0;i<400&&BodyflipLab.state.loadingRun;i++)await wait(50);
BodyflipLab.setPlaying(false);const s=BodyflipLab.state;await BodyflipLab.seek(s.flight.airStart+.37);document.querySelector('.jump-marker').click();
const box=document.getElementById('jumpPopover').getBoundingClientRect();qa.popup={left:box.left,right:box.right,top:box.top,bottom:box.bottom,width:box.width,height:box.height};qa.viewport=[innerWidth,innerHeight];qa.state={frame:BodyflipLab.state.frame,phase:BodyflipLab.state.flight.phase,motion:BodyflipLab.state.flight.jumpMotion};qa.errors.push(...BodyflipLab.state.errors);qa.overflow=[...document.querySelectorAll('#jumpPopover .jump-motion-fields input,#jumpPopover .jump-motion-fields select')].some(e=>{const r=e.getBoundingClientRect();return r.left<box.left||r.right>box.right;});qa.complete=true;document.title='QA '+JSON.stringify(qa);document.body.dataset.qa=JSON.stringify(qa);
})().catch(e=>{qa.errors.push(e.stack);document.title='QA FAIL '+e.message;document.body.dataset.qa=JSON.stringify(qa);});
</script>`;
const html=fs.readFileSync(path.join(lab,'index.html'),'utf8').replace('<head>','<head>'+guard).replace('</body>',test+'</body>');
fs.writeFileSync(path.join(lab,'.jump-motion-qa.html'),html);
console.log('Isolated preview generated; state writes blocked.');

// Isolated headless integration test. Its fixture blocks live-state writes.
const {spawn}=require('node:child_process');
const out=path.resolve(__dirname,'../../Saved/BodyflipLab'),profile=path.join(out,'jump-motion-render-profile'),sleep=ms=>new Promise(r=>setTimeout(r,ms));
fs.mkdirSync(profile,{recursive:true});
const portFile=path.join(profile,'DevToolsActivePort');if(fs.existsSync(portFile))fs.unlinkSync(portFile);
const chrome=process.env.BODYFLIP_BROWSER||['C:/Program Files/Google/Chrome/Application/chrome.exe','C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'].find(p=>fs.existsSync(p));
if(!chrome)throw Error('Set BODYFLIP_BROWSER to an installed Chromium browser');
const browser=spawn(chrome,['--headless','--remote-debugging-port=0','--disable-background-networking','--disable-extensions','--no-first-run','--no-default-browser-check','--disable-component-update','--disable-sync','--hide-scrollbars','--enable-unsafe-swiftshader','--use-angle=swiftshader','--window-size=1280,900','--user-data-dir='+profile,'about:blank'],{windowsHide:true,stdio:'ignore'});
let socket,serial=0;const pending=new Map();
function send(method,params={}){return new Promise((resolve,reject)=>{const id=++serial;pending.set(id,{resolve,reject});socket.send(JSON.stringify({id,method,params}));});}
async function evaluate(expression){const r=await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value;}
async function shot(name){const r=await send('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path.join(out,name+'.png'),Buffer.from(r.data,'base64'));}
(async()=>{
 for(let i=0;i<200&&!fs.existsSync(portFile);i++)await sleep(50);
 const port=fs.readFileSync(portFile,'utf8').split('\n')[0],targets=await(await fetch('http://127.0.0.1:'+port+'/json/list')).json();
 socket=new WebSocket(targets.find(t=>t.type==='page').webSocketDebuggerUrl);await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});
 socket.onmessage=event=>{const r=JSON.parse(event.data),p=pending.get(r.id);if(p){pending.delete(r.id);r.error?p.reject(Error(JSON.stringify(r.error))):p.resolve(r.result);}};
 await send('Page.enable');await send('Emulation.setDeviceMetricsOverride',{width:1280,height:900,deviceScaleFactor:1,mobile:false});
 await send('Page.navigate',{url:'http://127.0.0.1:8876/.jump-motion-qa.html'});
 let receipt;for(let i=0;i<240;i++){receipt=await evaluate('window.qa||null');if(receipt?.complete||receipt?.errors?.length)break;await sleep(250);}
 if(!receipt?.complete||receipt.errors.length||receipt.overflow||receipt.popup.top<0||receipt.popup.right>1280)throw Error(JSON.stringify(receipt));
 await shot('jump-motion-popup');
 await send('Emulation.setDeviceMetricsOverride',{width:1000,height:700,deviceScaleFactor:1,mobile:false});
 await evaluate("document.querySelector('.jump-marker').click();BodyflipLab.step(0)");
 await shot('jump-motion-popup-small');
 receipt.small=await evaluate("(()=>{const r=document.getElementById('jumpPopover').getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,overflow:[...document.querySelectorAll('#jumpPopover .jump-motion-fields input,#jumpPopover .jump-motion-fields select')].some(e=>{const x=e.getBoundingClientRect();return x.left<r.left||x.right>r.right;})};})()");
 await send('Emulation.setDeviceMetricsOverride',{width:1280,height:900,deviceScaleFactor:1,mobile:false});
 await evaluate("document.dispatchEvent(new KeyboardEvent('keydown',{code:'Escape'}));document.getElementById('cameraSide').click();");
 const start=await evaluate('BodyflipLab.state.flight.airStart');
 if(receipt.small.overflow||receipt.small.top<0||receipt.small.right>1000)throw Error('Small popup overflows viewport');
 receipt.escapeCloses=await evaluate("document.getElementById('jumpPopover').hidden");if(!receipt.escapeCloses)throw Error('Escape did not close jump popup');
 receipt.frames=[];
 for(const [i,age] of [0,.05,.1,.2,.3,.4,.5,.65,.8,.95].entries()){
  await evaluate(`BodyflipLab.seek(${start+age})`);await shot('jump-motion-frame-'+String(i).padStart(2,'0'));
  receipt.frames.push(await evaluate('({frame:BodyflipLab.state.frame,motion:BodyflipLab.state.flight.jumpMotion,errors:BodyflipLab.state.errors})'));
 }
 await evaluate("document.querySelector('.jump-marker').click();document.getElementById('jumpDelay').focus();document.getElementById('jumpDelay').select();");
 await send('Input.insertText',{text:'0.25'});
 await evaluate("document.body.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true}));");
 for(let i=0;i<120&&await evaluate('BodyflipLab.state.loadingRun');i++)await sleep(100);
 receipt.edit=await evaluate("({delay:BodyflipLab.state.settings.jumpEvents[0].turnDelay,time:BodyflipLab.state.simTime,closed:document.getElementById('jumpPopover').hidden,errors:BodyflipLab.state.errors})");
 if(receipt.edit.delay!==.25||!receipt.edit.closed||Math.abs(receipt.edit.time-Math.round((start+.95)*60)/60)>1e-8||receipt.edit.errors.length)throw Error('Click-away did not apply cleanly: '+JSON.stringify(receipt.edit));
 await evaluate("document.querySelector('.jump-marker').click();const summary=document.querySelector('#minorOptions>summary');summary.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true}));summary.click();document.getElementById('minorOptions').scrollTop=10000;");
 await shot('jump-more-options');
 receipt.advanced=await evaluate("(()=>{const r=document.getElementById('minorOptions').getBoundingClientRect();return {label:document.getElementById('jumpOptionsLabel').textContent,closed:document.getElementById('jumpPopover').hidden,enabled:!document.getElementById('jumpTurnIn').disabled,overflow:[...document.querySelectorAll('#jumpMotionOptions input')].some(e=>{const x=e.getBoundingClientRect();return x.left<r.left||x.right>r.right;})};})()");
 if(!receipt.advanced.closed||!receipt.advanced.enabled||receipt.advanced.overflow||!receipt.advanced.label.startsWith('J1'))throw Error('Advanced panel selection/layout failed');
 await evaluate("document.getElementById('jumpTurnIn').focus();document.getElementById('jumpTurnIn').select();");await send('Input.insertText',{text:'0.1'});await evaluate("document.body.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true}));");
 for(let i=0;i<120&&await evaluate('BodyflipLab.state.loadingRun');i++)await sleep(100);
 receipt.advancedEdit=await evaluate("({easeIn:BodyflipLab.state.settings.jumpEvents[0].turnIn,time:BodyflipLab.state.simTime,errors:BodyflipLab.state.errors})");
 if(receipt.advancedEdit.easeIn!==.1||receipt.advancedEdit.time!==receipt.edit.time||receipt.advancedEdit.errors.length)throw Error('Advanced blend edit failed');
 await send('Emulation.setDeviceMetricsOverride',{width:1000,height:700,deviceScaleFactor:1,mobile:false});await evaluate("document.getElementById('minorOptions').scrollTop=10000;");await shot('jump-more-options-small');
 fs.writeFileSync(path.join(out,'jump-motion-browser-verification.json'),JSON.stringify(receipt,null,2));console.log(JSON.stringify(receipt));
})().catch(async e=>{console.error(e);if(socket?.readyState===1){console.error(await evaluate("JSON.stringify({qa:window.qa,info:document.getElementById('runInfo')?.textContent,error:document.getElementById('error')?.textContent})"));await shot('jump-motion-failed');}process.exitCode=1;}).finally(async()=>{if(socket?.readyState===1){try{await send('Browser.close');}catch{}socket.close();}else if(browser.exitCode===null)browser.kill();const temporary=path.join(lab,'.jump-motion-qa.html');if(fs.existsSync(temporary))fs.unlinkSync(temporary);});
