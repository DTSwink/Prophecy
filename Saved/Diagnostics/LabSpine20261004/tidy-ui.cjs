const fs=require('fs'),path=require('path'),assert=require('assert/strict'),{spawn}=require('child_process');
const {chromium}=require('C:/Users/singerie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const lab='C:/Users/singerie/Documents/Cursor/stepper/training/slashes2/AttackRecoveryLab',store=path.join(__dirname,'tidy-ui-state-'+crypto.randomUUID()),origin='http://127.0.0.1:8828';
fs.mkdirSync(store,{recursive:true});fs.copyFileSync(path.join(lab,'snapshots/snapshot_0009.json'),path.join(store,'state.json'));
const server=spawn('C:/Users/singerie/Documents/Cursor/stepper/.tools/python310/python.exe',[path.join(lab,'server.py'),'--port','8828','--state-dir',store],{cwd:lab,windowsHide:true,stdio:'ignore'});
const pause=ms=>new Promise(r=>setTimeout(r,ms));let browser;
(async()=>{try{
 for(let i=0;i<50;i++){try{if((await fetch(origin+'/health')).ok)break;}catch{}await pause(100);}
 const token=crypto.randomUUID();await fetch(origin+'/desktop-session',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token})});
 browser=await chromium.launch({headless:true,executablePath:'C:/Users/singerie/AppData/Local/ms-playwright/chromium-1223/chrome-win64/chrome.exe',args:['--enable-webgl','--use-angle=swiftshader']});
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(origin+'/?desktopSession='+token);await page.waitForFunction(()=>window.recoveryLab?.ready);
 const before=await page.evaluate(()=>recoveryLab.state());
 await page.selectOption('#returnMethod','spring');await page.selectOption('#inertiaSpace','world');
 assert.equal(await page.evaluate(()=>recoveryLab.options().springReturn),true);assert.equal(await page.evaluate(()=>recoveryLab.options().worldInertia),true);assert.equal(await page.isHidden('#inertiaHoldControls'),true);
 await page.click('#durationPlus');assert(Math.abs((await page.evaluate(()=>recoveryLab.options().duration))-Number(before.controls.duration)-.01)<1e-9);await page.click('#durationMinus');
 await page.click('#viewTab');assert.equal(await page.isVisible('#upperOnly'),true);assert.equal(await page.isHidden('#duration'),true);await page.selectOption('#gizmoSide','l');
 await Promise.all([page.waitForEvent('load'),page.click('#refresh')]);await page.waitForFunction(()=>window.recoveryLab?.ready);assert.equal(await page.getAttribute('#viewTab','aria-selected'),'true');assert.equal(await page.inputValue('#gizmoSide'),'l');
 await page.click('#motionTab');assert.equal(await page.inputValue('#returnMethod'),'spring');assert.equal(await page.inputValue('#inertiaSpace'),'world');
 const previousTime=await page.evaluate(()=>recoveryLab.state().time);await page.locator('#returnMethod').focus();await page.keyboard.press('ArrowRight');assert((await page.evaluate(()=>recoveryLab.state().time))>previousTime);assert.equal(await page.inputValue('#returnMethod'),'spring');
 if(await page.isHidden('#boneInertiaPanel'))await page.click('#toggleBoneInertia');assert.equal(await page.isVisible('#boneInertiaPanel'),true);
 await Promise.all([page.waitForEvent('load'),page.click('#refresh')]);await page.waitForFunction(()=>window.recoveryLab?.ready);assert.equal(await page.isVisible('#boneInertiaPanel'),true);
 await page.setViewportSize({width:1440,height:900});await page.screenshot({path:path.join(__dirname,'ui-tidy-wide.png')});
 await page.setViewportSize({width:1280,height:720});await page.screenshot({path:path.join(__dirname,'ui-tidy-laptop.png')});
 for(const id of ['snapshot','refresh','spineTurn','attack','variant','play','next','returnMethod','duration','toggleBoneInertia']){const box=await page.locator('#'+id).boundingBox();assert(box&&box.y>=0&&box.y+box.height<=720,'unreachable main control '+id);}
 assert(await page.evaluate(()=>document.body.scrollWidth<=innerWidth),'horizontal page overflow');
 await page.click('#closeBoneInertia');await page.click('#libraryTab');assert.equal(await page.isVisible('#snapshots'),true);assert.equal(await page.isHidden('#removeVariant'),true);
 await page.click('#motionTab');await page.selectOption('#returnMethod','blend');assert.equal(await page.isVisible('#inertiaHoldControls'),true);assert.equal(await page.locator('label[for=returnEasing]').textContent(),'Easing');
 await page.setViewportSize({width:1024,height:768});await page.click('#toggleBoneInertia');await page.screenshot({path:path.join(__dirname,'ui-tidy-small.png')});for(const id of ['play','next','armed','hit','tail','idle','speed']){const b=await page.locator('#'+id).boundingBox();assert(b.x+b.width<=784&&b.y+b.height<=768,'small-screen playback clipped '+id);}
 assert.deepEqual(errors,[]);console.log('PASS: method/space wiring, time increments, tab and panel refresh persistence, playback keyboard ownership, conditional controls, compact layouts, library safeguards, no browser errors.');
 }finally{if(browser)await browser.close();server.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
