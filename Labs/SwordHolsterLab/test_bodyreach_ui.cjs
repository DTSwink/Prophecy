const {chromium}=require(process.env.HARNESS_PLAYWRIGHT_MODULE||'C:/Users/singerie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',args:['--enable-webgl','--use-angle=swiftshader']});
 const out=path.resolve(__dirname,'../../Saved/Diagnostics/SwordHolsterBodyReach');fs.mkdirSync(out,{recursive:true});
 try{
  const page=await browser.newPage({viewport:{width:1500,height:980}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:8818/');await page.waitForFunction(()=>window.holsterLab?.ready);
  const live=await(await fetch('http://127.0.0.1:8818/desktop-view')).json();
  if(live.state)await page.evaluate(s=>holsterLab.restore(s),live.state);
  await page.click('#motionTab');
  assert.equal(await page.locator('#spineClavicleAngleLimit').inputValue(),'45');
  assert.equal(await page.locator('#maxSpineClavicleAngularSpeed').inputValue(),'90');
  for(const action of ['sheathe','draw']){
   await page.selectOption('#action',action);
   await page.evaluate(()=>{const m=holsterLab.model();holsterLab.seek((m.frames.find(f=>f.phase==='Slide')?.tick||90)/60);});
   await page.screenshot({path:path.join(out,action+'.png')});
  }
  await page.click('#viewTab');assert(await page.locator('#bicolor').isChecked());
  const poseBefore=await page.evaluate(()=>holsterLab.pose().points);
  await page.uncheck('#bicolor');assert.deepEqual(await page.evaluate(()=>holsterLab.pose().points),poseBefore);
  await page.check('#bicolor');await page.screenshot({path:path.join(out,'bicolor-controls.png')});
  await page.click('#motionTab');
  await page.fill('#spineClavicleAngleLimit','30');await page.locator('#spineClavicleAngleLimit').dispatchEvent('change');
  await page.fill('#maxSpineClavicleAngularSpeed','25');await page.locator('#maxSpineClavicleAngularSpeed').dispatchEvent('change');
  const saved=await page.evaluate(()=>holsterLab.state());
  assert.equal(saved.parameters.spineClavicleAngleLimit,30);assert.equal(saved.parameters.maxSpineClavicleAngularSpeed,25);
  await page.evaluate(s=>{holsterLab.restore({schema:s.schema,parameters:Holster.defaults});holsterLab.restore(s);},saved);
  assert.equal(await page.locator('#spineClavicleAngleLimit').inputValue(),'30');
  assert.equal(await page.locator('#maxSpineClavicleAngularSpeed').inputValue(),'25');
  assert.equal(await page.evaluate(()=>holsterLab.state().controls.bicolor),true);
  assert.deepEqual(await page.evaluate(()=>holsterLab.errors),[]);assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(out,'ui.json'),JSON.stringify({passed:true,controlsRoundTrip:true,errors,desktopStateUntouched:true},null,2));
  console.log('PASS: new controls, state round-trip, draw/sheath renders; inspection only, desktop state untouched.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
