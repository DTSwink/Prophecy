const fs=require('fs'),path=require('path'),assert=require('assert/strict'),{spawn}=require('child_process');
const {chromium}=require('C:/Users/singerie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const lab='C:/Users/singerie/Documents/Cursor/stepper/training/slashes2/AttackRecoveryLab',store=path.join(__dirname,'follow-ui-state-'+crypto.randomUUID()),origin='http://127.0.0.1:8828';
fs.mkdirSync(store,{recursive:true});fs.copyFileSync(path.join(lab,'snapshots/snapshot_0009.json'),path.join(store,'state.json'));
const server=spawn('C:/Users/singerie/Documents/Cursor/stepper/.tools/python310/python.exe',[path.join(lab,'server.py'),'--port','8828','--state-dir',store],{cwd:lab,windowsHide:true,stdio:'ignore'});
const pause=ms=>new Promise(r=>setTimeout(r,ms));let browser;
(async()=>{try{
 for(let i=0;i<50;i++){try{if((await fetch(origin+'/health')).ok)break;}catch{}await pause(100);}
 const token=crypto.randomUUID();await fetch(origin+'/desktop-session',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token})});
 browser=await chromium.launch({headless:true,executablePath:'C:/Users/singerie/AppData/Local/ms-playwright/chromium-1223/chrome-win64/chrome.exe',args:['--enable-webgl','--use-angle=swiftshader']});
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(origin+'/?desktopSession='+token);await page.waitForFunction(()=>window.recoveryLab?.ready);
 assert.equal(await page.inputValue('#inertiaHold'),'0');assert.equal(await page.isChecked('#worldInertia'),false);assert.equal(await page.isChecked('#followThrough'),false);assert.equal(await page.inputValue('#inertiaDecay'),'1');assert.equal(await page.isChecked('#worldInertia'),false);assert.equal(await page.isChecked('#followThrough'),false);await page.check('#worldInertia');assert.equal(await page.isChecked('#followThrough'),false);await page.check('#followThrough');
 await page.evaluate(()=>{const e=document.getElementById('inertiaHold');e.value='.25';e.dispatchEvent(new Event('input',{bubbles:true}));});
 assert.equal(await page.evaluate(()=>recoveryLab.options().inertiaHold),0,'drag changed simulation before release');
 await page.evaluate(()=>{for(const [id,value] of [['inertiaHold','.25'],['inertiaDecay','.5']]){const e=document.getElementById(id);e.value=value;e.dispatchEvent(new Event('change',{bubbles:true}));}});
 const selected=await page.inputValue('#attack');
 await Promise.all([page.waitForEvent('load'),page.click('#refresh')]);await page.waitForFunction(()=>window.recoveryLab?.ready);assert.equal(await page.inputValue('#inertiaHold'),'0.25');assert.equal(await page.inputValue('#inertiaDecay'),'0.5');assert.equal(await page.isChecked('#worldInertia'),true);assert.equal(await page.isChecked('#followThrough'),true);
 await page.selectOption('#attack','pike');await page.waitForFunction(()=>recoveryLab.model()?.clip.name==='pike');assert.equal(await page.inputValue('#inertiaHold'),'0');assert.equal(await page.isChecked('#worldInertia'),false);assert.equal(await page.isChecked('#followThrough'),false);
 await page.selectOption('#attack',selected);await page.waitForFunction(name=>recoveryLab.model()?.clip.name===name,selected);assert.equal(await page.inputValue('#inertiaHold'),'0.25');
 await page.click('#toggleCopyProfile');await page.selectOption('#profileSource',selected);await page.check('#profileTargets input[value="pike"]');await page.click('#applyProfile');
 await page.selectOption('#attack','pike');await page.waitForFunction(()=>recoveryLab.model()?.clip.name==='pike');assert.equal(await page.inputValue('#inertiaHold'),'0.25');assert.equal(await page.inputValue('#inertiaDecay'),'0.5');assert.equal(await page.isChecked('#worldInertia'),true);assert.equal(await page.isChecked('#followThrough'),true);
 await page.click('#snapshot');await page.waitForFunction(()=>document.getElementById('notice').textContent.startsWith('Saved snapshot_'));
 const s=JSON.parse(fs.readFileSync(path.join(store,'snapshots/snapshot_0001.json')));assert.equal(s.attackInertiaTiming.pike.hold,.25);assert.equal(s.attackInertiaTiming.pike.world,true);assert.equal(s.controls.worldInertia,true);assert.equal(s.attackInertiaTiming.pike.follow,true);assert.equal(s.controls.followThrough,true);assert.equal(s.controls.inertiaDecay,'0.5');
 await page.screenshot({path:path.join(__dirname,'follow-ui.png')});assert.deepEqual(errors,[]);console.log('PASS: follow-through and world checkboxes, legacy defaults, slider commit, refresh persistence, per-attack isolation, profile copy, snapshot timing, no browser errors.');
 }finally{if(browser)await browser.close();server.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
