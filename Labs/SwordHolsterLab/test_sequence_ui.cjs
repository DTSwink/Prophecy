const {chromium}=require('C:/Users/singerie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),net=require('node:net'),{spawn}=require('node:child_process');
(async()=>{
 const out=path.resolve(__dirname,'../../Saved/Diagnostics/SwordSequence20261012');
 fs.mkdirSync(out,{recursive:true});
 const store=fs.mkdtempSync(path.join(out,'ui-')),saved=JSON.parse(fs.readFileSync(path.join(__dirname,'state.json'))),data=require('./data/motions.json');
 saved.controls.sequenceMode=false;saved.parameters.sheathe=true;fs.writeFileSync(path.join(store,'state.json'),JSON.stringify(saved));
 const probe=net.createServer();await new Promise(r=>probe.listen(0,'127.0.0.1',r));const port=probe.address().port;await new Promise(r=>probe.close(r));
 const server=spawn('C:/Users/singerie/Documents/Cursor/stepper/.tools/python310/python.exe',[path.join(__dirname,'backend.py'),'--port',String(port),'--state-dir',store],{windowsHide:true,stdio:'ignore'});
 const url='http://127.0.0.1:'+port;let browser;
 try{
  for(let i=0;;i++){try{if((await fetch(url+'/state')).ok)break;}catch(e){if(i>80)throw e;}await new Promise(r=>setTimeout(r,100));}
  const token='test-'+require('node:crypto').randomUUID();
  await fetch(url+'/desktop-session',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token})});
  browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',args:['--enable-webgl','--use-angle=swiftshader']});
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(url+'/?desktopSession='+token);await page.waitForFunction(()=>window.holsterLab?.ready);
  assert.deepEqual(await page.evaluate(()=>committed.bodyTargets),saved.parameters.sheatheBody.bodyTargets,'restore selects correct authored targets');
  await page.evaluate(()=>setPlaying(false));
  if(!await page.locator('#bodyTargetsPanel').isVisible())await page.locator('#openBodyTargets').click();
  const before=await page.evaluate(()=>({time,parameters:state().parameters}));
  const save=page.waitForResponse(r=>r.url().endsWith('/state')&&r.request().method()==='POST');
  await page.locator('#sequenceMode').check();await save;
  assert(await page.evaluate(()=>model.sequence?.second&&model.sequence.second.motionOffset===model.sequence.offset));
  assert.deepEqual(await page.evaluate(()=>state().parameters),before.parameters,'mode preserves tuning');
  assert.equal(await page.evaluate(()=>time),before.time,'mode does not seek');
  assert.equal(await page.locator('#timeline').getAttribute('max'),String(await page.evaluate(()=>model.playbackDuration)));
  assert.equal(await page.locator('#actionLabel').textContent(),'First action');
  assert((await page.locator('#caseTitle').textContent()).includes('S → D'));
  for(const action of ['sheathe','draw']){
   await page.evaluate(()=>window.sequenceBeforeEdit=model);
   await page.locator('#action').selectOption(action);
   assert.equal(await page.evaluate(()=>model.sequence.first.o.sheathe),action==='sheathe','selected mode starts the sequence');
   assert.equal(await page.locator('#sequenceLabel').textContent(),(action==='sheathe'?'S → D':'D → S')+' · after full return');
   if(!await page.locator('#bodyTargetsPanel').isVisible())await page.locator('#openBodyTargets').click();
   await page.locator('#bodyEndpoint').selectOption('clear');
   assert(await page.evaluate(()=>Math.abs(time-Playback.previewTime(model,0,committed.sheathe))<1e-9),'endpoint seeks selected segment');
   const expected=await page.evaluate(()=>Playback.sample(model,time).pose);
   assert.deepEqual(await page.evaluate(()=>bodyPreviewFrame.pose),expected);
  }
  // Worker body edits prepare both actions without losing assets or seeking.
  const tickBefore=await page.evaluate(()=>time);
  await page.locator('#body_spine_0').evaluate(el=>{el.value=Number(el.value)+.1;el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));});
  await page.waitForFunction(()=>!bodyPlanBusy&&!bodyPlanDirty);
  assert.equal(await page.evaluate(()=>time),tickBefore);
  assert(await page.evaluate(()=>model.sequence.second.data===motionData&&model.sequence.first.setup===equipmentSetup));
  await page.locator('#action').selectOption('sheathe');
  await page.locator('#openFKReturn').click();
  const oldOffset=await page.evaluate(()=>model.sequence.offset);
  await page.locator('#fk_duration').fill('2');await page.locator('#fk_duration').dispatchEvent('change');
  assert(await page.evaluate(old=>model.sequence.offset>old&&model.sequence.second.motionOffset===model.sequence.offset,oldOffset),'return edit reschedules D');
  await page.evaluate(()=>{seek(model.sequence.offset+.1);setPlaying(true);});
  await page.locator('#bypassCurves').setChecked(!saved.controls.bypassCurves);
  assert(await page.evaluate(()=>playing&&currentPose.diagnostics.sequenceAction==='D'),'playback continues in D');
  const persist=page.waitForResponse(r=>r.url().endsWith('/state')&&r.request().method()==='POST');
  await page.evaluate(()=>save());await persist;
  await page.locator('#action').selectOption('draw');
  const packet=await page.evaluate(()=>state());
  await page.evaluate(()=>post('/state',state()));
  await page.reload();await page.waitForFunction(()=>window.holsterLab?.ready);
  assert(await page.locator('#sequenceMode').isChecked());
  assert(await page.evaluate(()=>model.sequence.second&&model.sequence.first.o.sheathe===false),'reload preserves D first');
  await page.evaluate(s=>restore(s),packet);
  assert.equal(await page.evaluate(()=>time),packet.time,'snapshot restore retains extended time');
  await page.locator('#sequenceMode').uncheck();
  assert(await page.evaluate(()=>!model.sequence),'single action restored');
  assert.equal(await page.locator('#actionLabel').textContent(),'Action');
  assert.deepEqual(errors,[]);console.log('PASS: sequence mode, preserved profiles, continuous animation offset, extended timeline, contextual editing, worker rebuild, return reschedule, persistence/snapshot and standalone restore');
 }finally{if(browser)await browser.close();server.kill();}
})().catch(e=>{console.error(e);process.exitCode=1;});
