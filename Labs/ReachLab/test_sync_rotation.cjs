const {chromium}=require('C:/Users/singerie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),net=require('node:net'),crypto=require('node:crypto'),{spawn}=require('node:child_process');
(async()=>{
 const out=path.resolve(__dirname,'../../Saved/Diagnostics/ReachSyncRotation20261016');fs.mkdirSync(out,{recursive:true});
 const store=fs.mkdtempSync(path.join(out,'test-')),probe=net.createServer();await new Promise(r=>probe.listen(0,'127.0.0.1',r));const port=probe.address().port;await new Promise(r=>probe.close(r));
 const child=spawn('C:/Users/singerie/Documents/Cursor/stepper/.tools/python310/python.exe',[path.join(__dirname,'server.py'),'--port',String(port),'--state-dir',store],{windowsHide:true,stdio:'pipe'});
 let browser;try{
  const url=`http://127.0.0.1:${port}`,token=crypto.randomUUID();
  for(let i=0;;i++){try{if((await fetch(url+'/health')).ok)break;}catch(e){if(i>60)throw e;}await new Promise(r=>setTimeout(r,100));}
  await fetch(url+'/desktop-session',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token})});
  browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
  const page=await browser.newPage({viewport:{width:1440,height:960}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(url+'/reach?desktopSession='+token);await page.waitForFunction(()=>reachLab.ready);await page.evaluate(async()=>{setPlaying(false);await settled();});
  assert.equal(await page.locator('#syncRotation').inputValue(),'0');
  const result=await page.evaluate(async()=>{
   const run=async n=>{for(let i=0;i<n;i++)await step(1);};
   const setup=(sync,phatOn=false)=>{settings=defaults();settings.syncRotation=sync;settings.phat=phatOn;settings.hands.forEach(h=>{h.orientation='surface';h.speed=60;h.rotationSpeed=720;});resetPose();prepareGrabs();};
   // Compare the complete zero-setting trajectory with the exact previous rule.
   setup(0);const start=snapshot();await run(45);const zero=snapshot();await reachLab.restore(start);
   const current=rotationFraction;rotationFraction=(k,a)=>a>1e-8?Math.min(1,settings.hands[k].rotationSpeed/60/a):1;
   await run(45);const legacy=snapshot();rotationFraction=current;
   const zeroIdentical=['pose','grabs','solverState'].every(k=>JSON.stringify(zero[k])===JSON.stringify(legacy[k]));
   const trials=[];
   for(const sync of [0,.5,1]){
    setup(sync);const samples=[];let maxAngleStep=0;
    for(let i=0;i<150;i++){const old=copy(handQ);await step(1);maxAngleStep=Math.max(maxAngleStep,...handQ.map((q,k)=>angle(q,old[k])));samples.push(grabs.map(g=>({distance:g.distance,angle:g.angle,held:g.gripped})));}
    trials.push({sync,maxAngleStep,hands:[0,1].map(k=>({positionFrame:samples.findIndex(s=>s[k].distance<1e-5),rotationFrame:samples.findIndex(s=>s[k].angle<1e-4),held:samples.at(-1)[k].held})),samples});
   }
   // Mid-reach retargeting and snapshots use current distance, with no hidden timer.
   setup(1);await run(12);settings.hands[0].target[1]+=12;await run(8);const mid=snapshot();await run(16);const next=snapshot();await reachLab.restore(mid);await run(16);
   const deterministic=JSON.stringify(next.pose)===JSON.stringify(pose)&&JSON.stringify(next.grabs)===JSON.stringify(grabs);await run(180);const movedHeld=grabs.every(g=>g.gripped);
   // Clamp remains authoritative and acquisitions keep the existing gates.
   setup(1,true);let maxLimitError=0,badAcquisitions=0;
   for(let i=0;i<360;i++){const held=grabs.map(g=>g.gripped);await step(1);for(let k=0;k<2;k++){
    const q=pose[hands[k]].slice(3),limited=ReachWrist.constrain(phat.wrists[k],pose[arms[k][2]].slice(3),q);maxLimitError=Math.max(maxLimitError,1-Math.abs(dot(q,limited)));
    const g=grabs[k];if(!held[k]&&g.gripped&&(g.distance>=1.25||g.angle>settings.grip||g.close<1))badAcquisitions++;
   }}
   const clampedHeld=grabs.every(g=>g.gripped);settings.syncRotation=.65;resetPose();const resetPreserves=settings.syncRotation===.65;
   const saved=snapshot();settings.syncRotation=0;await reachLab.restore(saved);const snapshotPreserves=settings.syncRotation===.65;syncControls();await saveSettings();await saveSession();
   return {zeroIdentical,trials,deterministic,movedHeld,maxLimitError,badAcquisitions,clampedHeld,resetPreserves,snapshotPreserves,migration:sanitize({schema:2}).syncRotation,clampedInput:sanitize({syncRotation:4}).syncRotation};
  });
  fs.writeFileSync(path.join(out,'trial.json'),JSON.stringify(result,null,2));
  assert(result.zeroIdentical);assert(result.trials.every(t=>t.maxAngleStep<=12.00001&&t.hands.every(h=>h.held)));
  assert(result.trials[2].hands.every(h=>Math.abs(h.positionFrame-h.rotationFrame)<=1),'Full sync must finish with reachable translation');
  assert(result.trials[0].hands.every((h,k)=>h.rotationFrame<result.trials[2].hands[k].rotationFrame));
  assert(result.deterministic&&result.movedHeld&&result.clampedHeld&&result.resetPreserves&&result.snapshotPreserves);assert(result.maxLimitError<1e-12&&result.badAcquisitions===0);assert(result.migration===0&&result.clampedInput===1);
  await page.reload();await page.waitForFunction(()=>reachLab.ready);await page.evaluate(async()=>{setPlaying(false);await settled();});assert.equal(await page.locator('#syncRotation').inputValue(),'0.65');
  await page.locator('#syncRotation').fill('0.37');await page.locator('#syncRotation').dispatchEvent('input');assert.equal(await page.evaluate(()=>settings.syncRotation),.37);assert.equal(await page.locator('#syncRotationValue').textContent(),'0.37');
  await page.evaluate(async()=>{await saveSettings();await saveSession();});await page.reload();await page.waitForFunction(()=>reachLab.ready);assert.equal(await page.locator('#syncRotation').inputValue(),'0.37');
  const slider=await page.locator('#syncRotation').boundingBox(),aside=await page.locator('aside').boundingBox();assert(slider.x>=aside.x&&slider.x+slider.width<=aside.x+aside.width);
  await page.screenshot({path:path.join(out,'slider.png')});assert.deepEqual(errors,[]);
  const report={...result,trials:result.trials.map(({samples,...r})=>r),passed:true,persistent:true,errors};fs.writeFileSync(path.join(out,'verification.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
 }finally{if(browser)await browser.close();child.kill();}
})().catch(e=>{console.error(e);process.exitCode=1;});
