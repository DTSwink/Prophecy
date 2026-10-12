const {chromium}=require('C:/Users/singerie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),net=require('node:net'),{spawn}=require('node:child_process');
(async()=>{
 const out=path.resolve(__dirname,'../../Saved/Diagnostics/SwordRelativePole20261012');
 fs.mkdirSync(out,{recursive:true});
 const store=fs.mkdtempSync(path.join(out,'ui-')),saved=JSON.parse(fs.readFileSync(path.join(__dirname,'state.json'))),data=require('./data/motions.json');
 saved.parameters.swordRelativeSlidePole=false;fs.writeFileSync(path.join(store,'state.json'),JSON.stringify(saved));
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
  assert.equal(await page.locator('#swordRelativeSlidePole').isChecked(),false);
  const before=await page.evaluate(()=>({time,targets:committed.bodyTargets}));
  const save=page.waitForResponse(r=>r.url().endsWith('/state')&&r.request().method()==='POST');
  await page.locator('#swordRelativeSlidePole').check();await save;
  assert.equal((await(await fetch(url+'/state')).json()).parameters.swordRelativeSlidePole,true);
  assert.equal(await page.evaluate(()=>time),before.time,'no timeline seek');
  assert.deepEqual(await page.evaluate(()=>committed.bodyTargets),before.targets,'targets unchanged');
  assert(await page.evaluate(()=>model.o.swordRelativeSlidePole&&model.poleGuides.keys.some(k=>k.swordDown)));
  await page.reload();await page.waitForFunction(()=>window.holsterLab?.ready);
  assert(await page.locator('#swordRelativeSlidePole').isChecked(),'saved across reload');
  const action=await page.locator('#action').inputValue();
  await page.locator('#action').selectOption(action==='draw'?'sheathe':'draw');
  assert.equal(await page.evaluate(()=>model.o.swordRelativeSlidePole),false,'other action keeps its own pole mode');
  await page.locator('#action').selectOption(action);
  assert(await page.evaluate(()=>model.o.swordRelativeSlidePole));
  await page.evaluate(()=>{time=0;setPlaying(true);});
  const prior=await page.evaluate(()=>time);
  const saveOff=page.waitForResponse(r=>r.url().endsWith('/state')&&r.request().method()==='POST');
  await page.locator('#swordRelativeSlidePole').uncheck();await saveOff;
  assert(await page.evaluate(t=>playing&&time>t,prior),'toggle does not stop playback');
  assert.equal((await(await fetch(url+'/state')).json()).parameters.swordRelativeSlidePole,false);
  assert.deepEqual(errors,[]);console.log('PASS: pole checkbox, independent D/S, disk/reload persistence, untouched targets/time, uninterrupted playback, no runtime errors');
 }finally{if(browser)await browser.close();server.kill();}
})().catch(e=>{console.error(e);process.exitCode=1;});
