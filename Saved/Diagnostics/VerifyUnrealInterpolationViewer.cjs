const {chromium}=require('C:/Users/singerie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs=require('fs');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Users/singerie/AppData/Local/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-win64/chrome-headless-shell.exe',args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:960}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const root='http://127.0.0.1:8795/latest_predictive_pin_x5_20260924_refresh2/seed_2026092223/complete/';
  await page.goto(root+'variant_viewer_unreal_interpolation.html');
  await page.waitForFunction(()=>typeof activeMotion!=='undefined' && activeMotion && !document.getElementById('motionStatus').textContent.includes('failed'));
  const report=await page.evaluate(()=>{
   playing=false;
   const maxDifference=(a,b)=>Math.max(...a.flat(3).map((v,i)=>Math.abs(v-b.flat(3)[i])));
   let keyPosition=0,keyRotation=0,midRotationDifference=0;
   for(let f=0;f<901;f+=2){
    frameExact=f;comparisonInterpolation.value='unreal';const u=sampleActivePose();
    comparisonInterpolation.value='original';const o=sampleActivePose();
    keyPosition=Math.max(keyPosition,maxDifference(u.pose,o.pose));
    keyRotation=Math.max(keyRotation,maxDifference(u.poseAxes,o.poseAxes));
   }
   for(const f of [31.25,100.3,193.7,727.2,895.4]){
    frameExact=f;comparisonInterpolation.value='unreal';const u=sampleActivePose();
    comparisonInterpolation.value='original';const o=sampleActivePose();
    midRotationDifference=Math.max(midRotationDifference,maxDifference(u.poseAxes,o.poseAxes));
   }
   comparisonInterpolation.value='unreal';frameExact=727;draw();
   return {title:document.title,keyPosition,keyRotation,midRotationDifference,
      fps:payload.clips[clipIndex].motion_fps,frames:payload.clips[clipIndex].motion_frame_count};
  });
  await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>{draw();requestAnimationFrame(resolve);})));
  await page.screenshot({path:'Saved/Diagnostics/UnrealInterpolationViewer.png'});
  if(errors.length||report.keyPosition!==0||report.keyRotation!==0||report.midRotationDifference<=0)throw Error(JSON.stringify({errors,report}));
  await page.selectOption('#comparisonInterpolation','original');
  if(await page.locator('#comparisonLabel').innerText()!=='Original viewer interpolation')throw Error('Toggle label failed');
  await page.selectOption('#comparisonInterpolation','unreal');
  await page.click('#play');
  await page.waitForFunction(()=>playing && frameExact>729);
  await page.click('#play');
  await page.goto(root+'variant_viewer.html');
  await page.waitForFunction(()=>typeof activeMotion!=='undefined' && activeMotion);
  if(await page.locator('#comparisonInterpolation').count())throw Error('Original viewer modified');
  report.errors=errors;report.toggleAndPlaybackPassed=true;report.originalUnchanged=true;
  fs.writeFileSync('Saved/Diagnostics/UnrealInterpolationViewer-validation.json',JSON.stringify(report,null,2));
  console.log(JSON.stringify(report));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
