const fs=require('node:fs'),path=require('node:path');
const lab=__dirname,server=process.env.BODYFLIP_TEST_URL||'http://127.0.0.1:8876',expected=process.env.BODYFLIP_EXPECT_SHARED!=='0';
const S=require('./support.js'),k=Math.SQRT1_2;
const incline=S.rectangle('incline',[0,0,0],[1,0,0],[0,k,k],[-5,5,-4,100],.2);
const state={schema:'bodyflip-lab-v1',settings:{mode:'walk',motion:'kinematic',ramps:true,platforms:[S.platformRecord(incline)],airFlip:false,flipAngle:0,twistAngle:0,jumpEvents:[]},playback:{time:0,playing:false},camera:{yaw:2.1,pitch:-.3,zoom:1,panX:0,panY:0}};
state.settings.platformResetVersion=require(path.join(lab,'platforms.js')).restoreDefaultsOnce({}).platformResetVersion;
const guard=`<script>
window.qa={errors:[],writes:0,requests:[]};window.addEventListener('error',e=>qa.errors.push(e.message));window.addEventListener('unhandledrejection',e=>qa.errors.push(String(e.reason)));
const fixture=${JSON.stringify(state)},realFetch=window.fetch.bind(window);
window.fetch=(input,options={})=>{const url=new URL(typeof input==='string'?input:input.url,location.href);if(url.pathname==='/state'){if(options.method==='POST'){qa.writes++;return Promise.resolve(new Response('{}',{headers:{'Content-Type':'application/json'}}));}return Promise.resolve(new Response(JSON.stringify(fixture),{headers:{'Content-Type':'application/json'}}));}if(['/resume','/snapshot'].includes(url.pathname))throw Error('Unexpected write/inference route in isolated preview');const request={path:url.pathname,start:performance.now()};qa.requests.push(request);return realFetch(input,options).then(r=>{request.status=r.status;request.end=performance.now();return r;});};
</script>`;
const test=`<script>
(async()=>{const wait=ms=>new Promise(r=>setTimeout(r,ms));for(let i=0;i<1000&&!window.BodyflipLab;i++)await wait(50);if(!window.BodyflipLab)throw Error('Lab did not initialize');for(let i=0;i<400&&BodyflipLab.state.loadingRun;i++)await wait(50);
BodyflipLab.setPlaying(false);await BodyflipLab.seek(.8);qa.errors.push(...BodyflipLab.state.errors);qa.complete=true;
})().catch(e=>{qa.errors.push(e.stack);document.title='QA FAIL '+e.message;document.body.dataset.qa=JSON.stringify(qa);});
</script>`;
const html=fs.readFileSync(path.join(lab,'index.html'),'utf8').replace('<head>','<head>'+guard).replace('</body>',test+'</body>');
fs.writeFileSync(path.join(lab,'.shared-foot-ik-qa.html'),html);
console.log('Isolated preview generated; state writes blocked.');

// Isolated headless integration test. Its fixture blocks live-state writes.
const {spawn}=require('node:child_process');
const out=path.resolve(__dirname,'../../Saved/BodyflipLab'),profile=path.join(out,'shared-foot-ik-render-profile'),sleep=ms=>new Promise(r=>setTimeout(r,ms));
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
 await send('Page.navigate',{url:server+'/.shared-foot-ik-qa.html'});
 let receipt;for(let i=0;i<240;i++){receipt=await evaluate('window.qa||null');if(receipt?.complete||receipt?.errors?.length)break;await sleep(250);}
 if(!receipt?.complete||receipt.errors.length)throw Error(JSON.stringify(receipt));
 receipt.samples=[];
 for(const t of [0,.4,.8,1.2,1.6,2]){
  await evaluate(`BodyflipLab.seek(${t})`);await shot((expected?'shared-foot-ik-':'shared-foot-ik-pending-')+Math.round(t*60));
  receipt.samples.push(await evaluate('({frame:BodyflipLab.state.frame,phase:BodyflipLab.state.flight.phase,active:!!BodyflipLab.state.flight.footIK,source:BodyflipLab.state.flight.footIKSource,errors:BodyflipLab.state.errors})'));
 }
 if(receipt.samples.some(s=>s.active!==expected||s.errors.length||(expected&&!s.source)))throw Error('Shared solver not active in real app');
 await evaluate("document.getElementById('surfaceIK').click()");
 for(let i=0;i<120&&await evaluate('BodyflipLab.state.loadingRun');i++)await sleep(100);
 receipt.disabled=await evaluate('({enabled:BodyflipLab.state.settings.surfaceIK,time:BodyflipLab.state.simTime,active:!!BodyflipLab.state.flight.footIK,errors:BodyflipLab.state.errors})');
 if((expected&&receipt.disabled.enabled)||receipt.disabled.active||receipt.disabled.time!==2||receipt.disabled.errors.length)throw Error('Foot IK comparison toggle failed');

 fs.writeFileSync(path.join(out,expected?'shared-foot-ik-browser-verification.json':'shared-foot-ik-pending-verification.json'),JSON.stringify(receipt,null,2));console.log(JSON.stringify(receipt));
})().catch(async e=>{console.error(e);if(socket?.readyState===1){console.error(await evaluate("JSON.stringify({qa:window.qa,info:document.getElementById('runInfo')?.textContent,error:document.getElementById('error')?.textContent})"));await shot('shared-foot-ik-failed');}process.exitCode=1;}).finally(async()=>{if(socket?.readyState===1){try{await send('Browser.close');}catch{}socket.close();}else if(browser.exitCode===null)browser.kill();const temporary=path.join(lab,'.shared-foot-ik-qa.html');if(fs.existsSync(temporary))fs.unlinkSync(temporary);});
