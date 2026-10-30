const fs=require('fs'),z=require('zlib'),assert=require('assert/strict'),{chromium}=require('C:/Users/singerie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const before=await(await fetch('http://127.0.0.1:8890/state')).json();let saved=structuredClone(before);const writes=[],requests=[],errors=[],fixtures=[];
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',args:['--disable-background-networking','--disable-extensions','--disable-sync','--use-angle=swiftshader','--enable-unsafe-swiftshader','--disable-background-timer-throttling','--disable-renderer-backgrounding','--disable-backgrounding-occluded-windows']});
 try{
  const context=await browser.newContext({viewport:{width:1050,height:850}});
  // No read/write in this owned test page changes the user's saved setup.
  await context.route('**/state',async r=>{if(r.request().method()==='POST'){const q=r.request().postDataJSON();writes.push(q);for(const [section,values] of Object.entries(q.changes||{}))saved[section]={...saved[section],...values};}await r.fulfill({json:saved});});
  const page=await context.newPage();page.on('pageerror',e=>errors.push(String(e)));
  page.on('response',r=>{if(r.url().endsWith('/resume')&&r.request().postDataJSON()?.kind==='surface')fixtures.push((async()=>{const request=r.request().postDataJSON(),response=await r.json();requests.push({min:request.settings.pelvisSpeedMin,max:request.settings.pelvisSpeedMax,low:request.settings.pelvisCloser,high:request.settings.pelvisCloserMax,seconds:response.seconds});if(request.settings.pelvisCloserMax===30)fs.writeFileSync('snapshots/pelvis-speed-live-fixture.json.gz',z.gzipSync(JSON.stringify({request,response})));})());});
  await page.goto('http://127.0.0.1:8890');const ready=()=>page.waitForFunction(()=>window.FootIKLab&&!busy,null,{timeout:90000});await ready();console.log('Viewer ready');
  await page.screenshot({path:'snapshots/pelvis-speed-initial.png'});console.log(await page.locator('#minorOptions').evaluate(e=>({hidden:e.hidden,rect:e.getBoundingClientRect().toJSON(),html:e.outerHTML.slice(0,250)})));
  const initial=await page.evaluate(()=>({time,settings,offset:frame.pelvisOffset}));
  assert.equal(initial.settings.pelvisCloser,before.settings.pelvisCloser);assert.equal(initial.settings.pelvisCloserMax,before.settings.pelvisCloserMax??before.settings.pelvisCloser);assert.equal(initial.time,before.playback.time);
  await page.locator('#minorOptions summary').evaluate(e=>e.click());await page.locator('#pelvisCloserMax').scrollIntoViewIfNeeded();
  assert.equal(await page.locator('#minorOptions input').last().getAttribute('id'),'pelvisCloserMax');
  const bounds=await page.evaluate(()=>{const p=document.querySelector('#minorOptions'),a=document.querySelector('#pelvisSpeedMin').getBoundingClientRect(),b=document.querySelector('#pelvisSpeedMax').getBoundingClientRect();return {overflow:p.scrollWidth-p.clientWidth,sameRow:Math.abs(a.top-b.top)<1,gap:b.left-a.right};});
  assert(bounds.overflow<=1&&bounds.sameRow&&bounds.gap>=0);
  await page.locator('#pelvisCloserMax').fill('30');await page.locator('#pelvisCloserMax').press('Enter');await ready();await page.evaluate(()=>persistence.flush());
  assert(await page.evaluate(()=>document.activeElement.id!=='pelvisCloserMax'&&settings.pelvisCloserMax===30));assert.equal(saved.settings.pelvisCloserMax,30);assert.equal(await page.evaluate(()=>time),before.playback.time);
  await page.screenshot({path:'snapshots/pelvis-speed-controls.png'});
  await page.locator('#minorOptions summary').evaluate(e=>e.click());await page.locator('#viewport').screenshot({path:'snapshots/pelvis-speed-current.png'});
  for(const n of [76,95,143,180]){await page.evaluate(f=>seek(f/60),n);await page.locator('#viewport').screenshot({path:`snapshots/pelvis-speed-${n}.png`});}
  await page.evaluate(t=>{seek(t);return persistence.flush();},before.playback.time);
  await page.reload();await ready();assert.equal(await page.locator('#pelvisCloserMax').inputValue(),'30');assert.equal(await page.locator('#pelvisSpeedMin').inputValue(),'0');assert.equal(await page.locator('#pelvisSpeedMax').inputValue(),'3.5');assert.equal(await page.evaluate(()=>time),before.playback.time);
  await Promise.all(fixtures);assert.deepEqual(errors,[]);
  const after=await(await fetch('http://127.0.0.1:8890/state')).json();assert.deepEqual(after,before);
  fs.writeFileSync('snapshots/pelvis-speed-browser.json',JSON.stringify({passed:true,initial,requests,writes,bounds,errors,liveStateUnchanged:true},null,2));console.log(JSON.stringify({passed:true,requests,bounds,liveStateUnchanged:true}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
