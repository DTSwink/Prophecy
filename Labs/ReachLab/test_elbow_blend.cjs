const {chromium}=require('C:/Users/singerie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),net=require('node:net'),crypto=require('node:crypto'),{spawn}=require('node:child_process');
(async()=>{
 const out=path.resolve(__dirname,'../../Saved/Diagnostics/ReachElbowBlend20261016');
 const store=fs.mkdtempSync(path.join(out,'test-')),probe=net.createServer();await new Promise(r=>probe.listen(0,'127.0.0.1',r));const port=probe.address().port;await new Promise(r=>probe.close(r));
 const child=spawn('C:/Users/singerie/Documents/Cursor/stepper/.tools/python310/python.exe',[path.join(__dirname,'server.py'),'--port',String(port),'--state-dir',store],{windowsHide:true,stdio:'pipe',env:{...process.env,REACH_KERNEL_DLL:path.join(out,'reach.dll')}});
 let browser;try{
 const url=`http://127.0.0.1:${port}`,token=crypto.randomUUID();let log='';child.stderr.on('data',d=>log+=d);
 for(let i=0;;i++){try{if((await fetch(url+'/health')).ok)break;}catch(e){if(i>60)throw Error(log||e);}await new Promise(r=>setTimeout(r,100));}
 await fetch(url+'/desktop-session',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token})});
 browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 const page=await browser.newPage({viewport:{width:1440,height:960}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(url+'/reach?desktopSession='+token);await page.waitForFunction(()=>reachLab.ready);await page.evaluate(async()=>{setPlaying(false);await settled();});
 assert.equal(await page.locator('#elbowDownBlend').inputValue(),'1');
 const requests=[];page.on('request',r=>{if(r.url().endsWith('/step'))requests.push(r.postDataJSON());});
 const trials=await page.evaluate(async()=>{
 const trials=[];
 for(const blend of [0,.5,1]){
 settings=defaults();settings.elbowDownBlend=blend;settings.hands.forEach(h=>h.orientation='surface');resetPose();prepareGrabs();
 for(let i=0;i<240;i++)await step(1);
 trials.push({blend,held:grabs.map(g=>g.gripped),elbows:[pose[12].slice(0,3),pose[16].slice(0,3)]});
 }
 settings.elbowDownBlend=.37;const snap=snapshot();settings.elbowDownBlend=0;await reachLab.restore(snap);if(settings.elbowDownBlend!==.37)throw Error('snapshot');resetPose();if(settings.elbowDownBlend!==.37)throw Error('reset');syncControls();
 if(sanitize({}).elbowDownBlend!==1||sanitize({elbowDownBlend:-1}).elbowDownBlend!==0||sanitize({elbowDownBlend:2}).elbowDownBlend!==1)throw Error('migration');
 await saveSettings();await saveSession();return trials;
 });
 assert(trials.every(t=>t.held.every(Boolean)));assert(requests.some(r=>r.elbowDownBlend===0)&&requests.some(r=>r.elbowDownBlend===.5)&&requests.some(r=>r.elbowDownBlend===1));
 await page.reload();await page.waitForFunction(()=>reachLab.ready);assert.equal(await page.locator('#elbowDownBlend').inputValue(),'0.37');
 await page.locator('#elbowDownBlend').fill('0.62');await page.locator('#elbowDownBlend').dispatchEvent('input');assert.equal(await page.evaluate(()=>settings.elbowDownBlend),.62);assert.equal(await page.locator('#elbowDownBlendValue').textContent(),'0.62');
 const a=await page.locator('#syncRotation').boundingBox(),b=await page.locator('#elbowDownBlend').boundingBox();assert(b.y>a.y+a.height);await page.screenshot({path:path.join(out,'slider.png')});assert.deepEqual(errors,[]);
 const report={passed:true,trials,persistence:true,belowSync:true,errors};fs.writeFileSync(path.join(out,'ui-verification.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
 }finally{if(browser)await browser.close();child.kill();}
})().catch(e=>{console.error(e);process.exitCode=1;});
