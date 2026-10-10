const {chromium}=require(process.env.HARNESS_PLAYWRIGHT_MODULE||'C:/Users/singerie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',args:['--enable-webgl','--use-angle=swiftshader']});
 try{
  // No desktop token: this inspection client cannot write the user's saved state.
  const page=await browser.newPage(),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:8818/');
  await page.waitForFunction(()=>window.holsterLab?.ready);
  await page.evaluate(()=>{
   window.keyLeaks=[];
   for(const type of ['keydown','keyup']){
    document.addEventListener(type,e=>keyLeaks.push('document:'+e.code),true);
    window.addEventListener(type,e=>keyLeaks.push('window:'+e.code),true);
   }
  });
  for(const [tab,id] of [['motion','startTick'],['motion','action'],['motion','orbitYaw'],['motion','timeline'],['motion','start'],['motion','play'],['view','upperOnly']]){
   await page.click('#'+tab+'Tab');
   await page.evaluate(id=>{
    holsterLab.seek(1);
    const el=document.getElementById(id);
    el.focus();window.keyLeaks=[];window.widgetClicks=0;
    el.addEventListener('click',()=>window.widgetClicks++ ,{once:true});
   },id);
   const before=await page.locator('#'+id).evaluate(el=>({value:el.value,checked:el.checked}));
   await page.keyboard.press('ArrowRight');
   assert(Math.abs(await page.evaluate(()=>holsterLab.state().time)-1-1/60)<1e-8,id+' forward');
   await page.keyboard.press('ArrowLeft');
   assert(Math.abs(await page.evaluate(()=>holsterLab.state().time)-1)<1e-8,id+' backward');
   await page.keyboard.down('Space');
   await page.keyboard.down('Space'); // Browser repeat must not toggle a second time.
   assert.equal(await page.locator('#play').textContent(),'Pause',id+' repeat');
   await page.keyboard.up('Space');
   assert.equal(await page.locator('#play').textContent(),'Pause',id+' release');
   await page.keyboard.press('Space');
   assert.equal(await page.locator('#play').textContent(),'Play',id+' pause');
   assert.deepEqual(await page.evaluate(()=>keyLeaks),[],id+' propagation');
   assert.equal(await page.evaluate(()=>widgetClicks),0,id+' native click');
   if(id!=='timeline')assert.deepEqual(await page.locator('#'+id).evaluate(el=>({value:el.value,checked:el.checked})),before,id+' widget value');
  }
  await page.click('#motionTab');
  await page.locator('#startTick').focus();
  await page.evaluate(()=>{holsterLab.seek(1);window.keyLeaks=[];});
  await page.keyboard.down('ArrowRight');await page.keyboard.down('ArrowRight');await page.keyboard.up('ArrowRight');
  assert(Math.abs(await page.evaluate(()=>holsterLab.state().time)-1-2/60)<1e-8,'arrow repeat');
  await page.keyboard.press('7');
  assert((await page.evaluate(()=>keyLeaks)).some(x=>x.endsWith('Digit7')),'ordinary editing key still delivered');
  assert.deepEqual(errors,[]);
  console.log('PASS: playback owns keydown/keyup across numbers, selects, sliders, buttons and checkboxes; Space repeat suppressed, arrow repeat retained, editing keys delivered.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
