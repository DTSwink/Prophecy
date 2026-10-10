const assert=require('node:assert/strict');
const H=require('./holster.js'),data=require('./data/motions.json'),setup=require('./data/unreal-setup.json');
for(const motion of ['idle','walk'])for(const sheathe of [true,false]){
 const m=H.prepare(data,setup,{motion,sheathe,shrinkPercent:70,duration:8});
 assert(m.completionTick>m.o.startTick&&m.playbackDuration<8);
 assert.equal(m.playbackDuration,m.completionTick/60);
 assert.equal(m.frames.at(-1).phase,sheathe?'Holstered':'Held');
 assert(m.frames.at(-2).active);
 assert.deepEqual(H.sample(m,8),H.sample(m,m.playbackDuration));
 assert.equal(m.o.duration,8,'configured duration preserved');
}
for(const opts of [{shrinkPercent:10,spineClavicleAngleLimit:0},{startTick:600},{maxReachSpeed:.01}]){
 const m=H.prepare(data,setup,{...opts,duration:4});
 assert.equal(m.completionTick,null);assert.equal(m.playbackDuration,4);
}
const {chromium}=require(process.env.HARNESS_PLAYWRIGHT_MODULE||'C:/Users/singerie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',args:['--enable-webgl','--use-angle=swiftshader']});
 try{
  const page=await browser.newPage();
  await page.goto('http://127.0.0.1:8818/'); // Read-only inspection; no desktop token.
  await page.waitForFunction(()=>window.holsterLab?.ready);
  await page.evaluate(()=>holsterLab.restore({schema:'sword_holster_lab_v1',parameters:{...Holster.defaults,shrinkPercent:70},time:8}));
  const end=await page.evaluate(()=>holsterLab.model().playbackDuration);
  assert.equal(await page.evaluate(()=>holsterLab.state().time),end);
  assert.equal(Number(await page.locator('#timeline').getAttribute('max')),end);
  assert.equal(await page.locator('#duration').inputValue(),'8');
  await page.click('#start');await page.click('#end');
  assert.equal(await page.evaluate(()=>holsterLab.state().time),end);
  await page.keyboard.press('ArrowRight');
  assert.equal(await page.evaluate(()=>holsterLab.state().time),0);
  await page.keyboard.press('ArrowLeft');
  assert.equal(await page.evaluate(()=>holsterLab.state().time),end);
  await page.selectOption('#speed','2');await page.keyboard.press('Space');
  await page.waitForFunction(end=>holsterLab.state().time<end,end,{timeout:3000});
  await page.keyboard.press('Space');
  assert.deepEqual(await page.evaluate(()=>holsterLab.errors),[]);
  console.log('PASS: completion clamps draw/sheath idle/walk; stalls retain limit; seek, timeline, End, stepping and playback loop use effective end; configured limit preserved.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
