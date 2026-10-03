const {chromium}=require('C:/Users/singerie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 let browser;try{browser=await chromium.connectOverCDP('http://127.0.0.1:8034');}catch{browser=await chromium.launch({headless:false,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',args:['--start-maximized','--remote-debugging-port=8034']});}
 const page=browser.contexts()[0]?.pages()[0]||await browser.newPage({viewport:null});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:8021/turn_upper_horizon_temp.html?v=3',{waitUntil:'domcontentloaded',timeout:60000});
 await page.waitForFunction(()=>payload?.metadata?.upper_rotation_horizon===1&&payload.upper_root_window_positions,{},{timeout:180000});
 const original=await page.evaluate(()=>({window:payload.upper_root_window_forwards,root:payload.upper_root_window_positions,positions:payload.positions,joints:payload.joint_names}));
 async function select(value){await page.locator('#horizonSlider').fill(String(value));await page.locator('#horizonSlider').dispatchEvent('change');await page.waitForFunction(v=>payload?.metadata?.upper_rotation_horizon===v,value,{timeout:180000});}
 await select(0);
 const zero=await page.evaluate(()=>({window:payload.upper_root_window_forwards,root:payload.upper_root_window_positions,positions:payload.positions,status:document.getElementById('horizonStatus').textContent}));
 for(const rows of zero.window)for(const window of rows)for(const vector of window)for(let a=0;a<3;a++)if(Math.abs(vector[a]-window[0][a])>1e-8)throw Error('Zero did not flatten future orientation');
 if(JSON.stringify(zero.root)!==JSON.stringify(original.root))throw Error('Root positions changed');
 const lower=['pelvis','thigh_l','calf_l','foot_l','ball_l','thigh_r','calf_r','foot_r','ball_r'].map(b=>original.joints.indexOf(b));
 let lowerError=0;for(let r=0;r<original.positions.length;r++)for(let f=0;f<original.positions[r].length;f++)for(const b of lower)for(let a=0;a<3;a++)lowerError=Math.max(lowerError,Math.abs(original.positions[r][f][b][a]-zero.positions[r][f][b][a]));
 if(lowerError>1e-5)throw Error('Lower body moved');
 await select(.5);
 const half=await page.evaluate(()=>payload.upper_root_window_forwards);
 // Retiming half the eight-sample horizon places its last orientation at original R4.
 let halfError=0;for(let r=0;r<half.length;r++)for(let f=0;f<half[r].length;f++)for(let a=0;a<3;a++)halfError=Math.max(halfError,Math.abs(half[r][f][8][a]-original.window[r][f][4][a]));
 if(halfError>1e-7)throw Error('Half-window endpoint mismatch');
 await page.evaluate(()=>{setPlaying(false);frame=21;subframe=0;});
 await page.waitForFunction(()=>window.upperRootWindowDrawn===9);
 await page.screenshot({path:'C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/UpperRootHorizonPreview/window_check.png'});
 const report={zeroStatus:zero.status,rootsDrawn:9,lowerError,halfError,errors};
 require('fs').writeFileSync('Saved/UpperRootHorizonPreview/window_validation.json',JSON.stringify(report,null,2));
 if(errors.length)throw Error(errors.join('\n'));
 await select(1);await page.evaluate(()=>setPlaying(true));await page.bringToFront();
 console.log(JSON.stringify(report));
 page.on('close',()=>browser.close().catch(()=>{}));
})();
