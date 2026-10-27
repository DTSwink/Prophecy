/* Owned headless app preview; all saves stay in the fixture's memory. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),{spawn}=require('node:child_process');
const lab=__dirname,out=path.resolve(lab,'../../Saved/BodyflipLab'),profile=path.join(out,'torso-render-profile'),temporary=path.join(lab,'.torso-qa.html');
const state={schema:'bodyflip-lab-v1',settings:{mode:'spaceGym',motion:'kinematic',platformResetVersion:require('./platforms.js').restoreDefaultsOnce({}).platformResetVersion,platforms:[{id:'floor',position:[0,-.2,0],size:[10,.4,20],rotation:[0,0,0,1]}],jumpEvents:[{id:'first',time:.5,surface:'auto',jumpPercent:0,flip:0,twist:0,pose:'none',attack:'slashLD',attackDelay:.1}]},playback:{time:0,playing:false},camera:{yaw:-.7,pitch:-.1,zoom:1,panX:0,panY:0}};
const guard=`<script>
window.qa={errors:[],writes:0,requests:[]};window.addEventListener('error',e=>qa.errors.push(e.message));window.addEventListener('unhandledrejection',e=>qa.errors.push(String(e.reason)));
const key='bodyflip-torso-qa-only',realFetch=window.fetch.bind(window);let fixture=JSON.parse(sessionStorage.getItem(key)||'null')||${JSON.stringify(state)};
window.fetch=(input,options={})=>{const url=new URL(typeof input==='string'?input:input.url,location.href);if(url.pathname==='/state'){if(options.method==='POST'){qa.writes++;fixture=JSON.parse(options.body);sessionStorage.setItem(key,JSON.stringify(fixture));return Promise.resolve(new Response('{}'));}return Promise.resolve(new Response(JSON.stringify(fixture)));}if(['/run','/resume','/snapshot'].includes(url.pathname))throw Error('Unexpected inference/write in Space gym: '+url.pathname);qa.requests.push(url.pathname);return realFetch(input,options);};
</script>`;
fs.mkdirSync(profile,{recursive:true});fs.writeFileSync(temporary,fs.readFileSync(path.join(lab,'index.html'),'utf8').replace('<head>','<head>'+guard));
const portFile=path.join(profile,'DevToolsActivePort');if(fs.existsSync(portFile))fs.unlinkSync(portFile);
const chrome=['C:/Program Files/Google/Chrome/Application/chrome.exe','C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'].find(p=>fs.existsSync(p));
const browser=spawn(chrome,['--headless','--remote-debugging-port=0','--disable-background-networking','--disable-extensions','--no-first-run','--no-default-browser-check','--disable-component-update','--disable-sync','--hide-scrollbars','--enable-unsafe-swiftshader','--use-angle=swiftshader','--window-size=1280,900','--user-data-dir='+profile,'about:blank'],{windowsHide:true,stdio:'ignore'});
const sleep=ms=>new Promise(r=>setTimeout(r,ms)),pending=new Map();let socket,serial=0;
function send(method,params={}){return new Promise((resolve,reject)=>{const id=++serial;pending.set(id,{resolve,reject});socket.send(JSON.stringify({id,method,params}));});}
async function evaluate(expression){const r=await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value;}
async function ready(){for(let i=0;i<300;i++){const q=await evaluate('({ready:!!window.BodyflipLab&&!BodyflipLab.state.loadingRun,errors:window.qa?.errors||[]})');if(q.errors.length)throw Error(JSON.stringify(q));if(q.ready)return;await sleep(100);}throw Error('App did not become ready');}
async function shot(name){const r=await send('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path.join(out,name+'.png'),Buffer.from(r.data,'base64'));}
(async()=>{
 for(let i=0;i<200&&!fs.existsSync(portFile);i++)await sleep(50);
 const port=fs.readFileSync(portFile,'utf8').split('\n')[0],targets=await(await fetch('http://127.0.0.1:'+port+'/json/list')).json();
 socket=new WebSocket(targets.find(t=>t.type==='page').webSocketDebuggerUrl);await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});socket.onmessage=e=>{const r=JSON.parse(e.data),p=pending.get(r.id);if(p){pending.delete(r.id);r.error?p.reject(Error(JSON.stringify(r.error))):p.resolve(r.result);}};
 await send('Page.enable');await send('Emulation.setDeviceMetricsOverride',{width:1100,height:850,deviceScaleFactor:1,mobile:false});await send('Page.navigate',{url:'http://127.0.0.1:8876/.torso-qa.html'});await ready();
 await evaluate("document.getElementById('cameraFront').click();cameraState.zoom=2.1;BodyflipLab.seek(.6)");await shot('torso-before');
 const receipt={before:await evaluate('BodyflipLab.state.torso'),frames:[]};
 for(const t of [.8,1,1.1]){await evaluate('BodyflipLab.seek('+t+')');await shot('torso-'+t);receipt.frames.push(await evaluate('({frame:BodyflipLab.state.frame,torso:BodyflipLab.state.torso,geometry:BodyflipLab.state.torsoGeometry})'));}
 assert.equal(receipt.frames[0].torso.length,5);assert(receipt.frames.every(f=>f.geometry.every(g=>g.box)));
 const compensation=[];
 assert.equal(await evaluate("+document.getElementById('pelvisAttackCompensation').value"),50);
 for(const percent of [0,50,100]){
  await evaluate("document.getElementById('minorOptions').open=true;document.getElementById('pelvisAttackCompensation').value="+percent+";document.getElementById('pelvisAttackCompensation').onchange()");await ready();
  const result=await evaluate('({frame:BodyflipLab.state.frame,q:BodyflipLab.state.pose.q,value:settings.pelvisAttackCompensation})');assert.equal(result.value,percent/100);assert.equal(result.frame,66);compensation.push(result);
 }
 const upper=await evaluate('BodyflipJumpAttack.bones(names,parents)');
 for(let k=1;k<compensation.length;k++)for(const i of upper){const a=compensation[0].q[i],b=compensation[k].q[i];assert(1-Math.abs(a.reduce((v,x,j)=>v+x*b[j],0))<1e-9);}
 await evaluate("document.getElementById('pelvisAttackCompensation').scrollIntoView({block:'nearest'})");await shot('pelvis-compensation-options');
 await evaluate('persist(stored())');await send('Page.reload');await ready();
 assert.equal(await evaluate('settings.pelvisAttackCompensation'),1);assert.equal(await evaluate('BodyflipLab.state.frame'),66);
 await evaluate("document.getElementById('pelvisAttackCompensation').value=0;document.getElementById('pelvisAttackCompensation').onchange()");await ready();
 receipt.compensation={values:compensation.map(x=>x.value),refreshRestored:true};
 for(const attack of ['slashLD','KickR']){
  await evaluate("document.querySelector('.jump-marker').click();document.getElementById('jumpAttack').value='none';document.getElementById('jumpAttack').onchange()");await ready();
  await evaluate("BodyflipLab.loadAttack('"+attack+"',1)");await ready();
  await evaluate('BodyflipLab.seek(0);BodyflipLab.strike();BodyflipLab.step(20)');
  const result=await evaluate("(()=>{const before=BodyflipLab.state.pose;document.getElementById('stopAttack').click();const after=BodyflipLab.state.pose;return {attack:'"+attack+"',lowerError:Math.max(...[0,1,18,19,20,21,22,23,24,25].map(i=>Recovery.length(Recovery.sub(before.points[i],after.points[i]))))};})()");
  assert(result.lowerError<1e-9);receipt['manual_'+attack]=result;
  await evaluate('BodyflipLab.strike();BodyflipLab.step(20)');
  const error=await evaluate("(()=>{settings.pelvisAttackCompensation=0;const a=targetPose();settings.pelvisAttackCompensation=1;const b=targetPose();settings.pelvisAttackCompensation=0;return Math.max(...BodyflipJumpAttack.bones(names,parents).map(i=>Recovery.length(Recovery.qlog(Recovery.qm(a.q[i],Recovery.qinv(b.q[i]))))));})()");
  assert(error<1e-9);result.compensatedUpperError=error;
 }
 receipt.errors=await evaluate('[...qa.errors,...BodyflipLab.state.errors]');assert.equal(receipt.errors.length,0);
 fs.writeFileSync(path.join(out,'torso-browser-verification.json'),JSON.stringify(receipt,null,2));console.log(JSON.stringify({frames:receipt.frames.map(f=>f.frame),manualSlash:receipt.manual_slashLD,manualKick:receipt.manual_KickR,errors:receipt.errors}));
})().catch(async e=>{console.error(e);if(socket?.readyState===1){console.error(await evaluate("JSON.stringify({qa:window.qa,info:document.getElementById('runInfo')?.textContent,error:document.getElementById('error')?.textContent})"));await shot('torso-failed');}process.exitCode=1;}).finally(async()=>{if(socket?.readyState===1){try{await send('Browser.close');}catch{}socket.close();}else if(browser.exitCode===null)browser.kill();if(fs.existsSync(temporary))fs.unlinkSync(temporary);});
