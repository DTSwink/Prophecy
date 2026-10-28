/* Full app refresh check. Isolated headless browser; all state writes mocked. */
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require(process.env.FOOTIK_PLAYWRIGHT||'C:/Users/singerie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const url=process.env.FOOTIK_TEST_URL||'http://127.0.0.1:8890',checks=[],timings=[];
const check=(name,value)=>{assert(value,name);checks.push(name);};
(async()=>{
 let saved=await(await fetch(url+'/state')).json();saved.playback.playing=false;
 const browser=await chromium.launch({headless:true,executablePath:process.env.FOOTIK_BROWSER||'C:/Program Files/Google/Chrome/Application/chrome.exe',args:['--disable-background-networking','--disable-extensions','--disable-component-update','--disable-sync']});
 try{
  const page=await browser.newPage({viewport:{width:1100,height:850}}),errors=[],requests=[],appTimings=[];let changes=0,versionChanged=false;
  page.on('pageerror',e=>errors.push(e.message));
  page.on('console',message=>{if(message.text().startsWith('[Foot IK refresh] '))appTimings.push(JSON.parse(message.text().slice(18)));});
  page.on('request',r=>{if(r.url().endsWith('/resume'))requests.push(r.postDataJSON());});
  await page.route('**/state',route=>{
   if(route.request().method()==='GET')return route.fulfill({json:saved});
   changes++;const data=route.request().postDataJSON();
   for(const [key,value] of Object.entries(data.changes||{}))Object.assign(saved[key]||={},value);
   return route.fulfill({json:{saved:true}});
  });
  await page.route('**/app.js',async route=>{
   if(route.request().method()==='HEAD'&&versionChanged){versionChanged=false;return route.fulfill({headers:{'Last-Modified':new Date(Date.now()+5000).toUTCString()}});}
   return route.continue();
  });
  await page.goto(url);await page.waitForFunction(()=>window.FootIKLab&&!FootIKLab.state.busy,null,{timeout:45000});
  const original=await page.evaluate(()=>{
   window.refreshBaseline={model,renderer,run};
   return {frame:FootIKLab.state.frame,camera:{...cameraState},timeOrigin:performance.timeOrigin};
  });
  check('served sources predate this loaded page',await page.evaluate(()=>sourcesUnchanged()));
  const refresh=async()=>{
   const started=performance.now();assert(await page.locator('#refresh').isEnabled());
   // Headless GPU startup can stall Playwright's visual-stability probe even
   // after the app is ready. Exercise the actual button handler directly;
   // the real IAB mouse-click timing is recorded separately.
   await page.locator('#refresh').dispatchEvent('click');
   await page.waitForFunction(()=>!reloading&&!busy,null,{polling:50});timings.push(performance.now()-started);
  };
  const priorRequests=requests.length;
  for(let i=0;i<2;i++)await refresh();
  check('unchanged Refresh reuses all prepared frames, NN data and renderer',await page.evaluate(()=>model===refreshBaseline.model&&run===refreshBaseline.run&&renderer===refreshBaseline.renderer));
  check('unchanged Refresh performs no NN requests',requests.length===priorRequests);
  const current=await page.evaluate(()=>({frame:FootIKLab.state.frame,camera:{...cameraState},timeOrigin:performance.timeOrigin}));
  check('unchanged Refresh does not navigate',current.timeOrigin===original.timeOrigin);
  check('frame and camera are preserved',current.frame===original.frame&&JSON.stringify(current.camera)===JSON.stringify(original.camera));
  check('unchanged Refresh does not write saved state',changes===0);
  saved.camera.yaw+=.1;saved.settings.ghost=!saved.settings.ghost;saved.playback.time=1;
  await refresh();
  check('other-tab view and playback edits are adopted without motion rebuilding',await page.evaluate(expected=>model===refreshBaseline.model&&cameraState.yaw===expected.camera.yaw&&settings.ghost===expected.settings.ghost&&time===1,saved));
  check('adopted state does not get republished as an edit',changes===0);
  // Terrain-only change still needs a new solve, while retaining the NN and GL.
  saved.settings.enabled=!saved.settings.enabled;await refresh();
  check('changed motion settings reprepare without rebuilding the renderer or source NN',await page.evaluate(()=>model!==refreshBaseline.model&&renderer===refreshBaseline.renderer&&run===refreshBaseline.run));
  versionChanged=true;
  await page.locator('#refresh').dispatchEvent('click');
  await page.waitForFunction(origin=>performance.timeOrigin!==origin&&window.FootIKLab&&!busy,original.timeOrigin,{timeout:45000,polling:50});
  check('changed code triggers a real reload',await page.evaluate(()=>!window.refreshBaseline));
  check('no browser errors',errors.length===0);
  const result={passed:true,checks,clickToReadyMs:timings,appTimings,errors};fs.writeFileSync(path.join(__dirname,'snapshots/refresh-verification.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
