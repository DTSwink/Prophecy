const {chromium}=require(process.env.HARNESS_PLAYWRIGHT_MODULE||'C:/Users/singerie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),net=require('node:net'),{spawn}=require('node:child_process');
(async()=>{
 const out=process.env.HARNESS_OUTPUT_DIR||path.resolve(__dirname,'../../Saved/Diagnostics/FKReturnCurve20261014/ui');fs.mkdirSync(out,{recursive:true});
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

  await page.click('#openFKReturn');
  const linear=await page.evaluate(()=>Retime.linear()),profiles={};
  for(const action of ['draw','sheathe']){
   await page.selectOption('#action',action);
   const host=page.locator('#fkReturnCurveEditor');
   assert.equal(await host.locator('[data-point]').count(),4);
   await host.scrollIntoViewIfNeeded();
   await page.evaluate(()=>{holsterLab.seek(.5);holsterLab.setPlaying(true);});
   const svg=await host.locator('svg').boundingBox(),point=await host.locator('[data-point="1"]').boundingBox();
   await page.mouse.move(point.x+point.width/2,point.y+point.height/2);await page.mouse.down();
   const y=action==='draw'?.25:.35;
   await page.mouse.move(svg.x+svg.width*(20+250*.4)/280,svg.y+svg.height*(140-130*y)/160,{steps:6});
   assert.deepEqual(await page.evaluate(a=>holsterLab.state().parameters[a+'Return'].timingCurve,action),linear,'commit on release');
   await page.mouse.up();
   assert.equal(await page.locator('#play').textContent(),'Pause','editing preserves playback');
   profiles[action]=await page.evaluate(a=>holsterLab.state().parameters[a+'Return'].timingCurve,action);
   assert(Math.abs(profiles[action][1][1]-y)<.005);
   const time=await page.evaluate(()=>holsterLab.state().time);
   await page.waitForFunction(t=>holsterLab.state().time>t+.02,time);
   await page.evaluate(()=>holsterLab.setPlaying(false));
  }
  const saved=await page.evaluate(()=>holsterLab.state());
  await page.waitForTimeout(500);await page.reload();await page.waitForFunction(()=>window.holsterLab?.ready);
  for(const action of ['draw','sheathe']){
   await page.selectOption('#action',action);
   assert.deepEqual(await page.evaluate(a=>holsterLab.state().parameters[a+'Return'].timingCurve,action),profiles[action],'saved curve persists');
   assert(Math.abs(Number(await page.locator('#fkReturnCurveEditor [data-point="1"]').getAttribute('cy'))-(140-130*profiles[action][1][1]))<1e-8,'contextual display');
  }
  // Existing all-curves bypass includes return curves without erasing their points.
  await page.locator('#retimeControls summary').click();await page.check('#bypassCurves');
  assert(await page.evaluate(()=>holsterLab.model().fkReturn.curve.identity));
  for(const action of ['draw','sheathe'])assert.deepEqual(await page.evaluate(a=>holsterLab.state().parameters[a+'Return'].timingCurve,action),profiles[action]);
  await page.uncheck('#bypassCurves');assert(!(await page.evaluate(()=>holsterLab.model().fkReturn.curve.identity)));
  // Reset is local to the selected action and keeps every other setting.
  await page.locator('#fkReturnCurveEditor button').click();
  assert.deepEqual(await page.evaluate(()=>holsterLab.state().parameters),{...saved.parameters,sheatheReturn:{...saved.parameters.sheatheReturn,timingCurve:linear}});
  await page.evaluate(s=>holsterLab.restore(JSON.parse(JSON.stringify(s))),saved);
  for(const action of ['draw','sheathe'])assert.deepEqual(await page.evaluate(a=>holsterLab.state().parameters[a+'Return'].timingCurve,action),profiles[action],'snapshot/JSON restore');
  // Worker rebuild also carries the new profile field.
  await page.locator('#noCheat').check();
  assert.deepEqual(await page.evaluate(()=>holsterLab.model().fkReturn.options.timingCurve),profiles.sheathe);
  await page.locator('#fkReturnCurveEditor').scrollIntoViewIfNeeded();
  await page.screenshot({path:path.join(out,'return-curve.png')});
  assert.deepEqual(errors,[]);assert.deepEqual(await page.evaluate(()=>holsterLab.errors),[]);
  console.log('PASS: separate D/S return curves, drag without pause, reset isolation, bypass, disk reload, JSON/snapshot restore and causal planner.');
 }finally{if(browser)await browser.close();server.kill();}
})().catch(e=>{console.error(e);process.exitCode=1;});
