const {chromium}=require(process.env.HARNESS_PLAYWRIGHT_MODULE||'C:/Users/singerie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),net=require('node:net'),{spawn}=require('node:child_process');
(async()=>{
 const out=process.env.HARNESS_OUTPUT_DIR||path.resolve(__dirname,'../../Saved/Diagnostics/DrawSwordPoint20261014/ui');fs.mkdirSync(out,{recursive:true});
 const store=fs.mkdtempSync(path.join(out,'persistence-'));
 const probe=net.createServer();await new Promise(r=>probe.listen(0,'127.0.0.1',r));const port=probe.address().port;await new Promise(r=>probe.close(r));
 const server=spawn('C:/Users/singerie/Documents/Cursor/stepper/.tools/python310/python.exe',[path.join(__dirname,'backend.py'),'--port',String(port),'--state-dir',store],{windowsHide:true,stdio:'ignore'});
 const url='http://127.0.0.1:'+port;let browser;
 try{
  for(let i=0;;i++){try{if((await fetch(url+'/state')).ok)break;}catch(e){if(i>80)throw e;}await new Promise(r=>setTimeout(r,100));}
  const token='test-'+require('node:crypto').randomUUID();
  assert((await fetch(url+'/desktop-session',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token})})).ok);
  browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',args:['--enable-webgl','--use-angle=swiftshader']});
  const page=await browser.newPage({viewport:{width:1500,height:1050}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(url+'/?desktopSession='+token);await page.waitForFunction(()=>window.holsterLab?.ready);


  await page.selectOption('#action','draw');await page.click('#openFKReturn');
  assert(await page.locator('#fkSwordPoint').isVisible());
  assert.equal(await page.locator('#fk_swordPointSpeed').inputValue(),'0');
  const edit=async(id,value)=>page.locator('#fk_'+id).evaluate((el,v)=>{el.value=String(v);el.dispatchEvent(new Event('change',{bubbles:true}));},value);
  await page.evaluate(()=>{holsterLab.seek(.5);holsterLab.setPlaying(true);});
  await edit('swordPointSpeed',-180);await edit('swordPointExponent',2.5);await edit('swordPointCutoff',.35);
  assert.equal(await page.locator('#play').textContent(),'Pause');
  assert(await page.evaluate(()=>holsterLab.model().swordPoint));
  await page.evaluate(()=>holsterLab.setPlaying(false));
  await page.selectOption('#action','sheathe');assert(!(await page.locator('#fkSwordPoint').isVisible()));
  assert.equal(await page.evaluate(()=>holsterLab.state().parameters.sheatheReturn.swordPointSpeed),0);
  await page.selectOption('#action','draw');assert.equal(await page.locator('#fk_swordPointSpeed').inputValue(),'-180');
  await page.waitForTimeout(450);const saved=await page.evaluate(()=>holsterLab.state());
  await page.reload();await page.waitForFunction(()=>holsterLab?.ready);
  for(const [k,v] of [['swordPointSpeed','-180'],['swordPointExponent','2.5'],['swordPointCutoff','0.35']])assert.equal(await page.locator('#fk_'+k).inputValue(),v);
  await edit('swordPointSpeed',0);assert(!(await page.evaluate(()=>holsterLab.model().swordPoint)));
  await page.evaluate(s=>holsterLab.restore(JSON.parse(JSON.stringify(s))),saved);
  assert.equal(await page.locator('#fk_swordPointSpeed').inputValue(),'-180');
  await page.check('#noCheat');assert(await page.evaluate(()=>holsterLab.model().swordPoint));
  await page.evaluate(()=>holsterLab.seek(holsterLab.model().swordPoint.end/60));
  await page.screenshot({path:path.join(out,'sword-point.png')});
  assert.deepEqual(errors,[]);assert.deepEqual(await page.evaluate(()=>holsterLab.errors),[]);
  console.log('PASS: signed speed/exponent/cutoff, D-only panel, uninterrupted playback, disable, independent settings, disk reload, JSON restore and both planners.');
 }finally{if(browser)await browser.close();server.kill();}
})().catch(e=>{console.error(e);process.exitCode=1;});
