const {chromium}=require('C:/Users/singerie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),net=require('node:net'),{spawn}=require('node:child_process');
(async()=>{
 const out=path.resolve(__dirname,'../../Saved/Diagnostics/LocomotionCapture20261012');
 const store=fs.mkdtempSync(path.join(out,'ui-')),saved=JSON.parse(fs.readFileSync(path.join(__dirname,'state.json'))),data=require('./data/motions.json');
 saved.sourceHash=data.previousSourceHashes[0];fs.writeFileSync(path.join(store,'state.json'),JSON.stringify(saved));
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
  for(const motion of ['walk','run']){
   await page.click('#motionTab');await page.selectOption('#motion',motion);
   assert.equal(await page.evaluate(()=>model.o.motion),motion);
   assert((await page.locator('#caseSubtitle').textContent()).includes(motion==='run'?'Run forward':'Walk forward'));
   await page.waitForResponse(r=>r.url().endsWith('/state')&&r.request().method()==='POST');assert.equal((await(await fetch(url+'/state')).json()).parameters.motion,motion);
   await page.reload();await page.waitForFunction(()=>window.holsterLab?.ready);
   assert.equal(await page.locator('#motion').inputValue(),motion,'selection survives reload');
  }
  // Old exact-pose snapshots retain their source mismatch protection.
  assert(await page.evaluate(s=>{try{holsterLab.restore(s);return false;}catch(e){return e.message.includes('different source');}},saved));
  assert.deepEqual(errors,[]);console.log('PASS: settings migration, walk/run selection, persistence, old snapshot guard, no runtime errors');
 }finally{if(browser)await browser.close();server.kill();}
})().catch(e=>{console.error(e);process.exitCode=1;});
