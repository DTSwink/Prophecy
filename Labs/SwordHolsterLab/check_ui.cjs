const {chromium}=require(process.env.HARNESS_PLAYWRIGHT_MODULE||'C:/Users/singerie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs=require('fs'),path=require('path'),assert=require('assert');
(async()=>{
 const url='http://127.0.0.1:8819',token='qa-'+require('crypto').randomUUID();await fetch(url+'/desktop-session',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token})});
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',args:['--enable-webgl','--use-angle=swiftshader']});
 const out=path.resolve(__dirname,'../../Saved/Diagnostics/SwordHolsterLabQA');fs.mkdirSync(out,{recursive:true});
 try{
  const page=await browser.newPage({viewport:{width:1500,height:980}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(url+'/?desktopSession='+token);await page.waitForFunction(()=>window.holsterLab?.ready,null,{timeout:30000});
  await page.evaluate(()=>holsterLab.restore({schema:'sword_holster_lab_v1',parameters:{...Holster.defaults,spineClavicleAngleLimit:0},workspaceTab:'motion',time:0}));
  await page.evaluate(()=>holsterLab.seek(3));await page.screenshot({path:path.join(out,'idle-reach.png')});
  assert.equal(await page.locator('#phase').textContent(),'Reach limited');
  await page.fill('#shrinkPercent','70');await page.locator('#shrinkPercent').dispatchEvent('change');
  await page.evaluate(()=>holsterLab.seek(4));assert.equal(await page.locator('#phase').textContent(),'Holstered');
  await page.selectOption('#action','draw');await page.evaluate(()=>holsterLab.seek(4));assert.equal(await page.locator('#phase').textContent(),'Held');
  await page.selectOption('#motion','walk');await page.evaluate(()=>holsterLab.seek(1));await page.screenshot({path:path.join(out,'walk-draw.png')});
  await page.click('#snapshot');await page.waitForFunction(()=>document.getElementById('notice').textContent.startsWith('Saved snapshot_'));
  const saved=await page.evaluate(()=>holsterLab.state());await page.click('#refresh');await page.waitForFunction(()=>window.holsterLab?.ready);
  const after=await page.evaluate(()=>holsterLab.state());assert.deepEqual(after.parameters,saved.parameters);assert.equal(after.time,saved.time);
  await page.click('#motionTab');await page.fill('#shrinkPercent','20');await page.locator('#shrinkPercent').dispatchEvent('change');
  await page.click('#libraryTab');await page.selectOption('#snapshots',{index:1});await page.waitForFunction(()=>holsterLab.state().parameters.shrinkPercent===70);
  await page.keyboard.press('ArrowRight');assert(Math.abs((await page.evaluate(()=>holsterLab.state().time))-saved.time-1/60)<1e-7);
  await page.keyboard.press('Space');await page.waitForTimeout(550);await page.keyboard.press('Space');assert((await page.evaluate(()=>holsterLab.state().time))>saved.time+.2);
  await page.click('#viewTab');await page.check('#handGizmos');await page.check('#idleGhost');await page.screenshot({path:path.join(out,'view-gizmos.png')});
  await page.evaluate(()=>holsterLab.publishLive());const live=await(await fetch(url+'/desktop-view')).json();assert(live.ok&&live.displayedPose.equipment.sword&&live.runtimeErrors.length===0);
  assert.equal(errors.length,0,errors.join('\n'));fs.writeFileSync(path.join(out,'ui.json'),JSON.stringify({passed:true,errors,refresh:true,snapshot:true,keyboard:true,liveCapture:true},null,2));console.log('UI PASSED');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
