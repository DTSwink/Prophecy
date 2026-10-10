const {chromium}=require(process.env.HARNESS_PLAYWRIGHT_MODULE||'C:/Users/singerie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),net=require('node:net'),{spawn}=require('node:child_process');
(async()=>{
 const out=path.resolve(__dirname,'../../Saved/Diagnostics/SwordHolsterRetime');fs.mkdirSync(out,{recursive:true});
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
  await page.click('#motionTab');await page.click('#retimeControls summary');
  const linear=await page.evaluate(()=>Retime.linear()),curves={};
  for(const action of ['draw','sheathe']){
   await page.selectOption('#action',action);
   assert.equal(await page.locator('#retimeTitle').textContent(),(action==='draw'?'Drawing':'Sheathing')+' timing curves');
   assert.equal(await page.locator('.retime-editor:visible').count(),2);
   for(const phase of ['reach','slide']){
    const key=action+(phase==='slide'?'SlideCurve':'Curve'),host=page.locator('#'+phase+'CurveEditor');
    assert.equal(await host.locator('[data-point]').count(),4);await host.scrollIntoViewIfNeeded();
    const svg=await host.locator('svg').boundingBox(),handle=await host.locator('[data-point="1"]').boundingBox();
    await page.evaluate(()=>{holsterLab.seek(.5);window.preEditFrames=holsterLab.model().sourceFrames;holsterLab.setPlaying(true);});
    const y=.23+(action==='sheathe'?.04:0)+(phase==='slide'?.07:0);
    await page.mouse.move(handle.x+handle.width/2,handle.y+handle.height/2);await page.mouse.down();
    await page.mouse.move(svg.x+svg.width*(20+250*.35)/280,svg.y+svg.height*(140-130*y)/160,{steps:8});
    assert.deepEqual(await page.evaluate(k=>holsterLab.state().parameters[k],key),linear,'commit only on release');await page.mouse.up();
    curves[key]=await page.evaluate(k=>holsterLab.state().parameters[k],key);
    assert(Math.abs(curves[key][1][0]-.35)<.005&&Math.abs(curves[key][1][1]-y)<.005);
    assert.equal(await page.locator('#play').textContent(),'Pause','curve edit keeps playing');
    assert(await page.evaluate(()=>holsterLab.model().sourceFrames===window.preEditFrames),'no expensive pose rebuild');
    const afterEdit=await page.evaluate(()=>holsterLab.state().time);
    await page.waitForFunction(t=>holsterLab.state().time>t+.05,afterEdit);
    await page.evaluate(()=>holsterLab.setPlaying(false));
   }
  }
  assert.equal(new Set(Object.values(curves).map(JSON.stringify)).size,4,'four distinct profiles');
  await page.fill('#maxReachSpeed','120');await page.locator('#maxReachSpeed').dispatchEvent('change');
  assert.equal(await page.locator('#headCorrectionAlpha').count(),0);
  const headControls={headLookAtAlpha:.7,headLookInExponent:1.8,headLookOutExponent:2.4,maxHeadLookInVelocity:150,maxHeadLookOutVelocity:210,drawHeadLookOutThreshold:.25,sheatheHeadLookOutThreshold:.65};
  assert.equal(await page.locator('#drawHeadLookOutThreshold').inputValue(),'0.3');assert.equal(await page.locator('#sheatheHeadLookOutThreshold').inputValue(),'0.5');
  for(const [id,value] of Object.entries(headControls)){await page.fill('#'+id,String(value));await page.locator('#'+id).dispatchEvent('change');}
  const check=async()=>{const o=await page.evaluate(()=>holsterLab.state().parameters);for(const [id,value] of Object.entries(headControls)){assert.equal(o[id],value);assert.equal(await page.locator('#'+id).inputValue(),String(value));}for(const [k,v] of Object.entries(curves))assert.deepEqual(o[k],v,k);};
  await check();
  for(const action of ['draw','sheathe']){
   await page.selectOption('#action',action);await check();
   for(const phase of ['reach','slide']){
    const key=action+(phase==='slide'?'SlideCurve':'Curve');
    const cy=Number(await page.locator('#'+phase+'CurveEditor [data-point="1"]').getAttribute('cy'));
    assert(Math.abs(cy-(140-130*curves[key][1][1]))<1e-8,'switch restores displayed curve');
   }
  }
  await page.click('#openFKReturn');assert(await page.locator('#fkReturnPanel').isVisible());
  const canvasBox=await page.locator('#viewport').boundingBox(),panelBox=await page.locator('#fkReturnPanel').boundingBox();
  assert(panelBox.x>=canvasBox.x+canvasBox.width-1,'FK panel is separate on right');
  const returnProfiles={};
  for(const action of ['draw','sheathe']){
   await page.selectOption('#action',action);
   assert.equal(await page.locator('#fkReturnTitle').textContent(),(action==='draw'?'Drawing':'Sheathing')+' FK return');
   await page.fill('#fk_duration',action==='draw'?'0.4':'0.8');await page.locator('#fk_duration').dispatchEvent('change');
   await page.fill('#fk_inertia',action==='draw'?'0.2':'0.7');await page.locator('#fk_inertia').dispatchEvent('change');
   await page.locator('#fkReturnPanel summary').filter({hasText:'Inertia options'}).click();
   await page.selectOption('#fk_worldInertia',action==='draw'?'true':'false');
   await page.selectOption('#fk_springReturn',action==='sheathe'?'true':'false');
   await page.locator('#fkReturnPanel summary').filter({hasText:'Inertia options'}).click();
   returnProfiles[action]=await page.evaluate(a=>holsterLab.state().parameters[a+'Return'],action);
  }
  const checkReturns=async()=>{for(const action of ['draw','sheathe'])assert.deepEqual(await page.evaluate(a=>holsterLab.state().parameters[a+'Return'],action),returnProfiles[action]);};
  await checkReturns();
  const saved=await page.evaluate(()=>JSON.parse(JSON.stringify(holsterLab.state())));
  await page.evaluate(s=>{holsterLab.restore({schema:s.schema,parameters:Holster.defaults});holsterLab.restore(s);},saved);await check();
  await page.evaluate(()=>holsterLab.snapshot());
  const snap=JSON.parse(fs.readFileSync(path.join(store,'snapshots/snapshot_0001.json'),'utf8'));
  for(const [k,v] of Object.entries(curves))assert.deepEqual(snap.parameters[k],v,'snapshot disk persistence');
  await Promise.all([page.waitForEvent('load'),page.click('#refresh')]);await page.waitForFunction(()=>window.holsterLab?.ready);await check();await checkReturns();assert(await page.locator('#fkReturnPanel').isVisible(),'open panel persists');
  const disk=JSON.parse(fs.readFileSync(path.join(store,'state.json'),'utf8'));
  for(const [k,v] of Object.entries(curves))assert.deepEqual(disk.parameters[k],v,'settings disk persistence');
  if(!await page.locator('#retimeControls').evaluate(el=>el.open))await page.click('#retimeControls summary');
  await page.locator('#reachCurveEditor button').focus();await page.evaluate(()=>holsterLab.seek(1));
  await page.keyboard.press('ArrowRight');assert(Math.abs(await page.evaluate(()=>holsterLab.state().time)-1-1/60)<1e-8);
  await page.keyboard.press('Space');assert.equal(await page.locator('#play').textContent(),'Pause');await page.keyboard.press('Space');assert.equal(await page.locator('#play').textContent(),'Play');await check();
  await page.locator('#reachCurveEditor button').click();
  assert.equal(await page.locator('#play').textContent(),'Play','paused reset stays paused');
  assert.deepEqual(await page.evaluate(()=>holsterLab.state().parameters.sheatheCurve),linear);
  for(const k of ['sheatheSlideCurve','drawCurve','drawSlideCurve'])assert.deepEqual(await page.evaluate(k=>holsterLab.state().parameters[k],k),curves[k],'independent reset');
  await page.click('#libraryTab');await page.selectOption('#snapshots',{index:1});
  await page.waitForFunction(v=>JSON.stringify(holsterLab.state().parameters.sheatheCurve)===JSON.stringify(v),curves.sheatheCurve);await check();await checkReturns();
  await page.click('#motionTab');
  await page.evaluate(()=>{holsterLab.seek(.5);holsterLab.setPlaying(true);});
  await page.locator('#slideCurveEditor button').click();
  assert.equal(await page.locator('#play').textContent(),'Pause','linear reset keeps playing');
  const afterReset=await page.evaluate(()=>holsterLab.state().time);
  await page.waitForFunction(t=>holsterLab.state().time>t+.05,afterReset);
  await page.evaluate(s=>holsterLab.restore(s),saved);
  await page.evaluate(()=>{const s=holsterLab.model().retimeSegments.slide;holsterLab.seek((s.start+s.end)/2);});
  await page.locator('#retimeControls').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(out,'contextual-curves.png')});
  await page.locator('#maxHeadLookInVelocity').scrollIntoViewIfNeeded();
  await page.evaluate(()=>{const m=holsterLab.model();holsterLab.seek(m.plan.endTick/60);});
  await page.screenshot({path:path.join(out,'head-look-in.png')});
  await page.evaluate(()=>holsterLab.seek(holsterLab.model().playbackDuration));
  await page.screenshot({path:path.join(out,'head-look-out.png')});
  assert.deepEqual(errors,[]);assert.deepEqual(await page.evaluate(()=>holsterLab.errors),[]);
  await page.evaluate(()=>{const m=holsterLab.model();holsterLab.seek(m.fkReturn.start+.25);});await page.screenshot({path:path.join(out,'fk-return-panel.png')});
  console.log('PASS: contextual pair, four independent draggable curves, release commit, reset/keyboard, action switches, JSON, disk save, refresh and snapshot restore; isolated server/state only.');
 }finally{if(browser)await browser.close();server.kill();}
})().catch(e=>{console.error(e);process.exitCode=1;});
