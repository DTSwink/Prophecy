const {chromium}=require('C:/Users/singerie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),net=require('node:net'),{spawn}=require('node:child_process');
(async()=>{
 const out=path.resolve(__dirname,'../../Saved/Diagnostics/NoCheatGrip20261012');fs.mkdirSync(out,{recursive:true});
 const store=fs.mkdtempSync(path.join(out,'ui-')),saved=JSON.parse(fs.readFileSync(path.join(__dirname,'state.json')));
 saved.controls.sequenceMode=false;fs.writeFileSync(path.join(store,'state.json'),JSON.stringify(saved));
 const probe=net.createServer();await new Promise(r=>probe.listen(0,'127.0.0.1',r));const port=probe.address().port;await new Promise(r=>probe.close(r));
 const server=spawn('C:/Users/singerie/Documents/Cursor/stepper/.tools/python310/python.exe',[path.join(__dirname,'backend.py'),'--port',String(port),'--state-dir',store],{windowsHide:true,stdio:'ignore'});
 const url='http://127.0.0.1:'+port;let browser;
 try{
  for(let i=0;;i++){try{if((await fetch(url+'/state')).ok)break;}catch(e){if(i>80)throw e;}await new Promise(r=>setTimeout(r,100));}
  const token='test-'+require('node:crypto').randomUUID();await fetch(url+'/desktop-session',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token})});
  browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',args:['--enable-webgl','--use-angle=swiftshader']});
  const page=await browser.newPage({viewport:{width:1500,height:950}}),errors=[];page.on('pageerror',e=>{errors.push(e.message);console.error('PAGE',e.message);});page.on('console',m=>{if(m.type()==='error')console.error('CONSOLE',m.text());});
  await page.goto(url+'/?desktopSession='+token);await page.waitForFunction(()=>window.holsterLab?.ready);
  await page.evaluate(()=>{setPlaying(false);seek(.5);});const before=await page.evaluate(()=>state());
  await page.check('#noCheat');assert(await page.evaluate(()=>model.online));assert.equal(await page.evaluate(()=>time),before.time);
  const after=await page.evaluate(()=>state());delete after.parameters.noCheat;delete before.parameters.noCheat;assert.deepEqual(after.parameters,before.parameters,'other settings unchanged');
  await page.selectOption('#motion','run');await page.evaluate(()=>setPlaying(true));
  await page.check('#bypassCurves');assert(await page.evaluate(()=>playing&&model.online),'curve bypass keeps playback and mode');
  await page.check('#sequenceMode');assert(await page.evaluate(()=>model.sequence.first.online&&model.sequence.second?.online));
  await page.selectOption('#action','draw');assert(await page.evaluate(()=>model.sequence.first.o.sheathe===false&&model.sequence.second?.online));
  await page.evaluate(()=>{setPlaying(false);post('/state',state());});await page.waitForTimeout(500);
  await page.reload();await page.waitForFunction(()=>window.holsterLab?.ready);assert(await page.isChecked('#noCheat'));
  assert(await page.evaluate(()=>model.sequence.first.online),'mode restored after reload');
  // Same background worker as body-pose sliders; no solver during rendering.
  await page.evaluate(()=>{committed={...committed,pelvisRotationCompensation:.8};bodyPlanDirty=true;bodyPlanVersion++;buildBodyPlan();});
  await page.waitForFunction(()=>!bodyPlanBusy&&!bodyPlanDirty);assert(await page.evaluate(()=>model.sequence.second?.online));
  await page.uncheck('#sequenceMode');await page.locator('#noCheat').scrollIntoViewIfNeeded();
  await page.evaluate(()=>seek(model.plan.endTick/60));await page.screenshot({path:path.join(out,'no-cheat-ui.png')});
  await page.uncheck('#noCheat');assert(await page.evaluate(()=>!model.online),'D reference planner restored');
  assert.equal(await page.locator('#drawReachIK').count(),0,'IK trial removed');
  assert.deepEqual(errors,[]);assert.deepEqual(await page.evaluate(()=>runtimeErrors),[]);
  console.log('PASS: checkbox, no seek, independent settings, curves, both-action sequence, worker, persistence/reload, original mode. Isolated state only.');
 }finally{if(browser)await browser.close();server.kill();}
})().catch(e=>{console.error(e);process.exitCode=1;});
