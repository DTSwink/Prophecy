const {chromium}=require(process.env.HARNESS_PLAYWRIGHT_MODULE||'C:/Users/singerie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),net=require('node:net'),{spawn}=require('node:child_process');
(async()=>{
 const out=process.env.HARNESS_OUTPUT_DIR||path.resolve(__dirname,'../../Saved/Diagnostics/DrawHandRootReturn20261014/ui');fs.mkdirSync(out,{recursive:true});
 const store=fs.mkdtempSync(path.join(out,'persistence-'));
 const probe=net.createServer();await new Promise(r=>probe.listen(0,'127.0.0.1',r));const port=probe.address().port;await new Promise(r=>probe.close(r));
 const server=spawn('C:/Users/singerie/Documents/Cursor/stepper/.tools/python310/python.exe',[path.join(__dirname,'backend.py'),'--port',String(port),'--state-dir',store],{windowsHide:true,stdio:'ignore'});
 const url='http://127.0.0.1:'+port;let browser;
 try{
  for(let i=0;;i++){try{if((await fetch(url+'/state')).ok)break;}catch(e){if(i>80)throw e;}await new Promise(r=>setTimeout(r,100));}
  const token='test-'+require('node:crypto').randomUUID();
  assert((await fetch(url+'/desktop-session',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token})})).ok);
  browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',args:['--enable-webgl','--use-angle=swiftshader']});
  const page=await browser.newPage({viewport:{width:1500,height:1050}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(url+'/?desktopSession='+token);await page.waitForFunction(()=>window.holsterLab?.ready);


  await page.selectOption('#action','draw');await page.click('#openFKReturn');
  assert(await page.locator('#fkHandRotationControl').isVisible());
  assert.equal(await page.locator('#fk_handRotationFKAlpha').inputValue(),'1');
  await page.evaluate(()=>{holsterLab.seek(.5);holsterLab.setPlaying(true);});
  await page.locator('#fk_handRotationFKAlpha').evaluate(el=>{el.value='0.35';el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));});
  assert.equal(await page.locator('#play').textContent(),'Pause');
  assert.equal(await page.locator('#fkHandRotationValue').textContent(),'0.35');
  assert.equal(await page.evaluate(()=>holsterLab.state().parameters.drawReturn.handRotationFKAlpha),.35);
  const t=await page.evaluate(()=>holsterLab.state().time);await page.waitForFunction(t=>holsterLab.state().time>t+.02,t);
  await page.evaluate(()=>holsterLab.setPlaying(false));
  await page.selectOption('#action','sheathe');assert(!(await page.locator('#fkHandRotationControl').isVisible()));
  assert.equal(await page.evaluate(()=>holsterLab.state().parameters.sheatheReturn.handRotationFKAlpha),1);
  await page.selectOption('#action','draw');assert.equal(await page.locator('#fk_handRotationFKAlpha').inputValue(),'0.35');
  const saved=await page.evaluate(()=>holsterLab.state());await page.waitForTimeout(400);await page.reload();await page.waitForFunction(()=>holsterLab?.ready);
  assert.equal(await page.locator('#fk_handRotationFKAlpha').inputValue(),'0.35');
  await page.locator('#fk_handRotationFKAlpha').evaluate(el=>{el.value='0';el.dispatchEvent(new Event('change',{bubbles:true}));});
  assert.equal(await page.evaluate(()=>holsterLab.model().armReturn.options.handRotationFKAlpha),0);
  await page.evaluate(s=>holsterLab.restore(JSON.parse(JSON.stringify(s))),saved);
  assert.equal(await page.locator('#fk_handRotationFKAlpha').inputValue(),'0.35');
  await page.check('#noCheat');assert.equal(await page.evaluate(()=>holsterLab.model().armReturn.options.handRotationFKAlpha),.35);
  await page.evaluate(()=>holsterLab.seek(holsterLab.model().plan.slideEnd/60+.2));
  await page.screenshot({path:path.join(out,'hand-rotation.png')});
  assert.deepEqual(errors,[]);assert.deepEqual(await page.evaluate(()=>holsterLab.errors),[]);
  console.log('PASS: D-only hand-rotation alpha, endpoints, live playback, action switching, disk reload, JSON restore and both planners.');
 }finally{if(browser)await browser.close();server.kill();}
})().catch(e=>{console.error(e);process.exitCode=1;});
