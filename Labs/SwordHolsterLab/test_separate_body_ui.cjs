const {chromium}=require('C:/Users/singerie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),net=require('node:net'),{spawn}=require('node:child_process');
(async()=>{
 const out=path.resolve(__dirname,'../../Saved/Diagnostics/SwordSeparateBody20261012');
 fs.mkdirSync(out,{recursive:true});
 const store=fs.mkdtempSync(path.join(out,'ui-')),saved=JSON.parse(fs.readFileSync(path.join(__dirname,'state.json'))),data=require('./data/motions.json');
 delete saved.parameters.drawBody;delete saved.parameters.sheatheBody;fs.writeFileSync(path.join(store,'state.json'),JSON.stringify(saved));
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
  assert.deepEqual(await page.evaluate(()=>committed.bodyTargets),saved.parameters.bodyTargets,'migration preserves authored targets');
  await page.evaluate(()=>setPlaying(false));
  if(!await page.locator('#bodyTargetsPanel').isVisible())await page.locator('#openBodyTargets').click();
  const original=await page.evaluate(()=>bodyProfile(committed)),originalState=await page.evaluate(()=>state());
  assert.deepEqual(originalState.parameters.drawBody,original);
  assert.deepEqual(originalState.parameters.sheatheBody,original,'legacy values cloned into both actions');
  const startingAction=await page.locator('#action').inputValue(),other=startingAction==='draw'?'sheathe':'draw';
  await page.locator('#body_spine_0').evaluate(el=>{el.value=Number(el.value)+1;el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));});
  await page.waitForFunction(()=>!bodyPlanBusy&&!bodyPlanDirty);
  await page.locator('#body_pole').evaluate(el=>{el.value=Number(el.value)-2;el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));});
  await page.waitForFunction(()=>!bodyPlanBusy&&!bodyPlanDirty);
  await page.locator('#maxElbowPoleAngularSpeed').fill('123');await page.locator('#maxElbowPoleAngularSpeed').dispatchEvent('change');
  await page.locator('#maxSpineClavicleAngularSpeed').fill('321');await page.locator('#maxSpineClavicleAngularSpeed').dispatchEvent('change');
  await page.locator('#swordRelativeSlidePole').setChecked(!original.swordRelativeSlidePole);
  await page.locator('#pelvisRotationCompensation').evaluate(el=>{el.value='.37';el.dispatchEvent(new Event('input',{bubbles:true}));});
  await page.waitForFunction(()=>!bodyPlanBusy&&!bodyPlanDirty);
  for(const [id,value] of Object.entries({maxReachSpeed:231,maxReachRotationSpeed:601,slidingSpeed:151})){await page.locator('#'+id).fill(String(value));await page.locator('#'+id).dispatchEvent('change');}
  const edited=await page.evaluate(()=>bodyProfile(committed)),beforeTime=await page.evaluate(()=>time);
  assert.notDeepEqual(edited,original);
  await page.locator('#action').selectOption(other);
  assert.deepEqual(await page.evaluate(()=>bodyProfile(committed)),original,'other action retains all original panel values');
  assert.equal(await page.evaluate(()=>time),beforeTime,'switch does not seek');
  assert((await page.locator('#bodyTargetsTitle').textContent()).includes(other==='draw'?'Drawing':'Sheathing'));
  const save=page.waitForResponse(r=>r.url().endsWith('/state')&&r.request().method()==='POST');
  await page.locator('#action').selectOption(startingAction);await save;
  assert.deepEqual(await page.evaluate(()=>bodyProfile(committed)),edited);
  const disk=await(await fetch(url+'/state')).json();
  assert.deepEqual(disk.parameters[startingAction+'Body'],edited);assert.deepEqual(disk.parameters[other+'Body'],original);
  await page.reload();await page.waitForFunction(()=>window.holsterLab?.ready);
  assert.deepEqual(await page.evaluate(()=>bodyProfile(committed)),edited,'reload retains active values');
  await page.locator('#action').selectOption(other);assert.deepEqual(await page.evaluate(()=>bodyProfile(committed)),original);
  // Both planners must use their own speeds even while the other action is selected.
  await page.locator('#sequenceMode').check();
  const plans=await page.evaluate(()=>({draw:Playback.edited(model,false).model.o,sheathe:Playback.edited(model,true).model.o}));
  for(const key of ['maxReachSpeed','maxReachRotationSpeed','slidingSpeed']){assert.equal(plans[startingAction][key],edited[key]);assert.equal(plans[other][key],original[key]);}
  assert.equal(await page.locator('#speedTitle').textContent(),(other==='draw'?'Drawing':'Sheathing')+' speeds');
  await page.locator('#sequenceMode').uncheck();
  // Import/snapshot restore must choose the selected action, not flattened legacy values.
  await page.evaluate(s=>restore(s),{...disk,parameters:{...disk.parameters,sheathe:other==='sheathe'}});
  assert.deepEqual(await page.evaluate(()=>bodyProfile(committed)),original);
  await page.evaluate(()=>{time=0;setPlaying(true);});
  await page.locator('#pelvisRotationCompensation').evaluate(el=>{el.value='.12';el.dispatchEvent(new Event('input',{bubbles:true}));});
  await page.locator('#action').selectOption(startingAction);
  await page.waitForFunction(()=>!bodyPlanBusy&&!bodyPlanDirty);
  assert.deepEqual(await page.evaluate(()=>bodyProfile(committed)),edited,'old worker cannot overwrite switched action');
  assert.equal(await page.evaluate(()=>model.o.pelvisRotationCompensation),edited.pelvisRotationCompensation);
  assert(await page.evaluate(()=>playing&&time>0),'playback continues');
  assert.deepEqual(errors,[]);console.log('PASS: legacy duplication, independent body and speed profiles, per-action sequence speeds, action labels, disk/reload/import persistence, no seek, stale worker protection and continued playback');
 }finally{if(browser)await browser.close();server.kill();}
})().catch(e=>{console.error(e);process.exitCode=1;});
