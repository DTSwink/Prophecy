const {chromium}=require('C:/Users/singerie/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),net=require('node:net'),{spawn}=require('node:child_process');
(async()=>{
 const out=path.resolve(__dirname,'../../Saved/Diagnostics/ReachAbsoluteRotation20261015');fs.mkdirSync(out,{recursive:true});
 const store=fs.mkdtempSync(path.join(out,'test-'));
 const old={schema:1,hands:[{enabled:true,grab:false,target:[30,42,120],rotation:[35,15,-20],orientation:'target',speed:120,rotationSpeed:180},{enabled:true,grab:false,target:[-28,42,120],rotation:[-15,0,40],orientation:'target',speed:130,rotationSpeed:180}],phat:true,closure:8,grip:6};
 fs.writeFileSync(path.join(store,'state.json'),JSON.stringify(old));
 const probe=net.createServer();await new Promise(r=>probe.listen(0,'127.0.0.1',r));const port=probe.address().port;await new Promise(r=>probe.close(r));
 const child=spawn('C:/Users/singerie/Documents/Cursor/stepper/.tools/python310/python.exe',[path.join(__dirname,'server.py'),'--port',String(port),'--state-dir',store],{windowsHide:true,stdio:'pipe'});let browser,stderr='';child.stderr.on('data',d=>stderr+=d);
 try{
  for(let i=0;;i++){try{if((await fetch(`http://127.0.0.1:${port}/health`)).ok)break;}catch(e){if(i>60)throw Error(stderr||e);}await new Promise(r=>setTimeout(r,100));}
  const desktopToken=require('node:crypto').randomUUID();await fetch('http://127.0.0.1:'+port+'/desktop-session',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:desktopToken})});
  browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',args:['--enable-webgl','--use-angle=swiftshader']});
  const page=await browser.newPage({viewport:{width:1440,height:960}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(`http://127.0.0.1:${port}/reach?desktopSession=${desktopToken}`);await page.waitForFunction(()=>window.reachLab?.ready);await page.click('#play');await page.waitForFunction(()=>!pending);
  const migrated=await page.evaluate(()=>reachLab.snapshot().settings);assert.equal(migrated.schema,2);
  for(let k=0;k<2;k++){assert.deepEqual(migrated.hands[k].target,old.hands[k].target);assert.equal(migrated.hands[k].speed,old.hands[k].speed);}
  const math=await page.evaluate(old=>{
   const error=(a,b)=>Math.min(Math.hypot(...a.map((v,i)=>v-b[i])),Math.hypot(...a.map((v,i)=>v+b[i])));
   let max=0,count=0;
   for(const x of [-180,-90,-35,0,77,180])for(const y of [-90,-89.999,0,89.999,90])for(const z of [-180,-51,0,90,180]){const q=rotationQ([x,y,z]);max=Math.max(max,error(q,rotationQ(rotationDegrees(q))));count++;}
   return {count,max,migration:old.hands.map((h,k)=>error(R.qm(rotationQ(h.rotation),dataset.base[hands[k]].slice(3)),targetQ(k,pose))),zero:rotationQ([0,0,0]),z90:R.rotate(rotationQ([0,0,90]),[1,0,0])};
  },old);
  assert(math.max<1e-9);assert(math.migration.every(e=>e<1e-12));assert.deepEqual(math.zero,[0,0,0,1]);assert(Math.hypot(math.z90[0],math.z90[1]-1,math.z90[2])<1e-12);
  await page.reload();await page.waitForFunction(()=>reachLab?.ready);assert.deepEqual(await page.evaluate(()=>reachLab.snapshot().settings),migrated,'Migration must not apply twice');
  await page.click('#play');await page.waitForFunction(()=>!pending);await page.uncheck('#phat');
  for(let k=0;k<2;k++)for(let i=0;i<3;i++)await page.fill(`#r${k}${i}`,'0');
  await page.evaluate(async()=>{for(let i=0;i<10;i++)await reachLab.step(8);});
  const zero=await page.evaluate(()=>hands.map(j=>pose[j].slice(3)));for(const q of zero)assert(Math.hypot(...q.slice(0,3))<1e-12&&Math.abs(q[3]-1)<1e-12);
  await page.fill('#r02','90');await page.evaluate(()=>reachLab.step());
  const turn=await page.evaluate(()=>angle(pose[hands[0]].slice(3),[0,0,0,1]));assert(Math.abs(turn-3)<1e-8,'180 deg/s produces a 3 degree step');
  await page.evaluate(async()=>{for(let i=0;i<5;i++)await reachLab.step(8);});await page.fill('#p00','-55');
  await page.evaluate(async()=>{for(let i=0;i<5;i++)await reachLab.step(8);});
  assert((await page.evaluate(()=>angle(pose[hands[0]].slice(3),rotationQ([0,0,90]))))<1e-5,'Translation keeps the same absolute orientation');
  await page.waitForTimeout(350);await page.reload();await page.waitForFunction(()=>reachLab?.ready);assert.equal(await page.inputValue('#r02'),'90');
  await page.screenshot({path:path.join(out,'absolute-controls.png')});assert.deepEqual(errors,[]);
  const result={passed:true,math,migrationPreservesTargets:true,migrationIdempotent:true,zeroIdentityBothHands:true,rotationStepDegrees:turn,translationKeepsOrientation:true,persistence:true,errors};
  fs.writeFileSync(path.join(out,'verification.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 }finally{if(browser)await browser.close();child.kill();}
})().catch(e=>{console.error(e);process.exit(1);});
