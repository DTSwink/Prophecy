const {chromium}=require(process.env.HARNESS_PLAYWRIGHT_MODULE||'C:/Users/singerie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),net=require('node:net'),{spawn}=require('node:child_process');
(async()=>{
 const out=process.env.HARNESS_OUTPUT_DIR||path.resolve(__dirname,'../../Saved/Diagnostics/ReturnIK20261014/ui');fs.mkdirSync(out,{recursive:true});
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
  assert(await page.locator('#fkArmIK').isVisible());
  assert.equal(await page.locator('#fk_armIKEnabled').isChecked(),false);
  assert.equal(await page.locator('#fk_armIKStart').inputValue(),'0');
  assert.equal(await page.locator('#fk_armIKEnd').inputValue(),'0.25');
  const edit=async(id,value)=>page.locator('#fk_'+id).evaluate((el,v)=>{el.value=String(v);el.dispatchEvent(new Event('change',{bubbles:true}));},value);
  await page.check('#fk_armIKEnabled');await edit('armIKStart',.2);await edit('armIKEnd',.6);
  await page.evaluate(()=>{holsterLab.seek(.5);holsterLab.setPlaying(true);});
  await edit('armIKEnd',.7);assert.equal(await page.locator('#play').textContent(),'Pause');
  await page.evaluate(()=>holsterLab.setPlaying(false));
  assert(await page.evaluate(()=>(holsterLab.model().armReturn||holsterLab.model().fkReturn).armIK));
  assert((await page.locator('#fkArmIKTiming').textContent()).includes('Blend duration:'));
  await page.selectOption('#action','sheathe');assert(await page.locator('#fkArmIK').isVisible());
  assert.equal(await page.locator('#fk_armIKEnabled').isChecked(),false);
  await page.check('#fk_armIKEnabled');await edit('armIKStart',.4);await edit('armIKEnd',.8);
  await page.selectOption('#action','draw');assert.equal(await page.locator('#fk_armIKStart').inputValue(),'0.2');
  await page.waitForTimeout(450);const saved=await page.evaluate(()=>holsterLab.state());
  await page.reload();await page.waitForFunction(()=>holsterLab?.ready);
  assert.equal(await page.locator('#fk_armIKEnd').inputValue(),'0.7');
  assert.equal(await page.locator('#fk_armIKEnabled').isChecked(),true);
  await page.uncheck('#fk_armIKEnabled');assert(!(await page.evaluate(()=>(holsterLab.model().armReturn||holsterLab.model().fkReturn).armIK)));
  await page.evaluate(s=>holsterLab.restore(JSON.parse(JSON.stringify(s))),saved);
  assert.equal(await page.locator('#fk_armIKEnabled').isChecked(),true);
  await page.check('#noCheat');assert(await page.evaluate(()=>(holsterLab.model().armReturn||holsterLab.model().fkReturn).armIK));
  await page.evaluate(()=>{const m=holsterLab.model(),r=m.armReturn||m.fkReturn;holsterLab.seek(r.start+r.timing.duration*.5);});
  await page.screenshot({path:path.join(out,'return-ik.png')});
  assert.deepEqual(errors,[]);assert.deepEqual(await page.evaluate(()=>holsterLab.errors),[]);
  console.log('PASS: default-off FK/IK window, independent D/S, uninterrupted playback, disable, disk reload, JSON restore and both planners.');
 }finally{if(browser)await browser.close();server.kill();}
})().catch(e=>{console.error(e);process.exitCode=1;});
