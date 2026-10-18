const {chromium}=require('C:/Users/singerie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),net=require('node:net'),crypto=require('node:crypto'),{spawn}=require('node:child_process');
(async()=>{
 const out=path.resolve(__dirname,'../../Saved/Diagnostics/ReachGrabLab20261015');fs.mkdirSync(out,{recursive:true});const store=fs.mkdtempSync(path.join(out,'test-'));
 const probe=net.createServer();await new Promise(r=>probe.listen(0,'127.0.0.1',r));const port=probe.address().port;await new Promise(r=>probe.close(r));
 const url='http://127.0.0.1:'+port,token=crypto.randomUUID();let child,browser;
 try{
  child=spawn('C:/Users/singerie/Documents/Cursor/stepper/.tools/python310/python.exe',[path.join(__dirname,'server.py'),'--port',String(port),'--state-dir',store],{windowsHide:true,stdio:'pipe'});let log='';child.stderr.on('data',d=>log+=d);
  for(let i=0;;i++){try{if((await fetch(url+'/health')).ok)break;}catch(e){if(i>60)throw Error(log||e);}await new Promise(r=>setTimeout(r,100));}
  await fetch(url+'/desktop-session',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token})});
  browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',args:['--enable-webgl','--use-angle=swiftshader']});
  const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>window.addEventListener('load',()=>{window.invalidAcquisitions=0;const update=ReachGrab.update;ReachGrab.update=(g,h,w,t)=>{const held=g.gripped;update(g,h,w,t);if(!held&&g.gripped&&(g.angle>t.grip||g.distance>=1.25||g.close<1))window.invalidAcquisitions++;};}));
  await page.goto(url+'/reach?desktopSession='+token);await page.waitForFunction(()=>window.reachLab?.ready);await page.evaluate(()=>setPlaying(false));await page.waitForFunction(()=>!pending);
  
  const run=n=>page.evaluate(async n=>{for(let i=0;i<n;i+=8)await reachLab.step(Math.min(8,n-i));return reachLab.snapshot();},n);
  let s=await run(180);assert(s.grabs.every(g=>g.gripped),'Saved defaults grip with PHAT enabled');console.log('Default',s.grabs.map(g=>({held:g.gripped,error:g.error,angle:g.angle,d:g.distance,close:g.close,contacts:g.contacts})));
  await page.screenshot({path:path.join(out,'default.png')});
  const beforeRestart=await page.evaluate(()=>reachLab.snapshot());await page.uncheck('#phat');const restarted=await page.evaluate(()=>reachLab.snapshot());assert(restarted.settings.hands.every(h=>h.grab)&&restarted.grabs.every(g=>!g.gripped&&g.active&&g.close===0));assert.deepEqual(restarted.pose,beforeRestart.pose,'Clamp toggle preserves the complete current pose');assert.deepEqual(restarted.solverState.slice(0,6),beforeRestart.solverState.slice(0,6),'Body response is retained');assert.equal(restarted.tick,beforeRestart.tick);for(let k=0;k<2;k++){assert.deepEqual(restarted.handQ[k],beforeRestart.pose[k===0?13:17].slice(3));assert.deepEqual(restarted.solverState.slice(6+k*3,9+k*3),beforeRestart.pose[k===0?13:17].slice(0,3).map(v=>v*.01));}s=await run(120);assert(s.grabs.every(g=>g.gripped),'Both manual-orientation grabs acquire with reachable orientation');assert(s.grabs.every(g=>g.contacts>=3));
  assert(s.grabs.every(g=>g.curl.some(v=>v>0&&v<1)),'Contact fits differ from full fist');
  const held=s;
  const canvas=await page.locator('#view').boundingBox(),point=await page.evaluate(()=>reachLab.projectTarget(0));
  await page.mouse.move(canvas.x+point.x,canvas.y+point.y);await page.mouse.down({button:'right'});await page.mouse.move(canvas.x+point.x+35,canvas.y+point.y-12,{steps:5});await page.mouse.up({button:'right'});
  s=await run(20);assert(s.grabs[0].gripped);assert.notDeepEqual(s.settings.hands[0].target,held.settings.hands[0].target,'RMB moves the held target');
  await page.fill('#p01','70');s=await run(12);assert(s.grabs[0].gripped);assert.deepEqual(s.grabs[0].curl,held.grabs[0].curl,'Moving a held ball reuses finger fitting');
  const attached=await page.evaluate(()=>grabs.map((g,k)=>norm(sub(ReachGrab.compose(pose[hands[k]],g.attachment).slice(0,3),g.ball.slice(0,3)))));assert(attached.every(v=>v<1e-10));
  const snap=await page.evaluate(()=>reachLab.saveSnapshot());const saved=JSON.parse(fs.readFileSync(path.join(store,'snapshots',snap.name+'.json')));
  console.log('Snapshot',snap);
  const next=await run(8);await page.evaluate(s=>reachLab.restore(s),saved);const replay=await run(8);for(const key of ['pose','solverState','grabs'])assert.deepEqual(replay[key],next[key],key+' deterministic');
  await page.uncheck('#enabled0');const releaseStart=await page.evaluate(()=>reachLab.snapshot());assert(!releaseStart.grabs[0].gripped);s=await run(15);assert.equal(s.grabs[0].close,0);assert(s.grabs[1].gripped,'Other hand stays held');
  await page.check('#enabled0');await page.locator('#ballRadius').evaluate(el=>{el.value='6';el.dispatchEvent(new Event('input',{bubbles:true}));});s=await run(180);assert.equal(s.grabs[0].radius,6);assert(s.grabs[0].gripped);assert.notDeepEqual(s.grabs[0].curl,held.grabs[0].curl,'Size changes fitting');
  await page.locator('#ballRadius').evaluate(el=>{el.value='15';el.dispatchEvent(new Event('input',{bubbles:true}));});s=await run(8);assert(s.grabs[0].error);assert(!s.grabs[0].gripped,'Invalid open clearance is rejected');
  await page.locator('#ballRadius').evaluate(el=>{el.value='3';el.dispatchEvent(new Event('input',{bubbles:true}));});await page.check('#autoPalm');assert(await page.evaluate(()=>settings.hands.every(h=>h.orientation==='surface')));s=await run(180);assert(s.grabs.every(g=>g.gripped),'Automatic contact orientation grips both balls with clamp off');
  await page.screenshot({path:path.join(out,'automatic-grab.png')});
  const geometry=await page.evaluate(()=>{
   let trials=0,maxPenetration=0;
   for(let k=0;k<2;k++)for(const radius of [1,2,3,4,6,8,10]){
    const h={...settings.hands[k],radius},g=ReachGrab.start(fingerModels[k],h,pose[hands[k]],rotationQ(h.rotation),pose[arms[k][1]].slice(0,3));
    if(g.error)continue;
    const t=ReachGrab.target(g,h.target);
    for(const l of ReachGrab.segments(fingerModels[k],g,t,1))for(let i=0;i<=4;i++)maxPenetration=Math.max(maxPenetration,radius+.65-norm(sub(add(mul(l.a,1-i*.25),mul(l.b,i*.25)),h.target)));
    trials++;
   }
   return {trials,maxPenetration};
  });assert(geometry.trials>=12);assert(geometry.maxPenetration<1e-8,'Fitted native contact samples remain outside the ball');
  await page.evaluate(()=>reachLab.publishLive());const live=await(await fetch(url+'/desktop-view')).json();assert.equal(live.displayedPose.fingerLines.flat().length,30);assert(live.state.grabs.every(g=>g.gripped));
  assert.equal(await page.evaluate(()=>window.invalidAcquisitions),0);await Promise.all([page.waitForEvent('domcontentloaded'),page.click('#refresh')]);await page.waitForFunction(()=>window.reachLab?.ready);const restored=await page.evaluate(()=>reachLab.snapshot());for(const key of ['grabs','pose','settings'])assert.deepEqual(restored[key],s[key],key+' refresh');
  await page.check('#phat');assert(await page.evaluate(()=>settings.hands.every(h=>h.grab)&&grabs.every(g=>!g.gripped&&g.active&&g.close===0)),'Clamp-on also restarts both');await page.uncheck('#autoPalm');assert(await page.evaluate(()=>settings.hands.every(h=>h.orientation==='target')));await page.check('#grab0');await page.check('#grab1');await page.fill('#r00','0');await page.fill('#r01','0');await page.fill('#r02','0');s=await run(180);assert(await page.evaluate(()=>grabs.every((g,k)=>{const q=pose[hands[k]].slice(3),limited=ReachWrist.constrain(phat.wrists[k],pose[arms[k][2]].slice(3),q);return 1-Math.abs(dot(q,limited))<1e-12;})), 'Arm compensation may now reach zero rotation; PHAT still holds');
  await page.uncheck('#phat');await page.check('#grab0');await page.fill('#p02','290');s=await run(240);assert(!s.grabs[0].gripped&&s.grabs[0].distance>3,'Unreachable target does not acquire');
  await page.uncheck('#enabled0');await page.uncheck('#enabled1');s=await run(15);const tick=s.tick;await run(8);assert.equal((await page.evaluate(()=>reachLab.snapshot())).tick,tick,'Inactive solver retires after return');
  assert.equal(await page.evaluate(()=>window.invalidAcquisitions),0,'New grips must pass original gates; already-held grips may subsequently move');assert.deepEqual(errors,[]);const receipt={passed:true,defaultGripsWithPHAT:true,attachmentError:attached,nativeFingerCount:30,geometry,snapshotContinuation:true,releaseReturn:true,resizeRefits:true,oversizeRejection:true,automaticContact:true,heldRightDrag:true,sharedAutoPalmCheckbox:true,clampToggleRestartsFromCurrentPose:true,PHATLimitsRespected:true,unreachableBlocksAcquisition:true,inactiveRetirement:true,errors};fs.writeFileSync(path.join(out,'verification.json'),JSON.stringify(receipt,null,2));console.log(JSON.stringify(receipt));
 }finally{if(browser)await browser.close();if(child?.exitCode===null)child.kill();}
})().catch(e=>{console.error(e);process.exit(1);});

