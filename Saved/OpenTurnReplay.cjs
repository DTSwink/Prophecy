const {chromium}=require('C:/Users/singerie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const browser=await chromium.launch({headless:false,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',args:['--start-maximized']});
 const page=await browser.newPage({viewport:null});
 await page.goto('http://127.0.0.1:8021/turn_parity_temp.html');
 await page.waitForFunction(()=>typeof payload!=='undefined'&&payload?.positions?.length&&playing&&fullVisualisationToggle.checked);
 await page.bringToFront();console.log('Visible Python turn replay is open and playing. Close this browser window when finished.');
 page.on('close',()=>browser.close().catch(()=>{}));
})();
