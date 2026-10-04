const fs=require('fs'),path=require('path'),assert=require('assert/strict'),{spawn}=require('child_process');
const {chromium}=require('C:/Users/singerie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const lab='C:/Users/singerie/Documents/Cursor/stepper/training/slashes2/AttackRecoveryLab',store=path.join(__dirname,'angle-default-ui-state-'+crypto.randomUUID()),origin='http://127.0.0.1:8828';
fs.mkdirSync(store,{recursive:true});fs.copyFileSync(path.join(lab,'snapshots/snapshot_0009.json'),path.join(store,'state.json'));
const server=spawn('C:/Users/singerie/Documents/Cursor/stepper/.tools/python310/python.exe',[path.join(lab,'server.py'),'--port','8828','--state-dir',store],{cwd:lab,windowsHide:true,stdio:'ignore'});
const pause=ms=>new Promise(r=>setTimeout(r,ms));let browser;
(async()=>{try{
 for(let i=0;i<50;i++){try{if((await fetch(origin+'/health')).ok)break;}catch{}await pause(100);}
 const token=crypto.randomUUID();await fetch(origin+'/desktop-session',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token})});
 browser=await chromium.launch({headless:true,executablePath:'C:/Users/singerie/AppData/Local/ms-playwright/chromium-1223/chrome-win64/chrome.exe',args:['--enable-webgl','--use-angle=swiftshader']});
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(origin+'/?desktopSession='+token);await page.waitForFunction(()=>window.recoveryLab?.ready);
 const all=await page.evaluate(()=>recoveryLab.state().attackAngleTimeSeconds);assert.equal(Object.keys(all).length,16);assert(Object.values(all).every(x=>x===.29));assert.equal(await page.inputValue('#angleTimeSeconds'),'0.29');
 const source=await page.inputValue('#attack');
 await page.evaluate(()=>{const slider=document.getElementById('angleTimeSeconds');slider.value='2.5';slider.dispatchEvent(new Event('input',{bubbles:true}));});assert.equal(await page.evaluate(()=>recoveryLab.options().angleTimeSeconds),.29);
 await page.evaluate(()=>document.getElementById('angleTimeSeconds').dispatchEvent(new Event('change',{bubbles:true})));assert.equal(await page.evaluate(()=>recoveryLab.options().angleTimeSeconds),2.5);
 await page.selectOption('#attack','pike');await page.waitForFunction(()=>recoveryLab.model()?.clip.name==='pike');assert.equal(await page.inputValue('#angleTimeSeconds'),'0.29');
 await page.selectOption('#attack',source);await page.waitForFunction(a=>recoveryLab.model()?.clip.name===a,source);assert.equal(await page.inputValue('#angleTimeSeconds'),'2.5');
 await Promise.all([page.waitForEvent('load'),page.click('#refresh')]);await page.waitForFunction(()=>window.recoveryLab?.ready);assert.equal(await page.inputValue('#angleTimeSeconds'),'2.5');
 await page.click('#toggleCopyProfile');await page.selectOption('#profileSource',source);await page.click('#profileSelectNone');await page.check('#profileTargets input[value="pike"]');await page.click('#applyProfile');
 await page.selectOption('#attack','pike');await page.waitForFunction(()=>recoveryLab.model()?.clip.name==='pike');assert.equal(await page.inputValue('#angleTimeSeconds'),'2.5');
 await page.click('#idle');const timing=await page.evaluate(()=>({t:recoveryLab.state().time,end:recoveryLab.model().attackSeconds+Recovery.returnTiming(recoveryLab.model(),recoveryLab.options()).duration,max:Number(document.getElementById('timeline').max),phase:document.getElementById('phase').textContent}));assert(Math.abs(timing.t-timing.end)<1e-9);assert(Math.abs(timing.max-timing.end-.35)<1e-9);assert.equal(timing.phase,'Idle');await page.click('#snapshot');await page.waitForFunction(()=>document.getElementById('notice').textContent.startsWith('Saved snapshot_'));const saved=JSON.parse(fs.readFileSync(path.join(store,'snapshots/snapshot_0001.json')));assert.equal(saved.attackAngleTimeSeconds.pike,2.5);assert.equal(saved.attackAngleTimeSeconds.slashR,.29);assert.deepEqual(errors,[]);await page.screenshot({path:__dirname+'/angle-time-ui.png'});console.log('PASS: all 16 defaults 0.29s, release-only commit, per-attack isolation, selection/refresh, copy, snapshot and effective idle/timeline endpoint.');
 }finally{if(browser)await browser.close();server.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
