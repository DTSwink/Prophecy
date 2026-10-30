const fs=require('fs'),z=require('zlib'),assert=require('assert/strict');
const {chromium}=require('C:/Users/singerie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const threshold=Number(process.env.SLIDE_THRESHOLD||2),prefix=threshold===2?'slide-joints':'slide-joints-late';
 const before=await(await fetch('http://127.0.0.1:8890/state')).json(),fixture=JSON.parse(z.gunzipSync(fs.readFileSync(`snapshots/slide-live-${threshold}.json.gz`)));
 let saved=structuredClone(before);if(!process.env.SLIDE_LIVE)saved.settings={...saved.settings,...fixture.request.settings};
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',args:['--disable-background-networking','--disable-extensions','--disable-sync','--use-angle=swiftshader','--enable-unsafe-swiftshader','--disable-background-timer-throttling','--disable-renderer-backgrounding','--disable-backgrounding-occluded-windows']});
 try{
  const context=await browser.newContext({viewport:{width:1150,height:880}}),errors=[];
  await context.route('**/state',async r=>{if(r.request().method()==='POST')for(const [key,value]of Object.entries(r.request().postDataJSON().changes||{}))saved[key]={...saved[key],...value};await r.fulfill({json:saved});});
  if(!process.env.SLIDE_LIVE)await context.route('**/resume',async r=>r.fulfill({json:r.request().postDataJSON().kind==='direction'?fixture.request.source:fixture.response}));
  const page=await context.newPage();page.on('pageerror',e=>errors.push(String(e)));
  await page.goto('http://127.0.0.1:8890');await page.waitForFunction(()=>window.FootIKLab&&!busy,null,{timeout:45000});
  assert.deepEqual(errors,[]);assert.equal(await page.evaluate(()=>time),before.playback.time);
  await page.locator('#viewport').screenshot({path:`snapshots/${prefix}-current.png`});
  for(const f of threshold===2?[22,25,28,32,37,45,80,130,180,206]:[109,112,115,117,120,124,130,150]){await page.evaluate(f=>seek(f/60),f);await page.locator('#viewport').screenshot({path:`snapshots/${prefix}-${f}.png`});}
  await page.evaluate(()=>{seek(130/60);cameraState.yaw+=1.2;drawAll();});await page.locator('#viewport').screenshot({path:'snapshots/slide-joints-other-side.png'});
  await page.evaluate(()=>{cameraState.yaw-=2.4;drawAll();});await page.locator('#viewport').screenshot({path:'snapshots/slide-joints-bracing-side.png'});
  // Review a real-time segment in addition to isolated stills. The owned page's
  // saved-state endpoint is intercepted, including playback/camera writes.
  await page.evaluate(()=>{cameraState.yaw+=1.2;seek(70/60);settings.trimIn=70/60;settings.trimOut=150/60;});
  await page.locator('#play').click();await page.waitForTimeout(900);
  const moving=await page.evaluate(()=>({time,hand:frame.slide?.hand,feet:frame.feet.map(f=>f.state)}));assert(moving.time>70/60);
  await page.locator('#play').click();
  assert.deepEqual(await(await fetch('http://127.0.0.1:8890/state')).json(),before);
  fs.writeFileSync('snapshots/slide-joints-browser.json',JSON.stringify({passed:true,errors,moving,savedStateUnchanged:true},null,2));
  console.log(JSON.stringify({passed:true,errors,moving,savedStateUnchanged:true}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
