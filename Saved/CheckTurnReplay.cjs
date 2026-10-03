const {chromium}=require('C:/Users/singerie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:8021/turn_parity_temp.html');await page.waitForFunction(()=>typeof payload!=='undefined'&&payload?.positions?.length&&playing);
 console.log(await page.evaluate(()=>({rows:payload.rows.map(r=>r.clip_name),frames:payload.positions[0].length,playing,frame,full:fullVisualisationToggle.checked})));
 await page.evaluate(()=>{setPlaying(false);frame=35;subframe=0;fullVisualisationToggle.checked=true;fullVisualisationToggle.dispatchEvent(new Event('change'));});
 await page.screenshot({path:'C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/Diagnostics/TurnParity/replay_viewer_check.png'});
 console.log({errors});await browser.close();if(errors.length)process.exitCode=1;
})();
