const fs=require('fs'),path=require('path'),assert=require('assert/strict'),z=require('zlib'),{chromium}=require('C:/Users/singerie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const ROOT=__dirname,read=n=>JSON.parse(fs.readFileSync(path.join(ROOT,n),'utf8').replace(/^\uFEFF/,''));
(async()=>{
 const fixture=JSON.parse(z.gunzipSync(fs.readFileSync(path.join(ROOT,'data/platforms-speed-fixture.json.gz'))));let saved=fixture.saved;saved.playback.playing=false;
 const data=fixture.data,checks=[],check=(name,yes)=>{assert(yes,name);checks.push(name);};
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',args:['--disable-background-networking','--disable-extensions','--disable-sync']});
 try{
  const context=await browser.newContext({viewport:{width:1100,height:850}});
  await context.addInitScript(()=>{const original=globalThis.fetch;globalThis.fetch=(url,init)=>String(url).endsWith('/state')&&init?.method==='POST'?Promise.resolve(new Response('{"saved":true}',{headers:{'Content-Type':'application/json'}})):original(url,init);});
  await context.route('**/persistence.js',r=>r.fulfill({contentType:'text/javascript',body:'globalThis.FootPersistence={create:()=>({save(){},async flush(){},accept(){}})};'}));
  await context.route('**/state',r=>r.fulfill({json:r.request().method()==='GET'?saved:{saved:true}}));
  await context.route('**/resume',r=>r.fulfill({json:data}));
  // This suite exercises editor/persistence controls without NN inference.
  // Actual surface/NN coupling is checked by verify-surface-coupling.cjs and
  // the separate production-viewer receipt, rather than a wrong canned NN reply.
  await context.route('**/surface-coupling.js',r=>r.fulfill({contentType:'text/javascript',body:'globalThis.FootSurfaceCoupling={prepare:async(run,settings)=>FootSurface.prepare(run,settings)};'}));
  const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(String(e)));
  const ready=()=>page.waitForFunction(()=>window.FootIKLab&&!busy,null,{timeout:60000}).catch(async e=>{console.error({errors,body:await page.locator('body').innerText()});throw e;});
  await page.goto('http://127.0.0.1:8890');await ready();
  check('velocity matches total simulated root speed',await page.evaluate(()=>$('rootVelocityRead').textContent==='Root v '+norm(frame.surface.velocity).toFixed(2)+' m/s'));
  const positions=await page.evaluate(()=>Object.fromEntries(['phase','rootVelocityRead','addPlatform'].map(id=>[id,document.getElementById(id).getBoundingClientRect().toJSON()])));
  check('velocity and add button follow status vertically',positions.phase.bottom<positions.rootVelocityRead.top&&positions.rootVelocityRead.bottom<positions.addPlatform.top);
  await page.locator('#minorOptions summary').click({force:true});await page.locator('#pinReleaseSpeed').fill('0.5');await page.locator('#pinReleaseSpeed').press('Enter');await ready();
  check('numeric Enter commits and deselects',await page.evaluate(()=>settings.pinReleaseSpeed===.5&&document.activeElement.id!=='pinReleaseSpeed'));
  await page.locator('#cameraSide').click({force:true});
  check('outside click closes options',await page.locator('#minorOptions').evaluate(el=>!el.open));
  const frameBefore=await page.evaluate(()=>time),count=await page.evaluate(()=>platformRecords().length);
  await page.locator('#addPlatform').click({force:true});await ready();
  check('add creates/selects one real platform',await page.evaluate(n=>platformRecords().length===n+1&&!!platformEditor.selected&&model.terrain.surfaces.some(p=>p.id===platformEditor.selected),count));
  check('adding retains playback position',await page.evaluate(t=>time===t,frameBefore));
  await page.keyboard.press('w');check('W shows translation arrows',await page.locator('#platformGizmo').evaluate(el=>el.querySelectorAll('polygon').length===3));
  const before=await page.evaluate(()=>JSON.stringify(platformRecords()));
  const center=await page.locator('#platformGizmo circle[data-axis="3"]').boundingBox();assert(center);
  await page.mouse.move(center.x+center.width/2,center.y+center.height/2);await page.mouse.down();await page.mouse.move(center.x+center.width/2+35,center.y+center.height/2-12,{steps:5});
  check('drag updates preview without a rebuild per move',await page.evaluate(b=>!!platformEditor.drag&&!busy&&JSON.stringify(platformRecords())!==b,before));
  await page.mouse.up();await ready();
  check('completed transform is undoable',await page.evaluate(()=>platformEditor.history.length===1));
  await page.keyboard.press('Control+z');await ready();
  check('Ctrl+Z restores transform',await page.evaluate(b=>JSON.stringify(platformRecords())===b,before));
  await page.keyboard.press('e');check('E shows rotation rings',await page.locator('#platformGizmo').evaluate(el=>el.querySelectorAll('path[data-axis]').length===3&&el.querySelectorAll('polygon').length===0));
  await page.keyboard.press('r');check('R shows scale boxes',await page.locator('#platformGizmo').evaluate(el=>el.querySelectorAll('rect[data-axis]').length===4));
  saved=await page.evaluate(()=>snapshot());saved.playback.playing=false;
  await page.reload();await ready();check('platforms and threshold restore after reload',await page.evaluate(s=>settings.pinReleaseSpeed===s.settings.pinReleaseSpeed&&JSON.stringify(settings.platformLayouts)===JSON.stringify(s.settings.platformLayouts),saved));
  const added=saved.settings.platformLayouts.incline.at(-1).id;
  await page.evaluate(id=>{platformEditor.selected=id;platformEditor.render();},added);
  const cam=await page.evaluate(()=>cameraState.yaw),point=await page.evaluate(()=>{const rect=$('viewport').getBoundingClientRect();for(const u of [.25,.75,.35,.65])for(const v of [.4,.6,.7]){const x=rect.left+rect.width*u,y=rect.top+rect.height*v;if(document.elementFromPoint(x,y)===$('viewport')&&FootPlatforms.pick(FootPlatforms.ray(renderer.viewCamera,rect,x,y),sceneSurfaces()))return {x,y};}throw Error('No unobstructed platform pixel for orbit test');});
  await page.mouse.move(point.x,point.y);await page.mouse.down();await page.mouse.move(point.x+45,point.y+12,{steps:4});await page.mouse.up();
  check('camera drag still orbits and clears selection',await page.evaluate(y=>cameraState.yaw!==y&&platformEditor.selected===null,cam));
  await page.evaluate(id=>{platformEditor.selected=id;platformEditor.render();},added);await page.keyboard.press('Delete');await ready();
  check('Delete removes selected collider',await page.evaluate(id=>!model.terrain.surfaces.some(p=>p.id===id),added));
  await page.locator('#addPlatform').click({force:true});await ready();const newer=await page.evaluate(()=>platformEditor.selected);await page.keyboard.press('Backspace');await ready();
  check('Backspace removes selected collider',await page.evaluate(id=>!platformRecords().some(p=>p.id===id),newer));
  await page.locator('#minorOptions summary').click({force:true});await page.locator('#pinReleaseSpeed').focus();await page.keyboard.press('Control+z');
  check('text entry retains its own undo',await page.evaluate(()=>document.activeElement.id==='pinReleaseSpeed'));
  await page.locator('#cameraFront').click({force:true});await page.locator('#addPlatform').click({force:true});await ready();
  await page.screenshot({path:path.join(ROOT,'snapshots/platforms-ui.png')});
  const state=await page.evaluate(()=>({frame:Math.round(time*60),velocity:$('rootVelocityRead').textContent,errors:FootIKLab.state.errors,platforms:platformRecords().length}));
  check('no browser or app errors',errors.length===0&&state.errors.length===0);
  fs.writeFileSync(path.join(ROOT,'snapshots/platforms-ui-verification.json'),JSON.stringify({passed:true,checks,state,errors},null,2));console.log(JSON.stringify({passed:true,checks:checks.length,state}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
