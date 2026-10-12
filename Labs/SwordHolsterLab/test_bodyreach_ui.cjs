const {chromium}=require(process.env.HARNESS_PLAYWRIGHT_MODULE||'C:/Users/singerie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),net=require('node:net'),{spawn}=require('node:child_process');
(async()=>{
 const out=path.resolve(__dirname,'../../Saved/Diagnostics/SwordBodyTargets20261012');fs.mkdirSync(out,{recursive:true});
 const store=fs.mkdtempSync(path.join(out,'persistence-'));
 const userState=fs.readFileSync(path.join(__dirname,'state.json'));
 fs.writeFileSync(path.join(store,'state.json'),userState);
 const probe=net.createServer();await new Promise(r=>probe.listen(0,'127.0.0.1',r));const port=probe.address().port;await new Promise(r=>probe.close(r));
 const server=spawn('C:/Users/singerie/Documents/Cursor/stepper/.tools/python310/python.exe',[path.join(__dirname,'backend.py'),'--port',String(port),'--state-dir',store],{windowsHide:true,stdio:'ignore'});
 const url='http://127.0.0.1:'+port;let browser;
 try{
  for(let i=0;;i++){try{if((await fetch(url+'/state')).ok)break;}catch(e){if(i>80)throw e;}await new Promise(r=>setTimeout(r,100));}
  const token='test-'+require('node:crypto').randomUUID();assert((await fetch(url+'/desktop-session',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token})})).ok);
  browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',args:['--enable-webgl','--use-angle=swiftshader']});
  const page=await browser.newPage({viewport:{width:1500,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(url+'/?desktopSession='+token);await page.waitForFunction(()=>window.holsterLab?.ready);
  if(!await page.locator('#bodyTargetsPanel').isVisible())await page.click('#openBodyTargets');assert(await page.locator('#bodyTargetsPanel').isVisible());
  assert.equal(await page.locator('#previewBodyTarget,#stopBodyPreview').count(),0);
  const original=await page.evaluate(()=>holsterLab.state());
  for(const sheathe of [true,false])for(const early of [true,false]){
   await page.evaluate(({sheathe,early})=>{const s=holsterLab.state(),key=(sheathe?'sheathe':'draw')+'Return';s.parameters={...s.parameters,sheathe,[key]:{...s.parameters[key],enabled:true,startFraction:early?.5:1}};holsterLab.restore(s);},{sheathe,early});
   for(const endpoint of ['clear','seated']){
    await page.selectOption('#bodyEndpoint',endpoint);await page.locator('#bodyEndpoint').dispatchEvent('change');
    assert(await page.evaluate(({endpoint})=>{const m=holsterLab.model(),start=endpoint===(m.o.sheathe?'clear':'seated'),expected=Math.min((start?m.plan.endTick:m.plan.slideEnd)/60,m.fkReturn.start);return Math.abs(holsterLab.state().time-expected)<1e-9;},{endpoint}),'endpoint selector snaps to endpoint or earlier return start');
    await page.evaluate(()=>holsterLab.seek(.731));
    await page.locator('#body_left_0').evaluate(el=>{el.value=String(Number(el.value)+1);el.dispatchEvent(new Event('input',{bubbles:true}));});
    await page.waitForTimeout(60);
    assert.equal(await page.evaluate(()=>holsterLab.state().time),.731,'drag preserves arbitrary paused time');
    await page.locator('#body_left_0').dispatchEvent('change');
    await page.waitForFunction(()=>!bodyPlanDirty&&bodyPreviewLast===0);
    assert.equal(await page.evaluate(()=>holsterLab.state().time),.731,'release and worker preserve paused time');
    assert.equal(await page.evaluate(()=>bodyPreviewFrame.previewTime),.731,'preview samples current time');
   }
  }
  await page.evaluate(s=>holsterLab.restore(s),original);
  assert.equal(await page.locator('#spineClavicleAngleLimit').count(),0);assert.equal(await page.locator('#maxSpineClavicleAngularSpeed').count(),1);
  assert.equal(await page.locator('#bodyRotations input[type=range]').count(),10);
  const canvas=await page.locator('#viewport').boundingBox(),panel=await page.locator('#bodyTargetsPanel').boundingBox();assert(panel.x>=canvas.x+canvas.width-1);
  await page.selectOption('#bodyEndpoint','clear');
  await page.evaluate(()=>{window.oldFrames=holsterLab.model().sourceFrames;});
  const before=await page.evaluate(()=>holsterLab.pose().axes);
  await page.locator('#body_left_1').evaluate(el=>{el.value='12';el.dispatchEvent(new Event('input',{bubbles:true}));});
  await page.waitForFunction(()=>bodyPreviewFrame!==null);await page.waitForTimeout(60);assert.equal(await page.locator('#body_left_1_number').inputValue(),'12');assert.notDeepEqual(await page.evaluate(()=>holsterLab.pose().axes),before,'live preview responds before release');
  assert(await page.evaluate(()=>window.oldFrames===holsterLab.model().sourceFrames),'no full replan during drag');
  await page.locator('#body_left_1').dispatchEvent('change');await page.waitForFunction(()=>window.oldFrames!==holsterLab.model().sourceFrames);assert(await page.evaluate(()=>window.oldFrames!==holsterLab.model().sourceFrames),'replan on release');
  await page.selectOption('#bodyEndpoint','seated');const selectedTime=await page.evaluate(()=>holsterLab.state().time);await page.fill('#body_left_1_number','-7');await page.locator('#body_left_1_number').dispatchEvent('change');await page.waitForFunction(()=>holsterLab.model().o.bodyTargets.seated.left[1]===-7);
  const targets=await page.evaluate(()=>holsterLab.state().parameters.bodyTargets);assert.equal(targets.clear.left[1],12);assert.equal(targets.seated.left[1],-7);
  assert.equal(await page.evaluate(()=>holsterLab.state().time),selectedTime,'editing does not follow a shifted endpoint');
  for(const [endpoint,value] of [['clear',-35],['seated',50]]){
   await page.selectOption('#bodyEndpoint',endpoint);await page.fill('#body_pole_number',String(value));await page.locator('#body_pole_number').dispatchEvent('change');
   await page.waitForFunction(([e,v])=>holsterLab.model().o.bodyTargets[e].pole===v,[endpoint,value]);
  }
  await page.fill('#maxElbowPoleAngularSpeed','45');await page.locator('#maxElbowPoleAngularSpeed').dispatchEvent('change');
  assert.equal(await page.evaluate(()=>holsterLab.model().o.maxElbowPoleAngularSpeed),45);
  targets.clear.pole=-35;targets.seated.pole=50;
  await page.screenshot({path:path.join(out,'body-pose-panel.png')});
  // A dense event stream produces one smoothed preview per display frame, never a trajectory rebuild.
  const drag=await page.evaluate(async()=>{
   const oldPrepare=Holster.prepare,oldPreview=Holster.previewBody;let prepares=0,previews=0,previewMs=[];
   Holster.prepare=(...args)=>{prepares++;return oldPrepare(...args);};
   Holster.previewBody=(...args)=>{const t=performance.now(),result=oldPreview(...args);previewMs.push(performance.now()-t);previews++;return result;};
   const el=document.getElementById('body_left_1'),values=[],durations=[];
   const before=holsterLab.model().sourceFrames;let smooth=false;
   for(let frame=0;frame<20;frame++){
    const t=performance.now();for(let n=0;n<12;n++){el.value=String(-7+(frame*12+n)/239*30);el.dispatchEvent(new Event('input',{bubbles:true}));}durations.push(performance.now()-t);
    await new Promise(requestAnimationFrame);values.push(bodyPreviewTargets.seated.left[1]);if(frame===0){const exact=Holster.previewBody(model,1,committed.bodyTargets,time),j=model.bodyContext.left;smooth=Holster.angle(bodyPreviewFrame.pose[j].q,exact.pose[j].q)>.01;}
   }
   const deferred=holsterLab.model().sourceFrames===before;
   el.dispatchEvent(new Event('change',{bubbles:true}));
   await new Promise(r=>setTimeout(r,700));
   const settled=bodyPreviewTargets.seated.left[1],result={events:240,prepares,previews,deferred,smooth,settled,maxInputBatchMs:Math.max(...durations),maxPreviewMs:Math.max(...previewMs)};
   Holster.prepare=oldPrepare;Holster.previewBody=oldPreview;return result;
  });
  assert.equal(drag.prepares,0,'full planning stays off main thread');assert(drag.deferred&&drag.smooth,'coalesced smoothed preview');assert(drag.previews<100,'no render per input event');assert.equal(drag.settled,23,'smoothing settles exactly on saved target');
  await page.waitForFunction(()=>holsterLab.model().o.bodyTargets.seated.left[1]===23);
  // Starting a second edit invalidates an older worker response.
  await page.evaluate(()=>{const el=document.getElementById('body_left_1');for(const value of [5,9]){el.value=value;el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));}});
  await page.waitForFunction(()=>holsterLab.model().o.bodyTargets.seated.left[1]===9);
  fs.writeFileSync(path.join(out,'live-drag.json'),JSON.stringify(drag,null,2));

  await page.waitForFunction(()=>!bodyPlanDirty&&bodyPreviewLast===0);
  const match=await page.evaluate(()=>{const expected=Holster.sample(model,time);return Math.max(...model.arm.map(j=>Holster.angle(bodyPreviewFrame.pose[j].q,expected.pose[j].q)));});
  assert(match<1e-5,'settled preview uses actual playback elbow and FK arm');
  const handoff=await page.evaluate(()=>{const t=time,prior=bodyPreviewFrame.pose.map(v=>({...v}));holsterLab.setPlaying(true);updateBodyPreview(performance.now());const actual=Holster.sample(model,time);return {dt:time-t,error:Math.max(...model.arm.map(j=>Holster.angle(prior[j].q,actual.pose[j].q))),cleared:bodyPreview===null};});
  assert(handoff.cleared&&handoff.dt===0&&handoff.error<1e-5,'Play starts from the exact previewed frame');

  const running=await page.evaluate(()=>{
   holsterLab.seek(.731);holsterLab.setPlaying(true);document.getElementById('speed').value='1';
   const el=document.getElementById('body_left_2');el.value='3';el.dispatchEvent(new Event('input',{bubbles:true}));
   cancelAnimationFrame(frameHandle);frameHandle=null;tick(lastTick+100);cancelAnimationFrame(frameHandle);frameHandle=null;
   const during=time;el.dispatchEvent(new Event('change',{bubbles:true}));return {during};
  });
  assert(Math.abs(running.during-.831)<1e-9,'playback advances normally during drag');
  await page.waitForFunction(()=>!bodyPlanDirty);
  assert.equal(await page.evaluate(()=>holsterLab.state().time),running.during,'worker does not reset the running clock');
  await page.evaluate(()=>{tick(lastTick+100);cancelAnimationFrame(frameHandle);frameHandle=null;});
  assert(Math.abs(await page.evaluate(()=>holsterLab.state().time)-.931)<1e-9,'playback continues after worker completion');
  assert.equal(await page.locator('#play').textContent(),'Pause','editing does not stop playback');
  await page.locator('#body_left_2').focus();await page.keyboard.press('Space');assert.equal(await page.locator('#play').textContent(),'Play','playback keys remain global');
  const v=await page.locator('#body_left_2').inputValue();await page.keyboard.press('ArrowRight');assert.equal(await page.locator('#body_left_2').inputValue(),v,'arrows step playback without changing target');
  for(const action of ['draw','sheathe']){await page.selectOption('#action',action);assert.deepEqual(await page.evaluate(()=>holsterLab.state().parameters.bodyTargets.clear),targets.clear,'targets shared across D/S');}
  await page.click('#openFKReturn');assert(await page.locator('#fkReturnPanel').isVisible());assert(!await page.locator('#bodyTargetsPanel').isVisible());
  await page.click('#openBodyTargets');assert(!await page.locator('#fkReturnPanel').isVisible());
  await page.waitForTimeout(450);
  const expected=await page.evaluate(()=>holsterLab.state()),disk=JSON.parse(fs.readFileSync(path.join(store,'state.json'),'utf8'));assert.deepEqual(disk.parameters.bodyTargets,expected.parameters.bodyTargets);
  await page.reload();await page.waitForFunction(()=>window.holsterLab?.ready);assert(await page.locator('#bodyTargetsPanel').isVisible());assert.equal(await page.locator('#bodyEndpoint').inputValue(),'seated');assert.deepEqual(await page.evaluate(()=>holsterLab.state().parameters.bodyTargets),expected.parameters.bodyTargets);
  await page.evaluate(async()=>{await holsterLab.snapshot();});
  const snaps=fs.readdirSync(path.join(store,'snapshots')).filter(x=>x.endsWith('.json'));assert.equal(snaps.length,1);assert.deepEqual(JSON.parse(fs.readFileSync(path.join(store,'snapshots',snaps[0]),'utf8')).parameters.bodyTargets,expected.parameters.bodyTargets);
  for(const width of [1100,1000]){await page.setViewportSize({width,height:850});const button=await page.locator('#openBodyTargets').boundingBox();assert(button.x>=0&&button.x+button.width<=width);}
  assert.deepEqual(await page.evaluate(()=>holsterLab.errors),[]);assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(out,'ui.json'),JSON.stringify({passed:true,persistence:true,preview:true,keyboard:true,desktopStateUntouched:fs.readFileSync(path.join(__dirname,'state.json')).equals(userState),errors},null,2));
  console.log('PASS: right panel, both saved endpoints, live preview, release-only planning, D/S sharing, keyboard/playback, disk/reload/snapshot persistence.');
 }finally{if(browser)await browser.close();server.kill();}
})().catch(e=>{console.error(e);process.exitCode=1;});
