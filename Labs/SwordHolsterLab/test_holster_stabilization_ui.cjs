const {chromium}=require('C:/Users/singerie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),net=require('node:net'),{spawn}=require('node:child_process');
(async()=>{
 const out=path.resolve(__dirname,'../../Saved/Diagnostics/SwordHolsterStabilization20261012');
 fs.mkdirSync(out,{recursive:true});
 const store=fs.mkdtempSync(path.join(out,'ui-')),saved=JSON.parse(fs.readFileSync(path.join(__dirname,'state.json'))),data=require('./data/motions.json');
 delete saved.parameters.holsterRotationStabilization;saved.controls.sequenceMode=true;fs.writeFileSync(path.join(store,'state.json'),JSON.stringify(saved));
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
  await page.locator('details').filter({has:page.locator('#holsterRotationStabilization')}).locator('summary').click();
  assert.equal(await page.locator('#holsterRotationStabilization').inputValue(),'0','old settings preserve pelvis attachment');
  const before=await page.evaluate(()=>({time,targets:committed.bodyTargets}));
  const save=page.waitForResponse(r=>r.url().endsWith('/state')&&r.request().method()==='POST');
  await page.locator('#holsterRotationStabilization').evaluate(el=>{el.value='.5';el.dispatchEvent(new Event('input',{bubbles:true}));});
  await page.waitForFunction(()=>!bodyPlanDirty&&!bodyPlanBusy&&model.sequence.first.o.holsterRotationStabilization===.5&&model.sequence.second.o.holsterRotationStabilization===.5);await save;
  assert.equal((await(await fetch(url+'/state')).json()).parameters.holsterRotationStabilization,.5);
  assert.equal(await page.evaluate(()=>time),before.time,'no seek');
  assert.deepEqual(await page.evaluate(()=>committed.bodyTargets),before.targets);
  await page.reload();await page.waitForFunction(()=>window.holsterLab?.ready);
  assert.equal(await page.locator('#holsterRotationStabilization').inputValue(),'0.5');
  const action=await page.locator('#action').inputValue();
  await page.locator('#action').selectOption(action==='draw'?'sheathe':'draw');
  assert.equal(await page.evaluate(()=>model.sequence.first.o.holsterRotationStabilization),.5,'environment control is shared between actions');
  await page.locator('#action').selectOption(action);
  assert.equal(await page.evaluate(()=>model.sequence.second.o.holsterRotationStabilization),.5);
  await page.evaluate(s=>restore(s),await page.evaluate(()=>state()));
  assert.equal(await page.locator('#holsterRotationStabilization').inputValue(),'0.5','snapshot/import restore');
  await page.evaluate(()=>{time=0;setPlaying(true);});
  const saveOff=page.waitForResponse(r=>r.url().endsWith('/state')&&r.request().method()==='POST');
  await page.locator('#holsterRotationStabilization').evaluate(el=>{for(const value of [.8,.2,.7,0]){el.value=value;el.dispatchEvent(new Event('input',{bubbles:true}));}});
  await page.waitForFunction(()=>!bodyPlanDirty&&!bodyPlanBusy&&model.sequence.first.o.holsterRotationStabilization===0&&model.sequence.second.o.holsterRotationStabilization===0);await saveOff;
  assert(await page.evaluate(()=>playing&&time>0),'playback continues during worker planning');
  assert.equal((await(await fetch(url+'/state')).json()).parameters.holsterRotationStabilization,0);
  assert.deepEqual(errors,[]);console.log('PASS: holster stabilization default, shared S/D worker planning, rapid edits, persistence, unchanged body targets/time and uninterrupted playback');
 }finally{if(browser)await browser.close();server.kill();}
})().catch(e=>{console.error(e);process.exitCode=1;});
