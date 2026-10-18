const {chromium}=require('C:/Users/singerie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),net=require('node:net'),{spawn}=require('node:child_process');
(async()=>{
 const out=path.resolve(__dirname,'../../Saved/Diagnostics/ReachLab20261015');fs.mkdirSync(out,{recursive:true});const store=fs.mkdtempSync(path.join(out,'ui-'));
 const probe=net.createServer();await new Promise(r=>probe.listen(0,'127.0.0.1',r));const port=probe.address().port;await new Promise(r=>probe.close(r));
 const child=spawn('C:/Users/singerie/Documents/Cursor/stepper/.tools/python310/python.exe',[path.join(__dirname,'server.py'),'--port',String(port),'--state-dir',store],{windowsHide:true,stdio:'pipe'});let stderr='';child.stderr.on('data',d=>stderr+=d);const url='http://127.0.0.1:'+port;let browser;
 try{
  for(let i=0;;i++){try{if((await fetch(url+'/health')).ok)break;}catch(e){if(i>60)throw Error(stderr||e);}await new Promise(r=>setTimeout(r,100));}
  const desktopToken=require('node:crypto').randomUUID();await fetch('http://127.0.0.1:'+port+'/desktop-session',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:desktopToken})});
  browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',args:['--enable-webgl','--use-angle=swiftshader']});
  const page=await browser.newPage({viewport:{width:1440,height:960}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(url+'/reach?desktopSession='+desktopToken);await page.waitForFunction(()=>window.reachLab?.ready);await page.waitForFunction(()=>reachLab.snapshot().tick>=40);
  await page.click('#play');const initial=await page.evaluate(()=>reachLab.snapshot());
  const rect=await page.locator('#view').boundingBox(),pos=await page.evaluate(()=>reachLab.projectTarget(0));
  await page.mouse.move(rect.x+pos.x,rect.y+pos.y);await page.mouse.down({button:'right'});await page.mouse.move(rect.x+pos.x+75,rect.y+pos.y-45,{steps:8});await page.mouse.up({button:'right'});
  const moved=await page.evaluate(()=>reachLab.snapshot());assert(Math.hypot(...moved.settings.hands[0].target.map((v,i)=>v-initial.settings.hands[0].target[i]))>5,'Right drag moves target');assert.deepEqual(moved.settings.hands[1].target,initial.settings.hands[1].target);
  const pos2=await page.evaluate(()=>reachLab.projectTarget(0));await page.keyboard.down('Shift');await page.mouse.move(rect.x+pos2.x,rect.y+pos2.y);await page.mouse.down({button:'right'});await page.mouse.move(rect.x+pos2.x,rect.y+pos2.y-35,{steps:5});await page.mouse.up({button:'right'});await page.keyboard.up('Shift');
  const depth=await page.evaluate(()=>reachLab.snapshot());assert(Math.hypot(...depth.settings.hands[0].target.map((v,i)=>v-moved.settings.hands[0].target[i]))>3,'Depth drag works');
  await page.uncheck('#enabled0');assert.equal(await page.locator('#enabled1').isChecked(),true);await page.click('#play');await page.waitForTimeout(600);await page.uncheck('#enabled1');await page.waitForTimeout(900);
  const stopped=await page.evaluate(()=>reachLab.snapshot().tick);await page.waitForTimeout(250);assert.equal(await page.evaluate(()=>reachLab.snapshot().tick),stopped,'Inactive solver stops');
  await page.check('#enabled1');await page.waitForFunction(n=>reachLab.snapshot().tick>n,stopped);
  await page.click('#capture');await page.waitForFunction(()=>document.querySelector('#message').textContent.startsWith('Saved snapshot_'));
  assert(fs.readdirSync(path.join(store,'snapshots')).some(n=>n.endsWith('.png')));
  await page.waitForTimeout(350);await page.reload();await page.waitForFunction(()=>reachLab?.ready);assert.equal(await page.locator('#enabled0').isChecked(),false);assert.equal(await page.locator('#enabled1').isChecked(),true);
  await page.check('#enabled0');await page.waitForTimeout(500);await page.screenshot({path:path.join(out,'lab.png')});
  assert.deepEqual(errors,[]);fs.writeFileSync(path.join(out,'ui.json'),JSON.stringify({passed:true,rightDrag:true,depthDrag:true,independentHands:true,inactiveStops:true,persistence:true,snapshots:true,errors},null,2));console.log('UI PASSED');
 }finally{if(browser)await browser.close();child.kill();}
})().catch(e=>{console.error(e);process.exit(1)});
