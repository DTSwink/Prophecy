const {chromium}=require('C:/Users/singerie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),net=require('node:net'),crypto=require('node:crypto'),{spawn}=require('node:child_process');
(async()=>{
 const out=path.resolve(__dirname,'../../Saved/Diagnostics/ReachWorkspace20261015');fs.mkdirSync(out,{recursive:true});const store=fs.mkdtempSync(path.join(out,'test-'));
 const probe=net.createServer();await new Promise(r=>probe.listen(0,'127.0.0.1',r));const port=probe.address().port;await new Promise(r=>probe.close(r));
 const url='http://127.0.0.1:'+port,token=crypto.randomUUID();let child,browser;
 async function start(){child=spawn('C:/Users/singerie/Documents/Cursor/stepper/.tools/python310/python.exe',[path.join(__dirname,'server.py'),'--port',String(port),'--state-dir',store],{windowsHide:true,stdio:'pipe'});let errors='';child.stderr.on('data',d=>errors+=d);for(let i=0;;i++){try{if((await fetch(url+'/health')).ok)return;}catch(e){if(i>70)throw Error(errors||e);}await new Promise(r=>setTimeout(r,100));}}
 async function stop(){const done=new Promise(r=>child.once('exit',r));child.kill();await done;}
 try{
  await start();await fetch(url+'/desktop-session',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token})});
  browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',args:['--enable-webgl','--use-angle=swiftshader']});
  const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(url+'/reach?desktopSession='+token);await page.waitForFunction(()=>window.reachLab?.ready);await page.click('#play');await page.waitForFunction(()=>!pending);
  const baseline=await(await fetch(url+'/reset-defaults')).json();const initial=await page.evaluate(()=>reachLab.snapshot());
  assert.deepEqual(initial.settings.hands.map(h=>h.target),baseline.hands.map(h=>h.target));
  await page.fill('#p00','81');await page.fill('#r02','45');await page.fill('#p10','-63');await page.fill('#r11','25');
  await page.click('#reset-target-0');let s=await page.evaluate(()=>reachLab.snapshot());assert.deepEqual(s.settings.hands[0].target,baseline.hands[0].target);assert.equal(s.settings.hands[0].rotation[2],45);assert.equal(s.settings.hands[1].target[0],-63);
  await page.click('#reset-rotation-0');assert.deepEqual(await page.evaluate(()=>reachLab.snapshot().settings.hands[0].rotation),baseline.hands[0].rotation);
  await page.click('#reset-target-1');await page.click('#reset-rotation-1');
  assert.deepEqual(await page.evaluate(()=>reachLab.snapshot().settings.resetDefaults),baseline);
  await page.fill('#p00','23');await page.fill('#r02','15');await page.click('[data-view="side"]');await page.check('#skeleton');await page.selectOption('#playSpeed','.5');await page.evaluate(()=>reachLab.step(8));
  const saved=await page.evaluate(()=>reachLab.snapshot());await page.evaluate(()=>reachLab.saveSnapshot());
  const list=await(await fetch(url+'/snapshots')).json();assert.deepEqual(list,['snapshot_0001']);const disk=await(await fetch(url+'/snapshots/'+list[0]+'.json')).json();assert.deepEqual(disk.pose,saved.pose);assert.deepEqual(disk.settings,saved.settings);
  const png=Buffer.from(await(await fetch(url+'/snapshots/'+list[0]+'.png')).arrayBuffer());fs.writeFileSync(path.join(out,'snapshot.png'),png);
  const actual=await page.evaluate(()=>canvas.toDataURL('image/png'));fs.writeFileSync(path.join(out,'viewport.png'),Buffer.from(actual.split(',')[1],'base64'));
  await page.fill('#p00','65');await page.fill('#r02','-85');await page.click('[data-view="front"]');await page.evaluate(()=>reachLab.step(8));
  await page.click('#snapshotLibrary summary');await page.selectOption('#snapshots',list[0]);await page.waitForFunction(()=>document.querySelector('#message').textContent.startsWith('Snapshot restored'));
  for(const key of ['settings','pose','solverState','camera','controls','handQ','returns','wholeReturn','tick'])assert.deepEqual(await page.evaluate(key=>reachLab.snapshot()[key],key),saved[key],key+' restored');
  await page.evaluate(()=>reachLab.step(8));const next=await page.evaluate(()=>reachLab.snapshot());await page.evaluate(s=>reachLab.restore(s),disk);await page.evaluate(()=>reachLab.step(8));assert.deepEqual(await page.evaluate(()=>reachLab.snapshot().pose),next.pose,'Continuation matches after restore');
  const downloadPromise=page.waitForEvent('download');await page.click('#export');const download=await downloadPromise;await download.saveAs(path.join(out,'export.json'));assert.deepEqual(JSON.parse(fs.readFileSync(path.join(out,'export.json'))).pose,next.pose);
  await page.locator('#importFile').setInputFiles({name:'saved.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(disk))});await page.waitForFunction(()=>document.querySelector('#message').textContent==='REACH snapshot imported.');assert.deepEqual(await page.evaluate(()=>reachLab.snapshot().pose),disk.pose);
  await page.fill('#p00','33');const beforeRefresh=await page.evaluate(()=>reachLab.snapshot());await page.click('#refresh');await page.waitForFunction(()=>window.reachLab?.ready&&document.querySelector('#p00').value==='33.0');
  for(const key of ['settings','pose','solverState','camera','controls','tick'])assert.deepEqual(await page.evaluate(key=>reachLab.snapshot()[key],key),beforeRefresh[key],key+' survives refresh');
  await page.evaluate(()=>reachLab.publishLive());let live=await(await fetch(url+'/desktop-view')).json();assert(live.ok);assert.deepEqual(live.settings.resetDefaults,baseline);
  let image=await fetch(url+'/desktop-view.png?sequence='+live.sequence);if(image.status===409){live=await(await fetch(url+'/desktop-view')).json();image=await fetch(url+'/desktop-view.png?sequence='+live.sequence);}
  assert.equal(image.status,200);assert.equal(crypto.createHash('sha256').update(Buffer.from(await image.arrayBuffer())).digest('hex'),live.imageSha256);
  assert.equal((await fetch(url+'/desktop-view.png?sequence=-1')).status,409);
  assert.equal((await fetch(url+'/state',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'})).status,403);
  const inspection=await browser.newPage();await inspection.goto(url+'/reach');await inspection.waitForFunction(()=>window.reachLab?.ready);assert.equal(await inspection.locator('#capture').isDisabled(),true);await inspection.close();
  await page.evaluate(()=>saveSession());await stop();await start();await page.reload();await page.waitForFunction(()=>window.reachLab?.ready);assert.deepEqual(await page.evaluate(()=>reachLab.snapshot().camera),beforeRefresh.camera);assert.equal(await page.inputValue('#p00'),'33.0');
  await page.click('#reset-target-0');assert.equal(await page.inputValue('#p00'),'13.0');await page.waitForTimeout(350);assert.deepEqual(JSON.parse(fs.readFileSync(path.join(store,'state.json'))).resetDefaults,baseline);
  await page.locator('#view').click({position:{x:600,y:220}});await page.keyboard.press('p');await page.waitForFunction(()=>document.querySelector('#capture').textContent==='Snapshot (2)');
  await page.screenshot({path:path.join(out,'workspace.png')});assert.deepEqual(errors,[]);
  const receipt={passed:true,independentResets:true,baselineImmutable:true,snapshotRestore:true,deterministicContinuation:true,refreshPreservesExactState:true,serverRestartPersistence:true,liveImageHash:true,inspectionReadOnly:true,keyboardSnapshot:true,errors};fs.writeFileSync(path.join(out,'verification.json'),JSON.stringify(receipt,null,2));console.log(JSON.stringify(receipt));
 }finally{if(browser)await browser.close();if(child?.exitCode===null)await stop();}
})().catch(e=>{console.error(e);process.exit(1);});
