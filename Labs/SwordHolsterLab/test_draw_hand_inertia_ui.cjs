const {chromium}=require('C:/Users/singerie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),net=require('node:net'),{spawn}=require('node:child_process');
(async()=>{
 const out=path.resolve(__dirname,'../../Saved/Diagnostics/SwordDrawHandInertia20261012');
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
  await page.locator('#action').selectOption('draw');
  if(!await page.locator('#fkReturnPanel').isVisible())await page.locator('#openFKReturn').click();
  await page.locator('#fkBones').evaluate(el=>el.parentElement.open=true);
  assert.equal(await page.locator('#fk_bone_hand').inputValue(),'1','old settings enable drawing hand inertia');
  assert(await page.evaluate(()=>{const ret=model.armReturn||model.fkReturn;return ret.model.inertial[model.arm[2]];}));
  await page.evaluate(()=>{time=0;setPlaying(true);});
  const save=page.waitForResponse(r=>r.url().endsWith('/state')&&r.request().method()==='POST');
  await page.locator('#fk_bone_hand').fill('0.4');await page.locator('#fk_bone_hand').dispatchEvent('change');await save;
  assert(await page.evaluate(()=>playing),'editing does not pause');
  assert.equal((await(await fetch(url+'/state')).json()).parameters.drawReturn.boneInertia.hand,.4);
  await page.locator('#action').selectOption('sheathe');
  assert(!await page.locator('#fk_bone_hand').isVisible(),'drawing-only control');
  assert(await page.evaluate(()=>{const ret=model.armReturn||model.fkReturn;return !ret.model.inertial[model.arm[2]];}));
  const saveDraw=page.waitForResponse(r=>r.url().endsWith('/state')&&r.request().method()==='POST');
  await page.locator('#action').selectOption('draw');await saveDraw;
  assert.equal(await page.locator('#fk_bone_hand').inputValue(),'0.4');
  await page.reload();await page.waitForFunction(()=>window.holsterLab?.ready);
  assert.equal(await page.locator('#fk_bone_hand').inputValue(),'0.4','reload');
  const snapshot=await page.evaluate(()=>state());
  await page.evaluate(s=>restore(s),snapshot);
  assert.equal(await page.locator('#fk_bone_hand').inputValue(),'0.4','snapshot/import');
  assert.deepEqual(errors,[]);console.log('PASS: hand inertia default migration, drawing-only control, disk/reload/snapshot persistence and continued playback');
 }finally{if(browser)await browser.close();server.kill();}
})().catch(e=>{console.error(e);process.exitCode=1;});
